#!/usr/bin/env python3
"""The §13 acceptance bar, as commands that run.

Every item in PLAN §13's bar is one check here, each building a throwaway
git repository, driving the real ``wf.py`` through it, and reporting what it
observed.  The PR body's Evidence section is generated from these — a figure
in a document is a recollection unless a command produced it at the moment
of writing.

    acceptance.py                 run every item, print the table, exit 1 on any failure
    acceptance.py --only LABEL    run one item and print its observation

An item that cannot run reports ERROR and is never counted as a pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import support
import canonical

CHECKS = {}


def check(label):
    def register(fn):
        CHECKS[label] = fn
        return fn
    return register


class Walked:
    """A sandbox driven to a chosen point of the tdd gate."""

    def __init__(self):
        self.sb = support.Sandbox()
        self.sb.seed_project()
        self.sb.wf("init", check=0)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "acceptance",
                   check=0)

    def to_red(self):
        self.sb.wf("advance", "WO-001", check=0)
        return self

    def to_impl(self):
        self.to_red()
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=0)
        self.sb.wf("advance", "WO-001", check=0)
        return self

    def close(self):
        self.sb.destroy()


# -- the agent contract ----------------------------------------------------


@check("exit-map-usage-is-64")
def _usage():
    sb = support.Sandbox()
    try:
        sb.wf("init", check=0)
        codes = {
            "unknown verb": sb.wf("nosuchverb").returncode,
            "missing option": sb.wf("open", "--kind", "tdd").returncode,
            "no verb": sb.wf().returncode,
        }
        ok = set(codes.values()) == {64}
        return ok, f"usage errors exit {sorted(set(codes.values()))} (argparse's own default is 2)"
    finally:
        sb.destroy()


@check("exit-map-refusal-is-1")
def _refusal():
    sb = support.Sandbox()
    try:
        sb.wf("init", check=0)
        code = sb.wf("status", "WO-404").returncode
        return code == 1, f"an unknown work order exits {code}"
    finally:
        sb.destroy()


@check("exit-map-integrity-is-2")
def _integrity():
    walk = Walked().to_impl()
    try:
        chain = walk.sb.chain_file("WO-001")
        support.plant_bytes(
            chain, lambda raw: raw.replace(b'"acceptance"', b'"acceptanke"'),
            expect="edit",
            recognisable=lambda raw: support.jsonl_lines(raw) > 3,
        )
        code = walk.sb.wf("verify").returncode
        return code == 2, f"a corrupted export exits {code}"
    finally:
        walk.close()


@check("json-everywhere")
def _json_everywhere():
    sb = support.Sandbox()
    try:
        sb.wf("init", check=0)
        sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=0)
        verbs = (["init"], ["next"], ["status"], ["status", "WO-001"],
                 ["log", "WO-001"], ["verify"], ["export"])
        bad = []
        for argv in verbs:
            out = sb.wf("--json", *argv, check=0).stdout.strip()
            if out != canonical.dumps(json.loads(out)):
                bad.append(argv[0])
        return not bad, f"{len(verbs)} verbs emit canonical JSON under --json"
    finally:
        sb.destroy()


@check("zero-interactive-prompts")
def _no_prompts():
    # §13 names `grep -rn 'input(' ops/devlane/workflow`, which matches five
    # things that are not prompts: two test method names ending in _input(,
    # this checker's own grep argument, and PLAN.md's own sentence. Parsing
    # the AST answers the question the bar was asking — does any module
    # *call* input() — instead of approximating it.
    import ast

    calls, scanned = [], 0
    for path in sorted(support.WF_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in ("input", "raw_input"):
                calls.append(f"{path.name}:{node.lineno}")
    naive = subprocess.run(
        ["grep", "-rn", "input(", "ops/devlane/workflow"], capture_output=True, text=True
    )
    naive_hits = len([ln for ln in naive.stdout.splitlines() if ln.strip()])
    return not calls, (
        f"0 calls to input() in {scanned} python files (AST); §13's literal grep"
        f" matches {naive_hits}, all of them method names, this checker's own"
        " grep argument, and PLAN.md's own sentence"
    )


# -- red ------------------------------------------------------------------


@check("red-refuses-a-passing-command")
def _red_refuses():
    walk = Walked().to_red()
    try:
        walk.sb.make_green()
        proc = walk.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV)
        ok = proc.returncode == 1 and "the test command fails" in proc.stderr
        return ok, f"exit {proc.returncode}, refused: the test command fails"
    finally:
        walk.close()


@check("red-records-a-failing-command")
def _red_records():
    walk = Walked().to_red()
    try:
        body = json.loads(
            walk.sb.wf("--json", "red", "WO-001", "--",
                       *support.Sandbox.GATE_ARGV, check=0).stdout
        )
        ok = body["satisfied"] == ["receipt.red"] and body["exit_code"] != 0
        return ok, (f"exit 0, receipt.red recorded with exit_code {body['exit_code']}"
                    f" over {body['manifest_files']} in-scope files")
    finally:
        walk.close()


# -- green ----------------------------------------------------------------


@check("green-refuses-a-changed-manifest")
def _green_manifest():
    walk = Walked().to_impl()
    try:
        walk.sb.make_green()
        walk.sb.write("crates/demo/tests/gate.py",
                      support.Sandbox.GATE_SOURCE + "# deselected\n")
        walk.sb.commit_all("acceptance: change a frozen test")
        proc = walk.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV)
        ok = proc.returncode == 1 and "equals the frozen set" in proc.stderr
        return ok, f"exit {proc.returncode}, refused: the test manifest equals the frozen set"
    finally:
        walk.close()


@check("green-refuses-a-changed-argv")
def _green_argv():
    walk = Walked().to_impl()
    try:
        walk.sb.make_green()
        proc = walk.sb.wf("green", "WO-001", "--",
                          *support.Sandbox.GATE_ARGV, "--extra")
        ok = proc.returncode == 1 and "same command the bound red recorded" in proc.stderr
        return ok, f"exit {proc.returncode}, refused: green runs the same command the bound red recorded"
    finally:
        walk.close()


@check("green-refuses-a-dirty-tree")
def _green_dirty():
    walk = Walked().to_impl()
    try:
        walk.sb.make_green()
        walk.sb.write("scratch.txt", "uncommitted\n")
        proc = walk.sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV)
        ok = proc.returncode == 1 and "working tree is clean" in proc.stderr
        return ok, f"exit {proc.returncode}, refused: the working tree is clean (D3)"
    finally:
        walk.close()


@check("green-records-on-a-clean-match")
def _green_records():
    walk = Walked().to_impl()
    try:
        walk.sb.make_green()
        body = json.loads(
            walk.sb.wf("--json", "green", "WO-001", "--",
                       *support.Sandbox.GATE_ARGV, check=0).stdout
        )
        ok = body["satisfied"] == ["receipt.green"] and body["exit_code"] == 0
        return ok, (f"exit 0, receipt.green bound to red seq {body['red_seq']}"
                    f" against frozen set {body['test_manifest_sha256'][:12]}")
    finally:
        walk.close()


# -- the full walk ---------------------------------------------------------


@check("full-walk-to-terminal")
def _full_walk():
    walk = Walked().to_impl()
    sb = walk.sb
    try:
        sb.make_green()
        sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=0)
        sb.wf("advance", "WO-001", check=0)
        sb.wf("outcome", "WO-001", "accepted", "--by", "reviewer", check=0)
        body = json.loads(
            sb.wf("--json", "outcome", "WO-001", "ratified", "--by", "owner",
                  check=0).stdout
        )
        stages = [
            e["stage"] for e in json.loads(
                sb.wf("--json", "log", "--full", "--all", "WO-001", check=0).stdout
            )["events"] if e["type"] == "stage.entered"
        ]
        ok = stages == ["spec", "red", "impl", "review", "ratify"] and body[
            "applied_effect"] is None
        return ok, ("open -> red -> advance -> green -> advance -> outcome:"
                    f" stages {' -> '.join(stages)}; the owner-reserved"
                    " 'ratified' recorded with its effect withheld (D10)")
    finally:
        walk.close()


@check("verify-deep-green-after-the-walk")
def _verify_deep():
    walk = Walked().to_impl()
    sb = walk.sb
    try:
        sb.make_green()
        sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=0)
        sb.wf("advance", "WO-001", check=0)
        sb.wf("outcome", "WO-001", "accepted", "--by", "reviewer", check=0)
        proc = sb.wf("--json", "verify", "--deep")
        body = json.loads(proc.stdout) if proc.returncode == 0 else {}
        entry = (body.get("work_orders") or [{}])[0]
        ok = proc.returncode == 0
        return ok, (f"exit {proc.returncode}: {body.get('events')} events,"
                    f" {entry.get('receipts', {}).get('checked')} receipts re-hashed"
                    f" from their trees, {entry.get('cross_binds', {}).get('bound')}"
                    f" cross-binds, {entry.get('append_only', {}).get('versions')}"
                    " append-only versions")
    finally:
        walk.close()


@check("rebuild-reproduces-byte-identical-chains")
def _rebuild():
    walk = Walked().to_impl()
    sb = walk.sb
    try:
        sb.make_green()
        sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=0)
        sb.wf("advance", "WO-001", check=0)
        sb.wf("outcome", "WO-001", "accepted", "--by", "reviewer", check=0)
        before = {p.name: p.read_bytes() for p in sorted((sb.root / "chains").iterdir())}
        attempts_before = {
            p.name: p.read_bytes() for p in sorted((sb.root / "attempts").iterdir())
        }
        sb.db.unlink()
        sb.wf("init", "--rebuild", check=0)
        after = {p.name: p.read_bytes() for p in sorted((sb.root / "chains").iterdir())}
        attempts_after = {
            p.name: p.read_bytes() for p in sorted((sb.root / "attempts").iterdir())
        }
        written = json.loads(sb.wf("--json", "export", check=0).stdout)["written"]
        ok = before == after and attempts_before == attempts_after and written == []
        lines = sum(support.jsonl_lines(v) for v in after.values())
        return ok, (f"{lines} chain line(s) and {len(attempts_after)} attempt file(s)"
                    " byte-identical after init --rebuild; re-export writes nothing")
    finally:
        walk.close()


# -- the planted-fault suite ----------------------------------------------


def _planted(mutate, *, expect_code=2, expect_text="", **plant_kwargs):
    walk = Walked().to_impl()
    try:
        sb = walk.sb
        sb.wf("verify", check=0)      # the fixture must be sound before planting
        mutate(sb, plant_kwargs)
        proc = sb.wf("verify", "--deep")
        detected = proc.returncode == expect_code and expect_text in (
            proc.stderr + proc.stdout
        )
        return detected, f"exit {proc.returncode}"
    finally:
        walk.close()


@check("planted-corrupted-payload-byte")
def _p_corrupt():
    def mutate(sb, _):
        support.plant_bytes(
            sb.chain_file("WO-001"),
            lambda raw: raw.replace(b'"acceptance"', b'"acceptanke"'),
            expect="edit",
            recognisable=lambda raw: support.jsonl_lines(raw) > 3,
        )
    ok, code = _planted(mutate, expect_text="diverges from the recorded payload bytes")
    return ok, f"{code}: the exported chain diverges from the recorded payload bytes"


@check("planted-dropped-row")
def _p_dropped():
    walk = Walked().to_impl()
    sb = walk.sb
    try:
        sb.wf("verify", check=0)
        path = sb.chain_file("WO-001")
        total = support.jsonl_lines(path.read_bytes())
        support.plant_bytes(
            path,
            lambda raw: b"\n".join(
                [ln for ln in raw.split(b"\n") if ln.strip()][:1]
                + [ln for ln in raw.split(b"\n") if ln.strip()][2:]
            ) + b"\n",
            expect="shrink",
            recognisable=lambda raw: support.jsonl_lines(raw) == total - 1,
        )
        sb.db.unlink()
        rebuild = sb.wf("init", "--rebuild")
        # And the follow-on: a rebuild that failed part-way must not leave a
        # database that verifies vacuously over an export it never read.
        after = sb.wf("verify")
        ok = (rebuild.returncode == 2
              and "not contiguous" in rebuild.stderr
              and after.returncode == 2
              and "missing a work order the export records" in after.stderr)
        return ok, (f"init --rebuild exits {rebuild.returncode} (chain is not"
                    f" contiguous); a follow-up verify exits {after.returncode}"
                    " rather than passing over the empty database it left")
    finally:
        walk.close()


@check("planted-rewritten-indexed-column")
def _p_column():
    def mutate(sb, _):
        support.plant_sql(
            sb.db,
            "UPDATE events SET time='2099-01-01T00:00:00.000000Z'"
            " WHERE wo_id='WO-001' AND seq=2",
            check=lambda c: c.execute(
                "SELECT COUNT(*) FROM events WHERE wo_id='WO-001'"
            ).fetchone()[0] > 3,
        )
    ok, code = _planted(mutate, expect_text="disagrees with the hashed payload")
    return ok, f"{code}: stored column disagrees with the hashed payload"


@check("planted-broken-prev-link")
def _p_prev():
    def mutate(sb, _):
        row = json.loads(sb.wf("--json", "log", "--full", "--all", "WO-001", check=0).stdout)["events"][2]
        forged = dict(row)
        forged["prev"] = "0" * 63 + "1"
        forged["hash"] = canonical.digest(
            {k: v for k, v in forged.items() if k != "hash"}
        )
        support.plant_sql(
            sb.db,
            "UPDATE events SET payload=?, prev=?, hash=? WHERE wo_id='WO-001' AND seq=3",
            (canonical.dumps(forged), forged["prev"], forged["hash"]),
            check=lambda c: c.execute(
                "SELECT COUNT(*) FROM events WHERE wo_id='WO-001'"
            ).fetchone()[0] > 3,
        )
    ok, code = _planted(mutate, expect_text="prev does not link")
    return ok, f"{code}: prev does not link to the preceding event"


@check("planted-non-canonical-re-encoding")
def _p_canon():
    def mutate(sb, _):
        row = json.loads(sb.wf("--json", "log", "--full", "--all", "WO-001", check=0).stdout)["events"][1]
        spaced = json.dumps(row, sort_keys=True, separators=(", ", ": "))
        support.plant_sql(
            sb.db,
            "UPDATE events SET payload=? WHERE wo_id='WO-001' AND seq=2",
            (spaced,),
            check=lambda c: c.execute(
                "SELECT COUNT(*) FROM events WHERE wo_id='WO-001'"
            ).fetchone()[0] > 3,
        )
    ok, code = _planted(mutate, expect_text="not in canonical form")
    return ok, f"{code}: stored payload is not in canonical form (same value, different bytes)"


@check("planted-edited-gate-kind-spec")
def _p_spec():
    def mutate(sb, _):
        support.plant_bytes(
            sb.root / "gate-kinds" / "tdd.json",
            lambda raw: raw.replace(
                b'"leave_requires": ["receipt.red"]', b'"leave_requires": []'
            ),
            expect="shrink",
            recognisable=lambda raw: canonical.loads(raw).get("kind") == "tdd",
        )
        sb.commit_all("acceptance: edit tdd@1 in place")
        sb.wf("init", check=0)
    ok, code = _planted(mutate, expect_text="edited in place")
    return ok, f"{code}: a registered gate-kind version was edited in place"


@check("planted-voided-frozen-set")
def _p_frozen():
    walk = Walked().to_impl()
    sb = walk.sb
    try:
        before = json.loads(sb.wf("--json", "status", "WO-001", check=0).stdout)
        sealed = before["frozen"]["manifest_sha256"]
        sb.make_green()
        sb.wf("advance", "WO-001", "--to", "red", "--reason", "spec changed", check=0)
        after = json.loads(sb.wf("--json", "status", "WO-001", check=0).stdout)
        proc = sb.wf("green", "WO-001", "--", *support.Sandbox.GATE_ARGV)
        ok = after["frozen"] is None and proc.returncode == 1
        return ok, (f"seal {sealed[:12]} voided on re-entry; green then exits"
                    f" {proc.returncode} — the stale seal is unusable")
    finally:
        walk.close()


@check("planted-truncated-tail-needs-the-prefix-walk")
def _p_tail():
    """The one a per-row check cannot see (PLAN §3.6)."""
    walk = Walked().to_impl()
    sb = walk.sb
    try:
        committed = sb._git("show", "HEAD:ops/devlane/workflow/chains/WO-001.jsonl")
        total = len([ln for ln in committed.splitlines() if ln.strip()])
        support.plant_bytes(
            sb.chain_file("WO-001"),
            lambda raw: b"\n".join(
                [ln for ln in raw.split(b"\n") if ln.strip()][: total - 1]
            ) + b"\n",
            expect="shrink",
            recognisable=lambda raw: support.jsonl_lines(raw) == total - 1,
        )
        sb.commit_all("acceptance: truncate the chain")
        sb.db.unlink()
        sb.wf("init", "--rebuild", check=0)
        shallow = sb.wf("verify").returncode
        deep = sb.wf("verify", "--deep").returncode
        return shallow == 0 and deep == 2, (
            f"shallow verify exits {shallow} (the chain is internally perfect);"
            f" verify --deep exits {deep} via the append-only prefix walk"
        )
    finally:
        walk.close()


# -- runner ----------------------------------------------------------------


def run_one(label):
    fn = CHECKS[label]
    try:
        ok, observation = fn()
    except Exception as exc:  # a check that cannot run has no result to report
        return "ERROR", f"{type(exc).__name__}: {exc}"
    return ("PASS" if ok else "FAIL"), observation


def main():
    parser = argparse.ArgumentParser(description="the PLAN §13 acceptance bar")
    parser.add_argument("--only", default=None, help="run a single labelled item")
    parser.add_argument("--list", action="store_true", help="list the labels")
    args = parser.parse_args()

    if args.list:
        for label in CHECKS:
            print(label)
        return 0

    labels = [args.only] if args.only else list(CHECKS)
    if args.only and args.only not in CHECKS:
        print(f"unknown item: {args.only}", file=sys.stderr)
        return 64

    worst = 0
    for label in labels:
        status, observation = run_one(label)
        if status != "PASS":
            worst = 1
        if args.only:
            print(observation)
        else:
            print(f"{status}  {label}: {observation}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
