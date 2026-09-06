"""Independent tests for compile_launch safe argv and selection axes.

Written from ops/conductor/harness-capabilities.md (Conduct adapter
interface, Safe argv grammar), conductor-start-plan.md LaunchSelection,
permission-surface.md COND-AXIS-N1 / COND-ARGV / COND-SECRET, and
adoption review unit 4. Implementation was not read.

Each test names the contract rule it pins:

  A1  compile_launch is the declared in-process seam; missing name fails
      the assertion, not collection
  A2  Claude, Codex and Grok are separate configurable mechanics behind
      that one interface
  A3  harness, model, effort, conductor/worker role, job_role and profile
      are distinct axes; no substitution
  A4  closed grammar: every form, empty grammar, byte/order preservation
  A5  aliases, repetitions, indirect/response-file and reserved channels
      refuse at the offending index
  A6  rejected secret values never enter the refusal line
  A7  launch and resume bindings: invariant, argv digest, operation
  A8  unknown syntax is unmeasured; a closed-grammar reject is not
      UNREACHABLE
"""

from __future__ import annotations

import os
import unittest
from copy import deepcopy

import adapter_test_support as ats


class CompileLaunchIsTheDeclaredSeam(unittest.TestCase):
    """A1 — absent adapters.compile_launch fails the assertion, not import."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
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

    def test_compile_launch_does_not_invoke_the_fixture_executable(self):
        exe = self.transport["executable"]["path"]
        marker = exe + ".ran"
        self.assertFalse(os.path.exists(marker))
        self.assertTrue(os.path.isfile(exe))
        before = os.stat(exe)
        self.assertEqual(before.st_mode & 0o111, 0, "fixture executable must stay unarmed")
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertNotEqual(result, ats.MISSING_LAUNCH, ats.explain(result))
        self.assertFalse(
            os.path.exists(marker),
            "compile_launch must not launch, write or spawn the fixture",
        )
        after = os.stat(exe)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(after.st_size, before.st_size)

    def test_success_result_is_the_closed_five_key_object(self):
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        for key in ats.SUCCESS_KEYS:
            self.assertIn(key, result)
        argv = result["argv"]
        self.assertIsInstance(argv, list)
        self.assertGreaterEqual(len(argv), 1)
        self.assertEqual(argv[0], self.transport["executable"]["path"])
        self.assertTrue(os.path.isabs(argv[0]))
        env = result["environment"]
        self.assertIsInstance(env, dict)
        for name, value in env.items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(value, str)
        binding = result["binding"]
        self.assertEqual(
            set(binding),
            {"invariant_sha256", "argv_sha256", "operation"},
        )
        self.assertEqual(binding["operation"], "launch")


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
            self.assertEqual(argv0, transport["executable"]["path"])
            self.assertIn(f"fixture-{harness}", argv0)
            cap = result["capability"]
            self.assertEqual(cap["harness"]["name"], harness)
            self.assertEqual(
                cap["harness"]["executable"]["sha256"],
                transport["executable"]["sha256"],
            )
            seen[harness] = (
                argv0,
                transport["executable"]["sha256"],
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
        transport["executable"] = dict(grok)
        transport["adapter"]["executable_sha256"] = grok["sha256"]
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
    """A3 — COND-AXIS-N1: change each axis independently, never substitute."""

    AXES = (
        ("harness", "grok"),
        ("model", "other-fixture-model"),
        ("effort", "high"),
        ("role", "worker"),
        ("job_role", "write"),
        ("profile", "prod"),
    )

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.base = ats.selection_conductor()
        self.grants = ats.grants_for(self.base)
        self.transport = self.fx.transport(self.base)
        self.base_result = ats.compile_launch(
            self.base, self.grants, self.transport, [], "launch",
        )

    def test_base_conductor_selection_compiles(self):
        self.assertTrue(
            ats.is_success(self.base_result),
            ats.explain(self.base_result),
        )
        self.assertEqual(self.base["role"], "conductor")
        self.assertIsNone(self.base["job_role"])

    def test_each_axis_change_alters_the_invariant_and_does_not_rewrite_selection(self):
        self.assertTrue(
            ats.is_success(self.base_result),
            ats.explain(self.base_result),
        )
        base_inv = self.base_result["binding"]["invariant_sha256"]
        measured = {}
        for axis, value in self.AXES:
            with self.subTest(axis=axis, value=value):
                selection = deepcopy(self.base)
                selection[axis] = value
                if axis == "role" and value == "worker":
                    selection["job_role"] = "read"
                if axis == "job_role":
                    # conductor requires null job_role; this is a conflict.
                    pass
                grants = ats.grants_for(selection)
                if axis == "harness":
                    transport = self.fx.transport(selection)
                else:
                    transport = deepcopy(self.transport)
                held = deepcopy(selection)
                result = ats.compile_launch(
                    selection, grants, transport, [], "launch",
                )
                self.assertEqual(selection, held, "selection must not be rewritten")
                if axis == "job_role":
                    self.assertTrue(ats.is_refusal(result), ats.explain(result))
                    measured[axis] = "refused"
                    continue
                if axis == "role":
                    # worker uses TaskSelection; conductor interface role is
                    # literal conductor with no inherited worker grants.
                    self.assertTrue(
                        ats.is_success(result) or ats.is_refusal(result),
                        ats.explain(result),
                    )
                    if ats.is_success(result):
                        self.assertEqual(result["capability"]["role"], "worker")
                        self.assertNotEqual(
                            result["binding"]["invariant_sha256"], base_inv,
                        )
                    measured[axis] = result["binding"]["invariant_sha256"] if ats.is_success(result) else "refused"
                    continue
                self.assertTrue(ats.is_success(result), ats.explain(result))
                inv = result["binding"]["invariant_sha256"]
                self.assertNotEqual(inv, base_inv, axis)
                expected = ats.expected_invariant(
                    selection, grants, transport, [],
                )
                self.assertEqual(inv, expected)
                measured[axis] = inv
        self.assertEqual(len(set(measured.values())), len(self.AXES), measured)

    def test_conflicting_job_role_on_conductor_refuses_without_substitution(self):
        selection = ats.selection_conductor(job_role="write")
        held = deepcopy(selection)
        grants = ats.grants_for(ats.selection_conductor())
        result = ats.compile_launch(
            selection, grants, self.transport, [], "launch",
        )
        self.assertEqual(selection, held)
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        self.assertNotIn("write", selection["model"])

    def test_model_is_never_substituted(self):
        selection = ats.selection_conductor(model="fixture-model")
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
            self.transport["adapter"]["grammar_sha256"],
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
                self.assertEqual(argv[0], self.transport["executable"]["path"])
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
            transport["adapter"]["grammar_sha256"],
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

    def _refuse(self, tokens, *, index=None):
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, list(tokens), "launch",
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

    def test_more_than_sixty_four_tokens_is_a_vector_level_refusal(self):
        tokens = ["--quiet"] * 65
        line = self._refuse(tokens, index=0)
        self.assertIn("invalid token at index 0", line)

    def test_a_token_longer_than_two_hundred_fifty_six_bytes_refuses(self):
        token = "x" * 257
        self._refuse([token], index=0)

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
        transport["manifest"] = None
        transport["adapter"]["grammar_sha256"] = ats.digest_name("unmeasured")
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
    """A6 — COND-SECRET-N1: rejected values never enter the refusal line."""

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
        leaked = ats.secret_leaked(line, ats.CANARY_VALUE, ats.CANARY_LONG)
        self.assertEqual(leaked, [], line)
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
                line = ats.refusal_text(result)
                self.assertEqual(
                    ats.secret_leaked(line, ats.CANARY_LONG, ats.CANARY_VALUE),
                    [],
                    line,
                )


class LaunchResumeBinding(unittest.TestCase):
    """A7 — invariant vs argv digest; resume recompile; no vendor resume flag."""

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

    def test_resume_keeps_the_launch_invariant_and_differs_in_argv_digest(self):
        launch_transport = self.fx.transport(self.selection, "launch")
        launched = ats.compile_launch(
            self.selection, self.grants, launch_transport, self.tokens, "launch",
        )
        self.assertTrue(ats.is_success(launched), ats.explain(launched))
        resume_transport = self.fx.transport(self.selection, "resume")
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
        self.assertNotEqual(
            launched["binding"]["argv_sha256"],
            resumed["binding"]["argv_sha256"],
            "resume argv digest normally differs from launch",
        )
        self.assertEqual(
            resumed["binding"]["argv_sha256"],
            ats.expected_argv_sha256(resumed["argv"]),
        )

    def test_repeated_resume_with_identical_inputs_is_byte_identical(self):
        transport = self.fx.transport(self.selection, "resume")
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

    def test_operation_must_agree_with_the_binding(self):
        transport = self.fx.transport(self.selection, "launch")
        result = ats.compile_launch(
            self.selection, self.grants, transport, self.tokens, "resume",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))

    def test_raw_vendor_resume_flag_in_forwarded_tokens_refuses(self):
        transport = self.fx.transport(self.selection, "resume")
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
