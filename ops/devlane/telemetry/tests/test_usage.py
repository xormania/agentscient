"""The usage reporter, against fixtures shaped like the real session stores.

Each fixture replicates a shape measured on 2026-08-21 from the live
stores: Claude's per-message usage, Codex's cumulative token_count events,
and Grok's summary.json — which records NO token usage, a gap the report
must state rather than estimate around.
"""

import json
import sys
import unittest
from pathlib import Path
from urllib.parse import quote

from ops.testkit import World, run

USAGE = Path(__file__).resolve().parents[1] / "usage.py"
REPO = "/home/work/projects/uscient/agentscient"


def line(**kw):
    return json.dumps(kw) + "\n"


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.home = self.world.home

        # Claude: <dir>/<project-slug>/<session>.jsonl, usage per message.
        proj = self.home / "claude" / "-home-work-projects-uscient-agentscient"
        self.world.plant_text(
            proj / "aaaa.jsonl",
            line(timestamp="2026-08-21T10:00:00.000Z",
                 message={"model": "claude-fable-5",
                          "usage": {"input_tokens": 10,
                                    "cache_creation_input_tokens": 1000,
                                    "cache_read_input_tokens": 5000,
                                    "output_tokens": 200}})
            + line(timestamp="2026-08-21T10:05:00.000Z",
                   message={"model": "claude-fable-5",
                            "usage": {"input_tokens": 20,
                                      "cache_creation_input_tokens": 0,
                                      "cache_read_input_tokens": 6000,
                                      "output_tokens": 300}}))
        other = self.home / "claude" / "-somewhere-else"
        self.world.plant_text(
            other / "bbbb.jsonl",
            line(timestamp="2026-08-21T09:00:00.000Z",
                 message={"model": "claude-fable-5",
                          "usage": {"input_tokens": 999, "output_tokens": 999}}))

        # Codex: sessions/Y/M/D/rollout-*.jsonl, cumulative token_count.
        day = self.home / "codex" / "sessions" / "2026" / "08" / "21"
        self.world.plant_text(
            day / "rollout-2026-08-21T10-00-00-cccc.jsonl",
            line(timestamp="2026-08-21T10:00:00.000Z", type="session_meta",
                 payload={"id": "cccc", "cwd": REPO,
                          "timestamp": "2026-08-21T10:00:00.000Z"})
            + line(timestamp="2026-08-21T10:02:00.000Z", type="event_msg",
                   payload={"type": "token_count",
                            "info": {"total_token_usage": {
                                "input_tokens": 100, "cached_input_tokens": 50,
                                "output_tokens": 40, "total_tokens": 140}}})
            + line(timestamp="2026-08-21T10:09:00.000Z", type="event_msg",
                   payload={"type": "token_count",
                            "info": {"total_token_usage": {
                                "input_tokens": 400, "cached_input_tokens": 300,
                                "output_tokens": 90, "total_tokens": 490}}}))

        # Grok: sessions/<urlencoded-cwd>/<id>/summary.json — no tokens.
        gdir = (self.home / "grok" / "sessions"
                / quote(REPO, safe="") / "dddd")
        self.world.plant_text(gdir / "summary.json", json.dumps({
            "info": {"id": "dddd", "cwd": REPO},
            "session_summary": "SESSIONPROMPTTEXT", "num_messages": 177,
            "created_at": "2026-08-21T10:00:00.000000000Z",
            "updated_at": "2026-08-21T10:20:00.000000000Z",
            "current_model_id": "grok-4.6",
            "git_root_dir": REPO + "/"}))

    def run_usage(self, *args):
        return run(
            [sys.executable, str(USAGE), *args,
             "--claude-dir", str(self.home / "claude"),
             "--codex-dir", str(self.home / "codex"),
             "--grok-dir", str(self.home / "grok"),
             "--repo", REPO],
            cwd=self.world.cwd,
            env=self.world.env(),
            timeout=30,
        )

    def sessions(self):
        proc = self.run_usage("sessions", "--json")
        self.assertEqual(proc.exit, 0, proc.stderr)
        return json.loads(proc.stdout)["sessions"]


