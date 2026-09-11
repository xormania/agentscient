#!/usr/bin/env python3
"""Receipts: a claim anyone can re-derive, written per ``evidence.cue``.

Verbs:
    receipt.py record --claim TEXT [--cwd REL] [--allow-dirty] -- ARGV...
    receipt.py verify RECEIPT
    receipt.py show RECEIPT

``record`` runs ARGV at CWD (relative to the repository root), captures
exit code, both outputs and their digests, the head the tree was at and
whether it was dirty, and writes a ``#Receipt`` to
``.dev/records/receipts/<digest>.json`` whose name is the canonical
digest of the receipt itself. Exit 0 when the command passed, 1 when it
failed (the receipt is written either way: a red receipt is evidence),
2 on a refusal, one stderr line on the wire.

``verify`` re-runs a receipt's command at the recorded head and compares
exit code and output digests: 0 when they agree, 1 naming each field that
differs, 2 when the tree is not at the recorded head.

Adapted from the previous repository's workflow engine (``wf red``,
``wf green``, ``wf verify``): the receipt shape is the contract's closed
struct, not the engine's event; the store is a directory of files, not a
chain. The modules under ``receipt/`` are that engine's, verbatim.

Adaptations declared in the extraction checklist
(``.dev/ladder-inputs/extraction-checklist-receipts-20260911.md``):
``head_sha`` is the sha256 of the commit id's hex, since the contract wants
a 64-hex digest and git here gives 40; ``cwd`` is repository-relative;
``actor`` is ``WF_AGENT``; the refusal wire is this lane's.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "receipt"))
import canonical  # noqa: E402
import receipts  # noqa: E402
from errors import Refusal  # noqa: E402

RECEIPTS_DIR = Path(".dev") / "records" / "receipts"
FIELDS = ("kind", "claim", "argv", "cwd", "head_sha", "tree_dirty", "exit_code",
          "duration_ms", "stdout_sha256", "stderr_sha256", "actor", "at")


class Refused(Exception):
    pass


def refuse(kind, expected, found, needed):
    def clean(value):
        return " ".join(str(value).split())[:500]
    raise Refused(f"{kind}: expected {clean(expected)}; found {clean(found)}; needed {clean(needed)}")


def identity():
    value = os.environ.get("WF_AGENT", "").strip()
    if not value or "<" not in value or not value.endswith(">"):
        refuse("identity", "WF_AGENT as Name <address> for a writing verb", value or "absent identity",
               "export WF_AGENT='Name <address>'")
    return value


def repo_root(start: Path) -> Path:
    proc = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        refuse("repository", "a git work tree", str(start), "run inside a clone")
    return Path(proc.stdout.strip())


def head_digest(repo: Path) -> str:
    proc = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        refuse("head", "a commit at HEAD", "no commit", "commit once before recording a receipt")
    return hashlib.sha256(proc.stdout.strip().encode("ascii")).hexdigest()


def dirty_paths(repo: Path) -> list[str]:
    """Paths that differ from HEAD, the receipts directory itself excluded."""
    raw = subprocess.run(["git", "-C", str(repo), "status", "--porcelain=v1", "-z", "--untracked-files=normal"],
                         capture_output=True, text=True, check=False).stdout
    own = RECEIPTS_DIR.as_posix() + "/"
    fields = [f for f in raw.split("\0") if f]
    out, index = [], 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        status, path = entry[:2], entry[3:]
        if status[0] in ("R", "C"):
            index += 1
        if not path.startswith(own) and path != RECEIPTS_DIR.as_posix():
            out.append(path)
    return sorted(out)


def relative_cwd(repo: Path, cwd: str) -> str:
    candidate = Path(cwd)
    if candidate.is_absolute():
        refuse("cwd", "a path relative to the repository root", cwd, "give the path relative to the root")
    target = (repo / candidate).resolve()
    if not target.is_relative_to(repo.resolve()) or not target.is_dir():
        refuse("cwd", "a directory inside the repository", cwd, "give a directory under the root")
    return target.relative_to(repo.resolve()).as_posix() or "."


def write_receipt(repo: Path, body: dict) -> tuple[str, Path]:
    digest = canonical.digest(body)
    directory = repo / RECEIPTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.json"
    path.write_text(canonical.dumps(body) + "\n", encoding="utf-8")
    return digest, path


def load_receipt(repo: Path, ref: str) -> tuple[dict, Path]:
    path = Path(ref)
    if not path.is_file():
        path = repo / RECEIPTS_DIR / (ref if ref.endswith(".json") else f"{ref}.json")
    if not path.is_file():
        refuse("receipt", "a receipt file or digest under " + RECEIPTS_DIR.as_posix(), ref, "name a recorded receipt")
    try:
        body = canonical.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        refuse("receipt", "canonical JSON", f"{path}: {error}", "restore the receipt bytes")
    missing = [f for f in FIELDS if f not in body]
    extra = [k for k in body if k not in FIELDS]
    if body.get("kind") != "receipt" or missing or extra:
        refuse("receipt", "the twelve fields of #Receipt", f"kind={body.get('kind')!r} missing={missing} extra={extra}",
               "a receipt written by this lever")
    return body, path


def cmd_record(args) -> int:
    actor = identity()
    if not args.argv:
        refuse("arguments", "a command after --", "no command", "record --claim TEXT -- ARGV...")
    repo = repo_root(Path.cwd())
    cwd = relative_cwd(repo, args.cwd)
    dirty = dirty_paths(repo)
    if dirty and not args.allow_dirty:
        refuse("dirty", "a clean tree, so the receipt names a commit", f"{len(dirty)} changed path(s): {' '.join(dirty[:5])}",
               "commit first, or --allow-dirty to record tree_dirty true (not admissible)")
    head = head_digest(repo)
    code, out, err, duration = receipts.run(list(args.argv), repo / cwd)
    body = {
        "kind": "receipt",
        "claim": args.claim,
        "argv": list(args.argv),
        "cwd": cwd,
        "head_sha": head,
        "tree_dirty": bool(dirty),
        "exit_code": int(code),
        "duration_ms": int(duration),
        "stdout_sha256": canonical.sha256_hex(out.encode("utf-8", "replace")),
        "stderr_sha256": canonical.sha256_hex(err.encode("utf-8", "replace")),
        "actor": actor,
        "at": canonical.now(),
    }
    digest, path = write_receipt(repo, body)
    print(f"receipt {digest} exit={code} head={head[:8]} dirty={str(bool(dirty)).lower()} "
          f"path={path.relative_to(repo).as_posix()}")
    return 0 if code == 0 else 1


def cmd_verify(args) -> int:
    repo = repo_root(Path.cwd())
    body, path = load_receipt(repo, args.receipt)
    head = head_digest(repo)
    if head != body["head_sha"]:
        refuse("state", f"the tree at the recorded head {body['head_sha'][:8]}", f"head {head[:8]}",
               "check out the recorded commit, then verify")
    code, out, err, _duration = receipts.run(list(body["argv"]), repo / body["cwd"])
    differences = []
    if int(code) != body["exit_code"]:
        differences.append(f"exit_code recorded {body['exit_code']} now {code}")
    for name, text in (("stdout_sha256", out), ("stderr_sha256", err)):
        now = canonical.sha256_hex(text.encode("utf-8", "replace"))
        if now != body[name]:
            differences.append(f"{name} recorded {body[name][:8]} now {now[:8]}")
    if differences:
        print(f"differs {path.stem}: " + "; ".join(differences))
        return 1
    print(f"verified {path.stem} exit={code}")
    return 0


def cmd_show(args) -> int:
    repo = repo_root(Path.cwd())
    body, _path = load_receipt(repo, args.receipt)
    print(canonical.dumps(body))
    return 0


def parser():
    p = argparse.ArgumentParser(add_help=False)
    verbs = p.add_subparsers(dest="verb")
    rec = verbs.add_parser("record", add_help=False)
    rec.add_argument("--claim", required=True)
    rec.add_argument("--cwd", default=".")
    rec.add_argument("--allow-dirty", action="store_true")
    rec.add_argument("argv", nargs=argparse.REMAINDER)
    rec.set_defaults(run=cmd_record)
    ver = verbs.add_parser("verify", add_help=False)
    ver.add_argument("receipt")
    ver.set_defaults(run=cmd_verify)
    show = verbs.add_parser("show", add_help=False)
    show.add_argument("receipt")
    show.set_defaults(run=cmd_show)
    return p


def main(argv=None) -> int:
    args, unknown = parser().parse_known_args(argv)
    try:
        if unknown or not getattr(args, "run", None):
            refuse("arguments", "record, verify or show", " ".join(unknown or (argv or sys.argv[1:])) or "nothing",
                   "choose one documented verb")
        if args.verb == "record" and args.argv and args.argv[0] == "--":
            args.argv = args.argv[1:]
        return args.run(args)
    except Refused as error:
        print(str(error), file=sys.stderr)
        return 2
    except Refusal as error:
        print(f"command: expected {error.precondition}; found {error.actual}; needed {error.needed}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
