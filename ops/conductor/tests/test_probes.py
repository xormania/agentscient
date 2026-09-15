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

World owns HOME and the XDG roots; every subprocess goes through run;
fake sibling programs are planted through world.tools.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from ops.testkit import World, make_executable, run

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "probes.py"
SUBJECT_TOOL = TOOL
ABSENT_STUB = (
    "import json, sys\n"
    "print(json.dumps({'commit': 'dead', 'rows': [], "
    "'counts': {'pass': 0, 'fail': 0, 'unreachable': 0}}))\n"
    "sys.exit(1)\n"
)
CORPUS_DIR = Path("ops/conductor/handoff/probes")
SIBLINGS = ("instrument.py", "laneconf.py")
RUN_TIMEOUT = 60
LIVE_TIMEOUT = 600
STRIPPED_AGENT = "Should Be Stripped <strip@example.invalid>"


class _Fixture(unittest.TestCase):
    """A disposable repository with its own corpus directory."""

    def setUp(self):
        self.world = World(prefix="probes-")
        self.addCleanup(self.world.close)
        self.world.require("git")
        self.root = self.world.cwd
        self.world.git("init", "-q", "-b", "trunk", cwd=self.root)
        self.world.plant_text(
            self.root / "notes.md", "alpha lives here\nthe sky is blue\n",
        )
        tools = self.root / "ops" / "conductor" / "tools"
        tools.mkdir(parents=True)
        self._plant_fake(tools / "served.py", "served", stdout="served: forty-two\n")
        self._plant_fake(tools / "slow.py", "slow", stdout="", exit=0, delay=5.0)
        self._plant_fake(tools / "loud.py", "loud", stdout="x\n", exit=0)
        (self.root / CORPUS_DIR).mkdir(parents=True)
        self.world.git("add", "-A", cwd=self.root)
        self.world.git("commit", "-q", "-m", "fixture", cwd=self.root)
        short = self.world.git("rev-parse", "--short", "HEAD", cwd=self.root)
        self.short = short.stdout.strip()
        siblings = SIBLINGS if SUBJECT_TOOL.is_file() else ()
        self.staged = self.world.stage(
            SUBJECT_TOOL, "probes.py", siblings=siblings,
        )
        if not SUBJECT_TOOL.is_file():
            self.world.plant_text(self.staged, ABSENT_STUB)

    def _plant_fake(self, dest, name, **spec):
        fake = self.world.tools.plant(name, **spec)
        planted = self.world.plant_bytes(dest, fake.read_bytes())
        make_executable(planted)
        return planted

    def rows(self, name, rows):
        path = self.root / CORPUS_DIR / name
        self.world.plant_text(
            path, "".join(json.dumps(r) + "\n" for r in rows),
        )
        return path

    def run_tool(self, *argv, env=None):
        extra = {"WF_AGENT": STRIPPED_AGENT}
        if env is not None and "PROBES_TIMEOUT" in env:
            extra["PROBES_TIMEOUT"] = env["PROBES_TIMEOUT"]
        return run(
            [sys.executable, str(self.staged), *argv],
            cwd=str(self.root),
            env=self.world.env(extra=extra),
            timeout=RUN_TIMEOUT,
        )

    def assert_refusal(self, proc, klass):
        wire = proc.refusal(exit=2)
        self.assertEqual(wire.cls, klass, wire.line)
        self.assertTrue(wire.line.startswith(f"{klass}: expected "), wire.line)
        self.assertIn("; found ", wire.line)
        self.assertIn("; needed ", wire.line)
        return wire.line

    def report(self, proc):
        self.assertIn(proc.exit, (0, 1), proc.stdout + proc.stderr)
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
        self.assertEqual(proc.exit, 0, proc.stdout)
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
        self.assertEqual(proc.exit, 1)
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
        env = dict(PROBES_TIMEOUT="0.3")
        doc = self.report(self.run_tool("run", env=env))
        self.assertEqual([r["result"] for r in doc["rows"]], ["PASS", "UNREACHABLE"])
        self.assertIn("timeout", doc["rows"][1]["detail"])

    def test_rows_run_with_wf_agent_stripped(self):
        # Kit gap: Tools.plant cannot print an env var; this one-line
        # subject has to read WF_AGENT.
        self.world.plant_text(
            self.root / "ops/conductor/tools/whoami.py",
            "import os; print('agent=' + os.environ.get('WF_AGENT', 'none'))\n",
        )
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

    def test_an_rg_option_that_spawns_a_process_refuses_before_any_row_runs(self):
        """Codex review of PR #158 (2026-09-12): `rg --pre COMMAND` searches
        the output of `COMMAND PATH`, spawning it for every file, so a
        nominally read-only row could run a writer on the self-hosted
        runner; `--pre-glob` and `-z`/`--search-zip` spawn the same way."""
        witness = self.root / "witness"
        pre = self.root / "pre.sh"
        # Kit gap: Tools.plant cannot express "touch a path then cat $1".
        self.world.plant_text(pre, "#!/bin/sh\ntouch witness\ncat \"$1\"\n")
        pre.chmod(0o755)
        for command in ("rg --pre ./pre.sh alpha notes.md",
                        "rg --pre=./pre.sh alpha notes.md",
                        "rg --pre ./pre.sh --pre-glob '*.md' alpha notes.md",
                        "rg -z alpha notes.md",
                        "rg -cz alpha notes.md",
                        "rg --search-zip alpha notes.md"):
            self.rows("p.jsonl", [dict(SERVE, serve=command, expect="alpha")])
            line = self.assert_refusal(self.run_tool("run"), "corpus")
            self.assertIn("P-T-serve", line)
            self.assertIn("spawn", line)
            self.assertFalse(witness.exists(), command)

    def test_rg_options_that_only_read_stay_allowed(self):
        self.rows("p.jsonl", [dict(ABSENT, absent="rg -c -eomega notes.md"),
                              dict(SERVE, id="P-T-fixed", serve="rg -F -n alpha -- notes.md",
                                   expect="alpha")])
        doc = self.report(self.run_tool("run"))
        self.assertEqual(doc["counts"], {"pass": 2, "fail": 0, "unreachable": 0})

    def test_duplicate_id_refuses(self):
        self.rows("p.jsonl", [SERVE, dict(SERVE)])
        line = self.assert_refusal(self.run_tool("run"), "corpus")
        self.assertIn("P-T-serve", line)

    def test_blank_or_non_json_line_refuses(self):
        self.world.plant_text(
            self.root / CORPUS_DIR / "p.jsonl",
            json.dumps(SERVE) + "\n\nnot json\n",
        )
        self.assert_refusal(self.run_tool("run"), "corpus")

    def test_an_expect_that_spans_lines_refuses(self):
        """Pitfall 30 (2026-09-13): an expect pinning two entries of a sorted
        list as adjacent breaks when any session inserts a neighbour. The
        corpus refuses the shape; a row pins one line."""
        for row in (dict(SERVE, expect="alpha lives here\nthe sky is blue"),
                    dict(NEARMISS, expect="the sky is blue\n")):
            with self.subTest(id=row["id"]):
                self.rows("p.jsonl", [row])
                line = self.assert_refusal(self.run_tool("run"), "corpus")
                self.assertIn(row["id"], line)
                self.assertIn("one line", line)

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
        self.assertEqual(proc.exit, 0, proc.stderr)
        lines = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual([set(x) for x in lines], [{"id", "question"}] * 3)
        self.assertEqual([x["id"] for x in lines], ["P-T-serve", "P-T-absent", "P-T-near"])
        for secret in ("alpha lives here", "omega", "the sky is blue", "git show"):
            self.assertNotIn(secret, proc.stdout)


