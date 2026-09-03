#!/usr/bin/env python3
"""The import-contract checker must fire, and must stay quiet.

Every case builds a throwaway app tree in a temp dir, so nothing is
mutated in place and a plant cannot silently fail to land -- the tree
either exists as written or the test errors. Each planted case asserts
the plant landed (the file is on disk and contains the fault) before
asserting the verdict, because a check run against a fixture that was
never built answers a question about nothing.

The two false-positive shapes have their own cases. Both were real:
an earlier textual version of this checker reported three edges on dev
and all three were wrong.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[1] / "imports.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("dev_imports", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_tree(root: Path, files: dict[str, str], declared: dict | None):
    """Write an app tree; prove every file landed before returning."""
    for rel, body in files.items():
        path = root / "ops" / "devlane" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        # The plant guard: written, non-empty, and carrying what we wrote.
        if not path.exists():
            raise AssertionError(f"INVALID fixture: {rel} was not created")
        landed = path.read_text(encoding="utf-8")
        if landed != body or not landed.strip():
            raise AssertionError(f"INVALID fixture: {rel} did not land intact")
    decl = root / "ops" / "contracts" / "imports.json"
    decl.parent.mkdir(parents=True, exist_ok=True)
    if declared is not None:
        decl.write_text(json.dumps({"apps": declared}), encoding="utf-8")
    return decl


def run(root: Path, *extra):
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), *extra],
        capture_output=True, text=True, check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


class Quiet(unittest.TestCase):
    """Shapes that must NOT be reported."""

    def test_standalone_apps_are_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {
                "alpha/a.py": "import json\n\nX = 1\n",
                "beta/b.py": "import sys\n\nY = 2\n",
            }, {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 0, out)
            self.assertIn("clean", out)

    def test_a_comment_naming_another_app_is_not_an_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {
                "alpha/a.py": "# Re-derive with ops/devlane/beta/b.py rather than guessing.\nX = 1\n",
                "beta/b.py": "Y = 2\n",
            }, {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 0, out)

    def test_a_path_in_fixture_data_is_not_an_edge(self):
        """`"withheld": ["ops/devlane/beta/**.py"]` names a path, does not load it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {
                "alpha/a.py": (
                    "import importlib.util\n"
                    "from pathlib import Path\n"
                    "HERE = Path(__file__).parent\n"
                    "CASE = {'given': ['ops/devlane/beta/PLAN.md'],\n"
                    "        'withheld': ['ops/devlane/beta/**.py']}\n"
                    "def load():\n"
                    "    spec = importlib.util.spec_from_file_location('own', HERE / 'other.py')\n"
                    "    return spec\n"
                ),
                "alpha/other.py": "Z = 3\n",
                "beta/b.py": "Y = 2\n",
            }, {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 0, out)

    def test_a_declared_edge_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {
                "alpha/a.py": (
                    "from pathlib import Path\n"
                    "P = Path(__file__).parent.parent / 'beta' / 'b.py'\n"
                ),
                "beta/b.py": "Y = 2\n",
            }, {"alpha": {"may_import": ["beta"]}, "beta": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 0, out)


