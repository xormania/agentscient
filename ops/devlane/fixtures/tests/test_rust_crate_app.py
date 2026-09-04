"""rust-crate fixture-app tests, written from the slice-5 contract.

Contracts (only): the fixture-apps scope and the slices-3-to-5 plan in
the job input, using the slice-5 section (layout, seven faults by kind,
neighbours, probes, fixes, toolchain, manifest keys, the merged lever
`ops/bin/fixture.sh`). The app under
`ops/devlane/fixtures/apps/rust-crate` is the implementation and is not
read here beyond the paths the contract names. Slice 5 assigns no lever
change; `probe_timeout` and the preflight ignore list are slice 4's.

Red at this ref because that directory is absent: the existence test
fails on `FAULTS.json`. The K3-row assertion fails on FAULT-KINDS.md as
it stands (Python, PHP). Make/prove/grade cases invoke the merged lever
and fail on their own promises rather than on an import.

The app, its own tests, probes, fixes, FAULTS.json, and the K3 idiom
cell are the implementer's.
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

from test_fixture_manifests import KIND_IDS, parse_kind_rows, validate_manifest

REPO = Path(__file__).resolve().parents[4]
LEVER = REPO / "ops" / "bin" / "fixture.sh"
APPS = REPO / "ops" / "devlane" / "fixtures" / "apps"
APP = APPS / "rust-crate"
MANIFEST = APP / "FAULTS.json"
KINDS = APPS / "FAULT-KINDS.md"
CALIBRATION = REPO / "ops" / "conductor" / "findings" / "calibration.jsonl"

APP_NAME = "rust-crate"
AGENT = "Rust Crate Fixture Tester <rust-crate-fixture@example.invalid>"
RUN_CAP = 60
PROVE_CAP = 900
CHECK_CAP = 180
PROBE_CAP = 130
SUITES_CAP = 60
DISPATCH_CAP = 30
WARM_CAP = 180
METADATA_CAP = 30

EXPECTED_IDS = tuple(f"RC-{index:02d}" for index in range(1, 8))
REQUIRED_KINDS = frozenset({"K1", "K2", "K3", "K4", "K5", "K6", "K9"})
OMITTED_KINDS = frozenset({"K7", "K8"})
EXPECTED_KIND_VISIBLE = {
    "RC-01": ("K1", "audit"),
    "RC-02": ("K2", "both"),
    "RC-03": ("K3", "test"),
    "RC-04": ("K4", "audit"),
    "RC-05": ("K5", "test"),
    "RC-06": ("K6", "test"),
    "RC-07": ("K9", "audit"),
}
EXPECTED_SEVERITY = {
    "RC-01": "p1",
    "RC-02": "p1",
    "RC-03": "p2",
    "RC-04": "p1",
    "RC-05": "p2",
    "RC-06": "p2",
    "RC-07": "p2",
}
EXPECTED_LOCATION_PATHS = {
    "RC-01": "src/shell.rs",
    "RC-02": "src/store.rs",
    "RC-03": "src/render.rs",
    "RC-04": "src/audit.rs",
    "RC-05": "src/store.rs",
    "RC-06": "src/interval.rs",
    "RC-07": "Cargo.toml",
}
EXPECTED_DECLARATIONS = {
    "RC-01": (
        "User-supplied names are passed to Command as arguments, "
        "never through sh -c."
    ),
    "RC-02": "Record paths stay beneath the store root.",
    "RC-03": (
        "A count of zero is an answer and is distinct from an "
        "absent record."
    ),
    "RC-04": "Credentials never leave the process in failure logs.",
    "RC-05": (
        "An unreadable or corrupt store is reported as an error, "
        "never served as empty."
    ),
    "RC-06": (
        "Intervals are half-open, including their start and "
        "excluding their end."
    ),
    "RC-07": "Dependencies are pinned to one version and locked.",
}
SRC_MODULES = ("store", "interval", "shell", "audit", "render")
SRC_FILES = (
    "src/lib.rs",
    "src/store.rs",
    "src/interval.rs",
    "src/shell.rs",
    "src/audit.rs",
    "src/render.rs",
    "src/main.rs",
)
INTEGRATION_TESTS = (
    "tests/store.rs",
    "tests/interval.rs",
    "tests/render.rs",
)
LAYOUT_FILES = (
    "README.md",
    "Cargo.toml",
    "Cargo.lock",
    "rustfmt.toml",
    ".gitignore",
)
LAYOUT_DIRS = ("src", "tests", "probes", "fixes")
CARGO_TEST_NAMES = tuple(f"rc{index:02d}" for index in range(1, 7))
PROBE_TIMEOUT = 120
HEX_PIN = "=0.4.3"

LANE_COPY_PATHS = (
    "ops/devlane/fixtures/apps/FAULT-KINDS.md",
    "ops/bin/suites.sh",
    "ops/bin/dispatch.sh",
    "ops/conductor/tools/dispatch.sh",
    "ops/devlane/dispatch/launch.py",
    "ops/lane.conf",
    "ops/devlane/task/envelope.py",
    "ops/devlane/task/tests/support.py",
    "ops/devlane/task/tests/test_envelope.py",
)
CARGO_ENV_KEYS = (
    "CARGO_HOME",
    "CARGO_TARGET_DIR",
    "CARGO_TERM_COLOR",
    "RUSTUP_HOME",
    "RUSTUP_TOOLCHAIN",
    "RUSTFLAGS",
)

REC_ID = "20260904T000000Z-review-grok-rcrate01"
HARNESS = "grok"
MODEL = "grok-4.6"

ABSENT_STUB = b"#!/usr/bin/env bash\nexit 0\n"
COLOUR_RE = re.compile(r"\b(RED|GREEN|UNREACHABLE)\b")
FAULT_ID_RE = re.compile(r"\b(RC-\d{2})\b")
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
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
UNITTEST_RAN_RE = re.compile(r"Ran ([1-9]\d*) tests?")
CARGO_TEST_RAN_RE = re.compile(
    r"test result: ok\. (\d+) passed",
    re.IGNORECASE,
)
CONF_ASSIGN_RE = re.compile(
    r"^(?P<key>[A-Z][A-Z0-9_]*)='(?P<value>[^']*)'\s*$", re.MULTILINE
)

# Contract-derived dirty shapes at the practiced span (slice-5 Rust idiom).
KIND_DIRTY = {
    "K1": re.compile(r'"sh"|-c"|format!\('),
    "K2": re.compile(r"\.join\("),
    "K3": re.compile(r"unwrap_or\(0\)|== 0"),
    "K4": re.compile(r"env::vars|environment="),
    "K5": re.compile(r"Ok\(Vec::new\(\)\)|\.ok\(\)|let _ ="),
    "K6": re.compile(r"<= self\.end"),
    "K9": re.compile(r'= "\*"|\^|>='),
}

# Contract-derived clean neighbour shapes, discovered without FAULTS.json.
KIND_CLEAN = {
    "K1": re.compile(r'Command::new\("printf"\)'),
    "K2": re.compile(r"starts_with\("),
    "K3": re.compile(r"match label"),
    "K4": re.compile(r"\[REDACTED\]"),
    "K5": re.compile(r"fs::write\([^;]+\)\?"),
    "K6": re.compile(r"self\.start\.\.self\.end"),
    "K9": re.compile(r'hex\s*=\s*"=0\.4\.3"'),
}

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


def load_toml_object(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def fault_rows(data: dict) -> list[dict]:
    faults = data.get("faults")
    if not isinstance(faults, list):
        return []
    return [row for row in faults if isinstance(row, dict)]


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
        or not all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in lines
        )
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


def _as_lines(value) -> list[int] | None:
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in value
        )
    ):
        return [value[0], value[1]]
    return None


def _span_text(path: Path, lines: list[int]) -> str:
    start, end = lines
    body = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(body[start - 1 : end])


def _spans_overlap(path_a, lines_a, path_b, lines_b) -> bool:
    if path_a != path_b:
        return False
    span_a = _as_lines(lines_a)
    span_b = _as_lines(lines_b)
    if span_a is None or span_b is None:
        return False
    return span_a[0] <= span_b[1] and span_b[0] <= span_a[1]


def _strip_shell_comments(command: str) -> str:
    return "\n".join(
        line.split("#", 1)[0] for line in command.splitlines()
    )


def _conf_value(text: str, key: str) -> str | None:
    for match in CONF_ASSIGN_RE.finditer(text):
        if match.group("key") == key:
            return match.group("value")
    return None


def _probe_script_paths(command: str) -> list[str]:
    found: list[str] = []
    for token in command.split():
        if "probes/" in token or token.startswith("probes"):
            found.append(token)
    return found


def _patch_removed_lines(text: str) -> dict[str, list[int]]:
    current: str | None = None
    old_line = 0
    removed: dict[str, list[int]] = {}
    hunk_starts: dict[str, list[int]] = {}
    for line in text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip().removeprefix("b/")
            current = None if path == "/dev/null" else path
            if current is not None:
                removed.setdefault(current, [])
                hunk_starts.setdefault(current, [])
            continue
        hunk = HUNK_RE.match(line)
        if hunk is not None:
            old_line = int(hunk.group(1))
            if current is not None:
                hunk_starts[current].append(old_line)
            continue
        if current is None:
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("-") and not line.startswith("---"):
            removed[current].append(old_line)
            old_line += 1
        elif line.startswith("+") and not line.startswith("+++"):
            continue
        elif line.startswith(" "):
            old_line += 1
    for path, lines in list(removed.items()):
        if not lines:
            removed[path] = list(hunk_starts.get(path, []))
    return {path: lines for path, lines in removed.items() if path}


def _iter_app_sources(root: Path) -> list[tuple[str, Path, str]]:
    found: list[tuple[str, Path, str]] = []
    for folder in ("src", "tests"):
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.rs")):
            rel = path.relative_to(root).as_posix()
            found.append((rel, path, path.read_text(encoding="utf-8")))
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        found.append(
            ("Cargo.toml", cargo, cargo.read_text(encoding="utf-8"))
        )
    return found


def discover_clean_neighbours(
    root: Path,
) -> dict[str, list[tuple[str, int, int, str]]]:
    """Find clean-neighbour spans from the contract shapes, not FAULTS.json."""
    found: dict[str, list[tuple[str, int, int, str]]] = {
        kind: [] for kind in KIND_CLEAN
    }
    for rel, _path, text in _iter_app_sources(root):
        for kind, pattern in KIND_CLEAN.items():
            if kind == "K9" and rel != "Cargo.toml":
                continue
            if kind != "K9" and rel == "Cargo.toml":
                continue
            for match in pattern.finditer(text):
                start = text[: match.start()].count("\n") + 1
                end = text[: match.end()].count("\n") + 1
                snippet = "\n".join(text.splitlines()[start - 1 : end])
                found[kind].append((rel, start, end, snippet))
    return found


def _cargo_env_passthrough() -> dict[str, str]:
    extra: dict[str, str] = {}
    for key in CARGO_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            extra[key] = value
    return extra


class RustCrateExists(unittest.TestCase):
    def test_faults_json_exists(self):
        self.assertTrue(
            MANIFEST.is_file(),
            f"{MANIFEST} is missing; slice 5 plants apps/rust-crate",
        )


class RustCrateLayout(unittest.TestCase):
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
                    f"{APP / name} is missing; the contract names this "
                    "directory",
                )

    def test_src_lib_bin_and_modules_exist(self):
        for rel in SRC_FILES:
            with self.subTest(path=rel):
                self.assertTrue(
                    (APP / rel).is_file(),
                    f"{APP / rel} is missing; the crate is a lib and a bin",
                )
        text = (
            (APP / "src/lib.rs").read_text(encoding="utf-8")
            if (APP / "src/lib.rs").is_file()
            else ""
        )
        for name in SRC_MODULES:
            with self.subTest(module=name):
                self.assertIn(
                    f"pub mod {name}",
                    text,
                    "src/lib.rs must declare the contracted modules",
                )

    def test_integration_tests_exist(self):
        for rel in INTEGRATION_TESTS:
            with self.subTest(path=rel):
                self.assertTrue(
                    (APP / rel).is_file(),
                    f"{APP / rel} is missing; integration tests ship green",
                )

    def test_probes_and_fixes_exist(self):
        for index in range(1, 8):
            sh_name = f"probes/rc{index:02d}.sh"
            patch_name = f"fixes/rc{index:02d}.patch"
            with self.subTest(path=sh_name):
                self.assertTrue(
                    (APP / sh_name).is_file(),
                    f"{APP / sh_name} is missing",
                )
            with self.subTest(path=patch_name):
                self.assertTrue(
                    (APP / patch_name).is_file(),
                    f"{APP / patch_name} is missing",
                )
        for index in range(1, 7):
            rs_name = f"probes/rc{index:02d}.rs"
            with self.subTest(path=rs_name):
                self.assertTrue(
                    (APP / rs_name).is_file(),
                    f"{APP / rs_name} is missing; RC-01..RC-06 are "
                    "cargo test targets",
                )

    def test_cargo_toml_parses_as_the_contracted_crate(self):
        data = load_toml_object(APP / "Cargo.toml")
        package = data.get("package") if isinstance(data.get("package"), dict) else {}
        self.assertEqual(
            package.get("name"),
            "fixture-rust-crate",
            "Cargo.toml package name is fixture-rust-crate",
        )
        self.assertEqual(
            package.get("edition"),
            "2021",
            "edition 2021 so set_var in a probe is safe code",
        )
        self.assertIn("lib", data, "Cargo.toml must declare [lib]")
        bins = data.get("bin")
        self.assertIsInstance(bins, list, "Cargo.toml must declare [[bin]]")
        self.assertEqual(len(bins), 1, "exactly one [[bin]]")
        bin0 = bins[0] if bins and isinstance(bins[0], dict) else {}
        self.assertEqual(
            bin0.get("name"),
            "fixture-rust-crate",
            '[[bin]] name = "fixture-rust-crate"',
        )
        deps = (
            data.get("dependencies")
            if isinstance(data.get("dependencies"), dict)
            else {}
        )
        self.assertEqual(
            deps.get("hex"),
            HEX_PIN,
            f'hex must be pinned exactly as "{HEX_PIN}"',
        )
        self.assertIn("anyhow", deps, "anyhow is present (the K9 wildcard)")
        lints = data.get("lints") if isinstance(data.get("lints"), dict) else {}
        clippy = lints.get("clippy") if isinstance(lints.get("clippy"), dict) else {}
        self.assertTrue(clippy, "[lints.clippy] must be present")
        self.assertEqual(
            clippy.get("all"),
            "deny",
            '[lints.clippy] all = "deny"',
        )
        tests = data.get("test")
        self.assertIsInstance(
            tests,
            list,
            "Cargo.toml must declare [[test]] probe targets",
        )
        by_name = {
            row.get("name"): row
            for row in tests
            if isinstance(row, dict)
        }
        for name in CARGO_TEST_NAMES:
            with self.subTest(test=name):
                self.assertIn(
                    name,
                    by_name,
                    f"[[test]] name = {name!r} with test = false",
                )
                row = by_name.get(name) if isinstance(by_name.get(name), dict) else {}
                self.assertIs(
                    row.get("test"),
                    False,
                    f"{name} must set test = false (outside default discovery)",
                )
                path = row.get("path") if isinstance(row.get("path"), str) else ""
                self.assertTrue(
                    path.startswith("probes/") and path.endswith(".rs"),
                    f"{name} path must be under probes/: {path!r}",
                )

    def test_cargo_lock_names_anyhow_and_hex(self):
        lock_path = APP / "Cargo.lock"
        self.assertTrue(
            lock_path.is_file(),
            "Cargo.lock is committed generated data",
        )
        data = load_toml_object(lock_path)
        packages = data.get("package")
        if not isinstance(packages, list):
            packages = []
        names = {
            row.get("name")
            for row in packages
            if isinstance(row, dict)
        }
        self.assertIn("anyhow", names, "Cargo.lock must name the anyhow package")
        self.assertIn("hex", names, "Cargo.lock must name the hex package")

    def test_rustfmt_toml_pins_edition_and_width(self):
        data = load_toml_object(APP / "rustfmt.toml")
        self.assertEqual(
            data.get("edition"),
            "2021",
            "rustfmt.toml edition = 2021",
        )
        self.assertEqual(
            data.get("max_width"),
            100,
            "rustfmt.toml max_width = 100",
        )

    def test_gitignore_names_target(self):
        text = (
            (APP / ".gitignore").read_text(encoding="utf-8")
            if (APP / ".gitignore").is_file()
            else ""
        )
        self.assertRegex(
            text,
            r"(?m)^/target/?$",
            "the app .gitignore must name /target/ "
            "(the root gitignore is rooted)",
        )

    def test_readme_itself_declares_apparatus(self):
        text = (
            (APP / "README.md").read_text(encoding="utf-8")
            if (APP / "README.md").is_file()
            else ""
        )
        self.assertRegex(
            text,
            r"(?i)apparatus",
            "README.md itself must say the tree is apparatus, never product",
        )
        self.assertRegex(
            text,
            r"(?i)never product|not product|not a real project",
            "README.md must say this crate is never product code",
        )

    def test_readme_names_check_cargo_fetch_and_offline(self):
        text = (
            (APP / "README.md").read_text(encoding="utf-8")
            if (APP / "README.md").is_file()
            else ""
        )
        self.assertRegex(text, r"\bcargo fmt\b", "README.md must name cargo fmt")
        self.assertRegex(text, r"\bclippy\b", "README.md must name clippy")
        self.assertRegex(
            text,
            r"\bcargo test\b",
            "README.md must name cargo test",
        )
        self.assertRegex(
            text,
            r"\b--offline\b",
            "README.md must name --offline after the warm fetch",
        )
        self.assertRegex(
            text,
            r"\b--locked\b",
            "README.md must name --locked so the lock agrees",
        )
        self.assertRegex(
            text,
            r"\bcargo fetch\b",
            "README.md must name cargo fetch as the warm step",
        )
        self.assertRegex(
            text,
            r"\bCARGO_TARGET_DIR\b",
            "README.md must say CARGO_TARGET_DIR may point outside the scratch",
        )

    def test_readme_carries_one_declaration_per_fault(self):
        text = (
            (APP / "README.md").read_text(encoding="utf-8")
            if (APP / "README.md").is_file()
            else ""
        )
        for fault_id, quote in EXPECTED_DECLARATIONS.items():
            with self.subTest(fault=fault_id):
                self.assertRegex(
                    text,
                    rf"{re.escape(fault_id)}:",
                    f"README.md must label {fault_id}",
                )
                self.assertIn(
                    quote,
                    text,
                    f"README.md must carry the declared words for {fault_id}",
                )


class RustCrateKinds(unittest.TestCase):
    def test_fault_kinds_k3_row_names_rust(self):
        text = KINDS.read_text(encoding="utf-8") if KINDS.is_file() else ""
        rows = parse_kind_rows(text)
        self.assertIn("K3", rows, "FAULT-KINDS.md must have a K3 row")
        row = rows["K3"]
        self.assertIn(
            "a loose comparison (false as zero)",
            row,
            "K3 title is unchanged",
        )
        self.assertIn(
            "Rust",
            row,
            "slice 5 adds Rust to the K3 idiom cell",
        )


class RustCrateManifest(unittest.TestCase):
    def test_manifest_name_is_rust_crate(self):
        data = load_json_object(MANIFEST)
        self.assertEqual(
            data.get("name"),
            APP_NAME,
            "FAULTS.json name matches the app directory",
        )

    def test_manifest_has_seven_rows_over_seven_kinds(self):
        faults = fault_rows(load_json_object(MANIFEST))
        self.assertEqual(
            len(faults),
            7,
            f"seven planted faults, the eighth stays open; found {len(faults)}",
        )
        kinds = {row.get("kind") for row in faults}
        self.assertEqual(
            len(kinds),
            7,
            f"seven distinct kinds, found {sorted(kinds)}",
        )

    def test_manifest_cites_k1_to_k6_and_k9(self):
        faults = fault_rows(load_json_object(MANIFEST))
        kinds = {row.get("kind") for row in faults}
        self.assertTrue(
            kinds >= REQUIRED_KINDS,
            f"manifest must cite {sorted(REQUIRED_KINDS)}; found {sorted(kinds)}",
        )
        self.assertTrue(
            kinds.isdisjoint(OMITTED_KINDS),
            f"K7 is in python-service; K8 is in python-tooling and "
            f"symfony-app; found {sorted(kinds)}",
        )

    def test_manifest_ids_are_rc_01_to_rc_07(self):
        faults = fault_rows(load_json_object(MANIFEST))
        ids = tuple(row.get("id") for row in faults)
        self.assertEqual(
            ids,
            EXPECTED_IDS,
            "seven rows, ids RC-01 to RC-07; the eighth is left open",
        )

    def test_manifest_kind_visible_to_and_severity_match_the_contract(self):
        faults = fault_rows(load_json_object(MANIFEST))
        mapping = {
            row.get("id"): (row.get("kind"), row.get("visible_to"))
            for row in faults
        }
        self.assertEqual(
            mapping,
            EXPECTED_KIND_VISIBLE,
            "kind and visible_to must match the slice-5 fault table",
        )
        severities = {row.get("id"): row.get("severity") for row in faults}
        self.assertEqual(
            severities,
            EXPECTED_SEVERITY,
            "severity must match the slice-5 fault table",
        )

    def test_manifest_location_paths_match_the_contract(self):
        faults = fault_rows(load_json_object(MANIFEST))
        self.assertEqual(
            tuple(row.get("id") for row in faults),
            EXPECTED_IDS,
            "location paths are pinned per id, not by fixture luck",
        )
        for row in faults:
            fault_id = row.get("id")
            loc = row.get("location") if isinstance(row.get("location"), dict) else {}
            with self.subTest(fault=fault_id):
                self.assertEqual(
                    loc.get("path"),
                    EXPECTED_LOCATION_PATHS[fault_id],
                    f"{fault_id} location.path must be the contracted file",
                )

    def test_probe_timeout_is_120(self):
        data = load_json_object(MANIFEST)
        timeout = data.get("probe_timeout")
        self.assertIsInstance(
            timeout,
            int,
            "probe_timeout is a top-level integer (a patched probe recompiles)",
        )
        self.assertFalse(
            isinstance(timeout, bool),
            "probe_timeout must not be a JSON boolean",
        )
        self.assertEqual(
            timeout,
            PROBE_TIMEOUT,
            "probe_timeout is 120 seconds so cargo test after a patch can finish",
        )
        self.assertGreaterEqual(timeout, 1)
        self.assertLessEqual(timeout, 300)

    def test_needs_on_exactly_the_six_cargo_rows(self):
        faults = fault_rows(load_json_object(MANIFEST))
        self.assertEqual(
            tuple(row.get("id") for row in faults),
            EXPECTED_IDS,
        )
        needs_ids = []
        for row in faults:
            needs = row.get("needs")
            if isinstance(needs, list) and needs:
                needs_ids.append(row.get("id"))
                joined = " ".join(str(item) for item in needs)
                self.assertIn(
                    "command -v cargo",
                    joined,
                    f"{row.get('id')} needs must gate on cargo",
                )
        self.assertEqual(
            needs_ids,
            list(EXPECTED_IDS[:6]),
            "needs on RC-01 to RC-06 only; RC-07 is grep and needs none",
        )
        rc07 = faults[6]
        rc07_needs = rc07.get("needs")
        self.assertTrue(
            rc07_needs in (None, [], ())
            or (isinstance(rc07_needs, list) and not rc07_needs),
            "RC-07 must not carry needs; grep is RED with no toolchain",
        )
        rc07_probe = rc07.get("probe") if isinstance(rc07.get("probe"), str) else ""
        self.assertRegex(
            rc07_probe,
            r"\bgrep\b",
            "RC-07 probe is grep of Cargo.toml",
        )
        self.assertNotRegex(
            rc07_probe,
            r"\bcargo\b",
            "RC-07 probe needs no cargo",
        )

    def test_toolchain_install_and_ready_present(self):
        data = load_json_object(MANIFEST)
        toolchain = (
            data.get("toolchain")
            if isinstance(data.get("toolchain"), dict)
            else {}
        )
        install = toolchain.get("install") if isinstance(toolchain.get("install"), str) else ""
        ready = toolchain.get("ready") if isinstance(toolchain.get("ready"), str) else ""
        self.assertRegex(
            _strip_shell_comments(install),
            r"\bcargo fetch\b",
            "toolchain.install is cargo fetch",
        )
        ready_text = _strip_shell_comments(ready)
        self.assertRegex(
            ready_text,
            r"command -v cargo",
            "toolchain.ready checks cargo is on PATH",
        )
        self.assertRegex(
            ready_text,
            r"\bcargo metadata\b",
            "toolchain.ready runs cargo metadata",
        )
        self.assertRegex(
            ready_text,
            r"\b--offline\b",
            "toolchain.ready is offline",
        )
        self.assertRegex(
            ready_text,
            r"--format-version",
            "toolchain.ready asks cargo metadata for format-version 1",
        )

    def test_check_command_names_fmt_clippy_and_test(self):
        check = load_json_object(MANIFEST).get("check")
        text = check if isinstance(check, str) else ""
        stripped = _strip_shell_comments(text)
        self.assertRegex(
            stripped,
            r"\bcargo fmt\b",
            "check includes cargo fmt --check (comments do not count)",
        )
        self.assertRegex(
            stripped,
            r"\bclippy\b",
            "check includes cargo clippy --offline --all-targets",
        )
        self.assertRegex(
            stripped,
            r"\bcargo test\b",
            "check includes cargo test --offline --locked",
        )
        self.assertRegex(stripped, r"\b--offline\b")
        self.assertRegex(stripped, r"\b--locked\b")

    def test_not_planted_names_k7_and_k8(self):
        data = load_json_object(MANIFEST)
        not_planted = data.get("not_planted")
        self.assertIsInstance(
            not_planted,
            dict,
            "not_planted names the kinds this app leaves open",
        )
        self.assertIn("K7", not_planted, "K7 is in python-service")
        self.assertIn("K8", not_planted, "K8 is in python-tooling and symfony-app")

    def test_manifest_sweep_accepts_faults_json(self):
        problems = validate_manifest(APP, set(KIND_IDS))
        self.assertEqual(
            problems,
            [],
            f"the slice-1 sweep must accept rust-crate FAULTS.json: {problems}",
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
            prefix="rust-crate-app-", dir="/tmp"
        )
        root = Path(self._tmp.name)
        self.root = root
        self.home = root / "home"
        self.home.mkdir()
        self.conf_path = root / "copy-list.txt"
        self.lane_conf_path = root / "lane.conf"
        self.lane_conf_path.write_text(
            "LANE_NAME='agentscient'\n", encoding="utf-8"
        )
        listed = "".join(f"{path}\n" for path in LANE_COPY_PATHS)
        _plant_bytes(self, self.conf_path, listed.encode("utf-8"))

    def tearDown(self):
        try:
            self.assertEqual(
                {str(path): _store_snap(path) for path in _live_fixture_roots()},
                self._live_before,
                "live fixture state mutated",
            )
            self.assertEqual(
                {
                    str(path): _store_snap(path)
                    for path in _live_findings_stores()
                },
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
        cargo: bool = True,
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
        if cargo:
            env.update(_cargo_env_passthrough())
        self.assertNotIn("XDG_STATE_HOME", env)
        if agent is not None:
            env["WF_AGENT"] = agent
        if extra:
            env.update(extra)
        return env

    def scratch_env(self, *, cargo: bool = True) -> dict[str, str]:
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
        }
        if cargo:
            env.update(_cargo_env_passthrough())
        self.assertNotIn("LANE_CONF", env)
        self.assertNotIn("LAUNCHER_PIN", env)
        self.assertNotIn("XDG_STATE_HOME", env)
        self.assertNotIn("WF_AGENT", env)
        return env

    def path_without_cargo(self) -> str:
        kept: list[str] = []
        for item in os.environ.get("PATH", "/usr/bin:/bin").split(":"):
            if not item:
                continue
            if (Path(item) / "cargo").exists():
                continue
            kept.append(item)
        for essential in ("/usr/bin", "/bin"):
            if essential not in kept:
                kept.append(essential)
        self.assertTrue(kept, "PATH without cargo must still run sh and grep")
        return ":".join(kept)


class RustCrateMakeProve(_RepoFreeze):
    def invoke(
        self,
        argv: list[str],
        *,
        agent: str | None = AGENT,
        extra: dict[str, str] | None = None,
        timeout: int = RUN_CAP,
        cwd: Path | None = None,
        lever: Path | None = None,
        cargo: bool = True,
    ):
        env = self.env(agent=agent, extra=extra, cargo=cargo)
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
                f"colour line names an RC-* fault id: {line!r}",
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

    def made_app(self, name: str) -> Path:
        self.assertTrue(
            LEVER.is_file(),
            "INVALID: ops/bin/fixture.sh missing; slice 1 must be merged",
        )
        target = self.root / name
        self.assertFalse(target.exists())
        proc = self.make(target)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        return self.parse_dir(proc)

    def git(self, directory: Path, *args: str):
        proc = subprocess.run(
            ["git", *args],
            cwd=str(directory),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"git {args} in {directory}: {proc.stderr or proc.stdout}",
        )
        return proc

    def run_probe(self, directory: Path, command: str) -> str:
        self.assertTrue(command.strip(), "probe command is empty")
        env = self.scratch_env()
        try:
            proc = subprocess.run(
                ["/bin/sh", "-c", command],
                cwd=str(directory),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=PROBE_CAP,
            )
        except subprocess.TimeoutExpired:
            return "UNREACHABLE"
        if proc.returncode in {126, 127} or proc.returncode < 0:
            return "UNREACHABLE"
        return "GREEN" if proc.returncode == 0 else "RED"

    def apply_fix(self, directory: Path, rel: str) -> bytes:
        patch = directory / rel
        self.assertTrue(patch.is_file(), f"fix {rel} is missing")
        data = patch.read_bytes()
        self.assertTrue(data, f"fix {rel} is empty")
        check = subprocess.run(
            ["git", "apply", "--check", str(patch)],
            cwd=str(directory),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            check.returncode,
            0,
            f"git apply --check {rel}: {check.stderr or check.stdout}",
        )
        applied = subprocess.run(
            ["git", "apply", str(patch)],
            cwd=str(directory),
            env=self.git_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            applied.returncode,
            0,
            f"git apply {rel}: {applied.stderr or applied.stdout}",
        )
        return data

    def reset_tree(self, directory: Path) -> None:
        self.git(directory, "reset", "--hard", "HEAD")

    def load_faults(self, directory: Path) -> list[dict]:
        faults = fault_rows(load_json_object(directory / "FAULTS.json"))
        self.assertEqual(
            tuple(row.get("id") for row in faults),
            EXPECTED_IDS,
            "seven planted faults must be present before independent proofs run",
        )
        return faults

    def cargo_ready_skip(self, directory: Path) -> str | None:
        if shutil.which("cargo") is None:
            return "UNREACHABLE: no cargo on PATH"
        env = self.scratch_env()
        try:
            proc = subprocess.run(
                [
                    "cargo",
                    "metadata",
                    "--offline",
                    "--format-version",
                    "1",
                ],
                cwd=str(directory),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=METADATA_CAP,
            )
        except subprocess.TimeoutExpired:
            return "UNREACHABLE: cargo metadata --offline failed in the scratch"
        if proc.returncode != 0:
            return "UNREACHABLE: cargo metadata --offline failed in the scratch"
        return None

    def warm_crate(self, directory: Path) -> None:
        env = self.scratch_env()
        try:
            proc = subprocess.run(
                ["cargo", "build", "--offline", "--all-targets"],
                cwd=str(directory),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=WARM_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"cargo build --offline exceeded {WARM_CAP}s: {exc}")
        self.assertEqual(
            proc.returncode,
            0,
            "cargo build --offline --all-targets must warm the crate: "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )

    def test_make_rust_crate_into_a_temp_directory_succeeds(self):
        made = self.made_app("made")
        for name in LAYOUT_FILES:
            with self.subTest(copied=name):
                self.assertTrue(
                    (made / name).is_file(),
                    f"make copies the app to DIR root; missing {name}",
                )
        self.assertTrue(
            (made / "FAULTS.json").is_file(),
            "make copies FAULTS.json",
        )
        for name in LAYOUT_DIRS:
            with self.subTest(copied=name):
                self.assertTrue(
                    (made / name).is_dir(),
                    f"make copies the app to DIR root; missing {name}/",
                )
        for rel in LANE_COPY_PATHS:
            with self.subTest(copied=rel):
                self.assertTrue(
                    (made / rel).is_file(),
                    f"the lane copy list must ride into DIR: missing {rel}",
                )

    def test_scratch_runs_suites_and_dispatch_dry_run(self):
        made = self.made_app("portable")
        self.assertTrue((made / "ops/bin/suites.sh").is_file())
        self.assertTrue((made / "ops/bin/dispatch.sh").is_file())
        self.assertTrue((made / "ops/devlane/dispatch/launch.py").is_file())
        self.assertTrue((made / "ops/lane.conf").is_file())
        env = self.scratch_env()
        try:
            suites = subprocess.run(
                ["bash", str(made / "ops" / "bin" / "suites.sh")],
                cwd=str(made),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=SUITES_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"suites.sh in the scratch exceeded {SUITES_CAP}s: {exc}")
        self.assertEqual(
            suites.returncode,
            0,
            f"bash ops/bin/suites.sh must be green in the scratch: "
            f"stdout={suites.stdout!r} stderr={suites.stderr!r}",
        )
        combined = (suites.stdout or "") + (suites.stderr or "")
        ran = UNITTEST_RAN_RE.search(combined)
        self.assertIsNotNone(
            ran,
            "suites.sh must actually run tests, not skip every suite as "
            f"ABSENT: {combined!r}",
        )
        self.assertGreaterEqual(int(ran.group(1)), 1, combined)
        self.assertNotIn("FAILED", combined)
        scope = self.root / "dry-run-scope.txt"
        _plant_bytes(self, scope, b"fixture-apps slice-5 dry-run scope\n")
        try:
            dry = subprocess.run(
                [
                    "bash",
                    str(made / "ops" / "bin" / "dispatch.sh"),
                    "--worktree",
                    str(made),
                    "--job",
                    "sweep",
                    "--harness",
                    "claude",
                    "--scope-file",
                    str(scope),
                    "--dry-run",
                ],
                cwd=str(made),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=DISPATCH_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"dispatch.sh --dry-run exceeded {DISPATCH_CAP}s: {exc}")
        self.assertEqual(
            dry.returncode,
            0,
            f"dispatch.sh --dry-run must resolve from the copied conf: "
            f"stdout={dry.stdout!r} stderr={dry.stderr!r}",
        )
        lines = [ln for ln in (dry.stdout or "").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, dry.stdout)
        payload = json.loads(lines[0])
        self.assertIn("launcher", payload)
        self.assertIn("argv", payload)
        launcher = payload["launcher"]
        self.assertEqual(
            launcher.get("source"),
            "sibling",
            "dry-run must resolve the launcher from the copied tree, not the env",
        )
        launch_path = Path(str(launcher.get("path") or ""))
        self.assertEqual(
            launch_path.resolve(),
            (made / "ops" / "devlane" / "dispatch" / "launch.py").resolve(),
        )
        argv = payload.get("argv")
        self.assertIsInstance(argv, list)
        conf_text = (made / "ops" / "lane.conf").read_text(encoding="utf-8")
        model = _conf_value(conf_text, "MODEL_CLAUDE_READ")
        effort = _conf_value(conf_text, "EFFORT_CLAUDE")
        self.assertTrue(model, "copied lane.conf must declare MODEL_CLAUDE_READ")
        self.assertTrue(effort, "copied lane.conf must declare EFFORT_CLAUDE")
        self.assertIn("--model", argv)
        self.assertIn(model, argv)
        self.assertIn("--effort", argv)
        self.assertIn(effort, argv)

    def test_prove_without_cargo_colours_six_unreachable_and_rc07_red(self):
        target = self.root / "prove-no-cargo"
        proc_make = self.make(target)
        self.assertEqual(
            proc_make.returncode,
            0,
            proc_make.stderr or proc_make.stdout,
        )
        proc = self.invoke(
            ["prove", str(target)],
            agent=None,
            extra={"PATH": self.path_without_cargo()},
            timeout=RUN_CAP,
            cargo=False,
        )
        rows = self.parse_prove(proc.stdout)
        self.assertEqual(
            set(rows),
            set(EXPECTED_IDS),
            f"prove must colour every planted fault: {proc.stdout!r} "
            f"stderr={proc.stderr!r}",
        )
        for fault_id in EXPECTED_IDS[:6]:
            self.assertEqual(
                rows[fault_id],
                "UNREACHABLE",
                f"{fault_id} needs cargo; without it the colour is "
                f"UNREACHABLE: {proc.stdout!r}",
            )
        self.assertEqual(
            rows["RC-07"],
            "RED",
            f"RC-07 is grep and RED with no toolchain: {proc.stdout!r}",
        )
        self.assertNotIn("GREEN", set(rows.values()))
        counts = self.parse_counts(proc.stdout)
        self.assertEqual(counts["unreachable"], 6, proc.stdout)
        self.assertEqual(counts["red"], 1, proc.stdout)
        self.assertEqual(counts["green"], 0, proc.stdout)
        self.assertEqual(
            proc.returncode,
            1,
            "mixed UNREACHABLE/RED is not every expected colour: "
            f"stderr={proc.stderr!r} stdout={proc.stdout!r}",
        )

    def test_prove_reports_every_planted_fault_red_when_cargo_is_ready(self):
        target = self.root / "prove-fresh"
        proc_make = self.make(target)
        self.assertEqual(
            proc_make.returncode,
            0,
            proc_make.stderr or proc_make.stdout,
        )
        made = self.parse_dir(proc_make)
        reason = self.cargo_ready_skip(made)
        if reason:
            self.skipTest(reason)
        self.warm_crate(made)
        proc = self.invoke(
            ["prove", str(made)],
            agent=None,
            timeout=PROVE_CAP,
        )
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
        self.assertNotIn("UNREACHABLE", set(rows.values()))
        counts = self.parse_counts(proc.stdout)
        self.assertEqual(counts["unreachable"], 0, proc.stdout)
        self.assertEqual(counts["red"], len(EXPECTED_IDS), proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_prove_fixed_reports_every_probe_green_when_cargo_is_ready(self):
        target = self.root / "prove-fixed"
        proc_make = self.make(target)
        self.assertEqual(proc_make.returncode, 0, proc_make.stderr or proc_make.stdout)
        made = self.parse_dir(proc_make)
        reason = self.cargo_ready_skip(made)
        if reason:
            self.skipTest(reason)
        self.warm_crate(made)
        proc = self.invoke(
            ["prove", "--fixed", str(made)],
            agent=None,
            timeout=PROVE_CAP,
        )
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

    def test_each_planted_fault_is_proved_by_its_own_probe(self):
        made = self.made_app("independent-probes")
        reason = self.cargo_ready_skip(made)
        if reason:
            self.skipTest(reason)
        self.warm_crate(made)
        faults = self.load_faults(made)
        snapshots = []
        for row in faults:
            loc = row.get("location") if isinstance(row.get("location"), dict) else {}
            loc_path = loc.get("path") if isinstance(loc.get("path"), str) else ""
            loc_lines = _as_lines(loc.get("lines"))
            self.assertTrue(loc_path, f"{row.get('id')} location.path missing")
            self.assertIsNotNone(
                loc_lines, f"{row.get('id')} location.lines missing"
            )
            path = made / loc_path
            self.assertTrue(
                path.is_file(),
                f"{row.get('id')} location {loc_path} missing",
            )
            span = _span_text(path, loc_lines)
            self.assertTrue(span.strip(), f"{row.get('id')} location span is empty")
            snapshots.append((row, loc_path, loc_lines, span, path.read_bytes()))

        for row, loc_path, loc_lines, span, loc_before in snapshots:
            fault_id = row.get("id")
            kind = row.get("kind")
            probe_cmd = row.get("probe") if isinstance(row.get("probe"), str) else ""
            fix_rel = row.get("fix") if isinstance(row.get("fix"), str) else ""
            with self.subTest(fault=fault_id, stage="kind-and-red"):
                dirty = KIND_DIRTY.get(kind)
                self.assertIsNotNone(dirty, f"no dirty shape for {kind}")
                self.assertRegex(
                    span,
                    dirty,
                    f"{fault_id} practiced span must look like {kind}, "
                    f"not a label: {span!r}",
                )
                colour = self.run_probe(made, probe_cmd)
                self.assertEqual(
                    colour,
                    "RED",
                    f"{fault_id} probe must be RED while planted: {probe_cmd!r}",
                )

            probe_files = _probe_script_paths(probe_cmd)
            self.assertTrue(
                probe_files,
                f"{fault_id} probe must name a path under probes/",
            )
            probe_before = {
                rel: (made / rel).read_bytes()
                for rel in probe_files
                if (made / rel).is_file()
            }
            self.assertEqual(
                set(probe_before),
                set(probe_files),
                f"{fault_id} probe path missing: {probe_cmd!r}",
            )

            with self.subTest(fault=fault_id, stage="own-fix"):
                patch = self.apply_fix(made, fix_rel)
                loc_after = (made / loc_path).read_bytes()
                self.assertNotEqual(
                    loc_after,
                    loc_before,
                    f"{fault_id} fix must change {loc_path}",
                )
                self.assertTrue(loc_after, f"{fault_id} fix emptied {loc_path}")
                for rel, data in probe_before.items():
                    landed = (made / rel).read_bytes()
                    self.assertEqual(
                        landed,
                        data,
                        f"{fault_id} fix must not rewrite the probe {rel}",
                    )
                    self.assertEqual(len(landed), len(data))
                changed = [
                    line
                    for line in self.git(made, "diff", "--name-only").stdout.splitlines()
                    if line.strip()
                ]
                self.assertEqual(
                    set(changed),
                    {loc_path},
                    f"{fault_id} fix must change only {loc_path}, found {changed}",
                )
                removed = _patch_removed_lines(patch.decode("utf-8"))
                self.assertEqual(
                    set(removed),
                    {loc_path},
                    f"{fault_id} fix must touch only {loc_path}, "
                    f"found {sorted(removed)}",
                )
                start, end = loc_lines
                self.assertTrue(
                    removed[loc_path],
                    f"{fault_id} fix has no changed lines to constrain",
                )
                for line_no in removed[loc_path]:
                    self.assertGreaterEqual(
                        line_no,
                        start,
                        f"{fault_id} fix line {line_no} is before declared "
                        f"span {start}-{end}",
                    )
                    self.assertLessEqual(
                        line_no,
                        end,
                        f"{fault_id} fix line {line_no} is after declared "
                        f"span {start}-{end}",
                    )
                loc_text_after = (made / loc_path).read_text(encoding="utf-8")
                for (
                    other_row,
                    other_path,
                    _other_lines,
                    other_span,
                    other_bytes,
                ) in snapshots:
                    if other_row.get("id") == fault_id:
                        continue
                    if other_path == loc_path:
                        self.assertIn(
                            other_span,
                            loc_text_after,
                            f"{fault_id} fix must leave {other_row.get('id')} "
                            "planted",
                        )
                    else:
                        self.assertEqual(
                            (made / other_path).read_bytes(),
                            other_bytes,
                            f"{fault_id} fix must not touch {other_path} "
                            f"({other_row.get('id')})",
                        )
                colour = self.run_probe(made, probe_cmd)
                self.assertEqual(
                    colour,
                    "GREEN",
                    f"{fault_id} probe must be GREEN after its own fix",
                )

            with self.subTest(fault=fault_id, stage="others-stay-red"):
                for other in faults:
                    other_id = other.get("id")
                    if other_id == fault_id:
                        continue
                    other_probe = (
                        other.get("probe")
                        if isinstance(other.get("probe"), str)
                        else ""
                    )
                    colour = self.run_probe(made, other_probe)
                    self.assertEqual(
                        colour,
                        "RED",
                        f"{other_id} must stay RED while only {fault_id} is fixed",
                    )

            self.reset_tree(made)
            reset = (made / loc_path).read_bytes()
            self.assertEqual(reset, loc_before, f"{fault_id} reset did not restore")
            colour = self.run_probe(made, probe_cmd)
            self.assertEqual(
                colour,
                "RED",
                f"{fault_id} probe must be RED again after reset",
            )

    def test_clean_neighbours_are_found_apart_from_the_manifest(self):
        made = self.made_app("neighbours")
        faults = self.load_faults(made)
        locations = []
        for row in faults:
            loc = row.get("location") if isinstance(row.get("location"), dict) else {}
            locations.append(
                (loc.get("path"), loc.get("lines"), row.get("kind"), row)
            )
        discovered = discover_clean_neighbours(made)
        for kind in REQUIRED_KINDS:
            with self.subTest(kind=kind, stage="discovered"):
                self.assertTrue(
                    discovered.get(kind),
                    f"no clean neighbour for {kind} in src/, tests/, or "
                    "Cargo.toml; discovery does not read FAULTS.json "
                    "neighbour fields",
                )

        for path, lines, kind, row in locations:
            fault_id = row.get("id")
            with self.subTest(fault=fault_id, stage="not-the-fault"):
                candidates = []
                for rel, start, end, snippet in discovered.get(kind, []):
                    if _spans_overlap(rel, [start, end], path, lines):
                        continue
                    candidates.append((rel, start, end, snippet))
                self.assertTrue(
                    candidates,
                    f"{fault_id} ({kind}) has no independently found "
                    "clean neighbour",
                )
                neighbour = (
                    row.get("neighbour")
                    if isinstance(row.get("neighbour"), dict)
                    else {}
                )
                self.assertTrue(
                    any(
                        _spans_overlap(
                            neighbour.get("path"),
                            neighbour.get("lines"),
                            rel,
                            [start, end],
                        )
                        for rel, start, end, _snippet in candidates
                    ),
                    f"{fault_id} manifest neighbour is not one of the "
                    f"independently found clean {kind} spans: "
                    f"{candidates!r} vs {neighbour!r}",
                )

    def test_app_check_green_when_cargo_is_ready(self):
        made = self.made_app("check-fresh")
        reason = self.cargo_ready_skip(made)
        if reason:
            self.skipTest(reason)
        self.warm_crate(made)
        env = self.scratch_env()
        for rel in INTEGRATION_TESTS:
            self.assertTrue(
                (made / rel).is_file(),
                f"fresh make must carry {rel}",
            )
        try:
            fmt = subprocess.run(
                ["cargo", "fmt", "--check"],
                cwd=str(made),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=CHECK_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"cargo fmt --check exceeded {CHECK_CAP}s: {exc}")
        self.assertEqual(
            fmt.returncode,
            0,
            f"cargo fmt --check must be green: stdout={fmt.stdout!r} "
            f"stderr={fmt.stderr!r}",
        )
        try:
            clippy = subprocess.run(
                [
                    "cargo",
                    "clippy",
                    "--offline",
                    "--all-targets",
                    "--",
                    "-D",
                    "warnings",
                ],
                cwd=str(made),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=CHECK_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"cargo clippy exceeded {CHECK_CAP}s: {exc}")
        self.assertEqual(
            clippy.returncode,
            0,
            f"cargo clippy --offline --all-targets -D warnings must be green: "
            f"stdout={clippy.stdout!r} stderr={clippy.stderr!r}",
        )
        try:
            unit = subprocess.run(
                ["cargo", "test", "--offline", "--locked"],
                cwd=str(made),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=CHECK_CAP,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"cargo test exceeded {CHECK_CAP}s: {exc}")
        unit_out = (unit.stdout or "") + (unit.stderr or "")
        self.assertEqual(
            unit.returncode,
            0,
            f"cargo test --offline --locked must be green: {unit_out!r}",
        )
        ran = CARGO_TEST_RAN_RE.search(unit_out)
        self.assertIsNotNone(
            ran,
            f"cargo test must collect tests, not 0 passed: {unit_out!r}",
        )
        self.assertGreaterEqual(int(ran.group(1)), 1, unit_out)
        manifest = load_json_object(made / "FAULTS.json")
        check = manifest.get("check") if isinstance(manifest.get("check"), str) else ""
        self.assertTrue(check.strip(), "fresh make must carry a check command")
        stripped = _strip_shell_comments(check)
        self.assertRegex(stripped, r"\bcargo fmt\b")
        self.assertRegex(stripped, r"\bclippy\b")
        self.assertRegex(stripped, r"\bcargo test\b")
        try:
            proc = subprocess.run(
                ["bash", "-c", check],
                cwd=str(made),
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


class RustCrateGrade(_RepoFreeze):
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
        self.assertEqual(
            len(loaded["result"]["envelope"]["findings"]),
            len(findings),
        )
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
            self.assertEqual(
                tuple(row.get("id") for row in faults),
                EXPECTED_IDS,
                "grade scores RC-01 as caught, not a lucky first row",
            )
            first = faults[0]
            findings = [
                _finding(
                    "p1",
                    _where(first.get("location") or {}),
                    "PLANTED_CAUGHT_RC_LOCATION",
                ),
                _finding(
                    "p3",
                    "src/unrelated-not-a-fault.rs:1-2",
                    "PLANTED_UNMATCHED_RC",
                ),
                _finding("p3", "the CLI help text", "PLANTED_UNLOCATED_RC"),
            ]
        else:
            findings = [
                _finding(
                    "p1",
                    "src/shell.rs:1-1",
                    "PLANTED_CAUGHT_RC_LOCATION",
                ),
                _finding(
                    "p3",
                    "src/unrelated-not-a-fault.rs:1-2",
                    "PLANTED_UNMATCHED_RC",
                ),
                _finding("p3", "the CLI help text", "PLANTED_UNLOCATED_RC"),
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
        self.assertEqual(
            rec.read_bytes(),
            before,
            "grade writes nothing to the record",
        )
        self.assertIn(HARNESS, proc.stdout)
        self.assertIn(MODEL, proc.stdout)
        counts = self.parse_counts(proc.stdout)
        self.assertEqual(counts["caught"], 1, proc.stdout)
        self.assertEqual(counts["false-positive"], 0, proc.stdout)
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

    def test_grade_scores_a_false_positive_on_a_neighbour(self):
        source_root = APP if APP.is_dir() else self.root / "missing-app"
        discovered = discover_clean_neighbours(source_root)
        faults = fault_rows(load_json_object(self.staged_manifest()))
        self.assertEqual(
            tuple(row.get("id") for row in faults),
            EXPECTED_IDS,
            "grade FP proof needs the seven planted faults",
        )
        findings = []
        for row in faults:
            kind = row.get("kind")
            loc = row.get("location") if isinstance(row.get("location"), dict) else {}
            picked = None
            for rel, start, end, _snippet in discovered.get(kind, []):
                if _spans_overlap(
                    rel, [start, end], loc.get("path"), loc.get("lines")
                ):
                    continue
                picked = (rel, start, end)
                break
            self.assertIsNotNone(
                picked,
                f"{row.get('id')} ({kind}) has no independently found "
                "clean neighbour",
            )
            findings.append(
                _finding(
                    "p2",
                    f"{picked[0]}:{picked[1]}-{picked[2]}",
                    f"PLANTED_NEIGHBOUR_CLEAN_{row.get('id')}",
                )
            )
        rec = self.plant_record(findings)
        proc = self.invoke(["grade", str(rec), APP_NAME])
        self.assertEqual(
            proc.returncode,
            0,
            f"grade must score independently found neighbour findings: "
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
            "every independently found neighbour finding is a false positive",
        )
        self.assertEqual(counts["missed"], n_faults, proc.stdout)
        self.assertEqual(counts["unmatched"], 0, proc.stdout)
        self.assertEqual(counts["unlocated"], 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
