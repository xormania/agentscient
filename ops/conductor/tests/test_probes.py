"""probes.py — the corpus runner of probes-lever.md (D-OPS-11, ratified
2026-09-01, never built until 2026-09-12).

Owner, 2026-09-12: "there seems to be a huge disconnect between what i've
been told and reality - and it needs to fucking stop - right fucking now
- hand grants - i want it fixed for real"; "it has to be made impossible".
Measured that day: the lever page named `probes.py` with run/ask/grade
and 38 corpus rows sat under ops/conductor/handoff/probes/ with no
runner in the tree or its history.

Written from probes-lever.md alone. One producer (Claude Fable 5.1)
under hand grant 157 wrote these tests and the instrument; the second
producer is absent by the owner's word (AGENTS.md §Ground rules).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "probes.py"
CORPUS_DIR = Path("ops/conductor/handoff/probes")


def _git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True,
    ).stdout


class _Fixture(unittest.TestCase):
    """A disposable repository with its own corpus directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        _git(self.root, "init", "-q", "-b", "trunk")
        _git(self.root, "config", "user.email", "fixture@example.invalid")
        _git(self.root, "config", "user.name", "Fixture")
        (self.root / "notes.md").write_text("alpha lives here\nthe sky is blue\n")
        tools = self.root / "ops" / "conductor" / "tools"
        tools.mkdir(parents=True)
        (tools / "served.py").write_text("print('served: forty-two')\n")
        (tools / "slow.py").write_text("import time; time.sleep(5)\n")
        (tools / "loud.py").write_text("import sys; print('x'); sys.exit(0)\n")
        (self.root / CORPUS_DIR).mkdir(parents=True)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "fixture")
        self.short = _git(self.root, "rev-parse", "--short", "HEAD").strip()
        self.env = {k: v for k, v in os.environ.items() if k != "WF_AGENT"}
        self.env["WF_AGENT"] = "Should Be Stripped <strip@example.invalid>"

    def rows(self, name, rows):
        path = self.root / CORPUS_DIR / name
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return path

    def run_tool(self, *argv, env=None):
        return subprocess.run(
            [sys.executable, str(TOOL), *argv], cwd=self.root,
            capture_output=True, text=True, env=env or self.env, timeout=60,
        )

    def assert_refusal(self, proc, klass):
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout, "")
        lines = proc.stderr.splitlines()
        self.assertEqual(len(lines), 1, proc.stderr)
        line = lines[0]
        self.assertTrue(line.startswith(f"{klass}: expected "), line)
        self.assertIn("; found ", line)
        self.assertIn("; needed ", line)
        return line

    def report(self, proc):
        self.assertIn(proc.returncode, (0, 1), proc.stdout + proc.stderr)
        self.assertEqual(proc.stderr, "", proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertEqual(set(doc), {"commit", "rows", "counts"})
        self.assertEqual(doc["commit"], self.short)
        self.assertEqual(set(doc["counts"]), {"pass", "fail", "unreachable"})
        for row in doc["rows"]:
            self.assertEqual(set(row), {"id", "kind", "lane", "result", "detail"})
            if row["result"] == "PASS":
                self.assertEqual(row["detail"], "")
        return doc


SERVE = {"id": "P-T-serve", "kind": "serve", "lane": "git",
         "question": "Where does alpha live?",
         "serve": "git show HEAD:notes.md", "expect": "alpha lives here"}
ABSENT = {"id": "P-T-absent", "kind": "absent", "lane": "none",
          "question": "Is the secret in the notes?",
          "absent": "rg -c omega notes.md"}
NEARMISS = {"id": "P-T-near", "kind": "nearmiss", "lane": "aar",
            "question": "The sky is green, right?",
            "premise_flaw": "the sky is blue",
            "serve": "git show HEAD:notes.md", "expect": "the sky is blue"}
SIBLING = {"id": "P-T-sibling", "kind": "serve", "lane": "none",
           "question": "What does the sibling serve?",
           "serve": "python3 ops/conductor/tools/served.py",
           "expect": "forty-two"}


class RunPassesACleanCorpus(_Fixture):
    def test_every_kind_passes_and_exit_is_zero(self):
        self.rows("probes-a.jsonl", [SERVE, ABSENT])
        self.rows("probes-b.jsonl", [NEARMISS, SIBLING])
        proc = self.run_tool("run")
        doc = self.report(proc)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual([r["id"] for r in doc["rows"]],
                         ["P-T-serve", "P-T-absent", "P-T-near", "P-T-sibling"],
                         "files in name order, rows in file order")
        self.assertEqual({r["result"] for r in doc["rows"]}, {"PASS"})
        self.assertEqual(doc["counts"], {"pass": 4, "fail": 0, "unreachable": 0})
        self.assertEqual([r["kind"] for r in doc["rows"]],
                         ["serve", "absent", "nearmiss", "serve"])
        self.assertEqual(doc["rows"][2]["lane"], "aar")


class RunReportsFailAndUnreachable(_Fixture):
    def test_serve_without_expect_is_fail(self):
        self.rows("p.jsonl", [dict(SERVE, expect="not in the notes")])
        doc = self.report(self.run_tool("run"))
        self.assertEqual(doc["rows"][0]["result"], "FAIL")
        self.assertEqual(doc["counts"], {"pass": 0, "fail": 1, "unreachable": 0})

    def test_nonzero_exit_is_unreachable_not_fail(self):
        self.rows("p.jsonl", [dict(SERVE, serve="git show HEAD:no-such-file")])
        proc = self.run_tool("run")
        doc = self.report(proc)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(doc["rows"][0]["result"], "UNREACHABLE")
        self.assertTrue(doc["rows"][0]["detail"])
        self.assertEqual(doc["counts"]["unreachable"], 1)

    def test_absent_with_stdout_is_fail_quoting_the_first_line(self):
        self.rows("p.jsonl", [dict(ABSENT, absent="rg -c alpha notes.md")])
        doc = self.report(self.run_tool("run"))
        self.assertEqual(doc["rows"][0]["result"], "FAIL")
        self.assertIn("1", doc["rows"][0]["detail"])

    def test_absent_with_stderr_is_unreachable(self):
        self.rows("p.jsonl", [dict(ABSENT, absent="rg -c omega no-such-file.md")])
        doc = self.report(self.run_tool("run"))
        self.assertEqual(doc["rows"][0]["result"], "UNREACHABLE")

    def test_timeout_is_unreachable_on_its_line(self):
        self.rows("p.jsonl", [SERVE, dict(SIBLING, id="P-T-slow",
                                          serve="python3 ops/conductor/tools/slow.py")])
        env = dict(self.env, PROBES_TIMEOUT="0.3")
        doc = self.report(self.run_tool("run", env=env))
        self.assertEqual([r["result"] for r in doc["rows"]], ["PASS", "UNREACHABLE"])
        self.assertIn("timeout", doc["rows"][1]["detail"])

    def test_rows_run_with_wf_agent_stripped(self):
        (self.root / "ops/conductor/tools/whoami.py").write_text(
            "import os; print('agent=' + os.environ.get('WF_AGENT', 'none'))\n")
        self.rows("p.jsonl", [dict(SIBLING, serve="python3 ops/conductor/tools/whoami.py",
                                   expect="agent=none")])
        doc = self.report(self.run_tool("run"))
        self.assertEqual(doc["rows"][0]["result"], "PASS")


class CorpusRefusals(_Fixture):
    def test_no_corpus_file_refuses_corpus(self):
        self.assert_refusal(self.run_tool("run"), "corpus")

    def test_command_outside_the_allowlist_refuses_before_any_row_runs(self):
        witness = self.root / "witness"
        self.rows("p.jsonl", [
            dict(SIBLING, id="P-T-bad", serve="cat notes.md"),
            dict(SIBLING, id="P-T-touch",
                 serve="python3 ops/conductor/tools/loud.py"),
        ])
        line = self.assert_refusal(self.run_tool("run"), "corpus")
        self.assertIn("P-T-bad", line)
        self.assertFalse(witness.exists())

    def test_git_verb_outside_the_read_set_refuses(self):
        self.rows("p.jsonl", [dict(SERVE, serve="git commit -m x")])
        self.assert_refusal(self.run_tool("run"), "corpus")

    def test_a_pipe_is_malformed(self):
        self.rows("p.jsonl", [dict(SERVE, serve="git show HEAD:notes.md | rg alpha")])
        self.assert_refusal(self.run_tool("run"), "corpus")

    def test_duplicate_id_refuses(self):
        self.rows("p.jsonl", [SERVE, dict(SERVE)])
        line = self.assert_refusal(self.run_tool("run"), "corpus")
        self.assertIn("P-T-serve", line)

    def test_blank_or_non_json_line_refuses(self):
        (self.root / CORPUS_DIR / "p.jsonl").write_text(json.dumps(SERVE) + "\n\nnot json\n")
        self.assert_refusal(self.run_tool("run"), "corpus")

    def test_missing_field_for_kind_refuses(self):
        row = dict(NEARMISS)
        del row["premise_flaw"]
        self.rows("p.jsonl", [row])
        self.assert_refusal(self.run_tool("run"), "corpus")
        self.rows("p.jsonl", [dict(SERVE, expect="")])
        self.assert_refusal(self.run_tool("run"), "corpus")
        self.rows("p.jsonl", [dict(SERVE, id="X-no-prefix")])
        self.assert_refusal(self.run_tool("run"), "corpus")
        self.rows("p.jsonl", [dict(SERVE, lane="nowhere")])
        self.assert_refusal(self.run_tool("run"), "corpus")

    def test_unknown_verb_and_extra_argument_refuse_arguments(self):
        self.rows("p.jsonl", [SERVE])
        self.assert_refusal(self.run_tool("bogus"), "arguments")
        self.assert_refusal(self.run_tool("run", "extra"), "arguments")
        self.assert_refusal(self.run_tool("grade"), "arguments")
        self.assert_refusal(self.run_tool(), "arguments")


class AskIsTheStagingSurface(_Fixture):
    def test_ask_strips_every_key_field(self):
        self.rows("p.jsonl", [SERVE, ABSENT, NEARMISS])
        proc = self.run_tool("ask")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual([set(x) for x in lines], [{"id", "question"}] * 3)
        self.assertEqual([x["id"] for x in lines], ["P-T-serve", "P-T-absent", "P-T-near"])
        for secret in ("alpha lives here", "omega", "the sky is blue", "git show"):
            self.assertNotIn(secret, proc.stdout)


class GradeRulesArmB(_Fixture):
    def answers(self, rows):
        path = Path(self.tmp.name) / "answers.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return str(path)

    def test_grade_passes_a_correct_answer_set(self):
        self.rows("p.jsonl", [SERVE, ABSENT, NEARMISS])
        proc = self.run_tool("grade", self.answers([
            {"id": "P-T-serve", "status": "SERVED", "answer": "alpha lives here, per notes"},
            {"id": "P-T-absent", "status": "ABSENT"},
            {"id": "P-T-near", "status": "SERVED", "answer": "no: the sky is blue"},
        ]))
        doc = self.report(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(doc["counts"], {"pass": 3, "fail": 0, "unreachable": 0})

    def test_confabulation_unanswered_and_accepted_premise_fail(self):
        self.rows("p.jsonl", [SERVE, ABSENT, NEARMISS])
        proc = self.run_tool("grade", self.answers([
            {"id": "P-T-absent", "status": "SERVED", "answer": "omega is in the notes"},
            {"id": "P-T-near", "status": "SERVED", "answer": "yes, green"},
        ]))
        doc = self.report(proc)
        self.assertEqual(proc.returncode, 1)
        by = {r["id"]: r for r in doc["rows"]}
        self.assertEqual(by["P-T-serve"]["result"], "FAIL")
        self.assertEqual(by["P-T-serve"]["detail"], "unanswered")
        self.assertEqual(by["P-T-absent"]["result"], "FAIL")
        self.assertEqual(by["P-T-near"]["result"], "FAIL")
        self.assertEqual(doc["counts"], {"pass": 0, "fail": 3, "unreachable": 0})

    def test_answers_refusals(self):
        self.rows("p.jsonl", [SERVE])
        self.assert_refusal(self.run_tool("grade", str(self.root / "nope.jsonl")), "answers")
        self.assert_refusal(self.run_tool("grade", self.answers([
            {"id": "P-T-serve", "status": "MAYBE", "answer": "x"}])), "answers")
        self.assert_refusal(self.run_tool("grade", self.answers([
            {"id": "P-T-unknown", "status": "ABSENT"}])), "answers")
        self.assert_refusal(self.run_tool("grade", self.answers([
            {"id": "P-T-serve", "status": "SERVED", "answer": "a"},
            {"id": "P-T-serve", "status": "SERVED", "answer": "b"}])), "answers")
        self.assert_refusal(self.run_tool("grade", self.answers([
            {"id": "P-T-serve", "status": "SERVED"}])), "answers")


class TheTrackedCorpusRunsGreen(unittest.TestCase):
    """The repository's own corpus: every row PASS on this tree, or the
    tree is telling a story its records do not serve. This is the gate
    CI runs; it is what makes "done" a reading instead of a sentence."""

    def test_run_over_the_tracked_corpus_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(TOOL), "run"], cwd=REPO,
            capture_output=True, text=True, timeout=600,
        )
        self.assertEqual(proc.stderr, "", proc.stderr)
        doc = json.loads(proc.stdout)
        bad = [r for r in doc["rows"] if r["result"] != "PASS"]
        self.assertEqual(proc.returncode, 0, json.dumps(bad, indent=1))


if __name__ == "__main__":
    unittest.main()
