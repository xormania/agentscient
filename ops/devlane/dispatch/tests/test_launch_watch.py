"""status, DIED, resume.

Written from CONTRACT.md §Dispatch Watching, and picking up after a
kill. Plan items (h)(i).

  W1  DIED is pid gone, no exit file — never finished
  W2  running / finished / tripped / unlaunched
  W3  resume verbs, same cwd, markers cleared, output appended, attempt appended
  W4  a tripped job resumes only with a changed cap or a stated reason
  W5  close of a DIED job commits the record as invalid
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import launch_support as ls


class StatusReportsDiedNeverFinished(ls._TempLaunch):
    """W1 / plan (i). Planted job dirs — status does not need a live
    harness, but it does need launch.main."""

    def _plant_job(self, job_id, *, pid, exit_text=None, tripped=False):
        d = self.jobs_root / job_id
        d.mkdir()
        state = {
            "pid": pid,
            "pgid": pid,
            "session": {"id": "11111111-1111-4111-8111-111111111111"},
            "stream": str(d / "stream.jsonl"),
            "attempt": 1,
        }
        (d / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
        landed = json.loads((d / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(landed["pid"], pid, "plant: state.json pid")
        if exit_text is not None:
            (d / "exit").write_text(exit_text, encoding="utf-8")
            self.assertEqual((d / "exit").read_text(encoding="utf-8"), exit_text)
        if tripped:
            (d / "TRIPPED.md").write_text("tripped\n", encoding="utf-8")
            self.assertTrue((d / "TRIPPED.md").is_file())
        return d

    def _status(self, *args):
        argv = ["status", *args]
        return self.run_main(argv)

    def _status_blob(self, *args):
        code, out, err = self._status(*args)
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"status exits 0: {text!r}")
        self.assertTrue(out.strip() or err.strip(), "status prints a report")
        return text

    def test_a_dead_pid_with_no_exit_file_is_died_never_finished(self):
        job_id = "20260826T000000Z-plan-grok-d1ed00"
        pid = self.dead_pid()
        self._plant_job(job_id, pid=pid)
        self.assertFalse((self.jobs_root / job_id / "exit").exists())
        text = self._status_blob(job_id)
        self.assertIn("DIED", text)
        self.assertNotIn("finished", text.lower())
        code, out, _err = self._status(job_id, "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        row = payload if isinstance(payload, dict) else payload[0]
        if isinstance(payload, list):
            self.assertEqual(len(payload), 1)
            row = payload[0]
        status = row.get("status") or row.get("state")
        self.assertEqual(status, "DIED")
        self.assertNotEqual(status, "finished")

    def test_an_alive_pid_is_running(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(proc.kill)
        job_id = "20260826T000000Z-plan-grok-run001"
        self._plant_job(job_id, pid=proc.pid)
        os.kill(proc.pid, 0)  # plant: the pid is still alive
        text = self._status_blob(job_id, "--json")
        self.assertIn("running", text.lower())
        self.assertNotIn("DIED", text)

    def test_an_exit_file_is_finished(self):
        job_id = "20260826T000000Z-plan-grok-fin001"
        self._plant_job(job_id, pid=self.dead_pid(), exit_text="0\n")
        text = self._status_blob(job_id, "--json")
        self.assertIn("finished", text.lower())
        self.assertNotIn("DIED", text)

    def test_tripped_md_is_tripped(self):
        job_id = "20260826T000000Z-plan-grok-trp001"
        self._plant_job(
            job_id, pid=self.dead_pid(), exit_text="137\n", tripped=True,
        )
        text = self._status_blob(job_id, "--json")
        self.assertIn("tripped", text.lower())
        self.assertNotIn("DIED", text)

    def test_an_unknown_id_is_unlaunched(self):
        text = self._status_blob("20260826T000000Z-plan-grok-none00")
        self.assertIn("unlaunched", text.lower())


class ResumeRelaunchesInTheSameSnapshot(ls._TempLaunch):
    """W3 / plan (h)."""

    def test_resume_uses_the_harness_resume_verb_in_the_same_cwd(self):
        rec, first, *_ = self.launch_ok(
            job="plan", harness="grok", stage="plan",
        )
        job_id = rec["id"]
        snap = os.path.realpath(self.snapshot_of(rec))
        first_cwd = os.path.realpath(first["cwd"])
        self.assertEqual(first_cwd, snap)
        os.environ["TASK_LAUNCH_TOKEN"] = "SECOND-ATTEMPT"
        os.environ["TASK_LAUNCH_STDOUT"] = "token"
        self.witness.unlink()
        code, out, err = self.run_main(["resume", job_id])
        self.assertEqual(code, 0, self.combined(out, err))
        second = self.read_witness()
        argv = [str(p) for p in second["argv"]]
        self.assertIn("-r", argv)
        self.assertEqual(argv[argv.index("-r") + 1], rec["session"]["id"])
        self.assertEqual(os.path.realpath(second["cwd"]), snap)

    def test_resume_claude_uses_print_and_dash_r(self):
        rec, *_ = self.launch_ok(job="plan", harness="claude", stage="plan")
        self.witness.unlink()
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assertEqual(code, 0, self.combined(out, err))
        argv = [str(p) for p in self.read_witness()["argv"]]
        self.assertTrue("-p" in argv or "--print" in argv)
        self.assertIn("-r", argv)
        self.assertEqual(argv[argv.index("-r") + 1], rec["session"]["id"])

    def test_resume_codex_uses_exec_resume(self):
        rec, *_ = self.launch_ok(job="plan", harness="codex", stage="plan")
        self.witness.unlink()
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assertEqual(code, 0, self.combined(out, err))
        argv = [str(p) for p in self.read_witness()["argv"]]
        self.assertIn("exec", argv)
        self.assertIn("resume", argv)
        self.assertIn(rec["session"]["id"], argv)

    def test_resume_appends_output_and_an_attempt_and_clears_exit(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        job_dir = self.the_job_dir()
        raw = job_dir / "raw.out"
        self.assertTrue(raw.is_file(), "first attempt wrote raw.out")
        first_body = raw.read_bytes()
        self.assertTrue(first_body, "plant: raw.out from the first attempt")
        exit_path = job_dir / "exit"
        self.assertTrue(exit_path.is_file(), "exit is written last")
        before_attempts = rec.get("attempts") or []
        self.assertGreaterEqual(len(before_attempts), 1)
        os.environ["TASK_LAUNCH_TOKEN"] = "SECOND-ATTEMPT"
        os.environ["TASK_LAUNCH_STDOUT"] = "token"
        self.witness.unlink()
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assertEqual(code, 0, self.combined(out, err))
        after = raw.read_bytes()
        self.assertTrue(
            after.startswith(first_body) or first_body in after,
            "resume must append, not truncate, raw.out",
        )
        self.assertIn(b"SECOND-ATTEMPT", after)
        rec2 = self.read_record()
        attempts = rec2.get("attempts") or []
        self.assertGreater(
            len(attempts), len(before_attempts),
            "resume appends an attempts[] entry",
        )
        started = self.read_start_witness()
        self.assertFalse(
            started.get("exit_present"),
            "resume clears the exit marker before the child starts",
        )
        self.assertFalse(
            started.get("tripped_present"),
            "resume clears TRIPPED.md before the child starts",
        )


class TrippedResumeNeedsAReason(ls._TempLaunch):
    """W4."""

    def test_a_tripped_job_refuses_resume_without_a_changed_cap_or_reason(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        job_dir = self.the_job_dir()
        tripped = job_dir / "TRIPPED.md"
        self.plant_new_file(tripped, "battery tripped\n",
                            must_contain="tripped")
        self.start_witness.unlink(missing_ok=True)
        self.witness.unlink(missing_ok=True)
        # Rewrite status so close-time resume sees a trip.
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assertNotEqual(code, 0, self.combined(out, err))
        text = self.combined(out, err).lower()
        self.assertTrue(
            "trip" in text or "cap" in text or "reason" in text,
            f"tripped resume without reason must be refused: {text!r}",
        )
        self.assertTrue(tripped.is_file(), "a refused resume leaves the marker")
        self.assert_not_started()

    def test_a_tripped_job_resumes_with_a_stated_reason(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        job_dir = self.the_job_dir()
        tripped = job_dir / "TRIPPED.md"
        self.plant_new_file(tripped, "battery tripped\n",
                            must_contain="tripped")
        self.start_witness.unlink(missing_ok=True)
        self.witness.unlink(missing_ok=True)
        # §Watching requires a changed cap or stated reason. §Verbs
        # lists only --prompt-file on resume. --reason is the smallest
        # argv that makes the positive path pin-able.
        code, out, err = self.run_main([
            "resume", rec["id"], "--reason", "owner said continue",
        ])
        self.assertEqual(code, 0, self.combined(out, err))
        started = self.read_start_witness()
        self.assertFalse(
            started.get("tripped_present"),
            "a successful resume clears TRIPPED.md before the child starts",
        )
        self.assertFalse(tripped.is_file(), "trip marker does not return")
        rec2 = self.read_record()
        blob = json.dumps(rec2)
        self.assertIn("owner said continue", blob)
        attempts = rec2.get("attempts") or []
        self.assertGreaterEqual(len(attempts), 2)

    def test_a_tripped_job_resumes_with_a_changed_cap_and_rearms(self):
        rec, *_ = self.launch_ok(job="plan", harness="codex", stage="plan")
        job_dir = self.the_job_dir()
        tripped = job_dir / "TRIPPED.md"
        self.plant_new_file(tripped, "battery tripped\n",
                            must_contain="tripped")
        done = self.home / "resume-completed.marker"
        os.environ["TASK_LAUNCH_DONE"] = str(done)
        os.environ["TASK_LAUNCH_OVER_OUT"] = "5000000"
        os.environ["TASK_LAUNCH_SLEEP"] = "4"
        os.environ["TASK_LAUNCH_WRITE_STREAM"] = "1"
        self.start_witness.unlink(missing_ok=True)
        _code, out, err = self.run_main([
            "resume", rec["id"], "--cap-out", "100",
        ])
        rec2 = self.read_record()
        blob = json.dumps(rec2) + self.combined(out, err)
        self.assertTrue(
            "cap" in blob.lower() or rec2.get("caps"),
            f"changed cap must be recorded: {blob!r}",
        )
        # Re-arm: an over-budget sleeping child is killed, so DONE
        # is never written (same shape as run.py R9).
        self.assertFalse(
            done.is_file(),
            "re-armed battery must kill the over-budget resume child",
        )
        envelope = (rec2.get("result") or {}).get("envelope") or {}
        self.assertIn(
            envelope.get("status"), ("tripped", "invalid"),
            f"re-armed trip must surface: {rec2!r}",
        )


class CloseDiedCommitsInvalid(ls._TempLaunch):
    """W5 — close ID finalizes and commits a DIED job's record as invalid."""

    def test_close_of_a_died_job_commits_invalid(self):
        # A real launch first so the lineage can receive a later close
        # commit; then plant a sibling launched record as DIED.
        self.launch_ok(job="plan", harness="grok", stage="plan")
        job_id = "20260826T000000Z-plan-grok-d1edcc"
        d = self.jobs_root / job_id
        d.mkdir()
        pid = self.dead_pid()
        (d / "state.json").write_text(json.dumps({
            "pid": pid, "pgid": pid,
            "session": {"id": "22222222-2222-4222-8222-222222222222"},
            "attempt": 1,
        }) + "\n", encoding="utf-8")
        self.assertFalse((d / "exit").exists())
        record_path = (
            self.repo / ".dev" / "records" / "dispatches" / f"{job_id}.json"
        )
        seed = {
            "id": job_id, "lane": "dev", "stage": "plan", "unit": "work",
            "lineage": {"branch": "work", "base_sha": self.root_sha},
            "follows": [], "job": "plan", "role": "read",
            "dispatched_by": ls.AGENT,
            "at": {"launched": "2026-08-26T00:00:00Z", "closed": None},
            "snapshot": {
                "mode": "whole", "ref_name": "HEAD",
                "ref_sha": self.ref, "behind_tip": 0,
                "root": str(d / "snapshot"),
            },
            "harness": {
                "name": "grok", "version": "1.0.5",
                "isolation": {
                    "mechanism": "home",
                    "observed": {"unresolved": "not run"},
                },
                "sandbox": "plan", "containment": "policy", "argv": [],
            },
            "model": {
                "requested": ls.REQUESTED_MODEL,
                "effort_requested": None, "ran": None, "read_from": None,
            },
            "session": {"id": None, "stream": None,
                        "stream_sha256_at_close": None},
            "brief": {
                "template": {"path": "jobs.json", "sha256": "a" * 64},
                "scope": "x", "inputs": [], "sha256": "b" * 64, "bytes": 1,
            },
            "caps": {"source": "wires.py"},
            "overrides": [], "attempts": [],
            "result": None, "status": "launched",
        }
        (d / "snapshot").mkdir()
        record_path.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
        self.assertIn("launched", record_path.read_text(encoding="utf-8"))
        before_head = self._git("rev-parse", "HEAD").stdout.strip()
        code, out, err = self.run_main(["close", job_id])
        self.assertEqual(code, 0, self.combined(out, err))
        rec = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(rec["status"], "died")
        envelope = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(envelope.get("status"), "invalid")
        after_head = self._git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(after_head, before_head)
        msg = self._git("log", "-1", "--format=%s").stdout
        self.assertIn(job_id, msg)


