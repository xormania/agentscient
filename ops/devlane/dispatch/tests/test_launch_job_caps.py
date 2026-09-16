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

from ops.testkit import World

DEFAULT_TIMEOUT = 900.0
COMMIT_ON_RED = "Commit each test file as soon as its red is proven"
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
    test.assertIsInstance(test.world, World)
    path = test.jobs_file
    before = path.read_text(encoding="utf-8")
    before_obj = json.loads(before)
    test.assertIsInstance(before_obj, dict)
    test.assertIn(job, before_obj)
    prior = (before_obj.get(job) or {}).get("caps")
    prior_timeout = None if not isinstance(prior, dict) else prior.get("timeout")
    test.assertNotEqual(
        prior_timeout, seconds,
        f"plant {job} timeout={seconds} was already the fixture",
    )
    jobs = json.loads(before)
    spec = dict(jobs[job])
    spec["caps"] = {"timeout": seconds}
    jobs[job] = spec
    content = json.dumps(jobs, indent=2) + "\n"
    # The plant replaces caps that are already there, so the file may shrink;
    # what it has to prove is that it changed the catalogue and landed.
    test.assertNotEqual(content, before, "plant changed nothing")
    test.assertIn(job, content)
    test.assertIn('"timeout"', content)
    test.world.plant_text(path, content, recognisable='"timeout"')
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
    """Else 900, source default — a catalogue entry declaring no caps, and
    no env. The capless entry is planted (strip_job_caps): every job in the
    real catalogue declares its caps, and an absence this test needs is one
    it makes, never one it hopes to find."""

    def test_no_job_cap_and_no_env_records_900_from_default(self):
        self.assertIsInstance(self.world, World)
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        ls.strip_job_caps(self, "plan")
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        self.assertNotIn("caps", jobs["plan"])
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        caps = _caps(self, rec)
        self.assertEqual(float(caps["timeout"]), DEFAULT_TIMEOUT)
        self.assertEqual(caps["timeout_source"], "default")


class EveryJobDeclaresItsCaps(unittest.TestCase):
    """Every job in the catalogue declares caps.timeout and caps.turns.

    What this replaces: a pin naming five jobs and their exact numbers.
    It said nothing about a sixth job, which is how four jobs (verify,
    sweep, plan, adjudicate) ran uncapped while the pin was green, and it
    had to be edited beside the catalogue whenever a number moved. The
    contract owns the closure — a job declares what bounds it — and
    jobs.json owns the numbers (docs/tests.md rule 3: a pin on a count
    the contract does not own is a finding). A cap's value is a decision,
    recorded in the commit that moves it.
    """

    def setUp(self):
        self.world = World(prefix="launch-job-caps-catalog-")
        self.addCleanup(self.world.close)
        self.assertTrue(ls.JOBS_PATH.is_file(), f"missing {ls.JOBS_PATH}")
        planted = self.world.plant_text(
            self.world.cwd / "jobs.json",
            ls.JOBS_PATH.read_text(encoding="utf-8"),
            recognisable='"timeout"',
        )
        self.jobs = json.loads(planted.read_text(encoding="utf-8"))
        self.assertIsInstance(self.jobs, dict)
        self.assertGreater(len(self.jobs), 0, "jobs.json must name jobs")

    def positive_int(self, value, where):
        self.assertIsInstance(value, int, where)
        self.assertNotIsInstance(value, bool, where)
        self.assertGreater(value, 0, where)

    def test_every_job_carries_caps_with_turns_and_timeout(self):
        uncapped = sorted(
            name for name, spec in self.jobs.items()
            if not isinstance(spec, dict)
            or not isinstance(spec.get("caps"), dict)
            or "timeout" not in spec["caps"] or "turns" not in spec["caps"]
        )
        self.assertEqual(
            uncapped, [],
            f"every job declares caps.timeout and caps.turns; these do not: {uncapped}",
        )
        for name, spec in self.jobs.items():
            with self.subTest(job=name):
                self.positive_int(spec["caps"]["timeout"], f"{name} caps.timeout")
                self.positive_int(spec["caps"]["turns"], f"{name} caps.turns")


