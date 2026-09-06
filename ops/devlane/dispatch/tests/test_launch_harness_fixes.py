"""Harness fixes measured on 2026-08-29 (see the conductor's memo
`harness-bugs-2026-08-29.md`): read roles must be able to execute; grok
must never wait on a permission prompt; a harness that cannot commit
keeps its own message and attribution; what a harness leaves uncommitted
is preserved; a dispatch that ends without an envelope says why."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import launch_support as ls

LAUNCH = Path(__file__).resolve().parents[1] / "launch.py"


def _load(test):
    return ls.load_path(test, LAUNCH, "launch_under_harness_fixes")


class ReadRolesCanExecute(ls._TempLaunch):
    """B2: a skeptic that cannot run the suite is structural."""

    def test_claude_argv_preapproves_verification_commands_only(self):
        rec, witness, *_ = self.launch_ok(
            job="check-tests", harness="claude", stage="check-tests",
        )
        argv = [str(p) for p in witness["argv"]]
        self.assertIn("--allowedTools", argv)
        start = argv.index("--allowedTools") + 1
        rules = []
        for item in argv[start:]:
            if item.startswith("--"):
                break
            rules.append(item)
        for needed in ("Bash(python3 -m unittest *)", "Bash(ruff check *)", "Bash(cue vet *)",
                       "Bash(git diff *)", "Bash(git status *)", "Bash(python3 ops/*)"):
            self.assertIn(needed, rules)
        # an interpreter is arbitrary code under the operator's uid (review ba0d93/ffaf14)
        for leak in ("Bash(python3 *)", "Bash(python *)", "Bash(env *)", "Bash(find *)",
                     "Bash(cp *)", "Bash(sed *)", "Bash(sort *)", "Bash(mkdir *)", "Bash(*)", "Bash"):
            self.assertNotIn(leak, rules)
        for rule in rules:
            self.assertTrue(rule.startswith("Bash("), rule)
            for forbidden in ("git push", "git commit", "git reset", "docker",
                              "rm ", "curl", "wget", "ssh"):
                self.assertNotIn(forbidden, rule)
        self.assertIn("--disallowedTools", argv)
        dstart = argv.index("--disallowedTools") + 1
        denied = []
        for item in argv[dstart:]:
            if item.startswith("--"):
                break
            denied.append(item)
        for tool in ("WebFetch", "WebSearch", "Agent", "Task"):
            self.assertIn(tool, denied)
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")
        self.assertIn("--allowedTools", rec["harness"]["argv"])

    def test_a_read_role_that_writes_into_the_snapshot_is_recorded_and_salvaged(self):
        # The existing contract stands: a read role's stray write is recorded
        # as residual (HEAD must still equal the ref), never a refusal that
        # discards its report. What is new: the write is preserved.
        os.environ["TASK_LAUNCH_EDIT"] = "README.md"
        code, out, err = self.dispatch(
            job="check-tests", harness="claude", stage="check-tests",
        )
        self.assertNotEqual(code, ls.REFUSAL_EXIT, self.combined(out, err))
        rec = self.read_record()
        env = rec["result"]["envelope"]
        self.assertNotIn("read-role-residual", str(env.get("note", "")))
        self.assertTrue(rec["result"]["residual_paths"])
        salvage = rec["result"].get("residual_patch")
        self.assertIsInstance(salvage, dict)
        path = Path(salvage["path"])
        self.assertTrue(path.is_file(), salvage)
        self.assertEqual(salvage["sha256"], ls.sha256_file(path))
        self.assertIn("README.md", path.read_text())
        self.assertIn("cause", rec["result"])


class SpendIsMeasuredFromTheStore(ls._TempLaunch):
    """U5: 105 of 105 records carried spend: null on 2026-08-29."""

    def test_a_claude_dispatch_records_its_spend_from_the_fixture_store(self):
        rec, *_ = self.launch_ok(job="plan", harness="claude", stage="plan")
        spend = rec["session"]["spend"]
        self.assertIsInstance(spend, dict)
        self.assertNotIn("unresolved", spend, spend)
        # fixtures/stores.py: input 30, cached 12000, output 500
        self.assertEqual(spend["input"], 30)
        self.assertEqual(spend["cached"], 12000)
        self.assertEqual(spend["output"], 500)
        self.assertEqual(spend["total"], 12530)
        self.assertTrue(spend["source"].endswith(".jsonl"))

    def test_a_codex_dispatch_records_the_last_cumulative_count(self):
        rec, *_ = self.launch_ok(job="implement", harness="codex", stage="code")
        spend = rec["session"]["spend"]
        self.assertIsInstance(spend, dict)
        self.assertNotIn("unresolved", spend, spend)
        for key in ("input", "output", "total"):
            self.assertIsInstance(spend.get(key), int, spend)
        self.assertGreater(spend["total"], 0)

    def test_a_grok_store_without_usage_events_is_an_explicit_gap(self):
        rec, *_ = self.launch_ok(job="author-tests", harness="grok", stage="tests")
        spend = rec["session"]["spend"]
        self.assertIsInstance(spend, dict)
        # either measured tokens or a stated gap — never a zero
        self.assertTrue(("total" in spend and spend["total"] > 0) or "unresolved" in spend, spend)
        self.assertNotEqual(spend.get("total"), 0)


class GrokNeverWaitsOnAPrompt(ls._TempLaunch):
    """B1: 111 prompts, the last cancelled after 30 s, no envelope."""

    def test_grok_argv_carries_always_approve_and_no_web_and_no_permission_mode(self):
        rec, witness, *_ = self.launch_ok(
            job="author-tests", harness="grok", stage="tests",
        )
        argv = [str(p) for p in witness["argv"]]
        self.assertIn("--always-approve", argv)
        self.assertIn("--disable-web-search", argv)
        self.assertNotIn("--permission-mode", argv)
        self.assertEqual(rec["harness"]["sandbox"], "always-approve")

    def test_grok_resume_argv_keeps_the_same_flags(self):
        launch = _load(self)
        argv = launch._argv("grok", "grok-4.6", None, "sid", Path("/x/prompt.txt"),
                            ["--flag"], "always-approve", resume=True)
        self.assertIn("--always-approve", argv)
        self.assertIn("--disable-web-search", argv)
        self.assertIn("--flag", argv)
        self.assertIn("-r", argv)
        # U10: --json-schema (implies json). plain was the pre-U10 argv.
        self.assertNotIn("--json-schema", argv)  # grok 1.0.5 short-circuits under --json-schema (record 66ccb2)
        if "--output-format" in argv:
            self.assertEqual(
                argv[argv.index("--output-format") + 1], "plain",
            )


# Synthetic producer paragraphs. A colon-prefixed wrap inside a
# paragraph is prose: isolated git interpret-trailers --parse does not
# take the wrapped key as a trailer until assembly lifts the line.
_WRAPPED_PASS = (
    "The original 83 tests remain green after the wrap.\n"
    "pass: 100 checks, 51 local links and six JSON examples. Neighbors stay.\n"
    "The sentence continues on the following line."
)
_VALIDATION = (
    "Contracted checks include the supplied methods.\n"
    "Validation: links and existing examples preserved; 83 supplied test methods\n"
    "and the count is still part of this paragraph."
)
_ARBITRARY_KEY = (
    "Inventory after the filter is unchanged.\n"
    "Quux: 12 remaining after filter and still prose\n"
    "so a denylist of pass and Validation cannot hide the defect."
)
_KNOWN_KEY_IN_PROSE = (
    "The review named the required stamp as a\n"
    "Reviewed-by: line only when a reviewer actually read the change.\n"
    "Spelling the key inside this paragraph does not make it metadata."
)
_UNWRAPPED_PASS = (
    "The original 83 tests remain green after the wrap. "
    "pass: 100 checks, 51 local links and six JSON examples. Neighbors stay. "
    "The sentence continues on the following line."
)
_TERMINAL_ACK = "Acked-by: Reviewer <r@example.invalid>"
_OWN_COAUTHOR = "Co-Authored-By: GPT-5.6 Sol <noreply@openai.com>"
_DISPATCH = "Dispatch: 20260829T000000Z-code-codex-abc123"


class TheLauncherCommitsWithTheHarnessOwnMessage(unittest.TestCase):
    """B3: five green codex runs landed under a generic subject."""

    def setUp(self):
        self.launch = _load(self)
        self.rec = {"job": "implement", "id": "20260829T000000Z-code-codex-abc123",
                    "harness": {"name": "codex"},
                    "model": {"requested": "gpt-5.6-sol", "ran": "gpt-5.6-sol"}}

    def _git_parsed_trailers(self, message):
        """git interpret-trailers --parse with isolated config; git is the oracle."""
        env = {
            "PATH": os.defpath,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "LC_ALL": "C",
        }
        proc = subprocess.run(
            ["git", "interpret-trailers", "--parse"],
            input=message,
            text=True,
            capture_output=True,
            check=True,
            cwd="/",
            env=env,
        )
        return [line for line in proc.stdout.splitlines() if line.strip()]

    def _assert_producer_omits_prefixes(self, paragraph, *prefixes):
        producer = "docs: example\n\n" + paragraph + "\n"
        parsed = self._git_parsed_trailers(producer)
        for prefix in prefixes:
            self.assertFalse(
                any(line.startswith(prefix) for line in parsed),
                parsed,
            )

    def _assert_parsed_omits_prefixes(self, message, *prefixes):
        parsed = self._git_parsed_trailers(message)
        for prefix in prefixes:
            self.assertFalse(
                any(line.startswith(prefix) for line in parsed),
                parsed,
            )
        return parsed

    def test_subject_body_and_display_name_attribution(self):
        env = {"commit": {"subject": "infra: run jobs in the host lane",
                          "body": "Why and how.\n\nCo-Authored-By: GPT-5 Codex <noreply@openai.com>\nSource: original"}}
        msg = self.launch._commit_message(self.rec, env)
        lines = msg.rstrip("\n").splitlines()
        self.assertEqual(lines[0], "infra: run jobs in the host lane")
        self.assertIn("Why and how.", msg)
        self.assertEqual(msg.count("Co-Authored-By:"), 1)
        self.assertIn("Co-Authored-By: GPT-5.6 Sol <noreply@openai.com>", msg)
        self.assertNotIn("gpt-5.6-sol <", msg)
        self.assertIn("Dispatch: 20260829T000000Z-code-codex-abc123", msg)
        self.assertEqual(lines[-2:], ["Source: original",
                                      "Co-Authored-By: GPT-5.6 Sol <noreply@openai.com>"])

    def test_the_harness_own_source_line_is_kept_not_stripped(self):
        env = {"commit": {"subject": "x", "body": "b\n\nSource: owner 2026-08-29\nSource: original\nCo-Authored-By: GPT-5 Codex <noreply@openai.com>"}}
        msg = self.launch._commit_message(self.rec, env)
        lines = msg.rstrip("\n").splitlines()
        block_start = lines.index("Source: owner 2026-08-29")
        self.assertEqual(lines[block_start:], ["Source: owner 2026-08-29", "Source: original",
                                               "Co-Authored-By: GPT-5.6 Sol <noreply@openai.com>"])
        self.assertEqual(msg.count("Source: original"), 1)

    def test_a_second_co_author_from_the_harness_is_kept(self):
        env = {"commit": {"subject": "x", "body": "b\n\nCo-Authored-By: GPT-5 Codex <noreply@openai.com>\nCo-Authored-By: Grok 4.6 <noreply@x.ai>"}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn("Co-Authored-By: Grok 4.6 <noreply@x.ai>", msg)
        self.assertNotIn("GPT-5 Codex", msg)  # the running model's own line replaces its vendor's
        self.assertEqual(msg.count("<noreply@openai.com>"), 1)

    def test_without_a_commit_object_the_generic_subject_stands(self):
        msg = self.launch._commit_message(self.rec, {})
        self.assertTrue(msg.startswith("implement: work of dispatch 20260829T000000Z-code-codex-abc123\n"))
        self.assertIn("Co-Authored-By: GPT-5.6 Sol <noreply@openai.com>", msg)

    def test_an_unknown_model_id_is_credited_as_itself(self):
        self.rec["model"] = {"requested": "gpt-9", "ran": "gpt-9"}
        msg = self.launch._commit_message(self.rec, {"commit": {"subject": "x"}})
        self.assertIn("Co-Authored-By: gpt-9 <noreply@openai.com>", msg)

    def test_trailer_shaped_body_lines_move_into_the_final_block(self):
        env = {"commit": {"subject": "workflow: make vocabulary evidence honest",
                          "body": "Why.\n\nReviewed-by: Grok 4.6 <noreply@x.ai>\nReviewed-by: Claude Opus 5 <noreply@anthropic.com>\n\nMore why."}}
        msg = self.launch._commit_message(self.rec, env)
        lines = msg.rstrip("\n").splitlines()
        # the final block is contiguous and holds every trailer
        block_start = lines.index("Source: original")
        self.assertEqual(lines[block_start:], [
            "Source: original",
            "Reviewed-by: Grok 4.6 <noreply@x.ai>",
            "Reviewed-by: Claude Opus 5 <noreply@anthropic.com>",
            "Co-Authored-By: GPT-5.6 Sol <noreply@openai.com>",
        ])
        self.assertEqual(lines[block_start - 1], "")
        body = "\n".join(lines[2:block_start - 1])
        self.assertNotIn("Reviewed-by", body)
        self.assertIn("Why.", body)
        self.assertIn("More why.", body)

    def test_out_commit_msg_wins_over_the_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            job_dir = Path(td)
            (job_dir / "out").mkdir()
            (job_dir / "out" / "COMMIT_MSG").write_text("infra: from the file\n\nBody from file.\n")
            msg = self.launch._commit_message(self.rec, {"commit": {"subject": "from envelope"}}, job_dir)
        self.assertTrue(msg.startswith("infra: from the file\n\nBody from file.\n"))

    def test_a_blank_subject_falls_back(self):
        msg = self.launch._commit_message(self.rec, {"commit": {"subject": "   ", "body": "b"}})
        self.assertTrue(msg.startswith("implement: work of dispatch"))

    def test_wrapped_pass_prose_stays_contiguous_and_out_of_git_trailers(self):
        self._assert_producer_omits_prefixes(_WRAPPED_PASS, "pass:")
        env = {"commit": {"subject": "docs: example", "body": _WRAPPED_PASS}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn(_WRAPPED_PASS, msg)
        parsed = self._assert_parsed_omits_prefixes(msg, "pass:")
        self.assertIn("Source: original", parsed)
        self.assertIn(_OWN_COAUTHOR, parsed)
        self.assertIn(_DISPATCH, msg)

    def test_multiline_validation_prose_stays_contiguous_and_out_of_git_trailers(self):
        self._assert_producer_omits_prefixes(_VALIDATION, "Validation:")
        env = {"commit": {"subject": "docs: example", "body": _VALIDATION}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn(_VALIDATION, msg)
        self._assert_parsed_omits_prefixes(msg, "Validation:")

    def test_an_arbitrary_prose_key_is_not_a_hard_coded_exception(self):
        self._assert_producer_omits_prefixes(_ARBITRARY_KEY, "Quux:")
        env = {"commit": {"subject": "docs: example", "body": _ARBITRARY_KEY}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn(_ARBITRARY_KEY, msg)
        self._assert_parsed_omits_prefixes(msg, "Quux:")

    def test_a_known_trailer_key_inside_prose_is_not_metadata(self):
        self._assert_producer_omits_prefixes(_KNOWN_KEY_IN_PROSE, "Reviewed-by:")
        env = {"commit": {"subject": "docs: example", "body": _KNOWN_KEY_IN_PROSE}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn(_KNOWN_KEY_IN_PROSE, msg)
        parsed = self._assert_parsed_omits_prefixes(msg, "Reviewed-by:")
        self.assertIn("Source: original", parsed)

    def test_unwrapped_pass_prose_keeps_its_neighbors(self):
        self._assert_producer_omits_prefixes(_UNWRAPPED_PASS, "pass:")
        env = {"commit": {"subject": "docs: example", "body": _UNWRAPPED_PASS}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn(_UNWRAPPED_PASS, msg)
        self._assert_parsed_omits_prefixes(msg, "pass:")

    def test_json_round_trip_preserves_wrapped_prose_paragraphs(self):
        env = {"commit": {"subject": "docs: example", "body": _WRAPPED_PASS}}
        round_tripped = json.loads(json.dumps(env))
        self.assertEqual(round_tripped["commit"]["body"], _WRAPPED_PASS)
        self.assertIn("\npass: ", round_tripped["commit"]["body"])
        msg = self.launch._commit_message(self.rec, round_tripped)
        self.assertIn(_WRAPPED_PASS, msg)
        self._assert_parsed_omits_prefixes(msg, "pass:")

    def test_commit_msg_file_wins_and_keeps_wrapped_prose(self):
        envelope = {
            "commit": {
                "subject": "from envelope",
                "body": "envelope only\n" + _VALIDATION,
            },
        }
        with tempfile.TemporaryDirectory() as td:
            job_dir = Path(td)
            (job_dir / "out").mkdir()
            (job_dir / "out" / "COMMIT_MSG").write_text(
                "docs: from the file\n\n" + _WRAPPED_PASS + "\n",
            )
            msg = self.launch._commit_message(self.rec, envelope, job_dir)
        self.assertTrue(msg.startswith("docs: from the file\n"))
        self.assertIn(_WRAPPED_PASS, msg)
        self.assertNotIn("envelope only", msg)
        self.assertNotIn("from envelope", msg)
        self._assert_parsed_omits_prefixes(msg, "pass:", "Validation:")

    def test_envelope_fallback_keeps_wrapped_prose_when_the_file_is_absent(self):
        env = {"commit": {"subject": "docs: from envelope", "body": _VALIDATION}}
        with tempfile.TemporaryDirectory() as td:
            job_dir = Path(td)
            (job_dir / "out").mkdir()
            msg = self.launch._commit_message(self.rec, env, job_dir)
        self.assertTrue(msg.startswith("docs: from envelope\n"))
        self.assertIn(_VALIDATION, msg)
        self._assert_parsed_omits_prefixes(msg, "Validation:")

    def test_true_terminal_trailers_remain_while_wrapped_prose_does_not_join_them(self):
        body = _WRAPPED_PASS + "\n\n" + _TERMINAL_ACK + "\nSource: original"
        self._assert_producer_omits_prefixes(body, "pass:")
        producer = "docs: example\n\n" + body + "\n"
        self.assertIn(_TERMINAL_ACK, self._git_parsed_trailers(producer))
        env = {"commit": {"subject": "docs: example", "body": body}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn(_WRAPPED_PASS, msg)
        parsed = self._assert_parsed_omits_prefixes(msg, "pass:")
        self.assertIn(_TERMINAL_ACK, parsed)
        self.assertIn("Source: original", parsed)
        self.assertIn(_OWN_COAUTHOR, parsed)

    def test_standalone_reviewed_by_moves_while_wrapped_prose_stays(self):
        body = (
            "Why.\n\n"
            "Reviewed-by: Grok 4.6 <noreply@x.ai>\n"
            "Reviewed-by: Claude Opus 5 <noreply@anthropic.com>\n\n"
            "More why.\n\n" + _WRAPPED_PASS
        )
        env = {"commit": {"subject": "docs: example", "body": body}}
        msg = self.launch._commit_message(self.rec, env)
        self.assertIn(_WRAPPED_PASS, msg)
        self.assertIn("Why.", msg)
        self.assertIn("More why.", msg)
        lines = msg.rstrip("\n").splitlines()
        block_start = lines.index("Source: original")
        self.assertEqual(lines[block_start:], [
            "Source: original",
            "Reviewed-by: Grok 4.6 <noreply@x.ai>",
            "Reviewed-by: Claude Opus 5 <noreply@anthropic.com>",
            _OWN_COAUTHOR,
        ])
        self.assertEqual(lines[block_start - 1], "")
        body_text = "\n".join(lines[2:block_start - 1])
        self.assertNotIn("Reviewed-by", body_text)
        parsed = self._assert_parsed_omits_prefixes(msg, "pass:")
        self.assertIn("Reviewed-by: Grok 4.6 <noreply@x.ai>", parsed)
        self.assertIn("Reviewed-by: Claude Opus 5 <noreply@anthropic.com>", parsed)

    def test_collected_assembly_keeps_wrapped_prose_and_attribution(self):
        env = {
            "commit": {
                "subject": "docs: example",
                "body": (
                    _WRAPPED_PASS
                    + "\n\nSource: owner 2026-08-29\n"
                    "Source: original\n"
                    "Co-Authored-By: GPT-5 Codex <noreply@openai.com>\n"
                    "Co-Authored-By: Grok 4.6 <noreply@x.ai>"
                ),
            },
        }
        msg = self.launch._commit_message(self.rec, env, collected=True)
        self.assertIn(_WRAPPED_PASS, msg)
        self.assertIn("Source: owner 2026-08-29", msg)
        self.assertEqual(msg.count("Source: original"), 1)
        self.assertIn("Co-Authored-By: Grok 4.6 <noreply@x.ai>", msg)
        self.assertNotIn("GPT-5 Codex", msg)
        self.assertIn(_OWN_COAUTHOR, msg)
        self.assertIn(_DISPATCH, msg)
        self._assert_parsed_omits_prefixes(msg, "pass:")


class ADispatchThatEndsWithoutAnEnvelopeSaysWhy(unittest.TestCase):
    """B4: the record carried only 'no JSON object on stdout'."""

    def setUp(self):
        self.launch = _load(self)
        self._td = tempfile.TemporaryDirectory()
        self.job_dir = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _grok_events(self, lines):
        d = self.job_dir / "home" / "grok-stream" / "sessions" / "enc" / "sid"
        d.mkdir(parents=True)
        (d / "events.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        return d

    def test_a_cancelled_permission_prompt_is_named(self):
        self._grok_events([
            {"ts": "t1", "type": "permission_requested", "tool_name": "run_terminal_command"},
            {"ts": "t2", "type": "permission_resolved", "tool_name": "run_terminal_command",
             "decision": "cancelled", "wait_ms": 30002},
            {"ts": "t3", "type": "phase_changed"},
            {"ts": "t4", "type": "turn_ended"},
        ])
        rec = {"harness": {"name": "grok"}, "session": {"stream": None}}
        ended = self.launch._cause(rec, self.job_dir)
        self.assertEqual(ended["reason"], "permission-cancelled")
        self.assertEqual(ended["tool"], "run_terminal_command")
        self.assertEqual(ended["wait_ms"], 30002)

    def test_an_approved_prompt_followed_by_work_is_not_blamed(self):
        d = self._grok_events([
            {"ts": "t1", "type": "permission_requested", "tool_name": "run_terminal_command"},
            {"ts": "t2", "type": "permission_resolved", "tool_name": "run_terminal_command",
             "decision": "approved", "wait_ms": 5},
            {"ts": "t3", "type": "assistant_message"},
        ])
        rec = {"harness": {"name": "grok"}, "session": {"stream": str(d / "updates.jsonl")}}
        ended = self.launch._cause(rec, self.job_dir)
        self.assertEqual(ended["reason"], "last-event")
        self.assertEqual(ended["type"], "assistant_message")

    def test_a_recovered_prompt_is_not_blamed(self):
        self._grok_events([
            {"ts": "t1", "type": "permission_resolved", "tool_name": "run_terminal_command",
             "decision": "cancelled", "wait_ms": 30002},
            {"ts": "t2", "type": "tool_result"},
            {"ts": "t3", "type": "permission_resolved", "tool_name": "run_terminal_command",
             "decision": "approved", "wait_ms": 3},
            {"ts": "t4", "type": "assistant_message"},
            {"ts": "t5", "type": "turn_ended"},
        ])
        rec = {"harness": {"name": "grok"}, "session": {"stream": None}}
        self.assertEqual(self.launch._cause(rec, self.job_dir)["reason"], "last-event")

    def test_the_launchers_own_marker_names_the_kill_never_the_harness_prose(self):
        self._grok_events([{"ts": "t1", "type": "permission_resolved", "decision": "cancelled",
                            "tool_name": "x", "wait_ms": 1}, {"ts": "t2", "type": "turn_ended"}])
        rec = {"harness": {"name": "grok"}, "session": {"stream": None},
               "attempts": [{"exit": 137, "tripped": True}]}
        # production shape: TRIPPED.md written by the launcher, exit 137, tripped True
        (self.job_dir / "TRIPPED.md").write_text("timeout: harness exceeded 2700s\n")
        self.assertEqual(self.launch._cause(rec, self.job_dir)["reason"], "timeout")
        (self.job_dir / "TRIPPED.md").write_text("unsupervised: no session stream within grace\n")
        self.assertEqual(self.launch._cause(rec, self.job_dir)["reason"], "unsupervised")
        (self.job_dir / "TRIPPED.md").write_text("trip: cap-out 500000 exceeded\n")
        self.assertEqual(self.launch._cause(rec, self.job_dir)["reason"], "tripped")
        (self.job_dir / "TRIPPED.md").unlink()
        rec["attempts"] = [{"exit": 137, "tripped": False}]
        self.assertEqual(self.launch._cause(rec, self.job_dir)["reason"], "harness-cli:137")
        rec["attempts"] = [{"exit": 0, "tripped": False}]
        # the harness's own prose never decides the reason
        cause = self.launch._cause(rec, self.job_dir, {"status": "ok", "note": "no timeout was observed; unsupervised runs are fine"})
        self.assertEqual(cause["reason"], "permission-cancelled")

    def test_the_cancelled_tools_own_result_is_not_recovery(self):
        self._grok_events([
            {"ts": "t1", "type": "permission_requested", "tool_name": "run_terminal_command"},
            {"ts": "t2", "type": "permission_resolved", "tool_name": "run_terminal_command",
             "decision": "cancelled", "wait_ms": 30002},
            {"ts": "t2b", "type": "tool_result"},
            {"ts": "t3", "type": "phase_changed"},
            {"ts": "t4", "type": "turn_ended"},
        ])
        rec = {"harness": {"name": "grok"}, "session": {"stream": None}}
        self.assertEqual(self.launch._cause(rec, self.job_dir)["reason"], "permission-cancelled")

    def test_a_claude_stream_reports_its_last_event(self):
        stream = self.job_dir / "session.jsonl"
        stream.write_text('{"type":"user","timestamp":"a"}\n{"type":"result","timestamp":"b"}\n')
        rec = {"harness": {"name": "claude"}, "session": {"stream": str(stream)}}
        ended = self.launch._cause(rec, self.job_dir)
        self.assertEqual(ended, {"reason": "last-event", "type": "result", "at": "b"})

    def test_no_store_is_said_not_guessed(self):
        rec = {"harness": {"name": "codex"}, "session": {"stream": None}}
        self.assertEqual(self.launch._cause(rec, self.job_dir)["reason"], "no-session-store")


class WhatAHarnessLeavesUncommittedIsPreserved(unittest.TestCase):
    """B4: the conductor diffed a dead dispatch's snapshot by hand."""

    def setUp(self):
        self.launch = _load(self)
        self._td = tempfile.TemporaryDirectory()
        self.repo = Path(self._td.name) / "snap"
        self.job_dir = Path(self._td.name)
        self.repo.mkdir()
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        self.env = env
        for args in (("init", "-q"), ):
            subprocess.run(["git", *args], cwd=self.repo, check=True, env=env)
        (self.repo / "a.txt").write_text("one\n")
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True, env=env)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=self.repo, check=True, env=env)

    def tearDown(self):
        self._td.cleanup()

    def test_tracked_edits_and_untracked_files_land_in_residual_patch(self):
        (self.repo / "a.txt").write_text("two\n")
        (self.repo / "new.py").write_text("print(1)\n")
        salvage = self.launch._write_residual_patch(self.repo, self.job_dir)
        text = Path(salvage["path"]).read_text()
        self.assertIn("-one", text)
        self.assertIn("+two", text)
        self.assertIn("+++ b/new.py", text)
        self.assertIn("print(1)", text)
        self.assertEqual(salvage["untracked"], ["new.py"])
        self.assertEqual(salvage["sha256"], ls.sha256_file(Path(salvage["path"])))

    def test_tool_caches_are_not_in_the_patch_either(self):
        (self.repo / ".ruff_cache").mkdir()
        (self.repo / ".ruff_cache" / "x").write_text("c")
        (self.repo / "real.txt").write_text("r")
        salvage = self.launch._write_residual_patch(self.repo, self.job_dir)
        text = Path(salvage["path"]).read_text()
        self.assertIn("real.txt", text)
        self.assertNotIn(".ruff_cache", text)

    def test_tool_caches_are_not_residual(self):
        (self.repo / ".ruff_cache").mkdir()
        (self.repo / ".ruff_cache" / "x").write_text("c")
        (self.repo / "pkg" / "__pycache__").mkdir(parents=True)
        (self.repo / "pkg" / "__pycache__" / "m.pyc").write_bytes(b"\x00")
        self.assertEqual(self.launch._residual(self.repo), [])
        (self.repo / "real.txt").write_text("r")
        self.assertEqual([line[3:] for line in self.launch._residual(self.repo)], ["real.txt"])


if __name__ == "__main__":
    unittest.main()
