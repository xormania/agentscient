"""Independent startup tests for conduct and prepare_conductor.

Contracts (only): conductor-start-plan.md (CLI forms, descriptor,
connection/onboarding/resume), permission-surface.md and
harness-capabilities.md as cited from that plan. Implementation unread.

A missing tool file is one red (`test_the_conduct_tool_file_is_present`
and `test_the_conduct_bin_file_is_present`). Every other case stages a
copy-tool-bytes stand-in so a missing file is not every test's failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from conduct_test_support import (  # noqa: E402
    ADAPTER_KEYS,
    ADMITTED_EQUALS,
    BIN,
    COMPILED_KEYS,
    DESCRIPTOR_KEYS,
    DISPATCH_ID_RE,
    ID_RE,
    LAUNCH_BINDING_KEYS,
    MCP_KEYS,
    OMISSIONS,
    SCHEMA_LAUNCH,
    SELECTION_KEYS,
    SHA256_RE,
    TOOL,
    V3_TOOLS,
    ConductFixture,
    canonical_digest,
    canonical_dumps,
    sha256_hex,
    unpack_prepare,
)


class Presence(ConductFixture):
    def test_the_conduct_tool_file_is_present(self) -> None:
        self.assertTrue(
            TOOL.is_file(),
            "ops/conductor/tools/conduct.py is the composition owner",
        )

    def test_the_conduct_bin_file_is_present(self) -> None:
        self.assertTrue(
            BIN.is_file(),
            "ops/bin/conduct is the thin CLI owner",
        )


class CliForms(ConductFixture):
    """Four documented forms; optional -- after all positionals."""

    def test_harness_dev_is_an_admitted_form(self) -> None:
        result = self.invoke_conduct(["codex", "dev"])
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["selection"]["profile"], "dev")
        self.assertEqual(body["selection"]["harness"], "codex")
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_harness_prod_is_an_admitted_form(self) -> None:
        selection = self.selection(profile="prod")
        result = self.prepare(selection=selection)
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["selection"]["profile"], "prod")
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_harness_test_is_an_admitted_form(self) -> None:
        proc = self.run_cli(["codex", "test", "--", "--quiet"])
        self.assertNotEqual(
            (proc.returncode, proc.stdout, proc.stderr.strip()),
            (0, "", ""),
            "unprofiled test must not be a silent no-op",
        )

    def test_harness_profile_test_is_an_admitted_form(self) -> None:
        proc = self.run_cli(["codex", "docs", "test"])
        # Additional configured profile uses the same path. A stub's
        # empty success is not admission.
        self.assertNotEqual(proc.stdout.strip(), "")
        self.assertIn(proc.returncode, (0, 2, 3))

    def test_double_dash_may_carry_zero_tokens(self) -> None:
        result = self.prepare(tokens=[])
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["forwarded_tokens"], [])
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_tokens_after_double_dash_are_forwarded_in_order(self) -> None:
        result = self.prepare(tokens=list(ADMITTED_EQUALS))
        desc, _compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["forwarded_tokens"], ADMITTED_EQUALS)

    def test_no_positional_is_parsed_after_double_dash(self) -> None:
        proc = self.run_cli(["codex", "dev", "--", "prod"])
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_unprofiled_test_validates_every_profile_before_effects(self) -> None:
        before = list(self.effects.delta())
        proc = self.run_cli(["grok", "test", "--", "--config=x"])
        self.assert_no_durable_effects()
        after = list(self.effects.delta())
        self.assertEqual(before, after)
        self.assert_cli_refusal(proc, "conduct-argv")

    def test_missing_harness_is_a_pre_effect_refusal(self) -> None:
        proc = self.run_cli(["dev"])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.strip())
        self.assert_no_durable_effects()

    def test_bin_and_tool_share_the_four_forms(self) -> None:
        if not BIN.is_file():
            self.fail("ops/bin/conduct is absent")
        proc = self.run_bin(["codex", "dev", "--"])
        self.assertIn(proc.returncode, (0, 2, 3))
        self.assertNotEqual(
            (proc.returncode, proc.stdout, proc.stderr),
            (0, "", ""),
            "bin/conduct must not be a silent no-op",
        )


class SelectionAxes(ConductFixture):
    """Harness, model, effort, role, job_role and profile stay distinct."""

    def test_returned_selection_equals_the_caller_bytes(self) -> None:
        selection = self.selection(
            harness="claude",
            model="fixture-model",
            effort="high",
            profile="prod",
        )
        result = self.prepare(selection=selection)
        desc, _compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["selection"], selection)
        self.assertEqual(tuple(body["selection"]), SELECTION_KEYS)

    def test_harness_axis_does_not_imply_profile(self) -> None:
        selection = self.selection(harness="grok", profile="prod")
        result = self.prepare(selection=selection)
        desc, _compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["selection"]["harness"], "grok")
        self.assertEqual(body["selection"]["profile"], "prod")

    def test_model_is_the_explicit_caller_token(self) -> None:
        selection = self.selection(model="configured-model-token")
        result = self.prepare(selection=selection)
        desc, _compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["selection"]["model"], "configured-model-token")
        self.assertNotEqual(body["selection"]["model"], selection["harness"])

    def test_effort_null_is_distinct_from_a_nonempty_string(self) -> None:
        none = self.prepare(selection=self.selection(effort=None))
        high = self.prepare(selection=self.selection(effort="high"))
        desc_none, _ = unpack_prepare(none)
        desc_high, _ = unpack_prepare(high)
        a = self.assert_closed_object(desc_none, DESCRIPTOR_KEYS)
        b = self.assert_closed_object(desc_high, DESCRIPTOR_KEYS)
        self.assertIsNone(a["selection"]["effort"])
        self.assertEqual(b["selection"]["effort"], "high")
        self.assertNotEqual(
            canonical_digest(a["selection"]),
            canonical_digest(b["selection"]),
        )

    def test_role_must_be_conductor(self) -> None:
        selection = self.selection()
        selection["role"] = "worker"
        self.assert_prepare_refused(self.prepare(selection=selection))

    def test_job_role_must_be_null(self) -> None:
        selection = self.selection()
        selection["job_role"] = "write"
        self.assert_prepare_refused(self.prepare(selection=selection))

    def test_profile_must_exist_in_policy_and_discovery(self) -> None:
        selection = self.selection(profile="no-such-profile")
        self.assert_prepare_refused(self.prepare(selection=selection))

    def test_additional_configured_profile_uses_the_same_path(self) -> None:
        selection = self.selection(profile="docs")
        result = self.prepare(selection=selection)
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["selection"]["profile"], "docs")
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_daybreak_is_not_promoted_from_role_memory(self) -> None:
        selection = self.selection(model="gpt-daybreak-blue-latest")
        desc, _compiled = self.assert_prepare_ok(
            self.prepare(selection=selection)
        )
        self.assertEqual(desc["selection"]["role"], "conductor")
        self.assertIsNone(desc["selection"]["job_role"])
        self.assertEqual(
            desc["selection"]["model"],
            "gpt-daybreak-blue-latest",
        )

    def test_cond_axis_n1_each_axis_conflict_refuses_without_substitution(
        self,
    ) -> None:
        base = self.selection()
        conflicts = {
            "harness": "claude",
            "model": "other-model",
            "role": "worker",
            "job_role": "read",
            "profile": "prod",
        }
        ctx = self.make_context(selection=base)
        ctx.binding["selection"] = dict(base)
        for axis, value in conflicts.items():
            with self.subTest(axis=axis):
                selection = dict(base)
                selection[axis] = value
                result = self.prepare(selection=selection, ctx=ctx)
                self.assert_prepare_refused(result)


class DescriptorValidation(ConductFixture):
    def test_full_synthetic_descriptor_round_trip(self) -> None:
        selection = self.selection()
        tokens = list(ADMITTED_EQUALS)
        result = self.prepare(selection=selection, tokens=tokens)
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["schema"], SCHEMA_LAUNCH)
        self.assertRegex(body["launch_id"], DISPATCH_ID_RE)
        self.assertEqual(body["operation"], "launch")
        self.assertIsNone(body["resume"])
        self.assertEqual(body["forwarded_tokens"], tokens)
        self.assertRegex(body["custody_sha256"], SHA256_RE)
        self.assertRegex(body["policy_binding_sha256"], SHA256_RE)
        self.assert_closed_object(body["adapter"], ADAPTER_KEYS)
        self.assert_closed_object(body["mcp"], MCP_KEYS)
        self.assertEqual(
            body["mcp"]["config_sha256"],
            body["discovery"]["config_sha256"],
        )
        self.assertEqual(
            body["discovery"]["config_sha256"],
            self.config_sha256,
        )
        compiled_body = self.assert_closed_object(compiled, COMPILED_KEYS)
        self.assert_closed_object(
            compiled_body["binding"],
            LAUNCH_BINDING_KEYS,
        )
        self.assertEqual(compiled_body["binding"]["operation"], "launch")
        self.assertGreaterEqual(len(compiled_body["argv"]), 1)
        self.assertEqual(
            compiled_body["argv"][0],
            str(self.executable),
        )
        raw = canonical_dumps(body)
        self.assertLessEqual(len(raw), 65536)
        self.assertEqual(raw.decode("utf-8"), json.dumps(
            json.loads(raw),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ))

    def test_launch_id_is_reserved_in_memory_before_admission(self) -> None:
        result = self.prepare()
        desc, _compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(body["launch_id"], self.dispatch.reserved)
        self.assertIsNone(self.dispatch.claimed_path)
        self.assert_no_durable_effects()

    def test_unknown_key_is_conduct_config(self) -> None:
        proc = self.run_cli(["codex", "dev"])
        # Unknown-key coverage is on serialized transport. A successful
        # prepare must still reject a parent/inherited blob with extras.
        parent = self.expected_descriptor(
            self.selection(),
            [],
            "launch",
            "20260906T120000Z-conduct-codex-a1b2c3",
        )
        parent["extra"] = "nope"
        ctx = self.make_context(operation="resume", parent=parent)
        result = self.prepare(
            operation="resume",
            ctx=ctx,
            parent=parent,
        )
        self.assert_prepare_refused(result)
        if proc.returncode == 2:
            self.assertEqual(proc.stdout, "")

    def test_duplicate_key_in_serialized_descriptor_is_conduct_config(
        self,
    ) -> None:
        selection = self.selection()
        launch_id = "20260906T120000Z-conduct-codex-a1b2c3"
        parent = self.expected_descriptor(
            selection, [], "launch", launch_id
        )
        raw = canonical_dumps(parent)
        # Duplicate "schema" key: JSON object that the transport must
        # refuse before json.loads silently keeps one value.
        injected = raw.replace(
            b'"schema":"conductor-launch/1"',
            b'"schema":"conductor-launch/1","schema":"conductor-launch/1"',
            1,
        )
        self.assertIn(b'"schema"', injected)
        self.assertGreater(injected.count(b'"schema"'), raw.count(b'"schema"'))
        ctx = self.make_context(operation="resume", parent=parent)
        ctx.parent_descriptor_bytes = injected
        result = self.prepare(
            operation="resume",
            ctx=ctx,
            parent=parent,
        )
        self.assert_prepare_refused(result)

    def test_missing_null_resume_on_launch_is_conduct_config(self) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        self.assertIn("resume", desc)
        self.assertIsNone(desc["resume"])
        dropped = dict(desc)
        del dropped["resume"]
        self.assertNotIn("resume", dropped)
        ctx = self.make_context(operation="resume", parent=dropped)
        retry = self.prepare(operation="resume", ctx=ctx, parent=dropped)
        self.assert_prepare_refused(retry)

    def test_boolean_is_not_integer_in_anchors(self) -> None:
        ctx = self.make_context()
        ctx.boot["anchors"] = [
            {"id": "repo", "device": True, "inode": 1},
        ]
        self.assert_prepare_refused(self.prepare(ctx=ctx))

    def test_control_character_in_string_refuses(self) -> None:
        selection = self.selection(model="fixture\nmodel")
        self.assert_prepare_refused(self.prepare(selection=selection))

    def test_non_finite_number_refuses(self) -> None:
        ctx = self.make_context()
        ctx.boot["anchors"] = [
            {"id": "repo", "device": float("nan"), "inode": 1},
        ]
        self.assert_prepare_refused(self.prepare(ctx=ctx))

    def test_serialized_descriptor_over_65536_bytes_refuses(self) -> None:
        pad = "a" * 65537
        blob = json.dumps({"schema": SCHEMA_LAUNCH, "pad": pad}).encode(
            "utf-8"
        )
        self.assertGreater(len(blob), 65536)
        ctx = self.make_context(operation="resume")
        ctx.parent_descriptor_bytes = blob
        self.assert_prepare_refused(self.prepare(operation="resume", ctx=ctx))
        self.assert_no_durable_effects()

    def test_nesting_deeper_than_32_refuses(self) -> None:
        node: object = "leaf"
        for _ in range(33):
            node = {"n": node}
        blob = json.dumps(node).encode("utf-8")
        ctx = self.make_context(operation="resume")
        ctx.parent_descriptor_bytes = blob
        self.assert_prepare_refused(self.prepare(operation="resume", ctx=ctx))

    def test_adapter_fields_equal_capability_identity_fields(self) -> None:
        result = self.prepare()
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        compiled_body = self.assert_closed_object(compiled, COMPILED_KEYS)
        cap = compiled_body["capability"]
        self.assertEqual(body["adapter"]["revision"], cap["adapter"]["revision"])
        self.assertEqual(
            body["adapter"]["mechanism"],
            cap["adapter"]["mechanism"],
        )
        self.assertEqual(
            body["adapter"]["grammar_sha256"],
            cap["adapter"]["grammar_sha256"],
        )
        self.assertEqual(
            body["adapter"]["normalizer_sha256"],
            cap["adapter"]["normalizer_sha256"],
        )
        self.assertEqual(
            body["adapter"]["executable_sha256"],
            cap["harness"]["executable"]["sha256"],
        )
        self.assertEqual(
            body["adapter"]["config_sha256"],
            cap["adapter"]["config_sha256"],
        )
        self.assertEqual(body["mcp"], cap["mcp"])
        self.assertEqual(cap["role"], "conductor")

    def test_launch_id_harness_matches_selection(self) -> None:
        selection = self.selection(harness="claude")
        self.dispatch.harness = "claude"
        result = self.prepare(selection=selection)
        desc, _compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertIn("-conduct-claude-", body["launch_id"])
        self.assertTrue(ID_RE.match(body["selection"]["harness"]))


class UntrustedDigests(ConductFixture):
    def test_matching_digest_from_candidate_is_not_trusted_origin(self) -> None:
        impostor = b"not-the-held-custody-bytes\n"
        self.assertNotEqual(sha256_hex(impostor), self.custody_sha256)
        ctx = self.make_context(candidate_custody=impostor)
        ctx.custody_anchor = None
        ctx.claimed_custody_sha256 = self.custody_sha256
        self.assert_prepare_refused(self.prepare(ctx=ctx))
        self.assert_no_durable_effects()

    def test_held_anchor_equality_is_required_not_just_the_hex(self) -> None:
        ctx = self.make_context()
        other = b"trusted-caller-custody-anchor-v1\n"
        self.assertEqual(sha256_hex(other), self.custody_sha256)
        ctx.custody_anchor = other
        # Same bytes from the held caller are equality, not a candidate
        # path. Swapping the provider to a candidate-supplied handle
        # while keeping the hex must still refuse.
        ctx.candidate_supplied_custody = True
        ctx.custody_anchor_source = "candidate"
        self.assert_prepare_refused(self.prepare(ctx=ctx))

    def test_descriptor_digest_does_not_prove_binding_origin(self) -> None:
        desc, _compiled = self.assert_prepare_ok(
            self.prepare(selection=self.selection())
        )
        forged = dict(desc)
        forged["policy_binding_sha256"] = desc["policy_binding_sha256"]
        ctx = self.make_context(operation="resume", parent=forged)
        ctx.binding = None
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=forged)
        )


class McpConnection(ConductFixture):
    def test_actual_client_must_initialize_list_and_call_lane_start(
        self,
    ) -> None:
        self.mcp_client.connect = True
        result = self.invoke_conduct(["codex", "dev"])
        desc, compiled = unpack_prepare(result)
        self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assert_closed_object(compiled, COMPILED_KEYS)
        self.assertIn("initialize", self.mcp_client.calls)
        self.assertIn("tools/list", self.mcp_client.calls)
        self.assertIn(
            ("tools/call", "lane_start", {"profile": "dev"}),
            self.mcp_client.calls,
        )

    def test_separate_server_query_is_not_connection_proof(self) -> None:
        self.mcp_client.connect = False
        receipt = self.mcp_server.query("lane_start", {"profile": "dev"})
        self.assertEqual(receipt["schema"], "agentscient.lane/v1")
        self.assertTrue(self.mcp_server.queries)
        result = self.invoke_conduct(["codex", "dev"])
        self.assert_prepare_refused(result)
        self.assertEqual(self.mcp_client.calls, [])

    def test_server_self_reported_digest_is_not_connection_proof(self) -> None:
        self.mcp_client.connect = False
        ctx = self.make_context()
        ctx.server_self_digest = self.mcp_server.self_digest
        outcome = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_prepare_refused(outcome)

    def test_configured_server_entry_alone_is_not_connection_proof(
        self,
    ) -> None:
        self.mcp_client.connect = False
        ctx = self.make_context()
        ctx.configured_server = {
            "command": str(self.executable),
            "config_sha256": self.config_sha256,
        }
        outcome = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_prepare_refused(outcome)

    def test_missing_connection_is_conduct_mcp(self) -> None:
        self.mcp_client.connect = False
        proc = self.run_cli(["codex", "dev"])
        if proc.returncode == 3:
            self.assertTrue(proc.stderr.strip())
            self.assert_refusal_line(proc.stderr, "conduct-mcp")
            return
        if proc.returncode == 2:
            self.assert_cli_refusal(proc, "conduct-mcp")
            return
        outcome = self.invoke_conduct(["codex", "dev"])
        self.assert_prepare_refused(outcome)

    def test_invalid_params_does_not_establish_server_absence(self) -> None:
        self.mcp_client.invalid_params = True
        self.mcp_client.connect = True
        outcome = self.invoke_conduct(["codex", "dev"])
        listed = self.mcp_client.tools_list()
        self.assertIsInstance(listed, dict)
        self.assertIn("initialize", self.mcp_client.calls)
        self.assertIn("tools/list", self.mcp_client.calls)
        self.assertFalse(
            (self.home / ".claude" / "settings.json").exists()
        )
        self.assert_prepare_ok(outcome)

    def test_catalogue_has_eleven_v3_tools(self) -> None:
        self.assertEqual(len(self.catalogue["tools"]), V3_TOOLS)
        result = self.prepare()
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertEqual(
            body["mcp"]["catalogue_sha256"],
            canonical_digest(self.catalogue),
        )
        self.assert_closed_object(compiled, COMPILED_KEYS)


class Onboarding(ConductFixture):
    def test_partial_valid_discovery_onboards_without_inventing_a_handoff(
        self,
    ) -> None:
        self.envelope = self.make_envelope("dev", unavailable=True)
        self.mcp_client.envelope = self.envelope
        outcome = self.invoke_conduct(["codex", "dev"])
        desc, compiled = unpack_prepare(outcome)
        self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assert_closed_object(compiled, COMPILED_KEYS)
        packet = self.mcp_client.envelope
        self.assertEqual(packet["data"]["handoffs"]["selected_key"], None)
        self.assertIn(OMISSIONS[0], packet["data"]["omissions"])
        self.assertNotIn("path hint", json.dumps(packet))
        self.assertNotIn(str(self.repo_root), json.dumps(packet["data"]))

    def test_onboarding_does_not_select_by_filename_or_time(self) -> None:
        self.envelope = self.make_envelope("dev", unavailable=True)
        self.envelope["data"]["handoffs"]["selection"] = "unknown"
        self.mcp_client.envelope = self.envelope
        outcome = self.invoke_conduct(["codex", "dev"])
        desc, _compiled = unpack_prepare(outcome)
        self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assertIsNone(
            self.mcp_client.envelope["data"]["handoffs"]["selected_key"]
        )
        self.assertFalse(
            any(
                isinstance(item, tuple)
                and item[0] == "tools/call"
                and "path" in json.dumps(item[2])
                for item in self.mcp_client.calls
            )
        )

    def test_dev_prod_and_docs_onboard_without_path_hints(self) -> None:
        for profile in ("dev", "prod", "docs"):
            with self.subTest(profile=profile):
                selection = self.selection(profile=profile)
                envelope = self.make_envelope(profile, unavailable=True)
                self.mcp_client.envelope = envelope
                result = self.prepare(selection=selection)
                desc, compiled = unpack_prepare(result)
                body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
                self.assertEqual(body["selection"]["profile"], profile)
                self.assert_closed_object(compiled, COMPILED_KEYS)
                dumped = json.dumps(envelope)
                self.assertNotIn("/home/", dumped)
                self.assertNotIn("enter a path", dumped.lower())

    def test_resume_reverifies_the_actual_client_connection(self) -> None:
        first = self.prepare()
        desc, compiled = unpack_prepare(first)
        parent = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assert_closed_object(compiled, COMPILED_KEYS)
        self.mcp_client.calls.clear()
        ctx = self.make_context(operation="resume", parent=parent)
        retry = self.prepare(operation="resume", ctx=ctx, parent=parent)
        again, compiled2 = unpack_prepare(retry)
        body = self.assert_closed_object(again, DESCRIPTOR_KEYS)
        self.assertEqual(body["launch_id"], parent["launch_id"])
        self.assertEqual(body["operation"], "resume")
        self.assertIsNotNone(body["resume"])
        self.assertEqual(
            body["resume"]["parent_descriptor_sha256"],
            canonical_digest(parent),
        )
        self.assert_closed_object(compiled2, COMPILED_KEYS)
        self.assertEqual(compiled2["binding"]["operation"], "resume")
        self.assertEqual(
            compiled2["binding"]["invariant_sha256"],
            compiled["binding"]["invariant_sha256"],
        )
        self.assertNotEqual(
            compiled2["binding"]["argv_sha256"],
            compiled["binding"]["argv_sha256"],
        )

    def test_mismatched_record_descriptor_binding_refuses_before_effects(
        self,
    ) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        parent = dict(desc)
        parent["launch_id"] = "20260906T120000Z-conduct-codex-ffffff"
        self.assertNotEqual(parent["launch_id"], desc["launch_id"])
        ctx = self.make_context(operation="resume", parent=parent)
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=parent)
        )
        self.assert_no_durable_effects()

    def test_changed_discovery_content_does_not_change_bound_profile(
        self,
    ) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        ctx = self.make_context(operation="resume", parent=desc)
        ctx.boot["config_bytes"] = canonical_dumps(
            self.make_v3_config(extra_profile=False)
        )
        again, _compiled2 = self.assert_prepare_ok(
            self.prepare(operation="resume", ctx=ctx, parent=desc)
        )
        self.assertEqual(again["selection"]["profile"], "dev")
        self.assertNotEqual(
            again["discovery"]["config_sha256"],
            desc["discovery"]["config_sha256"],
        )

    def test_unbound_legacy_session_cannot_resume_in_place(self) -> None:
        ctx = self.make_context(operation="resume")
        ctx.parent_descriptor = None
        ctx.transport["session_binding"] = {"legacy": True}
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx)
        )
        self.assert_no_durable_effects()


if __name__ == "__main__":
    import unittest

    unittest.main()
