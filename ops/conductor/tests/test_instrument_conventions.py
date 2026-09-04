"""The conformance gate of instrument-conventions.md.

The registry is the directory ops/conductor/registry/: one JSON file
per instrument, named by the instrument (watchdog.py.json for
ops/conductor/tools/watchdog.py), read in sorted file-name order. A
new instrument joins by adding its file in the PR that lands it.
skills.py and co_doc.py predate the wire and join as they adopt it.

Every registered row still has one hermetic refusal-provoking
invocation, and the refusal wire is asserted on all of them
identically: exit 2, a single non-empty stderr line, the class token,
expected / found / needed in order, and an empty stdout.

The gate closes both ways: a file whose tool does not exist under
ops/conductor/tools/ is a failure naming the file; a tool under
ops/conductor/tools/ whose module docstring names
instrument-conventions.md and has no file is a failure naming the
tool; a malformed file is a failure naming the file and the field.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
REGISTRY_DIR = REPO / "ops" / "conductor" / "registry"
AGENT = "Conventions Referee <noreply@anthropic.com>"
CONVENTIONS_MARK = "instrument-conventions.md"
CLASS_TOKEN = re.compile(r"^[a-z]+(?:-[a-z0-9]+)*$")
VALID_ROW = {"argv": ["unexpected"], "class": "arguments", "identity": False}
DECLARING_STUB = (
    '"""Planted instrument that inherits instrument-conventions.md."""\n'
    "import sys\n"
    "sys.exit(0)\n"
)
SILENT_STUB = (
    '"""A tool that does not declare the conventions."""\n'
    "import sys\n"
    "sys.exit(0)\n"
)


@dataclass(frozen=True)
class RegistryRow:
    source: str
    tool: str
    argv: tuple[str, ...]
    refusal: str
    identity: bool


@dataclass(frozen=True)
class GateFailure:
    target: str
    field: str | None = None


def declaring_tools(tools_dir: Path) -> list[str]:
    names: list[str] = []
    for path in sorted(tools_dir.glob("*.py"), key=lambda item: item.name):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        doc = ast.get_docstring(tree) or ""
        if CONVENTIONS_MARK in doc:
            names.append(path.name)
    return names


def parse_registry_file(path: Path) -> tuple[list[RegistryRow], GateFailure | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [], GateFailure(path.name, "json")
    if not isinstance(data, dict):
        return [], GateFailure(path.name, "object")
    tool = data.get("tool")
    if not isinstance(tool, str) or not tool or path.name != f"{tool}.json":
        return [], GateFailure(path.name, "tool")
    raw_rows = data.get("rows")
    if not isinstance(raw_rows, list):
        return [], GateFailure(path.name, "rows")
    if len(raw_rows) == 0:
        return [], GateFailure(path.name, "rows")
    rows: list[RegistryRow] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            return [], GateFailure(path.name, "rows")
        if "argv" not in item:
            return [], GateFailure(path.name, "argv")
        if "class" not in item:
            return [], GateFailure(path.name, "class")
        if "identity" not in item:
            return [], GateFailure(path.name, "identity")
        argv = item["argv"]
        if not isinstance(argv, list) or any(not isinstance(part, str) for part in argv):
            return [], GateFailure(path.name, "argv")
        refusal = item["class"]
        if not isinstance(refusal, str) or CLASS_TOKEN.fullmatch(refusal) is None:
            return [], GateFailure(path.name, "class")
        identity = item["identity"]
        if not isinstance(identity, bool):
            return [], GateFailure(path.name, "identity")
        rows.append(
            RegistryRow(
                source=path.name,
                tool=tool,
                argv=tuple(argv),
                refusal=refusal,
                identity=identity,
            )
        )
    return rows, None


def read_registry(registry_dir: Path) -> tuple[list[RegistryRow], list[GateFailure]]:
    """Load rows from one-row-file-per-instrument JSON, sorted by file name."""
    rows: list[RegistryRow] = []
    failures: list[GateFailure] = []
    if not registry_dir.is_dir():
        return [], []
    for path in sorted(registry_dir.glob("*.json"), key=lambda item: item.name):
        parsed, failure = parse_registry_file(path)
        if failure is not None:
            failures.append(failure)
            continue
        rows.extend(parsed)
    return rows, failures


def closure_failures(registry_dir: Path, tools_dir: Path) -> list[GateFailure]:
    failures: list[GateFailure] = []
    if registry_dir.is_dir():
        for path in sorted(registry_dir.glob("*.json"), key=lambda item: item.name):
            parsed, failure = parse_registry_file(path)
            if failure is not None:
                failures.append(failure)
                continue
            if not (tools_dir / parsed[0].tool).is_file():
                failures.append(GateFailure(path.name))
    for name in declaring_tools(tools_dir):
        if not (registry_dir / f"{name}.json").is_file():
            failures.append(GateFailure(name))
    return failures


class TheRefusalWireIsUniform(unittest.TestCase):
    def live_rows(self) -> list[RegistryRow]:
        self.assertTrue(
            REGISTRY_DIR.is_dir(),
            f"registry directory missing: {REGISTRY_DIR}",
        )
        rows, failures = read_registry(REGISTRY_DIR)
        self.assertEqual(failures, [], f"malformed registry files: {failures}")
        self.assertGreater(len(rows), 0, "registry has no rows")
        return rows

    def invoke(self, tool: str, argv: list[str], *, identity: bool):
        with tempfile.TemporaryDirectory(prefix="conventions-") as home:
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": home,
                "LC_ALL": "C",
                "LANG": "C",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if identity:
                env["WF_AGENT"] = AGENT
            return subprocess.run(
                [sys.executable, str(TOOLS / tool), *argv],
                cwd=home,
                env=env,
                input="",
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )

    def test_every_registered_instrument_exists(self):
        for row in self.live_rows():
            with self.subTest(tool=row.tool):
                self.assertTrue(
                    (TOOLS / row.tool).is_file(),
                    f"registered instrument missing: {row.tool}",
                )

    def test_every_registered_instrument_speaks_the_wire(self):
        for row in self.live_rows():
            with self.subTest(tool=row.tool, refusal=row.refusal):
                proc = self.invoke(row.tool, list(row.argv), identity=row.identity)
                err = proc.stderr or ""
                self.assertEqual(proc.returncode, 2, err or proc.stdout)
                lines = [ln for ln in err.splitlines() if ln.strip()]
                self.assertEqual(
                    len(lines), 1, f"refusal must be one line: {err!r}"
                )
                line = lines[0]
                head = line.split(":", 1)[0].strip().lower().replace("_", "-")
                self.assertEqual(
                    head,
                    row.refusal,
                    f"refusal class must be the leading token {row.refusal!r}: {line!r}",
                )
                lower = line.lower()
                for word in ("expected", "found", "needed"):
                    self.assertIn(word, lower, line)
                self.assertLess(
                    lower.index("expected"), lower.index("found"), line
                )
                self.assertLess(
                    lower.index("found"), lower.index("needed"), line
                )
                self.assertEqual(
                    (proc.stdout or "").strip(), "",
                    "refusal text belongs on stderr, not stdout",
                )

    def test_identity_refusal_is_uniform_for_writing_instruments(self):
        rows = self.live_rows()
        writers = [row for row in rows if row.identity]
        self.assertGreater(len(writers), 0, "registry has no writing instruments")
        for row in writers:
            with self.subTest(tool=row.tool, argv=row.argv):
                proc = self.invoke(row.tool, list(row.argv), identity=False)
                err = proc.stderr or ""
                self.assertEqual(proc.returncode, 2, err)
                lines = [ln for ln in err.splitlines() if ln.strip()]
                self.assertEqual(len(lines), 1, err)
                head = lines[0].split(":", 1)[0].strip().lower().replace("_", "-")
                self.assertEqual(
                    head,
                    "identity",
                    f"identity refusal must be the leading token: {lines[0]!r}",
                )


class RegistryClosure(unittest.TestCase):
    def _scratch(self) -> tuple[Path, Path]:
        tmp = tempfile.TemporaryDirectory(prefix="registry-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        tools = root / "tools"
        registry = root / "registry"
        tools.mkdir()
        registry.mkdir()
        return tools, registry

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))
        self.assertNotEqual(landed, b"")

    def _plant_registry(self, registry: Path, tool: str, rows: list[dict]) -> Path:
        payload = {"tool": tool, "rows": rows}
        body = json.dumps(payload).encode("utf-8")
        path = registry / f"{tool}.json"
        self._plant_bytes(path, body)
        return path

    def test_every_declaring_tool_has_a_registry_file(self):
        declaring = declaring_tools(TOOLS)
        self.assertGreater(
            len(declaring), 0, "no tool declares instrument-conventions.md"
        )
        missing = [
            name
            for name in declaring
            if not (REGISTRY_DIR / f"{name}.json").is_file()
        ]
        self.assertEqual(
            missing,
            [],
            "declaring tool with no file: " + ", ".join(missing),
        )

    def test_file_for_a_missing_tool_is_a_failure_naming_the_file(self):
        tools, registry = self._scratch()
        path = self._plant_registry(registry, "ghost.py", [VALID_ROW])
        self.assertTrue(path.is_file(), "plant: registry file did not land")
        self.assertFalse(
            (tools / "ghost.py").exists(),
            "plant: ghost.py must stay missing",
        )
        failures = closure_failures(registry, tools)
        self.assertEqual(failures, [GateFailure("ghost.py.json")])

    def test_declaring_tool_with_no_file_is_a_failure_naming_the_tool(self):
        tools, registry = self._scratch()
        planted = tools / "named.py"
        self._plant_bytes(planted, DECLARING_STUB.encode("utf-8"))
        landed = planted.read_text(encoding="utf-8")
        self.assertIn(CONVENTIONS_MARK, landed)
        self.assertFalse(
            (registry / "named.py.json").exists(),
            "plant: named.py.json must stay missing",
        )
        failures = closure_failures(registry, tools)
        self.assertEqual(failures, [GateFailure("named.py")])

    def test_malformed_file_that_is_not_the_shape_names_the_file_and_the_field(self):
        tools, registry = self._scratch()
        path = registry / "not-shape.py.json"
        body = b"[]\n"
        self._plant_bytes(path, body)
        self.assertEqual(path.read_bytes(), body)
        failures = closure_failures(registry, tools)
        self.assertEqual(failures, [GateFailure("not-shape.py.json", "object")])

    def test_malformed_file_with_empty_rows_names_the_file_and_the_field(self):
        tools, registry = self._scratch()
        path = self._plant_registry(registry, "empty-rows.py", [])
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["rows"], [])
        failures = closure_failures(registry, tools)
        self.assertEqual(failures, [GateFailure("empty-rows.py.json", "rows")])

    def test_malformed_file_with_a_class_that_is_not_a_lower_case_token(
        self,
    ):
        tools, registry = self._scratch()
        row = {"argv": ["unexpected"], "class": "Arguments", "identity": False}
        path = self._plant_registry(registry, "bad-class.py", [row])
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["rows"][0]["class"], "Arguments")
        planted_class = payload["rows"][0]["class"]
        self.assertNotEqual(planted_class, planted_class.lower())
        failures = closure_failures(registry, tools)
        self.assertEqual(failures, [GateFailure("bad-class.py.json", "class")])

    def test_clean_planted_registry_passes(self):
        tools, registry = self._scratch()
        alpha = tools / "alpha.py"
        mute = tools / "mute.py"
        self._plant_bytes(alpha, DECLARING_STUB.encode("utf-8"))
        self._plant_bytes(mute, SILENT_STUB.encode("utf-8"))
        self.assertIn(CONVENTIONS_MARK, alpha.read_text(encoding="utf-8"))
        self.assertNotIn(CONVENTIONS_MARK, mute.read_text(encoding="utf-8"))
        rows = [
            {"argv": ["unexpected"], "class": "arguments", "identity": False},
            {"argv": ["NOSUCH"], "class": "record", "identity": True},
        ]
        path = self._plant_registry(registry, "alpha.py", rows)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(payload["tool"], "alpha.py")
        failures = closure_failures(registry, tools)
        self.assertEqual(failures, [])

    def test_registry_is_read_sorted_by_file_name(self):
        _tools, registry = self._scratch()
        self._plant_registry(registry, "zebra.py", [VALID_ROW])
        self._plant_registry(registry, "aardvark.py", [VALID_ROW])
        rows, failures = read_registry(registry)
        self.assertEqual(failures, [])
        self.assertGreater(len(rows), 0, "planted registry has no rows")
        names = [row.source for row in rows]
        self.assertEqual(names, ["aardvark.py.json", "zebra.py.json"])
        self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
