"""Immutable work-order declaration at canonical launch.

Written from FINDING-ADMISSION.md §Frozen work-order declaration.
launch.py internals were not read. Intended reds: paid jobs without
--work-order still spawn a model; brief.admission is absent; invalid
declaration bytes are not admission-criteria.

Fixture checks in this file use established launch/record surfaces and
must pass before the new-flag assertions.
"""

from __future__ import annotations

import json
import unittest

import admission_enforcement_support as aes
import launch_support as ls


def _minimum_record():
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


class _DeclarationLaunch(ls._TempLaunch):
    def plant_scope(self):
        path = self.home / "owner-scope.md"
        text = "owner scope for admission enforcement tests\n"
        path.write_text(text, encoding="utf-8")
        digest = aes.sha256_text(text)
        self.assertEqual(path.read_text(encoding="utf-8"), text)
        return path, digest

    def plant_work_order(self, **overrides):
        scope_path, scope_sha = self.plant_scope()
        authority = self.home / "owner-enforcement-addendum.md"
        authority.write_text("enforce prevention; not guidance\n", encoding="utf-8")
        body = aes.work_order(
            ident="WO-admission-aa41",
            branch=self.lineage,
            base_ref=self.ref,
            scope={"path": "owner-scope.md", "sha256": scope_sha},
            authority=[{
                "path": "owner-enforcement-addendum.md",
                "sha256": aes.sha256_file(authority),
            }],
            test_scope=["ops/devlane/dispatch/tests/"],
            fixture=[aes.command_row("fx-empty", "true", [])],
            acceptance=[aes.command_row(
                "ac-decl",
                "python3 -m unittest discover -s ops/devlane/dispatch/tests "
                "-p test_admission_enforcement_declaration.py",
                [],
            )],
            final=[aes.command_row("fn-suites", "ops/bin/suites.sh", [])],
            reviews=[{"slot": "check-tests", "job": "check-tests"}],
        )
        body.update(overrides)
        path = self.home / "work-order.json"
        digest = aes.write_json(path, body)
        self.assertEqual(aes.sha256_file(path), digest)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["id"], body["id"])
        planted_inputs = json.loads(path.read_text(encoding="utf-8"))["fixture"][0]["inputs"]
        self.assertEqual(planted_inputs, [])
        return path, body, digest, scope_path

    def paid_argv(self, job, stage, extra=(), scope="pin the launcher"):
        scope_path, _digest = self.plant_scope()
        flags = ["--input", str(scope_path), *extra]
        return self.argv_for(
            job=job, harness="grok", stage=stage, scope=scope, extra=flags,
        )

    def assert_admission_launch_refusal(self, code, out, err, ident):
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertEqual(
            code, ls.REFUSAL_EXIT,
            f"{ident} refuses with exit 3, got {code}: {text!r}",
        )
        self.assert_wire_refusal(
            code, out, err, ident=ident, phrases=[ident],
        )
        return text

    def assert_criteria_named(self, code, out, err):
        """Fixture already proved; the intended red is the class token."""
        self.assert_not_started()
        text = self.combined(out, err)
        self.assertIn(
            "admission-criteria",
            text.lower(),
            f"expected admission-criteria, got exit {code}: {text!r}",
        )
        self.assertEqual(code, ls.REFUSAL_EXIT, text)
        return text


class FixturePreconditionsHoldOnBaseline(_DeclarationLaunch):
    """GREEN neighbours: plan needs no work-order; empty inputs stay empty."""

    def test_plan_without_a_work_order_still_closes(self):
        rec, witness, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.assertEqual(rec["job"], "plan")
        self.assertEqual(rec["brief"]["inputs"], [])
        self.assertTrue(witness["argv"])

    def test_planted_work_order_keeps_empty_command_inputs(self):
        path, body, digest, _scope = self.plant_work_order()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["fixture"][0]["inputs"], [])
        self.assertEqual(aes.retain_list(loaded["fixture"][0]["inputs"], default=["x"]), [])
        self.assertEqual(loaded["terminal"], aes.TERMINAL)
        self.assertTrue(aes.SHA256_RE.fullmatch(digest))
        self.assertEqual(body["id"], "WO-admission-aa41")


