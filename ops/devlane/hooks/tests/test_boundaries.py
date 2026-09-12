"""The boundary registry closes both ways over the check matrix.

Owner, 2026-09-12: "the hook is supposed to have matrix of checks and
guarantees - its a framework for verification"; "if its not an
abstracted boundary - then we don't speak the same language". Law:
docs/workflow.md, a transition declares its actor class, its evidence
duty, its failure class and its gate.

ops/devlane/hooks/boundaries.json declares one row per refusal class.
This gate asserts: every class the matrix can emit is declared; every
declared class is emitted by the gate function the row names; every
test the row names exists in the file it names; every row carries the
four declared fields and a known escape; the matrix docstring names the
class; and deny() of an undeclared class raises, so the hook reports
hook-error rather than a rule nobody declared.

One producer (Claude Fable 5.1) under hand grant 162; the second
producer is absent by the owner's word.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
REPO = HOOKS.parents[2]
MATRIX = HOOKS / "claude" / "matrix.py"
REGISTRY = HOOKS / "boundaries.json"
FIELDS = ("class", "boundary", "actor", "trigger", "evidence", "gate", "tests", "escape")
ESCAPES = {"none", "grant", "unscoped-grant"}
BOUNDARIES = {"write", "search", "test-run", "dispatch", "branch", "pr", "commit", "publish"}


def emitted_classes():
    tree = ast.parse(MATRIX.read_text(encoding="utf-8"))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and getattr(sub.func, "id", None) == "deny"
                        and sub.args and isinstance(sub.args[0], ast.Constant)):
                    found.setdefault(sub.args[0].value, set()).add(node.name)
    return found


class TheRegistryClosesOverTheMatrix(unittest.TestCase):
    def setUp(self):
        self.assertTrue(REGISTRY.is_file(), f"missing {REGISTRY}")
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data.get("schema"), "agentscient.boundaries/1")
        self.rows = {row["class"]: row for row in data["rows"]}
        self.emitted = emitted_classes()
        self.docstring = MATRIX.read_text(encoding="utf-8").split('"""', 2)[1]

    def test_every_emitted_class_is_declared(self):
        self.assertEqual(sorted(set(self.emitted) - set(self.rows)), [],
                         "the matrix refuses with a class the registry does not declare")

    def test_every_declared_class_is_emitted_by_its_gate(self):
        for klass, row in self.rows.items():
            with self.subTest(klass=klass):
                self.assertIn(klass, self.emitted, "declared but the matrix never refuses with it")
                self.assertIn(row["gate"], self.emitted[klass],
                              f"{klass} is emitted by {sorted(self.emitted[klass])}, not {row['gate']}")

    def test_every_row_carries_the_declared_fields(self):
        for klass, row in self.rows.items():
            with self.subTest(klass=klass):
                for field in FIELDS:
                    self.assertIn(field, row)
                    self.assertTrue(row[field], f"{klass}.{field} is empty")
                self.assertIn(row["boundary"], BOUNDARIES)
                self.assertIn(row["escape"], ESCAPES)
                self.assertEqual(row["actor"], "session")
                self.assertIn(klass, self.docstring, "the matrix docstring table names every row")

    def test_every_named_test_exists(self):
        for klass, row in self.rows.items():
            for ref in row["tests"]:
                with self.subTest(klass=klass, test=ref):
                    path, name = ref.split("::", 1)
                    text = (REPO / path).read_text(encoding="utf-8")
                    self.assertRegex(text, rf"def {re.escape(name)}\(", f"{name} not in {path}")

    def test_an_undeclared_class_cannot_be_refused_with(self):
        probe = ("import sys; sys.path.insert(0, %r); import importlib.util as u; "
                 "s = u.spec_from_file_location('matrix', %r); m = u.module_from_spec(s); s.loader.exec_module(m); "
                 "m.deny('no-such-row', 'x', 'y', 'z')") % (str(HOOKS / "claude"), str(MATRIX))
        proc = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("undeclared gate: no-such-row", proc.stderr)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "true"}, "cwd": str(REPO)})
        proc = subprocess.run([sys.executable, str(MATRIX)], input=payload, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "", "a plain command still passes")


if __name__ == "__main__":
    unittest.main()