class SessionsAreNormalised(Fixtures):
    def test_all_three_harnesses_appear_once(self):
        rows = self.sessions()
        self.assertEqual(sorted(r["harness"] for r in rows),
                         ["claude", "codex", "grok"])

    def test_the_repo_filter_excludes_other_projects(self):
        for row in self.sessions():
            self.assertNotEqual(row.get("session"), "bbbb",
                                "a session from another repo leaked in")

    def test_claude_tokens_are_summed_per_message(self):
        row = next(r for r in self.sessions() if r["harness"] == "claude")
        self.assertEqual(row["tokens"]["output"], 500)
        self.assertEqual(row["tokens"]["input"], 30)
        self.assertEqual(row["tokens"]["cached"], 12000)

    def test_codex_takes_the_last_cumulative_count(self):
        row = next(r for r in self.sessions() if r["harness"] == "codex")
        self.assertEqual(row["tokens"]["total"], 490,
                         "cumulative counts must not be summed")
        self.assertEqual(row["tokens"]["output"], 90)

    def test_grok_states_its_gap_instead_of_inventing(self):
        row = next(r for r in self.sessions() if r["harness"] == "grok")
        self.assertIsNone(row["tokens"])
        self.assertIn("not yet parsed", row["note"])
        self.assertEqual(row["messages"], 177)
        self.assertEqual(row["model"], "grok-4.6")


class TheRepoPathIsResolvedAtTheBoundary(unittest.TestCase):
    """Origin LD-44 / T-63: `--repo .` from inside the checkout read no
    sessions at all, because collect() handed the readers a relative path
    to compare against the transcripts' absolute cwd. Silence is not a
    declaration: the relative form must read what the absolute one reads.
    worth.py took abspath at the boundary in abf766b5; usage.py takes the
    same one."""

    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.home = self.world.home
        self.repo = self.world.cwd / "checkout"
        # Planting the file makes the directory and proves it landed.
        self.world.plant_text(self.repo / "README.md", "checkout fixture\n")
        slug = "-" + "-".join(str(self.repo).strip("/").split("/"))
        self.world.plant_text(
            self.home / "claude" / slug / "eeee.jsonl",
            line(timestamp="2026-08-21T10:00:00.000Z",
                 message={"model": "claude-fable-5",
                          "usage": {"input_tokens": 7,
                                    "cache_creation_input_tokens": 0,
                                    "cache_read_input_tokens": 0,
                                    "output_tokens": 11}}))

    def _sessions(self, repo_arg, cwd):
        proc = run(
            [sys.executable, str(USAGE), "sessions", "--json",
             "--claude-dir", str(self.home / "claude"),
             "--codex-dir", str(self.home / "codex"),
             "--grok-dir", str(self.home / "grok"),
             "--repo", repo_arg],
            cwd=cwd,
            env=self.world.env(),
            timeout=30,
        )
        self.assertEqual(proc.exit, 0, proc.stderr)
        return [row["session"] for row in json.loads(proc.stdout)["sessions"]]

    def test_a_relative_repo_reads_what_the_absolute_one_reads(self):
        self.assertEqual(
            self._sessions(str(self.repo), self.repo), ["eeee"],
            "the absolute form did not read the planted session",
        )
        self.assertEqual(
            self._sessions(".", self.repo), ["eeee"],
            "--repo . read no sessions for the checkout it ran in",
        )
        self.assertEqual(
            self._sessions("checkout", self.world.cwd), ["eeee"],
            "a relative path named from the parent read no sessions",
        )


