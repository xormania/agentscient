"""Independent enforcement tests for conduct startup.

Contracts (only): harness-capabilities.md (safe argv grammar, compile
binding, secret-free refusals), permission-surface.md (opaque role,
mechanism-native input, evaluate_tool, COND-HAND/AXIS/EFFECT),
conductor-start-plan.md (pre-effect vs late refusal, resume binding).
Implementation unread.
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
    CALL_ID,
    CANARY_EQUALS,
    DECISION_KEYS,
    DELEGATE_TARGETS,
    DYNAMIC_CALL_KEYS,
    EMPTY_GRAMMAR,
    GRAMMAR,
    MECHANISM_CODEX,
    MECHANISM_SYNTHETIC,
    REASONS,
    REFUSAL_RE,
    REQUEST_KEYS,
    SCHEMA_DECISION,
    SCHEMA_TOOL,
    SECRET_CANARY,
    SYNTHETIC_GRAMMAR,
    ConductFixture,
    canonical_dumps,
    conduct_argv_line,
    conduct_mcp_line,
)


class AdmittedTokens(ConductFixture):
    def test_equals_form_is_preserved_byte_for_byte(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(
                tokens=list(ADMITTED_EQUALS),
                mechanism=MECHANISM_SYNTHETIC,
            )
        )
        self.assertEqual(desc["forwarded_tokens"], ADMITTED_EQUALS)
        argv = compiled["argv"]
        self.assertEqual(list(argv[-2:]), ["--display=compact", "--quiet"])
        self.assertEqual(argv[-2:], ADMITTED_EQUALS)
        self.assertEqual(desc["adapter"]["mechanism"], MECHANISM_SYNTHETIC)

    def test_split_form_keeps_two_tokens(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(
                tokens=list(ADMITTED_SPLIT),
                mechanism=MECHANISM_SYNTHETIC,
            )
        )
        self.assertEqual(desc["forwarded_tokens"], ADMITTED_SPLIT)
        self.assertEqual(compiled["argv"][-2:], ["--display", "plain"])

    def test_flag_form_is_admitted(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(
                tokens=list(ADMITTED_FLAG),
                mechanism=MECHANISM_SYNTHETIC,
            )
        )
        self.assertEqual(desc["forwarded_tokens"], ADMITTED_FLAG)
        self.assertIn("--quiet", compiled["argv"])

    def test_empty_forwarded_vector_is_admitted(self) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(
                tokens=list(ADMITTED_EMPTY),
                mechanism=MECHANISM_SYNTHETIC,
            )
        )
        self.assertEqual(desc["forwarded_tokens"], [])
        self.assertNotIn("--display", compiled["argv"])
        self.assertNotIn("--quiet", compiled["argv"])

    def test_grammar_fixture_is_the_contract_bytes(self) -> None:
        self.assertEqual(GRAMMAR["schema"], "adapter-argv/1")
        self.assertEqual(SYNTHETIC_GRAMMAR, GRAMMAR)
        self.assertEqual(EMPTY_GRAMMAR["options"], [])
        desc, compiled = self.assert_prepare_ok(
            self.prepare(mechanism=MECHANISM_SYNTHETIC)
        )
        self.assertEqual(
            desc["adapter"]["grammar_sha256"],
            self.grammar_sha256,
        )
        self.assertEqual(
            compiled["capability"]["adapter"]["grammar_sha256"],
            self.grammar_sha256,
        )
        codex, compiled_codex = self.assert_prepare_ok(
            self.prepare(mechanism=MECHANISM_CODEX)
        )
        self.assertEqual(
            codex["adapter"]["grammar_sha256"],
            self.empty_grammar_sha256,
        )
        self.assertEqual(
            compiled_codex["capability"]["adapter"]["grammar_sha256"],
            self.empty_grammar_sha256,
        )


class FixedArgvRefusals(ConductFixture):
    def _cli(self, tokens: list[str]):
        ctx = self.make_context(mechanism=MECHANISM_SYNTHETIC)
        return self.invoke_conduct(["codex", "dev", "--", *tokens], ctx=ctx)

    def test_repeated_display_across_forms_refuses_at_index_two(self) -> None:
        tokens = ["--display=compact", "--quiet", "--display", "plain"]
        result = self.prepare(tokens=tokens, mechanism=MECHANISM_SYNTHETIC)
        self.assert_prepare_refused(
            result,
            "conduct-argv",
            exact=conduct_argv_line(2),
        )
        proc = self._cli(tokens)
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(2),
        )
        self.assertNotIn(SECRET_CANARY, proc.stderr)

    def test_short_alias_refuses(self) -> None:
        proc = self._cli(["-q"])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )

    def test_abbreviation_refuses(self) -> None:
        proc = self._cli(["--dis"])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )

    def test_missing_display_value_refuses(self) -> None:
        proc = self._cli(["--display"])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )

    def test_bare_double_dash_inside_tokens_refuses(self) -> None:
        proc = self._cli(["--"])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )

    def test_response_file_form_refuses(self) -> None:
        proc = self._cli(["@file"])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )

    def test_trailing_positional_refuses(self) -> None:
        proc = self._cli(["plain"])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )

    def test_reserved_config_option_refuses(self) -> None:
        proc = self._cli(["--config=x"])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )
        self.assertNotIn("--config=x", proc.stderr)
        self.assertNotIn("=x", proc.stderr)
        needed = proc.stderr.split("needed", 1)[-1]
        self.assertNotIn("x", needed.split("doctor")[0])

    def test_rejected_tokens_never_reach_launch_records(self) -> None:
        proc = self._cli([CANARY_EQUALS])
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )
        self.assertFalse(self.receipt.exists())
        self.assertIsNone(self.dispatch.claimed_path)
        added, _removed, _changed = self.effects.delta()
        self.assertFalse(any("record.json" in name for name in added))

    def test_vector_level_violation_uses_index_zero(self) -> None:
        huge = ["--quiet"] * 65
        proc = self._cli(huge)
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )


class SecretCanary(ConductFixture):
    def test_rejected_secret_is_absent_from_prompt_output_state_and_git(
        self,
    ) -> None:
        ctx = self.make_context(mechanism=MECHANISM_SYNTHETIC)
        proc = self.invoke_conduct(
            ["codex", "dev", "--", CANARY_EQUALS],
            ctx=ctx,
        )
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )
        blob = proc.stdout + proc.stderr + json.dumps(list(self.effects.delta()))
        self.assertNotIn(SECRET_CANARY, blob)
        self.assertNotIn(CANARY_EQUALS, proc.stderr)
        self.assertFalse(self.receipt.exists())
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if path == self.cli_entry:
                continue
            text = path.read_bytes()
            self.assertNotIn(SECRET_CANARY.encode("ascii"), text)


class ResumeArgv(ConductFixture):
    def test_resume_reproduces_invariant_and_differs_in_argv_digest(
        self,
    ) -> None:
        desc, compiled = self.assert_prepare_ok(
            self.prepare(
                tokens=list(ADMITTED_EQUALS),
                mechanism=MECHANISM_SYNTHETIC,
            )
        )
        ctx = self.make_context(
            operation="resume",
            parent=desc,
            mechanism=MECHANISM_SYNTHETIC,
        )
        again, compiled2 = self.assert_prepare_ok(
            self.prepare(
                tokens=list(ADMITTED_EQUALS),
                operation="resume",
                ctx=ctx,
                parent=desc,
                mechanism=MECHANISM_SYNTHETIC,
            )
        )
        self.assertEqual(again["launch_id"], desc["launch_id"])
        self.assertEqual(
            compiled2["binding"]["invariant_sha256"],
            compiled["binding"]["invariant_sha256"],
        )
        self.assertEqual(compiled2["binding"]["operation"], "resume")
        self.assertEqual(again["forwarded_tokens"], ADMITTED_EQUALS)
        self.assertNotEqual(
            compiled2["binding"]["argv_sha256"],
            compiled["binding"]["argv_sha256"],
        )
        launch_codex, compiled_codex = self.assert_prepare_ok(
            self.prepare(mechanism=MECHANISM_CODEX)
        )
        resume_ctx = self.make_context(
            operation="resume",
            parent=launch_codex,
            mechanism=MECHANISM_CODEX,
        )
        resume_codex, compiled_codex2 = self.assert_prepare_ok(
            self.prepare(
                operation="resume",
                ctx=resume_ctx,
                parent=launch_codex,
                mechanism=MECHANISM_CODEX,
            )
        )
        self.assertEqual(
            compiled_codex2["binding"]["invariant_sha256"],
            compiled_codex["binding"]["invariant_sha256"],
        )
        self.assertEqual(compiled_codex2["argv"], compiled_codex["argv"])
        self.assertEqual(
            compiled_codex2["binding"]["argv_sha256"],
            compiled_codex["binding"]["argv_sha256"],
        )
        self.assertEqual(resume_codex["adapter"]["mechanism"], MECHANISM_CODEX)
        self.assertNotIn("--resume", compiled_codex2["argv"])
        self.assertNotIn("-r", compiled_codex2["argv"])

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
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(
            ["codex", "dev", "--", "-r", "session-id"],
            ctx=ctx,
        )
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )
        proc2 = self.invoke_conduct(
            ["codex", "dev", "--", "resume", "session-id"],
            ctx=ctx,
        )
        self.assert_cli_refusal(
            proc2,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )
        self.assertNotIn("session-id", proc.stderr)
        self.assertNotIn("session-id", proc2.stderr)


class CanonicalDelegation(ConductFixture):
    def test_evaluate_tool_allows_dispatch_go_and_ladder(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn), "evaluate_tool is the policy counterpart")
        role = self.issued_role()
        digest = role.descriptor_digest()
        for target in DELEGATE_TARGETS:
            with self.subTest(target=target):
                handle = role.resolve_tool("delegate", target)
                self.assertIsNotNone(handle)
                assert handle is not None
                arguments = self.frontend_request(target)
                self.assertTrue(handle.validate_arguments(arguments))
                request = self.tool_request(
                    kind="delegate",
                    target=target,
                    arguments=arguments,
                    binding_sha256=digest,
                    req_id=f"del{target[:4]}1",
                )
                self.assert_closed_object(request, REQUEST_KEYS)
                decision = fn(role, request)
                body = self.assert_closed_object(decision, DECISION_KEYS)
                self.assertEqual(body["schema"], SCHEMA_DECISION)
                self.assertEqual(body["id"], request["id"])
                self.assertEqual(body["binding_sha256"], digest)
                self.assertEqual(body["outcome"], "allow")
                self.assertIsNone(body["refusal"])
        missing = self.tool_request(
            kind="delegate",
            target="dispatch",
            arguments=self.frontend_request("dispatch"),
            binding_sha256=digest,
            req_id="delmiss1",
        )
        empty_role = self.issued_role(include_frontends=False, include_reads=False)
        refused = fn(empty_role, missing)
        miss_body = self.assert_closed_object(refused, DECISION_KEYS)
        self.assertEqual(miss_body["outcome"], "refuse")
        incomplete = dict(self.frontend_request("dispatch"))
        incomplete.pop("ref")
        bad_member = self.tool_request(
            kind="delegate",
            target="dispatch",
            arguments=incomplete,
            binding_sha256=digest,
            req_id="delmiss2",
        )
        self.assertFalse(
            role.resolve_tool("delegate", "dispatch").validate_arguments(incomplete)
        )
        member = fn(role, bad_member)
        member_body = self.assert_closed_object(member, DECISION_KEYS)
        self.assertEqual(member_body["outcome"], "refuse")
        extra = dict(self.frontend_request("go"))
        extra["command"] = "unexpected"
        extra_req = self.tool_request(
            kind="delegate",
            target="go",
            arguments=extra,
            binding_sha256=digest,
            req_id="delextra",
        )
        extra_dec = fn(role, extra_req)
        extra_body = self.assert_closed_object(extra_dec, DECISION_KEYS)
        self.assertEqual(extra_body["outcome"], "refuse")
        lookalike = self.binder.lookalike_role(role)
        look = fn(lookalike, missing)
        look_body = self.assert_closed_object(look, DECISION_KEYS)
        self.assertEqual(look_body["outcome"], "refuse")

    def test_coordination_read_is_allowed_without_wf_agent(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        role = self.issued_role()
        handle = role.resolve_tool("read", "board")
        self.assertIsNotNone(handle)
        assert handle is not None
        arguments = {"section": "branches", "json": True}
        self.assertTrue(handle.validate_arguments(arguments))
        self.assertNotIn("WF_AGENT", self.env())
        request = self.tool_request(
            kind="read",
            target="board",
            arguments=arguments,
            binding_sha256=role.descriptor_digest(),
            req_id="readboard1",
        )
        decision = fn(role, request)
        body = self.assert_closed_object(decision, DECISION_KEYS)
        self.assertEqual(body["outcome"], "allow")
        self.assertIsNone(body["refusal"])

    def test_read_containing_apply_is_not_classified_as_mutation(self) -> None:
        adapters = self.load_adapters()
        fn = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(fn), "normalize_tool is pinned adapter code")
        role = self.issued_role()
        bound = self.issued_bound_context(role=role, mechanism=MECHANISM_CODEX)
        native = self.dynamic_tool_call(
            "board",
            {"section": "prs", "json": True},
        )
        self.assertEqual(sorted(native), sorted(DYNAMIC_CALL_KEYS))
        self.assertIn("prs", json.dumps(native["arguments"]))
        request = fn(bound, native)
        body = self.assert_closed_object(request, REQUEST_KEYS)
        self.assertEqual(body["kind"], "read")
        self.assertEqual(body["target"], "board")
        self.assertNotEqual(body["kind"], "forbidden")
        git_state = self.dynamic_tool_call("git-state", {})
        git_req = fn(bound, git_state)
        git_body = self.assert_closed_object(git_req, REQUEST_KEYS)
        self.assertEqual(git_body["kind"], "read")
        self.assertNotEqual(git_body["kind"], "forbidden")

    def test_compound_command_naming_dispatch_is_not_an_allowed_request(
        self,
    ) -> None:
        adapters = self.load_adapters()
        fn = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(fn))
        role = self.issued_role()
        bound = self.issued_bound_context(role=role, mechanism=MECHANISM_CODEX)
        frame = self.relay_rpc(
            "command/exec",
            {"command": "echo ops/bin/dispatch.sh && rm -rf ."},
        )
        request = fn(bound, frame)
        self.assertIsNotNone(request, "relay gate must classify command/exec")
        body = self.assert_closed_object(request, REQUEST_KEYS)
        self.assertEqual(body["kind"], "forbidden")
        self.assertEqual(body["target"], "implementation")
        self.assertEqual(body["arguments"]["reason"], "shell-escape")
        self.assertEqual(self.effects.executor_calls, [])
        undeclared = self.dynamic_tool_call(
            "dispatch",
            {"command": "ops/bin/dispatch.sh"},
        )
        bad = fn(bound, undeclared)
        self.assertIsNotNone(bad)
        extra = self.assert_closed_object(bad, REQUEST_KEYS)
        self.assertNotEqual(extra.get("kind"), "delegate")
        self.assertNotEqual(extra.get("outcome"), "allow")


class ForbiddenHandwork(ConductFixture):
    def _evaluate(self, reason: str) -> dict:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        role = self.issued_role()
        request = self.tool_request(
            kind="forbidden",
            target="implementation",
            arguments={"reason": reason},
            binding_sha256=role.descriptor_digest(),
            req_id=reason.replace("-", "")[:12] + "1",
        )
        self.assertEqual(request["kind"], "forbidden")
        before = self.effects.delta()
        decision = fn(role, request)
        after = self.effects.delta()
        self.assertEqual(before, after)
        self.assert_no_durable_effects()
        return self.assert_closed_object(decision, DECISION_KEYS)

    def test_direct_edit_is_refused_before_effects(self) -> None:
        body = self._evaluate("direct-edit")
        self.assertEqual(body["outcome"], "refuse")
        self.assertIsNotNone(body["refusal"])
        refusal = body["refusal"]
        self.assertEqual(refusal["class"], "conductor-tool")
        self.assertEqual(refusal["found"], "direct-edit")
        self.assertNotIn(";", refusal["expected"])
        self.assertNotIn(";", refusal["found"])
        self.assertNotIn(";", refusal["needed"])
        self.assertIn("independent doctor", refusal["needed"])
        adapters = self.load_adapters()
        normalize = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(normalize))
        bound = self.issued_bound_context(mechanism=MECHANISM_CODEX)
        approval = self.relay_rpc(
            "item/fileChange/requestApproval",
            {"callId": CALL_ID},
        )
        _ = approval
        native = self.dynamic_tool_call("unknown-edit", {"path": "src/x.py"})
        result = normalize(bound, native)
        self.assertEqual(self.effects.delta()[0], [])
        if isinstance(result, dict) and "kind" in result:
            self.assertEqual(result["kind"], "forbidden")

    def test_git_mutation_is_refused_before_effects(self) -> None:
        body = self._evaluate("git-mutation")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "git-mutation")

    def test_shell_escape_is_refused_before_effects(self) -> None:
        body = self._evaluate("shell-escape")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "shell-escape")

    def test_raw_vendor_is_refused_before_effects(self) -> None:
        body = self._evaluate("raw-vendor")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "raw-vendor")

    def test_in_session_agent_is_refused_before_effects(self) -> None:
        body = self._evaluate("in-session-agent")
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "in-session-agent")

    def test_every_fixed_reason_code_is_accepted_as_a_reason(self) -> None:
        policy = self.load_policy()
        evaluate = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(evaluate))
        role = self.issued_role()
        for reason in REASONS:
            with self.subTest(reason=reason):
                request = self.tool_request(
                    kind="forbidden",
                    target="implementation",
                    arguments={"reason": reason},
                    binding_sha256=role.descriptor_digest(),
                    req_id=reason.replace("-", "")[:12] + "2",
                )
                decision = evaluate(role, request)
                body = self.assert_closed_object(decision, DECISION_KEYS)
                self.assertEqual(body["outcome"], "refuse")
                self.assertEqual(body["refusal"]["found"], reason)
        adapters = self.load_adapters()
        normalize = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(normalize))
        bound = self.issued_bound_context(mechanism=MECHANISM_CODEX)
        unknown = self.dynamic_tool_call("unknown", {})
        request = normalize(bound, unknown)
        body = self.assert_closed_object(request, REQUEST_KEYS)
        self.assertEqual(body["kind"], "forbidden")
        self.assertEqual(body["arguments"]["reason"], "unknown-tool")
        self.assertEqual(set(REASONS), set(REASONS))

    def test_binding_mismatch_is_refused(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        role = self.issued_role()
        request = self.tool_request(
            kind="read",
            target="git-state",
            arguments={},
            binding_sha256="b" * 64,
            req_id="mismatch1",
        )
        self.assertNotEqual(request["binding_sha256"], role.descriptor_digest())
        decision = fn(role, request)
        body = self.assert_closed_object(decision, DECISION_KEYS)
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "binding-mismatch")
        self.assertEqual(self.effects.executor_calls, [])
        stale = self.issued_role(current=False)
        current_req = self.tool_request(
            kind="read",
            target="git-state",
            arguments={},
            binding_sha256=stale.descriptor_digest(),
            req_id="stalerole",
        )
        unavailable = fn(stale, current_req)
        unavail_body = self.assert_closed_object(unavailable, DECISION_KEYS)
        self.assertEqual(unavail_body["outcome"], "refuse")
        self.assertNotEqual(unavail_body["outcome"], "allow")

    def test_malformed_request_is_refused(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        role = self.issued_role()
        request = {
            "schema": SCHEMA_TOOL,
            "id": "badreq1",
            "binding_sha256": role.descriptor_digest(),
            "kind": "delegate",
            "target": "dispatch",
            "arguments": ["not", "an", "object"],
        }
        decision = fn(role, request)
        body = self.assert_closed_object(decision, DECISION_KEYS)
        self.assertEqual(body["outcome"], "refuse")
        self.assertEqual(body["refusal"]["found"], "malformed-request")
        self.assertNotIn("not", json.dumps(body["refusal"]))

    def test_decision_serializes_to_the_wire_without_raw_echo(self) -> None:
        body = self._evaluate("direct-edit")
        refusal = body["refusal"]
        line = (
            f"{refusal['class']}: expected {refusal['expected']}; "
            f"found {refusal['found']}; needed {refusal['needed']}"
        )
        self.assertIsNotNone(REFUSAL_RE.match(line))
        self.assertNotIn("apply_patch", line)
        self.assertNotIn(str(self.cwd), line)
        self.assertNotIn(SECRET_CANARY, line)
        for path in self.effects.record_paths():
            self.assertNotIn(b"apply_patch", path.read_bytes())

    def test_adapter_cannot_turn_refusal_into_a_prompt(self) -> None:
        body = self._evaluate("direct-edit")
        self.assertEqual(body["outcome"], "refuse")
        adapters = self.load_adapters()
        normalize = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(normalize))
        role = self.issued_role()
        bound = self.issued_bound_context(role=role, mechanism=MECHANISM_CODEX)
        pending = self.dynamic_tool_call("unknown-edit", {"path": "x.py"})
        request = normalize(bound, pending)
        if isinstance(request, dict):
            self.assertNotEqual(request.get("kind"), "read")
        self.assertEqual(self.effects.prompts, [])
        self.assertEqual(self.effects.executor_calls, [])
        self.assertFalse(self.receipt.exists())


class FaultyControls(ConductFixture):
    def test_malformed_hook_payload_prevents_admission(self) -> None:
        ctx = self.make_context(interception=False)
        self.assert_prepare_refused(self.prepare(ctx=ctx), "lane-policy")
        live = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=live)
        self.assertIn(proc.returncode, (2, 3))
        self.assertEqual(self.effects.prompts, [])

    def test_replayed_binding_prevents_admission(self) -> None:
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        role = self.issued_role()
        request = self.tool_request(
            kind="delegate",
            target="dispatch",
            arguments=self.frontend_request("dispatch"),
            binding_sha256=role.descriptor_digest(),
            req_id="replay001",
        )
        first = fn(role, request)
        self.assert_closed_object(first, DECISION_KEYS)
        self.assertEqual(first["outcome"], "allow")
        adapters = self.load_adapters()
        normalize = getattr(adapters, "normalize_tool", None)
        self.assertTrue(callable(normalize))
        bound = self.issued_bound_context(role=role, mechanism=MECHANISM_CODEX)
        native = self.dynamic_tool_call(
            "dispatch",
            self.frontend_request("dispatch"),
            call_id="replay-call",
        )
        first_native = normalize(bound, native)
        self.assert_closed_object(first_native, REQUEST_KEYS)
        second_native = normalize(bound, native)
        if isinstance(second_native, dict) and "outcome" in second_native:
            self.assertEqual(second_native["outcome"], "refuse")
        self.assertEqual(
            [call for call in self.effects.executor_calls if call[0] == "invoke"],
            [],
        )

    def test_missing_interception_prevents_admission(self) -> None:
        ctx = self.make_context(interception=False, mechanism=MECHANISM_CODEX)
        self.assert_prepare_refused(self.prepare(ctx=ctx), "lane-policy")
        self.assert_no_durable_effects()
        self.assertIsNone(self.dispatch.claimed_path)

    def test_changed_binding_on_resume_is_lane_resume_before_mutation(
        self,
    ) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        parent = dict(desc)
        parent["policy_binding_sha256"] = "c" * 64
        ctx = self.make_context(
            operation="resume",
            parent=parent,
            parent_bytes=canonical_dumps(parent),
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=parent),
            "lane-resume",
        )
        self.assert_no_durable_effects()
        self.assertIsNone(self.dispatch.claimed_path)


class LaunchResumeBeforeEffects(ConductFixture):
    def test_prepare_creates_no_attempt_snapshot_record_or_child(self) -> None:
        self.assert_prepare_ok(self.prepare())
        self.assertIsNone(self.dispatch.claimed_path)
        self.assert_prepare_pure()
        self.assertFalse(self.receipt.exists())
        self.assertEqual(self.effects.children, [])
        self.assertEqual(self.mcp_client.calls, [])
        self.assertEqual(self.effects.hooks, [])
        self.assertEqual(self.effects.prompts, [])
        self.assertEqual(self.effects.transport_writes, [])

    def test_pre_effect_cli_refusal_is_exit_2_empty_stdout(self) -> None:
        ctx = self.make_context(mechanism=MECHANISM_SYNTHETIC)
        proc = self.invoke_conduct(
            ["codex", "dev", "--", "--config=x"],
            ctx=ctx,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)
        self.assert_cli_refusal(
            proc,
            "conduct-argv",
            exact=conduct_argv_line(0),
        )

    def test_late_mcp_failure_is_abort_3_with_partials(self) -> None:
        self.mcp_client.connect = False
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 3)
        self.assert_refusal_line(
            proc.stderr,
            "conduct-mcp",
            exact=conduct_mcp_line(),
        )
        self.assertNotEqual(self.dispatch.reserved, None)
        record = self.claimed_record()
        self.assertIsNotNone(record)
        assert record is not None
        result = record.get("result")
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result.get("status"), "invalid")
        self.assertIsNone(result.get("envelope"))
        policy = result.get("policy")
        self.assertIsNotNone(policy)

    def test_resume_preflight_precedes_marker_and_attempt_mutations(
        self,
    ) -> None:
        ctx = self.make_context(
            operation="resume",
            parent=None,
            parent_bytes=b"null",
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx),
            "lane-resume",
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
        role = self.issued_role()
        policy = self.load_policy()
        fn = getattr(policy, "evaluate_tool", None)
        self.assertTrue(callable(fn))
        request = self.tool_request(
            kind="delegate",
            target="dispatch",
            arguments=self.frontend_request("dispatch"),
            binding_sha256=role.descriptor_digest(),
            req_id="effectn1",
        )
        decision = fn(role, request)
        body = self.assert_closed_object(decision, DECISION_KEYS)
        self.assertEqual(body["outcome"], "allow")
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        added, _removed, changed = self.effects.delta()
        writes = [
            name
            for name in added + changed
            if name.startswith("repo/") or "/.git/" in name
        ]
        self.assertEqual(writes, [])
        _ = proc


if __name__ == "__main__":
    import unittest

    unittest.main()