class Fires(unittest.TestCase):
    """Shapes that MUST be reported."""

    def test_undeclared_path_join_is_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = ("from pathlib import Path\n"
                       "P = Path(__file__).parent.parent / 'beta' / 'b.py'\n")
            build_tree(root, {"alpha/a.py": planted, "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            # prove the fault is in the fixture, not merely intended
            self.assertIn("'beta'", (root / "ops/devlane/alpha/a.py").read_text())
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("alpha -> beta", out)

    def test_undeclared_import_is_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {
                "alpha/a.py": "import bmod\n",
                "beta/bmod.py": "Y = 2\n",
            }, {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("alpha -> beta", out)

    def test_an_app_missing_from_the_declaration_is_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {"alpha/a.py": "X = 1\n", "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("UNDECLARED APP", out)


class Refuses(unittest.TestCase):
    """A run that could not look must never render as a pass."""

    def test_absent_declaration_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {"alpha/a.py": "X = 1\n"}, None)
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("INVALID", out)

    def test_unparseable_declaration_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decl = build_tree(root, {"alpha/a.py": "X = 1\n"}, None)
            decl.write_text("{not json", encoding="utf-8")
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("INVALID", out)

    def test_no_app_tree_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run(Path(tmp))
            self.assertEqual(code, 1, out)
            self.assertIn("INVALID", out)

    def test_an_app_tree_with_no_python_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ops/devlane/alpha").mkdir(parents=True)
            (root / "ops/devlane/alpha/README.md").write_text("no python here\n")
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("INVALID", out)


class Harness(unittest.TestCase):
    """The checker's own historical bug: a textual match is not an edge."""

    def test_path_join_constants_ignores_list_elements(self):
        module = load_checker()
        import ast
        tree = ast.parse("D = ['ops/devlane/beta/x.py']\nP = HERE / 'beta' / 'b.py'\n")
        found = {v for v, _ in module.path_join_constants(tree)}
        self.assertIn("beta", found)
        self.assertNotIn("ops/devlane/beta/x.py", found)

class AnUndeclaredAppStillShowsItsEdges(unittest.TestCase):
    """A new app is the one whose coupling most needs seeing.

    The first version skipped edge-checking for any app absent from the
    declaration, so adding an app reported "UNDECLARED APP" and nothing
    else -- its arrows stayed invisible until someone declared it. Caught
    by a claim spec run against the real task branch, which reported no
    violation where `task -> telemetry` was plainly present.
    """

    def test_edges_of_an_undeclared_app_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = ("from pathlib import Path\n"
                       "P = Path(__file__).parent.parent / 'beta' / 'b.py'\n")
            build_tree(root, {"alpha/a.py": planted, "beta/b.py": "Y = 2\n"},
                       {"beta": {"may_import": []}})   # alpha not declared
            self.assertIn("'beta'", (root / "ops/devlane/alpha/a.py").read_text())
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("UNDECLARED APP", out)
            self.assertIn("alpha -> beta", out)

class ShapesCodexFound(unittest.TestCase):
    """Two loading forms the path-expression rule alone reported clean.

    Both are normal for standalone scripts, and both were verified as
    misses against the checker before the fix: each fixture below
    returned exit 0 and printed "clean".
    """

    def test_a_complete_path_string_handed_to_a_loader_is_an_edge(self):
        """PR #50 P1. spec_from_file_location("b", "ops/devlane/beta/b.py")."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = ('import importlib.util\n'
                       'spec = importlib.util.spec_from_file_location(\n'
                       '    "b", "ops/devlane/beta/b.py")\n')
            build_tree(root, {"alpha/a.py": planted, "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            self.assertIn("ops/devlane/beta", (root / "ops/devlane/alpha/a.py").read_text())
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("alpha -> beta", out)

    def test_a_namespace_package_import_of_an_app_dir_is_an_edge(self):
        """PR #50 P2. `from beta import b` with .dev/app on sys.path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {"alpha/a.py": "from beta import b\n",
                              "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("alpha -> beta", out)

    def test_loader_inspection_does_not_reopen_the_text_search(self):
        """The fix must not undo the precision it was built on.

        A loader call in the same file as fixture data naming another
        app stays clean: only the loader's OWN arguments are inspected.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = ('import importlib.util\n'
                   'from pathlib import Path\n'
                   'CASE = {"withheld": ["ops/devlane/beta/**.py"]}\n'
                   'def load():\n'
                   '    return importlib.util.spec_from_file_location(\n'
                   '        "own", Path(__file__).parent / "other.py")\n')
            build_tree(root, {"alpha/a.py": src, "alpha/other.py": "Z = 3\n",
                              "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            self.assertIn("ops/devlane/beta", (root / "ops/devlane/alpha/a.py").read_text())
            code, out = run(root)
            self.assertEqual(code, 0, out)


class ShapesCodexFoundInRoundTwo(unittest.TestCase):
    """Three more ways an app reaches another, all verified as misses first.

    Each fixture below returned exit 0 and printed "clean" against the
    checker as it stood after round one (Codex, PR #50 round two).
    """

    def test_a_complete_path_to_a_path_constructor_is_an_edge(self):
        """`Path("ops/devlane/beta/b.py").read_text()` -- consumed by reading."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = ('from pathlib import Path\n'
                       'X = Path("ops/devlane/beta/b.py").read_text()\n')
            build_tree(root, {"alpha/a.py": planted, "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            self.assertIn("ops/devlane/beta", (root / "ops/devlane/alpha/a.py").read_text())
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("alpha -> beta", out)

    def test_a_dynamic_import_is_an_edge(self):
        """`import_module("beta.b")` is an import in every sense."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = 'import importlib\nm = importlib.import_module("beta.b")\n'
            build_tree(root, {"alpha/a.py": planted, "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            self.assertIn("import_module", (root / "ops/devlane/alpha/a.py").read_text())
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("alpha -> beta", out)

    def test_ambiguous_ownership_refuses_rather_than_discarding_the_edge(self):
        """Two apps owning one basename: which is imported depends on
        sys.path at run time, so the graph cannot be read off the source.
        Returning None there printed clean and threw the edge away."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root, {
                "alpha/a.py": "import shared\n",
                "beta/shared.py": "Y = 2\n",
                "gamma/shared.py": "Z = 3\n",
            }, {"alpha": {"may_import": []}, "beta": {"may_import": []},
                "gamma": {"may_import": []}})
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("INVALID", out)
            self.assertIn("more than one app", out)

    def test_widening_to_path_constructors_kept_the_precision(self):
        """`Path`/`open` are now inspected, so the inert-fixture case has
        to be re-proved: a data string naming another app, in a file that
        also builds a path of its own, still reports clean."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = ('from pathlib import Path\n'
                   'CASE = {"withheld": ["ops/devlane/beta/**.py"]}\n'
                   'MINE = Path(__file__).parent / "other.py"\n')
            build_tree(root, {"alpha/a.py": src, "alpha/other.py": "Z = 3\n",
                              "beta/b.py": "Y = 2\n"},
                       {"alpha": {"may_import": []}, "beta": {"may_import": []}})
            self.assertIn("ops/devlane/beta", (root / "ops/devlane/alpha/a.py").read_text())
            code, out = run(root)
            self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
