"""Bind the executable acceptance bar into the ordinary sharded test suite."""

import subprocess
import sys
import unittest

import support

REPO = support.WF_DIR.parent.parent.parent
TESTS = support.WF_DIR / "tests"
ACCEPTANCE = TESTS / "acceptance.py"
SHARD = TESTS / "shard.py"
SHARD_COUNT = 3


class AcceptanceIsScheduled(unittest.TestCase):
    def test_the_complete_acceptance_driver_passes_from_the_repo_root(self):
        proc = subprocess.run(
            [sys.executable, str(ACCEPTANCE)],
            cwd=REPO,
            capture_output=True,
            text=True, check=False,
        )
        combined = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, combined[-2000:])

        pass_lines = [
            line for line in proc.stdout.splitlines()
            if line.startswith("PASS")
        ]
        self.assertGreaterEqual(
            len(pass_lines), 20,
            f"acceptance emitted only {len(pass_lines)} PASS lines:\n{combined}",
        )
        fail_lines = [
            line for line in combined.splitlines()
            if "FAIL" in line
        ]
        self.assertEqual(fail_lines, [], combined)

    def test_this_module_is_listed_in_exactly_one_ci_shard(self):
        module = __name__.rsplit(".", 1)[-1]
        occurrences = []
        for index in range(SHARD_COUNT):
            proc = subprocess.run(
                [sys.executable, str(SHARD), "--list",
                 str(SHARD_COUNT), str(index)],
                cwd=REPO,
                capture_output=True,
                text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            occurrences.extend(
                (index, listed)
                for listed in proc.stdout.split()
                if listed == module
            )

        self.assertEqual(
            occurrences,
            [(occurrences[0][0], module)] if occurrences else [],
            f"{module} must be owned by exactly one shard: {occurrences!r}",
        )
        self.assertEqual(len(occurrences), 1)


if __name__ == "__main__":
    unittest.main()
