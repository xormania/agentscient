"""Root-tree pins for fixture-apps slice 1, written from the contract.

The batch must exclude `ops/devlane/fixtures/apps` from root ruff (with
the planted-fault reason), keep linting the lane tests under
`ops/devlane/fixtures/tests/`, and name the apps directory and the
`fixture.sh` lever in `ops/README.md`. Those files exist today without
the rows; the missing exclusion and README lines are the intended red.
"""

from __future__ import annotations

import subprocess
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RUFF = REPO / "ruff.toml"
README = REPO / "ops" / "README.md"
LANE_CONF = REPO / "ops" / "lane.conf"
COPY_LIST = REPO / "ops" / "devlane" / "fixtures" / "copy-list"
COPY_LIST_REL = "ops/devlane/fixtures/copy-list"
APPS_EXCLUDE = "ops/devlane/fixtures/apps"
TESTS_PATH = "ops/devlane/fixtures/tests"


class RuffExclusion(unittest.TestCase):
    def test_ruff_toml_excludes_fixture_apps_with_reason(self):
        self.assertTrue(RUFF.is_file(), f"{RUFF} is missing")
        text = RUFF.read_text(encoding="utf-8")
        data = tomllib.loads(text)
        exclude = [str(item).rstrip("/") for item in data.get("extend-exclude", [])]
        self.assertIn(
            APPS_EXCLUDE,
            exclude,
            f"{RUFF} extend-exclude must name {APPS_EXCLUDE}",
        )
        lines = text.splitlines()
        hits = [index for index, line in enumerate(lines) if APPS_EXCLUDE in line]
        self.assertTrue(hits, f"{APPS_EXCLUDE} not found as text in {RUFF}")
        idx = hits[0]
        window = "\n".join(lines[max(0, idx - 8) : idx + 3]).lower()
        self.assertTrue(
            "planted" in window and ("k1" in window or "k4" in window or "s family" in window or "family" in window),
            f"the exclusion must state why planted faults survive root ruff: {window!r}",
        )
        self.assertTrue(
            "prove" in window or "check" in window,
            f"the exclusion must say apps are linted through prove/check: {window!r}",
        )

    def test_ruff_toml_still_lints_lane_fixture_tests(self):
        self.assertTrue(RUFF.is_file(), f"{RUFF} is missing")
        data = tomllib.loads(RUFF.read_text(encoding="utf-8"))
        exclude = [str(item).rstrip("/") for item in data.get("extend-exclude", [])]
        self.assertNotIn(
            TESTS_PATH,
            exclude,
            "lane tests under ops/devlane/fixtures/tests/ stay linted",
        )
        self.assertFalse(
            any(item.startswith(TESTS_PATH) for item in exclude),
            exclude,
        )


class ReadmeLayout(unittest.TestCase):
    def test_ops_readme_names_the_apps_directory(self):
        self.assertTrue(README.is_file(), f"{README} is missing")
        text = README.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"\|\s*`ops/devlane/fixtures/apps/`\s*\|",
            "ops/README.md layout table must have a row for ops/devlane/fixtures/apps/",
        )

    def test_ops_readme_names_the_fixture_lever(self):
        self.assertTrue(README.is_file(), f"{README} is missing")
        text = README.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"\|\s*`ops/bin/fixture\.sh`\s*\|",
            "ops/README.md levers table must have a row for ops/bin/fixture.sh",
        )


class CopyListDefault(unittest.TestCase):
    def test_copy_list_is_tracked(self):
        self.assertTrue(
            COPY_LIST.is_file(),
            f"{COPY_LIST} is missing; make's default copy list must be tracked",
        )
        proc = subprocess.run(
            ["git", "ls-files", "--", COPY_LIST_REL],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout.strip(),
            COPY_LIST_REL,
            f"{COPY_LIST_REL} must be tracked",
        )
        self.assertTrue(
            COPY_LIST.read_text(encoding="utf-8").strip(),
            "the tracked copy list must name at least one path",
        )

    def test_lane_conf_names_the_copy_list_as_the_default(self):
        self.assertTrue(LANE_CONF.is_file(), f"{LANE_CONF} is missing")
        text = LANE_CONF.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"(?m)^FIXTURE_COPY_LIST='ops/devlane/fixtures/copy-list'\s*$",
            f"{LANE_CONF} must name FIXTURE_COPY_LIST's default as the tracked copy list",
        )


if __name__ == "__main__":
    unittest.main()
