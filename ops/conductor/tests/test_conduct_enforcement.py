"""Independent enforcement tests for conduct startup.

Contracts (only): harness-capabilities.md (safe argv grammar, compile
binding, secret-free refusals), permission-surface.md (normalize_tool,
evaluate_tool, COND-HAND/AXIS/EFFECT), conductor-start-plan.md
(pre-effect vs late refusal, resume binding). Implementation unread.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from conduct_test_support import (  # noqa: E402
    ADMITTED_EMPTY,
    ADMITTED_EQUALS,
    ADMITTED_FLAG,
    ADMITTED_SPLIT,
    CANARY_EQUALS,
    DECISION_KEYS,
    DELEGATE_TARGETS,
    GRAMMAR,
    REASONS,
    REFUSAL_RE,
    REQUEST_KEYS,
    SCHEMA_DECISION,
    SCHEMA_TOOL,
    SECRET_CANARY,
    ConductFixture,
    canonical_digest,
)


class AdmittedTokens(ConductFixture):
    def test_equals_form_is_preserved_byte_for_byte(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(tokens=list(ADMITTED_EQUALS))
        )
        self.assertEqual(desc["forwarded_tokens"], ADMITTED_EQUALS)
        argv = compiled["argv"]
        self.assertEqual(list(argv[-2:]), ["--display=compact", "--quiet"])
        self.assertEqual(argv[-2:], ADMITTED_EQUALS)

    def test_split_form_keeps_two_tokens(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(tokens=list(ADMITTED_SPLIT))
        )
        self.assertEqual(desc["forwarded_tokens"], ADMITTED_SPLIT)
        self.assertEqual(compiled["argv"][-2:], ["--display", "plain"])

    def test_flag_form_is_admitted(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(tokens=list(ADMITTED_FLAG))
        )
        self.assertEqual(desc["forwarded_tokens"], ADMITTED_FLAG)
        self.assertIn("--quiet", compiled["argv"])

    def test_empty_forwarded_vector_is_admitted(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(tokens=list(ADMITTED_EMPTY))
        )
        self.assertEqual(desc["forwarded_tokens"], [])
        self.assertNotIn("--display", compiled["argv"])
        self.assertNotIn("--quiet", compiled["argv"])

    def test_grammar_fixture_is_the_contract_bytes(self) -> None:
        self.assertEqual(GRAMMAR["schema"], "adapter-argv/1")
        desc, compiled = self.assert_prepare_ok(self.prepare())
        self.assertEqual(
            desc["adapter"]["grammar_sha256"],
            self.grammar_sha256,
        )
        self.assertEqual(
            compiled["capability"]["adapter"]["grammar_sha256"],
            self.grammar_sha256,
        )


class FixedArgvRefusals(ConductFixture):
    def test_repeated_display_across_forms_refuses_at_index_two(self) -> None:
        tokens = ["--display=compact", "--quiet", "--display", "plain"]
        result = self.prepare(tokens=tokens)
        self.assert_prepare_refused(result)
        proc = self.run_cli(["codex", "dev", "--", *tokens])
        self.assert_cli_refusal(proc, "conduct-argv")
        self.assertIn("index 2", proc.stderr)

    def test_short_alias_refuses(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "-q"])
        self.assert_cli_refusal(proc, "conduct-argv")
        self.assertIn("index 0", proc.stderr)

    def test_abbreviation_refuses(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "--dis"])
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_missing_display_value_refuses(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "--display"])
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_bare_double_dash_inside_tokens_refuses(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "--"])
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_response_file_form_refuses(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "@file"])
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_trailing_positional_refuses(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "plain"])
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_reserved_config_option_refuses(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "--config=x"])
        self.assert_cli_refusal(proc, "conduct-argv")
        self.assertNotIn("x", proc.stderr.split("needed")[0])

    def test_rejected_tokens_never_reach_launch_records(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", CANARY_EQUALS])
        self.assert_cli_refusal(proc, "conduct-argv")
        self.assertFalse(self.receipt.exists())
        self.assertIsNone(self.dispatch.claimed_path)
        added, _removed, _changed = self.effects.delta()
        self.assertFalse(any("record.json" in name for name in added))

    def test_vector_level_violation_uses_index_zero(self) -> None:
        huge = ["--quiet"] * 65
        proc = self.run_cli(["codex", "dev", "--", *huge])
        self.assert_cli_refusal(proc, "conduct-argv")
        self.assertIn("index 0", proc.stderr)


class SecretCanary(ConductFixture):
    def test_rejected_secret_is_absent_from_prompt_output_state_and_git(
        self,
    ) -> None:
        proc = self.run_cli(["codex", "dev", "--", CANARY_EQUALS])
        self.assert_cli_refusal(proc, "conduct-argv")
        blob = (
            proc.stdout
            + proc.stderr
            + json.dumps(list(self.effects.delta()))
        )
        self.assertNotIn(SECRET_CANARY, blob)
        self.assertNotIn(CANARY_EQUALS, proc.stderr)
        self.assertFalse(self.receipt.exists())
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if path == self.staged_tool:
                continue
            text = path.read_bytes()
            self.assertNotIn(SECRET_CANARY.encode("ascii"), text)


class ResumeArgv(ConductFixture):
    def test_resume_reproduces_invariant_and_differs_in_argv_digest(
        self,
    ) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(tokens=list(ADMITTED_EQUALS))
        )
        ctx = self.make_context(operation="resume", parent=desc)
        again, compiled2 = self.assert_prepare_ok(
            self.prepare(
                tokens=list(ADMITTED_EQUALS),
                operation="resume",
                ctx=ctx,
                parent=desc,
            )
        )
        self.assertEqual(again["launch_id"], desc["launch_id"])
        self.assertEqual(
            compiled2["binding"]["invariant_sha256"],
            compiled["binding"]["invariant_sha256"],
        )
        self.assertNotEqual(
            compiled2["binding"]["argv_sha256"],
            compiled["binding"]["argv_sha256"],
        )
        self.assertEqual(compiled2["binding"]["operation"], "resume")
        self.assertEqual(again["forwarded_tokens"], ADMITTED_EQUALS)

    def test_repeated_resume_with_identical_inputs_is_byte_identical(
        self,
    ) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        ctx = self.make_context(operation="resume", parent=desc)
        first, compiled1 = self.assert_prepare_ok(
            self.prepare(operation="resume", ctx=ctx, parent=desc)
        )
        second, compiled2 = self.assert_prepare_ok(
            self.prepare(operation="resume", ctx=ctx, parent=desc)
        )
        self.assertEqual(first, second)
        self.assertEqual(compiled1["argv"], compiled2["argv"])
        self.assertEqual(
            compiled1["binding"]["argv_sha256"],
            compiled2["binding"]["argv_sha256"],
        )

    def test_raw_vendor_resume_flags_are_not_an_alternative_route(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "-r", "session-id"])
        self.assert_cli_refusal(proc, "conduct-argv")
        proc2 = self.run_cli(["codex", "dev", "--", "resume", "session-id"])
        self.assert_cli_refusal(proc2, "conduct-argv")


class CanonicalDelegation(ConductFixture):
    def _binding_digest(self) -> str:
        launch_id = self.dispatch.reserve(operation="launch")
        desc = self.expected_descriptor(
            self.selection(),
            list(ADMITTED_EMPTY),
            "launch",
            launch_id,
        )
        return canonical_digest(desc)

    def test_evaluate_tool_allows_dispatch_go_and_ladder(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn), "evaluate_tool is the policy counterpart")
        digest = self._binding_digest()
        bound = {
            "descriptor_sha256": digest,
            "binding": self.conductor_binding(
                self.selection(),
                "20260906T120000Z-conduct-codex-a1b2c3",
            ),
            "tools": {
                name: {"kind": "delegate", "arguments": {"type": "object"}}
                for name in DELEGATE_TARGETS
            },
        }
        for target in DELEGATE_TARGETS:
            with self.subTest(target=target):
                request = self.tool_request(
                    kind="delegate",
                    target=target,
                    arguments={"job": "author-tests"},
                    binding_sha256=digest,
                    req_id=f"del{target[:4]}1",
                )
                self.assert_closed_object(request, REQUEST_KEYS)
                decision = fn(bound, request)
                body = self.assert_closed_object(decision, DECISION_KEYS)
                self.assertEqual(body["schema"], SCHEMA_DECISION)
                self.assertEqual(body["id"], request["id"])
                self.assertEqual(body["binding_sha256"], digest)
                self.assertEqual(body["outcome"], "allow")
                self.assertIsNone(body["refusal"])

    def test_coordination_read_is_allowed_without_wf_agent(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        digest = self._binding_digest()
        request = self.tool_request(
            kind="read",
            target="git-status",
            arguments={"ref": "HEAD"},
            binding_sha256=digest,
            req_id="readhead1",
        )
        bound = {
            "descriptor_sha256": digest,
            "binding": self.conductor_binding(
                self.selection(),
                "20260906T120000Z-conduct-codex-a1b2c3",
            ),
            "tools": {"git-status": {"kind": "read"}},
        }
        decision = fn(bound, request)
        body = self.assert_closed_object(decision, DECISION_KEYS)
        self.assertEqual(body["outcome"], "allow")
        self.assertIsNone(body["refusal"])

    def test_read_containing_apply_is_not_classified_as_mutation(self) -> None:
        adapters = self.load_adapters()
        fn = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(fn), "normalize_tool is pinned adapter code")
        digest = self._binding_digest()
        native = self.native_request(
            "read",
            ["git", "log", "--grep", "apply"],
        )
        bound = {"descriptor_sha256": digest}
        request = fn(bound, native)
        body = self.assert_closed_object(request, REQUEST_KEYS)
        self.assertEqual(body["kind"], "read")
        self.assertNotEqual(body["kind"], "forbidden")

    def test_compound_command_naming_dispatch_is_not_an_allowed_request(
        self,
    ) -> None:
        adapters = self.load_adapters()
        fn = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(fn))
        native = self.native_request(
            "shell",
            ["sh", "-c", "echo ops/bin/dispatch.sh && rm -rf ."],
        )
        request = fn({"descriptor_sha256": "0" * 64}, native)
        body = self.assert_closed_object(request, REQUEST_KEYS)
        self.assertEqual(body["kind"], "forbidden")
        self.assertEqual(body["target"], "implementation")
        self.assertEqual(body["arguments"]["reason"], "shell-escape")


class ForbiddenHandwork(ConductFixture):
    def _evaluate(self, kind: str, reason: str) -> dict:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        launch_id = self.dispatch.reserve(operation="launch")
        desc = self.expected_descriptor(
            self.selection(),
            list(ADMITTED_EMPTY),
            "launch",
            launch_id,
        )
        digest = canonical_digest(desc)
        request = self.tool_request(
            kind="forbidden",
            target="implementation",
            arguments={"reason": reason},
            binding_sha256=digest,
            req_id=reason.replace("-", "")[:12] + "1",
        )
        self.assertEqual(request["kind"], "forbidden")
        bound = {
            "descriptor_sha256": digest,
            "binding": self.conductor_binding(
                self.selection(),
                desc["launch_id"],
            ),
        }
        before = self.effects.delta()
        decision = fn(bound, request)
        after = self.effects.delta()
        self.assertEqual(before, after)
        self.assert_no_durable_effects()
        return self.assert_closed_object(decision, DECISION_KEYS)

    def test_direct_edit_is_refused_before_effects(self) -> None:
        body = self._evaluate("forbidden", "direct-edit")
        self.assertEqual(body["outcome"], "refuse")
        self.assertIsNotNone(body["refusal"])
        refusal = body["refusal"]
        self.assertEqual(refusal["class"], "conductor-tool")
        self.assertEqual(refusal["found"], "direct-edit")
        self.assertNotIn(";", refusal["expected"])
        self.assertNotIn(";", refusal["found"])
        self.assertNotIn(";", refusal["needed"])
        self.assertIn("independent doctor", refusal["needed"])

    def test_git_mutation_is_refused_before_effects(self) -> None:
        body = self._evaluate("forbidden", "git-mutation")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "git-mutation")

    def test_shell_escape_is_refused_before_effects(self) -> None:
        body = self._evaluate("forbidden", "shell-escape")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "shell-escape")

    def test_raw_vendor_is_refused_before_effects(self) -> None:
        body = self._evaluate("forbidden", "raw-vendor")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "raw-vendor")

    def test_in_session_agent_is_refused_before_effects(self) -> None:
        body = self._evaluate("forbidden", "in-session-agent")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "in-session-agent")

    def test_every_fixed_reason_code_is_accepted_as_a_reason(self) -> None:
        adapters = self.load_adapters()
        fn = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(fn))
        surfaces = {
            "direct-edit": ("edit", ["apply_patch"]),
            "git-mutation": ("git", ["git", "apply", "x.patch"]),
            "shell-escape": ("shell", ["python3", "-c", "pass"]),
            "raw-vendor": ("vendor", ["codex", "exec"]),
            "in-session-agent": ("agent", ["Agent"]),
            "unknown-tool": ("unknown", ["mystery"]),
        }
        for reason, (surface, argv) in surfaces.items():
            with self.subTest(reason=reason):
                native = self.native_request(surface, argv)
                request = fn({"descriptor_sha256": "a" * 64}, native)
                body = self.assert_closed_object(request, REQUEST_KEYS)
                self.assertEqual(body["schema"], SCHEMA_TOOL)
                self.assertEqual(body["kind"], "forbidden")
                self.assertEqual(body["arguments"]["reason"], reason)
                self.assertIn(reason, REASONS)

    def test_binding_mismatch_is_refused(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        digest = canonical_digest(
            self.expected_descriptor(
                self.selection(),
                list(ADMITTED_EMPTY),
                "launch",
                self.dispatch.reserve(operation="launch"),
            )
        )
        request = self.tool_request(
            kind="read",
            target="git-status",
            arguments={},
            binding_sha256="b" * 64,
            req_id="mismatch1",
        )
        bound = {"descriptor_sha256": digest}
        self.assertNotEqual(request["binding_sha256"], bound["descriptor_sha256"])
        decision = fn(bound, request)
        body = self.assert_closed_object(decision, DECISION_KEYS)
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "binding-mismatch")

    def test_malformed_request_is_refused(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        digest = canonical_digest(
            self.expected_descriptor(
                self.selection(),
                list(ADMITTED_EMPTY),
                "launch",
                self.dispatch.reserve(operation="launch"),
            )
        )
        request = {
            "schema": SCHEMA_TOOL,
            "id": "badreq1",
            "binding_sha256": digest,
            "kind": "delegate",
            "target": "dispatch",
            "arguments": ["not", "an", "object"],
        }
        decision = fn({"descriptor_sha256": digest}, request)
        body = self.assert_closed_object(decision, DECISION_KEYS)
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "malformed-request")

    def test_decision_serializes_to_the_wire_without_raw_echo(self) -> None:
        body = self._evaluate("forbidden", "direct-edit")
        refusal = body["refusal"]
        line = (
            f"{refusal['class']}: expected {refusal['expected']}; "
            f"found {refusal['found']}; needed {refusal['needed']}"
        )
        self.assertIsNotNone(REFUSAL_RE.match(line))
        self.assertNotIn("apply_patch", line)
        self.assertNotIn(str(self.cwd), line)

    def test_adapter_cannot_turn_refusal_into_a_prompt(self) -> None:
        body = self._evaluate("forbidden", "direct-edit")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(self.effects.prompts, [])
        proc = self.run_cli(["codex", "dev"])
        self.assertNotIn("permission", (proc.stdout + proc.stderr).lower())


class FaultyControls(ConductFixture):
    def test_malformed_hook_payload_prevents_admission(self) -> None:
        ctx = self.make_context()
        ctx.hook_payload = "{"
        self.assert_prepare_refused(self.prepare(ctx=ctx))
        self.assert_no_durable_effects()

    def test_replayed_binding_prevents_admission(self) -> None:
        digest = canonical_digest(
            self.expected_descriptor(
                self.selection(),
                list(ADMITTED_EMPTY),
                "launch",
                self.dispatch.reserve(operation="launch"),
            )
        )
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        request = self.tool_request(
            kind="delegate",
            target="dispatch",
            arguments={"job": "author-tests"},
            binding_sha256=digest,
            req_id="replay001",
        )
        bound = {"descriptor_sha256": digest}
        first = fn(bound, request)
        self.assert_closed_object(first, DECISION_KEYS)
        second = fn(bound, request)
        body = self.assert_closed_object(second, DECISION_KEYS)
        self.assertEqual(body["outcome"], "refuse")

    def test_missing_interception_prevents_admission(self) -> None:
        ctx = self.make_context()
        ctx.transport["manifest"] = None
        ctx.interception = None
        self.assert_prepare_refused(self.prepare(ctx=ctx))
        self.assert_no_durable_effects()

    def test_changed_binding_on_resume_is_lane_resume_before_mutation(
        self,
    ) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        parent = dict(desc)
        parent["policy_binding_sha256"] = "c" * 64
        ctx = self.make_context(operation="resume", parent=parent)
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=parent)
        )
        self.assert_no_durable_effects()
        self.assertIsNone(self.dispatch.claimed_path)


class LaunchResumeBeforeEffects(ConductFixture):
    def test_prepare_creates_no_attempt_snapshot_record_or_child(self) -> None:
        self.assert_prepare_ok(self.prepare())
        self.assertIsNone(self.dispatch.claimed_path)
        self.assert_no_durable_effects()
        self.assertFalse(self.receipt.exists())
        self.assertEqual(self.effects.children, [])

    def test_pre_effect_cli_refusal_is_exit_2_empty_stdout(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "--config=x"])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_late_mcp_failure_is_abort_3_with_partials(self) -> None:
        self.mcp_client.connect = False
        proc = self.run_cli(["codex", "dev"])
        if proc.returncode == 2:
            self.assertEqual(proc.stdout, "")
            self.assert_refusal_line(proc.stderr, "conduct-mcp")
            self.assert_no_durable_effects()
            return
        self.assertEqual(proc.returncode, 3)
        self.assert_refusal_line(proc.stderr, "conduct-mcp")
        self.assertNotEqual(self.dispatch.reserved, None)

    def test_resume_preflight_precedes_marker_and_attempt_mutations(
        self,
    ) -> None:
        ctx = self.make_context(operation="resume")
        ctx.parent_descriptor = None
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx)
        )
        added, removed, changed = self.effects.delta()
        self.assertEqual(removed, [])
        self.assertFalse(any("exit" in name for name in added + changed))
        self.assertFalse(any("TRIPPED" in name for name in added + changed))
        self.assertIsNone(self.dispatch.claimed_path)

    def test_cond_effect_n1_delegation_does_not_grant_source_writes(
        self,
    ) -> None:
        desc, compiled = self.assert_prepare_ok(self.prepare())
        cap = compiled["capability"]
        self.assertEqual(cap["scope"]["outputs"], [])
        self.assertEqual(desc["selection"]["job_role"], None)
        denials = cap["scope"]["source_write_denials"]
        self.assertTrue(denials)
        self.assert_no_durable_effects()


if __name__ == "__main__":
    import unittest

    unittest.main()
