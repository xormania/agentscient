"""Test support: sandboxes, and fault planting that proves it landed.

The planted-fault suite is the acceptance bar (PLAN §13).  A plant that
silently fails to land leaves a clean fixture, and the assertion afterwards
answers a question about nothing — confidently, and in whichever direction
happens to be wrong.  So every plant here proves two properties:

* the fixture **differs** from clean, and
* it is **still recognisably the fixture** — not empty, not half destroyed.

A byte comparison alone misses the second: a clobbered file *did* change.
When a plant cannot prove both, it raises :class:`PlantFailed`, which
surfaces as a unittest *error* rather than a pass or a failure — a case
whose precondition was never met has no result to report.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WF_DIR = Path(__file__).resolve().parent.parent
if str(WF_DIR) not in sys.path:
    sys.path.insert(0, str(WF_DIR))

WF_PY = WF_DIR / "wf.py"


class PlantFailed(Exception):
    """A fault could not be proven to have landed intact."""


def _describe(label: str, before: bytes, after: bytes) -> str:
    return f"{label}: {len(before)} bytes before, {len(after)} bytes after"


def plant_bytes(path, mutate, *, expect: str = "edit", recognisable=None) -> bytes:
    """Rewrite ``path`` through ``mutate``, proving the fault landed intact.

    ``expect`` is what the plant claims to do to the file's size — ``edit``
    (same length), ``shrink``, or ``grow``.  Declaring it is what catches an
    anchor that moved: a substitution that matched nothing keeps the length
    *and* the bytes, and only the byte comparison catches that; a truncating
    self-read empties the file, and only the size band catches that.
    """
    path = Path(path)
    before = path.read_bytes()
    if not before:
        raise PlantFailed(f"fixture {path} was already empty before planting")

    after = mutate(before)
    if not isinstance(after, (bytes, bytearray)):
        raise PlantFailed(f"mutate() returned {type(after).__name__}, not bytes")
    after = bytes(after)

    if after == before:
        raise PlantFailed(
            f"plant changed nothing in {path} — the anchor did not match "
            f"({len(before)} bytes, unchanged)"
        )
    if not after:
        raise PlantFailed(f"plant emptied {path} — that is a clobber, not a fault")

    if expect == "edit" and len(after) != len(before):
        raise PlantFailed(_describe(f"plant claimed an in-place edit of {path}", before, after))
    if expect == "shrink" and len(after) >= len(before):
        raise PlantFailed(_describe(f"plant claimed to shrink {path}", before, after))
    if expect == "grow" and len(after) <= len(before):
        raise PlantFailed(_describe(f"plant claimed to grow {path}", before, after))
    if expect not in ("edit", "shrink", "grow"):
        raise PlantFailed(f"unknown expect={expect!r}")

    if recognisable is not None and not recognisable(after):
        raise PlantFailed(
            f"plant left {path} unrecognisable as the fixture "
            f"({len(before)} bytes before, {len(after)} after)"
        )

    path.write_bytes(after)
    landed = path.read_bytes()
    if landed != after:
        raise PlantFailed(f"plant did not reach disk for {path}")
    return before


MUTATING_TABLE = re.compile(
    r"\b(?:UPDATE|DELETE\s+FROM|INSERT\s+INTO)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def _table_digest(conn, table: str) -> str:
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def plant_sql(db_path, sql: str, params=(), *, expect_rows: int = 1, check=None) -> None:
    """Run one mutating statement, proving it changed what it claimed to.

    ``rowcount`` alone is not a landing proof.  It counts the rows the WHERE
    clause *matched*, not the rows whose content changed, and SQLite reports
    a match for an UPDATE that assigns the value already stored — so a plant
    that mutates nothing would report success.  The table's contents are
    digested before and after and required to differ.

    The mutation runs inside a transaction and is rolled back unless every
    property holds, so a rejected plant leaves the fixture exactly as it was
    — the same discipline ``plant_bytes`` gets by checking before it writes.
    """
    match = MUTATING_TABLE.search(sql)
    if not match:
        raise PlantFailed(f"plant_sql cannot tell which table this mutates: {sql}")
    table = match.group(1)

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        before = _table_digest(conn, table)
        conn.execute("BEGIN IMMEDIATE")
        touched = conn.execute(sql, params).rowcount
        after = _table_digest(conn, table)

        problem = None
        if touched != expect_rows:
            problem = f"plant touched {touched} rows, expected {expect_rows}: {sql}"
        elif after == before:
            problem = (
                f"plant changed no content in {table} — the rows it matched already "
                f"held the values it set: {sql}"
            )
        elif check is not None and not check(conn):
            problem = f"plant left the database unrecognisable: {sql}"

        if problem:
            conn.execute("ROLLBACK")
            raise PlantFailed(problem)
        conn.execute("COMMIT")
    finally:
        conn.close()


def relink_chain(wo_id, events):
    """Re-link a mutated chain so every *per-row* check passes again.

    Recomputes seq, prev, the replayed state hash and the event hash for
    every event, so the result is internally consistent: hashes verify,
    links join, the projection matches. This is the coordinated rewrite the
    shallow pass cannot see — the plant that leaves only the repository-side
    checks (manifest re-hash, cross-binds, the prefix walk) able to catch it.

    Without it, a forged payload breaks the chain immediately and a test
    asserting "verify failed" would be passing for the wrong reason.
    """
    import canonical
    import chain as chainmod

    state = chainmod.initial_state(wo_id)
    prev = canonical.ZERO_DIGEST
    out = []
    for index, event in enumerate(events, 1):
        event = {k: v for k, v in event.items() if k != "hash"}
        event["seq"] = index
        event["prev"] = prev
        state = chainmod.apply_event(state, event, index)
        event["state_sha256"] = canonical.digest(state)
        event["hash"] = chainmod.event_hash(event)
        prev = event["hash"]
        out.append(event)
    return out


def chain_bytes_for(events) -> bytes:
    import canonical

    return b"".join(canonical.dumpb(event) + b"\n" for event in events)


def assert_runnable(case, advances):
    """PLAN §4 promises `next` gives the exact argv that advances a work order.

    Assert the promise, not the spelling: argv[0] must resolve to something
    executable and argv[1] must be a file that exists. Asserting a literal
    like ["wf", ...] is how a command nobody could run passed for weeks —
    no `wf` binary is installed anywhere.
    """

    case.assertTrue(advances, "there is nothing to run")
    case.assertIsNotNone(shutil.which(advances[0]),
                         f"argv[0] {advances[0]!r} is not on PATH")
    if advances[0] in ("python3", "python"):
        case.assertTrue(Path(advances[1]).exists(),
                        f"argv[1] {advances[1]!r} does not exist")
    return advances


def without_binds(events):
    """Events excluding commit.landed.

    Every chain-appending verb auto-commits (D5) and the commit is bound into
    the chain afterwards, so a bind trails each verb. Tests about what a verb
    *recorded* filter them out; tests about the bind itself do not.
    """
    return [e for e in events if e.get("type") != "commit.landed"]


def jsonl_lines(raw: bytes) -> int:
    """Number of non-empty lines — the cheap 'still a chain file' predicate."""
    return len([ln for ln in raw.split(b"\n") if ln.strip()])


class Sandbox:
    """A throwaway git repo with a ``wf`` state root inside it."""

    def __init__(self, gate_kinds=("tdd", "artifact")):
        self.dir = Path(tempfile.mkdtemp(prefix="wf-sandbox-"))
        self.root = self.dir / "ops" / "devlane" / "workflow"
        (self.root / "gate-kinds").mkdir(parents=True)
        for kind in gate_kinds:
            src = WF_DIR / "gate-kinds" / f"{kind}.json"
            shutil.copy(src, self.root / "gate-kinds" / f"{kind}.json")
        # The seeded specs register checks by repo-relative script path, so a
        # sandbox running those specs needs the scripts as well as the specs.
        checks_src = WF_DIR / "checks"
        if checks_src.is_dir():
            shutil.copytree(checks_src, self.root / "checks")
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "sandbox@example.invalid")
        self._git("config", "user.name", "sandbox")
        self._git("config", "commit.gpgsign", "false")
        self._git("config", "core.hooksPath", "/dev/null")
        self._git("config", "core.excludesFile", "/dev/null")
        # The repo's own tracked .gitignore, not a hand-written stand-in: a
        # test asserting "the lock file is gitignored" must be asserting it
        # about the rules the real repo ships, or it proves nothing.
        shutil.copy(WF_DIR.parents[2] / ".gitignore", self.dir / ".gitignore")
        self._git("add", "-A")
        self._git("commit", "-qm", "sandbox: seed")

    # -- git ---------------------------------------------------------------

    def _git(self, *args) -> str:
        out = subprocess.run(
            ("git", "-C", str(self.dir)) + args,
            capture_output=True, text=True, check=True,
        )
        return out.stdout

    def head(self) -> str:
        return self._git("rev-parse", "HEAD").strip()

    def log(self, n: int = 20) -> str:
        return self._git("log", "--oneline", f"-{n}")

    # -- wf ----------------------------------------------------------------

    #: A complete Co-Authored-By identity: wf refuses a bare name, because
    #: the value becomes a commit trailer.
    AGENT = "Test Agent <noreply@example.invalid>"

    def wf(self, *args, agent: str | None = None, check: int | None = None,
           raw: bool = False):
        """Run the real ``wf.py`` against this sandbox."""
        env = dict(os.environ)
        env["WF_AGENT"] = self.AGENT if agent is None else agent
        env.pop("GIT_DIR", None)
        args = list(map(str, args))
        if not raw:
            args = self._with_default_source(args)
        proc = subprocess.run(
            [sys.executable, str(WF_PY), "--root", str(self.root), *args],
            capture_output=True, text=True, cwd=str(self.dir), env=env,
        )
        if check is not None and proc.returncode != check:
            raise AssertionError(
                f"wf {' '.join(map(str, args))} exited {proc.returncode}, expected {check}\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
        return proc

    #: Verbs that record caller-authored text and therefore require --source.
    SOURCED_VERBS = ("open", "outcome", "marker")

    def _with_default_source(self, args):
        """Supply --source for the verbs that require it.

        Keeps the several dozen call sites readable. The requirement itself
        is not assumed away: SourceProvenance in test_cli_basics asserts the
        refusal directly, so this default cannot hide a regression.
        """
        if any(a == "--source" or a.startswith("--source=") for a in args):
            return args
        # Keyed on the *verb*, not on any argument: "wf marker WO-1 open F1"
        # contains "open" as the action, and matching that injected --source
        # into marker-open but not marker-close.
        takes_a_value = {"--root", "--agent", "--source"}
        verb, skip = None, False
        for arg in args:
            if skip:
                skip = False
                continue
            if arg.startswith("-"):
                if arg in takes_a_value:
                    skip = True
                continue
            verb = arg
            break
        if verb in self.SOURCED_VERBS:
            return args + ["--source", "original"]
        return args

    # A tree shaped like the seeded tdd@1 scope: one harness file and one
    # test file, so the manifest is non-empty and both scopes are exercised.
    GATE_SOURCE = (
        "import pathlib, sys\n"
        "sys.exit(0 if pathlib.Path('src.txt').exists() else 1)\n"
    )

    def seed_project(self) -> str:
        self.write("Cargo.toml", '[package]\nname = "demo"\n')
        self.write("crates/demo/tests/gate.py", self.GATE_SOURCE)
        return self.commit_all("sandbox: seed project")

    def make_green(self) -> str:
        """Make the seeded gate command pass, without touching test scope."""
        self.write("src.txt", "implemented\n")
        return self.commit_all("sandbox: implement")

    def make_red(self) -> str:
        """Return the seeded gate command to failing, without touching scope."""
        (self.dir / "src.txt").unlink(missing_ok=True)
        return self.commit_all("sandbox: un-implement")

    GATE_ARGV = ["python3", "crates/demo/tests/gate.py"]

    def write(self, relpath: str, text: str) -> Path:
        path = self.dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def commit_all(self, message: str = "sandbox: change") -> str:
        self._git("add", "-A")
        self._git("commit", "-qm", message)
        return self.head()

    @property
    def db(self) -> Path:
        return self.root / "wf.db"

    def chain_file(self, wo: str) -> Path:
        return self.root / "chains" / f"{wo}.jsonl"

    def destroy(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


class SandboxCase(unittest.TestCase):
    """Base case that builds and tears down a sandbox per test."""

    gate_kinds = ("tdd", "artifact")

    def setUp(self):
        self.sb = Sandbox(gate_kinds=self.gate_kinds)
        self.addCleanup(self.sb.destroy)