class PaidWorkRequiresTheFrozenDeclaration(_DeclarationLaunch):
    """--work-order is required for tests, implementation, review, adjudicate."""

    def test_check_tests_without_work_order_refuses_before_the_model(self):
        code, out, err = self.dispatch(self.paid_argv("check-tests", "check-tests"))
        self.assert_admission_launch_refusal(code, out, err, "admission-criteria")
        self.assertEqual(self.record_files(), [])

    def test_author_tests_without_work_order_refuses_before_the_model(self):
        code, out, err = self.dispatch(self.paid_argv("author-tests", "tests"))
        self.assert_admission_launch_refusal(code, out, err, "admission-criteria")

    def test_implement_without_work_order_refuses_before_the_model(self):
        code, out, err = self.dispatch(self.paid_argv("implement", "code"))
        self.assert_admission_launch_refusal(code, out, err, "admission-criteria")

    def test_adjudicate_without_work_order_refuses_before_the_model(self):
        code, out, err = self.dispatch(
            self.paid_argv("adjudicate", "adjudicate", scope=None),
        )
        self.assert_admission_launch_refusal(code, out, err, "admission-criteria")

    def test_a_valid_declaration_lands_brief_admission_and_starts_once(self):
        wo, body, digest, scope = self.plant_work_order()
        self.assertEqual(body["fixture"][0]["inputs"], [])
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--work-order", str(wo), "--input", str(scope)],
        ))
        text = self.combined(out, err)
        self.assertNotIn(
            "unrecognized arguments",
            text.lower(),
            f"missing --work-order flag is not fixture proof: {text!r}",
        )
        self.assertEqual(code, 0, text)
        rec = self.read_record()
        admission = rec["brief"]["admission"]
        self.assertEqual(set(admission), set(aes.ADMISSION_BRIEF_KEYS))
        self.assertEqual(admission["work_order"], body["id"])
        self.assertEqual(admission["declaration_sha256"], digest)
        self.assertEqual(admission["scope_sha256"], body["scope"]["sha256"])
        self.assertIsNone(admission["review"])
        self.assertTrue(self.start_witness.is_file())


class ChangedOrMalformedCriteriaRefuse(_DeclarationLaunch):
    def test_blank_work_order_id_is_admission_criteria(self):
        wo, body, _digest, scope = self.plant_work_order()
        self.assertEqual(body["fixture"][0]["inputs"], [])
        body["id"] = " "
        aes.write_json(wo, body)
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--work-order", str(wo), "--input", str(scope)],
        ))
        self.assert_criteria_named(code, out, err)

    def test_changed_final_command_is_admission_criteria(self):
        wo, body, digest, scope = self.plant_work_order()
        body["final"][0]["command"] = "echo mutated-final"
        aes.write_json(wo, body)
        self.assertNotEqual(aes.sha256_file(wo), digest)
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--work-order", str(wo), "--input", str(scope)],
        ))
        self.assert_criteria_named(code, out, err)

    def test_duplicate_json_keys_in_the_declaration_refuse(self):
        scope_path, scope_sha = self.plant_scope()
        raw = (
            '{\n'
            '  "id": "WO-dup",\n'
            '  "id": "WO-other",\n'
            '  "branch": "work",\n'
            f'  "base_ref": "{self.ref}",\n'
            f'  "scope": {{"path": "owner-scope.md", "sha256": "{scope_sha}"}},\n'
            '  "authority": [],\n'
            '  "test_scope": ["ops/devlane/dispatch/tests/"],\n'
            '  "fixture": [{"id": "fx", "command": "true", "inputs": []}],\n'
            '  "acceptance": [{"id": "ac", "command": "true", "inputs": []}],\n'
            '  "final": [{"id": "fn", "command": "ops/bin/suites.sh", "inputs": []}],\n'
            '  "reviews": [{"slot": "check-tests", "job": "check-tests"}],\n'
            '  "terminal": {"action": "draft-pr", "base": "dev"}\n'
            '}\n'
        )
        wo = self.home / "dup.json"
        wo.write_text(raw, encoding="utf-8")
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--work-order", str(wo), "--input", str(scope_path)],
        ))
        self.assert_criteria_named(code, out, err)

    def test_absolute_declaration_paths_refuse(self):
        wo, body, _digest, scope = self.plant_work_order()
        body["test_scope"] = [str(self.home / "outside")]
        aes.write_json(wo, body)
        code, out, err = self.dispatch(self.argv_for(
            job="check-tests",
            harness="grok",
            stage="check-tests",
            extra=["--work-order", str(wo), "--input", str(scope)],
        ))
        self.assert_criteria_named(code, out, err)


class RecordValidateBindsAdmissionShape(unittest.TestCase):
    """record.py validates brief.admission; worker prose is not proof."""

    def recmod(self):
        return ls.require_module(self, "record")

    def test_valid_admission_is_preserved(self):
        record = self.recmod()
        payload = _minimum_record()
        payload["brief"]["admission"] = aes.admission_brief(
            "WO-admission-aa41", "a" * 64, "b" * 64, review=None,
        )
        built = record.build(payload)
        kept = built["brief"]["admission"]
        self.assertEqual(kept["work_order"], "WO-admission-aa41")
        self.assertEqual(kept["review"], None)
        record.validate(built)

    def test_blank_work_order_id_is_refused(self):
        record = self.recmod()
        payload = _minimum_record()
        payload["brief"]["admission"] = aes.admission_brief(
            " ", "a" * 64, "b" * 64, review=None,
        )
        with self.assertRaises(Exception) as caught:
            record.validate(record.build(payload))
        self.assertIn("admission", str(caught.exception).lower())

    def test_an_extra_admission_key_is_refused(self):
        record = self.recmod()
        payload = _minimum_record()
        admission = aes.admission_brief(
            "WO-admission-aa41", "a" * 64, "b" * 64, review=None,
        )
        admission["hint"] = "worker-supplied"
        payload["brief"]["admission"] = admission
        with self.assertRaises(Exception) as caught:
            record.validate(record.build(payload))
        self.assertIn("admission", str(caught.exception).lower())


if __name__ == "__main__":
    unittest.main()
