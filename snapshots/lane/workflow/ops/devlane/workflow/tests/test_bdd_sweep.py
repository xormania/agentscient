"""The BDD sweep as a standing guard (ops/process/bdd.md).

Every scenario in ops/design/features/ either has a test naming it
verbatim in a docstring, or carries an explicit `# deferred: <why>`
line in the feature file. A scenario silently unimplemented is the
gap nobody notices — the same class as a check silently dropped
from CI.
"""

import ast
import re
import unittest
from pathlib import Path

import support

REPO = support.WF_DIR.parent.parent.parent
FEATURES = REPO / "ops" / "design" / "features"
TEST_TREES = (
    REPO / "ops" / "devlane" / "workflow" / "tests",
    REPO / "ops" / "devlane" / "telemetry" / "tests",
    REPO / "ops" / "devlane" / "fixtures" / "tests",
    REPO / "ops" / "devlane" / "hooks" / "tests",
    REPO / "ops" / "devlane" / "dispatch" / "tests",
    REPO / "ops" / "devlane" / "task" / "tests",
)


def scenarios():
    found = []
    for feature in sorted(FEATURES.rglob("*.feature")):
        lines = feature.read_text().splitlines()
        for index, line in enumerate(lines):
            match = re.match(r"\s*Scenario:\s*(.+?)\s*$", line)
            if not match:
                continue
            found.append((feature, match.group(1),
                          "# deferred:" in "\n".join(
                              lines[index + 1:index + 3])))
    return found


def docstrings(test_file):
    # only DOCSTRINGS carry mappings: a comment or a string literal
    # elsewhere is not a test naming the scenario (Grok, PR #33
    # review — a planted comment satisfied the raw-text grep)
    try:
        tree = ast.parse(test_file.read_text())
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                yield doc


def named_in_tests(name):
    needle = f"Scenario: {name}"
    for tree in TEST_TREES:
        for test_file in tree.glob("test*.py"):
            if any(needle in doc for doc in docstrings(test_file)):
                return True
    return False


class EveryScenarioIsMappedOrDeferred(unittest.TestCase):
    def test_the_feature_shelf_exists_and_is_not_empty(self):
        self.assertTrue(FEATURES.is_dir(), f"{FEATURES} is missing")
        self.assertGreaterEqual(
            len(scenarios()), 20,
            "the feature shelf lost its scenarios")

    def test_every_scenario_has_a_test_or_a_deferral(self):
        for feature, name, deferred in scenarios():
            with self.subTest(feature=feature.name, scenario=name):
                if deferred:
                    continue
                self.assertTrue(
                    named_in_tests(name),
                    f"no test names 'Scenario: {name}' and the"
                    f" feature carries no deferral for it")

    def test_no_test_names_a_scenario_that_does_not_exist(self):
        declared = {name for _, name, _ in scenarios()}
        for tree in TEST_TREES:
            for test_file in tree.glob("test*.py"):
                if test_file.name == Path(__file__).name:
                    continue  # this file talks ABOUT scenario names
                doc_text = "\n".join(docstrings(test_file))
                for match in re.finditer(
                        r"Scenario: (.+?)\s*$", doc_text,
                        re.MULTILINE):
                    with self.subTest(test=test_file.name,
                                      scenario=match.group(1)):
                        self.assertIn(
                            match.group(1), declared,
                            "a test names a scenario no feature"
                            " declares — the contract moved without"
                            " its implementation")


if __name__ == "__main__":
    unittest.main()
