"""The job-directory record copy at mint carries the resolved wall.

Written from the record-wall plan (fix scope item 36) and CONTRACT.md
§The record ``caps.timeout`` bullet. launch.py was not read.

The launcher already resolves ``caps.timeout`` and
``caps.timeout_source`` before the harness starts. The mint copy in
the job directory must carry those fields in the closed record's
shape, so a running record tells the truth about its wall.

Acceptance, the three named sources:

- ``DISPATCH_TIMEOUT=N`` → ``caps.timeout == N``,
  ``caps.timeout_source == "DISPATCH_TIMEOUT"``
- the conf default (``WALL_DEFAULT``) → that many seconds,
  ``timeout_source == "default"``
- ``--timeout`` → the same fields; the dispatcher flag is an env
  delta ``DISPATCH_TIMEOUT``, not a launch.py callee flag
  (``ops/conductor/tests/test_dispatch_wrapper.py`` PIN_ARGV_MAP)

The job catalogue layer (CONTRACT.md: else the job's own
``caps.timeout``, source ``job``) is pinned too: a new record must
carry the resolved wall so the watchdog's catalogue fallback stays
only for records that predate the field.

Inspected while the harness is still running: job-directory
``record.json``, status ``launched``, no ``exit`` file yet.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import launch_support as ls

CONF_ENV = "LANE_CONF"

# Measured incident: DISPATCH_TIMEOUT=3600 against a catalogue 1800.
ENV_TIMEOUT = 3600
# Distinct from 900 and from ENV_TIMEOUT, so a hardcoded 3600 fails.
FLAG_TIMEOUT = 240
CONF_TIMEOUT = 480
JOB_TIMEOUT = 42
CATALOGUE_DECOY = 1800
DEFAULT_TIMEOUT = 900.0

REQUIRED_DEFAULTS = {
    "LANE_NAME": "agentscient",
    "TRUNK_BRANCH": "dev",
    "RELEASE_BRANCH": "master",
    "REPO_SLUG": "uscient/agentscient",
    "CHECK_NAMES": "lane app",
    "WF_AGENT_DEFAULT": ls.AGENT,
    "LANE_AUTHOR": "Lane Owner <lane-owner@example.invalid>",
    "MODEL_GROK": "model-grok",
    "MODEL_CODEX": "model-codex",
    "MODEL_CLAUDE_READ": "model-claude-read",
    "MODEL_CLAUDE_PLAN": "model-claude-plan",
    "EFFORT_GROK": "high",
    "EFFORT_CODEX": "high",
    "EFFORT_CLAUDE": "high",
    "WALL_DEFAULT": "900",
    "SCOPE_CAP": "1024",
}


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


def _caps(test, rec):
    test.assertIsInstance(rec, dict)
    test.assertIn("caps", rec)
    caps = rec["caps"]
    test.assertIsInstance(caps, dict)
    test.assertIn(
        "timeout", caps,
        "mint copy must carry caps.timeout while the harness runs: "
        f"{caps!r}",
    )
    test.assertIn(
        "timeout_source", caps,
        "mint copy must carry caps.timeout_source while the harness "
        f"runs: {caps!r}",
    )
    timeout = caps["timeout"]
    test.assertIsInstance(timeout, (int, float))
    test.assertNotIsInstance(timeout, bool)
    test.assertIsInstance(caps["timeout_source"], str)
    test.assertTrue(
        caps["timeout_source"].strip(),
        "timeout_source must name the layer that answered",
    )
    test.assertIn("cap-out", caps)
    test.assertIn("source", caps)
    return caps


class _MintCopyLaunch(ls._TempLaunch):
    """Capture the job-directory record.json before the harness exits."""

    def capture_mint_copy(self, argv, *, sleep=1.0):
        os.environ["TASK_LAUNCH_SLEEP"] = str(sleep)
        seen = {}

        def watch():
            deadline = time.time() + 8
            while not self.start_witness.is_file() and time.time() < deadline:
                time.sleep(0.01)
            seen["started"] = self.start_witness.is_file()
            while time.time() < deadline:
                files = self.record_files()
                seen["n_tracked"] = len(files)
                if len(files) != 1:
                    time.sleep(0.01)
                    continue
                job_id = files[0].stem
                beside = self.jobs_root / job_id / "record.json"
                exit_path = self.jobs_root / job_id / "exit"
                seen["beside_exists"] = beside.is_file()
                seen["exit"] = exit_path.exists()
                if beside.is_file() and not exit_path.exists():
                    body = beside.read_bytes()
                    rec = json.loads(body)
                    seen["rec"] = rec
                    seen["status"] = rec.get("status")
                    seen["result"] = rec.get("result")
                    seen["caps"] = rec.get("caps")
                    seen["id"] = rec.get("id")
                    seen["tracked_bytes"] = files[0].read_bytes()
                    seen["beside_bytes"] = body
                    return
                time.sleep(0.01)

        watcher = threading.Thread(target=watch)
        watcher.start()
        code, out, err = self.dispatch(argv)
        watcher.join(timeout=10)
        seen["code"] = code
        seen["out"] = out
        seen["err"] = err
        return seen

    def assert_mint_wall(self, seen, timeout, source):
        self.assertTrue(
            seen.get("started"),
            "harness must have started: " + repr(seen),
        )
        self.assertTrue(
            seen.get("beside_exists"),
            "job-directory record.json missing at mint: " + repr(seen),
        )
        self.assertFalse(
            seen.get("exit"),
            "exit is written last; mint copy is read before it exists: "
            + repr(seen),
        )
        self.assertEqual(
            seen.get("status"), "launched",
            f"mint copy status must be launched: {seen!r}",
        )
        self.assertIsNone(seen.get("result"))
        self.assertEqual(
            seen.get("beside_bytes"),
            seen.get("tracked_bytes"),
            "job-directory copy must match the tracked record at mint",
        )
        rec = seen.get("rec")
        caps = _caps(self, rec)
        self.assertEqual(
            float(caps["timeout"]), float(timeout),
            f"mint caps.timeout: {caps!r}",
        )
        self.assertEqual(
            caps["timeout_source"], source,
            f"mint caps.timeout_source: {caps!r}",
        )
        self.assertNotEqual(
            float(caps["timeout"]), float(DEFAULT_TIMEOUT),
            "resolved wall must not silently be the 900s default: "
            f"{caps!r}",
        )
        return caps


class _ConfMintLaunch(_MintCopyLaunch):
    """Scratch LANE_CONF so WALL_DEFAULT can differ from 900."""

    def setUp(self):
        self._lane_conf_was = os.environ.get(CONF_ENV)
        super().setUp()
        self.conf_path = self.home / "lane.conf"
        self.plant_conf()
        os.environ[CONF_ENV] = str(self.conf_path)

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            if self._lane_conf_was is None:
                os.environ.pop(CONF_ENV, None)
            else:
                os.environ[CONF_ENV] = self._lane_conf_was

    def plant_conf(self, **overrides: object) -> Path:
        omit = tuple(overrides.pop("omit", ()) or ())
        keys = dict(REQUIRED_DEFAULTS)
        for name, value in overrides.items():
            keys[name] = str(value)
        for name in omit:
            keys.pop(name, None)
        lines = ["# scratch lane conf\n"]
        for name, value in keys.items():
            lines.append(f"{name}='{value}'\n")
        text = "".join(lines)
        self.conf_path.write_text(text, encoding="utf-8")
        landed = self.conf_path.read_text(encoding="utf-8")
        self.assertEqual(landed, text, "conf plant did not land intact")
        for name, value in keys.items():
            self.assertIn(name, landed)
            self.assertIn(value, landed)
        os.environ[CONF_ENV] = str(self.conf_path)
        return self.conf_path


class MintCopyUnderDispatchTimeout(_MintCopyLaunch):
    """DISPATCH_TIMEOUT=N is on the mint copy before the harness exits."""

    def test_mint_copy_carries_dispatch_timeout_not_the_job_catalogue(self):
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        plant_job_timeout(self, "plan", CATALOGUE_DECOY)
        os.environ["DISPATCH_TIMEOUT"] = str(ENV_TIMEOUT)
        seen = self.capture_mint_copy(
            self.argv_for(job="plan", harness="grok", stage="plan"),
        )
        caps = self.assert_mint_wall(
            seen, ENV_TIMEOUT, "DISPATCH_TIMEOUT",
        )
        self.assertNotEqual(float(caps["timeout"]), float(CATALOGUE_DECOY))
        self.assertEqual(seen.get("code"), 0, self.combined(
            seen.get("out") or "", seen.get("err") or "",
        ))
        closed = self.read_record()
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(float(closed["caps"]["timeout"]), float(ENV_TIMEOUT))
        self.assertEqual(closed["caps"]["timeout_source"], "DISPATCH_TIMEOUT")
        self.assertEqual(
            float(closed["caps"]["timeout"]), float(caps["timeout"]),
        )
        self.assertEqual(
            closed["caps"]["timeout_source"], caps["timeout_source"],
        )


class MintCopyUnderConfDefault(_ConfMintLaunch):
    """WALL_DEFAULT from the conf is on the mint copy; source is default."""

    def test_mint_copy_carries_conf_wall_default(self):
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        self.assertNotIn("caps", jobs["plan"])
        self.plant_conf(WALL_DEFAULT=str(CONF_TIMEOUT))
        planted = self.conf_path.read_text(encoding="utf-8")
        self.assertIn(f"WALL_DEFAULT='{CONF_TIMEOUT}'", planted)
        seen = self.capture_mint_copy(
            self.argv_for(job="plan", harness="grok", stage="plan"),
        )
        caps = self.assert_mint_wall(seen, CONF_TIMEOUT, "default")
        self.assertNotEqual(float(caps["timeout"]), float(ENV_TIMEOUT))
        self.assertEqual(seen.get("code"), 0, self.combined(
            seen.get("out") or "", seen.get("err") or "",
        ))
        closed = self.read_record()
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(
            float(closed["caps"]["timeout"]), float(CONF_TIMEOUT),
        )
        self.assertEqual(closed["caps"]["timeout_source"], "default")


class MintCopyUnderTimeoutFlag(_MintCopyLaunch):
    """--timeout is DISPATCH_TIMEOUT; the mint copy carries that wall."""

    def test_mint_copy_carries_the_timeout_flag_env_delta(self):
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        self.assertNotIn("caps", jobs["plan"])
        os.environ["DISPATCH_TIMEOUT"] = str(FLAG_TIMEOUT)
        seen = self.capture_mint_copy(
            self.argv_for(job="plan", harness="grok", stage="plan"),
        )
        caps = self.assert_mint_wall(
            seen, FLAG_TIMEOUT, "DISPATCH_TIMEOUT",
        )
        self.assertNotEqual(float(caps["timeout"]), float(ENV_TIMEOUT))
        self.assertEqual(seen.get("code"), 0, self.combined(
            seen.get("out") or "", seen.get("err") or "",
        ))
        closed = self.read_record()
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(
            float(closed["caps"]["timeout"]), float(FLAG_TIMEOUT),
        )
        self.assertEqual(
            closed["caps"]["timeout_source"], "DISPATCH_TIMEOUT",
        )


class MintCopyUnderJobCap(_MintCopyLaunch):
    """A job-layer wall is on the mint copy so catalogue fallback is unused."""

    def test_mint_copy_carries_the_job_cap(self):
        self.assertNotIn("DISPATCH_TIMEOUT", os.environ)
        plant_job_timeout(self, "plan", JOB_TIMEOUT)
        seen = self.capture_mint_copy(
            self.argv_for(job="plan", harness="grok", stage="plan"),
        )
        caps = self.assert_mint_wall(seen, JOB_TIMEOUT, "job")
        self.assertEqual(seen.get("code"), 0, self.combined(
            seen.get("out") or "", seen.get("err") or "",
        ))
        closed = self.read_record()
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(float(closed["caps"]["timeout"]), float(JOB_TIMEOUT))
        self.assertEqual(closed["caps"]["timeout_source"], "job")
        self.assertEqual(
            float(closed["caps"]["timeout"]), float(caps["timeout"]),
        )
        self.assertEqual(
            closed["caps"]["timeout_source"], caps["timeout_source"],
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
