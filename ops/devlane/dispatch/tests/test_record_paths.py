"""A run record that lands in the tree carries no host-absolute path.

Measured 2026-09-03: the term wall refused a branch in 5 s because eight
committed records carried the account name inside Claude's project slug
and Grok's URL-encoded session path, two forms the wall's ``/home/``
exemption does not cover. The launcher now writes records through
``_portable_paths`` and reads them back through ``_absolute_paths``.

Written by the same author as the fix, at the owner's word ("can you fix
it yourself real quick"); the residual is declared in the PR.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
LAUNCH = HERE.parent / "launch.py"


def _load_launch():
    sys.path.insert(0, str(HERE.parent))
    spec = importlib.util.spec_from_file_location("launch_under_test", LAUNCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordPathsArePortable(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home" / "acmeuser"
        self.store = self.home / ".local/state/agentscient/dispatch"
        self.store.mkdir(parents=True)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home)}, clear=False)
        self.env.start()
        os.environ.pop("DISPATCH_JOBS", None)
        os.environ.pop("XDG_STATE_HOME", None)
        self.launch = _load_launch()
        self.job = "20260903T000000Z-plan-claude-abc123"
        self.snapshot = str(self.store / self.job / "snapshot")
        self.slug = self.snapshot.replace("/", "-").replace(".", "-")
        self.encoded = urllib.parse.quote(self.snapshot, safe="")
        self.rec = {
            "id": self.job,
            "snapshot": {"root": self.snapshot},
            "harness": {"argv": ["claude", "--add-dir", str(self.store / self.job / "out")]},
            "model": {"read_from": str(self.home / ".claude/projects" / self.slug / "s.jsonl")},
            "session": {
                "stream": str(self.store / self.job / "home/grok-stream/sessions" / self.encoded / "updates.jsonl"),
                "spend": {"source": str(self.store / self.job / "home/grok-stream/sessions" / self.encoded / "updates.jsonl")},
            },
            "note": "plain prose stays plain",
        }

    def tearDown(self):
        self.env.stop()

    def test_the_written_form_names_the_account_only_after_home(self):
        # The term wall's rule: the account name may appear only right after
        # "/home/". The slug and the URL-encoded forms break that; nothing
        # else in a record does.
        portable = self.launch._portable_paths(self.rec)
        dump = json.dumps(portable)
        self.assertIsNone(re.search(r"(?<!/home/)acmeuser", dump), dump)
        self.assertNotIn(self.slug, dump)
        self.assertNotIn(self.encoded, dump)
        self.assertEqual(portable["snapshot"]["root"], self.snapshot)
        self.assertEqual(portable["model"]["read_from"],
                         str(self.home / ".claude/projects/<snapshot-slug>/s.jsonl"))
        self.assertIn("<snapshot-encoded>", portable["session"]["stream"])
        self.assertEqual(portable["harness"]["argv"][2], str(self.store / self.job / "out"))
        self.assertEqual(portable["note"], "plain prose stays plain")

    def test_the_round_trip_is_exact(self):
        portable = self.launch._portable_paths(self.rec)
        self.assertEqual(self.launch._absolute_paths(portable), self.rec)

    def test_write_then_find_restores_absolute_paths(self):
        repo = self.tmp / "repo"
        (repo / ".dev/records/dispatches").mkdir(parents=True)
        full = json.loads(json.dumps(self.rec))
        with mock.patch.object(self.launch.record, "validate", lambda r: r):
            path = self.launch._write_record(repo, full)
            on_disk = json.loads(path.read_text())
            self.assertIsNone(re.search(r"(?<!/home/)acmeuser", json.dumps(on_disk)))
            _path, loaded = self.launch._find_record(repo, self.job)
        self.assertEqual(loaded, self.rec)

    def test_a_record_without_a_snapshot_root_is_written_unchanged(self):
        rec = {"id": self.job, "harness": {"argv": [str(self.home / "bin/claude")]}}
        self.assertEqual(self.launch._portable_paths(rec), rec)
        self.assertEqual(self.launch._absolute_paths(rec), rec)


if __name__ == "__main__":
    unittest.main()
