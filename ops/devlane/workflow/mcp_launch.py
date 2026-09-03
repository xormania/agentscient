#!/usr/bin/env python3
"""Prepare the cache, then hand over to the read-only server.

The database is a gitignored cache (D1) — the tracked export is the evidence
— so a fresh clone has no database, and the server cannot build one because
building one is a write. Before this existed, the first tool call on a clone
answered `no such table: work_orders`.

The split is the point: **this** writes, the server does not. It runs
`wf init --rebuild`, which reconstructs the cache from the tracked export and
originates no evidence, and then `exec`s the server — replacing itself, so
nothing that can write is even in the process afterwards.

A rebuild that fails is reported on stderr and does not stop the handover:
the server then answers with the refusal naming what to run, which is more
useful than a server that never starts.

    python3 mcp_launch.py --root ops/devlane/workflow
"""

from __future__ import annotations

import argparse
import sqlite3
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def classify_cache(db_path: Path) -> str:
    """How the cache relates to the tracked export: the export is the
    evidence (D1), the database a cache of it, and there are exactly three
    honest answers.

    - "match":   the cache is the export — serve it.
    - "rebuild": missing, schema-only, behind, or divergent — rebuild from
      the export (the evidence wins), preserving coordination.
    - "ahead":   the cache holds a verified extension of the export. Chains
      are append-only, so this is what un-flushed --no-commit work looks
      like — and ALSO what a switch to a branch with a shorter chain looks
      like. The two are indistinguishable here, and rebuilding would
      silently destroy recorded events in the first case, so ahead is
      never rebuilt: the server refuses queries and names the two ways to
      reconcile (flush with `wf commit`, or discard with `init --rebuild`).
      "Ahead" wins over "rebuild" when both appear: after the flush, the
      next launch sees plain "rebuild" and heals the rest.

    A lower-bound count was not enough (a pull that appended kept the file
    count identical), and neither was per-chain counts alone (a shorter or
    divergent tracked chain still satisfied ">="). The comparison is now
    the exported tail: line count AND the hash of the last exported line.
    """
    import json as _json

    if not db_path.exists():
        return "rebuild"
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return "rebuild"
    try:
        if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='work_orders'"
        ).fetchone() is None:
            return "rebuild"
        rows = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        counts = dict(conn.execute(
            "SELECT wo_id, COUNT(*) FROM events GROUP BY wo_id"))
        def cached_hashes(wo):
            return dict(conn.execute(
                "SELECT seq, hash FROM events WHERE wo_id = ?", (wo,)))
        chains = db_path.parent / "chains"
        exported = len(list(chains.glob("*.jsonl"))) if chains.is_dir() else 0
        if rows < exported:
            return "rebuild"
        verdicts = set()
        seen = set()
        if chains.is_dir():
            for path in chains.glob("*.jsonl"):
                wo = path.name[: -len(".jsonl")]
                seen.add(wo)
                lines = [row for row in path.read_bytes().split(b"\n")
                         if row.strip()]
                if not lines:
                    continue
                # Every exported line, not just the tail: the file's own
                # hash chain makes mid-file divergence impossible on the
                # export side, but a corrupt CACHE can disagree mid-chain
                # while its tail still matches — and we are already reading
                # every line to count them.
                cached = cached_hashes(wo)
                n_c = counts.get(wo, 0)
                try:
                    exported_hashes = [
                        _json.loads(row).get("hash") for row in lines]
                except ValueError:
                    verdicts.add("rebuild")
                    continue
                if n_c < len(lines) or any(
                        cached.get(seq) != h
                        for seq, h in enumerate(exported_hashes, start=1)):
                    verdicts.add("rebuild")
                elif n_c > len(lines):
                    verdicts.add("ahead")
        if set(counts) - seen:
            verdicts.add("ahead")   # a work order opened but never exported
    except sqlite3.Error:
        return "rebuild"
    finally:
        conn.close()
    if "ahead" in verdicts:
        return "ahead"
    if "rebuild" in verdicts:
        return "rebuild"
    return "match"


def usable_cache(db_path: Path) -> bool:
    """The launcher's question: is there a cache that must not be rebuilt?
    Both "match" and "ahead" answer yes — rebuilding either loses state."""
    return classify_cache(db_path) != "rebuild"