class GradeRulesArmB(_Fixture):
    def answers(self, rows):
        path = self.world.tmp / "answers.jsonl"
        self.world.plant_text(path, "".join(json.dumps(r) + "\n" for r in rows))
        return str(path)

    def test_grade_passes_a_correct_answer_set(self):
        self.rows("p.jsonl", [SERVE, ABSENT, NEARMISS])
        proc = self.run_tool("grade", self.answers([
            {"id": "P-T-serve", "status": "SERVED", "answer": "alpha lives here, per notes"},
            {"id": "P-T-absent", "status": "ABSENT"},
            {"id": "P-T-near", "status": "SERVED", "answer": "no: the sky is blue"},
        ]))
        doc = self.report(proc)
        self.assertEqual(proc.exit, 0)
        self.assertEqual(doc["counts"], {"pass": 3, "fail": 0, "unreachable": 0})

    def test_confabulation_unanswered_and_accepted_premise_fail(self):
        self.rows("p.jsonl", [SERVE, ABSENT, NEARMISS])
        proc = self.run_tool("grade", self.answers([
            {"id": "P-T-absent", "status": "SERVED", "answer": "omega is in the notes"},
            {"id": "P-T-near", "status": "SERVED", "answer": "yes, green"},
        ]))
        doc = self.report(proc)
        self.assertEqual(proc.exit, 1)
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
        with World(ambient=("GH_TOKEN",), prefix="probes-live-") as world:
            siblings = SIBLINGS if SUBJECT_TOOL.is_file() else ()
            staged = world.stage(SUBJECT_TOOL, "probes.py", siblings=siblings)
            if not SUBJECT_TOOL.is_file():
                world.plant_text(staged, ABSENT_STUB)
            proc = run(
                [sys.executable, str(staged), "run"],
                cwd=str(REPO),
                env=world.env(),
                timeout=LIVE_TIMEOUT,
            )
        self.assertEqual(proc.stderr, "", proc.stderr)
        doc = json.loads(proc.stdout)
        bad = [r for r in doc["rows"] if r["result"] != "PASS"]
        self.assertEqual(proc.exit, 0, json.dumps(bad, indent=1))


if __name__ == "__main__":
    unittest.main()
