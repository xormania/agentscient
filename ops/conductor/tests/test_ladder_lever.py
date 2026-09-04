"""Ladder-driver acceptance tests, written from the unit 2 contract.

Contract (only): the dispatch input `contract-ladder-driver.md` (scope
plus plan §3) and the inherited
`ops/conductor/instrument-conventions.md`. The tools
`ops/conductor/tools/ladder.py` and `ops/bin/ladder.sh` are the
subject and are not read here. Tests invoke the staged copy as a
subprocess inside a scratch git repository whose `ops/` carries stub
levers; a stub `gh` sits first on PATH. No environment knob selects
the stubs — the driver must locate levers relative to the worktree.

The named branch is checked out in a linked worktree; the driver is
invoked from a different checkout so a cwd-relative driver fails.
The live dispatch store and this repo must stay untouched — asserted
in tearDown.

The implementation lands in a later run. A missing tool file is one
red (`test_the_tool_files_are_present`). Every other case stages a
copy-tool-bytes stand-in so a missing file is not every test's
failure: when the tool exists its bytes are copied and run; when it
does not, a no-op stub (exit 0, no output) is planted so each
assertion goes red on the contract promise rather than Python's
missing-file exit 2.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "ladder.py"
SHIM = REPO / "ops" / "bin" / "ladder.sh"
LANECONF = REPO / "ops" / "conductor" / "tools" / "laneconf.py"

BRANCH = "lane/ladder-aa32"
SLUG = "ladder-aa32"
TRUNK = "trunkx"
RELEASE = "relx"
REPO_SLUG = "org/projx"
CHECK_NAME = "checkx"
LANE_NAME = "lanex"
WORKTREE_ROOT = "wt-ladder-aa32"
MODEL_GROK = "ladder-model-grok-aa32"
MODEL_CODEX = "ladder-model-codex-aa32"
MODEL_CODEX_SECURITY = "ladder-model-codex-security-aa32"
MODEL_CLAUDE_READ = "ladder-model-claude-read-aa32"
MODEL_CLAUDE_PLAN = "ladder-model-claude-plan-aa32"
EFFORT_GROK = "ladder-effort-grok-aa32"
EFFORT_CODEX = "ladder-effort-codex-aa32"
EFFORT_CLAUDE = "ladder-effort-claude-aa32"
ADDRESS_GROK = "noreply-grok@example.invalid"
ADDRESS_CODEX = "noreply-codex@example.invalid"
ADDRESS_CLAUDE = "noreply-claude@example.invalid"
RAN_GROK = "grok-ran-aa32"
RAN_CODEX = "codex-ran-aa32"
AGENT = "Ladder Tester <ladder-tester@example.invalid>"
REPO_USER = "Scratch Owner"
REPO_EMAIL = "scratch-owner@example.invalid"
LANE_AUTHOR = "Lane Owner <lane-owner@example.invalid>"
SCOPE_FIRST = "SCOPE_FIRST_LINE_aa32 the slice pointer"
IMPLEMENT_LINE = "IMPLEMENT_ENVELOPE_LINE_aa32 unique"
IMPLEMENT_BODY = "IMPL_ENVELOPE_BODY_aa32 unique in envelope not in markers"
TEST_ALPHA = "ops/conductor/tests/test_alpha.py"
TEST_BETA = "ops/conductor/tests/test_beta.py"
TEST_RELAY = "packages/relay/spec/test_relay.py"
SKEPTIC_BODY = "SKEPTIC_MD_BODY_aa32 the skeptic report"
CHECK_TESTS_FINDING_CLAIM = "CHECK_TESTS_FINDING_CLAIM_aa32 quotation pair"
CHECK_TESTS_FINDING_REPRO = (
    "python3 -m unittest discover -s ops/conductor/tests -p test_alpha.py"
)
CHECK_TESTS_FINDING = {
    "severity": "p2",
    "where": "ops/conductor/tests/test_alpha.py §test_ok",
    "claim": CHECK_TESTS_FINDING_CLAIM,
    "reproduce": CHECK_TESTS_FINDING_REPRO,
}
PR_URL = "https://example.invalid/org/projx/pull/7"
NOT_A_URL = "not-a-url"
PWN_ARTIFACT = "tests/test_ok.py; printf PWNED; #.py"
HELPER_UNDER_TESTS = "ops/conductor/tests/conftest.py"
OUTSIDE_BUCKET = "ops/pwn-aa32.sh"
RUN_CAP = 60
SLICE_M = "ladder-driver-slice"
BUCKET_S1 = "land-flags"
BUCKET_S2 = "ladder-driver"

ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)

JOBS = (
    "author-tests",
    "check-tests",
    "implement",
    "security-audit",
    "adversarial-review",
)

STAGE_NAMES = (
    "tests",
    "check-tests",
    "tests-fix",
    "code",
    "security",
    "adversarial",
    "fix-tests",
    "fix-code",
    "security-re",
    "pr",
)

WRITE_STAGES = frozenset(
    {"tests", "tests-fix", "code", "code-2", "fix-tests", "fix-code"}
)
WITHHELD_STAGES = ("tests", "check-tests", "tests-fix", "fix-tests")

QUOTED_LITERALS = (
    "'dev'",
    '"dev"',
    "'master'",
    '"master"',
    "'main'",
    '"main"',
    "'../wt'",
    '"../wt"',
    "'ci'",
    '"ci"',
    f"'{MODEL_GROK}'",
    f'"{MODEL_GROK}"',
    f"'{MODEL_CODEX}'",
    f'"{MODEL_CODEX}"',
    f"'{MODEL_CODEX_SECURITY}'",
    f'"{MODEL_CODEX_SECURITY}"',
)

DEFAULT_PLAN = "# plan\nunit 2 named files for the ladder driver\n"

BUCKET_PLAN = (
    "# plan\n"
    "unit 2 named files for the ladder driver\n"
    f"slice\t{SLICE_M}\tM\n"
    f"bucket\t{BUCKET_S1}\tS\t"
    "ops/conductor/tools/land.py ops/conductor/land-lever.md\n"
    f"bucket\t{BUCKET_S2}\tS\t"
    "ops/conductor/tools/ladder.py ops/bin/ladder.sh\n"
)

_JOB_DIR = re.compile(r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$")


def stage_model_effort(name: str) -> tuple[str, str]:
    grok = (MODEL_GROK, EFFORT_GROK)
    codex = (MODEL_CODEX, EFFORT_CODEX)
    security = (MODEL_CODEX_SECURITY, EFFORT_CODEX)
    mapping = {
        "tests": grok,
        "check-tests": codex,
        "tests-fix": grok,
        "code": codex,
        "code-2": codex,
        "security": security,
        "adversarial": grok,
        "fix-tests": grok,
        "fix-code": codex,
        "security-re": security,
    }
    return mapping[name]


def _store_snap(path: Path) -> tuple[str, tuple[str, ...]]:
    if not path.exists():
        return ("absent", ())
    if not path.is_dir():
        return ("other", ())
    return ("dir", tuple(sorted(p.name for p in path.iterdir())))


def _without_new_job_dirs(before, after):
    kept = {}
    for key, (kind, names) in after.items():
        if kind == "dir" and key in before and before[key][0] == "dir":
            previous = set(before[key][1])
            names = tuple(
                n for n in names
                if n in previous or not _JOB_DIR.match(n)
            )
        kept[key] = (kind, names)
    return kept


def _live_store_paths() -> list[Path]:
    paths: list[Path] = []
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        paths.append(Path(xdg) / "agentscient" / "dispatch")
    paths.append(Path.home() / ".local" / "state" / "agentscient" / "dispatch")
    snap = REPO.resolve()
    if snap.name == "snapshot":
        job = snap.parent
        if job.parent.name == "dispatch":
            paths.append(job.parent)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path if not path.exists() else path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _git_out(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"{args} in {cwd}: {proc.stderr}")
    return proc.stdout


DISPATCH_PY = r'''
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
REPO = Path("@@REPO@@")
argv = sys.argv[1:]
log = STUB / "dispatch-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
plant_path = STUB / "plant.json"
plant = json.loads(plant_path.read_text(encoding="utf-8"))
plant.setdefault("cwds", []).append(os.getcwd())
plant.setdefault("script_paths", []).append(str(Path(__file__).resolve()))


def conf_map():
    keys = {}
    text = (REPO / "ops" / "lane.conf").read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        keys[name] = value.strip().strip("'")
    return keys


def flag(name, default=None):
    key = "--" + name
    if key in argv:
        i = argv.index(key)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


job = flag("job", "")
harness = flag("harness", "")
stage = flag("stage", "")
dry = "--dry-run" in argv
conf = conf_map()


def resolve_model():
    explicit = flag("model")
    if explicit:
        return explicit
    if job == "security-audit":
        return conf.get("MODEL_CODEX_SECURITY_AUDIT") or conf.get("MODEL_CODEX")
    if harness == "grok":
        return conf.get("MODEL_GROK")
    if harness == "codex":
        return conf.get("MODEL_CODEX")
    if harness == "claude":
        if job == "plan":
            return conf.get("MODEL_CLAUDE_PLAN")
        return conf.get("MODEL_CLAUDE_READ")
    return conf.get("MODEL_GROK")


def resolve_effort():
    explicit = flag("effort")
    if explicit:
        return explicit
    if harness == "grok":
        return conf.get("EFFORT_GROK")
    if harness == "codex":
        return conf.get("EFFORT_CODEX")
    if harness == "claude":
        return conf.get("EFFORT_CLAUDE")
    return conf.get("EFFORT_GROK")


model = resolve_model()
effort = resolve_effort()
launch_argv = [
    str(REPO / "ops" / "devlane" / "dispatch" / "launch.py"),
    job,
    "--harness", harness or "",
    "--model", model or "",
    "--effort", effort or "",
    "--stage", stage or "",
]
if dry:
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps({"argv": launch_argv, "env": {}}) + "\n")
    raise SystemExit(0)

seen = [c.get("name") for c in plant.get("calls", [])]


def logical_name():
    if job == "author-tests" and stage == "tests":
        if "adversarial" in seen or "security" in seen:
            return "fix-tests"
        if "check-tests" in seen:
            return "tests-fix"
        return "tests"
    if job == "implement" and stage == "code":
        if "fix-tests" in seen or "fix-code" in seen:
            return "fix-code"
        code_n = sum(
            1 for info in (plant.get("records") or {}).values()
            if (info or {}).get("name") == "code"
            or str((info or {}).get("name") or "").startswith("code-")
        )
        if code_n == 0:
            return "code"
        return "code-" + str(code_n + 1)
    if job == "security-audit" and stage == "review":
        minted = [
            (info or {}).get("name")
            for info in (plant.get("records") or {}).values()
        ]
        if "fix-code" in seen or "fix-tests" in seen or "security" in minted:
            return "security-re"
        return "security"
    if job == "check-tests":
        return "check-tests"
    if job == "adversarial-review":
        return "adversarial"
    return job + ":" + stage + ":" + str(len(seen) + 1)


name = logical_name()
plant.setdefault("calls", []).append(
    {"name": name, "job": job, "stage": stage, "argv": argv}
)
if "--detach" not in argv:
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stderr.write(
        "arguments: expected --detach; found a wait-and-hold dispatch; "
        "needed pass --detach\n"
    )
    raise SystemExit(3)
if name in plant.get("refuse_stages", []) or job in plant.get("refuse_jobs", []):
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stderr.write(
        "job: expected a mint; found a refusal; needed a dispatchable job\n"
    )
    raise SystemExit(3)

seq = plant.get("n", 0) + 1
plant["n"] = seq
rec_id = "20260904T120000Z-" + (stage or "stage") + "-" + (harness or "h") + "-aa" + f"{seq:02d}" + "32"
verdicts = plant.get("verdicts", {})
verdict = verdicts.get(name, "approve")
artifacts = {}
if name == "tests":
    if plant.get("empty_artifacts"):
        artifacts = {}
    else:
        artifacts = dict(plant.get("artifacts", {}))
if name == "check-tests" and plant.get("skeptic_md"):
    body = plant.get("skeptic_text") or "SKEPTIC_MD_BODY_aa32 the skeptic report"
    dest = REPO / "SKEPTIC.md"
    dest.write_text(body, encoding="utf-8")
    artifacts["skeptic"] = str(dest)
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        lane = conf.get("LANE_NAME") or "lanex"
        outp = Path(xdg) / lane / "dispatch" / rec_id / "out" / "SKEPTIC.md"
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(body, encoding="utf-8")
        artifacts["skeptic"] = str(outp)
mismatch = name in plant.get("model_mismatch_stages", [])
effort_mismatch = name in plant.get("effort_mismatch_stages", [])
requested = "wrong-model-aa32" if mismatch else model
effort_requested = "wrong-effort-aa32" if effort_mismatch else effort
ran = plant.get("ran_" + (harness or ""), (harness or "h") + "-ran-aa32")
note = None
if name == "code" or str(name).startswith("code-"):
    note = "IMPLEMENT_ENVELOPE_LINE_aa32 unique"
    artifacts["body"] = "IMPL_ENVELOPE_BODY_aa32 unique in envelope not in markers"
if plant.get("leak_implement_into") == name:
    note = "IMPLEMENT_ENVELOPE_LINE_aa32 unique"
notes = plant.get("notes") or {}
if name in notes:
    note = notes[name]
findings = list((plant.get("stage_findings") or {}).get(name) or [])
if plant.get("leak_implement_into_findings") == name:
    findings.append({
        "severity": "p2",
        "where": "planted",
        "claim": "IMPL_ENVELOPE_BODY_aa32 unique in envelope not in markers",
        "reproduce": None,
    })


def counts_for(items):
    counts = {"p1": 0, "p2": 0, "p3": 0, "opinions": 0}
    for item in items:
        if not item.get("reproduce"):
            counts["opinions"] += 1
            continue
        sev = item.get("severity")
        if sev in ("p1", "p2", "p3"):
            counts[sev] += 1
        else:
            counts["opinions"] += 1
    return counts


tripping = name in plant.get("trip_stages", [])
crashing = name in plant.get("crash_stages", [])
walling = name in plant.get("wait_wall_stages", [])
envelope = {
    "job": job,
    "status": "ok",
    "verdict": verdict,
    "counts": counts_for(findings),
    "findings": findings,
    "artifacts": artifacts,
    "spend": {"harness": harness, "total": 0, "out": 0, "runs": 0},
    "stamp": {"ref": "planted", "started": None, "ended": None},
    "note": note,
}
record = {
    "id": rec_id,
    "lane": "dev",
    "stage": stage,
    "unit": flag("unit") or "lane/ladder-aa32",
    "lineage": {
        "branch": flag("branch") or "lane/ladder-aa32",
        "base_sha": "0" * 40,
    },
    "follows": [],
    "job": job,
    "role": "write" if job in ("author-tests", "implement") else "read",
    "dispatched_by": "stub",
    "at": {
        "launched": "2026-09-04T12:00:00Z",
        "closed": None,
    },
    "snapshot": {
        "mode": "whole",
        "ref_name": "HEAD",
        "ref_sha": "0" * 40,
        "behind_tip": 0,
        "root": "/tmp",
    },
    "harness": {
        "name": harness,
        "version": "0",
        "isolation": {
            "mechanism": "home",
            "observed": {"unresolved": "stub"},
        },
        "sandbox": "always-approve",
        "containment": "policy",
        "argv": [],
    },
    "model": {
        "requested": requested,
        "effort_requested": effort_requested,
        "effort_argv": ["--reasoning-effort", effort_requested or ""],
        "ran": ran,
        "read_from": None,
        "note": None,
    },
    "session": {"id": None, "stream": None, "stream_sha256_at_close": None},
    "brief": {
        "template": {"path": "jobs.json", "sha256": "a" * 64},
        "scope": "",
        "inputs": [],
        "sha256": "b" * 64,
        "bytes": 0,
    },
    "caps": {"timeout": 1800, "source": "jobs.json"},
    "overrides": [],
    "attempts": [],
    "result": None,
    "status": "launched",
}
dest = REPO / ".dev" / "records" / "dispatches" / (rec_id + ".json")
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
plant.setdefault("records", {})[rec_id] = {
    "name": name,
    "job": job,
    "path": str(dest),
}
plant.setdefault("envelopes", {})[rec_id] = envelope
plant["last_id"] = rec_id
plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
sys.stdout.write("record: " + rec_id + "\n")
sys.stdout.write("launcher-pid: " + str(os.getpid()) + "\n")
raise SystemExit(0)
'''.lstrip()

LAUNCH_PY = r'''
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
argv = sys.argv[1:]
log = STUB / "launch-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
plant_path = STUB / "plant.json"
plant = json.loads(plant_path.read_text(encoding="utf-8"))
plant.setdefault("cwds", []).append(os.getcwd())
if not argv or argv[0] != "wait" or len(argv) < 2:
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stderr.write(
        "arguments: expected wait ID; found "
        + json.dumps(argv)
        + "; needed launch.py wait ID\n"
    )
    raise SystemExit(2)
rec_id = argv[1]
info = plant.get("records", {}).get(rec_id)
if not info:
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stderr.write(
        "wait: expected a minted record; found unknown id "
        + rec_id
        + "; needed wait the detach id\n"
    )
    raise SystemExit(2)
name = info.get("name")
plant.setdefault("waits", []).append({"id": rec_id, "name": name, "cwd": os.getcwd()})
path = Path(info["path"])
if name in plant.get("crash_stages", []):
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(
        rec_id + " died attempt=1 exit=137 tripped=false envelope=none\n"
    )
    raise SystemExit(1)
if name in plant.get("trip_stages", []):
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(
        rec_id + " died attempt=1 exit=137 tripped=true envelope=none\n"
    )
    raise SystemExit(1)
if name in plant.get("wait_wall_stages", []):
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(rec_id + " running attempt=1 wall=1\n")
    raise SystemExit(2)
payload = json.loads(path.read_text(encoding="utf-8"))
envelope = dict(plant.get("envelopes", {}).get(rec_id) or {})
summary = "ok"
if name in plant.get("invalid_envelope_stages", []):
    envelope["status"] = "invalid"
    summary = "invalid"
patch = (plant.get("envelope_patches") or {}).get(name)
if isinstance(patch, dict):
    envelope.update(patch)
payload["status"] = "closed"
payload["at"]["closed"] = "2026-09-04T12:00:01Z"
payload["result"] = {"envelope": envelope}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
sys.stdout.write(
    rec_id + " closed attempt=1 exit=0 tripped=false envelope=" + summary + "\n"
)
raise SystemExit(0)
'''.lstrip()

LAND_PY = r'''
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
REPO = Path("@@REPO@@")
argv = sys.argv[1:]
log = STUB / "land-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
plant_path = STUB / "plant.json"
plant = json.loads(plant_path.read_text(encoding="utf-8"))
plant.setdefault("cwds", []).append(os.getcwd())
plant.setdefault("land_cwds", []).append(os.getcwd())
if plant.get("land_abort"):
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write("abort conflict sha=deadbeef remainder=1\n")
    raise SystemExit(3)
if plant.get("land_lineage_break"):
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Unrelated"
    env["GIT_AUTHOR_EMAIL"] = "unrelated-aa32@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Unrelated"
    env["GIT_COMMITTER_EMAIL"] = "unrelated-aa32@example.invalid"
    tree = subprocess.run(
        ["git", "mktree"],
        input=b"",
        cwd=str(REPO),
        capture_output=True,
        check=False,
        env=env,
    )
    tree_sha = (tree.stdout or b"").decode("utf-8").strip()
    commit = subprocess.run(
        ["git", "commit-tree", tree_sha, "-m", "unrelated-aa32"],
        cwd=str(REPO),
        capture_output=True,
        check=False,
        env=env,
    )
    sha = (commit.stdout or b"").decode("utf-8").strip()
    plant["lineage_break_sha"] = sha
    plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write("LANDED\t" + sha + "\tnot-descended\n")
    sys.stdout.write("landed n=1 ref=refs/dispatch/planted\n")
    raise SystemExit(0)
rec = argv[0] if argv and not argv[0].startswith("-") else "planted"
extra = plant.get("land_extra_path")
info = (plant.get("records") or {}).get(rec) or {}
if extra and str(info.get("name") or "").startswith("code"):
    path = REPO / extra
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("outside-bucket-aa32\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "--", extra],
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
subprocess.run(
    ["git", "-c", "commit.gpgsign=false", "commit", "--allow-empty",
     "-m", "landed-stub\n\nSource: original\n"],
    cwd=str(REPO),
    capture_output=True,
    check=False,
)
sha_proc = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=str(REPO),
    capture_output=True,
    text=True,
    check=False,
)
sha = (sha_proc.stdout or "").strip()
plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
sys.stdout.write("LANDED\t" + sha + "\tlanded-stub\n")
sys.stdout.write("landed n=1 ref=refs/dispatch/" + rec + "\n")
raise SystemExit(0)
'''.lstrip()

FINDINGS_PY = r'''
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
argv = sys.argv[1:]
log = STUB / "findings-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
plant_path = STUB / "plant.json"
plant = json.loads(plant_path.read_text(encoding="utf-8"))
plant.setdefault("cwds", []).append(os.getcwd())
plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
if plant.get("ledger_fail"):
    sys.stderr.write(
        "ledger: expected a writable findings export; found a write error; "
        "needed a writable ledger\n"
    )
    raise SystemExit(3)
if argv and argv[0] == "export":
    sys.stdout.write("{}\n")
raise SystemExit(0)
'''.lstrip()

GH_PY = r'''
from __future__ import annotations
import json
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
argv = sys.argv[1:]
log = STUB / "gh-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
sys.stdout.write("@@PR_URL@@\n")
raise SystemExit(0)
'''.lstrip()


class _LadderFixture(unittest.TestCase):
    """Scratch HOME + linked worktree, staged driver, stub levers."""

    def setUp(self):
        self.maxDiff = None
        self.assertIsNotNone(shutil.which("git"), "INVALID: git not on PATH")
        self._live_before = {str(p): _store_snap(p) for p in _live_store_paths()}
        self._head_before = _git_out(["git", "rev-parse", "HEAD"], REPO).strip()
        self._diff_before = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            check=False,
        ).stdout
        self._tmp = tempfile.TemporaryDirectory(prefix="ladder-lever-")
        root = Path(self._tmp.name)
        self.root = root
        self.home = root / "home"
        self.xdg = root / "xdg"
        self.scratch = root / "scratch"
        self.bin = root / "bin"
        self.stub_dir = root / "stubs"
        self.main = root / "main"
        self.wt = root / WORKTREE_ROOT / ("ag-" + SLUG)
        self.repo = self.wt
        self.invoke_cwd = self.main
        for path in (
            self.home, self.xdg, self.scratch, self.bin, self.stub_dir,
        ):
            path.mkdir()
        self.store = self.xdg / LANE_NAME / "dispatch"
        self.home_store = (
            self.home / ".local" / "state" / "agentscient" / "dispatch"
        )
        self.assertFalse(self.store.exists(), "plant: isolated store starts absent")
        self.assertFalse(
            self.home_store.exists(),
            "plant: isolated HOME agentscient store starts absent",
        )
        self.staged = self.scratch / "ladder.py"
        self._stage_tool_bytes()
        self.gh = self.bin / "gh"
        self.scope_path = self.wt / "scope.md"
        self.plan_path = self.wt / "plan.md"
        self.conf_path = self.wt / "ops" / "lane.conf"
        self.origin = root / "origin.git"
        self._write_plant()
        self._plant_stub_scripts()
        self.seed_repo()
        self.plant_gh()
        self.assertFalse(
            (self.stub_dir / "dispatch-argv.jsonl").exists(),
            "plant: dispatch argv log must start absent",
        )
        self.assertNotEqual(self.wt.resolve(), self.main.resolve())
        self.assertEqual(self.invoke_cwd.resolve(), self.main.resolve())

    def tearDown(self):
        try:
            self.assertEqual(
                _without_new_job_dirs(
                    self._live_before,
                    {str(p): _store_snap(p) for p in _live_store_paths()},
                ),
                self._live_before,
                "live dispatch store mutated",
            )
            self.assertEqual(
                _git_out(["git", "rev-parse", "HEAD"], REPO).strip(),
                self._head_before,
                "real repo HEAD moved",
            )
            diff_after = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=str(REPO),
                capture_output=True,
                check=False,
            ).stdout
            self.assertEqual(
                diff_after,
                self._diff_before,
                "real repo tracked files mutated",
            )
        finally:
            self._tmp.cleanup()

    def _stage_tool_bytes(self) -> None:
        if TOOL.is_file():
            data = TOOL.read_bytes()
            self.staged.write_bytes(data)
            landed = self.staged.read_bytes()
            self.assertEqual(landed, data, "copy-tool-bytes did not land intact")
            self.assertEqual(len(landed), len(data))
            self.assertNotEqual(landed, ABSENT_STUB)
        else:
            self.staged.write_bytes(ABSENT_STUB)
            landed = self.staged.read_bytes()
            self.assertEqual(
                landed, ABSENT_STUB, "stub plant did not land intact",
            )
            self.assertEqual(len(landed), len(ABSENT_STUB))
        self.assertTrue(self.staged.is_file())

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _make_executable(self, path: Path) -> None:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.assertTrue(os.access(path, os.X_OK), f"not executable: {path}")

    def default_plant(self) -> dict:
        return {
            "verdicts": {name: "approve" for name in STAGE_NAMES},
            "artifacts": {
                "test_alpha": TEST_ALPHA,
                "test_beta": TEST_BETA,
            },
            "empty_artifacts": False,
            "refuse_stages": [],
            "refuse_jobs": [],
            "trip_stages": [],
            "crash_stages": [],
            "wait_wall_stages": [],
            "invalid_envelope_stages": [],
            "model_mismatch_stages": [],
            "effort_mismatch_stages": [],
            "land_lineage_break": False,
            "land_abort": False,
            "ledger_fail": False,
            "leak_implement_into": None,
            "leak_implement_into_findings": None,
            "notes": {},
            "skeptic_md": False,
            "skeptic_text": SKEPTIC_BODY,
            "stage_findings": {},
            "envelope_patches": {},
            "land_extra_path": None,
            "ran_grok": RAN_GROK,
            "ran_codex": RAN_CODEX,
            "n": 0,
            "calls": [],
            "records": {},
            "envelopes": {},
            "cwds": [],
            "waits": [],
        }

    def _write_plant(self, updates: dict | None = None) -> dict:
        plant = self.default_plant()
        if updates:
            plant.update(updates)
            if "verdicts" in updates:
                merged = {name: "approve" for name in STAGE_NAMES}
                merged.update(updates["verdicts"])
                plant["verdicts"] = merged
        text = json.dumps(plant, indent=2) + "\n"
        self._plant_bytes(self.stub_dir / "plant.json", text.encode("utf-8"))
        landed = json.loads(
            (self.stub_dir / "plant.json").read_text(encoding="utf-8")
        )
        self.assertEqual(landed["ran_grok"], plant["ran_grok"])
        return plant

    def load_plant(self) -> dict:
        return json.loads(
            (self.stub_dir / "plant.json").read_text(encoding="utf-8")
        )

    def patch_plant(self, **updates) -> dict:
        plant = self.load_plant()
        plant.update(updates)
        text = json.dumps(plant, indent=2) + "\n"
        self._plant_bytes(self.stub_dir / "plant.json", text.encode("utf-8"))
        return plant

    def _fill(self, template: str) -> str:
        return (
            template
            .replace("@@STUB@@", str(self.stub_dir))
            .replace("@@REPO@@", str(self.wt))
            .replace("@@PR_URL@@", PR_URL)
        )

    def _plant_stub_scripts(self) -> None:
        dispatch_py = self.stub_dir / "dispatch.py"
        self._plant_bytes(
            dispatch_py, self._fill(DISPATCH_PY).encode("utf-8"),
        )
        self._plant_bytes(
            self.stub_dir / "launch.py",
            self._fill(LAUNCH_PY).encode("utf-8"),
        )
        self._plant_bytes(
            self.stub_dir / "land.py",
            self._fill(LAND_PY).encode("utf-8"),
        )
        self._plant_bytes(
            self.stub_dir / "findings.py",
            self._fill(FINDINGS_PY).encode("utf-8"),
        )

    def conf_text(self, **overrides: object) -> str:
        omit = tuple(overrides.pop("omit", ()) or ())
        keys = {
            "LANE_NAME": LANE_NAME,
            "TRUNK_BRANCH": TRUNK,
            "RELEASE_BRANCH": RELEASE,
            "REPO_SLUG": REPO_SLUG,
            "CHECK_NAME": CHECK_NAME,
            "WF_AGENT_DEFAULT": AGENT,
            "LANE_AUTHOR": LANE_AUTHOR,
            "MODEL_GROK": MODEL_GROK,
            "MODEL_CODEX": MODEL_CODEX,
            "MODEL_CODEX_SECURITY_AUDIT": MODEL_CODEX_SECURITY,
            "MODEL_CLAUDE_READ": MODEL_CLAUDE_READ,
            "MODEL_CLAUDE_PLAN": MODEL_CLAUDE_PLAN,
            "EFFORT_GROK": EFFORT_GROK,
            "EFFORT_CODEX": EFFORT_CODEX,
            "EFFORT_CLAUDE": EFFORT_CLAUDE,
            "WALL_DEFAULT": "900",
            "SCOPE_CAP": "1024",
            "WORKTREE_ROOT": WORKTREE_ROOT,
            "ADDRESS_GROK": ADDRESS_GROK,
            "ADDRESS_CODEX": ADDRESS_CODEX,
            "ADDRESS_CLAUDE": ADDRESS_CLAUDE,
            "LADDER_WAIT_GRACE": "12",
        }
        for name, value in overrides.items():
            keys[name] = str(value)
        for name in omit:
            keys.pop(name, None)
        lines = ["# scratch lane conf for the ladder driver\n"]
        for name, value in keys.items():
            lines.append(f"{name}='{value}'\n")
        return "".join(lines)

    def plant_conf(self, **overrides: object) -> Path:
        text = self.conf_text(**overrides)
        self._plant_bytes(self.conf_path, text.encode("utf-8"))
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertEqual(landed, text, "conf plant did not land intact")
        return self.conf_path

    def plant_plan(self, text: str) -> None:
        self._plant_bytes(self.plan_path, text.encode("utf-8"))
        rel = str(self.plan_path.relative_to(self.repo))
        self.git("add", rel)
        self.git("commit", "-m", "plant plan\n")
        self.assertEqual(
            self.plan_path.read_text(encoding="utf-8"),
            text,
            "plan plant did not land intact",
        )
        self.assertEqual(self.porcelain(), "")

    def jobs_json(self) -> str:
        data = {
            name: {
                "adapter": "harness",
                "role": "write" if name in ("author-tests", "implement") else "read",
                "snapshot": "whole",
                "caps": {"timeout": 1800},
            }
            for name in JOBS
        }
        return json.dumps(data, indent=2) + "\n"

    def git_env(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": REPO_USER,
            "GIT_AUTHOR_EMAIL": REPO_EMAIL,
            "GIT_COMMITTER_NAME": REPO_USER,
            "GIT_COMMITTER_EMAIL": REPO_EMAIL,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }

    def git(self, *args: str, check: bool = True, cwd: Path | None = None):
        proc = subprocess.run(
            [
                "git",
                "-c",
                f"user.name={REPO_USER}",
                "-c",
                f"user.email={REPO_EMAIL}",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=str(cwd or self.repo),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        if check:
            self.assertEqual(
                proc.returncode,
                0,
                f"git {args}: {proc.stderr or proc.stdout}",
            )
        return proc

    def sha(self, rev: str, cwd: Path | None = None) -> str:
        out = self.git("rev-parse", rev, cwd=cwd).stdout.strip()
        self.assertRegex(out, r"^[0-9a-f]{40}$", out)
        return out

    def porcelain(self, cwd: Path | None = None) -> str:
        return self.git("status", "--porcelain", cwd=cwd).stdout

    def seed_repo(self, **conf_overrides: object) -> str:
        dest = self.main
        dest.mkdir()
        init = self.git("init", "-b", TRUNK, cwd=dest, check=False)
        self.assertEqual(init.returncode, 0, init.stderr)
        self.git("config", "user.name", REPO_USER, cwd=dest)
        self.git("config", "user.email", REPO_EMAIL, cwd=dest)
        name = self.git("config", "--get", "user.name", cwd=dest).stdout.strip()
        email = self.git("config", "--get", "user.email", cwd=dest).stdout.strip()
        self.assertEqual(name, REPO_USER)
        self.assertEqual(email, REPO_EMAIL)
        conf_text = self.conf_text(**conf_overrides)
        self._plant_bytes(dest / "ops" / "lane.conf", conf_text.encode("utf-8"))
        scope = SCOPE_FIRST + "\nrest of the scope for the ladder slice\n"
        self._plant_bytes(dest / "scope.md", scope.encode("utf-8"))
        self._plant_bytes(dest / "plan.md", DEFAULT_PLAN.encode("utf-8"))
        self.assertEqual(
            (dest / "scope.md").read_text(encoding="utf-8").splitlines()[0],
            SCOPE_FIRST,
        )
        jobs_text = self.jobs_json()
        self._plant_bytes(
            dest / "ops" / "devlane" / "task" / "jobs.json",
            jobs_text.encode("utf-8"),
        )
        wrapper = (
            "#!/bin/sh\n"
            f"exec {shlex.quote(sys.executable)} "
            f"{shlex.quote(str(self.stub_dir / 'dispatch.py'))} \"$@\"\n"
        )
        dispatch_sh = dest / "ops" / "bin" / "dispatch.sh"
        self._plant_bytes(dispatch_sh, wrapper.encode("utf-8"))
        self._make_executable(dispatch_sh)
        for rel, src in (
            ("ops/devlane/dispatch/launch.py", self.stub_dir / "launch.py"),
            ("ops/conductor/tools/land.py", self.stub_dir / "land.py"),
            ("ops/conductor/tools/findings.py", self.stub_dir / "findings.py"),
        ):
            body = (
                "#!/usr/bin/env python3\n"
                + src.read_text(encoding="utf-8")
            )
            dest_path = dest / rel
            self._plant_bytes(dest_path, body.encode("utf-8"))
            self._make_executable(dest_path)
        if LANECONF.is_file():
            data = LANECONF.read_bytes()
            dest_conf = dest / "ops" / "conductor" / "tools" / "laneconf.py"
            self._plant_bytes(dest_conf, data)
            self.assertEqual(dest_conf.read_bytes(), data)
            self.assertNotEqual(dest_conf.read_bytes(), ABSENT_STUB)
        self._plant_bytes(dest / "README", b"scratch ladder repo\n")
        self.git("add", "-A", cwd=dest)
        self.git("commit", "-m", "seed ladder scratch\n", cwd=dest)
        self.git("branch", BRANCH, cwd=dest)
        self.origin.mkdir()
        origin_init = subprocess.run(
            ["git", "init", "--bare", "-b", BRANCH],
            cwd=str(self.origin),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(origin_init.returncode, 0, origin_init.stderr)
        self.git("remote", "add", "origin", str(self.origin), cwd=dest)
        common = self.git(
            "rev-parse", "--git-common-dir", cwd=dest,
        ).stdout.strip()
        common_dir = Path(common) if Path(common).is_absolute() else dest / common
        hook = common_dir / "hooks" / "pre-push"
        hook_body = (
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> "
            f"{shlex.quote(str(self.stub_dir / 'push-log.txt'))}\n"
            "exit 0\n"
        )
        self._plant_bytes(hook, hook_body.encode("utf-8"))
        self._make_executable(hook)
        self.wt.parent.mkdir(parents=True, exist_ok=True)
        self.git("worktree", "add", str(self.wt), BRANCH, cwd=dest)
        self.repo = self.wt
        self.scope_path = self.wt / "scope.md"
        self.plan_path = self.wt / "plan.md"
        self.conf_path = self.wt / "ops" / "lane.conf"
        self.invoke_cwd = self.main
        self.base = self.sha("HEAD")
        main_head = self.git(
            "symbolic-ref", "--short", "HEAD", cwd=self.main,
        ).stdout.strip()
        wt_head = self.git(
            "symbolic-ref", "--short", "HEAD", cwd=self.wt,
        ).stdout.strip()
        self.assertEqual(main_head, TRUNK)
        self.assertEqual(wt_head, BRANCH)
        self.assertEqual(self.porcelain(), "")
        self.assertEqual(self.porcelain(cwd=self.main), "")
        listed = self.git(
            "worktree", "list", "--porcelain", cwd=self.main,
        ).stdout
        self.assertIn("branch refs/heads/" + BRANCH, listed)
        self.assertIn(str(self.wt), listed)
        return self.base

    def path_without_gh(self) -> str:
        nobin = self.root / "nobin"
        nobin.mkdir(exist_ok=True)
        for name in ("git", "python3", "python", "bash", "sh"):
            src = shutil.which(name)
            if not src:
                continue
            dest = nobin / name
            if not dest.exists():
                dest.symlink_to(src)
        path = str(nobin)
        self.assertIsNone(shutil.which("gh", path=path))
        self.assertIsNotNone(shutil.which("git", path=path))
        self.assertIsNotNone(shutil.which("python3", path=path))
        return path

    def path_with_gh(self) -> str:
        path = str(self.bin) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
        if self.gh.exists():
            found = shutil.which("gh", path=path)
            self.assertEqual(Path(found).resolve(), self.gh.resolve())
        return path

    def plant_gh(self) -> None:
        body = "#!/usr/bin/env python3\n" + self._fill(GH_PY)
        self._plant_bytes(self.gh, body.encode("utf-8"))
        self._make_executable(self.gh)
        self.assertEqual(
            self.gh.read_text(encoding="utf-8"),
            body,
            "gh stub plant did not land intact",
        )

    def plant_silent_gh(self) -> None:
        body = (
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"STUB = Path({str(self.stub_dir)!r})\n"
            "argv = sys.argv[1:]\n"
            "log = STUB / 'gh-argv.jsonl'\n"
            "with log.open('a', encoding='utf-8') as fh:\n"
            "    fh.write(json.dumps(argv) + '\\n')\n"
            "raise SystemExit(0)\n"
        )
        before = self.gh.read_bytes()
        self._plant_bytes(self.gh, body.encode("utf-8"))
        self._make_executable(self.gh)
        landed = self.gh.read_bytes()
        self.assertNotEqual(landed, before, "silent gh plant did not replace stub")
        self.assertNotIn(PR_URL.encode("utf-8"), landed)
        self.assertIn(b"raise SystemExit(0)", landed)

    def plant_gh_stdout(self, text: str) -> None:
        body = (
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"STUB = Path({str(self.stub_dir)!r})\n"
            "argv = sys.argv[1:]\n"
            "log = STUB / 'gh-argv.jsonl'\n"
            "with log.open('a', encoding='utf-8') as fh:\n"
            "    fh.write(json.dumps(argv) + '\\n')\n"
            f"sys.stdout.write({text!r} + '\\n')\n"
            "raise SystemExit(0)\n"
        )
        before = self.gh.read_bytes()
        self._plant_bytes(self.gh, body.encode("utf-8"))
        self._make_executable(self.gh)
        landed = self.gh.read_bytes()
        self.assertNotEqual(landed, before, "gh stdout plant did not replace stub")
        self.assertIn(text.encode("utf-8"), landed)

    def plant_git_wrapper(self) -> Path:
        real = shutil.which("git")
        self.assertIsNotNone(real, "INVALID: git not on PATH")
        log = self.stub_dir / "git-argv.jsonl"
        body = (
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"LOG = Path({str(log)!r})\n"
            f"REAL = {real!r}\n"
            "with LOG.open('a', encoding='utf-8') as fh:\n"
            "    fh.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "os.execv(REAL, [REAL, *sys.argv[1:]])\n"
        )
        dest = self.bin / "git"
        self._plant_bytes(dest, body.encode("utf-8"))
        self._make_executable(dest)
        self.assertTrue(os.access(dest, os.X_OK), dest)
        return dest

    def git_argvs(self) -> list:
        return self.jsonl("git-argv.jsonl")

    def commit_conf(self, message: str = "plant conf") -> None:
        rel = str(self.conf_path.relative_to(self.repo))
        self.git("add", rel)
        self.git("commit", "-m", message + "\n")
        self.assertEqual(self.porcelain(), "")

    def rewrite_ladder_record(self, ladder_id: str | None = None, **updates):
        payload = self.ladder_record(ladder_id)
        payload.update(updates)
        path = self.repo / ".dev" / "records" / "ladders" / (
            str(payload["id"]) + ".json"
        )
        text = json.dumps(payload, indent=2) + "\n"
        self._plant_bytes(path, text.encode("utf-8"))
        self.git("add", "-A", ".dev/records")
        self.git("commit", "-m", "rewrite ladder record\n")
        self.assertEqual(self.porcelain(), "")
        return json.loads(path.read_text(encoding="utf-8"))

    def implement_scope_text(self, argv: list[str]) -> str:
        chunks: list[str] = []
        for flag in ("--scope-file", "--scope"):
            for value in self.flag_values(argv, flag):
                path = Path(value)
                if path.is_file():
                    chunks.append(path.read_text(encoding="utf-8"))
                else:
                    chunks.append(value)
        return "\n".join(chunks)

    def wait_timeouts(self) -> list[str]:
        found: list[str] = []
        for row in self.launch_argvs():
            if not row or row[0] != "wait":
                continue
            if "--timeout" in row:
                idx = row.index("--timeout")
                if idx + 1 < len(row):
                    found.append(str(row[idx + 1]))
        return found

    def env(
        self,
        *,
        agent: str | None = AGENT,
        extra: dict[str, str] | None = None,
        with_gh: bool = True,
    ) -> dict[str, str]:
        env = {
            "PATH": self.path_with_gh() if with_gh else self.path_without_gh(),
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.xdg),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
        self.assertNotIn("LANE_CONF", env)
        self.assertNotIn("DISPATCH_JOBS", env)
        if agent is not None:
            env["WF_AGENT"] = agent
        if extra:
            env.update(extra)
        return env

    def invoke(
        self,
        argv: list[str],
        *,
        agent: str | None = AGENT,
        extra_env: dict[str, str] | None = None,
        with_gh: bool = True,
        cwd: Path | None = None,
    ):
        env = self.env(agent=agent, extra=extra_env, with_gh=with_gh)
        try:
            return subprocess.run(
                [sys.executable, str(self.staged), *argv],
                cwd=str(cwd or self.invoke_cwd),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=RUN_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"ladder exceeded {RUN_CAP}s: {exc}")

    def run_ladder(self, *extra: str, **kw):
        if extra and extra[0] == "resume":
            argv = list(extra)
        elif extra and extra[0] == "--dry-run":
            argv = ["--dry-run", str(self.scope_path), BRANCH]
        else:
            argv = [str(self.scope_path), BRANCH, *extra]
        return self.invoke(argv, **kw)

    def combined(self, proc) -> str:
        return f"{proc.stdout or ''}{proc.stderr or ''}"

    def jsonl(self, name: str) -> list:
        path = self.stub_dir / name
        if not path.is_file():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def dispatch_calls(self) -> list:
        return self.load_plant().get("calls", [])

    def dispatch_names(self) -> list[str]:
        return [row["name"] for row in self.dispatch_calls()]

    def dispatch_count(self, *, job: str, stage: str) -> int:
        return sum(
            1 for row in self.dispatch_calls()
            if row.get("job") == job and row.get("stage") == stage
        )

    def dispatch_argv_for(self, name: str) -> list[str]:
        for row in self.dispatch_calls():
            if row["name"] == name:
                return list(row["argv"])
        self.fail(f"no dispatch call named {name}: {self.dispatch_names()!r}")
        return []

    def land_argvs(self) -> list:
        return self.jsonl("land-argv.jsonl")

    def findings_argvs(self) -> list:
        return self.jsonl("findings-argv.jsonl")

    def gh_argvs(self) -> list:
        return self.jsonl("gh-argv.jsonl")

    def launch_argvs(self) -> list:
        return self.jsonl("launch-argv.jsonl")

    def waited_ids(self) -> list[str]:
        ids: list[str] = []
        for row in self.launch_argvs():
            if row and row[0] == "wait" and len(row) > 1:
                ids.append(row[1])
        return ids

    def push_log(self) -> list[str]:
        path = self.stub_dir / "push-log.txt"
        if not path.is_file():
            return []
        return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def flag_values(self, argv: list[str], flag: str) -> list[str]:
        values: list[str] = []
        i = 0
        while i < len(argv):
            if argv[i] == flag and i + 1 < len(argv):
                values.append(argv[i + 1])
                i += 2
                continue
            i += 1
        return values

    def inputs_text(self, argv: list[str]) -> str:
        chunks: list[str] = []
        for flag in ("--input", "--scope-file", "--scope", "--follows"):
            for value in self.flag_values(argv, flag):
                chunks.append(value)
                path = Path(value)
                if path.is_file():
                    chunks.append(path.read_text(encoding="utf-8"))
        return "\n".join(chunks)

    def implement_ids(self) -> list[str]:
        ids = []
        for rec_id, info in self.load_plant().get("records", {}).items():
            name = info.get("name")
            if name == "code" or str(name).startswith("code-"):
                ids.append(rec_id)
        return ids

    def implement_record_id(self) -> str:
        ids = self.implement_ids()
        if not ids:
            self.fail("no implement record was planted")
        return ids[0]

    def record_id_for(self, name: str) -> str:
        for rec_id, info in self.load_plant().get("records", {}).items():
            if info.get("name") == name:
                return rec_id
        self.fail(f"no record named {name}")
        return ""

    def plant_check_tests_findings(self, *, verdict: str) -> list[dict]:
        planted = [dict(CHECK_TESTS_FINDING)]
        self.patch_plant(
            verdicts={"check-tests": verdict},
            stage_findings={"check-tests": planted},
        )
        landed = self.load_plant()
        self.assertEqual(landed["verdicts"]["check-tests"], verdict)
        self.assertEqual(landed["stage_findings"]["check-tests"], planted)
        self.assertFalse(landed.get("skeptic_md"))
        return planted

    def check_tests_envelope(self) -> dict:
        rec_id = self.record_id_for("check-tests")
        path = Path(self.load_plant()["records"][rec_id]["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        env = ((payload.get("result") or {}).get("envelope")) or {}
        self.assertIsInstance(env, dict, payload)
        return env

    def dispatch_record_paths(self) -> set[Path]:
        found: set[Path] = set()
        for info in self.load_plant().get("records", {}).values():
            raw = info.get("path")
            if not raw:
                continue
            path = Path(raw)
            if path.is_file():
                found.add(path.resolve())
        return found

    def existing_file_for(self, value: str) -> Path | None:
        path = Path(value)
        candidates = [path]
        if not path.is_absolute():
            candidates.append(self.repo / path)
            candidates.append(self.wt / path)
        for cand in candidates:
            if cand.is_file():
                return cand
        return None

    def files_before_run(self) -> set[Path]:
        found: set[Path] = set()
        for path in self.root.rglob("*"):
            if path.is_file():
                found.add(path.resolve())
        return found

    def counts_from_findings(self, findings: list) -> dict:
        counts = {"p1": 0, "p2": 0, "p3": 0, "opinions": 0}
        for item in findings:
            if not item.get("reproduce"):
                counts["opinions"] += 1
                continue
            sev = item.get("severity")
            if sev in counts:
                counts[sev] += 1
            else:
                counts["opinions"] += 1
        return counts

    def findings_fields_in_record(self, record: dict) -> list[tuple[str, str]]:
        """The ladder record's own findings field(s) that name a path."""
        found: list[tuple[str, str]] = []

        def walk(value, prefix: str) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    path = f"{prefix}.{key}" if prefix else str(key)
                    if "finding" in str(key).lower() and isinstance(item, str):
                        found.append((path, item))
                    walk(item, path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    walk(item, f"{prefix}[{i}]")

        walk(record, "")
        return found

    def serialized_findings(self, path: Path) -> list:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            return data["findings"]
        self.fail(
            "findings file is not the complete serialized findings: "
            f"{path}: {text[:240]!r}"
        )
        return []

    def driver_written_findings_files(self, record: dict, planted) -> list[Path]:
        """Files the record's findings field names whose JSON is planted.

        A claim substring is not enough: `planted` must be the findings
        list. A pre-existing decoy that merely contains the claim is
        not a findings file.
        """
        if not isinstance(planted, list):
            return []
        dispatch = self.dispatch_record_paths()
        found: list[Path] = []
        for _key, raw in self.findings_fields_in_record(record):
            path = self.existing_file_for(raw)
            if path is None or not path.is_file():
                continue
            if path.resolve() in dispatch:
                continue
            try:
                loaded = self.serialized_findings(path)
            except (json.JSONDecodeError, AssertionError):
                continue
            if loaded == planted:
                found.append(path)
        return found

    def record_named_findings_file(
        self,
        record: dict,
        planted: list,
        *,
        before: set[Path],
    ) -> Path:
        fields = self.findings_fields_in_record(record)
        self.assertTrue(
            fields,
            "ladder record has no findings field naming a file: "
            f"{record!r}",
        )
        matching = self.driver_written_findings_files(record, planted)
        self.assertEqual(
            len(matching),
            1,
            "ladder record must name exactly one driver-written findings "
            "file whose content is the complete planted findings; "
            f"fields={fields!r} matching={matching!r} record={record!r}",
        )
        path = matching[0]
        self.assertNotIn(
            path.resolve(),
            before,
            f"findings file {path} existed before the driver ran",
        )
        self.assertNotEqual(path.name, "SKEPTIC.md", path)
        self.assertEqual(self.serialized_findings(path), planted)
        return path

    def ladder_paths(self) -> list[Path]:
        folder = self.repo / ".dev" / "records" / "ladders"
        if not folder.is_dir():
            return []
        return sorted(p for p in folder.glob("*.json") if p.is_file())

    def ladder_record(self, ladder_id: str | None = None) -> dict:
        paths = self.ladder_paths()
        self.assertGreaterEqual(len(paths), 1, "ladder record was not written")
        if ladder_id is not None:
            for path in paths:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("id") == ladder_id:
                    self.assertIsInstance(payload, dict, payload)
                    return payload
            self.fail(f"ladder record {ladder_id} missing from {paths!r}")
        self.assertEqual(
            len(paths),
            1,
            "multiple ladder records; pass the named id, do not pick newest",
        )
        payload = json.loads(paths[0].read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict, payload)
        return payload

    def stage_row(self, record: dict, name: str) -> dict:
        stages = record.get("stages")
        self.assertIsInstance(stages, list, stages)
        self.assertGreater(len(stages), 0, "ladder record has no stages")
        for row in stages:
            if row.get("name") == name:
                return row
        self.fail(f"stage {name!r} missing from {stages!r}")
        return {}

    def proof_strings(self, value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                if isinstance(item, str):
                    out.append(item)
                else:
                    out.append(json.dumps(item))
            return out
        if isinstance(value, dict):
            return [json.dumps(value)]
        return [str(value)]

    def parse_stage_table(self, proc) -> list[dict]:
        text = self.combined(proc)
        start = text.find("{")
        if start < 0:
            start = text.find("[")
        self.assertGreaterEqual(
            start, 0,
            f"dry-run must print a JSON stage table; got {text!r}",
        )
        end = max(text.rfind("}"), text.rfind("]"))
        self.assertGreater(end, start, f"dry-run JSON is not closed: {text!r}")
        payload = json.loads(text[start:end + 1])
        if isinstance(payload, dict) and "stages" in payload:
            stages = payload["stages"]
        elif isinstance(payload, list):
            stages = payload
        else:
            self.fail(f"dry-run JSON has no stages: {payload!r}")
        self.assertIsInstance(stages, list, stages)
        self.assertGreater(len(stages), 0, stages)
        return stages

    def argv_has(self, argv: list, token: str) -> bool:
        return token in [str(item) for item in argv]

    def is_write_stage(self, name: str) -> bool:
        return name in WRITE_STAGES or str(name).startswith("code")

    def assert_refusal(self, proc, class_name: str, *, named: tuple[str, ...] = ()) -> str:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err or proc.stdout)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        lower = lines[0].lower()
        token = class_name.lower().replace("_", "-")
        self.assertIn(token, lower, lines[0])
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, lines[0])
        self.assertLess(lower.index("expected"), lower.index("found"), lines[0])
        self.assertLess(lower.index("found"), lower.index("needed"), lines[0])
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            "refusal text belongs on stderr, not stdout",
        )
        for item in named:
            self.assertIn(item, lines[0], lines[0])
        return lines[0]

    def assert_stopped(
        self,
        proc,
        *,
        stage: str,
        record: str,
        reason: str | None = None,
        verdict: str | None = None,
        exit_code: int = 3,
    ) -> str:
        text = self.combined(proc)
        self.assertEqual(proc.returncode, exit_code, text)
        self.assertIn(proc.returncode, {0, 1, 2, 3}, proc.returncode)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertTrue(lines, f"stop printed nothing: {text!r}")
        last = lines[-1]
        self.assertIn(f"stage={stage}", last)
        self.assertIn(f"record={record}", last)
        if reason is not None:
            self.assertIn(f"reason={reason}", last)
        if verdict is not None:
            self.assertIn(f"verdict={verdict}", last)
        return last

    def assert_gh_draft_pr(self, argv: list) -> None:
        self.assertIn("--draft", argv)
        self.assertIn("--base", argv)
        self.assertEqual(argv[argv.index("--base") + 1], TRUNK)
        self.assertIn("--head", argv)
        self.assertEqual(argv[argv.index("--head") + 1], BRANCH)
        self.assertIn("--repo", argv)
        self.assertEqual(argv[argv.index("--repo") + 1], REPO_SLUG)
        self.assertIn("--title", argv)
        self.assertTrue(str(argv[argv.index("--title") + 1]).strip(), argv)
        self.assertIn("--body-file", argv)
        body = Path(argv[argv.index("--body-file") + 1])
        self.assertTrue(body.is_file(), f"gh --body-file missing: {body}")
        self.assertTrue(body.read_text(encoding="utf-8").strip(), body)

    def assert_dispatches_waited_and_detached(self) -> None:
        plant = self.load_plant()
        rec_ids = list(plant.get("records", {}))
        self.assertTrue(rec_ids, "no dispatch records were minted")
        self.assertEqual(sorted(self.waited_ids()), sorted(rec_ids))
        for row in self.dispatch_calls():
            self.assertIn("--detach", row["argv"], row)

    def assert_lands_match_write_records(self) -> None:
        plant = self.load_plant()
        landed_ids = [
            argv[0] for argv in self.land_argvs()
            if argv and not str(argv[0]).startswith("-")
        ]
        for rec_id, info in plant.get("records", {}).items():
            name = info.get("name")
            if self.is_write_stage(name):
                self.assertIn(
                    rec_id, landed_ids,
                    f"write stage {name} record {rec_id} was not landed",
                )
            else:
                self.assertNotIn(
                    rec_id, landed_ids,
                    f"review stage {name} record {rec_id} was landed",
                )
        for argv in self.land_argvs():
            self.assertNotIn("--push", argv, argv)

    def assert_branch_pushed_once(self) -> None:
        self.assertEqual(len(self.push_log()), 1, self.push_log())
        remote = subprocess.run(
            [
                "git", "--git-dir", str(self.origin),
                "rev-parse", f"refs/heads/{BRANCH}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            remote.returncode, 0,
            f"branch was not pushed to origin: {remote.stderr}",
        )
        self.assertRegex(remote.stdout.strip(), r"^[0-9a-f]{40}$")

    def ladder_record_commits(self) -> list[str]:
        log = self.git("log", "--format=%s", f"{self.base}..HEAD").stdout
        return [
            ln.strip() for ln in log.splitlines()
            if ln.strip().startswith("ladder: record")
        ]

    def plant_decoy_ladder(self, real_id: str) -> str:
        decoy_id = "20990909T000000Z-ladder-ffff32"
        self.assertGreater(decoy_id, real_id, (decoy_id, real_id))
        folder = self.repo / ".dev" / "records" / "ladders"
        folder.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": decoy_id,
            "status": "done",
            "branch": BRANCH,
            "worktree": str(self.wt),
            "stages": [],
            "stopped": None,
            "pr": {"number": 99, "url": "https://example.invalid/decoy"},
        }
        path = folder / (decoy_id + ".json")
        text = json.dumps(payload, indent=2) + "\n"
        self._plant_bytes(path, text.encode("utf-8"))
        rel = str(path.relative_to(self.repo))
        self.git("add", rel)
        self.git("commit", "-m", f"decoy ladder {decoy_id}\n")
        self.assertEqual(self.porcelain(), "")
        self.assertGreaterEqual(len(self.ladder_paths()), 2)
        return decoy_id

    def close_tripped_record(self) -> str:
        plant = self.load_plant()
        rec_id = None
        path = None
        for key, info in plant.get("records", {}).items():
            if info.get("name") in plant.get("trip_stages", []):
                rec_id = key
                path = Path(info["path"])
                break
        self.assertIsNotNone(rec_id, "plant: no tripped record")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["status"] = "closed"
        payload["at"]["closed"] = "2026-09-04T12:01:00Z"
        if plant.get("empty_artifacts"):
            artifacts = {}
        else:
            artifacts = dict(plant.get("artifacts") or {})
        payload["result"] = {
            "envelope": {
                "job": payload["job"],
                "status": "ok",
                "verdict": "approve",
                "counts": {"p1": 0, "p2": 0, "p3": 0, "opinions": 0},
                "findings": [],
                "artifacts": artifacts,
                "spend": {"harness": "grok", "total": 0, "out": 0, "runs": 0},
                "stamp": {"ref": "planted", "started": None, "ended": None},
                "note": None,
            }
        }
        raw = json.dumps(payload, indent=2) + "\n"
        self._plant_bytes(path, raw.encode("utf-8"))
        landed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(landed["status"], "closed")
        self.assertEqual(landed["result"]["envelope"]["status"], "ok")
        self.assertEqual(
            landed["result"]["envelope"]["artifacts"],
            artifacts,
        )
        return rec_id

    def save_ladder_record(self, payload: dict) -> dict:
        ident = payload.get("id")
        self.assertTrue(ident, payload)
        path = self.repo / ".dev" / "records" / "ladders" / (
            str(ident) + ".json"
        )
        text = json.dumps(payload, indent=2) + "\n"
        self._plant_bytes(path, text.encode("utf-8"))
        self.git("add", "-A", ".dev/records")
        self.git("commit", "-m", "rewrite ladder record\n")
        self.assertEqual(self.porcelain(), "")
        landed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(landed.get("id"), ident)
        return landed

    def replace_findings_file_paths(self, payload: dict, new_path: str) -> int:
        replaced = 0

        def walk(value) -> None:
            nonlocal replaced
            if isinstance(value, dict):
                for key, item in list(value.items()):
                    if "finding" in str(key).lower() and isinstance(item, str):
                        value[key] = new_path
                        replaced += 1
                    else:
                        walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return replaced

    def new_files_under(self, root: Path, before: set[Path]) -> list[Path]:
        found: list[Path] = []
        if not root.exists():
            return found
        for path in root.rglob("*"):
            if path.is_file() and path.resolve() not in before:
                found.append(path)
        return found

    def findings_payload_files(self, before: set[Path]) -> list[Path]:
        """New files that are a findings list or the literal null dump."""
        dispatch = self.dispatch_record_paths()
        found: list[Path] = []
        roots = [self.wt, self.xdg]
        for root in roots:
            for path in self.new_files_under(root, before):
                if path.resolve() in dispatch:
                    continue
                if path.parent.name == "ladders" and path.suffix == ".json":
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                stripped = text.strip()
                if stripped == "null":
                    found.append(path)
                    continue
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, list):
                    found.append(path)
        return found

    def host_secret(self, name: str, body: str) -> Path:
        path = self.root / name
        self._plant_bytes(path, body.encode("utf-8"))
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, body)
        self.assertFalse(
            str(path.resolve()).startswith(str(self.wt.resolve()) + os.sep),
            path,
        )
        return path


