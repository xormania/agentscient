"""Round three of Codex's promotion review (PR #16, head ef2bdab).

Both findings are coverage-shaped silence: a product-test check that stays
out of the derived matrix unless a future PR remembers a flag, and a path
filter that skips the suite exactly when its repository-level inputs change.

The path-filtered workflow and the verifier it must list were renamed
on 2026-08-25 (wf-tests.yml -> ci-dev-apps.yml, wf-verify.yml ->
ci-dev.yml). The findings are about the properties, not the filenames.
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

CI_MATRIX = support.WF_DIR / "checks" / "ci_matrix.py"
REPO = support.WF_DIR.parents[2]
DEV_YML = REPO / ".github" / "workflows" / "ci-dev.yml"


def active_yaml(text: str) -> str:
    """Lines that are not comments. A path named only in a comment is not
    in the filter, and a commented-out run: is not scheduled."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )


def job_named(text: str, name: str) -> str:
    marker = f'name: "{name}"'
    start = text.index(marker)
    rest = text[start:]
    nxt = re.search(r"\n  [a-z-]+:\n", rest)
    return rest[: nxt.start()] if nxt else rest


class AWorkspaceWithoutItsTestsInCiIsRefused(unittest.TestCase):
    """[P1 Codex] cargo-test defaults to ci: false (no workspace exists),
    and nothing forces the product PR that adds Cargo.toml to flip it — so
    broken Rust could pass every gate without one product test running.
    The discover job is unfiltered and runs on every PR, so it is the place
    detection becomes enforcement."""

    def payload(self, ci: bool):
        return {
            "checks": [{"kind": "tdd", "kind_version": 1, "name": "cargo-test",
                        "class": "build", "argv": ["cargo", "test", "--workspace"],
                        "ci": ci}],
            "ci_matrix": ["cargo-test"] if ci else [],
        }

    def run_matrix(self, payload, workspace: bool):
        root = Path(tempfile.mkdtemp(prefix="wf-matrix-"))
        self.addCleanup(__import__("shutil").rmtree, root, True)
        (root / "checks.json").write_text(json.dumps(payload))
        if workspace:
            (root / "Cargo.toml").write_text("[workspace]\n")
        return subprocess.run(
            [sys.executable, str(CI_MATRIX), "checks.json"],
            capture_output=True, text=True, cwd=str(root))

    def test_a_workspace_whose_test_check_is_not_in_ci_fails_discovery(self):
        proc = self.run_matrix(self.payload(ci=False), workspace=True)
        self.assertNotEqual(proc.returncode, 0,
                            "a workspace with its tests outside CI passed")
        self.assertIn("cargo-test", proc.stderr,
                      "the refusal must name the check to flip")

    def test_no_workspace_keeps_the_flag_optional(self):
        proc = self.run_matrix(self.payload(ci=False), workspace=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_workspace_with_the_flag_on_passes(self):
        proc = self.run_matrix(self.payload(ci=True), workspace=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("cargo-test", proc.stdout)


class TheWorkspaceGuardRunsOnUnfilteredDiscover(unittest.TestCase):
    """The cargo-test refusal in ci_matrix.py only fires for a product PR
    that adds Cargo.toml if the unfiltered discover job is the one that
    runs it. After the 2026-08-25 split, the mini-app suites live behind a
    path filter; parking the guard there would skip the PR this finding
    exists for. Nothing else asserted that the YAML still invokes the
    script."""

    def test_discover_runs_ci_matrix_py_without_a_path_filter(self):
        self.assertTrue(DEV_YML.is_file(), DEV_YML)
        text = DEV_YML.read_text()
        head, jobs = text.split("jobs:", 1)
        self.assertNotIn(
            "paths:", head,
            "a path filter on the host of ci_matrix.py skips the PR "
            "that adds Cargo.toml",
        )
        marker = 'name: "dev: discover"'
        self.assertIn(marker, jobs, "the unfiltered workflow lost discover")
        active = active_yaml(job_named(jobs, "dev: discover"))
        self.assertRegex(
            active,
            r"python3\s+\ops/devlane/workflow/checks/ci_matrix\.py\b",
            "discover must run the workspace-tests guard",
        )


if __name__ == "__main__":
    unittest.main()
