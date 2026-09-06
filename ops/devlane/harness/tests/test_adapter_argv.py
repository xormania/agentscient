"""Independent tests for compile_launch safe argv and selection axes.

Written from ops/conductor/harness-capabilities.md (Conduct adapter
interface, Safe argv grammar, trusted compilation transport),
conductor-start-plan.md LaunchSelection, dispatch CONTRACT.md C2
worker encoding and evidence custody, permission-surface.md
COND-AXIS-N1 / COND-ARGV / COND-SECRET, and adoption review unit 4.
Corrected from d3ea314b against review 20260906T125857Z-review-claude-10edd9.
Implementation was not read.

Each test names the contract rule it pins:

  A1  compile_launch is the declared in-process seam; missing name fails
      the assertion, not collection; subprocess spy never fires
  A2  Claude, Codex and Grok are separate configurable mechanics behind
      that one interface
  A3  harness, model, effort, role, job_role and profile are distinct
      axes; valid rebounds are separate from required refusals
  A4  closed grammar: every form, empty grammar, byte/order preservation,
      measured insertion
  A5  aliases, repetitions, indirect/response-file and reserved channels
      refuse at the offending index; 64/65 and 8192/8193 are independent
  A6  rejected secret values never enter declared observation sinks
  A7  launch and resume bindings: invariant, argv digest, retained
      session identity, independently compiled expected resume vector
  A8  unknown syntax is unmeasured; a closed-grammar reject is not
      UNREACHABLE
"""

from __future__ import annotations

import os
import subprocess
import unittest
from copy import deepcopy

import adapter_test_support as ats


class CompileLaunchIsTheDeclaredSeam(unittest.TestCase):
    """A1 — absent adapters.compile_launch fails the assertion, not import."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.spy = ats.attach_subprocess_spy(self)
        self.selection = ats.selection_conductor()
        self.grants = ats.grants_for(self.selection)
        self.transport = self.fx.transport(self.selection)

    def test_the_declared_seam_is_compile_launch(self):
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertNotEqual(
            result,
            ats.MISSING_LAUNCH,
            "declared seam adapters.compile_launch is absent",
        )
        self.assertTrue(
            ats.is_success(result) or ats.is_refusal(result),
            ats.explain(result),
        )

    def test_subprocess_spy_fires_on_a_direct_call_and_not_on_compile(self):
        self.assertEqual(self.spy.calls, [])
        subprocess.run(["fixture-spy-probe"], check=False)
        self.assertEqual(len(self.spy.calls), 1, self.spy.calls)
        self.assertEqual(self.spy.calls[0][0], "run")
        self.spy.calls.clear()
        exe = self.transport.executable["path"]
        before = os.stat(exe)
        self.assertEqual(before.st_mode & 0o111, 0, "fixture executable must stay unarmed")
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertNotEqual(result, ats.MISSING_LAUNCH, ats.explain(result))
        self.assertEqual(
            self.spy.calls,
            [],
            "compile_launch must not reach the subprocess seam",
        )
        after = os.stat(exe)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(after.st_size, before.st_size)

    def test_success_result_is_the_closed_five_key_object(self):
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        self.assertEqual(set(result), set(ats.SUCCESS_KEYS))
        argv = result["argv"]
        self.assertIsInstance(argv, list)
        self.assertGreaterEqual(len(argv), 1)
        self.assertEqual(argv[0], self.transport.executable["path"])
        self.assertTrue(os.path.isabs(argv[0]))
        env = result["environment"]
        self.assertEqual(env, ats.expected_environment(self.transport))
        self.assertIn("FIXTURE_MARK", env)
        self.assertEqual(env["FIXTURE_MARK"], "admitted-nonsecret")
        for canary_name, canary_value in ats.ENV_CANARIES.items():
            self.assertNotEqual(env.get(canary_name), canary_value)
        binding = result["binding"]
        self.assertEqual(set(binding), set(ats.BINDING_KEYS))
        self.assertEqual(binding["operation"], "launch")
        cap = result["capability"]
        self.assertEqual(set(cap), set(ats.CONDUCT_CAPABILITY_KEYS))
        self.assertEqual(set(cap["adapter"]), set(ats.CONDUCT_ADAPTER_KEYS))
        self.assertEqual(cap["role"], "conductor")


class ConfigurableAdaptersShareOneInterface(unittest.TestCase):
    """A2 — separate Claude/Codex/Grok mechanics, one compile_launch."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)

    def _compile(self, harness, tokens=None):
        selection = ats.selection_conductor(harness)
        grants = ats.grants_for(selection)
        transport = self.fx.transport(selection)
        return ats.compile_launch(
            selection, grants, transport, list(tokens or []), "launch",
        ), transport

    def test_each_harness_pins_its_own_fixture_executable(self):
        seen = {}
        for harness in ("claude", "codex", "grok"):
            result, transport = self._compile(harness)
            self.assertTrue(ats.is_success(result), ats.explain(result))
            argv0 = result["argv"][0]
            self.assertEqual(argv0, transport.executable["path"])
            self.assertIn(f"fixture-{harness}", argv0)
            cap = result["capability"]
            self.assertEqual(cap["harness"]["name"], harness)
            self.assertEqual(
                cap["harness"]["executable"]["sha256"],
                transport.executable["sha256"],
            )
            seen[harness] = (
                argv0,
                transport.executable["sha256"],
                result["binding"]["invariant_sha256"],
            )
        paths = {row[0] for row in seen.values()}
        hashes = {row[1] for row in seen.values()}
        invariants = {row[2] for row in seen.values()}
        self.assertEqual(len(paths), 3, seen)
        self.assertEqual(len(hashes), 3, seen)
        self.assertEqual(len(invariants), 3, seen)

    def test_one_harness_cannot_admit_anothers_executable(self):
        selection = ats.selection_conductor("codex")
        grants = ats.grants_for(selection)
        transport = self.fx.transport(selection)
        grok = self.fx.executables["grok"]
        transport.executable = dict(grok)
        transport.manifest["adapter"]["executable_sha256"] = grok["sha256"]
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(
            line.startswith(ats.CAPABILITY_REFUSAL_PREFIX)
            or line.startswith(ats.ARGV_REFUSAL_PREFIX),
            line,
        )


