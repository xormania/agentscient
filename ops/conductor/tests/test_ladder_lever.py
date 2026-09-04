"""Ladder-driver acceptance tests, written from the unit 2 contract.

Contract (only): the dispatch input `contract-ladder-driver.md` (scope
plus plan §3) and the inherited
`ops/conductor/instrument-conventions.md`. The tools
`ops/conductor/tools/ladder.py` and `ops/bin/ladder.sh` are the
subject and are not read here. Tests invoke the staged copy as a
subprocess inside a scratch git repository whose `ops/` carries stub
levers; a stub `gh` sits first on PATH. No environment knob selects
the stubs — the driver must locate levers relative to the worktree.

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
TEST_ALPHA = "ops/conductor/tests/test_alpha.py"
TEST_BETA = "ops/conductor/tests/test_beta.py"
PR_URL = "https://example.invalid/org/projx/pull/7"
RUN_CAP = 60

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

_JOB_DIR = re.compile(r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$")


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
    sys.stdout.write(json.dumps({"argv": launch_argv, "env": {}}) + "\n")
    raise SystemExit(0)

counts = plant.setdefault("dispatch_counts", {})
key = job + ":" + stage
n = counts.get(key, 0) + 1
counts[key] = n


def logical_name():
    if job == "author-tests" and stage == "tests":
        return {1: "tests", 2: "tests-fix", 3: "fix-tests"}.get(
            n, "author-tests-" + str(n)
        )
    if job == "implement" and stage == "code":
        return {1: "code", 2: "fix-code"}.get(n, "code-" + str(n))
    if job == "security-audit" and stage == "review":
        return {1: "security", 2: "security-re"}.get(n, "security-" + str(n))
    if job == "check-tests":
        return "check-tests"
    if job == "adversarial-review":
        return "adversarial"
    return job + ":" + stage + ":" + str(n)


name = logical_name()
plant.setdefault("calls", []).append(
    {"name": name, "job": job, "stage": stage, "argv": argv}
)
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
mismatch = name in plant.get("model_mismatch_stages", [])
requested = "wrong-model-aa32" if mismatch else model
ran = plant.get("ran_" + (harness or ""), (harness or "h") + "-ran-aa32")
note = None
if name == "code":
    note = "IMPLEMENT_ENVELOPE_LINE_aa32 unique"
if plant.get("leak_implement_into") == name:
    note = "IMPLEMENT_ENVELOPE_LINE_aa32 unique"
tripping = name in plant.get("trip_stages", [])
envelope = {
    "job": job,
    "status": "ok",
    "verdict": verdict,
    "counts": {"p1": 0, "p2": 0, "p3": 0, "opinions": 0},
    "findings": [],
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
        "closed": None if tripping else "2026-09-04T12:00:01Z",
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
        "effort_requested": effort,
        "effort_argv": ["--reasoning-effort", effort or ""],
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
    "result": None if tripping else {"envelope": envelope},
    "status": "launched" if tripping else "closed",
}
dest = REPO / ".dev" / "records" / "dispatches" / (rec_id + ".json")
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
plant.setdefault("records", {})[rec_id] = {
    "name": name,
    "job": job,
    "path": str(dest),
}
plant["last_id"] = rec_id
plant_path.write_text(json.dumps(plant, indent=2) + "\n", encoding="utf-8")
sys.stdout.write("record: " + rec_id + "\n")
sys.stdout.write("launcher-pid: " + str(os.getpid()) + "\n")
raise SystemExit(0)
'''.lstrip()

LAUNCH_PY = r'''
from __future__ import annotations
import json
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
argv = sys.argv[1:]
log = STUB / "launch-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
plant = json.loads((STUB / "plant.json").read_text(encoding="utf-8"))
if not argv or argv[0] != "wait" or len(argv) < 2:
    sys.stderr.write(
        "arguments: expected wait ID; found "
        + json.dumps(argv)
        + "; needed launch.py wait ID\n"
    )
    raise SystemExit(2)
rec_id = argv[1]
info = plant.get("records", {}).get(rec_id, {})
name = info.get("name")
if name in plant.get("trip_stages", []):
    sys.stdout.write(
        rec_id + " died attempt=1 exit=137 tripped=true envelope=none\n"
    )
    raise SystemExit(1)
sys.stdout.write(
    rec_id + " closed attempt=1 exit=0 tripped=false envelope=ok\n"
)
raise SystemExit(0)
'''.lstrip()

LAND_PY = r'''
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
REPO = Path("@@REPO@@")
argv = sys.argv[1:]
log = STUB / "land-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
plant = json.loads((STUB / "plant.json").read_text(encoding="utf-8"))
if plant.get("land_lineage_break"):
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        input=b"orphan-blob-aa32\n",
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
    sha = (blob.stdout or b"").decode("utf-8").strip()
    sys.stdout.write("LANDED\t" + sha + "\tnot-descended\n")
    sys.stdout.write("landed n=1 ref=refs/dispatch/planted\n")
    raise SystemExit(0)
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
rec = argv[0] if argv and not argv[0].startswith("-") else "planted"
sys.stdout.write("LANDED\t" + sha + "\tlanded-stub\n")
sys.stdout.write("landed n=1 ref=refs/dispatch/" + rec + "\n")
raise SystemExit(0)
'''.lstrip()

FINDINGS_PY = r'''
from __future__ import annotations
import json
import sys
from pathlib import Path

STUB = Path("@@STUB@@")
argv = sys.argv[1:]
log = STUB / "findings-argv.jsonl"
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\n")
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
    """Scratch HOME + git worktree, staged driver, stub levers, live store frozen."""

    def setUp(self):
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
        self.repo = root / "repo"
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
        self.scope_path = self.repo / "scope.md"
        self.plan_path = self.repo / "plan.md"
        self.conf_path = self.repo / "ops" / "lane.conf"
        self._write_plant()
        self._plant_stub_scripts()
        self.seed_repo()
        self.plant_gh()
        self.assertFalse(
            (self.stub_dir / "dispatch-argv.jsonl").exists(),
            "plant: dispatch argv log must start absent",
        )

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
            "model_mismatch_stages": [],
            "land_lineage_break": False,
            "leak_implement_into": None,
            "ran_grok": RAN_GROK,
            "ran_codex": RAN_CODEX,
            "n": 0,
            "calls": [],
            "records": {},
            "dispatch_counts": {},
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
            .replace("@@REPO@@", str(self.repo))
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

    def sha(self, rev: str) -> str:
        out = self.git("rev-parse", rev).stdout.strip()
        self.assertRegex(out, r"^[0-9a-f]{40}$", out)
        return out

    def porcelain(self) -> str:
        return self.git("status", "--porcelain").stdout

    def seed_repo(self, **conf_overrides: object) -> str:
        if not self.repo.exists():
            self.repo.mkdir()
        init = self.git("init", "-b", BRANCH, cwd=self.repo, check=False)
        self.assertEqual(init.returncode, 0, init.stderr)
        self.git("config", "user.name", REPO_USER)
        self.git("config", "user.email", REPO_EMAIL)
        name = self.git("config", "--get", "user.name").stdout.strip()
        email = self.git("config", "--get", "user.email").stdout.strip()
        self.assertEqual(name, REPO_USER)
        self.assertEqual(email, REPO_EMAIL)
        self.plant_conf(**conf_overrides)
        scope = SCOPE_FIRST + "\nrest of the scope for the ladder slice\n"
        plan = "# plan\nunit 2 named files for the ladder driver\n"
        self._plant_bytes(self.scope_path, scope.encode("utf-8"))
        self._plant_bytes(self.plan_path, plan.encode("utf-8"))
        self.assertEqual(
            self.scope_path.read_text(encoding="utf-8").splitlines()[0],
            SCOPE_FIRST,
        )
        jobs_text = self.jobs_json()
        self._plant_bytes(
            self.repo / "ops" / "devlane" / "task" / "jobs.json",
            jobs_text.encode("utf-8"),
        )
        wrapper = (
            "#!/bin/sh\n"
            f"exec {shlex.quote(sys.executable)} "
            f"{shlex.quote(str(self.stub_dir / 'dispatch.py'))} \"$@\"\n"
        )
        dispatch_sh = self.repo / "ops" / "bin" / "dispatch.sh"
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
            dest = self.repo / rel
            self._plant_bytes(dest, body.encode("utf-8"))
            self._make_executable(dest)
        if LANECONF.is_file():
            data = LANECONF.read_bytes()
            dest = self.repo / "ops" / "conductor" / "tools" / "laneconf.py"
            self._plant_bytes(dest, data)
            self.assertEqual(dest.read_bytes(), data)
            self.assertNotEqual(dest.read_bytes(), ABSENT_STUB)
        readme = self.repo / "README"
        self._plant_bytes(readme, b"scratch ladder repo\n")
        self.git("add", "-A")
        self.git("commit", "-m", "seed ladder scratch\n")
        self.git("branch", TRUNK)
        self.base = self.sha("HEAD")
        head_branch = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()
        self.assertEqual(head_branch, BRANCH)
        self.assertEqual(self.porcelain(), "")
        listed = self.git("worktree", "list", "--porcelain").stdout
        self.assertIn("branch refs/heads/" + BRANCH, listed)
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
                cwd=str(cwd or self.repo),
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
        for flag in ("--input", "--scope-file", "--scope"):
            for value in self.flag_values(argv, flag):
                path = Path(value)
                if path.is_file():
                    chunks.append(path.read_text(encoding="utf-8"))
                else:
                    chunks.append(value)
        return "\n".join(chunks)

    def implement_record_id(self) -> str:
        for rec_id, info in self.load_plant().get("records", {}).items():
            if info.get("name") == "code":
                return rec_id
        self.fail("no implement record was planted")
        return ""

    def ladder_paths(self) -> list[Path]:
        folder = self.repo / ".dev" / "records" / "ladders"
        if not folder.is_dir():
            return []
        return sorted(p for p in folder.glob("*.json") if p.is_file())

    def ladder_record(self) -> dict:
        paths = self.ladder_paths()
        self.assertGreaterEqual(len(paths), 1, "ladder record was not written")
        payload = json.loads(paths[-1].read_text(encoding="utf-8"))
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
        payload["result"] = {
            "envelope": {
                "job": payload["job"],
                "status": "ok",
                "verdict": "approve",
                "counts": {"p1": 0, "p2": 0, "p3": 0, "opinions": 0},
                "findings": [],
                "artifacts": {},
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
        return rec_id


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
        for name in ("tests", "check-tests", "code", "security", "adversarial"):
            argv = by_name[name]["argv"]
            self.assertIsInstance(argv, list, argv)
            self.assertTrue(argv, f"{name} argv empty")
        self.assertTrue(
            self.argv_has(by_name["tests"]["argv"], MODEL_GROK),
            by_name["tests"]["argv"],
        )
        self.assertTrue(
            self.argv_has(by_name["tests"]["argv"], EFFORT_GROK),
            by_name["tests"]["argv"],
        )
        self.assertTrue(
            self.argv_has(by_name["code"]["argv"], MODEL_CODEX),
            by_name["code"]["argv"],
        )
        self.assertTrue(
            self.argv_has(by_name["code"]["argv"], EFFORT_CODEX),
            by_name["code"]["argv"],
        )
        self.assertTrue(
            self.argv_has(by_name["security"]["argv"], MODEL_CODEX_SECURITY),
            by_name["security"]["argv"],
        )
        self.assertTrue(
            self.argv_has(by_name["security-re"]["argv"], MODEL_CODEX_SECURITY),
            by_name["security-re"]["argv"],
        )
        self.assertFalse(
            self.argv_has(by_name["security"]["argv"], MODEL_CODEX)
            and not self.argv_has(by_name["security"]["argv"], MODEL_CODEX_SECURITY),
            "security stage must carry MODEL_CODEX_SECURITY_AUDIT, not the"
            f" generic codex model: {by_name['security']['argv']!r}",
        )
        pr_argv = by_name["pr"]["argv"]
        self.assertIn("--draft", pr_argv)
        self.assertIn(TRUNK, pr_argv)
        self.assertIn(REPO_SLUG, pr_argv)
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
        argv = gh[0]
        self.assertIn("--draft", argv)
        self.assertIn("--base", argv)
        self.assertEqual(argv[argv.index("--base") + 1], TRUNK)
        self.assertIn("--repo", argv)
        self.assertEqual(argv[argv.index("--repo") + 1], REPO_SLUG)
        self.assertIn(PR_URL, self.combined(proc))


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
        gh = self.gh_argvs()
        self.assertGreaterEqual(len(gh), 1, names)
        self.assertIn("--draft", gh[0])


class SecurityReChanges(_LadderFixture):
    """Planted changes at stage 8: exit 1, findings imported, no dispatch after."""

    def test_changes_at_security_re_stops_with_the_verdict_and_no_later_dispatch(self):
        self.patch_plant(
            verdicts={"adversarial": "changes", "security-re": "changes"},
        )
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 1, self.combined(proc))
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

    def test_no_test_artifact_stops_with_class_artifacts(self):
        self.patch_plant(empty_artifacts=True, artifacts={})
        proc = self.run_ladder()
        self.assert_stopped(
            proc, stage="code", record="none", reason="artifacts",
        )
        names = self.dispatch_names()
        self.assertNotIn("code", names, names)


class Withholding(_LadderFixture):
    """Stages 1, 2, 3, 7a never see implement records; 7b does; a leak stops."""

    def test_fix_tests_inputs_withhold_the_implement_record_and_envelope(self):
        self.patch_plant(verdicts={"adversarial": "changes"})
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        implement_id = self.implement_record_id()
        implement_path = Path(
            self.load_plant()["records"][implement_id]["path"]
        )
        envelope_text = implement_path.read_text(encoding="utf-8")
        self.assertIn(IMPLEMENT_LINE, envelope_text)
        withheld_stages = ("tests", "check-tests", "fix-tests")
        for name in withheld_stages:
            argv = self.dispatch_argv_for(name)
            text = self.inputs_text(argv)
            self.assertNotIn(
                implement_id, text,
                f"{name} input leaked the implement record id",
            )
            self.assertNotIn(
                IMPLEMENT_LINE, text,
                f"{name} input leaked an implement envelope line",
            )
        fix_code = self.inputs_text(self.dispatch_argv_for("fix-code"))
        self.assertIn(implement_id, fix_code)
        record = self.ladder_record()
        for name in ("tests", "check-tests", "fix-tests"):
            row = self.stage_row(record, name)
            proof = (row.get("input") or {}).get("proof") or row.get("proof")
            self.assertIsInstance(proof, dict, row)
            given = proof.get("given")
            withheld = proof.get("withheld")
            self.assertTrue(given, row)
            self.assertTrue(withheld, row)
            given_text = given if isinstance(given, str) else json.dumps(given)
            withheld_text = (
                withheld if isinstance(withheld, str) else json.dumps(withheld)
            )
            self.assertIn(SCOPE_FIRST, given_text)
            self.assertIn(IMPLEMENT_LINE, withheld_text)
            self.assertIn(implement_id, withheld_text)

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


class Landing(_LadderFixture):
    """Land after write stages with --author from git identity and --co-author."""

    def test_land_is_called_after_write_stages_with_author_and_co_author(self):
        proc = self.run_ladder()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        lands = self.land_argvs()
        self.assertGreaterEqual(len(lands), 2, lands)
        author = f"{REPO_USER} <{REPO_EMAIL}>"
        grok_co = f"{RAN_GROK} <{ADDRESS_GROK}>"
        codex_co = f"{RAN_CODEX} <{ADDRESS_CODEX}>"
        authors = []
        coauthors = []
        for argv in lands:
            self.assertIn("--author", argv, argv)
            authors.append(argv[argv.index("--author") + 1])
            self.assertIn("--co-author", argv, argv)
            coauthors.append(argv[argv.index("--co-author") + 1])
        self.assertIn(author, authors)
        self.assertNotIn(LANE_AUTHOR, authors)
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


class ModelGuarantee(_LadderFixture):
    """A record whose model.requested differs from the dry-run --model stops."""

    def test_a_record_model_mismatch_stops_with_class_model(self):
        self.patch_plant(model_mismatch_stages=["tests"])
        proc = self.run_ladder()
        rec_id = self.load_plant().get("last_id") or "none"
        self.assert_stopped(
            proc, stage="tests", record=rec_id, reason="model",
        )


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
        self.close_tripped_record()
        self.patch_plant(trip_stages=[])
        ladder_id = self.ladder_record().get("id")
        second = self.invoke(["resume", ladder_id])
        self.assertEqual(second.returncode, 0, self.combined(second))
        self.assertEqual(self.dispatch_names().count("tests"), 1)
        self.assertGreaterEqual(len(self.land_argvs()), 1)
        self.assertGreaterEqual(len(self.gh_argvs()), 1)


class ExitClasses(_LadderFixture):
    """Every exit the suite observes is one of the wire's four."""

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


if __name__ == "__main__":
    unittest.main()