class LaunchedRecordExistsBeforeTheChildFinishes(ls._TempLaunch):
    """The launched record is written before the child runs to completion."""

    def test_status_launched_is_visible_while_the_child_is_still_running(self):
        os.environ["TASK_LAUNCH_SLEEP"] = "0.5"
        seen = {}

        def watch():
            deadline = time.time() + 4
            while not self.start_witness.is_file() and time.time() < deadline:
                time.sleep(0.01)
            files = self.record_files()
            seen["n_records"] = len(files)
            if files:
                data = json.loads(files[0].read_text(encoding="utf-8"))
                seen["status"] = data.get("status")
                seen["result"] = data.get("result")
            exits = list(self.jobs_root.glob("*/exit"))
            seen["exit"] = bool(exits)

        t = threading.Thread(target=watch)
        t.start()
        self.dispatch(self.argv_for(job="plan", harness="grok", stage="plan"))
        t.join(timeout=6)
        self.assertEqual(
            seen.get("status"), "launched",
            "the launched record must exist before the child finishes: "
            f"{seen!r}",
        )
        self.assertIsNone(seen.get("result"))
        self.assertFalse(
            seen.get("exit"),
            "exit is written last, so it must be absent at child-start",
        )


class RuntimeOutcomesStillCommitARecord(ls._TempLaunch):
    """harness-cli, envelope-parse, timeout, trip produce committed records."""

    def _committed_invalid(self, rec, *, needles):
        envelope = (rec.get("result") or {}).get("envelope") or {}
        blob = (json.dumps(rec) + json.dumps(envelope)).lower()
        self.assertTrue(
            envelope.get("status") in ("invalid", "tripped")
            or rec.get("status") in ("closed", "died"),
            f"runtime outcome must still write a record: {rec!r}",
        )
        for n in needles:
            self.assertIn(n, blob, f"missing {n!r} in {blob!r}")
        msg = self._git("log", "-1", "--format=%B").stdout
        self.assertIn(rec["id"], msg)
        self.assertIn("Source: generated: ops/devlane/dispatch/launch.py", msg)

    def test_harness_cli_nonzero_exit_commits_an_invalid_record(self):
        os.environ["TASK_LAUNCH_EXIT"] = "127"
        os.environ["TASK_LAUNCH_STDOUT"] = "none"
        os.environ["TASK_LAUNCH_WRITE_STREAM"] = "0"
        before = self._git("rev-parse", "HEAD").stdout.strip()
        self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        rec = self.read_record()
        self.assertNotEqual(
            self._git("rev-parse", "HEAD").stdout.strip(), before,
        )
        self._committed_invalid(rec, needles=["harness-cli"])
        self.assertTrue(self.start_witness.is_file())

    def test_prose_stdout_is_envelope_parse_and_is_committed(self):
        os.environ["TASK_LAUNCH_STDOUT"] = "prose"
        before = self._git("rev-parse", "HEAD").stdout.strip()
        self.dispatch(self.argv_for(job="plan", harness="grok", stage="plan"))
        rec = self.read_record()
        self.assertNotEqual(
            self._git("rev-parse", "HEAD").stdout.strip(), before,
        )
        self._committed_invalid(rec, needles=["envelope-parse"])

    def test_timeout_kills_the_child_and_commits_the_record(self):
        os.environ["DISPATCH_TIMEOUT"] = "0.3"
        os.environ["TASK_LAUNCH_SLEEP"] = "8"
        os.environ["TASK_LAUNCH_WRITE_STREAM"] = "1"
        started = time.monotonic()
        self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        elapsed = time.monotonic() - started
        rec = self.read_record()
        self.assertLess(elapsed, 4, f"timeout must not wait out 8s: {elapsed}")
        self._committed_invalid(rec, needles=["timeout"])
        if self.start_witness.is_file():
            pid = self.read_start_witness()["pid"]
            self.assertFalse(ls.pid_is_alive(pid))

    def test_a_battery_trip_commits_a_tripped_record(self):
        done = self.home / "trip-completed.marker"
        os.environ["TASK_LAUNCH_DONE"] = str(done)
        os.environ["TASK_LAUNCH_OVER_OUT"] = "5000000"
        os.environ["TASK_LAUNCH_SLEEP"] = "6"
        os.environ["TASK_LAUNCH_WRITE_STREAM"] = "1"
        self.dispatch(self.argv_for(job="plan", harness="codex", stage="plan"))
        rec = self.read_record()
        self._committed_invalid(rec, needles=["trip"])
        self.assertFalse(
            done.is_file(),
            "a tripped run must not be allowed to complete",
        )


