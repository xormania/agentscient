"""Per-job runtime caps: resolution order, policy values, enforcement.

Written from CONTRACT.md §The record, the ``caps.timeout`` bullet:
``DISPATCH_TIMEOUT`` from the invoking environment, else the job's own
``caps.timeout`` in jobs.json, else 900 — and ``caps.timeout_source``
names the layer that answered: ``DISPATCH_TIMEOUT``, ``job``, or
``default``. Policy values and the author-tests commit-on-red clause
come from ``ops/devlane/task/jobs.json``. launch.py and record.py were
not read.
"""

from __future__ import annotations

import json
import os
import time
import unittest

import launch_support as ls

DEFAULT_TIMEOUT = 900.0
POLICY_CAPS = {
    "author-tests": 1800,
    "check-tests": 1800,
    "adversarial-review": 1800,
    "security-audit": 1200,
    "implement": 3600,
}
COMMIT_ON_RED = "Commit each test file as soon as its red is proven"
POLICY_TURNS = {
    "author-tests": 200,
    "check-tests": 150,
    "adversarial-review": 150,
    "security-audit": 150,
    "implement": 200,
}
JOB_TURNS = 37
ENV_TURNS = 21
JOB_TIMEOUT = 42
ENV_TIMEOUT = 123.5
LOOP_TIMEOUT = 0.3


def _caps(test, rec):
    test.assertIsInstance(rec, dict)
    test.assertIn("caps", rec)
    caps = rec["caps"]
    test.assertIsInstance(caps, dict)
    test.assertIn("timeout", caps)
    test.assertIn("timeout_source", caps)
    timeout = caps["timeout"]
    test.assertIsInstance(timeout, (int, float))
    test.assertNotIsInstance(timeout, bool)
    test.assertIsInstance(caps["timeout_source"], str)
    return caps


def plant_job_timeout(test, job, seconds):
    """Write ``caps.timeout`` onto one job in the fixture catalog."""
    path = test.jobs_file
    before_obj = json.loads(path.read_text(encoding="utf-8"))
    test.assertIsInstance(before_obj, dict)
    test.assertIn(job, before_obj)
    prior = (before_obj.get(job) or {}).get("caps")
    prior_timeout = None if not isinstance(prior, dict) else prior.get("timeout")
    test.assertNotEqual(
        prior_timeout, seconds,
        f"plant {job} timeout={seconds} was already the fixture",
    )

    def mutate(raw):
        jobs = json.loads(raw)
        spec = dict(jobs[job])
        spec["caps"] = {"timeout": seconds}
        jobs[job] = spec
        return (json.dumps(jobs, indent=2) + "\n").encode("utf-8")

    ls.plant_bytes(
        path,
        mutate,
        expect="grow",
        recognisable=lambda after: (
            job.encode("utf-8") in after and b'"timeout"' in after
        ),
    )
    landed = json.loads(path.read_text(encoding="utf-8"))
    test.assertEqual(landed[job]["caps"]["timeout"], seconds)
    test.assertNotEqual(landed[job].get("caps"), prior)
    test.ref = test._commit(f"plant {job} caps.timeout={seconds}")
    return seconds


class JobTimeoutIsRecordedWhenEnvIsAbsent(ls._TempLaunch):
    """Else the job's own caps.timeout; source is job."""

    def test_a_job_cap_is_recorded_as_timeout_with_source_job(self):
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        plant_job_timeout(self, "plan", JOB_TIMEOUT)
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        caps = _caps(self, rec)
        self.assertEqual(float(caps["timeout"]), float(JOB_TIMEOUT))
        self.assertNotEqual(float(caps["timeout"]), DEFAULT_TIMEOUT)
        self.assertEqual(caps["timeout_source"], "job")


class EnvTimeoutWinsOverTheJobCap(ls._TempLaunch):
    """DISPATCH_TIMEOUT from the invoking environment wins; source names it."""

    def test_dispatch_timeout_beats_the_job_cap_and_names_its_source(self):
        plant_job_timeout(self, "plan", JOB_TIMEOUT)
        os.environ["DISPATCH_TIMEOUT"] = str(ENV_TIMEOUT)
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        caps = _caps(self, rec)
        self.assertEqual(float(caps["timeout"]), float(ENV_TIMEOUT))
        self.assertNotEqual(float(caps["timeout"]), float(JOB_TIMEOUT))
        self.assertNotEqual(float(caps["timeout"]), DEFAULT_TIMEOUT)
        self.assertEqual(caps["timeout_source"], "DISPATCH_TIMEOUT")


class DefaultTimeoutWhenNeitherLayerAnswers(ls._TempLaunch):
    """Else 900, source default — a job with no caps entry and no env."""

    def test_no_job_cap_and_no_env_records_900_from_default(self):
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        self.assertNotIn("caps", jobs["plan"])
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        caps = _caps(self, rec)
        self.assertEqual(float(caps["timeout"]), DEFAULT_TIMEOUT)
        self.assertEqual(caps["timeout_source"], "default")