class DistinctSelectionAxes(unittest.TestCase):
    """A3 — COND-AXIS-N1: rebound each axis independently; refuse stale witnesses."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.base = ats.selection_conductor()
        self.grants = ats.grants_for(self.base)
        self.transport = self.fx.transport(self.base)
        self.base_result = ats.compile_launch(
            self.base, self.grants, self.transport, [], "launch",
        )
        self.spy = ats.attach_subprocess_spy(self)

    def test_base_conductor_selection_compiles(self):
        self.assertTrue(
            ats.is_success(self.base_result),
            ats.explain(self.base_result),
        )
        self.assertEqual(self.base["role"], "conductor")
        self.assertIsNone(self.base["job_role"])
        self.assertEqual(
            set(self.base_result["capability"]),
            set(ats.CONDUCT_CAPABILITY_KEYS),
        )

    def test_valid_axis_rebounds_change_the_invariant(self):
        self.assertTrue(
            ats.is_success(self.base_result),
            ats.explain(self.base_result),
        )
        base_inv = self.base_result["binding"]["invariant_sha256"]
        measured = {}

        def rebound(selection, grants, transport, axis):
            held = deepcopy(selection)
            result = ats.compile_launch(
                selection, grants, transport, [], "launch",
            )
            self.assertEqual(selection, held, "selection must not be rewritten")
            self.assertTrue(ats.is_success(result), ats.explain(result))
            inv = result["binding"]["invariant_sha256"]
            self.assertNotEqual(inv, base_inv, axis)
            expected = ats.expected_invariant(
                selection, grants, transport, [],
            )
            self.assertEqual(inv, expected)
            self.assertEqual(
                set(result["capability"]),
                set(ats.capability_keys_for(selection)),
            )
            self.assertEqual(result["capability"]["role"], selection["role"])
            measured[axis] = inv

        with self.subTest(axis="harness"):
            selection = ats.selection_conductor("grok")
            grants = ats.grants_for(selection)
            rebound(selection, grants, self.fx.transport(selection), "harness")

        with self.subTest(axis="model"):
            selection = ats.selection_conductor(model="other-fixture-model")
            grants = ats.grants_for(selection)
            rebound(selection, grants, self.fx.transport(selection), "model")

        with self.subTest(axis="effort"):
            selection = ats.selection_conductor(effort="high")
            grants = ats.grants_for(selection)
            rebound(selection, grants, self.fx.transport(selection), "effort")

        with self.subTest(axis="role"):
            selection = ats.selection_worker()
            grants = ats.grants_for(selection)
            transport = self.fx.transport(selection)
            rebound(selection, grants, transport, "role")
            result = ats.compile_launch(
                selection, grants, transport, [], "launch",
            )
            self.assertEqual(result["capability"]["role"], "worker")
            self.assertEqual(
                set(result["capability"]),
                set(ats.WORKER_CAPABILITY_KEYS),
            )
            self.assertNotIn("mcp", result["capability"])
            self.assertNotIn("policy", result["capability"])
            self.assertEqual(
                set(result["capability"]["adapter"]),
                set(ats.WORKER_ADAPTER_KEYS),
            )

        with self.subTest(axis="job_role"):
            selection = ats.selection_worker(job_role="write")
            grants = ats.grants_for(selection)
            rebound(
                selection, grants, self.fx.transport(selection), "job_role",
            )

        with self.subTest(axis="profile"):
            selection = ats.selection_conductor(profile="prod")
            grants = ats.grants_for(selection)
            rebound(selection, grants, self.fx.transport(selection), "profile")

        self.assertEqual(set(measured), {
            "harness", "model", "effort", "role", "job_role", "profile",
        })
        self.assertEqual(len(set(measured.values())), 6, measured)
        self.assertNotIn("refused", measured.values())

    def test_stale_worker_selection_with_conductor_witness_refuses(self):
        selection = ats.selection_worker()
        held = deepcopy(selection)
        grants = ats.grants_for(selection)
        result = ats.compile_launch(
            selection, grants, deepcopy(self.transport), [], "launch",
        )
        self.assertEqual(selection, held)
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("stale", line)

    def test_conflicting_job_role_on_conductor_refuses_without_substitution(self):
        selection = ats.selection_conductor(
            job_role="write",
            model="fixture-write-model",
        )
        self.assertIn("write", selection["model"])
        held = deepcopy(selection)
        grants = ats.grants_for(selection)
        transport = self.fx.transport(selection)
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertEqual(selection, held)
        self.assertEqual(selection["model"], "fixture-write-model")
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        self.assertEqual(self.spy.calls, [])

    def test_model_containing_write_is_never_substituted(self):
        selection = ats.selection_conductor(model="fixture-write-model")
        self.assertIn("write", selection["model"])
        grants = ats.grants_for(selection)
        transport = self.fx.transport(selection)
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        inv = result["binding"]["invariant_sha256"]
        expected = ats.expected_invariant(selection, grants, transport, [])
        self.assertEqual(inv, expected)
        other = deepcopy(selection)
        other["model"] = "silently-defaulted-model"
        other_inv = ats.expected_invariant(other, grants, transport, [])
        self.assertNotEqual(inv, other_inv)
        self.assertEqual(selection["model"], "fixture-write-model")


class SafeArgvGrammarPositive(unittest.TestCase):
    """A4 — documentary positives, both forms, empty grammar, preservation."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_conductor()
        self.grants = ats.grants_for(self.selection)
        self.transport = self.fx.transport(self.selection)

    def test_grammar_sha256_binds_the_synthetic_declaration(self):
        self.assertEqual(
            self.transport.manifest["adapter"]["grammar_sha256"],
            ats.GRAMMAR_SHA256,
        )
        self.assertEqual(ats.sha256_json(ats.SYNTHETIC_GRAMMAR), ats.GRAMMAR_SHA256)
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        self.assertEqual(
            result["capability"]["adapter"]["grammar_sha256"],
            ats.GRAMMAR_SHA256,
        )

    def test_documentary_positive_vectors_preserve_bytes_and_order(self):
        hashes = []
        for tokens in ats.POSITIVE_VECTORS:
            with self.subTest(tokens=tokens):
                held = list(tokens)
                result = ats.compile_launch(
                    self.selection, self.grants, self.transport, tokens, "launch",
                )
                self.assertTrue(ats.is_success(result), ats.explain(result))
                self.assertEqual(tokens, held)
                argv = result["argv"]
                self.assertEqual(argv[0], self.transport.executable["path"])
                if tokens:
                    segment = ats.contiguous_segment(argv, tokens)
                    self.assertEqual(
                        segment,
                        tokens,
                        f"forwarded tokens must be a contiguous argv segment: {argv!r}",
                    )
                    for got, want in zip(segment, tokens, strict=True):
                        self.assertEqual(got.encode("utf-8"), want.encode("utf-8"))
                else:
                    self.assertNotIn("--display", argv)
                    self.assertNotIn("--quiet", argv)
                argv_digest = result["binding"]["argv_sha256"]
                self.assertEqual(argv_digest, ats.expected_argv_sha256(argv))
                hashes.append(argv_digest)
        self.assertEqual(len(hashes), 3)
        self.assertEqual(len(set(hashes)), 3, hashes)

    def test_forwarded_tokens_insert_at_the_measured_index(self):
        tokens = ["--display=compact", "--quiet"]
        base = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertTrue(ats.is_success(base), ats.explain(base))
        index = self.transport.manifest["insertion"]["launch"]
        self.assertGreaterEqual(index, 1)
        self.assertLessEqual(index, len(base["argv"]))
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        expected = base["argv"][:index] + tokens + base["argv"][index:]
        self.assertEqual(result["argv"], expected)
        self.assertEqual(ats.contiguous_segment(result["argv"], tokens), tokens)

    def test_changed_insertion_index_without_renewed_evidence_refuses(self):
        original = self.transport.manifest["insertion"]["resume"]
        self.transport.manifest["insertion"]["resume"] = original + 1
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, ["--quiet"], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))

    def test_equals_form_is_not_rewritten_to_split(self):
        tokens = ["--display=compact"]
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        argv = result["argv"]
        self.assertIn("--display=compact", argv)
        self.assertNotIn("compact", [t for t in argv if t != "--display=compact"])
        display_at = argv.index("--display=compact")
        if display_at + 1 < len(argv):
            self.assertNotEqual(argv[display_at + 1], "compact")

    def test_split_form_is_not_rewritten_to_equals(self):
        tokens = ["--display", "plain"]
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        argv = result["argv"]
        self.assertEqual(ats.contiguous_segment(argv, tokens), tokens)
        self.assertNotIn("--display=plain", argv)

    def test_empty_grammar_admits_only_an_empty_forwarded_vector(self):
        transport = self.fx.transport(
            self.selection, grammar=ats.EMPTY_GRAMMAR,
        )
        self.assertEqual(
            transport.manifest["adapter"]["grammar_sha256"],
            ats.EMPTY_GRAMMAR_SHA256,
        )
        ok = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(ok), ats.explain(ok))
        refused = ats.compile_launch(
            self.selection, self.grants, transport, ["--quiet"], "launch",
        )
        self.assertTrue(ats.is_refusal(refused), ats.explain(refused))
        line = ats.refusal_text(refused)
        self.assertTrue(line.startswith(ats.ARGV_REFUSAL_PREFIX), line)
        self.assertIn("invalid token at index 0", line)

    def test_repeatable_option_keeps_both_occurrences(self):
        tokens = ["--tag=alpha", "--tag", "beta"]
        transport = self.fx.transport(
            self.selection, grammar=ats.REPEATABLE_GRAMMAR,
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        self.assertEqual(
            ats.contiguous_segment(result["argv"], tokens),
            tokens,
        )


class SafeArgvGrammarNegative(unittest.TestCase):
    """A5 — documentary negatives, aliases, repetitions, reserved, limits."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_conductor()
        self.grants = ats.grants_for(self.selection)
        self.transport = self.fx.transport(self.selection)

    def _refuse(self, tokens, *, index=None, transport=None):
        transport = self.transport if transport is None else transport
        result = ats.compile_launch(
            self.selection, self.grants, transport, list(tokens), "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.ARGV_REFUSAL_PREFIX), line)
        self.assertIn("expected declared safe tokens", line)
        self.assertIn("needed use the measured adapter grammar", line)
        if index is not None:
            self.assertIn(f"invalid token at index {index}", line)
        self.assertNotIn("UNREACHABLE", line)
        return line

    def test_documentary_negative_vectors_refuse_at_the_offending_index(self):
        expected_index = {
            "repetition-across-forms": 1,
            "abbreviation": 0,
            "short-alias": 0,
            "unsafe-value": 0,
            "response-file": 0,
            "reserved-config": 0,
            "trailing-positional": 1,
            "bare-double-dash": 0,
            "missing-split-value": 0,
        }
        self.assertEqual(len(ats.NEGATIVE_VECTORS), 9)
        for tokens, label in ats.NEGATIVE_VECTORS:
            with self.subTest(label=label, tokens=tokens):
                line = self._refuse(tokens, index=expected_index[label])
                self.assertNotIn("UNREACHABLE", line)

    def test_reserved_permission_sandbox_session_and_selection_tokens_refuse(self):
        for token in ats.RESERVED_TOKENS:
            with self.subTest(token=token):
                self._refuse([token], index=0)

    def test_repeated_flag_refuses_unless_repeatable(self):
        self._refuse(["--quiet", "--quiet"], index=1)

    def test_nul_and_control_bytes_refuse(self):
        self._refuse(["--quiet\x00"], index=0)
        self._refuse(["--quiet\n"], index=0)

    def test_sixty_four_repeatable_tokens_admit(self):
        tokens = ["--tag=alpha"] * 64
        self.assertEqual(len(tokens), 64)
        transport = self.fx.transport(
            self.selection, grammar=ats.REPEATABLE_GRAMMAR,
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        self.assertEqual(ats.contiguous_segment(result["argv"], tokens), tokens)

    def test_sixty_five_repeatable_tokens_refuse_at_index_zero(self):
        tokens = ["--tag=alpha"] * 65
        self.assertEqual(len(tokens), 65)
        transport = self.fx.transport(
            self.selection, grammar=ats.REPEATABLE_GRAMMAR,
        )
        line = self._refuse(tokens, index=0, transport=transport)
        self.assertIn("invalid token at index 0", line)

    def test_total_byte_bound_admits_at_eight_thousand_one_hundred_ninety_two(self):
        tokens = list(ats.VECTOR_8192)
        total = sum(len(token.encode("utf-8")) for token in tokens)
        self.assertEqual(total, 8192)
        self.assertEqual(len(tokens), 32)
        self.assertTrue(all(len(token.encode("utf-8")) <= 256 for token in tokens))
        transport = self.fx.transport(
            self.selection, grammar=ats.BYTE_BOUND_GRAMMAR,
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        self.assertEqual(ats.contiguous_segment(result["argv"], tokens), tokens)

    def test_total_byte_bound_refuses_at_eight_thousand_one_hundred_ninety_three(self):
        tokens = list(ats.VECTOR_8193)
        total = sum(len(token.encode("utf-8")) for token in tokens)
        self.assertEqual(total, 8193)
        self.assertEqual(len(tokens), 64)
        self.assertTrue(all(len(token.encode("utf-8")) <= 256 for token in tokens))
        transport = self.fx.transport(
            self.selection, grammar=ats.BYTE_BOUND_GRAMMAR,
        )
        line = self._refuse(tokens, index=0, transport=transport)
        self.assertIn("invalid token at index 0", line)

    def test_a_token_of_two_hundred_fifty_six_bytes_admits(self):
        tokens = [ats.FLAG_256]
        self.assertEqual(len(tokens[0].encode("utf-8")), 256)
        transport = self.fx.transport(
            self.selection, grammar=ats.BYTE_BOUND_GRAMMAR,
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))

    def test_a_token_longer_than_two_hundred_fifty_six_bytes_refuses(self):
        token = ats.FLAG_257
        self.assertEqual(len(token.encode("utf-8")), 257)
        self.assertRegex(token, r"^--[a-z][a-z0-9-]*$")
        transport = self.fx.transport(
            self.selection, grammar=ats.BYTE_BOUND_GRAMMAR,
        )
        names = [option["name"] for option in transport.manifest["grammar"]["options"]]
        self.assertIn(token, names)
        self._refuse([token], index=0, transport=transport)

    def test_invalid_manifest_flag_with_values_does_not_admit(self):
        broken = {
            "schema": "adapter-argv/1",
            "options": [
                {
                    "name": "--quiet",
                    "forms": ["flag"],
                    "values": ["yes"],
                    "repeatable": False,
                },
            ],
        }
        transport = self.fx.transport(self.selection, grammar=broken)
        result = ats.compile_launch(
            self.selection, self.grants, transport, ["--quiet"], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))

    def test_unknown_installation_syntax_is_unmeasured_not_a_guess(self):
        transport = self.fx.transport(self.selection)
        unmeasured = ats.digest_name("unmeasured")
        transport.manifest["grammar"] = None
        transport.manifest["adapter"]["grammar_sha256"] = unmeasured
        identity = deepcopy(transport.evidence.identity)
        identity["adapter"]["grammar_sha256"] = unmeasured
        transport.evidence.identity = identity
        self.assertEqual(
            transport.manifest["adapter"]["grammar_sha256"],
            transport.evidence.identity["adapter"]["grammar_sha256"],
        )
        self.assertIsNone(transport.manifest["grammar"])
        result = ats.compile_launch(
            self.selection, self.grants, transport, ["--quiet"], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertNotIn("UNREACHABLE", line)
        self.assertFalse(ats.is_success(result))
        self.assertTrue(
            line.startswith(ats.CAPABILITY_REFUSAL_PREFIX),
            line,
        )
        self.assertIn("unresolved", line)


class SecretFreeRefusals(unittest.TestCase):
    """A6 — COND-SECRET-N1: rejected values never enter observation sinks."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_conductor()
        self.grants = ats.grants_for(self.selection)
        self.transport = self.fx.transport(self.selection)

    def test_rejected_secret_value_is_absent_from_the_refusal(self):
        tokens = [f"--display={ats.CANARY_VALUE}"]
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, tokens, "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        sinks = ats.observation_sinks(result)
        leaked = ats.secret_leaked(sinks, ats.CANARY_VALUE, ats.CANARY_LONG)
        self.assertEqual(leaked, [], sinks)
        self.assertIn("invalid token at index 0", line)
        self.assertNotIn(ats.CANARY_VALUE.lower(), line.lower())

    def test_long_canary_in_equals_and_split_is_absent_from_the_refusal(self):
        cases = (
            [f"--display={ats.CANARY_LONG}"],
            ["--display", ats.CANARY_LONG],
            [f"--config={ats.CANARY_LONG}"],
        )
        for tokens in cases:
            with self.subTest(tokens=tokens):
                result = ats.compile_launch(
                    self.selection, self.grants, self.transport, tokens, "launch",
                )
                self.assertTrue(ats.is_refusal(result), ats.explain(result))
                sinks = ats.observation_sinks(result)
                self.assertEqual(
                    ats.secret_leaked(sinks, ats.CANARY_LONG, ats.CANARY_VALUE),
                    [],
                    sinks,
                )


class LaunchResumeBinding(unittest.TestCase):
    """A7 — invariant vs argv digest; retained session; expected resume vector."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_conductor()
        self.grants = ats.grants_for(self.selection)
        self.tokens = ["--display=compact", "--quiet"]

    def test_launch_binding_hashes_invariant_inputs_and_final_argv(self):
        transport = self.fx.transport(self.selection, "launch")
        result = ats.compile_launch(
            self.selection, self.grants, transport, self.tokens, "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        binding = result["binding"]
        self.assertEqual(set(binding), set(ats.BINDING_KEYS))
        self.assertEqual(binding["operation"], "launch")
        self.assertEqual(
            binding["invariant_sha256"],
            ats.expected_invariant(
                self.selection, self.grants, transport, self.tokens,
            ),
        )
        self.assertEqual(
            binding["argv_sha256"],
            ats.expected_argv_sha256(result["argv"]),
        )
        self.assertRegex(binding["invariant_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(binding["argv_sha256"], r"^[0-9a-f]{64}$")

    def test_ordinary_cli_resume_equals_independently_compiled_expected_vector(self):
        launch_transport = self.fx.transport(self.selection, "launch")
        launched = ats.compile_launch(
            self.selection, self.grants, launch_transport, self.tokens, "launch",
        )
        self.assertTrue(ats.is_success(launched), ats.explain(launched))
        resume_transport = self.fx.resume_transport(
            self.selection, self.grants, self.tokens,
        )
        session_id = resume_transport.resume["session"]["id"]
        self.assertEqual(session_id, ats.SESSION_ID)
        self.assertEqual(
            resume_transport.resume["session"]["launch_id"],
            resume_transport.launch_session["launch_id"],
        )
        resumed = ats.compile_launch(
            self.selection, self.grants, resume_transport, self.tokens, "resume",
        )
        self.assertTrue(ats.is_success(resumed), ats.explain(resumed))
        self.assertEqual(resumed["binding"]["operation"], "resume")
        self.assertEqual(
            launched["binding"]["invariant_sha256"],
            resumed["binding"]["invariant_sha256"],
        )
        self.assertEqual(
            launched["binding"]["invariant_sha256"],
            ats.expected_invariant(
                self.selection, self.grants, resume_transport, self.tokens,
            ),
        )
        again = ats.compile_launch(
            self.selection,
            self.grants,
            deepcopy(resume_transport),
            list(self.tokens),
            "resume",
        )
        self.assertTrue(ats.is_success(again), ats.explain(again))
        self.assertEqual(resumed["argv"], again["argv"])
        self.assertEqual(
            resumed["binding"]["argv_sha256"],
            ats.expected_argv_sha256(resumed["argv"]),
        )
        self.assertTrue(
            any(session_id in token for token in resumed["argv"]),
            resumed["argv"],
        )
        self.assertNotEqual(
            launched["binding"]["argv_sha256"],
            resumed["binding"]["argv_sha256"],
            "ordinary CLI resume renders the retained session segment",
        )

    def test_repeated_resume_with_identical_inputs_is_byte_identical(self):
        transport = self.fx.resume_transport(
            self.selection, self.grants, self.tokens,
        )
        first = ats.compile_launch(
            self.selection, self.grants, transport, self.tokens, "resume",
        )
        second = ats.compile_launch(
            self.selection, self.grants, deepcopy(transport), list(self.tokens), "resume",
        )
        self.assertTrue(ats.is_success(first), ats.explain(first))
        self.assertTrue(ats.is_success(second), ats.explain(second))
        self.assertEqual(first["argv"], second["argv"])
        self.assertEqual(
            first["binding"]["argv_sha256"],
            second["binding"]["argv_sha256"],
        )
        self.assertEqual(first["environment"], second["environment"])

    def test_relay_resume_keeps_launch_argv_and_uses_thread_id(self):
        selection = ats.selection_conductor()
        grants = ats.grants_for(selection)
        relay = self.fx.synthetic_relay()
        kwargs = {
            "grammar": ats.EMPTY_GRAMMAR,
            "mechanism": "codex-sole-client-relay/1",
            "relay": relay,
        }
        launch_transport = self.fx.transport(selection, "launch", **kwargs)
        launched = ats.compile_launch(
            selection, grants, launch_transport, [], "launch",
        )
        self.assertTrue(ats.is_success(launched), ats.explain(launched))
        inv = ats.expected_invariant(selection, grants, launch_transport, [])
        resume_relay = self.fx.synthetic_relay(
            thread_id=ats.SESSION_ID,
            session_binding=ats.session_binding_sha256(
                ats.session_object(
                    selection,
                    launch_id=ats.launch_id_for(selection),
                    session_id=ats.SESSION_ID,
                    invariant_sha256=inv,
                    connection={
                        "client_sha256": ats.digest_name("client"),
                        "server_sha256": ats.digest_name("server"),
                    },
                ),
            ),
        )
        resume_transport = self.fx.transport(
            selection, "resume", invariant_sha256=inv, **{
                **kwargs,
                "relay": resume_relay,
            },
        )
        self.assertEqual(
            resume_transport.relay["resume"]["thread_id"],
            ats.SESSION_ID,
        )
        resumed = ats.compile_launch(
            selection, grants, resume_transport, [], "resume",
        )
        self.assertTrue(ats.is_success(resumed), ats.explain(resumed))
        self.assertEqual(resumed["binding"]["operation"], "resume")
        self.assertEqual(resumed["argv"], launched["argv"])
        self.assertEqual(
            resumed["binding"]["argv_sha256"],
            launched["binding"]["argv_sha256"],
        )
        again = ats.compile_launch(
            selection, grants, deepcopy(resume_transport), [], "resume",
        )
        self.assertEqual(again["argv"], resumed["argv"])

    def test_operation_must_agree_with_the_binding(self):
        transport = self.fx.transport(self.selection, "launch")
        result = ats.compile_launch(
            self.selection, self.grants, transport, self.tokens, "resume",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))

    def test_raw_vendor_resume_flag_in_forwarded_tokens_refuses(self):
        transport = self.fx.resume_transport(
            self.selection, self.grants, ["--resume", "sess_fixture"],
        )
        result = ats.compile_launch(
            self.selection,
            self.grants,
            transport,
            ["--resume", "sess_fixture"],
            "resume",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.ARGV_REFUSAL_PREFIX), line)
        self.assertNotIn("sess_fixture", line)

    def test_changed_forwarded_tokens_change_the_invariant(self):
        transport = self.fx.transport(self.selection, "launch")
        a = ats.compile_launch(
            self.selection, self.grants, transport, ["--quiet"], "launch",
        )
        b = ats.compile_launch(
            self.selection, self.grants, transport, ["--display=plain"], "launch",
        )
        self.assertTrue(ats.is_success(a), ats.explain(a))
        self.assertTrue(ats.is_success(b), ats.explain(b))
        self.assertNotEqual(
            a["binding"]["invariant_sha256"],
            b["binding"]["invariant_sha256"],
        )
        self.assertNotEqual(a["argv"], b["argv"])


class TrustedEnvironmentAndCanaries(unittest.TestCase):
    """Closed environment equals trusted declarations; process canaries stay out."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_conductor()
        self.grants = ats.grants_for(self.selection)
        self._previous = {
            name: os.environ.get(name) for name in ats.ENV_CANARIES
        }
        os.environ.update(ats.ENV_CANARIES)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for name, value in self._previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_compiled_environment_equals_trusted_map_not_an_empty_or_canary_map(self):
        transport = self.fx.transport(self.selection)
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        env = result["environment"]
        self.assertEqual(env, ats.expected_environment(transport))
        self.assertEqual(env["FIXTURE_MARK"], "admitted-nonsecret")
        self.assertEqual(set(env), set(ats.TRUSTED_ENV))
        self.assertNotEqual(env.get("PATH"), ats.ENV_CANARIES["PATH"])
        self.assertNotEqual(env.get("HOME"), ats.ENV_CANARIES["HOME"])
        self.assertNotEqual(env.get("TMPDIR"), ats.ENV_CANARIES["TMPDIR"])
        self.assertNotEqual(env, {})