class AuthorTestsPromptContainsTheCommitOnRedClause(unittest.TestCase):
    """The author-tests prompt asks to commit each test file on proven red."""

    def setUp(self):
        self.world = World(prefix="launch-job-caps-prompt-")
        self.addCleanup(self.world.close)
        self.assertTrue(ls.JOBS_PATH.is_file(), f"missing {ls.JOBS_PATH}")
        planted = self.world.plant_text(
            self.world.cwd / "jobs.json",
            ls.JOBS_PATH.read_text(encoding="utf-8"),
            recognisable=COMMIT_ON_RED,
        )
        self.jobs = json.loads(planted.read_text(encoding="utf-8"))

    def test_author_tests_prompt_contains_the_commit_on_red_clause(self):
        self.assertIn("author-tests", self.jobs)
        spec = self.jobs["author-tests"]
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
    test.assertIsInstance(test.world, World)
    path = test.jobs_file
    before = path.read_text(encoding="utf-8")
    before_obj = json.loads(before)
    test.assertIn(job, before_obj)
    prior = (before_obj.get(job) or {}).get("caps")
    test.assertNotEqual(
        None if not isinstance(prior, dict) else prior.get("turns"), turns,
        f"plant {job} turns={turns} was already the fixture",
    )
    jobs = json.loads(before)
    spec = dict(jobs[job])
    spec["caps"] = {"timeout": JOB_TIMEOUT, "turns": turns}
    jobs[job] = spec
    content = json.dumps(jobs, indent=2) + "\n"
    # The plant replaces caps that are already there, so the file may shrink;
    # what it has to prove is that it changed the catalogue and landed.
    test.assertNotEqual(content, before, "plant changed nothing")
    test.assertIn(job, content)
    test.assertIn('"turns"', content)
    test.world.plant_text(path, content, recognisable='"turns"')
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
    """A catalogue entry with no caps.turns and no env records turns None,
    source none. The capless entry is planted, as above."""

    def test_no_job_turns_and_no_env_records_none(self):
        self.assertIsInstance(self.world, World)
        self.assertNotIn("DISPATCH_TURNS", os.environ)
        ls.strip_job_caps(self, "plan")
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


class EveryJobsTurnCapIsDeclared(unittest.TestCase):
    """caps.turns on every job, read through the file's own text.

    The numbers were chosen 2026-09-12 from the store's message counts
    (Grok author-tests: median 229, p90 325, max 500 messages) and
    extended to the four short jobs on 2026-09-16; the harness turn unit
    is not the store's message unit, so a run under a cap re-measures it.
    The values live in jobs.json, not here."""

    def setUp(self):
        self.world = World(prefix="launch-job-caps-turns-")
        self.addCleanup(self.world.close)
        planted = self.world.plant_text(
            self.world.cwd / "jobs.json",
            ls.JOBS_PATH.read_text(encoding="utf-8"),
            recognisable='"turns"',
        )
        self.jobs = json.loads(planted.read_text(encoding="utf-8"))

    def test_the_capped_jobs_carry_the_named_turns(self):
        carrying = {
            name: spec["caps"]["turns"]
            for name, spec in self.jobs.items()
            if isinstance(spec, dict) and isinstance(spec.get("caps"), dict)
            and "turns" in spec["caps"]
        }
        self.assertEqual(sorted(carrying), sorted(self.jobs),
                         f"a job declares no caps.turns: {sorted(set(self.jobs) - set(carrying))}")
        for name, turns in carrying.items():
            self.assertIsInstance(turns, int, name)
            self.assertNotIsInstance(turns, bool, name)
            self.assertGreater(turns, 0, name)