class JobsJsonCarriesExactlyTheFivePolicyCaps(unittest.TestCase):
    """author-tests 1800, check-tests 1800, adversarial-review 1800
    (raised from 1200 on 2026-09-11: Grok reviews ran to 19 of 20 minutes),
    security-audit 1200, implement 3600."""

    def test_exactly_five_jobs_carry_the_named_caps(self):
        self.assertTrue(ls.JOBS_PATH.is_file(), f"missing {ls.JOBS_PATH}")
        jobs = json.loads(ls.JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(jobs, dict)
        self.assertGreater(len(jobs), 0, "jobs.json must name jobs")
        carrying = {}
        for name, spec in jobs.items():
            self.assertIsInstance(spec, dict, f"{name} spec is not an object")
            if "caps" not in spec:
                continue
            caps = spec["caps"]
            self.assertIsInstance(caps, dict, f"{name} caps is not an object")
            self.assertIn("timeout", caps, f"{name} caps has no timeout")
            carrying[name] = caps["timeout"]
        self.assertEqual(
            len(carrying), len(POLICY_CAPS),
            f"expected {len(POLICY_CAPS)} jobs with caps, got {carrying!r}",
        )
        self.assertEqual(set(carrying), set(POLICY_CAPS))
        self.assertEqual(carrying, POLICY_CAPS)


class AuthorTestsPromptContainsTheCommitOnRedClause(unittest.TestCase):
    """The author-tests prompt asks to commit each test file on proven red."""

    def test_author_tests_prompt_contains_the_commit_on_red_clause(self):
        self.assertTrue(ls.JOBS_PATH.is_file(), f"missing {ls.JOBS_PATH}")
        jobs = json.loads(ls.JOBS_PATH.read_text(encoding="utf-8"))
        self.assertIn("author-tests", jobs)
        spec = jobs["author-tests"]
        self.assertIsInstance(spec, dict)
        prompt = spec.get("prompt")
        self.assertIsInstance(prompt, str)
        self.assertTrue(prompt.strip(), "author-tests prompt is empty")
        self.assertIn(COMMIT_ON_RED, prompt)


class SupervisionEnforcesTheResolvedJobCap(ls._TempLaunch):
    """The resolved cap, not a flat 900, is what the supervision loop enforces."""

    def test_a_short_job_cap_trips_the_loop_without_waiting_out_900(self):
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        plant_job_timeout(self, "plan", LOOP_TIMEOUT)
        os.environ["TASK_LAUNCH_SLEEP"] = "8"
        os.environ["TASK_LAUNCH_WRITE_STREAM"] = "1"
        started = time.monotonic()
        self.dispatch(self.argv_for(job="plan", harness="grok", stage="plan"))
        elapsed = time.monotonic() - started
        rec = self.read_record()
        self.assertLess(
            elapsed, 4,
            f"job cap {LOOP_TIMEOUT}s must not wait out 8s, "
            f"let alone 900s: elapsed={elapsed}",
        )
        blob = json.dumps(rec).lower()
        self.assertIn("timeout", blob)
        self.assertTrue(
            self.start_witness.is_file(),
            "plant: the harness child started before the timeout",
        )
        pid = self.read_start_witness()["pid"]
        self.assertFalse(ls.pid_is_alive(pid))


def plant_job_turns(test, job, turns):
    """Write ``caps.turns`` (beside a timeout) onto one job in the fixture."""
    path = test.jobs_file
    before_obj = json.loads(path.read_text(encoding="utf-8"))
    test.assertIn(job, before_obj)
    prior = (before_obj.get(job) or {}).get("caps")
    test.assertNotEqual(
        None if not isinstance(prior, dict) else prior.get("turns"), turns,
        f"plant {job} turns={turns} was already the fixture",
    )

    def mutate(raw):
        jobs = json.loads(raw)
        spec = dict(jobs[job])
        spec["caps"] = {"timeout": JOB_TIMEOUT, "turns": turns}
        jobs[job] = spec
        return (json.dumps(jobs, indent=2) + "\n").encode("utf-8")

    ls.plant_bytes(
        path,
        mutate,
        expect="grow",
        recognisable=lambda after: (
            job.encode("utf-8") in after and b'"turns"' in after
        ),
    )
    landed = json.loads(path.read_text(encoding="utf-8"))
    test.assertEqual(landed[job]["caps"]["turns"], turns)
    test.ref = test._commit(f"plant {job} caps.turns={turns}")
    return turns


def _turn_caps(test, rec):
    caps = _caps(test, rec)
    for key in ("turns", "turns_source", "turns_argv"):
        test.assertIn(key, caps, f"caps has no {key}")
    test.assertIsInstance(caps["turns_argv"], list)
    test.assertIsInstance(caps["turns_source"], str)
    return caps


def _max_turns_value(test, argv):
    test.assertIn("--max-turns", argv, argv)
    idx = argv.index("--max-turns")
    test.assertLess(idx + 1, len(argv), argv)
    test.assertEqual(argv.count("--max-turns"), 1, argv)
    return argv[idx + 1]


class JobTurnCapReachesTheGrokArgvAndTheRecord(ls._TempLaunch):
    """Owner, 2026-09-12: "hand grant - cap turns". Grok takes --max-turns N;
    the record carries caps.turns, its source and the exact argv tokens.
    One producer (Claude Fable 5.1) wrote this test and the change under
    a hand grant; no second producer."""

    def test_grok_gets_max_turns_from_the_job_cap(self):
        self.assertNotIn("DISPATCH_TURNS", os.environ)
        plant_job_turns(self, "plan", JOB_TURNS)
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        caps = _turn_caps(self, rec)
        self.assertEqual(caps["turns"], JOB_TURNS)
        self.assertEqual(caps["turns_source"], "job")
        self.assertEqual(caps["turns_argv"], ["--max-turns", str(JOB_TURNS)])
        witness = self.read_start_witness()
        self.assertEqual(_max_turns_value(self, witness["argv"]), str(JOB_TURNS))
        self.assertEqual(rec["harness"]["argv"][-len(witness["argv"]) + 1:],
                         witness["argv"][1:])


class JobTurnCapReachesTheClaudeArgv(ls._TempLaunch):
    """Claude's print mode takes --max-turns N the same way."""

    def test_claude_gets_max_turns_from_the_job_cap(self):
        self.assertNotIn("DISPATCH_TURNS", os.environ)
        plant_job_turns(self, "plan", JOB_TURNS)
        rec, *_ = self.launch_ok(job="plan", harness="claude", stage="plan")
        caps = _turn_caps(self, rec)
        self.assertEqual(caps["turns"], JOB_TURNS)
        self.assertEqual(caps["turns_argv"], ["--max-turns", str(JOB_TURNS)])
        witness = self.read_start_witness()
        self.assertEqual(_max_turns_value(self, witness["argv"]), str(JOB_TURNS))


class CodexHasNoTurnFlagAndTheRecordSaysSo(ls._TempLaunch):
    """`codex exec --help | grep -c turn` is 0 on this host (2026-09-12):
    the cap is recorded, no flag is forged, and the record declares the
    absence rather than staying silent."""

    def test_codex_records_the_cap_with_empty_argv_and_a_note(self):
        self.assertNotIn("DISPATCH_TURNS", os.environ)
        plant_job_turns(self, "plan", JOB_TURNS)
        rec, *_ = self.launch_ok(job="plan", harness="codex", stage="plan")
        caps = _turn_caps(self, rec)
        self.assertEqual(caps["turns"], JOB_TURNS)
        self.assertEqual(caps["turns_source"], "job")
        self.assertEqual(caps["turns_argv"], [])
        self.assertIn("codex", caps.get("turns_note", ""))
        self.assertNotIn("--max-turns", self.read_start_witness()["argv"])


class NoTurnCapIsDeclaredNotInferred(ls._TempLaunch):
    """A job with no caps.turns and no env records turns None, source none."""

    def test_no_job_turns_and_no_env_records_none(self):
        self.assertNotIn("DISPATCH_TURNS", os.environ)
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        self.assertNotIn("caps", jobs["plan"])
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        caps = _turn_caps(self, rec)
        self.assertIsNone(caps["turns"])
        self.assertEqual(caps["turns_source"], "none")
        self.assertEqual(caps["turns_argv"], [])
        self.assertNotIn("--max-turns", self.read_start_witness()["argv"])


class EnvTurnsWinOverTheJobCap(ls._TempLaunch):
    """DISPATCH_TURNS from the invoking environment wins; source names it."""

    def test_dispatch_turns_beats_the_job_cap(self):
        plant_job_turns(self, "plan", JOB_TURNS)
        os.environ["DISPATCH_TURNS"] = str(ENV_TURNS)
        self.addCleanup(os.environ.pop, "DISPATCH_TURNS", None)
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        caps = _turn_caps(self, rec)
        self.assertEqual(caps["turns"], ENV_TURNS)
        self.assertEqual(caps["turns_source"], "DISPATCH_TURNS")
        self.assertEqual(_max_turns_value(self, self.read_start_witness()["argv"]),
                         str(ENV_TURNS))


class JobsJsonCarriesTheTurnPolicy(unittest.TestCase):
    """The five capped jobs carry caps.turns: author-tests 200, implement
    200, check-tests 150, adversarial-review 150, security-audit 150.
    Chosen 2026-09-12 from the store's message counts (Grok author-tests:
    median 229, p90 325, max 500 messages); the harness turn unit is not
    the store's message unit, so the first ladder under the cap re-measures."""

    def test_the_capped_jobs_carry_the_named_turns(self):
        jobs = json.loads(ls.JOBS_PATH.read_text(encoding="utf-8"))
        carrying = {
            name: spec["caps"]["turns"]
            for name, spec in jobs.items()
            if isinstance(spec, dict) and isinstance(spec.get("caps"), dict)
            and "turns" in spec["caps"]
        }
        self.assertEqual(carrying, POLICY_TURNS)
        for name, turns in carrying.items():
            self.assertIsInstance(turns, int, name)
            self.assertNotIsInstance(turns, bool, name)
            self.assertGreater(turns, 0, name)
