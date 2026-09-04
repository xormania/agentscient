"""Manifest-sweep tests, written from the slice-1 contract.

Pins `ops/devlane/fixtures/apps/FAULT-KINDS.md` and every
`apps/*/FAULTS.json` found. The kinds file is the subject and is not
written here. A missing kinds file is one red
(`test_fault_kinds_md_exists`). Every other case reads that file first
so a missing file is not a collection error: each assertion goes red on
the contract promise.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
APPS = REPO / "ops" / "devlane" / "fixtures" / "apps"
KINDS = APPS / "FAULT-KINDS.md"

KIND_IDS = tuple(f"K{i}" for i in range(1, 10))
KIND_TITLES = {
    "K1": "untrusted string reaching a shell or argv",
    "K2": "a path escaping its root",
    "K3": "a loose comparison (false as zero)",
    "K4": "a secret in the environment or a log",
    "K5": "an error swallowed",
    "K6": "a boundary off by one (half-open intervals)",
    "K7": "a test proving against a stub",
    "K8": "an oracle taken from the code under test",
    "K9": "an unpinned or drifted dependency",
}
TOP_KEYS = ("name", "check", "faults")
FAULT_KEYS = (
    "id",
    "kind",
    "severity",
    "location",
    "declared",
    "practiced",
    "finding",
    "neighbour",
    "probe",
    "fix",
    "visible_to",
)
LOC_KEYS = ("path", "lines")
QUOTE_KEYS = ("text", "path", "lines")
NEIGHBOUR_KEYS = ("path", "lines", "why_clean")
SEVERITIES = {"p1", "p2", "p3"}
VISIBLE = {"test", "audit", "both"}
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d{2}$")
KIND_TOKEN = re.compile(r"\bK[1-9]\b")


def _plant_bytes(testcase: unittest.TestCase, path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    landed = path.read_bytes()
    testcase.assertEqual(landed, data, f"plant did not land intact: {path}")
    testcase.assertEqual(len(landed), len(data))


def _span_text(path: Path, lines: list[int]) -> str:
    start, end = lines
    body = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(body[start - 1 : end])


def _as_lines(value) -> list[int] | None:
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    ):
        return [value[0], value[1]]
    return None


def validate_manifest(app_root: Path, kind_ids: set[str]) -> list[str]:
    """Return problems; empty means the manifest satisfies the sweep."""
    problems: list[str] = []
    manifest_path = app_root / "FAULTS.json"
    if not manifest_path.is_file():
        return [f"{manifest_path} is missing"]
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{manifest_path} is not JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{manifest_path} is not an object"]
    for key in TOP_KEYS:
        if key not in data:
            problems.append(f"missing top-level key {key}")
    if problems:
        return problems
    if not isinstance(data["name"], str) or not data["name"].strip():
        problems.append("name must be a non-empty string")
    if not isinstance(data["check"], str) or not data["check"].strip():
        problems.append("check must be a non-empty command")
    faults = data.get("faults")
    if not isinstance(faults, list):
        problems.append("faults must be a list")
        return problems
    n_faults = len(faults)
    if n_faults < 6 or n_faults > 8:
        problems.append(f"need six to eight faults, found {n_faults}")
    ids: list[str] = []
    kinds_seen: set[str] = set()
    for index, fault in enumerate(faults, 1):
        prefix = f"fault[{index}]"
        if not isinstance(fault, dict):
            problems.append(f"{prefix} is not an object")
            continue
        for key in FAULT_KEYS:
            if key not in fault:
                problems.append(f"{prefix} missing {key}")
        if any(key not in fault for key in FAULT_KEYS):
            continue
        fid = fault["id"]
        if not isinstance(fid, str) or not ID_RE.match(fid):
            problems.append(f"{prefix} id {fid!r} is not <APP>-<nn>")
        else:
            ids.append(fid)
        kind = fault["kind"]
        if kind not in kind_ids:
            problems.append(f"{prefix} kind {kind!r} does not resolve")
        else:
            kinds_seen.add(kind)
        if fault["severity"] not in SEVERITIES:
            problems.append(f"{prefix} severity {fault['severity']!r}")
        if fault["visible_to"] not in VISIBLE:
            problems.append(f"{prefix} visible_to {fault['visible_to']!r}")
        if not isinstance(fault["finding"], str) or not fault["finding"].strip():
            problems.append(f"{prefix} finding is empty")
        if not isinstance(fault["probe"], str) or not fault["probe"].strip():
            problems.append(f"{prefix} probe is empty")
        else:
            for token in fault["probe"].split():
                if "/" in token:
                    probe_path = app_root / token
                    if not probe_path.is_file():
                        problems.append(
                            f"{prefix} probe path {token} is missing"
                        )
        fix_path = app_root / str(fault["fix"])
        if not fix_path.is_file():
            problems.append(f"{prefix} fix {fault['fix']} is missing")
        problems.extend(
            _validate_loc(app_root, fault["location"], f"{prefix}.location")
        )
        problems.extend(
            _validate_quote(app_root, fault["declared"], f"{prefix}.declared")
        )
        problems.extend(
            _validate_quote(app_root, fault["practiced"], f"{prefix}.practiced")
        )
        problems.extend(
            _validate_neighbour(
                app_root, fault["neighbour"], f"{prefix}.neighbour"
            )
        )
    if len(ids) != len(set(ids)):
        problems.append(f"fault ids are not unique: {ids}")
    if n_faults >= 6 and len(kinds_seen) < 6:
        problems.append(
            f"need six or more distinct kinds, found {sorted(kinds_seen)}"
        )
    return problems


def _validate_loc(app_root: Path, loc, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(loc, dict):
        return [f"{label} is not an object"]
    for key in LOC_KEYS:
        if key not in loc:
            problems.append(f"{label} missing {key}")
    if problems:
        return problems
    return _validate_file_span(app_root, loc["path"], loc["lines"], label)


def _validate_quote(app_root: Path, quote, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(quote, dict):
        return [f"{label} is not an object"]
    for key in QUOTE_KEYS:
        if key not in quote:
            problems.append(f"{label} missing {key}")
    if problems:
        return problems
    text = quote["text"]
    if not isinstance(text, str) or not text.strip():
        problems.append(f"{label} text is empty")
        return problems
    problems.extend(
        _validate_file_span(app_root, quote["path"], quote["lines"], label)
    )
    if problems:
        return problems
    span = _span_text(app_root / quote["path"], quote["lines"])
    if text not in span:
        problems.append(
            f"{label} quote is not present verbatim at the stated span"
        )
    return problems


def _validate_neighbour(app_root: Path, neighbour, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(neighbour, dict):
        return [f"{label} is not an object"]
    for key in NEIGHBOUR_KEYS:
        if key not in neighbour:
            problems.append(f"{label} missing {key}")
    if problems:
        return problems
    if (
        not isinstance(neighbour["why_clean"], str)
        or not neighbour["why_clean"].strip()
    ):
        problems.append(f"{label} why_clean is empty")
    problems.extend(
        _validate_file_span(
            app_root, neighbour["path"], neighbour["lines"], label
        )
    )
    return problems


def _validate_file_span(app_root: Path, rel, lines, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(rel, str) or not rel.strip():
        return [f"{label} path is empty"]
    path = app_root / rel
    if not path.is_file():
        return [f"{label} path {rel} does not exist"]
    span = _as_lines(lines)
    if span is None:
        return [f"{label} lines must be [start, end]"]
    start, end = span
    n_lines = len(path.read_text(encoding="utf-8").splitlines())
    if start < 1 or end < start or end > n_lines:
        problems.append(
            f"{label} span {start}-{end} is outside 1-{n_lines}"
        )
    return problems


class _KindsMixin:
    def kinds_text(self) -> str:
        self.assertTrue(
            KINDS.is_file(),
            f"{KINDS} is missing; the contract requires FAULT-KINDS.md",
        )
        text = KINDS.read_text(encoding="utf-8")
        self.assertTrue(text.strip(), "FAULT-KINDS.md is empty")
        return text

    def kind_ids(self) -> set[str]:
        found = set(KIND_TOKEN.findall(self.kinds_text()))
        self.assertEqual(set(KIND_IDS), found)
        return found


class FaultKindsExist(_KindsMixin, unittest.TestCase):
    def test_fault_kinds_md_exists(self):
        self.assertTrue(
            KINDS.is_file(),
            f"{KINDS} is missing; the contract requires FAULT-KINDS.md",
        )

    def test_fault_kinds_md_declares_the_nine_stable_ids(self):
        text = self.kinds_text()
        for kind_id in KIND_IDS:
            with self.subTest(kind=kind_id):
                self.assertRegex(
                    text,
                    rf"\b{kind_id}\b",
                    f"{KINDS} must declare {kind_id}",
                )
        self.assertEqual(set(KIND_TOKEN.findall(text)), set(KIND_IDS))

    def test_fault_kinds_md_names_the_nine_kinds(self):
        text = self.kinds_text()
        for kind_id, title in KIND_TITLES.items():
            with self.subTest(kind=kind_id):
                self.assertIn(title, text, f"{kind_id} title missing")

    def test_fault_kinds_md_states_idioms_and_probe_shapes(self):
        text = self.kinds_text()
        for idiom in ("Python", "PHP", "Rust"):
            self.assertIn(idiom, text, f"idiom {idiom} missing")
        for shape in ("failing test", "static grep", "runtime check"):
            self.assertIn(shape, text, f"probe shape {shape!r} missing")


class ManifestSweep(_KindsMixin, unittest.TestCase):
    def test_every_found_manifest_validates(self):
        kind_ids = self.kind_ids()
        manifests = sorted(APPS.glob("*/FAULTS.json"))
        for path in manifests:
            with self.subTest(app=path.parent.name):
                problems = validate_manifest(path.parent, kind_ids)
                self.assertEqual(problems, [], problems)

    def test_a_manifest_missing_a_required_field_is_refused(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-missing-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            del payload["faults"][0]["finding"]
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(
                any("finding" in item for item in problems),
                problems,
            )

    def test_a_manifest_with_an_unknown_kind_is_refused(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-kind-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            payload["faults"][0]["kind"] = "K99"
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(any("K99" in item for item in problems), problems)

    def test_a_manifest_with_an_empty_quote_is_refused(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-quote-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            payload["faults"][0]["declared"]["text"] = "   "
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(
                any("declared" in item and "empty" in item for item in problems),
                problems,
            )

    def test_a_quote_missing_from_its_stated_span_is_refused(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-span-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            payload["faults"][0]["practiced"]["text"] = "THIS QUOTE IS ABSENT"
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(
                any("verbatim" in item for item in problems),
                problems,
            )

    def test_a_missing_probe_or_fix_is_refused(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-probe-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            (app / "probes" / "p01.sh").unlink()
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(any("probe" in item for item in problems), problems)
        with tempfile.TemporaryDirectory(prefix="manifest-fix-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            (app / "fixes" / "p01.patch").unlink()
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(any("fix" in item for item in problems), problems)

    def test_duplicate_ids_too_few_rows_and_too_few_kinds_are_refused(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-ids-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            payload["faults"][1]["id"] = payload["faults"][0]["id"]
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(any("unique" in item for item in problems), problems)
        with tempfile.TemporaryDirectory(prefix="manifest-count-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            payload["faults"] = payload["faults"][:2]
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(
                any("six to eight" in item for item in problems),
                problems,
            )
        with tempfile.TemporaryDirectory(prefix="manifest-kinds-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            for fault in payload["faults"]:
                fault["kind"] = "K1"
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(
                any("distinct kinds" in item for item in problems),
                problems,
            )

    def test_a_span_past_eof_or_a_missing_neighbour_file_is_refused(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-eof-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            payload["faults"][0]["location"]["lines"] = [1, 999]
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(any("outside" in item for item in problems), problems)
        with tempfile.TemporaryDirectory(prefix="manifest-neigh-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            payload = json.loads((app / "FAULTS.json").read_text())
            payload["faults"][0]["neighbour"]["path"] = "no-such-neigh.py"
            planted = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            _plant_bytes(self, app / "FAULTS.json", planted)
            problems = validate_manifest(app, kind_ids)
            self.assertTrue(
                any("no-such-neigh.py" in item for item in problems),
                problems,
            )

    def test_a_valid_six_row_manifest_has_no_problems(self):
        kind_ids = self.kind_ids()
        with tempfile.TemporaryDirectory(prefix="manifest-ok-") as tmp:
            app = self._plant_valid_app(Path(tmp) / "app")
            problems = validate_manifest(app, kind_ids)
            self.assertEqual(problems, [], problems)

    def _plant_valid_app(self, app: Path) -> Path:
        readme_lines = ["# tmpapp", ""]
        src_lines = ["# src"]
        faults = []
        for index in range(1, 7):
            declared = f"DECLARED_QUOTE_TMP_{index:02d}."
            practiced = f"PRACTICED_QUOTE_TMP_{index:02d}"
            neighbour = f"NEIGHBOUR_CLEAN_TMP_{index:02d}"
            readme_lines.append(declared)
            src_lines.append(practiced)
            src_lines.append(neighbour)
            readme_path = "README.md"
            src_path = "src/mod.py"
            dec_line = len(readme_lines)
            prac_line = len(src_lines) - 1
            neigh_line = len(src_lines)
            probe_rel = f"probes/p{index:02d}.sh"
            fix_rel = f"fixes/p{index:02d}.patch"
            _plant_bytes(self, app / probe_rel, b"#!/bin/sh\nexit 1\n")
            _plant_bytes(self, app / fix_rel, b"dummy patch\n")
            faults.append(
                {
                    "id": f"TMP-{index:02d}",
                    "kind": f"K{index}",
                    "severity": "p2",
                    "location": {
                        "path": src_path,
                        "lines": [prac_line, prac_line],
                    },
                    "declared": {
                        "text": declared,
                        "path": readme_path,
                        "lines": [dec_line, dec_line],
                    },
                    "practiced": {
                        "text": practiced,
                        "path": src_path,
                        "lines": [prac_line, prac_line],
                    },
                    "finding": f"tmpapp plants {index} as a quotation pair",
                    "neighbour": {
                        "path": src_path,
                        "lines": [neigh_line, neigh_line],
                        "why_clean": f"{neighbour} has no fault",
                    },
                    "probe": f"sh {probe_rel}",
                    "fix": fix_rel,
                    "visible_to": "audit" if index % 2 else "test",
                }
            )
        _plant_bytes(
            self,
            app / "README.md",
            ("\n".join(readme_lines) + "\n").encode("utf-8"),
        )
        _plant_bytes(
            self,
            app / "src" / "mod.py",
            ("\n".join(src_lines) + "\n").encode("utf-8"),
        )
        manifest = {
            "name": "tmpapp",
            "check": "python3 -c 'print(0)'",
            "faults": faults,
        }
        planted = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        _plant_bytes(self, app / "FAULTS.json", planted)
        loaded = json.loads((app / "FAULTS.json").read_text(encoding="utf-8"))
        self.assertEqual(len(loaded["faults"]), 6)
        return app


if __name__ == "__main__":
    unittest.main()
