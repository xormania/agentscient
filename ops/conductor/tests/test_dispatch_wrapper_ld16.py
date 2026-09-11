"""LD-16 regression: a job directory minted while the wrapper suite runs
is not the wrapper's write, so the suite's teardown guard must pass.

The wrapper fixture snapshots every jobs root it guards in setUp and
compares in tearDown through the shared live-store guard. Here the
guarded root is a temporary directory of this test's own, a job
directory of the declared shape appears after the snapshot, and the
fixture's own tearDown is the assertion: it runs before the cleanup
that removes the planted directory. The negative half proves the guard
still fails on an ordinary added name.

Written by hand by the conductor (owner, 2026-09-11: "FIX IT"); the
second producer the defect list asks for was not dispatched.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_dispatch_wrapper as wrapper_suite
from live_store_guard import assert_unchanged

PLANTED = "20260101T000000Z-tests-grok-a1d016"


class AJobDirMintedMidRun(wrapper_suite._WrapperFixture):
    def setUp(self):
        self._own_root = tempfile.TemporaryDirectory(prefix="ld16-jobs-")
        self.addCleanup(self._own_root.cleanup)
        own = Path(self._own_root.name)
        original = wrapper_suite._jobs_roots_to_guard
        wrapper_suite._jobs_roots_to_guard = lambda: [own]
        self.addCleanup(setattr, wrapper_suite, "_jobs_roots_to_guard", original)
        super().setUp()
        self.assertEqual([root for root, _ in self._guarded], [own])

    def test_the_fixture_teardown_passes_with_a_new_job_dir(self):
        root = self._guarded[0][0]
        planted = root / PLANTED
        planted.mkdir()
        self.addCleanup(planted.rmdir)
        self.assertTrue(planted.is_dir())
        # tearDown is the assertion; cleanups run after it.


class TheGuardStillFailsOnAnOrdinaryName(unittest.TestCase):
    def test_an_ordinary_added_name_fails(self):
        before = {"root": ("dir", ("keep",))}
        after = {"root": ("dir", ("keep", "stray.txt"))}
        with self.assertRaises(AssertionError):
            assert_unchanged(self, before, after)

    def test_a_new_job_dir_passes(self):
        before = {"root": ("dir", ("keep",))}
        after = {"root": ("dir", ("keep", PLANTED))}
        assert_unchanged(self, before, after)


if __name__ == "__main__":
    unittest.main()
