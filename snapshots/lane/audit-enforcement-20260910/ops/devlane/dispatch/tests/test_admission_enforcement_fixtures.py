"""GREEN fixture-precondition checks for the prevention amendment.

These run against the established baseline only: no new verify verb, no
--work-order. They prove planted empty lists, observation keys, record
identity/model/producer and retained-input hashes using existing public
interfaces. A missing-new-API red is not this file's job.

Independently executable:

    python3 -m unittest ops.devlane.dispatch.tests.test_admission_enforcement_fixtures
    python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_admission_enforcement_fixtures.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import admission_enforcement_support as aes
import launch_support as ls

ENVELOPE_PY = ls.APP.parents[0] / "task" / "envelope.py"


class EmptyListSubstitutionIsRejected(unittest.TestCase):
    """Matrix: empty-list substitution. Helper preserving [] passes."""

    def test_explicit_empty_inputs_stay_empty(self):
        planted = []
        kept = aes.retain_list(planted, default=["dev", "main"], name="inputs")
        self.assertEqual(kept, [])
        self.assertEqual(len(kept), 0)
        self.assertIsNot(kept, planted)
        row = aes.command_row("fx-empty", "true", [])
        self.assertEqual(row["inputs"], [])
        self.assertEqual(json.loads(aes.canonical_json(row))["inputs"], [])

    def test_or_default_substitution_is_the_defect_this_check_catches(self):
        planted = []
        default = ["dev", "main"]
        self.assertEqual(aes.substituting_list(planted, default), default)
        self.assertEqual(aes.retain_list(planted, default=default), [])
        self.assertNotEqual(
            aes.retain_list(planted, default=default),
            aes.substituting_list(planted, default),
        )

    def test_none_may_take_a_default_but_empty_may_not(self):
        default = ["only-when-missing"]
        self.assertEqual(aes.retain_list(None, default=default), default)
        self.assertEqual(aes.retain_list([], default=default), [])


class EstablishedEventConsumerFormat(unittest.TestCase):
    """Matrix: guessed event consumer. Format checks run before new API."""

    def test_monitor_observation_uses_the_documented_closed_object(self):
        planted = aes.planted_observation(subject="rec-aa41")
        self.assertEqual(tuple(planted), aes.OBSERVATION_KEYS)
        self.assertEqual(planted["state"], "ok")
        self.assertEqual(planted["metrics"]["status"], "completion")
        for key in aes.DISPATCH_METRICS:
            self.assertIn(key, planted["metrics"])

    def test_a_guessed_event_metric_shape_is_not_the_consumer(self):
        planted = aes.planted_observation(subject="rec-aa41")
        guessed = aes.guessed_observation(
            {
                "event": planted["subject"],
                "metric": planted["metrics"]["status"],
                "when": planted["observed_at"],
            }
        )
        self.assertNotEqual(set(guessed), set(aes.OBSERVATION_KEYS))
        with self.assertRaises(ValueError):
            aes.observation(guessed)

    def test_unknown_is_not_zero(self):
        payload = aes.planted_observation(subject="rec-aa41")
        payload["state"] = "unknown"
        payload["metrics"] = {
            "status": "unknown",
            "changed": 0,
            "input": 0,
            "cached": 0,
            "output": 0,
            "total": 0,
        }
        kept = aes.observation(payload)
        self.assertEqual(kept["state"], "unknown")
        self.assertNotEqual(kept["state"], 0)
        self.assertNotEqual(kept["state"], "ok")


class EstablishedRecordIdentityAndHashes(ls._TempLaunch):
    """Producer, model and retained-input hashes via real launch."""

    def test_follows_empty_list_is_an_empty_list_not_defaults(self):
        rec, witness, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        follows = rec.get("follows")
        self.assertIsInstance(follows, list)
        self.assertEqual(follows, [])
        self.assertEqual(aes.retain_list(follows, default=["invented"]), [])
        self.assertNotEqual(aes.substituting_list(follows, ["invented"]), [])
        self.assertEqual(rec["dispatched_by"], ls.AGENT)
        self.assertEqual(rec["harness"]["name"], "grok")
        model = rec["model"]
        self.assertEqual(model["requested"], ls.REQUESTED_MODEL)
        self.assertEqual(model["ran"], ls.RAN_MODEL)
        self.assertIsInstance(model["effort_argv"], list)
        self.assertTrue(witness["argv"])
        brief = rec["brief"]
        self.assertIsInstance(brief.get("inputs"), list)
        self.assertEqual(brief["inputs"], [])
        self.assertEqual(tuple(rec)[: len(ls.RECORD_FIELDS)], ls.RECORD_FIELDS)
        self.assertEqual(rec["lane"], "dev")
        self.assertEqual(rec["job"], "plan")

    def test_retained_input_bytes_and_digest_match_the_planted_file(self):
        payload = b"owner-scope-bytes-aa41\n"
        planted = self.home / "owner-scope.md"
        planted.write_bytes(payload)
        self.assertEqual(planted.read_bytes(), payload)
        digest = aes.sha256_bytes(payload)
        rec, *_ = self.launch_ok(self.argv_for(
            job="plan",
            harness="grok",
            stage="plan",
            extra=["--input", str(planted)],
        ))
        inputs = rec["brief"]["inputs"]
        self.assertEqual(len(inputs), 1, inputs)
        entry = inputs[0]
        self.assertEqual(entry.get("sha256"), digest)
        named = Path(entry["path"]).name
        self.assertEqual(named, "owner-scope.md")
        job_copy = self.the_job_dir() / "in" / "owner-scope.md"
        self.assertTrue(job_copy.is_file(), job_copy)
        self.assertEqual(job_copy.read_bytes(), payload)
        self.assertEqual(aes.sha256_file(job_copy), digest)


class CanonicalEncodingAndExistingClis(unittest.TestCase):
    """Bindings use the same canonical JSON as evaluations. CLIs exist."""

    def test_canonical_json_matches_the_evaluation_encoding(self):
        finding = {
            "claim": "café",
            "reproduce": None,
            "severity": "p2",
            "where": "ops/x.py",
        }
        encoded = aes.canonical_json(finding)
        self.assertNotIn(" ", encoded)
        self.assertIn("café", encoded)
        self.assertEqual(encoded, json.dumps(
            finding, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            allow_nan=False,
        ))
        self.assertTrue(aes.SHA256_RE.fullmatch(aes.sha256_text(encoded)))

    def test_paid_jobs_exist_in_the_catalogue(self):
        jobs = aes.jobs_catalogue()
        for name in aes.PAID_JOBS:
            self.assertIn(name, jobs, name)
        self.assertIn("plan", jobs)
        self.assertIn("check-tests", jobs)

    def test_existing_entrypoints_are_files(self):
        for path in (
            aes.LAUNCH, aes.RECORD, aes.ENVELOPE, aes.JOBS, aes.WRAPPER,
            aes.FINDINGS, aes.LADDER_SH, aes.LADDER_PY, aes.TEST_GUARD,
            aes.SUITES,
        ):
            self.assertTrue(path.is_file(), path)

    def test_collect_verify_is_the_existing_recovery_verb(self):
        proc = subprocess.run(
            [sys.executable, str(aes.LAUNCH), "collect", "-h"],
            capture_output=True,
            text=True,
            check=False,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, text)
        self.assertIn("--verify", text)
        self.assertIn("collect", text.lower())
        # collect --verify remains a recovery check; it is not --phase.

    def test_test_guard_is_advisory_regex_not_fixture_proof(self):
        with tempfile.TemporaryDirectory(prefix="guard-aa41-") as raw:
            root = Path(raw)
            planted = root / "test_no_plant.py"
            planted.write_text(
                "import unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(1, 1)\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(aes.TEST_GUARD), str(planted)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = (proc.stdout or "") + (proc.stderr or "")
            self.assertIn("guarded", text.lower())
            # Exit 0 here does not prove empty-list or event assumptions.


class EnvelopeAndRecordPublicSurfaces(unittest.TestCase):
    """Original admission surfaces remain callable; extras are not required."""

    def test_envelope_finding_evaluation_keyword_exists(self):
        envelope = ls.load_path(self, ENVELOPE_PY, "fixture_envelope")
        evaluation = {
            "classification": "unproven",
            "scope_sha256": "a" * 64,
            "requirement": None,
            "trigger": None,
            "failure": None,
            "evidence": None,
            "refutation": "baseline surface check; no new enforcement",
            "source": None,
            "ruling": None,
        }
        got = envelope.finding(
            "p3",
            "ops/devlane/task/envelope.py",
            "evaluation keyword remains on the original surface",
            reproduce=None,
            evaluation=evaluation,
        )
        self.assertEqual(got["evaluation"]["classification"], "unproven")
        self.assertEqual(got["reproduce"], None)

    def test_record_build_preserves_brief_inputs_empty_list(self):
        record = ls.require_module(self, "record")
        payload = {
            "id": "20260826T000000Z-plan-grok-abc123",
            "lane": "dev",
            "stage": "plan",
            "unit": "work",
            "lineage": {"branch": "work", "base_sha": "a" * 40},
            "follows": [],
            "job": "plan",
            "role": "read",
            "dispatched_by": ls.AGENT,
            "at": {"launched": "2026-08-26T00:00:00Z", "closed": None},
            "snapshot": {
                "mode": "whole",
                "ref_name": "HEAD",
                "ref_sha": "b" * 40,
                "behind_tip": 0,
                "root": "/tmp/jobs/id/snapshot",
            },
            "harness": {
                "name": "grok",
                "version": "1.0.5",
                "isolation": {
                    "mechanism": "home",
                    "env": {"GROK_HOME": "/tmp/jobs/id/home/grok"},
                    "home": "/tmp/jobs/id/home/grok",
                    "auth_files": ["auth.json"],
                    "store": "/tmp/jobs/id/home/grok/sessions",
                    "observed": {"unresolved": "behavioural probe has not run"},
                },
                "sandbox": "plan",
                "containment": "policy",
                "argv": ["grok", "-s", "uuid"],
            },
            "model": {
                "requested": "alias-requested",
                "effort_requested": None,
                "effort_argv": [],
                "ran": None,
                "read_from": None,
            },
            "session": {
                "id": "00000000-0000-4000-8000-000000000001",
                "stream": None,
                "stream_sha256_at_close": None,
            },
            "brief": {
                "template": {
                    "path": "ops/devlane/task/jobs.json",
                    "sha256": "c" * 64,
                },
                "scope": "pin",
                "inputs": [],
                "sha256": "d" * 64,
                "bytes": 3,
            },
            "caps": {"cap-out": 500000, "source": "wires.py"},
            "overrides": [],
            "attempts": [],
            "result": None,
            "status": "launched",
        }
        built = record.build(payload)
        self.assertEqual(built["follows"], [])
        self.assertEqual(built["brief"]["inputs"], [])
        self.assertEqual(built["model"]["effort_argv"], [])
        record.validate(built)


if __name__ == "__main__":
    unittest.main()
