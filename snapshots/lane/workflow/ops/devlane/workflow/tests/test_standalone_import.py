"""Every test module must import on its own.

These suites put their own directory on sys.path through support.py,
so a module that imports a workflow module before support has run is
uncollectable alone — and yet passes under discovery, because some
earlier module already wired the path. That is a false green: the
module looks tested and cannot be run.

It happened twice on 2026-08-22 (test_ci_shape, test_bdd_lifecycle),
once reaching dev, both times because an import sorter alphabetised a
load-bearing block. ruff.toml now refuses to sort those blocks; this
proves the order still works, which the ignore alone cannot.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
TEST_DIRS = (
    APP / "workflow" / "tests",
    APP / "telemetry" / "tests",
    APP / "fixtures" / "tests",
)


def modules(directory):
    # Every module in the directory, not just test*.py: acceptance.py
    # and the helpers are imported by the suites and are subject to
    # the same sorter, so a broken order there is the same outage
    # (Grok, PR #36 review).
    return sorted(p for p in directory.glob("*.py"))


def clean_env():
    # An inherited PYTHONPATH can already contain the app directory,
    # which wires the path for free and hides the exact failure this
    # file exists to catch (Grok, PR #36 review).
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class EveryTestModuleImportsAlone(unittest.TestCase):
    def test_the_scan_finds_the_suites_it_claims_to_cover(self):
        # A run over zero modules would pass silently, which is the
        # shape this file exists to refuse.
        for directory in TEST_DIRS:
            with self.subTest(directory=directory.name):
                self.assertTrue(directory.is_dir(), directory)
                self.assertGreaterEqual(len(modules(directory)), 1)
        total = sum(len(modules(d)) for d in TEST_DIRS)
        self.assertGreaterEqual(
            total, 30, "the module scan lost most of the suite")

    def test_each_module_imports_in_a_fresh_interpreter(self):
        for directory in TEST_DIRS:
            for module in modules(directory):
                with self.subTest(module=f"{directory.name}/{module.name}"):
                    proc = subprocess.run(
                        [sys.executable, "-c", f"import {module.stem}"],
                        cwd=directory, capture_output=True, text=True,
                        check=False, env=clean_env(),
                    )
                    self.assertEqual(
                        proc.returncode, 0,
                        f"{module.name} cannot be imported on its own —"
                        f" it passes only because another module ran"
                        f" first:\n{proc.stderr[-800:]}")


if __name__ == "__main__":
    unittest.main()