class ACwdInsideTheRepoIsTheRepo(unittest.TestCase):
    """The comparison is containment, not string equality.

    All four readers asked whether the cwd was the repo path exactly, so
    a session that worked from a subdirectory of the repo counted for no
    repo at all. Measured 2026-09-16 across 243 claude sessions on this
    host, no session is dropped by this today — every session that
    starts at the root keeps the root in its cwd set forever. The rule
    is still wrong, and an exact compare on a path is the kind of wrong
    that is invisible until the day it is not.
    """

    SUB = REPO + "/ops/conductor"
    SIBLING = REPO + "-other"

    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.home = self.world.home

    def usage(self, *args):
        return run(
            [sys.executable, str(USAGE), *args,
             "--claude-dir", str(self.home / "claude"),
             "--codex-dir", str(self.home / "codex"),
             "--grok-dir", str(self.home / "grok"),
             "--repo", REPO, "--json"],
            cwd=self.world.cwd, env=self.world.env(), timeout=30,
        )

    def ids(self):
        proc = self.usage("sessions")
        self.assertEqual(proc.exit, 0, proc.stderr)
        return sorted(s["session"] for s in json.loads(proc.stdout)["sessions"])

    @staticmethod
    def slug(cwd):
        """Claude's own spelling of a cwd as a project directory name."""
        return "-" + "-".join(cwd.strip("/").split("/"))

    def plant_claude(self, name, cwd):
        # The directory name matters: it is the first of the two filters,
        # and inventing one would let a row pass or fail for a reason the
        # defect has nothing to do with.
        self.world.plant_text(
            self.home / "claude" / self.slug(cwd) / f"{name}.jsonl",
            line(timestamp="2026-08-21T10:00:00.000Z", cwd=cwd,
                 message={"id": f"m-{name}", "model": "claude-fable-5",
                          "usage": {"input_tokens": 10, "output_tokens": 20}}))

    def plant_codex(self, name, cwd):
        day = self.home / "codex" / "sessions" / "2026" / "08" / "21"
        self.world.plant_text(
            day / f"rollout-2026-08-21T10-00-00-{name}.jsonl",
            line(timestamp="2026-08-21T10:00:00.000Z", type="session_meta",
                 payload={"id": name, "cwd": cwd})
            + line(timestamp="2026-08-21T10:02:00.000Z", type="event_msg",
                   payload={"type": "token_count",
                            "info": {"total_token_usage": {
                                "input_tokens": 1, "cached_input_tokens": 0,
                                "output_tokens": 1, "total_tokens": 2}}}))

    def plant_grok(self, name, cwd):
        gdir = self.home / "grok" / "sessions" / quote(cwd, safe="") / name
        self.world.plant_text(gdir / "summary.json", json.dumps({
            "info": {"id": name, "cwd": cwd}, "num_messages": 3,
            "created_at": "2026-08-21T10:00:00.000000000Z",
            "updated_at": "2026-08-21T10:20:00.000000000Z",
            "current_model_id": "grok-4.6"}))

    def test_a_claude_session_run_from_a_subdirectory_counts(self):
        self.plant_claude("inside", self.SUB)
        self.assertIn("inside", self.ids())

    def test_a_codex_session_run_from_a_subdirectory_counts(self):
        self.plant_codex("inside", self.SUB)
        self.assertIn("inside", self.ids())

    def test_a_grok_session_run_from_a_subdirectory_counts(self):
        self.plant_grok("inside", self.SUB)
        self.assertIn("inside", self.ids())

    def test_a_sibling_path_that_merely_shares_a_prefix_is_not_the_repo(self):
        # The containment test is on path components, not on characters:
        # <repo>-other starts with the repo's spelling and is a different
        # checkout. A prefix compare would silently absorb its spend. For
        # claude this is the whole reason the cwd is consulted at all: the
        # slug flattens '/' and '-' alike, so this sibling and a genuine
        # subdirectory produce the same directory name, and only the cwd
        # in the entries tells them apart.
        self.plant_claude("stranger", self.SIBLING)
        self.plant_codex("stranger-c", self.SIBLING)
        self.plant_grok("stranger-g", self.SIBLING)
        found = self.ids()
        for name in ("stranger", "stranger-c", "stranger-g"):
            self.assertNotIn(name, found)

    def test_the_repo_itself_still_counts(self):
        self.plant_claude("root", REPO)
        self.plant_codex("root-c", REPO)
        self.plant_grok("root-g", REPO)
        found = self.ids()
        for name in ("root", "root-c", "root-g"):
            self.assertIn(name, found)


class TheReportAggregates(Fixtures):
    def test_totals_per_harness_and_the_gap_stated(self):
        proc = self.run_usage("report")
        self.assertEqual(proc.exit, 0, proc.stderr)
        self.assertIn("claude", proc.stdout)
        self.assertIn("490", proc.stdout, "codex total")
        self.assertIn("not yet parsed", proc.stdout, "the grok gap is stated")

    def test_the_report_never_prints_prompt_text(self):
        # The stores hold prompts and summaries; the report is aggregates
        # only. The fixture plants a distinctive marker to catch a leak.
        proc = self.run_usage("report")
        self.assertNotIn("SESSIONPROMPTTEXT", proc.stdout,
                         "session content leaked into the report")


if __name__ == "__main__":
    unittest.main()
