"""record.py: one implementation per rule, the way envelope.py is.

Written from CONTRACT.md §Dispatch The record, before the module
existed. Each test names the contract rule it pins:

  Rec1  fields land in the contracted order (input order is not enough)
  Rec2  status launched carries no result
  Rec3  model.ran is the stream value, or null with a note — never the alias
  Rec4  observed is the probe's result or {"unresolved": ...}, never false
  Rec5  lane is "dev"
  Rec6  validate names the field it refuses
  Rec7  follows is a list of ids; unit is a string
  Rec8  a record that fails validation is never "valid"
  Rec9  schema-complete: lineage, role, snapshot.mode, containment, status
  Rec10 optional brief.policy: absent is legacy; string/null/empty object refuse
  Rec11 required binding fields, types, schema/path, Git-id and digest shapes
        (Git-id length is this repository's measured sha1 object format)
  Rec12 template_sha256 equals brief.template.sha256
  Rec13 maintenance null or exactly standing/per_job sorted unique rows
  Rec14 profile syntax [a-z][a-z0-9-]* including digits; no membership lookup
"""

from __future__ import annotations

import copy
import unittest

import launch_support as ls
import support

from ops.testkit import World


class _RecordCase(unittest.TestCase):
    def setUp(self):
        self.world = World(prefix="record-")
        self.world.enter()
        self.addCleanup(self.world.close)

    def recmod(self):
        # Load inside the test method so a missing file is an empty
        # stub, not a setUp ERROR, and the assertion below is the red.
        if getattr(self, "record", None) is None:
            self.record = ls.require_module(self, "record")
        return self.record

    def built(self, **overrides):
        record = self.recmod()
        payload = dict(self._minimum())
        payload.update(overrides)
        try:
            return record.build(payload)
        except TypeError:
            return record.build(**payload)

    def _minimum(self):
        return {
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
                "template": {"path": "ops/devlane/task/jobs.json", "sha256": "c" * 64},
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

    def _raises_naming(self, rec, field):
        with self.assertRaises(Exception) as caught:
            self.recmod().validate(rec)
        self.assertIn(field, str(caught.exception).lower())
        return caught.exception


class FieldOrderIsTheContract(_RecordCase):
    """Rec1 — a caller diffing two records sees the same fields in the
    same places. envelope.py already treats key order as shape.
    Input is deliberately reversed so an echo-the-payload stub fails."""

    def test_built_record_keys_match_the_contracted_order(self):
        payload = self._minimum()
        scrambled = {k: payload[k] for k in reversed(list(payload))}
        self.assertNotEqual(tuple(scrambled), ls.RECORD_FIELDS)
        record = self.recmod()
        try:
            rec = record.build(scrambled)
        except TypeError:
            rec = record.build(**scrambled)
        self.assertEqual(tuple(rec), ls.RECORD_FIELDS)

    def test_module_declares_the_same_order(self):
        declared = getattr(self.recmod(), "FIELDS", None)
        self.assertIsNotNone(declared, "FIELDS is the order contract")
        self.assertEqual(tuple(declared), ls.RECORD_FIELDS)


class LaunchedCarriesNoResult(_RecordCase):
    """Rec2 — written at launch with status: launched and no result."""

    def test_a_launched_record_has_result_none(self):
        rec = self.built(
            status="launched",
            result={
                "head": "b" * 40,
                "changed_paths": [],
                "residual_paths": [],
                "envelope": {},
            },
        )
        self.assertEqual(rec["status"], "launched")
        self.assertIsNone(rec["result"])

    def test_validate_refuses_a_launched_record_that_already_has_a_result(self):
        rec = self.built()
        rec["result"] = {
            "head": "b" * 40,
            "changed_paths": [],
            "residual_paths": [],
            "envelope": {},
        }
        rec["status"] = "launched"
        self._raises_naming(rec, "result")


class ModelRanIsNeverTheAliasCopiedOver(_RecordCase):
    """Rec3 — requested is the alias; ran is the stream; no stream →
    null with a note, never the alias copied over."""

    def test_ran_null_is_not_silently_filled_with_requested(self):
        rec = self.built()
        rec["model"]["ran"] = None
        rec["model"]["requested"] = "alias-requested"
        rec["model"]["read_from"] = None
        rec["model"].pop("note", None)
        rec.pop("note", None)
        rec = self.recmod().validate(rec)
        self.assertIsNone(rec["model"]["ran"])
        self.assertEqual(rec["model"]["requested"], "alias-requested")
        self.assertNotEqual(rec["model"]["ran"], rec["model"]["requested"])
        note = rec.get("note") or rec["model"].get("note")
        self.assertTrue(
            str(note or "").strip(),
            "null ran must carry a note, not silence",
        )

    def test_copying_the_alias_into_ran_without_a_stream_is_refused(self):
        rec = self.built()
        rec["model"]["ran"] = rec["model"]["requested"]
        rec["model"]["read_from"] = None
        rec["session"]["stream"] = None
        self._raises_naming(rec, "ran")


class ObservedIsNeverAManufacturedFalse(_RecordCase):
    """Rec4 / plan (u) — observed is verbatim or {"unresolved": why}."""

    def test_unresolved_is_the_honest_absent_observation(self):
        payload = self._minimum()
        del payload["harness"]["isolation"]["observed"]
        record = self.recmod()
        try:
            rec = record.build(payload)
        except TypeError:
            rec = record.build(**payload)
        isolation = rec["harness"]["isolation"]
        self.assertIn("observed", isolation)
        observed = isolation["observed"]
        self.assertIsInstance(observed, dict)
        self.assertIn("unresolved", observed)
        self.assertNotIn(observed.get("unresolved"), (None, "", False))

    def test_observed_false_is_refused(self):
        rec = self.built()
        rec["harness"]["isolation"]["observed"] = False
        self._raises_naming(rec, "observed")

    def test_observed_true_without_evidence_is_refused(self):
        rec = self.built()
        rec["harness"]["isolation"]["observed"] = True
        self._raises_naming(rec, "observed")


class LaneIsDev(_RecordCase):
    """Rec5 — every record is lane: "dev"; the launcher refuses main."""

    def test_built_lane_is_dev(self):
        rec = self.built(lane="prod")
        self.assertEqual(rec["lane"], "dev")

    def test_a_product_lane_is_refused(self):
        rec = self.built()
        rec["lane"] = "prod"
        self._raises_naming(rec, "lane")


class ValidateNamesTheField(_RecordCase):
    """Rec6 — a record that fails validation is never committed; the
    launcher exits non-zero naming the field."""

    def test_a_missing_field_is_named(self):
        rec = self.built()
        del rec["job"]
        self._raises_naming(rec, "job")


class FollowsAndUnitAreShaped(_RecordCase):
    """Rec7 / plan (q) — follows [ids], unit a string defaulting to the
    branch. Neither is context.prior."""

    def test_follows_is_a_list_and_unit_is_a_string(self):
        rec = self.built(
            follows=["20260826T000000Z-plan-grok-000001"],
            unit="",
        )
        self.assertIsInstance(rec["follows"], list)
        self.assertEqual(len(rec["follows"]), 1)
        self.assertIsInstance(rec["unit"], str)
        self.assertTrue(rec["unit"].strip(), "unit defaults to the lineage branch")
        self.assertEqual(rec["unit"], rec["lineage"]["branch"])

    def test_follows_default_is_an_empty_list_not_absent(self):
        payload = self._minimum()
        del payload["follows"]
        record = self.recmod()
        try:
            rec = record.build(payload)
        except TypeError:
            rec = record.build(**payload)
        self.assertIn("follows", rec)
        self.assertEqual(rec["follows"], [])


class StatusIsTheEnum(_RecordCase):
    """Rec8 — status is launched | closed | died."""

    def test_unknown_status_is_refused(self):
        rec = self.built()
        rec["status"] = "finished"
        self._raises_naming(rec, "status")


class SchemaIsComplete(_RecordCase):
    """Rec9 — a shallow validator that accepts lineage=None, role=execute,
    or snapshot.mode=shared-and-wrong is not the contract."""

    def test_lineage_none_is_refused(self):
        rec = self.built()
        rec["lineage"] = None
        self._raises_naming(rec, "lineage")

    def test_lineage_missing_branch_is_refused(self):
        rec = self.built()
        rec["lineage"] = {"base_sha": "a" * 40}
        self._raises_naming(rec, "lineage")

    def test_role_execute_is_refused(self):
        rec = self.built()
        rec["role"] = "execute"
        self._raises_naming(rec, "role")

    def test_snapshot_mode_shared_is_refused(self):
        rec = self.built()
        rec["snapshot"]["mode"] = "shared-and-wrong"
        self._raises_naming(rec, "mode")

    def test_containment_must_be_os_or_policy(self):
        rec = self.built()
        rec["harness"]["containment"] = "hope"
        self._raises_naming(rec, "containment")

    def test_follows_must_be_a_list(self):
        rec = self.built()
        rec["follows"] = "20260826T000000Z-plan-grok-000001"
        self._raises_naming(rec, "follows")


class EffortArgvCarriesTheDial(_RecordCase):
    """model.effort_argv is the exact tokens that reached the command
    line: a list; when effort_requested is set, non-empty and one token
    equals the requested value; every token appears, in order, in
    harness.argv; when unset, []. Missing is a refusal, not silence.
    Findings D3 and G4: a substring check accepted high inside xhigh
    and never compared effort_argv with harness.argv."""

    def test_effort_requested_carried_in_effort_argv_validates(self):
        rec = self.built()
        rec["model"]["effort_requested"] = "high"
        rec["model"]["effort_argv"] = ["--reasoning-effort", "high"]
        rec["harness"]["argv"] = [
            "grok", "-s", "uuid", "--reasoning-effort", "high",
        ]
        rec = self.recmod().validate(rec)
        self.assertEqual(rec["model"]["effort_requested"], "high")
        self.assertEqual(
            rec["model"]["effort_argv"], ["--reasoning-effort", "high"],
        )
        argv = rec["harness"]["argv"]
        self.assertTrue(
            any(argv[i:i + 2] == ["--reasoning-effort", "high"]
                for i in range(len(argv) - 1)),
            argv,
        )

    def test_effort_requested_not_carried_refuses_naming_effort_argv(self):
        rec = self.built()
        rec["model"]["effort_requested"] = "high"
        rec["model"]["effort_argv"] = []
        self._raises_naming(rec, "model.effort_argv")

    def test_effort_argv_without_effort_requested_is_refused(self):
        rec = self.built()
        rec["model"]["effort_requested"] = None
        rec["model"]["effort_argv"] = ["--reasoning-effort", "high"]
        self._raises_naming(rec, "model.effort_argv")

    def test_effort_argv_that_is_not_a_list_is_refused(self):
        rec = self.built()
        rec["model"]["effort_requested"] = "high"
        rec["model"]["effort_argv"] = "--reasoning-effort high"
        self.assertIsInstance(rec["model"]["effort_argv"], str)
        self.assertNotIsInstance(rec["model"]["effort_argv"], list)
        self.assertIn("high", rec["model"]["effort_argv"])
        self._raises_naming(rec, "model.effort_argv")

    def test_high_inside_xhigh_is_not_an_exact_token_and_is_refused(self):
        rec = self.built()
        rec["model"]["effort_requested"] = "high"
        rec["model"]["effort_argv"] = ["--reasoning-effort", "xhigh"]
        rec["harness"]["argv"] = [
            "grok", "--reasoning-effort", "xhigh",
        ]
        self.assertIn("high", "xhigh")
        self.assertNotIn("high", rec["model"]["effort_argv"])
        self._raises_naming(rec, "model.effort_argv")

    def test_a_token_that_merely_contains_xhigh_is_refused(self):
        rec = self.built()
        rec["model"]["effort_requested"] = "xhigh"
        rec["model"]["effort_argv"] = ["not-xhigh"]
        rec["harness"]["argv"] = ["codex", "exec", "--model", "M"]
        self.assertIn("xhigh", "not-xhigh")
        self.assertNotIn("xhigh", rec["model"]["effort_argv"])
        self._raises_naming(rec, "model.effort_argv")

    def test_effort_argv_tokens_missing_from_harness_argv_are_refused(self):
        rec = self.built()
        rec["model"]["effort_requested"] = "xhigh"
        rec["model"]["effort_argv"] = ["--reasoning-effort", "xhigh"]
        rec["harness"]["argv"] = ["codex", "exec", "--model", "M"]
        self.assertNotIn("--reasoning-effort", rec["harness"]["argv"])
        self.assertNotIn("xhigh", rec["harness"]["argv"])
        self._raises_naming(rec, "argv")

    def test_effort_argv_tokens_out_of_order_in_harness_argv_are_refused(self):
        rec = self.built()
        rec["model"]["effort_requested"] = "high"
        rec["model"]["effort_argv"] = ["--reasoning-effort", "high"]
        rec["harness"]["argv"] = ["grok", "high", "--reasoning-effort"]
        self.assertIn("--reasoning-effort", rec["harness"]["argv"])
        self.assertIn("high", rec["harness"]["argv"])
        self.assertLess(
            rec["harness"]["argv"].index("high"),
            rec["harness"]["argv"].index("--reasoning-effort"),
        )
        self._raises_naming(rec, "argv")


class CollectedResultRequiresAGreenVerify(_RecordCase):
    """A present result.collected must carry at, by, head, and verify.exit == 0."""

    def _closed_with_collected(self, collected):
        rec = self.built()
        rec["status"] = "closed"
        rec["at"]["closed"] = "2026-09-03T00:00:01Z"
        rec["result"] = {
            "head": rec["snapshot"]["ref_sha"],
            "changed_paths": [],
            "residual_paths": [],
            "envelope": {
                "job": "implement",
                "status": "invalid",
                "verdict": None,
                "counts": {"p1": 0, "p2": 0, "p3": 0, "opinions": 0},
                "findings": [],
                "artifacts": {},
                "spend": {"harness": "codex", "total": 0, "out": 0, "runs": 1},
                "stamp": {
                    "ref": rec["snapshot"]["ref_sha"],
                    "started": None,
                    "ended": None,
                },
                "note": "timeout",
            },
            "collected": collected,
        }
        return rec

    def _green_collected(self, **overrides):
        payload = {
            "at": "2026-09-03T00:00:02Z",
            "by": ls.AGENT,
            "head": "c" * 40,
            "verify": {"command": "true", "exit": 0},
            "reason": None,
        }
        payload.update(overrides)
        return payload

    def test_a_collected_result_without_a_green_verify_is_refused(self):
        rec = self._closed_with_collected(self._green_collected(
            verify={"command": "false", "exit": 1},
        ))
        self.assertEqual(rec["result"]["collected"]["verify"]["exit"], 1)
        self.assertNotEqual(rec["result"]["collected"]["verify"]["exit"], 0)
        self._raises_naming(rec, "result.collected")

    def test_a_collected_result_missing_at_is_refused(self):
        collected = self._green_collected()
        del collected["at"]
        rec = self._closed_with_collected(collected)
        self.assertNotIn("at", rec["result"]["collected"])
        self._raises_naming(rec, "result.collected")

    def test_a_collected_result_missing_by_is_refused(self):
        collected = self._green_collected()
        del collected["by"]
        rec = self._closed_with_collected(collected)
        self.assertNotIn("by", rec["result"]["collected"])
        self._raises_naming(rec, "result.collected")

    def test_a_collected_result_missing_head_is_refused(self):
        collected = self._green_collected()
        del collected["head"]
        rec = self._closed_with_collected(collected)
        self.assertNotIn("head", rec["result"]["collected"])
        self._raises_naming(rec, "result.collected")

    def test_a_collected_result_with_a_non_string_head_is_refused(self):
        rec = self._closed_with_collected(self._green_collected(head=0))
        self.assertEqual(rec["result"]["collected"]["head"], 0)
        self._raises_naming(rec, "result.collected")

    def test_a_collected_result_with_json_false_verify_exit_is_refused(self):
        """Security finding 5: JSON false equals 0 in Python; a forged
        verify.exit must still be refused."""
        rec = self._closed_with_collected(self._green_collected(
            verify={"command": "true", "exit": False},
        ))
        exit_value = rec["result"]["collected"]["verify"]["exit"]
        self.assertIs(exit_value, False)
        self.assertEqual(exit_value, 0)
        self.assertIs(type(exit_value), bool)
        self._raises_naming(rec, "result.collected")


class BriefPolicyBindingShape(_RecordCase):
    """Structural brief.policy from the published lane-policy binding shape.

    Structural validation is not permission admission. These cases do not
    look up an authority store, recompute grants_sha256, or exercise a CLI.

    Git-id fixture: this repository's object format was measured as sha1
    (`git rev-parse --show-object-format` at the authoring tree). The
    valid `ref` is therefore the full 40-character lowercase hex Git id.
    That is this repository's measured object format, not a universal
    SHA-1 policy rule and not a SHA-256 object-id grammar.

    Profile fixture: brief.policy.profile uses the declared profile
    namespace grammar [a-z][a-z0-9-]* without membership lookup.
    """

    _SCHEMA = "agentscient.lane-policy/v1"
    _PATH = "ops/lane-policy.json"
    # Measured object format of this repository, not a policy-universal length.
    _OBJECT_FORMAT = "sha1"
    _FULL_GIT_ID_HEX_LEN = 40
    _VALID_REF = "c" * 40
    _REQUIRED = (
        "schema",
        "path",
        "ref",
        "sha256",
        "admission",
        "profile",
        "template_sha256",
        "grants_sha256",
        "maintenance",
    )
    _REQUIRED_SET = frozenset((
        "schema",
        "path",
        "ref",
        "sha256",
        "admission",
        "profile",
        "template_sha256",
        "grants_sha256",
        "maintenance",
    ))
    _INVALID_PROFILES = {
        "empty": "",
        "uppercase": "Dev",
        "leading-digit": "1dev",
        "underscore": "fixture_only",
        "leading-hyphen": "-dev",
        "slash": "dev/prod",
    }

    def recmod(self):
        if getattr(self, "record", None) is None:
            self.record = support.load("record")
        return self.record

    def _binding(self, **overrides):
        policy = {
            "schema": self._SCHEMA,
            "path": self._PATH,
            "ref": self._VALID_REF,
            "sha256": "e" * 64,
            "admission": {"record": "D-LANES-1", "sha256": "f" * 64},
            "profile": "fixture-only",
            "template_sha256": self._minimum()["brief"]["template"]["sha256"],
            "grants_sha256": "1" * 64,
            "maintenance": None,
        }
        policy.update(overrides)
        return policy

    def _required_refusal_name(self, field):
        # Rec6: name the missing field. Unqualified "path" and "sha256"
        # are substrings of other record fields (template.path,
        # grants_sha256, template_sha256); "ref" is qualified the same way.
        if field in ("path", "ref", "sha256"):
            return "policy." + field
        return field

    def _with_policy(self, policy):
        rec = self.built()
        rec["brief"]["policy"] = copy.deepcopy(policy)
        return rec

    def _row(self, record_id, digest_char):
        return {"record": record_id, "sha256": digest_char * 64}

    def _maintenance(self, standing=None, per_job=None):
        return {
            "standing": list([] if standing is None else standing),
            "per_job": list([] if per_job is None else per_job),
        }

    def test_a_string_policy_is_refused(self):
        rec = self._with_policy("agentscient.lane-policy/v1")
        self.assertEqual(rec["brief"]["policy"], "agentscient.lane-policy/v1")
        self.assertIsInstance(rec["brief"]["policy"], str)
        self._raises_naming(rec, "policy")

    def test_a_null_policy_is_refused(self):
        rec = self._with_policy(None)
        self.assertIsNone(rec["brief"]["policy"])
        self.assertIn("policy", rec["brief"])
        self._raises_naming(rec, "policy")

    def test_an_empty_object_policy_is_refused(self):
        rec = self._with_policy({})
        self.assertEqual(rec["brief"]["policy"], {})
        self.assertIsInstance(rec["brief"]["policy"], dict)
        self.assertEqual(len(rec["brief"]["policy"]), 0)
        self._raises_naming(rec, "policy")

    def test_a_list_policy_is_refused(self):
        rec = self._with_policy([])
        self.assertEqual(rec["brief"]["policy"], [])
        self.assertIsInstance(rec["brief"]["policy"], list)
        self._raises_naming(rec, "policy")

    def test_each_required_binding_field_missing_is_refused(self):
        self.assertEqual(len(self._REQUIRED), 9)
        self.assertEqual(set(self._REQUIRED), set(self._REQUIRED_SET))
        for field in self._REQUIRED:
            with self.subTest(field=field):
                policy = self._binding()
                del policy[field]
                rec = self._with_policy(policy)
                self.assertNotIn(field, rec["brief"]["policy"])
                self._raises_naming(rec, self._required_refusal_name(field))

    def test_wrong_schema_value_is_refused(self):
        policy = self._binding(schema="agentscient.lane-policy/v0")
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["schema"], "agentscient.lane-policy/v0")
        self.assertNotEqual(rec["brief"]["policy"]["schema"], self._SCHEMA)
        self._raises_naming(rec, "schema")

    def test_non_string_schema_is_refused(self):
        policy = self._binding(schema=1)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["schema"], 1)
        self._raises_naming(rec, "schema")

    def test_wrong_path_is_refused(self):
        policy = self._binding(path="ops/conductor/lane-policy.json")
        rec = self._with_policy(policy)
        self.assertEqual(
            rec["brief"]["policy"]["path"], "ops/conductor/lane-policy.json",
        )
        self.assertNotEqual(rec["brief"]["policy"]["path"], self._PATH)
        self._raises_naming(rec, "policy.path")

    def test_non_string_path_is_refused(self):
        policy = self._binding(path=["ops/lane-policy.json"])
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["path"], ["ops/lane-policy.json"])
        self._raises_naming(rec, "policy.path")

    def test_abbreviated_ref_is_refused(self):
        policy = self._binding(ref="c" * 7)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["ref"], "c" * 7)
        self.assertEqual(len(rec["brief"]["policy"]["ref"]), 7)
        self.assertNotEqual(
            len(rec["brief"]["policy"]["ref"]), self._FULL_GIT_ID_HEX_LEN,
        )
        self._raises_naming(rec, "policy.ref")

    def test_uppercase_ref_is_refused(self):
        policy = self._binding(ref="C" * self._FULL_GIT_ID_HEX_LEN)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["ref"], "C" * self._FULL_GIT_ID_HEX_LEN)
        self.assertEqual(len(rec["brief"]["policy"]["ref"]), self._FULL_GIT_ID_HEX_LEN)
        self.assertNotEqual(
            rec["brief"]["policy"]["ref"], rec["brief"]["policy"]["ref"].lower(),
        )
        self._raises_naming(rec, "policy.ref")

    def test_non_hex_ref_is_refused(self):
        policy = self._binding(ref="g" * self._FULL_GIT_ID_HEX_LEN)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["ref"], "g" * self._FULL_GIT_ID_HEX_LEN)
        self.assertEqual(len(rec["brief"]["policy"]["ref"]), self._FULL_GIT_ID_HEX_LEN)
        self._raises_naming(rec, "policy.ref")

    def test_non_string_ref_is_refused(self):
        policy = self._binding(ref=40)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["ref"], 40)
        self._raises_naming(rec, "policy.ref")

    def test_empty_ref_is_refused(self):
        policy = self._binding(ref="")
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["ref"], "")
        self._raises_naming(rec, "policy.ref")

    def test_uppercase_policy_sha256_is_refused(self):
        policy = self._binding(sha256="E" * 64)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["sha256"], "E" * 64)
        self.assertEqual(len(rec["brief"]["policy"]["sha256"]), 64)
        self.assertNotEqual(
            rec["brief"]["policy"]["sha256"],
            rec["brief"]["policy"]["sha256"].lower(),
        )
        self._raises_naming(rec, "policy.sha256")

    def test_short_policy_sha256_is_refused(self):
        policy = self._binding(sha256="e" * 40)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["sha256"], "e" * 40)
        self.assertEqual(len(rec["brief"]["policy"]["sha256"]), 40)
        self._raises_naming(rec, "policy.sha256")

    def test_non_string_policy_sha256_is_refused(self):
        policy = self._binding(sha256=["e" * 64])
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["sha256"], ["e" * 64])
        self._raises_naming(rec, "policy.sha256")

    def test_admission_that_is_not_an_object_is_refused(self):
        policy = self._binding(admission="D-LANES-1")
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["admission"], "D-LANES-1")
        self._raises_naming(rec, "admission")

    def test_admission_missing_record_is_refused(self):
        policy = self._binding(admission={"sha256": "f" * 64})
        rec = self._with_policy(policy)
        self.assertNotIn("record", rec["brief"]["policy"]["admission"])
        self._raises_naming(rec, "admission")

    def test_admission_missing_sha256_is_refused(self):
        policy = self._binding(admission={"record": "D-LANES-1"})
        rec = self._with_policy(policy)
        self.assertNotIn("sha256", rec["brief"]["policy"]["admission"])
        self._raises_naming(rec, "admission")

    def test_admission_record_outside_the_decision_id_pattern_is_refused(self):
        policy = self._binding(admission={"record": "d-lanes-1", "sha256": "f" * 64})
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["admission"]["record"], "d-lanes-1")
        self._raises_naming(rec, "admission")

    def test_admission_record_missing_the_D_prefix_is_refused(self):
        policy = self._binding(admission={"record": "LANES-1", "sha256": "f" * 64})
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["admission"]["record"], "LANES-1")
        self._raises_naming(rec, "admission")

    def test_empty_admission_record_is_refused(self):
        policy = self._binding(admission={"record": "", "sha256": "f" * 64})
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["admission"]["record"], "")
        self._raises_naming(rec, "admission")

    def test_non_string_admission_record_is_refused(self):
        policy = self._binding(admission={"record": ["D-LANES-1"], "sha256": "f" * 64})
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["admission"]["record"], ["D-LANES-1"])
        self._raises_naming(rec, "admission")

    def test_admission_sha256_uppercase_is_refused(self):
        policy = self._binding(admission={"record": "D-LANES-1", "sha256": "F" * 64})
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["admission"]["sha256"], "F" * 64)
        self._raises_naming(rec, "admission")

    def test_template_sha256_unequal_to_brief_template_is_refused(self):
        policy = self._binding(template_sha256="a" * 64)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["template_sha256"], "a" * 64)
        self.assertEqual(len(rec["brief"]["policy"]["template_sha256"]), 64)
        self.assertNotEqual(
            rec["brief"]["policy"]["template_sha256"],
            rec["brief"]["template"]["sha256"],
        )
        self._raises_naming(rec, "template_sha256")

    def test_uppercase_template_sha256_is_refused(self):
        policy = self._binding(template_sha256="C" * 64)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["template_sha256"], "C" * 64)
        self.assertEqual(len(rec["brief"]["policy"]["template_sha256"]), 64)
        self.assertNotEqual(
            rec["brief"]["policy"]["template_sha256"],
            rec["brief"]["policy"]["template_sha256"].lower(),
        )
        self.assertEqual(rec["brief"]["template"]["sha256"], "c" * 64)
        self._raises_naming(rec, "template_sha256")

    def test_short_template_sha256_is_refused(self):
        policy = self._binding(template_sha256="c" * 40)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["template_sha256"], "c" * 40)
        self.assertEqual(len(rec["brief"]["policy"]["template_sha256"]), 40)
        self._raises_naming(rec, "template_sha256")

    def test_uppercase_grants_sha256_is_refused(self):
        policy = self._binding(grants_sha256="A" * 64)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["grants_sha256"], "A" * 64)
        self.assertEqual(len(rec["brief"]["policy"]["grants_sha256"]), 64)
        self._raises_naming(rec, "grants_sha256")

    def test_short_grants_sha256_is_refused(self):
        policy = self._binding(grants_sha256="1" * 40)
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["grants_sha256"], "1" * 40)
        self._raises_naming(rec, "grants_sha256")

    def test_non_string_grants_sha256_is_refused(self):
        policy = self._binding(grants_sha256=["1" * 64])
        rec = self._with_policy(policy)
        self.assertEqual(rec["brief"]["policy"]["grants_sha256"], ["1" * 64])
        self._raises_naming(rec, "grants_sha256")

    def test_profile_outside_the_specified_syntax_is_refused(self):
        invalid = dict(self._INVALID_PROFILES)
        self.assertEqual(len(invalid), 6)
        self.assertEqual(
            set(invalid),
            {
                "empty",
                "uppercase",
                "leading-digit",
                "underscore",
                "leading-hyphen",
                "slash",
            },
        )
        for label, profile in invalid.items():
            with self.subTest(label=label, profile=profile):
                rec = self._with_policy(self._binding(profile=profile))
                self.assertEqual(rec["brief"]["policy"]["profile"], profile)
                self._raises_naming(rec, "profile")

    def test_non_string_profile_is_refused(self):
        rec = self._with_policy(self._binding(profile=["fixture-only"]))
        self.assertEqual(rec["brief"]["policy"]["profile"], ["fixture-only"])
        self._raises_naming(rec, "profile")

    def test_maintenance_empty_object_is_refused(self):
        rec = self._with_policy(self._binding(maintenance={}))
        self.assertEqual(rec["brief"]["policy"]["maintenance"], {})
        self._raises_naming(rec, "maintenance")

    def test_maintenance_list_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=[]))
        self.assertEqual(rec["brief"]["policy"]["maintenance"], [])
        self._raises_naming(rec, "maintenance")

    def test_maintenance_missing_standing_is_refused(self):
        rec = self._with_policy(self._binding(maintenance={"per_job": []}))
        self.assertNotIn("standing", rec["brief"]["policy"]["maintenance"])
        self._raises_naming(rec, "maintenance")

    def test_maintenance_missing_per_job_is_refused(self):
        rec = self._with_policy(self._binding(maintenance={"standing": []}))
        self.assertNotIn("per_job", rec["brief"]["policy"]["maintenance"])
        self._raises_naming(rec, "maintenance")

    def test_maintenance_extra_key_is_refused(self):
        maint = self._maintenance()
        maint["purpose"] = "widen"
        rec = self._with_policy(self._binding(maintenance=maint))
        self.assertEqual(
            set(rec["brief"]["policy"]["maintenance"]),
            {"standing", "per_job", "purpose"},
        )
        self._raises_naming(rec, "maintenance")

    def test_standing_that_is_not_a_list_is_refused(self):
        rec = self._with_policy(self._binding(maintenance={
            "standing": self._row("D-LANES-1", "2"),
            "per_job": [],
        }))
        self.assertIsInstance(rec["brief"]["policy"]["maintenance"]["standing"], dict)
        self._raises_naming(rec, "maintenance")

    def test_per_job_that_is_not_a_list_is_refused(self):
        rec = self._with_policy(self._binding(maintenance={
            "standing": [],
            "per_job": self._row("D-JOB-1", "3"),
        }))
        self.assertIsInstance(rec["brief"]["policy"]["maintenance"]["per_job"], dict)
        self._raises_naming(rec, "maintenance")

    def test_standing_item_missing_record_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            standing=[{"sha256": "2" * 64}],
        )))
        self.assertNotIn("record", rec["brief"]["policy"]["maintenance"]["standing"][0])
        self._raises_naming(rec, "maintenance")

    def test_standing_item_missing_sha256_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            standing=[{"record": "D-LANES-1"}],
        )))
        self.assertNotIn("sha256", rec["brief"]["policy"]["maintenance"]["standing"][0])
        self._raises_naming(rec, "maintenance")

    def test_standing_not_sorted_by_record_id_is_refused(self):
        standing = [self._row("D-LANES-2", "2"), self._row("D-LANES-1", "3")]
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            standing=standing,
        )))
        ids = [row["record"] for row in rec["brief"]["policy"]["maintenance"]["standing"]]
        self.assertEqual(ids, ["D-LANES-2", "D-LANES-1"])
        self.assertNotEqual(ids, sorted(set(ids)))
        self._raises_naming(rec, "maintenance")

    def test_duplicate_standing_record_id_is_refused(self):
        standing = [self._row("D-LANES-1", "2"), self._row("D-LANES-1", "3")]
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            standing=standing,
        )))
        ids = [row["record"] for row in rec["brief"]["policy"]["maintenance"]["standing"]]
        self.assertEqual(ids, ["D-LANES-1", "D-LANES-1"])
        self.assertNotEqual(len(ids), len(set(ids)))
        self._raises_naming(rec, "maintenance")

    def test_standing_decision_id_outside_the_pattern_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            standing=[self._row("LANES-1", "2")],
        )))
        self.assertEqual(
            rec["brief"]["policy"]["maintenance"]["standing"][0]["record"], "LANES-1",
        )
        self._raises_naming(rec, "maintenance")

    def test_per_job_not_sorted_by_record_id_is_refused(self):
        per_job = [self._row("D-JOB-2", "4"), self._row("D-JOB-1", "5")]
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            per_job=per_job,
        )))
        ids = [row["record"] for row in rec["brief"]["policy"]["maintenance"]["per_job"]]
        self.assertEqual(ids, ["D-JOB-2", "D-JOB-1"])
        self.assertNotEqual(ids, sorted(set(ids)))
        self._raises_naming(rec, "maintenance")

    def test_per_job_item_missing_record_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            per_job=[{"sha256": "4" * 64}],
        )))
        self.assertNotIn("record", rec["brief"]["policy"]["maintenance"]["per_job"][0])
        self._raises_naming(rec, "maintenance")

    def test_per_job_item_missing_sha256_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            per_job=[{"record": "D-JOB-1"}],
        )))
        self.assertNotIn("sha256", rec["brief"]["policy"]["maintenance"]["per_job"][0])
        self._raises_naming(rec, "maintenance")

    def test_duplicate_per_job_record_id_is_refused(self):
        per_job = [self._row("D-JOB-1", "4"), self._row("D-JOB-1", "5")]
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            per_job=per_job,
        )))
        ids = [row["record"] for row in rec["brief"]["policy"]["maintenance"]["per_job"]]
        self.assertEqual(ids, ["D-JOB-1", "D-JOB-1"])
        self.assertNotEqual(len(ids), len(set(ids)))
        self._raises_naming(rec, "maintenance")

    def test_per_job_decision_id_outside_the_pattern_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            per_job=[self._row("JOB-1", "4")],
        )))
        self.assertEqual(
            rec["brief"]["policy"]["maintenance"]["per_job"][0]["record"], "JOB-1",
        )
        self._raises_naming(rec, "maintenance")

    def test_per_job_item_uppercase_digest_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            per_job=[{"record": "D-JOB-1", "sha256": "F" * 64}],
        )))
        self.assertEqual(
            rec["brief"]["policy"]["maintenance"]["per_job"][0]["sha256"], "F" * 64,
        )
        self._raises_naming(rec, "maintenance")

    def test_standing_item_uppercase_digest_is_refused(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance(
            standing=[{"record": "D-LANES-1", "sha256": "B" * 64}],
        )))
        self.assertEqual(
            rec["brief"]["policy"]["maintenance"]["standing"][0]["sha256"], "B" * 64,
        )
        self._raises_naming(rec, "maintenance")

    def test_a_legacy_record_with_policy_absent_validates(self):
        rec = self.built()
        self.assertNotIn("policy", rec["brief"])
        out = self.recmod().validate(rec)
        self.assertNotIn("policy", out["brief"])
        self.assertEqual(out["id"], rec["id"])

    def test_a_complete_valid_binding_validates(self):
        binding = self._binding()
        rec = self._with_policy(binding)
        out = self.recmod().validate(rec)
        self.assertEqual(out["brief"]["policy"], binding)
        self.assertEqual(
            out["brief"]["policy"]["template_sha256"],
            out["brief"]["template"]["sha256"],
        )
        self.assertIsNone(out["brief"]["policy"]["maintenance"])

    def test_build_then_validate_accepts_a_complete_valid_binding(self):
        payload = self._minimum()
        brief = dict(payload["brief"])
        brief["policy"] = self._binding()
        rec = self.built(brief=brief)
        out = self.recmod().validate(rec)
        self.assertEqual(out["brief"]["policy"]["schema"], self._SCHEMA)
        self.assertEqual(out["brief"]["policy"]["profile"], "fixture-only")
        self.assertEqual(
            out["brief"]["policy"]["template_sha256"],
            out["brief"]["template"]["sha256"],
        )

    def test_null_maintenance_validates_when_no_protected_writes_are_requested(self):
        rec = self._with_policy(self._binding(maintenance=None))
        self.assertIsNone(rec["brief"]["policy"]["maintenance"])
        out = self.recmod().validate(rec)
        self.assertIsNone(out["brief"]["policy"]["maintenance"])

    def test_empty_maintenance_lists_validate(self):
        rec = self._with_policy(self._binding(maintenance=self._maintenance()))
        self.assertEqual(rec["brief"]["policy"]["maintenance"]["standing"], [])
        self.assertEqual(rec["brief"]["policy"]["maintenance"]["per_job"], [])
        out = self.recmod().validate(rec)
        self.assertEqual(out["brief"]["policy"]["maintenance"]["standing"], [])
        self.assertEqual(out["brief"]["policy"]["maintenance"]["per_job"], [])

    def test_sorted_unique_maintenance_rows_validate(self):
        maint = self._maintenance(
            standing=[self._row("D-LANES-1", "2"), self._row("D-LANES-2", "3")],
            per_job=[self._row("D-JOB-1", "4")],
        )
        rec = self._with_policy(self._binding(maintenance=maint))
        standing_ids = [
            row["record"] for row in rec["brief"]["policy"]["maintenance"]["standing"]
        ]
        self.assertEqual(standing_ids, ["D-LANES-1", "D-LANES-2"])
        self.assertEqual(standing_ids, sorted(set(standing_ids)))
        out = self.recmod().validate(rec)
        self.assertEqual(
            [row["record"] for row in out["brief"]["policy"]["maintenance"]["standing"]],
            ["D-LANES-1", "D-LANES-2"],
        )

    def test_a_syntactically_valid_synthetic_profile_validates_without_membership(self):
        rec = self._with_policy(self._binding(profile="fixture-only"))
        self.assertEqual(rec["brief"]["policy"]["profile"], "fixture-only")
        out = self.recmod().validate(rec)
        self.assertEqual(out["brief"]["policy"]["profile"], "fixture-only")

    def test_a_digit_bearing_syntactically_valid_synthetic_profile_validates(self):
        rec = self._with_policy(self._binding(profile="fixture-only2"))
        self.assertEqual(rec["brief"]["policy"]["profile"], "fixture-only2")
        out = self.recmod().validate(rec)
        self.assertEqual(out["brief"]["policy"]["profile"], "fixture-only2")

    def test_template_digest_equality_holds_when_both_digests_change_together(self):
        rec = self.built()
        rec["brief"]["template"]["sha256"] = "a" * 64
        rec["brief"]["policy"] = self._binding(template_sha256="a" * 64)
        self.assertEqual(
            rec["brief"]["policy"]["template_sha256"],
            rec["brief"]["template"]["sha256"],
        )
        out = self.recmod().validate(rec)
        self.assertEqual(out["brief"]["policy"]["template_sha256"], "a" * 64)
        self.assertEqual(
            out["brief"]["policy"]["template_sha256"],
            out["brief"]["template"]["sha256"],
        )
