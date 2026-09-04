"""python-tooling fixture-app tests, written from the slice-2 contract.

Contracts (only): the fixture-apps scope and the slice-2 plan in the
job input (layout, seven faults by kind, neighbours, the merged lever
`ops/bin/fixture.sh`). The app under
`ops/devlane/fixtures/apps/python-tooling` is the implementation and is
not read here beyond the paths the contract names.

Red at this ref because that directory is absent: the existence test
fails on `FAULTS.json`. Make/prove/grade cases invoke the merged lever
and fail on their own promises (expected ids and colours, make's
directory, grade exit 0) rather than on an import.

The app's own `tests/`, probes, fixes, and `FAULTS.json` are the
implementer's.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from test_fixture_manifests import KIND_IDS, validate_manifest

REPO = Path(__file__).resolve().parents[4]
LEVER = REPO / "ops" / "bin" / "fixture.sh"
APPS = REPO / "ops" / "devlane" / "fixtures" / "apps"
APP = APPS / "python-tooling"
MANIFEST = APP / "FAULTS.json"
CALIBRATION = REPO / "ops" / "conductor" / "findings" / "calibration.jsonl"

APP_NAME = "python-tooling"
AGENT = "Python Tooling Fixture Tester <python-tooling-fixture@example.invalid>"
COPY_REL = "ops/devlane/fixtures/apps/FAULT-KINDS.md"
RUN_CAP = 60
CHECK_CAP = 60

EXPECTED_IDS = tuple(f"PT-{index:02d}" for index in range(1, 8))
REQUIRED_KINDS = frozenset({"K1", "K2", "K3", "K4", "K5", "K6", "K8"})
OMITTED_KINDS = frozenset({"K7", "K9"})
EXPECTED_KIND_VISIBLE = {
    "PT-01": ("K1", "audit"),
    "PT-02": ("K2", "both"),
    "PT-03": ("K3", "test"),
    "PT-04": ("K4", "audit"),
    "PT-05": ("K5", "test"),
    "PT-06": ("K6", "test"),
    "PT-07": ("K8", "audit"),
}
LAYOUT_FILES = ("README.md", "ruff.toml")
LAYOUT_DIRS = ("tool", "tests", "probes", "fixes")
PACKAGING_NAMES = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "pdm.lock",
)

REC_ID = "20260904T000000Z-review-grok-ptool01"
HARNESS = "grok"
MODEL = "grok-4.6"

ABSENT_STUB = b"#!/usr/bin/env bash\nexit 0\n"
COLOUR_RE = re.compile(r"\b(RED|GREEN|UNREACHABLE)\b")
FAULT_ID_RE = re.compile(r"\b(PT-\d{2})\b")
COUNTS_RE = re.compile(
    r"red=(?P<red>\d+)\s+green=(?P<green>\d+)\s+"
    r"unreachable=(?P<unreachable>\d+)"
)
GRADE_COUNTS_RE = re.compile(
    r"caught=(?P<caught>\d+)\s+missed=(?P<missed>\d+)\s+"
    r"false-positive=(?P<fp>\d+)\s+unmatched=(?P<unmatched>\d+)\s+"
    r"unlocated=(?P<unlocated>\d+)"
)
GRADE_RATE_RE = re.compile(
    r"caught/faults=(?P<caught>0(?:\.\d+)?|1(?:\.0+)?)\s+"
    r"false-positive/neighbours=(?P<fp>0(?:\.\d+)?|1(?:\.0+)?)"
)

CALIBRATE_STUB = r'''#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def refuse(cls, expected, found, needed):
    print(
        f"{cls}: expected {expected}; found {found}; needed {needed}",
        file=sys.stderr,
    )
    raise SystemExit(2)

verb = sys.argv[1] if len(sys.argv) > 1 else ""
if verb != "calibrate":
    refuse("arguments", "calibrate", verb or "none", "name calibrate")
agent = os.environ.get("WF_AGENT", "")
if "<" not in agent or ">" not in agent:
    refuse(
        "identity",
        "Name <address>",
        agent or "unset",
        "export WF_AGENT",
    )
capture = os.environ.get("CALIBRATE_CAPTURE")
if not capture:
    refuse("calibration", "CALIBRATE_CAPTURE", "unset", "set it in tests")
Path(capture).write_text(sys.stdin.read(), encoding="utf-8")
'''


def load_json_object(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def fault_rows(data: dict) -> list[dict]:
    faults = data.get("faults")
    if not isinstance(faults, list):
        return []
    return [row for row in faults if isinstance(row, dict)]


def _rule_prefix(token: str) -> str:
    return str(token).rstrip("0123456789")


def _ruff_select(text: str) -> list[str]:
    if not text.strip():
        return []
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    lint = data.get("lint")
    raw = None
    if isinstance(lint, dict) and "select" in lint:
        raw = lint.get("select")
    elif "select" in data:
        raw = data.get("select")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def _store_snap(path: Path) -> tuple[str, tuple[str, ...] | None]:
    if not path.exists():
        return ("absent", None)
    if path.is_file():
        return ("file", (str(path.stat().st_size),))
    if not path.is_dir():
        return ("other", None)
    names = tuple(sorted(p.name for p in path.iterdir()))
    return ("dir", names)


def _live_fixture_roots() -> list[Path]:
    paths: list[Path] = []
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        paths.append(Path(xdg) / "agentscient" / "fixtures")
    paths.append(Path.home() / ".local" / "state" / "agentscient" / "fixtures")
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path if not path.exists() else path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _live_findings_stores() -> list[Path]:
    paths: list[Path] = []
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        paths.append(Path(xdg) / "agentscient" / "findings.db")
    paths.append(Path.home() / ".local" / "state" / "agentscient" / "findings.db")
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path if not path.exists() else path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _plant_bytes(testcase: unittest.TestCase, path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    landed = path.read_bytes()
    testcase.assertEqual(landed, data, f"plant did not land intact: {path}")
    testcase.assertEqual(len(landed), len(data))


def _where(span: dict) -> str:
    path = span.get("path")
    lines = span.get("lines")
    if not isinstance(path, str) or not path.strip():
        return "unlocated-span"
    if (
        not isinstance(lines, list)
        or len(lines) != 2
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in lines)
    ):
        return f"{path}:1-1"
    return f"{path}:{lines[0]}-{lines[1]}"


def _finding(severity: str, where: str, claim: str) -> dict:
    return {
        "severity": severity,
        "where": where,
        "claim": claim,
        "reproduce": "true",
    }


class PythonToolingExists(unittest.TestCase):
    def test_faults_json_exists(self):
        self.assertTrue(
            MANIFEST.is_file(),
            f"{MANIFEST} is missing; slice 2 plants apps/python-tooling",
        )


class PythonToolingLayout(unittest.TestCase):
    def test_layout_paths_exist(self):
        for name in LAYOUT_FILES:
            with self.subTest(path=name):
                self.assertTrue(
                    (APP / name).is_file(),
                    f"{APP / name} is missing; the contract names this file",
                )
        for name in LAYOUT_DIRS:
            with self.subTest(path=name):
                self.assertTrue(
                    (APP / name).is_dir(),
                    f"{APP / name} is missing; the contract names this directory",
                )

    def test_ruff_toml_selects_dev_dialect_not_security(self):
        text = (
            (APP / "ruff.toml").read_text(encoding="utf-8")
            if (APP / "ruff.toml").is_file()
            else ""
        )
        select = _ruff_select(text)
        prefixes = {_rule_prefix(token) for token in select}
        for family in ("E", "F", "I", "B"):
            with self.subTest(family=family):
                self.assertIn(
                    family,
                    prefixes,
                    f"ruff.toml must select {family} (dev dialect); found {select!r}",
                )
        self.assertNotIn(
            "S",
            prefixes,
            "ruff.toml must not select S, so K1 and K4 survive the app lint",
        )

    def test_readme_names_apparatus_and_omits_k9(self):
        text = (
            (APP / "README.md").read_text(encoding="utf-8")
            if (APP / "README.md").is_file()
            else ""
        )
        blob = text
        manifest_text = (
            MANIFEST.read_text(encoding="utf-8") if MANIFEST.is_file() else ""
        )
        blob = f"{text}\n{manifest_text}"
        self.assertRegex(
            blob,
            r"(?i)apparatus",
            "README must say the tree is apparatus, never product",
        )
        self.assertRegex(
            blob,
            r"\bK9\b",
            "the dialect has no packaging or lock; the manifest must say K9 does not apply",
        )
        self.assertRegex(
            blob.lower(),
            r"does not apply|not apply|not planted",
            "K9 must be named as not applying to this dialect",
        )

    def test_no_packaging_or_lock(self):
        self.assertTrue(
            APP.is_dir(),
            f"{APP} is missing; python-tooling is stdlib only, no packaging",
        )
        for name in PACKAGING_NAMES:
            with self.subTest(path=name):
                self.assertFalse(
                    (APP / name).is_file(),
                    f"{name} must not exist: K9 does not apply to this dialect",
                )


class PythonToolingManifest(unittest.TestCase):
    def test_manifest_has_six_to_eight_rows_over_six_or_more_kinds(self):
        faults = fault_rows(load_json_object(MANIFEST))
        self.assertGreaterEqual(len(faults), 6, f"need six to eight faults, found {len(faults)}")
        self.assertLessEqual(len(faults), 8, f"need six to eight faults, found {len(faults)}")
        kinds = {row.get("kind") for row in faults}
        self.assertGreaterEqual(
            len(kinds),
            6,
            f"need six or more distinct kinds, found {sorted(kinds)}",
        )

    def test_manifest_cites_k1_k2_k3_k4_k5_k6_k8(self):
        faults = fault_rows(load_json_object(MANIFEST))
        kinds = {row.get("kind") for row in faults}
        self.assertTrue(
            kinds >= REQUIRED_KINDS,
            f"manifest must cite {sorted(REQUIRED_KINDS)}; found {sorted(kinds)}",
        )
        self.assertTrue(
            kinds.isdisjoint(OMITTED_KINDS),
            f"K7 is for python-service; K9 does not apply here; found {sorted(kinds)}",
        )

    def test_manifest_ids_are_pt_01_to_pt_07(self):
        faults = fault_rows(load_json_object(MANIFEST))
        ids = tuple(row.get("id") for row in faults)
        self.assertEqual(
            ids,
            EXPECTED_IDS,
            "seven rows, ids PT-01 to PT-07; the eighth is left open",
        )

    def test_manifest_kind_and_visible_to_match_the_contract(self):
        faults = fault_rows(load_json_object(MANIFEST))
        mapping = {
            row.get("id"): (row.get("kind"), row.get("visible_to"))
            for row in faults
        }
        self.assertEqual(
            mapping,
            EXPECTED_KIND_VISIBLE,
            "kind and visible_to must match the slice-2 fault table",
        )

    def test_check_command_names_unittest_and_ruff(self):
        check = load_json_object(MANIFEST).get("check")
        text = check if isinstance(check, str) else ""
        self.assertIn(
            "unittest",
            text,
            "check is unittest discovery over tests/ from the app root",
        )
        self.assertIn(
            "ruff",
            text,
            "check includes ruff check . from the app root",
        )

    def test_manifest_sweep_accepts_faults_json(self):
        problems = validate_manifest(APP, set(KIND_IDS))
        self.assertEqual(
            problems,
            [],
            f"the slice-1 sweep must accept python-tooling FAULTS.json: {problems}",
        )


class _RepoFreeze(unittest.TestCase):
    """Live fixture roots, findings store, calibration export, and this repo stay put."""

    def setUp(self):
        self.assertIsNotNone(shutil.which("git"), "INVALID: git not on PATH")
        self.assertIsNotNone(shutil.which("bash"), "INVALID: bash not on PATH")
        self._live_before = {
            str(path): _store_snap(path) for path in _live_fixture_roots()
        }
        self._findings_before = {
            str(path): _store_snap(path) for path in _live_findings_stores()
        }
        self._calibration_before = _store_snap(CALIBRATION)
        self._head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        self._diff_before = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            check=False,
        ).stdout
        self._tmp = tempfile.TemporaryDirectory(
            prefix="python-tooling-app-", dir="/tmp"
        )
        root = Path(self._tmp.name)
        self.root = root
        self.home = root / "home"
        self.home.mkdir()
        self.conf_path = root / "copy-list.txt"
        self.lane_conf_path = root / "lane.conf"
        self.lane_conf_path.write_text("LANE_NAME='agentscient'\n", encoding="utf-8")
        _plant_bytes(self, self.conf_path, f"{COPY_REL}\n".encode("utf-8"))

    def tearDown(self):
        try:
            self.assertEqual(
                {str(path): _store_snap(path) for path in _live_fixture_roots()},
                self._live_before,
                "live fixture state mutated",
            )
            self.assertEqual(
                {str(path): _store_snap(path) for path in _live_findings_stores()},
                self._findings_before,
                "live findings store mutated",
            )
            self.assertEqual(
                _store_snap(CALIBRATION),
                self._calibration_before,
                "tracked calibration.jsonl mutated",
            )
            head_after = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            self.assertEqual(head_after, self._head_before, "real repo HEAD moved")
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
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }

    def env(
        self,
        *,
        agent: str | None = AGENT,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "TZ": "UTC",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "LANE_CONF": str(self.lane_conf_path),
            "FIXTURE_COPY_LIST": str(self.conf_path),
        }
        self.assertNotIn("XDG_STATE_HOME", env)
        if agent is not None:
            env["WF_AGENT"] = agent
        if extra:
            env.update(extra)
        return env


class PythonToolingMakeProve(_RepoFreeze):
    def invoke(
        self,
        argv: list[str],
        *,
        agent: str | None = AGENT,
        extra: dict[str, str] | None = None,
        timeout: int = RUN_CAP,
        cwd: Path | None = None,
        lever: Path | None = None,
    ):
        env = self.env(agent=agent, extra=extra)
        if agent is None:
            self.assertNotIn("WF_AGENT", env)
        lever_path = lever or LEVER
        try:
            return subprocess.run(
                [str(lever_path), *argv],
                cwd=str(cwd or REPO),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"fixture.sh {argv} exceeded {timeout}s: {exc}")

    def make(self, target: Path):
        return self.invoke(["make", APP_NAME, str(target)])

    def parse_dir(self, proc) -> Path:
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        self.assertEqual(
            len(lines),
            1,
            f"make prints one directory on stdout: {proc.stdout!r} "
            f"stderr={proc.stderr!r}",
        )
        path = Path(lines[0].strip())
        self.assertTrue(path.is_dir(), f"printed DIR is not a directory: {path}")
        return path

    def parse_prove(self, stdout: str) -> dict[str, str]:
        rows: dict[str, str] = {}
        for line in stdout.splitlines():
            colour_match = COLOUR_RE.search(line)
            if not colour_match:
                continue
            colour = colour_match.group(1)
            id_match = FAULT_ID_RE.search(line)
            self.assertIsNotNone(
                id_match,
                f"colour line names a PT-* fault id: {line!r}",
            )
            fault_id = id_match.group(1)
            self.assertNotIn(fault_id, rows, f"duplicate colour for {fault_id}")
            rows[fault_id] = colour
        return rows

    def parse_counts(self, stdout: str) -> dict[str, int]:
        match = COUNTS_RE.search(stdout)
        self.assertIsNotNone(
            match,
            f"prove prints red= green= unreachable= counts: {stdout!r}",
        )
        return {key: int(value) for key, value in match.groupdict().items()}

    def test_make_python_tooling_into_a_temp_directory_succeeds(self):
        self.assertTrue(
            LEVER.is_file(),
            "INVALID: ops/bin/fixture.sh missing; slice 1 must be merged",
        )
        target = self.root / "made"
        self.assertFalse(target.exists())
        proc = self.make(target)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        made = self.parse_dir(proc)
        self.assertEqual(made.resolve(), target.resolve())
        for name in LAYOUT_FILES:
            with self.subTest(copied=name):
                self.assertTrue(
                    (made / name).is_file(),
                    f"make copies the app to DIR root; missing {name}",
                )
        self.assertTrue((made / "FAULTS.json").is_file(), "make copies FAULTS.json")
        for name in LAYOUT_DIRS:
            with self.subTest(copied=name):
                self.assertTrue(
                    (made / name).is_dir(),
                    f"make copies the app to DIR root; missing {name}/",
                )
        self.assertTrue(
            (made / COPY_REL).is_file(),
            "the stub copy list must ride into DIR",
        )

    def test_prove_reports_every_planted_fault_red(self):
        target = self.root / "prove-fresh"
        self.make(target)
        proc = self.invoke(["prove", str(target)], agent=None)
        rows = self.parse_prove(proc.stdout)
        self.assertEqual(
            set(rows),
            set(EXPECTED_IDS),
            f"prove must colour every planted fault: {proc.stdout!r} "
            f"stderr={proc.stderr!r}",
        )
        for fault_id in EXPECTED_IDS:
            self.assertEqual(
                rows[fault_id],
                "RED",
                f"{fault_id} must be RED on a fresh make: {proc.stdout!r}",
            )
        self.assertNotIn("GREEN", set(rows.values()))
        counts = self.parse_counts(proc.stdout)
        self.assertEqual(counts["unreachable"], 0, proc.stdout)
        self.assertEqual(counts["red"], len(EXPECTED_IDS), proc.stdout)
        # Merged lever: exit 0 when every probe has the expected colour.
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_prove_fixed_reports_every_probe_green(self):
        target = self.root / "prove-fixed"
        self.make(target)
        proc = self.invoke(["prove", "--fixed", str(target)], agent=None)
        rows = self.parse_prove(proc.stdout)
        self.assertEqual(
            set(rows),
            set(EXPECTED_IDS),
            f"prove --fixed must colour every planted fault: {proc.stdout!r} "
            f"stderr={proc.stderr!r}",
        )
        for fault_id in EXPECTED_IDS:
            self.assertEqual(
                rows[fault_id],
                "GREEN",
                f"{fault_id} must be GREEN after planted fixes: {proc.stdout!r}",
            )
        self.assertNotIn("RED", set(rows.values()))
        self.assertNotIn("UNREACHABLE", set(rows.values()))
        counts = self.parse_counts(proc.stdout)
        self.assertEqual(counts["unreachable"], 0, proc.stdout)
        self.assertEqual(counts["green"], len(EXPECTED_IDS), proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_app_check_exits_0_on_a_fresh_make(self):
        target = self.root / "check-fresh"
        self.make(target)
        manifest = load_json_object(target / "FAULTS.json")
        check = manifest.get("check") if isinstance(manifest.get("check"), str) else ""
        self.assertTrue(
            check.strip(),
            "fresh make must carry a check command so the app suite can run",
        )
        env = self.env(agent=None)
        try:
            proc = subprocess.run(
                ["bash", "-c", check],
                cwd=str(target),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=CHECK_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"app check exceeded {CHECK_CAP}s: {exc}")
        self.assertEqual(
            proc.returncode,
            0,
            f"app check must be green on a fresh make: stdout={proc.stdout!r} "
            f"stderr={proc.stderr!r}",
        )


class PythonToolingGrade(_RepoFreeze):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "grade-repo"
        self.repo.mkdir()
        self.staged = self.repo / "ops" / "bin" / "fixture.sh"
        self.capture = self.root / "calibrate.stdin"
        self._stage_lever()
        self._plant_findings_stub()
        self._plant_lane_conf()
        self._stage_manifest()

    def _stage_lever(self) -> None:
        self.staged.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(
            LEVER.is_file(),
            "INVALID: ops/bin/fixture.sh missing; slice 1 must be merged",
        )
        data = LEVER.read_bytes()
        self.staged.write_bytes(data)
        landed = self.staged.read_bytes()
        self.assertEqual(landed, data, "copy-lever-bytes did not land intact")
        self.assertEqual(len(landed), len(data))
        self.assertNotEqual(landed, ABSENT_STUB)
        self.staged.chmod(self.staged.stat().st_mode | stat.S_IXUSR)

    def _plant_findings_stub(self) -> None:
        path = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        data = CALIBRATE_STUB.encode("utf-8")
        _plant_bytes(self, path, data)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _plant_lane_conf(self) -> None:
        _plant_bytes(
            self,
            self.repo / "ops" / "lane.conf",
            b"LANE_NAME='agentscient'\n",
        )

    def _stage_manifest(self) -> None:
        dest = (
            self.repo
            / "ops"
            / "devlane"
            / "fixtures"
            / "apps"
            / APP_NAME
            / "FAULTS.json"
        )
        if MANIFEST.is_file():
            data = MANIFEST.read_bytes()
            _plant_bytes(self, dest, data)
            self.assertEqual(dest.read_bytes(), data)

    def staged_manifest(self) -> Path:
        return (
            self.repo
            / "ops"
            / "devlane"
            / "fixtures"
            / "apps"
            / APP_NAME
            / "FAULTS.json"
        )

    def invoke(self, argv: list[str], *, agent: str | None = AGENT):
        env = self.env(agent=agent, extra={"CALIBRATE_CAPTURE": str(self.capture)})
        if agent is None:
            self.assertNotIn("WF_AGENT", env)
        try:
            return subprocess.run(
                [str(self.staged), *argv],
                cwd=str(self.repo),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=RUN_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"fixture.sh {argv} exceeded {RUN_CAP}s: {exc}")

    def plant_record(self, findings: list[dict]) -> Path:
        payload = {
            "id": REC_ID,
            "job": "security-audit",
            "harness": {"name": HARNESS},
            "model": {"ran": MODEL, "requested": MODEL},
            "result": {"envelope": {"findings": findings}},
        }
        raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
        path = self.root / f"{REC_ID}.json"
        _plant_bytes(self, path, raw)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["id"], REC_ID)
        self.assertEqual(len(loaded["result"]["envelope"]["findings"]), len(findings))
        return path

    def parse_counts(self, stdout: str) -> dict[str, int]:
        match = GRADE_COUNTS_RE.search(stdout)
        self.assertIsNotNone(
            match,
            f"grade prints caught/missed/false-positive/unmatched/"
            f"unlocated counts: {stdout!r}",
        )
        raw = match.groupdict()
        return {
            "caught": int(raw["caught"]),
            "missed": int(raw["missed"]),
            "false-positive": int(raw["fp"]),
            "unmatched": int(raw["unmatched"]),
            "unlocated": int(raw["unlocated"]),
        }

    def parse_rates(self, stdout: str) -> dict[str, float]:
        match = GRADE_RATE_RE.search(stdout)
        self.assertIsNotNone(
            match,
            f"grade prints caught/faults and false-positive/neighbours: "
            f"{stdout!r}",
        )
        return {key: float(value) for key, value in match.groupdict().items()}

    def test_grade_scores_a_planted_review(self):
        faults = fault_rows(load_json_object(self.staged_manifest()))
        if faults:
            first = faults[0]
            findings = [
                _finding(
                    "p1",
                    _where(first.get("location") or {}),
                    "PLANTED_CAUGHT_PT_LOCATION",
                ),
                _finding(
                    "p2",
                    _where(first.get("neighbour") or {}),
                    "PLANTED_FP_PT_NEIGHBOUR",
                ),
                _finding(
                    "p3",
                    "tool/unrelated-not-a-fault.py:1-2",
                    "PLANTED_UNMATCHED_PT",
                ),
                _finding("p3", "the CLI help text", "PLANTED_UNLOCATED_PT"),
            ]
        else:
            findings = [
                _finding("p1", "tool/cli.py:1-1", "PLANTED_CAUGHT_PT_LOCATION"),
                _finding("p2", "tool/cli.py:2-2", "PLANTED_FP_PT_NEIGHBOUR"),
                _finding(
                    "p3",
                    "tool/unrelated-not-a-fault.py:1-2",
                    "PLANTED_UNMATCHED_PT",
                ),
                _finding("p3", "the CLI help text", "PLANTED_UNLOCATED_PT"),
            ]
        rec = self.plant_record(findings)
        before = rec.read_bytes()
        proc = self.invoke(["grade", str(rec), APP_NAME])
        self.assertEqual(
            proc.returncode,
            0,
            f"grade must score a planted review of {APP_NAME}: "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertEqual(rec.read_bytes(), before, "grade writes nothing to the record")
        self.assertIn(HARNESS, proc.stdout)
        self.assertIn(MODEL, proc.stdout)
        counts = self.parse_counts(proc.stdout)
        self.assertEqual(counts["caught"], 1, proc.stdout)
        self.assertEqual(counts["false-positive"], 1, proc.stdout)
        self.assertEqual(counts["unmatched"], 1, proc.stdout)
        self.assertEqual(counts["unlocated"], 1, proc.stdout)
        self.assertEqual(
            counts["missed"],
            len(EXPECTED_IDS) - 1,
            proc.stdout,
        )
        rates = self.parse_rates(proc.stdout)
        n_faults = len(EXPECTED_IDS)
        self.assertEqual(
            rates["caught"],
            float(f"{counts['caught'] / n_faults:.6f}"),
        )
        self.assertEqual(
            rates["fp"],
            float(f"{counts['false-positive'] / n_faults:.6f}"),
        )

    def test_grade_scores_neighbour_findings_as_false_positives(self):
        faults = fault_rows(load_json_object(self.staged_manifest()))
        if faults:
            findings = [
                _finding(
                    "p2",
                    _where(row.get("neighbour") or {}),
                    f"PLANTED_NEIGHBOUR_CLEAN_{row.get('id')}",
                )
                for row in faults
            ]
        else:
            findings = [
                _finding("p2", "tool/cli.py:2-2", "PLANTED_NEIGHBOUR_CLEAN_PT-01")
            ]
        rec = self.plant_record(findings)
        proc = self.invoke(["grade", str(rec), APP_NAME])
        self.assertEqual(
            proc.returncode,
            0,
            f"grade must score neighbour-only findings: "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        counts = self.parse_counts(proc.stdout)
        n_faults = len(EXPECTED_IDS)
        self.assertEqual(
            counts["caught"],
            0,
            "a clean neighbour must not count as a caught fault",
        )
        self.assertEqual(
            counts["false-positive"],
            n_faults,
            "every neighbour finding is a false positive",
        )
        self.assertEqual(counts["missed"], n_faults, proc.stdout)
        self.assertEqual(counts["unmatched"], 0, proc.stdout)
        self.assertEqual(counts["unlocated"], 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