class ResumeFindsTheMovedStore(ls._TempLaunch):
    """After a normal launch the store is moved to <harness>-stream.
    resume restores it under CODEX_HOME / GROK_HOME before the child
    starts, then moves it forward again. A resume with no store in
    either place refuses resume-store. A failed resume keeps the prior
    stream and spend. A resume commits the record."""

    def _job_dir_of(self, rec):
        return Path(rec["snapshot"]["root"]).parent

    def test_a_codex_resume_finds_its_rollout_under_codex_home(self):
        rec, *_ = self.launch_ok(job="plan", harness="codex", stage="plan")
        job_dir = self._job_dir_of(rec)
        stream_rollouts = list(
            (job_dir / "home" / "codex-stream").rglob("rollout-*.jsonl")
        )
        live_rollouts = list(
            (job_dir / "home" / "codex").rglob("rollout-*.jsonl")
        )
        self.assertTrue(
            stream_rollouts or live_rollouts,
            "plant: a codex launch left a rollout somewhere under home/",
        )
        self.start_witness.unlink(missing_ok=True)
        self.witness.unlink(missing_ok=True)
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assertEqual(code, 0, self.combined(out, err))
        started = self.read_start_witness()
        self.assertTrue(
            started.get("rollout_present"),
            "resume must restore the rollout under CODEX_HOME/sessions "
            f"before the child starts: witness={started!r} "
            f"stream_rollouts={stream_rollouts!r} live={live_rollouts!r}",
        )
        rec2 = self.read_record()
        stream = rec2.get("session", {}).get("stream") or ""
        self.assertTrue(stream, rec2.get("session"))
        self.assertIn(
            "codex-stream", stream,
            f"after resume the stream sits under codex-stream again: "
            f"{stream!r}",
        )

    def test_a_grok_resume_finds_its_summary_under_grok_home(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        job_dir = self._job_dir_of(rec)
        summaries = list((job_dir / "home").rglob("summary.json"))
        self.assertTrue(summaries, "plant: a grok launch left a summary.json")
        self.start_witness.unlink(missing_ok=True)
        self.witness.unlink(missing_ok=True)
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assertEqual(code, 0, self.combined(out, err))
        started = self.read_start_witness()
        self.assertTrue(
            started.get("summary_present"),
            "resume must restore the summary under GROK_HOME/sessions "
            f"before the child starts: witness={started!r} "
            f"summaries={summaries!r}",
        )
        rec2 = self.read_record()
        stream = rec2.get("session", {}).get("stream") or ""
        self.assertTrue(stream, rec2.get("session"))
        self.assertIn(
            "grok-stream", stream,
            f"after resume the stream sits under grok-stream again: "
            f"{stream!r}",
        )

    def test_a_resume_with_no_store_anywhere_refuses_resume_store(self):
        rec, *_ = self.launch_ok(job="plan", harness="codex", stage="plan")
        job_dir = self._job_dir_of(rec)
        before_attempts = list(rec.get("attempts") or [])
        self.assertGreaterEqual(len(before_attempts), 1)
        removed = []
        for root in (
            job_dir / "home" / "codex" / "sessions",
            job_dir / "home" / "codex-stream" / "sessions",
        ):
            if root.exists():
                shutil.rmtree(root)
                removed.append(str(root))
        self.assertTrue(
            removed,
            "plant: deleted the session store under home/codex and "
            "home/codex-stream",
        )
        leftover = list((job_dir / "home").rglob("rollout-*.jsonl"))
        self.assertEqual(
            leftover, [],
            f"plant: no rollout remains, found {leftover!r}",
        )
        self.start_witness.unlink(missing_ok=True)
        self.witness.unlink(missing_ok=True)
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assert_refusal(
            code, out, err, ident="resume-store",
            phrases=["resume-store"],
        )
        self.assert_not_started()
        rec2 = self.read_record()
        self.assertEqual(
            len(rec2.get("attempts") or []), len(before_attempts),
            "a refused resume does not append an attempt",
        )

    def test_a_failed_resume_keeps_the_prior_stream_and_spend(self):
        rec, *_ = self.launch_ok(job="plan", harness="codex", stage="plan")
        prior_stream = rec.get("session", {}).get("stream")
        prior_spend = rec.get("session", {}).get("spend") or {}
        self.assertTrue(prior_stream, "plant: first close recorded a stream")
        self.assertIn(
            "total", prior_spend,
            f"plant: first close recorded session.spend.total: "
            f"{prior_spend!r}",
        )
        os.environ["TASK_LAUNCH_EXIT"] = "1"
        os.environ["TASK_LAUNCH_WRITE_STREAM"] = "0"
        self.start_witness.unlink(missing_ok=True)
        self.witness.unlink(missing_ok=True)
        _code, _out, _err = self.run_main(["resume", rec["id"]])
        rec2 = self.read_record()
        self.assertEqual(
            rec2.get("session", {}).get("stream"), prior_stream,
            "a failed resume must not drop the prior session.stream",
        )
        spend2 = rec2.get("session", {}).get("spend") or {}
        self.assertEqual(
            spend2.get("total"), prior_spend.get("total"),
            f"a failed resume must keep the prior session.spend: "
            f"before={prior_spend!r} after={spend2!r}",
        )
        self.assertNotIn(
            "_envelope_cause", rec2,
            "a committed record does not carry private envelope-scan keys",
        )
        raw = (
            self.repo / ".dev" / "records" / "dispatches"
            / f"{rec['id']}.json"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_envelope_cause", raw)

    def test_a_resume_commits_its_record(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.start_witness.unlink(missing_ok=True)
        self.witness.unlink(missing_ok=True)
        code, out, err = self.run_main(["resume", rec["id"]])
        self.assertEqual(code, 0, self.combined(out, err))
        subject = self._git("log", "-1", "--format=%s").stdout.strip()
        self.assertEqual(
            subject,
            f"dispatch: record {rec['id']} after attempt 2",
            f"resume commits the record after attempt 2, got {subject!r}",
        )
        self.assertEqual(
            self.porcelain(), "",
            "a resume leaves no uncommitted record",
        )


class WaitPollsTheRecord(ls._TempLaunch):
    """wait ID polls the record until closed or died. Launch prints
    record: <id> at mint."""

    def test_wait_returns_when_the_record_closes(self):
        job_id = "20260826T000000Z-plan-grok-wa1t00"
        self.force_id(job_id)
        os.environ["TASK_LAUNCH_SLEEP"] = "1"
        launched = {}

        def _run():
            launched["code"], launched["out"], launched["err"] = self.dispatch(
                self.argv_for(job="plan", harness="grok", stage="plan"),
            )

        t = threading.Thread(target=_run)
        t.start()
        record_path = (
            self.repo / ".dev" / "records" / "dispatches" / f"{job_id}.json"
        )
        deadline = time.time() + 5
        while time.time() < deadline and not record_path.is_file():
            time.sleep(0.05)
        self.assertTrue(
            record_path.is_file(),
            "plant: the launched record exists before wait",
        )
        code, out, err = self.run_main(
            ["wait", job_id, "--interval", "0.2"],
        )
        t.join(timeout=8)
        self.assertEqual(
            code, 0,
            f"wait returns 0 on a clean close: out={out!r} err={err!r} "
            f"launch={launched!r}",
        )
        line = out.strip().splitlines()[-1] if out.strip() else ""
        self.assertIn(job_id, line)
        self.assertIn("attempt=", line)
        self.assertIn("exit=", line)
        self.assertIn("tripped=", line)
        self.assertIn("envelope=", line)

    def test_wait_names_an_unknown_id(self):
        code, out, err = self.run_main(
            ["wait", "20260826T000000Z-plan-grok-none00"],
        )
        self.assert_refusal(
            code, out, err, ident="wait-target",
            phrases=["wait-target"],
        )

    def test_wait_returns_2_at_its_wall_with_the_last_poll(self):
        job_id = "20260826T000000Z-plan-grok-wa11zz"
        d = self.jobs_root / job_id
        d.mkdir()
        record_path = (
            self.repo / ".dev" / "records" / "dispatches" / f"{job_id}.json"
        )
        record_path.parent.mkdir(parents=True, exist_ok=True)
        seed = {
            "id": job_id, "lane": "dev", "stage": "plan", "unit": "work",
            "lineage": {"branch": "work", "base_sha": self.root_sha},
            "follows": [], "job": "plan", "role": "read",
            "dispatched_by": ls.AGENT,
            "at": {"launched": "2026-08-26T00:00:00Z", "closed": None},
            "snapshot": {
                "mode": "whole", "ref_name": "HEAD",
                "ref_sha": self.ref, "behind_tip": 0,
                "root": str(d / "snapshot"),
            },
            "harness": {
                "name": "grok", "version": "1.0.5",
                "isolation": {
                    "mechanism": "home",
                    "observed": {"unresolved": "not run"},
                },
                "sandbox": "plan", "containment": "policy", "argv": [],
            },
            "model": {
                "requested": ls.REQUESTED_MODEL,
                "effort_requested": None, "ran": None, "read_from": None,
            },
            "session": {"id": None, "stream": None,
                        "stream_sha256_at_close": None},
            "brief": {
                "template": {"path": "jobs.json", "sha256": "a" * 64},
                "scope": "x", "inputs": [], "sha256": "b" * 64, "bytes": 1,
            },
            "caps": {"source": "wires.py"},
            "overrides": [], "attempts": [],
            "result": None, "status": "launched",
        }
        record_path.write_text(
            json.dumps(seed, indent=2) + "\n", encoding="utf-8",
        )
        planted = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(planted["status"], "launched")
        (d / "snapshot").mkdir()
        code, out, err = self.run_main(
            ["wait", job_id, "--timeout", "0.6", "--interval", "0.2"],
        )
        self.assertEqual(
            code, 2,
            f"wait's wall is exit 2: out={out!r} err={err!r}",
        )
        text = self.combined(out, err)
        self.assertIn("poll", text)
        self.assertIn(job_id, text)
        self.assertIn("elapsed=", text)
        last_poll = [
            ln for ln in text.splitlines() if ln.strip().startswith("poll ")
        ]
        self.assertTrue(
            last_poll,
            f"the last poll line is printed at the wall: {text!r}",
        )

    def test_launch_prints_the_record_id_at_mint(self):
        rec, _witness, out, _err = self.launch_ok(
            job="plan", harness="grok", stage="plan",
        )
        matching = [
            ln for ln in out.splitlines()
            if ln.strip().startswith("record:")
        ]
        self.assertEqual(
            len(matching), 1,
            f"launch prints exactly one record: line, got {matching!r} "
            f"from stdout={out!r}",
        )
        self.assertEqual(
            matching[0].strip(), f"record: {rec['id']}",
            "the record: line carries the id and nothing else",
        )