class ToolPresence(_LadderFixture):
    """Missing tool files each count once."""

    def test_the_tool_files_are_present(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")
        self.assertTrue(SHIM.is_file(), f"RED: shim is absent: {SHIM}")

    def test_the_shim_execs_the_instrument(self):
        self.assertTrue(SHIM.is_file(), f"RED: shim is absent: {SHIM}")
        text = SHIM.read_text(encoding="utf-8")
        self.assertRegex(text, r"\bexec\b", text)
        self.assertIn("ladder.py", text)


class RefusalsBeforeLaunch(_LadderFixture):
    """Preconditions refuse on the wire, exit 2, stdout empty, no dispatch."""

    def test_no_arguments_refuses_arguments(self):
        proc = self.invoke([])
        self.assert_refusal(proc, "arguments")
        self.assertEqual(self.dispatch_calls(), [])

    def test_absent_scope_file_refuses_scope(self):
        missing = self.repo / "no-such-scope-aa32.md"
        self.assertFalse(missing.exists(), "plant: scope must be absent")
        proc = self.invoke([str(missing), BRANCH])
        self.assert_refusal(proc, "scope", named=(str(missing),))
        self.assertEqual(self.dispatch_calls(), [])

    def test_branch_without_a_worktree_refuses_worktree_naming_the_add(self):
        other = "lane/no-wt-aa32"
        self.git("branch", other)
        listed = self.git("worktree", "list", "--porcelain").stdout
        self.assertNotIn("refs/heads/" + other, listed)
        current = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()
        self.assertEqual(current, BRANCH)
        proc = self.invoke([str(self.scope_path), other])
        line = self.assert_refusal(proc, "worktree")
        self.assertIn("git worktree add", line)
        self.assertIn(WORKTREE_ROOT, line)
        self.assertIn("ag-", line)
        self.assertIn(other.split("/")[-1], line)
        self.assertEqual(self.dispatch_calls(), [])

    def test_dirty_worktree_refuses_dirty(self):
        tracked = self.repo / "README"
        before = tracked.read_bytes()
        self._plant_bytes(tracked, b"dirty-uncommitted-aa32\n")
        self.assertNotEqual(tracked.read_bytes(), before)
        self.assertTrue(self.porcelain().strip(), "plant: tree still clean")
        self.assertEqual(self.porcelain(cwd=self.main), "")
        proc = self.run_ladder()
        self.assert_refusal(proc, "dirty")
        self.assertEqual(self.dispatch_calls(), [])

    def test_conf_missing_address_grok_refuses_conf_key(self):
        self.plant_conf(omit=("ADDRESS_GROK",))
        planted = self.conf_path.read_text(encoding="utf-8")
        self.assertNotIn("ADDRESS_GROK=", planted)
        self.git("add", str(self.conf_path.relative_to(self.repo)))
        self.git("commit", "-m", "drop ADDRESS_GROK\n")
        self.assertEqual(self.porcelain(), "")
        proc = self.run_ladder()
        line = self.assert_refusal(proc, "conf-key", named=("ADDRESS_GROK",))
        self.assertIn(str(self.conf_path), line)
        self.assertEqual(self.dispatch_calls(), [])

    def test_gh_absent_refuses_gh_missing(self):
        self.gh.unlink()
        self.assertFalse(self.gh.exists(), "plant: gh stub still present")
        proc = self.run_ladder(with_gh=False)
        self.assert_refusal(proc, "gh-missing")
        self.assertEqual(self.dispatch_calls(), [])


class DryRun(_LadderFixture):
    """--dry-run prints the stage table with dispatcher argv; no write stubs."""

    def test_dry_run_prints_the_stage_table_and_invokes_no_write_stub(self):
        proc = self.run_ladder("--dry-run")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        stages = self.parse_stage_table(proc)
        names = [row.get("name") for row in stages]
        for name in STAGE_NAMES:
            self.assertIn(name, names, names)
        by_name = {row["name"]: row for row in stages}
        for name in STAGE_NAMES:
            if name == "pr":
                continue
            argv = by_name[name]["argv"]
            self.assertIsInstance(argv, list, argv)
            self.assertTrue(argv, f"{name} argv empty")
            model, effort = stage_model_effort(name)
            self.assertTrue(
                self.argv_has(argv, model),
                f"{name} missing model {model}: {argv!r}",
            )
            self.assertTrue(
                self.argv_has(argv, effort),
                f"{name} missing effort {effort}: {argv!r}",
            )
        self.assertFalse(
            self.argv_has(by_name["security"]["argv"], MODEL_CODEX)
            and not self.argv_has(
                by_name["security"]["argv"], MODEL_CODEX_SECURITY,
            ),
            "security stage must carry MODEL_CODEX_SECURITY_AUDIT, not the"
            f" generic codex model: {by_name['security']['argv']!r}",
        )
        pr_argv = by_name["pr"]["argv"]
        self.assertIn("--draft", pr_argv)
        self.assertIn(TRUNK, pr_argv)
        self.assertIn(REPO_SLUG, pr_argv)
        self.assertIn(BRANCH, pr_argv)
        self.assertEqual(self.land_argvs(), [])
        self.assertEqual(self.findings_argvs(), [])
        self.assertEqual(self.gh_argvs(), [])
        for row in self.dispatch_calls():
            self.assertNotIn(
                "--detach", row["argv"],
                f"dry-run detached a dispatch: {row!r}",
            )


class HappyPath(_LadderFixture):
    """Every verdict approve: stages 1, 2, 4, 5, 6 run; 3, 7a, 7b, 8 skipped."""

    def test_approve_everywhere_opens_the_draft_pr_and_skips_fix_rounds(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(
            self.dispatch_names(),
            ["tests", "check-tests", "code", "security", "adversarial"],
        )
        record = self.ladder_record()
        self.assertEqual(record.get("status"), "done")
        self.assertIsNotNone(record.get("pr"))
        skipped = ("tests-fix", "fix-tests", "fix-code", "security-re")
        for name in skipped:
            row = self.stage_row(record, name)
            self.assertEqual(row.get("outcome"), "skipped", row)
            condition = row.get("condition") or row.get("skipped") or ""
            self.assertTrue(
                str(condition).strip(),
                f"skipped {name} must name the condition: {row!r}",
            )
        gh = self.gh_argvs()
        self.assertGreaterEqual(len(gh), 1, "gh was not invoked")
        self.assert_gh_draft_pr(gh[0])
        self.assertIn(PR_URL, self.combined(proc))
        self.assert_dispatches_waited_and_detached()
        self.assert_lands_match_write_records()
        self.assert_branch_pushed_once()


class SkepticChanges(_LadderFixture):
    """Planted changes at stage 2: tests-fix once, then implement; no re-check."""

    def test_changes_at_check_tests_runs_tests_fix_once_then_implement(self):
        self.patch_plant(verdicts={"check-tests": "changes"})
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        self.assertEqual(
            names[:4],
            ["tests", "check-tests", "tests-fix", "code"],
            names,
        )
        self.assertEqual(names.count("check-tests"), 1, names)
        self.assertEqual(names.count("tests-fix"), 1, names)
        self.assertNotIn("check-tests", names[names.index("tests-fix") + 1:])


class AuditChanges(_LadderFixture):
    """Planted changes at stage 6 only: 7a, 7b, then 8 approve opens the PR."""

    def test_changes_at_adversarial_runs_fix_then_security_re_then_pr(self):
        self.patch_plant(verdicts={"adversarial": "changes"})
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        self.assertEqual(
            names[-4:],
            ["adversarial", "fix-tests", "fix-code", "security-re"],
            names,
        )
        self.assertNotIn("tests-fix", names)
        gh = self.gh_argvs()
        self.assertGreaterEqual(len(gh), 1, names)
        self.assert_gh_draft_pr(gh[0])


class SecurityReChanges(_LadderFixture):
    """Planted changes at stage 8: exit 1, findings imported, no dispatch after."""

    def test_changes_at_security_re_stops_with_the_verdict_and_no_later_dispatch(self):
        self.patch_plant(
            verdicts={"adversarial": "changes", "security-re": "changes"},
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 1, self.combined(proc))
        self.assertIn(proc.returncode, {0, 1, 2, 3})
        self.assertNotEqual(proc.returncode, 0)
        record = self.ladder_record()
        self.assertEqual(record.get("status"), "stopped")
        stopped = record.get("stopped") or {}
        self.assertEqual(stopped.get("stage") or record.get("stage"), "security-re")
        last = [ln for ln in self.combined(proc).splitlines() if ln.strip()][-1]
        self.assertIn("stage=security-re", last)
        self.assertIn("verdict=changes", last)
        findings = self.findings_argvs()
        verbs = [row[0] if row else "" for row in findings]
        self.assertIn("import", verbs, findings)
        self.assertIn("export", verbs, findings)
        self.assertLess(
            verbs.index("import"),
            verbs.index("export"),
            findings,
        )
        names = self.dispatch_names()
        self.assertIn("security-re", names)
        self.assertEqual(names[-1], "security-re", names)
        self.assertEqual(self.gh_argvs(), [])
        self.assertEqual(self.push_log(), [])


class DerivedCommand(_LadderFixture):
    """Stage 4 scope is discover invocations joined with &&; none stops."""

    def test_two_test_artifacts_become_joined_discover_invocations(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv = self.dispatch_argv_for("code")
        scope = self.inputs_text(argv)
        self.assertIn(
            "python3 -m unittest discover -s ops/conductor/tests -p test_alpha.py",
            scope,
        )
        self.assertIn(
            "python3 -m unittest discover -s ops/conductor/tests -p test_beta.py",
            scope,
        )
        self.assertIn(" && ", scope)
        self.assertEqual(len(scope.split(" && ")), 2, scope)

    def test_a_test_file_outside_tests_is_not_a_discover_target(self):
        planted = {"relay": TEST_RELAY}
        self.patch_plant(artifacts=planted)
        self.assertEqual(self.load_plant()["artifacts"], planted)
        self.assertFalse(
            TEST_RELAY.split("/")[0] == "tests"
            or "/tests/" in "/" + TEST_RELAY,
            TEST_RELAY,
        )
        proc = self.run_ladder()
        self.assert_stopped(
            proc, stage="code", record="none", reason="artifacts",
        )
        names = self.dispatch_names()
        self.assertNotIn("code", names, names)
        text = self.combined(proc)
        self.assertNotIn("packages/relay/spec", text)
        self.assertNotIn("test_relay.py", text)

    def test_a_non_test_star_file_under_tests_is_a_discover_target(self):
        planted = {"helper": HELPER_UNDER_TESTS}
        self.patch_plant(artifacts=planted)
        self.assertEqual(self.load_plant()["artifacts"], planted)
        self.assertIn("/tests/", "/" + HELPER_UNDER_TESTS)
        self.assertFalse(
            Path(HELPER_UNDER_TESTS).name.startswith("test"),
            HELPER_UNDER_TESTS,
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotIn("reason=artifacts", self.combined(proc))
        scope = self.inputs_text(self.dispatch_argv_for("code"))
        self.assertIn(
            "python3 -m unittest discover -s ops/conductor/tests "
            "-p conftest.py",
            scope,
        )

    def test_no_test_artifact_stops_with_class_artifacts(self):
        self.patch_plant(empty_artifacts=True, artifacts={})
        proc = self.run_ladder()
        self.assert_stopped(
            proc, stage="code", record="none", reason="artifacts",
        )
        names = self.dispatch_names()
        self.assertNotIn("code", names, names)


class Buckets(_LadderFixture):
    """An M slice of two S buckets: two implements, audits once after both."""

    def test_m_slice_of_two_s_buckets_implements_twice_then_audits_once(self):
        self.plant_plan(BUCKET_PLAN)
        planted = self.plan_path.read_text(encoding="utf-8")
        self.assertIn(f"slice\t{SLICE_M}\tM", planted)
        self.assertIn(f"bucket\t{BUCKET_S1}\tS\t", planted)
        self.assertIn(f"bucket\t{BUCKET_S2}\tS\t", planted)
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        self.assertEqual(
            names,
            [
                "tests", "check-tests", "code", "code-2",
                "security", "adversarial",
            ],
            names,
        )
        self.assertLess(names.index("code"), names.index("code-2"))
        self.assertLess(names.index("code-2"), names.index("security"))
        self.assertEqual(names.count("security"), 1, names)
        self.assertEqual(names.count("adversarial"), 1, names)
        self.assert_lands_match_write_records()
        record = self.ladder_record()
        cal = record.get("calibration")
        self.assertIsInstance(cal, list, record)
        self.assertGreaterEqual(len(cal), 1, cal)
        slice_row = cal[0]
        self.assertEqual(slice_row.get("declared") or slice_row.get("bucket"), "M")
        self.assertEqual(slice_row.get("slice") or slice_row.get("name"), SLICE_M)
        measured = slice_row.get("measured")
        self.assertIsInstance(measured, dict, slice_row)
        for key in ("files", "tests", "lines", "minutes", "findings"):
            self.assertIn(key, measured, measured)
        self.assertIsInstance(measured["files"], int)
        self.assertIsInstance(measured["tests"], int)
        self.assertIsInstance(measured["lines"], int)
        self.assertIsInstance(measured["minutes"], dict)
        self.assertIsInstance(measured["findings"], dict)
        buckets = slice_row.get("buckets")
        self.assertIsInstance(buckets, list, slice_row)
        self.assertEqual(len(buckets), 2, buckets)
        declared = [
            row.get("declared") or row.get("bucket") for row in buckets
        ]
        self.assertEqual(declared, ["S", "S"], buckets)
        names_b = [row.get("name") for row in buckets]
        self.assertEqual(names_b, [BUCKET_S1, BUCKET_S2], buckets)


class Withholding(_LadderFixture):
    """Stages 1, 2, 3, 7a never see implement records; 7b does; a leak stops."""

    def test_withholding_is_proved_on_dispatched_bytes_at_every_stage(self):
        self.patch_plant(
            verdicts={"check-tests": "changes", "adversarial": "changes"},
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        self.assertIn("tests-fix", names)
        self.assertIn("fix-tests", names)
        implement_ids = self.implement_ids()
        self.assertGreaterEqual(len(implement_ids), 1, implement_ids)
        for rec_id in implement_ids:
            envelope_text = Path(
                self.load_plant()["records"][rec_id]["path"]
            ).read_text(encoding="utf-8")
            self.assertIn(IMPLEMENT_LINE, envelope_text)
        record = self.ladder_record()
        previous = None
        for name in names:
            argv = self.dispatch_argv_for(name)
            text = self.inputs_text(argv)
            row = self.stage_row(record, name)
            proof = ((row.get("input") or {}).get("proof"))
            self.assertIsInstance(proof, dict, row)
            given = self.proof_strings(proof.get("given"))
            withheld = self.proof_strings(proof.get("withheld"))
            given_blob = "\n".join(given)
            withheld_blob = "\n".join(withheld)
            for item in given:
                self.assertIn(
                    item, text,
                    f"{name} proof.given {item!r} missing from dispatched bytes",
                )
            for item in withheld:
                self.assertNotIn(
                    item, text,
                    f"{name} proof.withheld {item!r} present in dispatched bytes",
                )
            self.assertTrue(
                any(SCOPE_FIRST in item for item in given) or SCOPE_FIRST in given_blob,
                row,
            )
            self.assertIn(SCOPE_FIRST, text)
            if previous is not None:
                prev_id = self.record_id_for(previous)
                self.assertIn(prev_id, given_blob)
                self.assertIn(prev_id, text)
            if name in WITHHELD_STAGES:
                self.assertNotIn(IMPLEMENT_LINE, text)
                for rec_id in implement_ids:
                    self.assertNotIn(rec_id, text)
                if name == "fix-tests":
                    self.assertIn(IMPLEMENT_LINE, withheld_blob)
                    for rec_id in implement_ids:
                        self.assertIn(rec_id, withheld_blob)
            previous = name
        fix_code = self.inputs_text(self.dispatch_argv_for("fix-code"))
        for rec_id in implement_ids:
            self.assertIn(rec_id, fix_code)

    def test_a_leaked_implement_line_in_a_security_envelope_stops_withheld(self):
        self.patch_plant(
            verdicts={"security": "changes"},
            leak_implement_into="security",
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        text = self.combined(proc)
        self.assertIn("reason=withheld", text)
        self.assertNotIn("fix-tests", self.dispatch_names())

    def test_a_leaked_implement_line_in_check_tests_stops_tests_fix_withheld(self):
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            leak_implement_into="check-tests",
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertIn("reason=withheld", self.combined(proc))
        self.assertNotIn("tests-fix", self.dispatch_names())


class Landing(_LadderFixture):
    """Land after write stages with --author LANE_AUTHOR and --co-author."""

    def test_land_is_called_after_write_stages_with_author_and_co_author(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        lands = self.land_argvs()
        self.assertGreaterEqual(len(lands), 2, lands)
        worktree_author = f"{REPO_USER} <{REPO_EMAIL}>"
        grok_co = f"{RAN_GROK} <{ADDRESS_GROK}>"
        codex_co = f"{RAN_CODEX} <{ADDRESS_CODEX}>"
        authors = []
        coauthors = []
        for argv in lands:
            self.assertIn("--author", argv, argv)
            authors.append(argv[argv.index("--author") + 1])
            self.assertIn("--co-author", argv, argv)
            coauthors.append(argv[argv.index("--co-author") + 1])
        self.assertTrue(authors, lands)
        for value in authors:
            self.assertEqual(value, LANE_AUTHOR, authors)
        self.assertNotIn(worktree_author, authors)
        self.assertIn(grok_co, coauthors)
        self.assertIn(codex_co, coauthors)
        findings = self.findings_argvs()
        self.assertGreaterEqual(len(findings), 1, "read stages must import findings")
        self.assertGreaterEqual(
            len(findings),
            len(lands),
            "land must not run on read stages: "
            f"land={len(lands)} findings={len(findings)}",
        )
        self.assert_lands_match_write_records()


class Lineage(_LadderFixture):
    """A LANDED sha that does not descend from the stage base is class lineage."""

    def test_a_landed_sha_that_is_not_a_descendant_stops_lineage(self):
        self.patch_plant(land_lineage_break=True)
        proc = self.run_ladder()
        last = self.assert_stopped(
            proc, stage="tests", record=self.load_plant().get("last_id") or "none",
            reason="lineage",
        )
        self.assertIn("lineage", last)
        sha = self.load_plant().get("lineage_break_sha")
        self.assertTrue(sha, "land stub did not plant an unrelated commit")
        typ = self.git("cat-file", "-t", sha).stdout.strip()
        self.assertEqual(typ, "commit", sha)
        probe = self.git("merge-base", "--is-ancestor", self.base, sha, check=False)
        self.assertNotEqual(
            probe.returncode, 0,
            f"planted sha {sha} is a descendant of {self.base}",
        )


class ModelGuarantee(_LadderFixture):
    """A record whose model or effort differs from the dry-run argv stops."""

    def test_a_record_model_mismatch_stops_with_class_model(self):
        self.patch_plant(model_mismatch_stages=["tests"])
        proc = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        self.assert_stopped(
            proc, stage="tests", record=rec_id, reason="model",
        )

    def test_a_record_effort_mismatch_stops_with_class_model(self):
        self.patch_plant(effort_mismatch_stages=["tests"])
        proc = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        self.assert_stopped(
            proc, stage="tests", record=rec_id, reason="model",
        )

    def test_a_record_model_mismatch_at_security_stops_with_class_model(self):
        self.patch_plant(model_mismatch_stages=["security"])
        proc = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        self.assert_stopped(
            proc, stage="security", record=rec_id, reason="model",
        )

    def test_a_record_effort_mismatch_at_tests_fix_stops_with_class_model(self):
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            effort_mismatch_stages=["tests-fix"],
        )
        proc = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        self.assert_stopped(
            proc, stage="tests-fix", record=rec_id, reason="model",
        )

    def test_every_stage_dispatch_carries_conf_model_and_effort(self):
        self.patch_plant(
            verdicts={"check-tests": "changes", "adversarial": "changes"},
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        expected = [
            "tests", "check-tests", "tests-fix", "code",
            "security", "adversarial", "fix-tests", "fix-code", "security-re",
        ]
        self.assertEqual(names, expected, names)
        record = self.ladder_record()
        for name in expected:
            argv = self.dispatch_argv_for(name)
            model, effort = stage_model_effort(name)
            self.assertTrue(
                self.argv_has(argv, model),
                f"{name} argv missing model {model}: {argv!r}",
            )
            self.assertTrue(
                self.argv_has(argv, effort),
                f"{name} argv missing effort {effort}: {argv!r}",
            )
            row = self.stage_row(record, name)
            dispatched = row.get("dispatched") or {}
            recorded = row.get("recorded") or {}
            self.assertEqual(dispatched.get("model"), model, row)
            self.assertEqual(dispatched.get("effort"), effort, row)
            self.assertEqual(recorded.get("model_requested"), model, row)
            self.assertEqual(recorded.get("effort"), effort, row)


class WorktreeNotCwd(_LadderFixture):
    """Levers run in the named branch's worktree, not the invoke cwd."""

    def test_levers_run_in_the_branch_worktree_not_the_invoke_cwd(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotEqual(self.wt.resolve(), self.main.resolve())
        self.assertEqual(self.invoke_cwd.resolve(), self.main.resolve())
        plant = self.load_plant()
        cwds = plant.get("cwds") or []
        self.assertTrue(cwds, "stubs recorded no cwd")
        wt = self.wt.resolve()
        main = self.main.resolve()
        for raw in cwds:
            cwd = Path(raw).resolve()
            self.assertEqual(cwd, wt, f"lever cwd {cwd} is not the worktree {wt}")
            self.assertNotEqual(cwd, main)
        argv = self.dispatch_argv_for("tests")
        if "--worktree" in argv:
            given = Path(argv[argv.index("--worktree") + 1]).resolve()
            self.assertEqual(given, wt)
        elif "--branch" in argv:
            self.assertEqual(argv[argv.index("--branch") + 1], BRANCH)
        else:
            self.fail(f"dispatch had neither --branch nor --worktree: {argv!r}")


class RefusalAndResume(_LadderFixture):
    """Mint refusal at security: stop record=none; resume once; retry-cap at 2."""

    def test_a_dispatcher_refusal_at_security_stops_naming_record_none(self):
        self.patch_plant(refuse_stages=["security"])
        proc = self.run_ladder()
        self.assert_stopped(
            proc, stage="security", record="none", reason="job",
        )
        self.assertEqual(
            self.dispatch_names(),
            ["tests", "check-tests", "code", "security"],
        )

    def test_resume_relaunches_security_once_and_continues_to_the_pr(self):
        self.patch_plant(refuse_stages=["security"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        record = self.ladder_record()
        ladder_id = record.get("id")
        self.assertTrue(ladder_id, record)
        self.patch_plant(refuse_stages=[])
        second = self.invoke(["resume", ladder_id])
        self.assertEqual(second.returncode, 0, self.combined(second))
        names = self.dispatch_names()
        self.assertEqual(names.count("security"), 2, names)
        self.assertIn("adversarial", names)
        self.assertGreaterEqual(len(self.gh_argvs()), 1)

    def test_a_second_refusal_on_resume_stops_retry_cap_at_exactly_two_calls(self):
        self.patch_plant(refuse_stages=["security"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        ladder_id = self.ladder_record().get("id")
        self.assertTrue(ladder_id)
        second = self.invoke(["resume", ladder_id])
        self.assert_stopped(
            second, stage="security",
            record="none",
            reason="retry-cap",
        )
        self.assertEqual(self.dispatch_names().count("security"), 2)
        self.assertEqual(
            self.dispatch_count(job="security-audit", stage="review"),
            2,
        )

    def test_a_third_resume_after_retry_cap_does_not_launch_again(self):
        self.patch_plant(refuse_stages=["security"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        ladder_id = self.ladder_record().get("id")
        self.assertTrue(ladder_id)
        second = self.invoke(["resume", ladder_id])
        self.assert_stopped(
            second, stage="security",
            record="none",
            reason="retry-cap",
        )
        self.assertEqual(self.dispatch_names().count("security"), 2)
        self.assertEqual(
            self.dispatch_count(job="security-audit", stage="review"),
            2,
        )
        self.patch_plant(refuse_stages=[])
        third = self.invoke(["resume", ladder_id])
        self.assert_stopped(
            third, stage="security",
            record="none",
            reason="retry-cap",
        )
        self.assertEqual(self.dispatch_names().count("security"), 2)
        self.assertEqual(
            self.dispatch_count(job="security-audit", stage="review"),
            2,
        )
        self.assertEqual(self.gh_argvs(), [])

    def test_resume_of_refused_code_relaunches_code_not_a_second_bucket(self):
        self.patch_plant(refuse_stages=["code"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        self.assertEqual(
            self.dispatch_names(),
            ["tests", "check-tests", "code"],
        )
        ladder_id = self.ladder_record().get("id")
        self.assertTrue(ladder_id)
        second = self.invoke(["resume", ladder_id])
        self.assert_stopped(
            second, stage="code",
            record="none",
            reason="retry-cap",
        )
        names = self.dispatch_names()
        self.assertEqual(
            names,
            ["tests", "check-tests", "code", "code"],
            names,
        )
        self.assertNotIn("code-2", names)
        self.assertEqual(
            self.dispatch_count(job="implement", stage="code"),
            2,
            names,
        )
        self.assertNotIn("security", names)

    def test_resume_uses_the_named_record_not_the_newest(self):
        self.patch_plant(refuse_stages=["security"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        real_id = self.ladder_record().get("id")
        self.assertTrue(real_id)
        decoy_id = self.plant_decoy_ladder(real_id)
        self.patch_plant(refuse_stages=[])
        second = self.invoke(["resume", real_id])
        self.assertEqual(second.returncode, 0, self.combined(second))
        self.assertEqual(self.dispatch_names().count("security"), 2)
        decoy = json.loads(
            (self.repo / ".dev" / "records" / "ladders" / (decoy_id + ".json"))
            .read_text(encoding="utf-8")
        )
        self.assertEqual(decoy.get("status"), "done")
        self.assertEqual((decoy.get("pr") or {}).get("number"), 99)
        resumed = self.ladder_record(real_id)
        self.assertNotEqual(resumed.get("id"), decoy_id)
        self.assertEqual(resumed.get("id"), real_id)

    def test_each_stage_transition_commits_the_ladder_record(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        record = self.ladder_record()
        ran = [
            row for row in record.get("stages") or []
            if row.get("outcome") != "skipped"
        ]
        self.assertGreaterEqual(len(ran), 5, ran)
        commits = self.ladder_record_commits()
        self.assertGreaterEqual(
            len(commits),
            len(ran),
            f"transitions={len(ran)} record-commits={commits!r}",
        )


class TripAndResume(_LadderFixture):
    """wait tripped=true stops naming collect; resume of a closed ok record lands it."""

    def test_a_planted_trip_stops_naming_collect(self):
        self.patch_plant(trip_stages=["tests"])
        proc = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        last = self.assert_stopped(
            proc, stage="tests", record=rec_id, reason="tripped",
        )
        self.assertIn("launch.py collect", self.combined(proc))
        self.assertIn("collect", last.lower() + self.combined(proc).lower())

    def test_resume_after_a_closed_ok_record_lands_without_a_relaunch(self):
        self.patch_plant(trip_stages=["tests"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        before = self.dispatch_names().count("tests")
        self.assertEqual(before, 1)
        rec_id = self.close_tripped_record()
        closed = json.loads(
            Path(self.load_plant()["records"][rec_id]["path"])
            .read_text(encoding="utf-8")
        )
        self.assertEqual(
            closed["result"]["envelope"]["artifacts"],
            {"test_alpha": TEST_ALPHA, "test_beta": TEST_BETA},
        )
        self.patch_plant(trip_stages=[])
        ladder_id = self.ladder_record().get("id")
        second = self.invoke(["resume", ladder_id])
        self.assertEqual(second.returncode, 0, self.combined(second))
        self.assertEqual(self.dispatch_names().count("tests"), 1)
        self.assertGreaterEqual(len(self.land_argvs()), 1)
        self.assertGreaterEqual(len(self.gh_argvs()), 1)

    def test_a_second_trip_on_resume_stops_as_retry_cap(self):
        self.patch_plant(trip_stages=["tests"])
        first = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        self.assert_stopped(
            first, stage="tests", record=rec_id, reason="tripped",
        )
        self.assertEqual(self.dispatch_names().count("tests"), 1)
        ladder_id = self.ladder_record().get("id")
        self.assertTrue(ladder_id)
        second = self.invoke(["resume", ladder_id])
        text = self.combined(second)
        self.assertEqual(second.returncode, 3, text)
        last = [ln for ln in text.splitlines() if ln.strip()][-1]
        self.assertIn("stage=tests", last)
        self.assertIn("reason=retry-cap", last)
        self.assertEqual(self.dispatch_names().count("tests"), 2)
        self.assertEqual(
            self.dispatch_count(job="author-tests", stage="tests"),
            2,
        )


class ExitClasses(_LadderFixture):
    """Every contract-named failure returns one of the wire's four exits."""

    def test_every_observed_exit_is_in_the_wire_four(self):
        codes = []
        codes.append(self.invoke([]).returncode)
        missing = self.repo / "missing-scope-aa32.md"
        codes.append(self.invoke([str(missing), BRANCH]).returncode)
        self.patch_plant(
            verdicts={"adversarial": "changes", "security-re": "changes"},
        )
        codes.append(self.run_ladder().returncode)
        self.patch_plant(
            verdicts={name: "approve" for name in STAGE_NAMES},
            refuse_stages=["security"],
        )
        codes.append(self.run_ladder().returncode)
        for code in codes:
            self.assertIn(code, {0, 1, 2, 3}, codes)
        self.assertIn(2, codes)
        self.assertTrue(
            any(code in (1, 3) for code in codes),
            f"suite must observe a stop, not only refusals: {codes!r}",
        )

    def test_invalid_envelope_stops_exit_3(self):
        self.patch_plant(invalid_envelope_stages=["tests"])
        proc = self.run_ladder()
        self.assertIn(proc.returncode, {0, 1, 2, 3}, self.combined(proc))
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertIn("stage=tests", self.combined(proc))

    def test_landing_abort_stops_exit_3(self):
        self.patch_plant(land_abort=True)
        proc = self.run_ladder()
        self.assertIn(proc.returncode, {0, 1, 2, 3}, self.combined(proc))
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertIn("stage=tests", self.combined(proc))

    def test_wait_wall_stops_exit_3(self):
        self.patch_plant(wait_wall_stages=["tests"])
        proc = self.run_ladder()
        self.assertIn(proc.returncode, {0, 1, 2, 3}, self.combined(proc))
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertIn("stage=tests", self.combined(proc))

    def test_ledger_failure_stops_exit_3(self):
        self.patch_plant(ledger_fail=True)
        proc = self.run_ladder()
        self.assertIn(proc.returncode, {0, 1, 2, 3}, self.combined(proc))
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertGreaterEqual(len(self.findings_argvs()), 1)

    def test_a_stage_crash_stops_exit_3_naming_collect(self):
        self.patch_plant(crash_stages=["tests"])
        proc = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        self.assertIn(proc.returncode, {0, 1, 2, 3}, self.combined(proc))
        self.assert_stopped(proc, stage="tests", record=rec_id)
        self.assertIn("launch.py collect", self.combined(proc))

    def test_a_silent_gh_pr_create_stops_exit_3_without_a_traceback(self):
        self.plant_silent_gh()
        proc = self.run_ladder()
        text = self.combined(proc)
        self.assertEqual(proc.returncode, 3, text)
        self.assertIn(proc.returncode, {0, 1, 2, 3}, proc.returncode)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("IndexError", text)
        self.assertEqual(len(self.gh_argvs()), 1, self.gh_argvs())
        last = [ln for ln in text.splitlines() if ln.strip()][-1]
        self.assertIn("stage=pr", last)
        self.assertIn("stopped", last)


class Literals(_LadderFixture):
    """The driver file carries none of the lane names as quoted literals."""

    def test_the_driver_source_has_no_quoted_lane_literals(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")
        text = TOOL.read_text(encoding="utf-8")
        self.assertTrue(text.strip(), "driver file is empty")
        for token in QUOTED_LITERALS:
            self.assertNotIn(
                token, text,
                f"driver carries quoted lane literal {token}",
            )


class CheckNamesConf(_LadderFixture):
    """S2: the tracked conf key is CHECK_NAMES; the driver loads it."""

    def test_check_names_without_singular_check_name_is_enough_to_start(self):
        self.plant_conf(omit=("CHECK_NAME",), CHECK_NAMES=CHECK_NAME)
        planted = self.conf_path.read_text(encoding="utf-8")
        self.assertIn("CHECK_NAMES=", planted)
        self.assertNotIn("CHECK_NAME=", planted)
        self.commit_conf("plant CHECK_NAMES without CHECK_NAME")
        proc = self.run_ladder("--dry-run")
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotIn("CHECK_NAME", proc.stderr or "")
        self.assertEqual(self.dispatch_calls(), [])


class DerivedCommandContract(_LadderFixture):
    """S3, A3, A9: the named command is the tests/ rule, quoted, as scope."""

    def test_an_artifact_path_with_shell_separators_is_not_unquoted(self):
        planted = {"pwn": PWN_ARTIFACT}
        self.patch_plant(artifacts=planted)
        self.assertEqual(self.load_plant()["artifacts"], planted)
        proc = self.run_ladder()
        names = self.dispatch_names()
        if "code" in names:
            scope = self.inputs_text(self.dispatch_argv_for("code"))
            tokens = shlex.split(scope, posix=True)
            self.assertNotIn("printf", tokens, scope)
            self.assertNotIn("PWNED", tokens, scope)
            self.assertNotRegex(
                scope,
                r"(^|[;&\n]|&&|\|\|)\s*printf PWNED",
                scope,
            )
        else:
            self.assertIn(proc.returncode, {2, 3}, self.combined(proc))
            self.assertNotIn("printf PWNED", self.combined(proc))

    def test_implement_scope_is_the_derived_command_not_the_work_order(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv = self.dispatch_argv_for("code")
        scope = self.implement_scope_text(argv)
        self.assertIn("python3 -m unittest discover", scope)
        self.assertIn("test_alpha.py", scope)
        self.assertNotIn(
            SCOPE_FIRST, scope,
            "implement {scope} is the named command, not the work-order",
        )
        self.assertTrue(
            self.flag_values(argv, "--scope-file")
            or self.flag_values(argv, "--scope"),
            argv,
        )


class WithholdingEnvelope(_LadderFixture):
    """S7, A2: leak proof searches every implement-envelope string;
    a summary note is not a leak."""

    def test_a_changes_envelope_with_a_summary_note_is_not_a_withheld_leak(self):
        summary = "skeptic summary: tests need another round"
        self.assertNotIn(IMPLEMENT_LINE, summary)
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            notes={"check-tests": summary},
        )
        self.assertEqual(self.load_plant()["notes"]["check-tests"], summary)
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertNotIn("reason=withheld", self.combined(proc))
        names = self.dispatch_names()
        self.assertIn("tests-fix", names, names)

    def test_implementation_text_in_findings_is_a_withheld_leak(self):
        self.patch_plant(
            verdicts={"security": "changes"},
            leak_implement_into_findings="security",
        )
        self.assertEqual(
            self.load_plant()["leak_implement_into_findings"],
            "security",
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 3, self.combined(proc))
        self.assertIn("reason=withheld", self.combined(proc))
        self.assertNotIn("fix-tests", self.dispatch_names())


class TestsFixInputs(_LadderFixture):
    """Item 31: tests-fix is given the findings file the driver wrote."""

    def test_tests_fix_input_is_the_named_findings_file(self):
        planted = self.plant_check_tests_findings(verdict="changes")
        before = self.files_before_run()
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        env = self.check_tests_envelope()
        self.assertEqual(env.get("status"), "ok", env)
        self.assertEqual(env.get("verdict"), "changes", env)
        self.assertEqual(env.get("artifacts") or {}, {}, env)
        self.assertEqual(env.get("findings"), planted, env)
        self.assertEqual(
            env.get("counts"),
            self.counts_from_findings(planted),
            env,
        )
        names = self.dispatch_names()
        self.assertIn("tests-fix", names, names)
        self.assertIn("code", names, names)
        self.assertLess(names.index("check-tests"), names.index("tests-fix"), names)
        self.assertLess(names.index("tests-fix"), names.index("code"), names)
        record = self.ladder_record()
        named = self.record_named_findings_file(
            record, planted, before=before,
        )
        argv = self.dispatch_argv_for("tests-fix")
        input_paths = []
        for value in self.flag_values(argv, "--input"):
            path = self.existing_file_for(value)
            if path is None:
                path = Path(value)
            input_paths.append(path.resolve())
        self.assertTrue(input_paths, argv)
        self.assertIn(
            named.resolve(),
            input_paths,
            "tests-fix --input must equal the ladder record's findings "
            f"file {named}: {argv!r}",
        )
        self.assertFalse(
            any(Path(value).name == "SKEPTIC.md" for value in self.flag_values(argv, "--input")),
            argv,
        )

    def test_a_preexisting_claim_substring_file_is_not_the_findings_file(self):
        planted = self.plant_check_tests_findings(verdict="changes")
        decoy = self.wt / "decoy-claim-aa32.txt"
        body = CHECK_TESTS_FINDING_CLAIM + "\n"
        self._plant_bytes(decoy, body.encode("utf-8"))
        rel = str(decoy.relative_to(self.wt))
        self.git("add", rel)
        self.git("commit", "-m", "decoy claim substring\n")
        self.assertEqual(self.porcelain(), "")
        before = self.files_before_run()
        self.assertIn(decoy.resolve(), before)
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        record = self.ladder_record()
        named = self.record_named_findings_file(
            record, planted, before=before,
        )
        self.assertNotEqual(named.resolve(), decoy.resolve())
        argv = self.dispatch_argv_for("tests-fix")
        for value in self.flag_values(argv, "--input"):
            path = self.existing_file_for(value)
            if path is None:
                continue
            self.assertNotEqual(path.resolve(), decoy.resolve(), argv)


class ResumeDigests(_LadderFixture):
    """S4: resume verifies recorded SHA-256 digests and stays in-tree."""

    def test_resume_refuses_a_scope_digest_mismatch(self):
        self.patch_plant(trip_stages=["tests"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        rec_id = self.close_tripped_record()
        self.assertTrue(rec_id)
        payload = self.ladder_record()
        scope = payload.get("scope")
        self.assertIsInstance(scope, dict, payload)
        self.assertIn("sha256", scope, payload)
        self.assertIn("path", scope, payload)
        self.assertNotEqual(scope["sha256"], "0" * 64)
        scope["sha256"] = "0" * 64
        ladder_id = payload["id"]
        self.rewrite_ladder_record(ladder_id, scope=scope)
        self.patch_plant(trip_stages=[])
        second = self.invoke(["resume", ladder_id])
        text = self.combined(second)
        self.assertIn(second.returncode, {2, 3}, text)
        self.assertNotEqual(second.returncode, 0)
        lower = text.lower()
        self.assertTrue(
            "sha256" in lower or "digest" in lower or "scope" in lower,
            text,
        )
        self.assertEqual(self.dispatch_names().count("check-tests"), 0)

    def test_resume_refuses_a_scope_path_outside_the_worktree(self):
        self.patch_plant(trip_stages=["tests"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        rec_id = self.close_tripped_record()
        self.assertTrue(rec_id)
        secret = self.root / "host-secret-aa32"
        body = "credential-aa32\n"
        secret.write_text(body, encoding="utf-8")
        self.assertEqual(secret.read_text(encoding="utf-8"), body)
        self.assertFalse(
            str(secret.resolve()).startswith(str(self.wt.resolve()) + os.sep),
            secret,
        )
        digest = hashlib.sha256(secret.read_bytes()).hexdigest()
        payload = self.ladder_record()
        scope = dict(payload.get("scope") or {})
        self.assertIn("path", scope, payload)
        scope["path"] = str(secret)
        scope["sha256"] = digest
        ladder_id = payload["id"]
        self.rewrite_ladder_record(ladder_id, scope=scope)
        self.patch_plant(trip_stages=[])
        second = self.invoke(["resume", ladder_id])
        text = self.combined(second)
        self.assertIn(second.returncode, {2, 3}, text)
        self.assertNotIn("credential-aa32", text)
        for row in self.dispatch_calls():
            argv = row.get("argv") or []
            blob = self.inputs_text(argv)
            self.assertNotIn("credential-aa32", blob)
            self.assertNotIn(str(secret), argv)


class ResumeBindsJob(_LadderFixture):
    """S5: existing_result binds job, stage, harness, lineage, and branch."""

    def test_resume_does_not_accept_an_unrelated_jobs_closed_record(self):
        self.patch_plant(trip_stages=["tests"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        rec_id = self.close_tripped_record()
        path = Path(self.load_plant()["records"][rec_id]["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["job"], "author-tests")
        payload["job"] = "adversarial-review"
        payload["stage"] = "review"
        raw = json.dumps(payload, indent=2) + "\n"
        self._plant_bytes(path, raw.encode("utf-8"))
        landed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(landed["job"], "adversarial-review")
        self.assertEqual(landed["status"], "closed")
        self.patch_plant(trip_stages=[])
        ladder_id = self.ladder_record().get("id")
        second = self.invoke(["resume", ladder_id])
        text = self.combined(second)
        tests_row = self.stage_row(self.ladder_record(ladder_id), "tests")
        if tests_row.get("outcome") == "ok":
            bound = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                bound.get("job"),
                "author-tests",
                "tests must not consume a review record",
            )
        self.assertTrue(
            self.dispatch_names().count("tests") >= 2
            or second.returncode in {2, 3},
            text,
        )
        if second.returncode == 0:
            self.assertGreaterEqual(self.dispatch_names().count("tests"), 2)


class PushRefspec(_LadderFixture):
    """S6: git push uses -- before a validated refspec."""

    def test_git_push_separates_the_refspec_from_options(self):
        self.plant_git_wrapper()
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        pushes = [row for row in self.git_argvs() if row and row[0] == "push"]
        self.assertTrue(pushes, self.git_argvs())
        for row in pushes:
            self.assertIn("--", row, row)
            dash = row.index("--")
            self.assertIn(BRANCH, row[dash + 1 :], row)
            self.assertNotIn("--mirror", row)

    def test_a_mirror_branch_value_is_refused_before_push(self):
        self.plant_git_wrapper()
        self.patch_plant(trip_stages=["tests"])
        first = self.run_ladder()
        self.assertEqual(first.returncode, 3, self.combined(first))
        self.close_tripped_record()
        payload = self.ladder_record()
        ladder_id = payload["id"]
        self.rewrite_ladder_record(ladder_id, branch="--mirror")
        self.patch_plant(trip_stages=[])
        second = self.invoke(["resume", ladder_id])
        pushes = [row for row in self.git_argvs() if row and row[0] == "push"]
        for row in pushes:
            self.assertNotIn("--mirror", row, row)
        self.assertIn(second.returncode, {2, 3}, self.combined(second))
        self.assertNotEqual(second.returncode, 0)


class BucketFiles(_LadderFixture):
    """S8: a landed path outside the bucket's files stops the driver."""

    def test_a_landed_path_outside_the_bucket_stops_the_driver(self):
        self.plant_plan(BUCKET_PLAN)
        planted = self.plan_path.read_text(encoding="utf-8")
        self.assertIn("ops/conductor/tools/land.py", planted)
        self.assertNotIn(OUTSIDE_BUCKET, planted)
        self.patch_plant(land_extra_path=OUTSIDE_BUCKET)
        self.assertEqual(self.load_plant()["land_extra_path"], OUTSIDE_BUCKET)
        proc = self.run_ladder()
        text = self.combined(proc)
        self.assertIn(proc.returncode, {2, 3}, text)
        self.assertNotEqual(proc.returncode, 0)
        last = [ln for ln in text.splitlines() if ln.strip()][-1]
        lower = last.lower()
        self.assertTrue(
            any(token in lower for token in ("bucket", "files", "paths")),
            last,
        )
        self.assertNotIn("adversarial", self.dispatch_names())


class PlanGrammar(_LadderFixture):
    """S9: an M slice is two named S buckets; undocumented plans refuse."""

    def test_an_m_slice_without_buckets_is_refused(self):
        plan = (
            "# plan\n"
            "ordinary markdown with no bucket lines\n"
            f"slice\t{SLICE_M}\tM\n"
        )
        self.plant_plan(plan)
        planted = self.plan_path.read_text(encoding="utf-8")
        self.assertIn(f"slice\t{SLICE_M}\tM", planted)
        self.assertNotIn("bucket\t", planted)
        proc = self.run_ladder()
        text = self.combined(proc)
        self.assertIn(proc.returncode, {2, 3}, text)
        self.assertEqual(
            self.dispatch_count(job="implement", stage="code"),
            0,
            self.dispatch_names(),
        )
        lower = text.lower()
        self.assertTrue(
            any(token in lower for token in ("bucket", "plan", "slice")),
            text,
        )

    def test_an_m_slice_with_more_than_two_s_buckets_is_refused(self):
        lines = [
            "# plan\n",
            f"slice\t{SLICE_M}\tM\n",
        ]
        for i in range(7):
            lines.append(f"bucket\tb{i}\tS\tfile{i}.py\n")
        self.plant_plan("".join(lines))
        planted = self.plan_path.read_text(encoding="utf-8")
        self.assertEqual(planted.count("bucket\t"), 7)
        proc = self.run_ladder()
        text = self.combined(proc)
        self.assertIn(proc.returncode, {2, 3}, text)
        self.assertLess(
            self.dispatch_count(job="implement", stage="code"),
            3,
            self.dispatch_names(),
        )
        self.assertEqual(
            self.dispatch_count(job="implement", stage="code"),
            0,
            self.dispatch_names(),
        )


class WaitWall(_LadderFixture):
    """A6: wait is invoked with --timeout of caps.timeout + grace."""

    def test_wait_passes_the_contracted_wall_as_timeout(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        waits = [row for row in self.launch_argvs() if row and row[0] == "wait"]
        self.assertTrue(waits, self.launch_argvs())
        timeouts = self.wait_timeouts()
        self.assertEqual(len(timeouts), len(waits), waits)
        for raw in timeouts:
            self.assertEqual(int(float(raw)), 1800 + 12, waits)


class AuditPairTrip(_LadderFixture):
    """A7: a trip at security waits the sibling; resume does not mint another."""

    def test_a_trip_at_security_waits_the_adversarial_sibling(self):
        self.patch_plant(trip_stages=["security"])
        first = self.run_ladder()
        rec_id = self.record_id_for("security")
        self.assert_stopped(
            first, stage="security", record=rec_id, reason="tripped",
        )
        names = self.dispatch_names()
        self.assertIn("adversarial", names, names)
        waited = set(self.waited_ids())
        minted = set(self.load_plant().get("records") or {})
        self.assertTrue(minted, names)
        self.assertEqual(
            minted, waited,
            "a live sibling dispatch must be waited before stop",
        )

    def test_resume_after_a_security_trip_does_not_mint_a_second_adversarial(
            self):
        self.patch_plant(trip_stages=["security"])
        first = self.run_ladder()
        rec_id = self.record_id_for("security")
        self.assert_stopped(
            first, stage="security", record=rec_id, reason="tripped",
        )
        names = self.dispatch_names()
        self.assertIn("adversarial", names, names)
        self.assertEqual(names.count("adversarial"), 1, names)
        self.patch_plant(trip_stages=[])
        ladder_id = self.ladder_record().get("id")
        self.invoke(["resume", ladder_id])
        later = self.dispatch_names()
        self.assertEqual(later.count("adversarial"), 1, later)


class PrUrl(_LadderFixture):
    """S11: exit 0 records a URL, not an arbitrary gh stdout line."""

    def test_a_non_url_gh_stdout_is_not_recorded_as_the_pr(self):
        self.plant_gh_stdout(NOT_A_URL)
        proc = self.run_ladder()
        text = self.combined(proc)
        self.assertNotEqual(proc.returncode, 0, text)
        self.assertIn(proc.returncode, {1, 2, 3}, text)
        if self.ladder_paths():
            record = self.ladder_record()
            pr = record.get("pr") or {}
            self.assertNotEqual(pr.get("url"), NOT_A_URL, record)
            self.assertNotEqual(record.get("status"), "done", record)


class CheckTestsFindingsFile(_LadderFixture):
    """Item 31: the driver writes findings to a file it names in the record."""

    def test_ladder_record_names_the_findings_file_the_driver_wrote(self):
        planted = self.plant_check_tests_findings(verdict="changes")
        before = self.files_before_run()
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        env = self.check_tests_envelope()
        self.assertEqual(env.get("status"), "ok", env)
        self.assertEqual(env.get("verdict"), "changes", env)
        self.assertEqual(env.get("artifacts") or {}, {}, env)
        self.assertEqual(env.get("findings"), planted, env)
        self.assertEqual(
            env.get("counts"),
            self.counts_from_findings(planted),
            env,
        )
        record = self.ladder_record()
        named = self.record_named_findings_file(
            record, planted, before=before,
        )
        self.assertEqual(self.serialized_findings(named), planted)


class PlantedCheckTestsEnvelopeIsWellFormed(unittest.TestCase):
    """Item 31: the planted check-tests envelope's counts agree with findings."""

    def test_planted_finding_is_p2_with_a_reproduce_command(self):
        self.assertEqual(CHECK_TESTS_FINDING["severity"], "p2")
        self.assertTrue(CHECK_TESTS_FINDING["reproduce"])
        self.assertEqual(
            CHECK_TESTS_FINDING["claim"],
            CHECK_TESTS_FINDING_CLAIM,
        )

    def test_dispatch_stub_does_not_hardcode_zero_counts_beside_findings(self):
        self.assertNotIn(
            '"counts": {"p1": 0, "p2": 0, "p3": 0, "opinions": 0}',
            DISPATCH_PY,
        )
        self.assertIn("counts_for", DISPATCH_PY)
        self.assertIn("counts_for(findings)", DISPATCH_PY)


class TestsFixContractText(unittest.TestCase):
    """Item 31: ladder-lever.md says tests-fix takes findings, in prose too."""

    def _contract_text(self) -> str:
        path = REPO / "ops" / "conductor" / "ladder-lever.md"
        self.assertTrue(path.is_file(), path)
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.strip(), "ladder-lever.md is empty")
        return text

    def _tests_fix_table_rows(self) -> list[str]:
        text = self._contract_text()
        rows = [
            line for line in text.splitlines()
            if "`tests-fix`" in line and "|" in line
        ]
        self.assertTrue(rows, "ladder-lever.md has no tests-fix table row")
        return rows

    def test_ladder_lever_tests_fix_row_does_not_name_skeptic_md(self):
        blob = "\n".join(self._tests_fix_table_rows())
        self.assertNotIn("SKEPTIC.md", blob, blob)

    def test_ladder_lever_tests_fix_row_names_findings(self):
        blob = "\n".join(self._tests_fix_table_rows())
        self.assertIn("findings", blob.lower(), blob)

    def test_ladder_lever_prose_does_not_give_tests_fix_skeptic_md(self):
        text = self._contract_text()
        hits = 0
        idx = 0
        while True:
            i = text.find("tests-fix", idx)
            if i < 0:
                break
            hits += 1
            window = text[max(0, i - 240): i + 240]
            self.assertNotIn("SKEPTIC.md", window, window)
            idx = i + 1
        self.assertGreater(hits, 0, "ladder-lever.md never names tests-fix")

    def test_ladder_lever_every_tests_fix_line_is_examined_not_only_the_table(self):
        text = self._contract_text()
        lines = [ln for ln in text.splitlines() if "tests-fix" in ln]
        self.assertTrue(lines, "ladder-lever.md never names tests-fix")
        blob = "\n".join(lines)
        self.assertIn("findings", blob.lower(), blob)
        for line in lines:
            self.assertNotIn("SKEPTIC.md", line, line)


class CheckTestsEnvelopeValidatedBeforeFindingsFile(_LadderFixture):
    """Validate verdict, counts, and findings shape before writing.

    A check-tests envelope that is merely status=ok is not enough:
    findings must be a list of quotation-pair objects, counts must
    tally that list, and verdict must agree. tests-fix runs only when
    the validated verdict is changes. verdict=changes with an empty
    findings list is an envelope stop, not a tests-fix dispatch.
    """

    def test_changes_with_no_findings_is_an_envelope_stop(self):
        empty_counts = {"p1": 0, "p2": 0, "p3": 0, "opinions": 0}
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            stage_findings={"check-tests": []},
            envelope_patches={
                "check-tests": {
                    "verdict": "changes",
                    "findings": [],
                    "counts": dict(empty_counts),
                },
            },
        )
        planted = self.load_plant()
        self.assertEqual(planted["verdicts"]["check-tests"], "changes")
        self.assertEqual(planted["stage_findings"]["check-tests"], [])
        self.assertEqual(
            planted["envelope_patches"]["check-tests"]["findings"],
            [],
        )
        self.assertEqual(
            planted["envelope_patches"]["check-tests"]["counts"],
            empty_counts,
        )
        before = self.files_before_run()
        proc = self.run_ladder()
        rec_id = self.record_id_for("check-tests")
        self.assert_stopped(
            proc, stage="check-tests", record=rec_id, reason="envelope",
        )
        env = self.check_tests_envelope()
        self.assertEqual(env.get("verdict"), "changes", env)
        self.assertEqual(env.get("findings"), [], env)
        self.assertEqual(env.get("counts"), empty_counts, env)
        names = self.dispatch_names()
        self.assertNotIn(
            "tests-fix",
            names,
            "verdict=changes with no findings must not mint tests-fix: "
            f"{names!r} {self.combined(proc)}",
        )
        self.assertNotIn("code", names, names)
        leaked = self.findings_payload_files(before)
        self.assertEqual(
            leaked,
            [],
            "an empty changes envelope must not write a findings "
            f"payload: {leaked!r}",
        )

    def test_findings_none_does_not_move_to_tests_fix(self):
        planted = [dict(CHECK_TESTS_FINDING)]
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            stage_findings={"check-tests": planted},
            envelope_patches={"check-tests": {"findings": None}},
        )
        before = self.files_before_run()
        proc = self.run_ladder()
        names = self.dispatch_names()
        self.assertNotIn(
            "tests-fix",
            names,
            "findings=None must not become the tests-fix spec: "
            f"{names!r} {self.combined(proc)}",
        )
        self.assertNotIn("code", names, names)
        leaked = self.findings_payload_files(before)
        self.assertEqual(
            leaked,
            [],
            "findings=None must not be written (json.dumps(None) is "
            f"'null') before the driver refuses: {leaked!r}",
        )

    def test_counts_that_disagree_with_findings_do_not_move_to_tests_fix(self):
        planted = [dict(CHECK_TESTS_FINDING)]
        self.assertEqual(self.counts_from_findings(planted)["p2"], 1)
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            stage_findings={"check-tests": planted},
            envelope_patches={
                "check-tests": {
                    "counts": {
                        "p1": 0, "p2": 0, "p3": 0, "opinions": 0,
                    },
                },
            },
        )
        before = self.files_before_run()
        proc = self.run_ladder()
        names = self.dispatch_names()
        self.assertNotIn(
            "tests-fix",
            names,
            "a truncated counts tally must not become the tests-fix "
            f"spec: {names!r} {self.combined(proc)}",
        )
        self.assertNotIn("code", names, names)
        leaked = self.findings_payload_files(before)
        self.assertEqual(
            leaked,
            [],
            "disagreeing counts must be refused before the findings "
            f"file is written: {leaked!r}",
        )

    def test_a_finding_missing_its_shape_does_not_move_to_tests_fix(self):
        planted = [dict(CHECK_TESTS_FINDING)]
        self.patch_plant(
            verdicts={"check-tests": "changes"},
            stage_findings={"check-tests": planted},
            envelope_patches={
                "check-tests": {
                    "findings": [{"severity": "p2", "where": "x.py:1"}],
                    "counts": {
                        "p1": 0, "p2": 1, "p3": 0, "opinions": 0,
                    },
                },
            },
        )
        before = self.files_before_run()
        proc = self.run_ladder()
        names = self.dispatch_names()
        self.assertNotIn(
            "tests-fix",
            names,
            "a finding without claim/reproduce is not a quotation "
            f"pair: {names!r} {self.combined(proc)}",
        )
        self.assertNotIn("code", names, names)
        leaked = self.findings_payload_files(before)
        self.assertEqual(
            leaked,
            [],
            "a malformed findings list must not be written: "
            f"{leaked!r}",
        )

    def test_approve_with_findings_does_not_skip_to_implement(self):
        planted = self.plant_check_tests_findings(verdict="approve")
        self.assertTrue(planted)
        before = self.files_before_run()
        proc = self.run_ladder()
        names = self.dispatch_names()
        self.assertNotIn(
            "tests-fix",
            names,
            "tests-fix runs only on verdict changes, never to paper "
            f"over an approve that still carries findings: {names!r}",
        )
        self.assertNotIn(
            "code",
            names,
            "an approve envelope that still carries findings must not "
            f"move to implement: {names!r} {self.combined(proc)}",
        )
        leaked = self.findings_payload_files(before)
        self.assertEqual(
            leaked,
            [],
            "verdict and findings that disagree must be refused "
            f"before the findings file is written: {leaked!r}",
        )

    def test_validated_changes_still_moves_to_tests_fix(self):
        self.plant_check_tests_findings(verdict="changes")
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        names = self.dispatch_names()
        self.assertIn("tests-fix", names, names)
        self.assertIn("code", names, names)
        self.assertLess(
            names.index("check-tests"), names.index("tests-fix"), names,
        )


class FindingsFilePathStaysInsideLadderInputs(_LadderFixture):
    """The findings file is resolved against the worktree, inside inputs.

    A mutated absolute path, a ../ escape, or a symlink that resolves
    outside the ladder input directory is refused. tests-fix must not
    receive that path as --input.
    """

    def _run_to_tripped_tests_fix(self) -> tuple[list, Path, str]:
        planted = self.plant_check_tests_findings(verdict="changes")
        self.patch_plant(trip_stages=["tests-fix"])
        before = self.files_before_run()
        first = self.run_ladder()
        rec_id = self.record_id_for("tests-fix")
        self.assert_stopped(
            first, stage="tests-fix", record=rec_id, reason="tripped",
        )
        self.assertIn("tests-fix", self.dispatch_names())
        record = self.ladder_record()
        named = self.record_named_findings_file(
            record, planted, before=before,
        )
        self.assertTrue(named.is_file(), named)
        return planted, named, record["id"]

    def _resume_must_refuse_escaped_path(
        self,
        ladder_id: str,
        secret: Path,
        token: str,
    ) -> None:
        self.patch_plant(trip_stages=[])
        before_names = list(self.dispatch_names())
        second = self.invoke(["resume", ladder_id])
        text = self.combined(second)
        self.assertIn(second.returncode, {2, 3}, text)
        self.assertNotEqual(second.returncode, 0, text)
        self.assertNotIn(token, text)
        later = self.dispatch_names()
        self.assertEqual(
            later.count("tests-fix"),
            before_names.count("tests-fix"),
            f"escaped findings path dispatched tests-fix again: "
            f"{later!r} {text}",
        )
        for row in self.dispatch_calls():
            argv = row.get("argv") or []
            self.assertNotIn(str(secret), argv, argv)
            blob = self.inputs_text(argv)
            self.assertNotIn(token, blob)

    def test_resume_refuses_a_findings_file_outside_the_worktree(self):
        _planted, _named, ladder_id = self._run_to_tripped_tests_fix()
        secret = self.host_secret(
            "host-secret-findings-aa32",
            "credential-findings-aa32\n",
        )
        payload = self.ladder_record(ladder_id)
        n = self.replace_findings_file_paths(payload, str(secret))
        self.assertGreater(
            n, 0,
            "ladder record has no findings path field to mutate: "
            f"{payload!r}",
        )
        self.save_ladder_record(payload)
        self._resume_must_refuse_escaped_path(
            ladder_id, secret, "credential-findings-aa32",
        )

    def test_resume_refuses_a_findings_file_dotdot_escape(self):
        _planted, _named, ladder_id = self._run_to_tripped_tests_fix()
        rel = os.path.join("..", "escaped-findings-aa32.json")
        self.assertIn("..", Path(rel).parts, rel)
        body = json.dumps([dict(CHECK_TESTS_FINDING)], indent=2) + "\n"
        planted_outsides = [
            (self.wt / rel).resolve(),
            (self.invoke_cwd / rel).resolve(),
        ]
        for outside in planted_outsides:
            self._plant_bytes(outside, body.encode("utf-8"))
            self.assertEqual(outside.read_text(encoding="utf-8"), body)
            self.assertFalse(
                str(outside).startswith(str(self.wt.resolve()) + os.sep),
                outside,
            )
        payload = self.ladder_record(ladder_id)
        n = self.replace_findings_file_paths(payload, rel)
        self.assertGreater(n, 0, payload)
        self.save_ladder_record(payload)
        self.patch_plant(trip_stages=[])
        before_names = list(self.dispatch_names())
        second = self.invoke(["resume", ladder_id])
        text = self.combined(second)
        self.assertIn(
            second.returncode, {2, 3},
            f"../ findings path must refuse, not crash or proceed: {text}",
        )
        self.assertNotEqual(second.returncode, 0, text)
        later = self.dispatch_names()
        self.assertEqual(
            later.count("tests-fix"),
            before_names.count("tests-fix"),
            f"../ findings path dispatched tests-fix again: "
            f"{later!r} {text}",
        )
        forbidden = {p.resolve() for p in planted_outsides}
        for row in self.dispatch_calls():
            argv = row.get("argv") or []
            for value in self.flag_values(argv, "--input"):
                raw = Path(value)
                resolved = raw.resolve() if raw.is_absolute() else (
                    self.wt / raw
                ).resolve()
                self.assertNotIn(
                    resolved, forbidden,
                    f"tests-fix --input escaped via {rel!r}: {argv!r}",
                )

    def test_resume_refuses_a_findings_file_symlink_outside_inputs(self):
        _planted, named, ladder_id = self._run_to_tripped_tests_fix()
        secret = self.host_secret(
            "host-secret-symlink-aa32",
            "credential-symlink-aa32\n",
        )
        self.assertTrue(named.is_file(), named)
        named.unlink()
        named.symlink_to(secret)
        self.assertTrue(named.is_symlink(), named)
        self.assertEqual(named.resolve(), secret.resolve())
        self.assertEqual(
            secret.read_text(encoding="utf-8"),
            "credential-symlink-aa32\n",
        )
        try:
            rel = str(named.relative_to(self.wt))
        except ValueError:
            rel = None
        if rel is not None:
            self.git("add", "-A", "--", rel)
            self.git("commit", "-m", "plant findings symlink\n")
            self.assertEqual(self.porcelain(), "")
        self._resume_must_refuse_escaped_path(
            ladder_id, secret, "credential-symlink-aa32",
        )

    def test_a_relative_findings_file_is_resolved_against_the_worktree(self):
        planted, named, ladder_id = self._run_to_tripped_tests_fix()
        rel = os.path.relpath(named, start=self.wt)
        self.assertFalse(os.path.isabs(rel), rel)
        decoy = self.invoke_cwd / rel
        decoy.parent.mkdir(parents=True, exist_ok=True)
        decoy_body = json.dumps(
            [{"severity": "p1", "where": "decoy", "claim": "DECOY_FINDINGS_aa32",
              "reproduce": "false"}],
            indent=2,
        ) + "\n"
        self._plant_bytes(decoy, decoy_body.encode("utf-8"))
        self.assertEqual(decoy.read_text(encoding="utf-8"), decoy_body)
        self.assertNotEqual(decoy.resolve(), named.resolve())
        payload = self.ladder_record(ladder_id)
        n = self.replace_findings_file_paths(payload, rel)
        self.assertGreater(n, 0, payload)
        self.save_ladder_record(payload)
        self.patch_plant(trip_stages=[])
        second = self.invoke(["resume", ladder_id])
        text = self.combined(second)
        for row in self.dispatch_calls():
            argv = row.get("argv") or []
            for value in self.flag_values(argv, "--input"):
                raw = Path(value)
                from_cwd = (
                    raw.resolve()
                    if raw.is_absolute()
                    else (self.invoke_cwd / raw).resolve()
                )
                self.assertNotEqual(
                    from_cwd,
                    decoy.resolve(),
                    "a relative findings path must resolve against the "
                    f"worktree, not cwd: {argv!r}",
                )
                self.assertNotIn("DECOY_FINDINGS_aa32", value)
        if second.returncode == 0:
            argv = None
            for row in self.dispatch_calls():
                if row.get("name") == "tests-fix":
                    argv = row.get("argv") or []
            self.assertIsNotNone(argv, self.dispatch_names())
            input_paths = []
            for value in self.flag_values(argv, "--input"):
                raw = Path(value)
                resolved = (
                    raw.resolve()
                    if raw.is_absolute()
                    else (self.wt / raw).resolve()
                )
                input_paths.append(resolved)
            self.assertIn(named.resolve(), input_paths, argv)
            self.assertNotIn(decoy.resolve(), input_paths, argv)
            self.assertEqual(self.serialized_findings(named), planted)
        else:
            self.assertIn(second.returncode, {2, 3}, text)


class FindingsPayloadWriteDoesNotFollowASymlink(_LadderFixture):
    """Write-time: the payload file is not a followed symlink.

    Consume-time Path.resolve checks are a different finding. A
    pre-existing check-tests-findings.payload.json symlink must not
    redirect the driver's write onto the host.
    """

    def test_payload_symlink_is_not_followed(self):
        host_body = "HOST"
        secret = self.host_secret("host-payload-aa32", host_body)
        self.patch_plant(trip_stages=["tests"])
        first = self.run_ladder()
        rec_id = self.record_id_for("tests")
        self.assert_stopped(
            first, stage="tests", record=rec_id, reason="tripped",
        )
        ladder_id = self.ladder_record()["id"]
        inputs_dir = (
            self.wt / ".dev" / "records" / "ladders" / ladder_id
        )
        inputs_dir.mkdir(parents=True, exist_ok=True)
        payload = inputs_dir / "check-tests-findings.payload.json"
        self.assertFalse(payload.exists(), payload)
        payload.symlink_to(secret)
        self.assertTrue(payload.is_symlink(), payload)
        self.assertEqual(Path(os.readlink(payload)), secret)
        self.assertEqual(payload.resolve(), secret.resolve())
        self.assertEqual(secret.read_text(encoding="utf-8"), host_body)
        rel = str(payload.relative_to(self.wt))
        self.git("add", "-A", "--", rel)
        self.git("commit", "-m", "plant findings payload symlink\n")
        self.assertEqual(self.porcelain(), "")
        self.assertTrue(payload.is_symlink(), payload)
        self.assertEqual(secret.read_text(encoding="utf-8"), host_body)
        self.close_tripped_record()
        planted = self.plant_check_tests_findings(verdict="changes")
        self.assertTrue(planted)
        self.patch_plant(trip_stages=["tests-fix"])
        second = self.invoke(["resume", ladder_id])
        names = self.dispatch_names()
        self.assertIn(
            "check-tests",
            names,
            "plant must reach the findings write: "
            f"{names!r} {self.combined(second)}",
        )
        env = self.check_tests_envelope()
        self.assertEqual(env.get("verdict"), "changes", env)
        self.assertEqual(env.get("findings"), planted, env)
        after = secret.read_text(encoding="utf-8")
        self.assertEqual(
            after,
            host_body,
            "findings payload write followed a symlink onto the host; "
            f"host now reads {after[:240]!r}",
        )
        self.assertFalse(
            str(secret.resolve()).startswith(str(self.wt.resolve()) + os.sep),
            secret,
        )
        for row in self.dispatch_calls():
            argv = row.get("argv") or []
            self.assertNotIn(str(secret), argv, argv)
            blob = self.inputs_text(argv)
            self.assertNotIn(host_body, blob)
            for value in self.flag_values(argv, "--input"):
                raw = Path(value)
                resolved = (
                    raw.resolve()
                    if raw.is_absolute()
                    else (self.wt / raw).resolve()
                )
                self.assertNotEqual(
                    resolved,
                    secret.resolve(),
                    "tests-fix --input is the host target of the "
                    f"payload symlink: {argv!r}",
                )
                self.assertTrue(
                    str(resolved).startswith(str(self.wt.resolve()) + os.sep),
                    f"tests-fix --input escaped the worktree: {argv!r}",
                )


if __name__ == "__main__":
    unittest.main()
