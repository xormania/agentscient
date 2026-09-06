"""Independent startup tests for conduct and prepare_conductor.

Contracts (only): conductor-start-plan.md (CLI forms, inherited bootstrap,
prepare packaging, connection/onboarding/resume), permission-surface.md and
harness-capabilities.md as cited from that plan. Implementation unread.

A missing tool file is one red (`test_the_conduct_tool_file_is_present`
and `test_the_conduct_bin_file_is_present`). Every other case invokes the
held runtime path, or a copy-tool-bytes stand-in so a missing file is not
every test's failure.
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
    BOOTSTRAP_SLOTS,
    COMPILED_KEYS,
    CONFIG_REASONS,
    DESCRIPTOR_KEYS,
    DISPATCH_ID_RE,
    ID_RE,
    LAUNCH_BINDING_KEYS,
    MCP_KEYS,
    MECHANISM_CODEX,
    MECHANISM_SYNTHETIC,
    NESTING_MAX,
    OMISSIONS,
    PREPARE_KEYS,
    PROFILES,
    SCHEMA_DIAGNOSTIC,
    SCHEMA_LAUNCH,
    SELECTION_KEYS,
    SHA256_RE,
    TOOL,
    V3_TOOL_NAMES,
    V3_TOOL_SCHEMAS,
    V3_TOOLS,
    ConductFixture,
    canonical_digest,
    canonical_dumps,
    conduct_config_line,
    conduct_mcp_line,
    json_nesting,
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
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = self.retained_descriptor(proc)
        self.assertEqual(body["selection"]["profile"], "dev")
        self.assertEqual(body["selection"]["harness"], "codex")
        self.assertEqual(sorted(body["selection"]), sorted(SELECTION_KEYS))
        self.assertIn("effort", body["selection"])
        self.assertTrue(self.mcp_client.observations)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
        )

    def test_harness_prod_is_an_admitted_form(self) -> None:
        selection = self.selection(profile="prod")
        ctx = self.make_context(selection=selection, mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "prod"], ctx=ctx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = self.retained_descriptor(proc)
        self.assertEqual(body["selection"]["profile"], "prod")
        prepared = self.prepare(selection=selection, mechanism=MECHANISM_CODEX)
        desc, compiled = self.assert_prepare_ok(prepared)
        self.assertEqual(desc["selection"]["profile"], "prod")
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_double_dash_may_carry_zero_tokens(self) -> None:
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev", "--"], ctx=ctx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = self.retained_descriptor(proc)
        self.assertEqual(body["forwarded_tokens"], [])
        prepared = self.prepare(tokens=[], mechanism=MECHANISM_SYNTHETIC)
        desc, compiled = self.assert_prepare_ok(prepared)
        self.assertEqual(desc["forwarded_tokens"], [])
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_tokens_after_double_dash_are_forwarded_in_order(self) -> None:
        ctx = self.make_context(mechanism=MECHANISM_SYNTHETIC)
        proc = self.invoke_conduct(
            ["codex", "dev", "--", *ADMITTED_EQUALS],
            ctx=ctx,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = self.retained_descriptor(proc)
        self.assertEqual(body["forwarded_tokens"], ADMITTED_EQUALS)
        prepared = self.prepare(
            tokens=list(ADMITTED_EQUALS),
            mechanism=MECHANISM_SYNTHETIC,
        )
        desc, compiled = self.assert_prepare_ok(prepared)
        self.assertEqual(desc["forwarded_tokens"], ADMITTED_EQUALS)
        self.assertEqual(compiled["argv"][-2:], ADMITTED_EQUALS)

    def test_harness_test_is_an_admitted_form(self) -> None:
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "test"], ctx=ctx)
        self.assertNotEqual(proc.returncode, 2)
        self.assertTrue(proc.stdout.strip(), proc.stderr)
        self.assert_diagnostic_report(proc.stdout, profiles=PROFILES)

    def test_harness_profile_test_is_an_admitted_form(self) -> None:
        selection = self.selection(profile="docs")
        ctx = self.make_context(selection=selection, mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "docs", "test"], ctx=ctx)
        self.assertTrue(proc.stdout.strip())
        body = json.loads(proc.stdout)
        self.assertEqual(body["schema"], SCHEMA_DIAGNOSTIC)
        self.assert_diagnostic_report(proc.stdout, profiles=("docs",))

    def test_no_positional_is_parsed_after_double_dash(self) -> None:
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev", "--", "prod"], ctx=ctx)
        self.assert_cli_refusal(proc, "conduct-argv", found="invalid token at index 0")
        self.assert_no_durable_effects()

    def test_unprofiled_test_validates_every_profile_before_effects(self) -> None:
        ctx = self.make_context(
            selection=self.selection(profile="docs"),
            mechanism=MECHANISM_CODEX,
            interception=False,
        )
        before = list(self.effects.delta())
        proc = self.invoke_conduct(["codex", "test"], ctx=ctx)
        after = list(self.effects.delta())
        self.assertEqual(before, after)
        self.assert_no_durable_effects()
        self.assertIn(proc.returncode, (1, 2))
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.strip())
        self.assertEqual(self.effects.hooks, [])
        self.assertEqual(self.mcp_client.calls, [])

    def test_missing_harness_is_a_pre_effect_refusal(self) -> None:
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.strip())
        self.assert_no_durable_effects()

    def test_bin_and_tool_share_the_four_forms(self) -> None:
        if not BIN.is_file():
            self.fail("ops/bin/conduct is absent")
        forms = (
            ["codex", "dev"],
            ["codex", "prod"],
            ["codex", "test"],
            ["codex", "docs", "test"],
        )
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        for form in forms:
            with self.subTest(form=form):
                tool_proc = self.run_cli(form, ctx=ctx)
                bin_proc = self.run_bin(form, ctx=ctx)
                self.assertEqual(tool_proc.returncode, bin_proc.returncode)
                self.assertEqual(tool_proc.stdout, bin_proc.stdout)
                self.assertEqual(tool_proc.stderr, bin_proc.stderr)
        missing = self.run_cli(["codex", "dev"], inherit=False)
        self.assert_cli_refusal(
            missing,
            "conduct-config",
            exact=conduct_config_line("bootstrap-missing"),
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
        self.assertEqual(sorted(selection), sorted(SELECTION_KEYS))
        result = self.prepare(selection=selection)
        desc, _compiled = self.assert_prepare_ok(result)
        self.assert_selection_bytes(desc, selection)

    def test_harness_axis_does_not_imply_profile(self) -> None:
        selection = self.selection(harness="grok", profile="prod")
        result = self.prepare(selection=selection)
        desc, _compiled = self.assert_prepare_ok(result)
        self.assertEqual(desc["selection"]["harness"], "grok")
        self.assertEqual(desc["selection"]["profile"], "prod")
        self.assertIn("effort", desc["selection"])

    def test_model_is_the_explicit_caller_token(self) -> None:
        selection = self.selection(model="configured-model-token")
        result = self.prepare(selection=selection)
        desc, _compiled = self.assert_prepare_ok(result)
        self.assertEqual(desc["selection"]["model"], "configured-model-token")
        self.assertNotEqual(desc["selection"]["model"], selection["harness"])

    def test_effort_null_is_distinct_from_a_nonempty_string(self) -> None:
        none = self.prepare(selection=self.selection(effort=None))
        high = self.prepare(selection=self.selection(effort="high"))
        a, _ = self.assert_prepare_ok(none)
        b, _ = self.assert_prepare_ok(high)
        self.assertIsNone(a["selection"]["effort"])
        self.assertEqual(b["selection"]["effort"], "high")
        self.assertNotEqual(
            canonical_digest(a["selection"]),
            canonical_digest(b["selection"]),
        )
        self.assertEqual(sorted(a["selection"]), sorted(SELECTION_KEYS))
        self.assertEqual(sorted(b["selection"]), sorted(SELECTION_KEYS))

    def test_role_must_be_conductor(self) -> None:
        selection = self.selection()
        selection["role"] = "worker"
        self.assert_prepare_refused(
            self.prepare(selection=selection),
            "lane-policy",
        )

    def test_job_role_must_be_null(self) -> None:
        selection = self.selection()
        selection["job_role"] = "write"
        self.assert_prepare_refused(
            self.prepare(selection=selection),
            "lane-policy",
        )

    def test_profile_must_exist_in_policy_and_discovery(self) -> None:
        selection = self.selection(profile="no-such-profile")
        self.assert_prepare_refused(
            self.prepare(selection=selection),
            "lane-profile",
        )

    def test_additional_configured_profile_uses_the_same_path(self) -> None:
        selection = self.selection(profile="docs")
        result = self.prepare(selection=selection)
        desc, compiled = self.assert_prepare_ok(result)
        self.assertEqual(desc["selection"]["profile"], "docs")
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_daybreak_is_not_promoted_from_role_memory(self) -> None:
        selection = self.selection(model="gpt-daybreak-blue-latest")
        desc, _compiled = self.assert_prepare_ok(self.prepare(selection=selection))
        self.assertEqual(desc["selection"]["role"], "conductor")
        self.assertIsNone(desc["selection"]["job_role"])
        self.assertEqual(
            desc["selection"]["model"],
            "gpt-daybreak-blue-latest",
        )
        self.assertIn("effort", desc["selection"])

    def test_cond_axis_n1_each_axis_conflict_refuses_without_substitution(
        self,
    ) -> None:
        base = self.selection(effort=None)
        self.assertEqual(sorted(base), sorted(SELECTION_KEYS))
        conflicts = {
            "harness": "claude",
            "model": "other-model",
            "effort": "high",
            "role": "worker",
            "job_role": "read",
            "profile": "prod",
        }
        self.assertEqual(sorted(conflicts), sorted(SELECTION_KEYS))
        ctx = self.make_context(selection=base)
        for axis, value in conflicts.items():
            with self.subTest(axis=axis):
                selection = dict(base)
                selection[axis] = value
                result = self.prepare(selection=selection, ctx=ctx)
                self.assert_prepare_refused(result, "lane-policy")


class DescriptorValidation(ConductFixture):
    def test_full_synthetic_descriptor_round_trip(self) -> None:
        selection = self.selection()
        tokens = list(ADMITTED_EQUALS)
        result = self.prepare(selection=selection, tokens=tokens)
        desc, compiled = self.assert_prepare_ok(result)
        self.assertEqual(desc["schema"], SCHEMA_LAUNCH)
        self.assertRegex(desc["launch_id"], DISPATCH_ID_RE)
        self.assertEqual(desc["operation"], "launch")
        self.assertIsNone(desc["resume"])
        self.assertEqual(desc["forwarded_tokens"], tokens)
        self.assertRegex(desc["custody_sha256"], SHA256_RE)
        self.assertRegex(desc["policy_binding_sha256"], SHA256_RE)
        self.assert_closed_object(desc["adapter"], ADAPTER_KEYS)
        self.assert_closed_object(desc["mcp"], MCP_KEYS)
        self.assertEqual(
            desc["mcp"]["config_sha256"],
            desc["discovery"]["config_sha256"],
        )
        self.assertEqual(
            desc["discovery"]["config_sha256"],
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
        raw = canonical_dumps(desc)
        self.assertLessEqual(len(raw), 65536)
        self.assertEqual(
            raw.decode("utf-8"),
            json.dumps(
                json.loads(raw),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        )

    def test_launch_id_is_reserved_in_memory_before_admission(self) -> None:
        result = self.prepare()
        desc, _compiled = self.assert_prepare_ok(result)
        self.assertEqual(desc["launch_id"], self.dispatch.reserved)
        self.assertIsNone(self.dispatch.claimed_path)
        self.assert_no_durable_effects()

    def test_unknown_key_is_conduct_config(self) -> None:
        parent = self.expected_descriptor(
            self.selection(),
            [],
            "launch",
            "20260906T120000Z-conduct-codex-a1b2c3",
        )
        parent["extra"] = "nope"
        ctx = self.make_context(
            operation="resume",
            parent=parent,
            parent_bytes=canonical_dumps(parent),
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=parent),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )
        malformed = self.make_context(slot_kinds={"custody.json": "writable"})
        self.assert_prepare_refused(
            self.prepare(ctx=malformed),
            "conduct-config",
            exact=conduct_config_line("bootstrap-invalid"),
        )

    def test_duplicate_key_in_serialized_descriptor_is_conduct_config(
        self,
    ) -> None:
        selection = self.selection()
        launch_id = "20260906T120000Z-conduct-codex-a1b2c3"
        parent = self.expected_descriptor(selection, [], "launch", launch_id)
        raw = canonical_dumps(parent)
        injected = raw.replace(
            b'"schema":"conductor-launch/1"',
            b'"schema":"conductor-launch/1","schema":"conductor-launch/1"',
            1,
        )
        self.assertIn(b'"schema"', injected)
        self.assertGreater(injected.count(b'"schema"'), raw.count(b'"schema"'))
        ctx = self.make_context(
            operation="resume",
            parent=parent,
            parent_bytes=injected,
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=parent),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )

    def test_missing_null_resume_on_launch_is_conduct_config(self) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        self.assertIn("resume", desc)
        self.assertIsNone(desc["resume"])
        dropped = dict(desc)
        del dropped["resume"]
        self.assertNotIn("resume", dropped)
        ctx = self.make_context(
            operation="resume",
            parent=dropped,
            parent_bytes=canonical_dumps(dropped),
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=dropped),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )

    def test_boolean_is_not_integer_in_anchors(self) -> None:
        ctx = self.make_context(
            discovery_anchors=[{"id": "repo", "device": True, "inode": 1}],
        )
        self.assert_prepare_refused(
            self.prepare(ctx=ctx),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )

    def test_control_character_in_string_refuses(self) -> None:
        selection = self.selection(model="fixture\nmodel")
        self.assert_prepare_refused(
            self.prepare(selection=selection),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )

    def test_non_finite_number_refuses(self) -> None:
        ctx = self.make_context(
            discovery_anchors=[
                {"id": "repo", "device": float("nan"), "inode": 1},
            ],
        )
        self.assert_prepare_refused(
            self.prepare(ctx=ctx),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )

    def test_serialized_descriptor_over_65536_bytes_refuses(self) -> None:
        pad = "a" * 65537
        blob = json.dumps({"schema": SCHEMA_LAUNCH, "pad": pad}).encode("utf-8")
        self.assertGreater(len(blob), 65536)
        ctx = self.make_context(operation="resume", parent_bytes=blob)
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )

    def test_nesting_deeper_than_32_refuses(self) -> None:
        node: object = "leaf"
        for _ in range(NESTING_MAX + 1):
            node = {"n": node}
        blob = json.dumps(node).encode("utf-8")
        self.assertGreater(json_nesting(node), NESTING_MAX)
        ctx = self.make_context(operation="resume", parent_bytes=blob)
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx),
            "conduct-config",
            exact=conduct_config_line("descriptor-invalid"),
        )

    def test_adapter_fields_equal_capability_identity_fields(self) -> None:
        result = self.prepare()
        desc, compiled = self.assert_prepare_ok(result)
        cap = compiled["capability"]
        self.assertEqual(desc["adapter"]["revision"], cap["adapter"]["revision"])
        self.assertEqual(
            desc["adapter"]["mechanism"],
            cap["adapter"]["mechanism"],
        )
        self.assertEqual(
            desc["adapter"]["grammar_sha256"],
            cap["adapter"]["grammar_sha256"],
        )
        self.assertEqual(
            desc["adapter"]["normalizer_sha256"],
            cap["adapter"]["normalizer_sha256"],
        )
        self.assertEqual(
            desc["adapter"]["executable_sha256"],
            cap["harness"]["executable"]["sha256"],
        )
        self.assertEqual(
            desc["adapter"]["config_sha256"],
            cap["adapter"]["config_sha256"],
        )
        self.assertEqual(desc["mcp"], cap["mcp"])
        self.assertEqual(cap["role"], "conductor")

    def test_launch_id_harness_matches_selection(self) -> None:
        selection = self.selection(harness="claude")
        self.dispatch.harness = "claude"
        result = self.prepare(selection=selection)
        desc, _compiled = self.assert_prepare_ok(result)
        self.assertIn("-conduct-claude-", desc["launch_id"])
        self.assertTrue(ID_RE.match(desc["selection"]["harness"]))


class UntrustedDigests(ConductFixture):
    def test_matching_digest_from_candidate_is_not_trusted_origin(self) -> None:
        impostor = b"not-the-held-custody-bytes\n"
        self.assertNotEqual(sha256_hex(impostor), self.custody_sha256)
        ctx = self.make_context(
            custody_bytes=impostor,
            candidate_origin=True,
        )
        self.assert_prepare_refused(
            self.prepare(ctx=ctx),
            "conduct-config",
            exact=conduct_config_line("bootstrap-untrusted"),
        )
        missing = self.make_context(missing_slots=("custody.json",))
        self.assert_prepare_refused(
            self.prepare(ctx=missing),
            "conduct-config",
            exact=conduct_config_line("bootstrap-missing"),
        )
        pipe = self.make_context(slot_kinds={"custody.json": "pipe"})
        self.assert_prepare_refused(
            self.prepare(ctx=pipe),
            "conduct-config",
            exact=conduct_config_line("bootstrap-invalid"),
        )
        writable = self.make_context(slot_kinds={"binding.json": "writable"})
        self.assert_prepare_refused(
            self.prepare(ctx=writable),
            "conduct-config",
            exact=conduct_config_line("bootstrap-invalid"),
        )
        neighbor = self.make_context()
        self.assert_prepare_ok(self.prepare(ctx=neighbor))

    def test_held_anchor_equality_is_required_not_just_the_hex(self) -> None:
        other = b"trusted-caller-custody-anchor-v1\n"
        self.assertEqual(sha256_hex(other), self.custody_sha256)
        ctx = self.make_context(
            custody_bytes=other,
            candidate_origin=True,
        )
        self.assert_prepare_refused(
            self.prepare(ctx=ctx),
            "conduct-config",
            exact=conduct_config_line("bootstrap-untrusted"),
        )

    def test_descriptor_digest_does_not_prove_binding_origin(self) -> None:
        desc, _compiled = self.assert_prepare_ok(
            self.prepare(selection=self.selection())
        )
        forged = dict(desc)
        forged["policy_binding_sha256"] = desc["policy_binding_sha256"]
        ctx = self.make_context(
            operation="resume",
            parent=forged,
            parent_bytes=canonical_dumps(forged),
            candidate_origin=True,
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=forged),
            "conduct-config",
            exact=conduct_config_line("bootstrap-untrusted"),
        )


class McpConnection(ConductFixture):
    def test_actual_client_must_initialize_list_and_call_lane_start(
        self,
    ) -> None:
        self.mcp_client.connect = True
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
        )
        prepared = self.prepare(mechanism=MECHANISM_CODEX)
        self.assert_prepare_ok(prepared)
        self.assertEqual(self.mcp_client.calls, [])

    def test_separate_server_query_is_not_connection_proof(self) -> None:
        self.mcp_client.connect = False
        receipt = self.mcp_server.query("lane_start", {"profile": "dev"})
        self.assertEqual(receipt["schema"], "agentscient.lane/v1")
        self.assertTrue(self.mcp_server.queries)
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_cli_refusal(
            proc,
            "conduct-mcp",
            exact=conduct_mcp_line(),
            exit_code=3,
        )
        self.assertEqual(self.mcp_client.observations, [])
        self.assertIsNotNone(self.dispatch.reserved)
        self.assertTrue(self.effects.record_paths() or self.dispatch.claimed_path)

    def test_server_self_reported_digest_is_not_connection_proof(self) -> None:
        self.mcp_client.connect = False
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        self.assertEqual(
            canonical_digest({"server": "self-reported"}),
            self.mcp_server.self_digest,
        )
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_cli_refusal(
            proc,
            "conduct-mcp",
            exact=conduct_mcp_line(),
            exit_code=3,
        )

    def test_configured_server_entry_alone_is_not_connection_proof(
        self,
    ) -> None:
        self.mcp_client.connect = False
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_cli_refusal(
            proc,
            "conduct-mcp",
            exact=conduct_mcp_line(),
            exit_code=3,
        )
        self.mcp_client.endpoint = "wrong-endpoint"
        self.mcp_client.connect = True
        self.mcp_client.emit_connection(profile="dev")
        self.assertNotEqual(self.mcp_client.endpoint, "bound-app-server")
        proc2 = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_cli_refusal(
            proc2,
            "conduct-mcp",
            exact=conduct_mcp_line(),
            exit_code=3,
        )
        self.mcp_client.endpoint = "bound-app-server"
        self.mcp_client.epoch = 0
        stale = self.mcp_client.emit_connection(profile="dev")
        self.assertTrue(all(row["epoch"] == 0 for row in stale))
        self.mcp_client.epoch = 1
        proc3 = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_cli_refusal(
            proc3,
            "conduct-mcp",
            exact=conduct_mcp_line(),
            exit_code=3,
        )

    def test_missing_connection_is_conduct_mcp(self) -> None:
        self.mcp_client.connect = True
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        self.mcp_client.connect = False
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assert_cli_refusal(
            proc,
            "conduct-mcp",
            exact=conduct_mcp_line(),
            exit_code=3,
        )
        self.assertTrue(self.mcp_client.reaped or proc.returncode == 3)

    def test_invalid_params_does_not_establish_server_absence(self) -> None:
        self.mcp_client.invalid_params = True
        self.mcp_client.connect = True
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 3)
        self.assert_refusal_line(
            proc.stderr,
            "conduct-mcp",
            exact=conduct_mcp_line(),
        )
        self.assertEqual(len(self.mcp_client.observations), 3)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
        )
        self.assertIn("error", self.mcp_client.observations[2]["response"])
        self.assertEqual(
            self.mcp_client.observations[2]["response"]["error"]["code"],
            -32602,
        )
        self.assertFalse((self.home / ".claude" / "settings.json").exists())
        self.assertNotIn("server absence", proc.stderr.lower())
        self.assertIsNone(
            self.claimed_record()
            and self.claimed_record().get("result", {}).get("envelope")
        )

    def test_catalogue_has_eleven_v3_tools(self) -> None:
        self.assertEqual(len(self.catalogue["tools"]), V3_TOOLS)
        self.assertEqual(
            [tool["name"] for tool in self.catalogue["tools"]],
            list(V3_TOOL_NAMES),
        )
        for tool in self.catalogue["tools"]:
            self.assertEqual(tool["inputSchema"], V3_TOOL_SCHEMAS[tool["name"]])
            self.assertNotEqual(tool["inputSchema"], {"type": "object"})
        result = self.prepare()
        desc, compiled = self.assert_prepare_ok(result)
        self.assertEqual(
            desc["mcp"]["catalogue_sha256"],
            canonical_digest(self.catalogue),
        )
        self.assert_closed_object(compiled, COMPILED_KEYS)
        self.assertEqual(self.mcp_client.calls, [])
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
        )
        listed = self.mcp_client.observations[1]["response"]["result"]["tools"]
        self.assertEqual([tool["name"] for tool in listed], list(V3_TOOL_NAMES))
        for tool in listed:
            self.assertEqual(tool["inputSchema"], V3_TOOL_SCHEMAS[tool["name"]])


class Onboarding(ConductFixture):
    def test_partial_valid_discovery_onboards_without_inventing_a_handoff(
        self,
    ) -> None:
        self.envelope = self.make_envelope("dev", unavailable=True)
        self.mcp_client.envelope = self.envelope
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
        )
        packet = self.mcp_client.observations[2]["response"]["result"]
        self.assertEqual(packet["data"]["handoffs"]["selected_key"], None)
        self.assertIn(OMISSIONS[0], packet["data"]["omissions"])
        dumped = json.dumps(packet)
        self.assertNotIn("path hint", dumped)
        self.assertNotIn(str(self.repo_root), json.dumps(packet["data"]))

    def test_onboarding_does_not_select_by_filename_or_time(self) -> None:
        self.envelope = self.make_envelope("dev", unavailable=True)
        self.envelope["data"]["handoffs"]["selection"] = "unknown"
        self.mcp_client.envelope = self.envelope
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
        )
        packet = self.mcp_client.observations[2]["response"]["result"]
        self.assertIsNone(packet["data"]["handoffs"]["selected_key"])
        call = self.mcp_client.observations[2]["request"]["params"]
        self.assertNotIn("path", json.dumps(call))

    def test_dev_prod_and_docs_onboard_without_path_hints(self) -> None:
        for profile in PROFILES:
            with self.subTest(profile=profile):
                selection = self.selection(profile=profile)
                envelope = self.make_envelope(profile, unavailable=True)
                self.mcp_client.envelope = envelope
                ctx = self.make_context(
                    selection=selection,
                    mechanism=MECHANISM_CODEX,
                )
                proc = self.invoke_conduct(["codex", profile], ctx=ctx)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assert_connection_observations(
                    self.mcp_client.observations,
                    profile=profile,
                )
                packet = self.mcp_client.observations[2]["response"]["result"]
                dumped = json.dumps(packet)
                self.assertNotIn("/home/", dumped)
                self.assertNotIn("enter a path", dumped.lower())
                self.assertEqual(packet["profile"], profile)

    def test_resume_reverifies_the_actual_client_connection(self) -> None:
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        first = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(first.returncode, 0, first.stderr)
        parent = self.retained_descriptor(first)
        first_obs = list(self.mcp_client.observations)
        self.assert_connection_observations(first_obs, profile="dev", epoch=0)
        self.mcp_client.calls.clear()
        self.mcp_client.observations = []
        self.mcp_client.epoch = 1
        resume_ctx = self.make_context(
            operation="resume",
            parent=parent,
            mechanism=MECHANISM_CODEX,
        )
        retry = self.invoke_conduct(["codex", "dev"], ctx=resume_ctx)
        self.assertEqual(retry.returncode, 0, retry.stderr)
        body = self.retained_descriptor(retry)
        self.assertEqual(body["launch_id"], parent["launch_id"])
        self.assertEqual(body["operation"], "resume")
        self.assertIsNotNone(body["resume"])
        self.assertEqual(
            body["resume"]["parent_descriptor_sha256"],
            canonical_digest(parent),
        )
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
            epoch=1,
        )
        self.assertNotEqual(self.mcp_client.observations, first_obs)
        prepared = self.prepare(
            operation="resume",
            ctx=self.make_context(operation="resume", parent=parent),
            parent=parent,
        )
        desc, compiled = self.assert_prepare_ok(prepared)
        self.assertEqual(desc["launch_id"], parent["launch_id"])
        self.assertEqual(compiled["binding"]["operation"], "resume")
        self.assertEqual(self.mcp_client.calls, [])

    def test_mismatched_record_descriptor_binding_refuses_before_effects(
        self,
    ) -> None:
        desc, _compiled = self.assert_prepare_ok(self.prepare())
        parent = dict(desc)
        parent["launch_id"] = "20260906T120000Z-conduct-codex-ffffff"
        self.assertNotEqual(parent["launch_id"], desc["launch_id"])
        ctx = self.make_context(
            operation="resume",
            parent=parent,
            parent_bytes=canonical_dumps(parent),
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx, parent=parent),
            "lane-resume",
        )
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 2)
        self.assert_refusal_line(proc.stderr, "lane-resume")
        self.assert_no_durable_effects()

    def test_changed_discovery_content_does_not_change_bound_profile(
        self,
    ) -> None:
        ctx = self.make_context(mechanism=MECHANISM_CODEX)
        first = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(first.returncode, 0, first.stderr)
        parent = self.retained_descriptor(first)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
        )
        first_snapshot = self.mcp_client.observations[2]["response"]["result"][
            "snapshot"
        ]
        self.envelope = self.make_envelope(
            "dev",
            unavailable=True,
            work=[{"id": "work-extra", "title": "acquired later"}],
        )
        self.mcp_client.envelope = self.envelope
        self.mcp_client.epoch = 1
        resume_ctx = self.make_context(
            operation="resume",
            parent=parent,
            mechanism=MECHANISM_CODEX,
        )
        retry = self.invoke_conduct(["codex", "dev"], ctx=resume_ctx)
        self.assertEqual(retry.returncode, 0, retry.stderr)
        again = self.retained_descriptor(retry)
        self.assert_connection_observations(
            self.mcp_client.observations,
            profile="dev",
            epoch=1,
        )
        packet = self.mcp_client.observations[2]["response"]["result"]
        self.assertEqual(again["selection"]["profile"], "dev")
        self.assertEqual(
            again["discovery"]["config_sha256"],
            parent["discovery"]["config_sha256"],
        )
        self.assertNotEqual(packet["snapshot"], first_snapshot)
        drifted = self.make_context(
            operation="resume",
            parent=parent,
            extra_profile=False,
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=drifted, parent=parent),
            "lane-resume",
        )

    def test_unbound_legacy_session_cannot_resume_in_place(self) -> None:
        ctx = self.make_context(
            operation="resume",
            parent=None,
            parent_bytes=canonical_dumps({"legacy": True}),
        )
        self.assert_prepare_refused(
            self.prepare(operation="resume", ctx=ctx),
            "lane-resume",
        )
        proc = self.invoke_conduct(["codex", "dev"], ctx=ctx)
        self.assertEqual(proc.returncode, 2)
        self.assert_refusal_line(proc.stderr, "lane-resume")
        self.assert_no_durable_effects()


class PreparePackaging(ConductFixture):
    def test_success_is_exactly_descriptor_and_compiled_launch(self) -> None:
        result = self.prepare()
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(tuple(sorted(result)), tuple(sorted(PREPARE_KEYS)))
        desc, compiled = unpack_prepare(result)
        self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        self.assert_closed_object(compiled, COMPILED_KEYS)

    def test_tuple_or_compiled_alias_is_not_success(self) -> None:
        desc, compiled = unpack_prepare(("descriptor", "compiled_launch"))
        self.assertEqual(desc, ("descriptor", "compiled_launch"))
        self.assertIsNone(compiled)
        desc2, compiled2 = unpack_prepare({"descriptor": {}, "compiled": {}})
        self.assertIsInstance(desc2, dict)
        self.assertIsNone(compiled2)

    def test_conduct_config_reasons_are_the_closed_set(self) -> None:
        self.assertEqual(
            CONFIG_REASONS,
            (
                "bootstrap-missing",
                "bootstrap-invalid",
                "bootstrap-untrusted",
                "descriptor-invalid",
                "input-mismatch",
            ),
        )
        self.assertEqual(len(BOOTSTRAP_SLOTS), 6)


if __name__ == "__main__":
    import unittest

    unittest.main()