def save_coordination(db_path: Path) -> dict:
    """Claims and sessions from the old cache, or {} when unreadable."""
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    out = {}
    try:
        for table in ("claims", "sessions"):
            cursor = conn.execute(f"SELECT * FROM {table}")
            names = [c[0] for c in cursor.description]
            out[table] = (names, cursor.fetchall())
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    return out


def restore_coordination(db_path: Path, saved: dict) -> None:
    """Best-effort reinsert. A claim on a work order the fresh export no
    longer knows is dropped by the foreign key — correctly."""
    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return
    try:
        for table, (names, rows) in saved.items():
            marks = ", ".join("?" for _ in names)
            for row in rows:
                try:
                    conn.execute(
                        f"INSERT OR IGNORE INTO {table} ({', '.join(names)})"
                        f" VALUES ({marks})", row)
                except sqlite3.Error:
                    continue
        conn.commit()
    finally:
        conn.close()


def rebuild_lock(root: Path):
    """An exclusive lock so concurrent launches do not rebuild over each other.

    `init --rebuild` unlinks the database. Two launchers could both pass the
    cache check and then destroy each other's work: 24 simultaneous launchers
    against a tracked work order lost it in 3 runs out of 3, leaving a
    schema-only cache behind.

    Best-effort by design — on a platform without fcntl the launcher still
    works, it just races again. The lock lives beside wf.db, which is
    gitignored, so it never dirties the tree.
    """
    try:
        import fcntl
    except ImportError:          # pragma: no cover - not POSIX
        return None
    # NOT a context manager: the open handle IS the lock, and
    # closing it at the end of a with-block releases it.
    handle = open(root / "wf.db.lock", "w")  # noqa: SIM115
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="prepare and serve wf status")
    parser.add_argument("--root", default=str(HERE))
    args, passthrough = parser.parse_known_args(argv)

    root = Path(args.root)
    # Serialised, and the cache re-checked *under* the lock: the loser of the
    # race must see the winner's finished rebuild rather than start its own.
    lock = rebuild_lock(root)  # noqa: F841 — the binding holds
    # the fcntl lock open; dropping it releases it and revives the
    # concurrent-rebuild race this function exists to prevent.
    if usable_cache(root / "wf.db"):
        # Do NOT rebuild. `init --rebuild` unlinks wf.db, and claims and
        # sessions are deliberately absent from the export (PLAN §8) — so
        # rebuilding as a side effect of *starting a reader* silently frees
        # work another agent holds. A two-hour claim became null after one
        # launch. Losing coordination state on a rebuild is correct when
        # somebody asks for a rebuild; it is not correct as a consequence of
        # opening a status server.
        os.execv(sys.executable, [  # noqa: S606 — replacing this
            # process with the server is the whole job
            sys.executable, str(HERE / "mcp_server.py"), "--root", args.root,
            *passthrough,
        ])

    # An automatic rebuild must not lose coordination: claims and sessions
    # are deliberately absent from the export, and destroying them as a side
    # effect of freshening a stale cache is the same P1 as destroying them
    # on launch. An EXPLICIT `wf init --rebuild` still resets them — asking
    # for a rebuild is asking for that; starting a reader is not.
    coordination = save_coordination(root / "wf.db")
    rebuild = subprocess.run(
        [sys.executable, str(HERE / "wf.py"), "--root", args.root,
         "init", "--rebuild", "--json"],
        capture_output=True, text=True, check=False)
    if rebuild.returncode == 0 and coordination:
        restore_coordination(root / "wf.db", coordination)
    if rebuild.returncode != 0:
        # stderr reaches the client's MCP log. The server still starts — a
        # silent non-start is the worse failure — but it will refuse every
        # query and say what to run: the rebuild is atomic (wf.py rebuild
        # builds into a temp and renames only on success), so a failure
        # leaves no partial database to serve from.
        print(f"mcp_launch: init --rebuild exited {rebuild.returncode}; "
              f"the server will refuse queries: "
              f"{rebuild.stderr.strip()[:300]}", file=sys.stderr)

    os.execv(sys.executable, [  # noqa: S606 — replacing this process
        # with the server is the whole job
        sys.executable, str(HERE / "mcp_server.py"), "--root", args.root,
        *passthrough,
    ])


if __name__ == "__main__":
    sys.exit(main())
