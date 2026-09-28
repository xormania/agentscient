"""Agy dispatch tests from CONTRACT.md and measured native evidence.

Authored independently of launch.py. Pins: fresh read prompt/model/effort
transport, session/snapshot association, missing-auth and write-role
refusal, explicit-ID resume or declared refusal, terminal usage without
double-counting a resumed total, live wall/output supervision from
observed stdout usage, and an explicit unresolved provider. Permission
flags and native provider fields are not invented.
"""

from __future__ import annotations

import json
import os
import stat
import time
import unittest
from pathlib import Path

import agy_dispatch_support as agy
import launch_support as ls


def _iso(test):
    return ls.load_path(
        test, ls.HARNESS_DIR / "isolation.py", "agy_dispatch_isolation",
    )


class _AgyLaunch(ls._TempLaunch):
    """Existing launcher fixture plus a synthetic agy executable."""

    def setUp(self):
        super().setUp()
        self._install_cli("agy")
        os.environ["WORKER_HARNESSES"] = "claude codex grok agy"
        os.environ["EXECUTABLE_AGY"] = str(self.bin / "agy")
        self.launch = self.load_launch()

    def tearDown(self):
        os.environ.pop("WORKER_HARNESSES", None)
        os.environ.pop("EXECUTABLE_AGY", None)
        os.environ.pop("AGY_FAKE_START", None)
        os.environ.pop("AGY_FAKE_DONE", None)
        os.environ.pop("AGY_FAKE_SLEEP", None)
        os.environ.pop("AGY_FAKE_STATUS", None)
        os.environ.pop("AGY_FAKE_OMIT_USAGE", None)
        os.environ.pop("AGY_FAKE_USAGE", None)
        os.environ.pop("AGY_FAKE_OUTPUT", None)
        os.environ.pop("AGY_FAKE_CONVERSATION", None)
        os.environ.pop("AGY_FAKE_RESPONSE", None)
        super().tearDown()

    def plant_auth(self, home=None):
        home = Path(home or self.home)
        path = agy.auth_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("agy-synthetic-auth\n", encoding="utf-8")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, "agy-synthetic-auth\n", "plant: auth leaf")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        canary = agy.canary_path(home)
        canary.write_text("personal-settings-must-not-cross\n", encoding="utf-8")
        self.assertEqual(
            canary.read_text(encoding="utf-8"),
            "personal-settings-must-not-cross\n",
            "plant: neighboring canary",
        )
        self.assertTrue(path.is_file())
        self.assertTrue(canary.is_file())
        return path

    def plant_transcript(self, home, conversation_id, marker):
        path = agy.transcript_path(home, conversation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "step_index": 1,
            "source": "USER",
            "type": "USER_INPUT",
            "status": "DONE",
            "created_at": "2026-09-08T00:00:00Z",
            "content": marker,
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        landed = path.read_text(encoding="utf-8")
        self.assertIn(marker, landed, "plant: transcript marker")
        self.assertIn(conversation_id, str(path))
        return path

    def dispatch_agy(self, argv=None, **kwargs):
        kwargs.setdefault("harness", agy.HARNESS)
        kwargs.setdefault("model", agy.MODEL)
        if argv is None:
            argv = self.argv_for(**kwargs)
        try:
            return self.dispatch(argv)
        except Exception as exc:
            self.fail(
                f"agy dispatch raised {type(exc).__name__}: {exc}"
            )

    def argv_list(self, witness):
        argv = [str(p) for p in witness["argv"]]
        self.assertTrue(argv, "witness argv is empty")
        return argv

    def install_live_child(self):
        dest = self.bin / "agy"
        dest.write_text(agy.LIVE_CHILD, encoding="utf-8")
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)
        self.assertIn("AGY_FAKE_SLEEP", dest.read_text(encoding="utf-8"))
        return dest


class AgyFreshReadTransport(_AgyLaunch):
    """Fresh read argv carries measured print/model/stream-json transport."""

    def test_fresh_read_argv_uses_print_equals_stream_json_and_model(self):
        prompt = Path("/synthetic/prompt.txt")
        executable = str(self.bin / "agy")
        argv = agy.call_argv(
            self.launch, model=agy.MODEL, effort="high",
            session="", prompt=prompt, flags=[], sandbox=None,
            executable=executable,
        )
        self.assertIsInstance(argv, list, "launch._argv must return argv")
        self.assertGreaterEqual(len(argv), 2, argv)
        self.assertEqual(argv[0], executable, argv)
        self.assertEqual(agy.print_tokens(argv), [agy.PRINT_EQUALS], argv)
        self.assertNotIn("--print", argv)
        self.assertIn("--input-format", argv)
        self.assertEqual(
            argv[argv.index("--input-format") + 1], agy.INPUT_FORMAT, argv,
        )
        self.assertIn("--output-format", argv)
        self.assertEqual(
            argv[argv.index("--output-format") + 1], agy.OUTPUT_FORMAT, argv,
        )
        self.assertIn(agy.DISABLE_SLASH, argv)
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], agy.MODEL, argv)
        self.assertNotIn(str(prompt), argv)
        self.assertNotIn("Reply with the single word ok.", argv)

    def test_a_path_with_spaces_stays_one_argv0_token(self):
        executable = str(self.home / "agy binary")
        argv = agy.call_argv(
            self.launch, model=agy.MODEL, executable=executable,
        )
        self.assertIsInstance(argv, list, "launch._argv must return argv")
        self.assertEqual(argv[0], executable, argv)
        self.assertNotIn("binary", argv[1:], argv)

    def test_fresh_read_does_not_invent_permission_flags(self):
        argv = agy.call_argv(self.launch, model=agy.MODEL, effort="high")
        self.assertIsInstance(argv, list, "launch._argv must return argv")
        for flag in agy.PERMISSION_FLAGS:
            self.assertNotIn(flag, argv, argv)

    def test_prompt_travels_as_one_user_ndjson_on_stdin(self):
        self.plant_auth()
        body = "synthetic-agy-prompt-body"
        os.environ["TASK_LAUNCH_NOTE"] = "agy-stdin"
        code, out, err = self.dispatch_agy(
            job="plan", harness=agy.HARNESS, stage="plan", scope=body,
        )
        self.assertTrue(
            self.witness.is_file() or self.start_witness.is_file(),
            f"child must start to record stdin: {self.combined(out, err)!r} "
            f"exit={code}",
        )
        witness = self.read_witness() if self.witness.is_file() else {}
        stdin = witness.get("stdin")
        self.assertIsInstance(stdin, str)
        self.assertTrue(stdin, "stdin must carry the user event")
        lines = [ln for ln in stdin.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, stdin)
        event = json.loads(lines[0])
        self.assertEqual(event.get("event"), "user", event)
        message = event.get("message") or {}
        content = message.get("content")
        self.assertIsInstance(content, str, event)
        self.assertIn(body, content)
        argv = self.argv_list(witness)
        self.assertEqual(agy.print_tokens(argv), [agy.PRINT_EQUALS], argv)
        self.assertNotIn(body, argv)
        self.assertNotIn(content, argv)


class AgyEffortTransport(_AgyLaunch):
    """Supported effort is forwarded unchanged; absent effort is empty."""

    def test_supported_effort_is_forwarded_as_effort_flag(self):
        self.assertEqual(len(agy.SUPPORTED_EFFORTS), 3)
        for level in agy.SUPPORTED_EFFORTS:
            tokens = agy.call_effort_argv(self.launch, level)
            self.assertEqual(
                tokens, ["--effort", level],
                f"agy effort {level!r} must not be dropped or translated: "
                f"{tokens!r}",
            )
            argv = agy.call_argv(
                self.launch, model=agy.MODEL, effort=level,
            )
            self.assertIsInstance(argv, list, argv)
            self.assertIn("--effort", argv, argv)
            self.assertEqual(argv[argv.index("--effort") + 1], level, argv)
            self.assertNotIn("--reasoning-effort", argv)
            self.assertFalse(
                any("model_reasoning_effort=" in str(t) for t in argv),
                argv,
            )

    def test_absent_effort_sends_no_effort_argv(self):
        self.assertEqual(agy.call_effort_argv(self.launch, None), [])
        self.assertEqual(agy.call_effort_argv(self.launch, ""), [])
        argv = agy.call_argv(
            self.launch, model=agy.MODEL, effort=None,
            executable=str(self.bin / "agy"),
        )
        self.assertIsInstance(argv, list, argv)
        self.assertNotIn("--effort", argv, argv)
        self.assertEqual(agy.print_tokens(argv), [agy.PRINT_EQUALS], argv)
        self.assertNotIn("--permission-mode", argv, argv)

    def test_unsupported_effort_refuses_model(self):
        self.plant_auth()
        code, out, err = self.dispatch_agy(self.argv_for(
            job="plan", harness=agy.HARNESS, stage="plan",
            extra=["--effort", agy.UNSUPPORTED_EFFORT],
        ))
        self.assert_refusal(
            code, out, err, ident="model",
            phrases=["model", agy.UNSUPPORTED_EFFORT],
        )
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])


class AgySessionSnapshotAssociation(_AgyLaunch):
    """Native conversation id binds to this job and snapshot only."""

    def test_isolation_declares_the_measured_auth_and_brain_paths(self):
        iso = _iso(self)
        self.assertIn(agy.HARNESS, iso.HARNESSES)
        entry = iso.HARNESSES[agy.HARNESS]
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry.get("mechanism"), "home", entry)
        self.assertEqual(entry.get("auth_files"), [agy.AUTH_REL], entry)
        sessions = entry.get("sessions") or {}
        self.assertEqual(sessions.get("under"), "minimal", sessions)
        self.assertEqual(sessions.get("path"), agy.BRAIN_REL, sessions)
        self.assertNotEqual(sessions.get("path"), agy.CLAUDE_FALLBACK)
        self.assertNotEqual(entry.get("auth_files"), [])

    def test_harness_meta_uses_the_measured_store_not_claude_fallback(self):
        self.plant_auth()
        job_dir = self.home / "job"
        job_dir.mkdir()
        try:
            meta = agy.call_harness_meta(
                self.launch, agy.HARNESS, "read", job_dir, os.environ,
            )
        except Exception as exc:
            self.fail(
                f"launch._harness_meta raised {type(exc).__name__}: {exc}"
            )
        self.assertIsInstance(meta, dict, "launch._harness_meta for agy")
        isolation = meta.get("isolation") or {}
        store = isolation.get("store") or meta.get("store")
        self.assertTrue(store, f"agy store must be measured: {meta!r}")
        store_s = str(store)
        self.assertIn("antigravity-cli", store_s)
        self.assertNotIn(agy.CLAUDE_FALLBACK, store_s)
        containment = meta.get("containment") or (
            (meta.get("harness") or {}).get("containment")
        )
        self.assertEqual(containment, "policy", meta)

    def test_stream_discovery_binds_the_named_conversation_not_a_newer_foreign_one(
            self):
        self.plant_auth()
        snap = self.repo
        job_dir = self.home / "job"
        home = job_dir / "home" / "agy"
        home.mkdir(parents=True)
        own = self.plant_transcript(home, agy.CONVERSATION_ID, "OWN-SESSION")
        foreign = self.plant_transcript(
            home, agy.FOREIGN_CONVERSATION_ID, "FOREIGN-NEWER",
        )
        os.utime(foreign, (2_000_000_000, 2_000_000_000))
        self.assertGreater(foreign.stat().st_mtime, own.stat().st_mtime)
        claude_decoy = self.home / ".claude" / "projects" / "decoy" / "x.jsonl"
        claude_decoy.parent.mkdir(parents=True, exist_ok=True)
        claude_decoy.write_text("claude-fallback-decoy\n", encoding="utf-8")
        os.utime(claude_decoy, (2_100_000_000, 2_100_000_000))
        self.assertIn("claude-fallback-decoy", claude_decoy.read_text())

        got = agy.call_stream(
            self.launch, job_dir, agy.HARNESS, agy.CONVERSATION_ID,
            snap, self.ref, "read",
        )
        self.assertIsInstance(got, (tuple, list), got)
        self.assertGreaterEqual(len(got), 3, got)
        path, ran, stream_id = got[0], got[1], got[2]
        self.assertEqual(stream_id, agy.CONVERSATION_ID, got)
        self.assertNotEqual(stream_id, agy.FOREIGN_CONVERSATION_ID, got)
        path_s = str(path or "")
        self.assertTrue(path_s, got)
        self.assertIn(agy.CONVERSATION_ID, path_s)
        self.assertNotIn(agy.FOREIGN_CONVERSATION_ID, path_s)
        self.assertNotIn(agy.CLAUDE_FALLBACK, path_s)
        self.assertIn("OWN-SESSION", Path(path_s).read_text(encoding="utf-8"))
        self.assertNotIn("FOREIGN-NEWER", Path(path_s).read_text(encoding="utf-8"))
        self.assertNotEqual(ran, "decoy-claude-model")


class AgyMissingAuthRefuses(_AgyLaunch):
    """Missing measured auth leaf refuses isolation before a child."""

    def test_missing_auth_leaf_refuses_isolation_and_does_not_start(self):
        path = agy.auth_path(self.home)
        self.assertFalse(path.exists(), "plant: auth leaf is absent")
        neighbor = path.parent / "personal-settings.json"
        neighbor.parent.mkdir(parents=True, exist_ok=True)
        neighbor.write_text("not-auth\n", encoding="utf-8")
        self.assertTrue(neighbor.is_file(), "plant: neighboring file is not auth")
        before = list(self.jobs_root.iterdir())
        code, out, err = self.dispatch_agy(
            job="plan", harness=agy.HARNESS, stage="plan",
        )
        text = self.assert_refusal(
            code, out, err, ident="isolation",
            phrases=["isolation", "agy"],
        )
        self.assertIn("antigravity-oauth-token", text)
        self.assertEqual(list(self.jobs_root.iterdir()), before)
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])


class AgyWriteRoleUnadmitted(_AgyLaunch):
    """Agy has no write sandbox until measured; existing refusal stands."""

    def test_agy_implement_is_refused_as_write_role_unadmitted(self):
        self.plant_auth()
        code, out, err = self.dispatch_agy(self.argv_for(
            job="implement", harness=agy.HARNESS, stage="code",
            scope="python3 -m unittest",
        ))
        self.assert_refusal(
            code, out, err, ident="write-role-unadmitted",
            phrases=["write-role-unadmitted", "agy"],
        )
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])

    def test_agy_author_tests_is_refused_the_same_way(self):
        self.plant_auth()
        code, out, err = self.dispatch_agy(self.argv_for(
            job="author-tests", harness=agy.HARNESS, stage="tests",
            scope="pin the contract",
        ))
        self.assert_refusal(
            code, out, err, ident="write-role-unadmitted",
            phrases=["write-role-unadmitted", "agy"],
        )
        self.assert_not_started()

    def test_an_agy_read_job_is_not_the_write_role_refusal(self):
        self.plant_auth()
        code, out, err = self.dispatch_agy(
            job="plan", harness=agy.HARNESS, stage="plan",
        )
        text = self.combined(out, err).lower()
        self.assertNotIn(
            "write-role-unadmitted", text,
            f"agy read must not use the write-role refusal: exit={code} {text!r}",
        )


class AgyExplicitIdResume(_AgyLaunch):
    """Resume uses --conversation <recorded id>, never implicit continue."""

    def test_resume_argv_uses_the_recorded_conversation_id(self):
        argv = agy.call_argv(
            self.launch, model=agy.MODEL, session=agy.CONVERSATION_ID,
            resume=True, executable=str(self.bin / "agy"),
        )
        self.assertIsInstance(argv, list, "resume argv")
        self.assertIn(agy.CONVERSATION_FLAG, argv, argv)
        self.assertEqual(
            argv[argv.index(agy.CONVERSATION_FLAG) + 1],
            agy.CONVERSATION_ID, argv,
        )
        for flag in agy.CONTINUE_FLAGS:
            self.assertNotIn(flag, argv, argv)
        self.assertNotIn("-r", argv)
        self.assertEqual(agy.print_tokens(argv), [agy.PRINT_EQUALS], argv)
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], agy.MODEL, argv)

    def test_resume_without_a_store_is_a_declared_refusal(self):
        self.plant_auth()
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        planted = self.read_record()
        planted["harness"] = dict(planted.get("harness") or {})
        planted["harness"]["name"] = agy.HARNESS
        planted["session"] = {
            "id": agy.CONVERSATION_ID,
            "stream": None,
            "stream_sha256_at_close": None,
        }
        path = self.the_record_path()
        before = path.read_bytes()
        path.write_text(json.dumps(planted) + "\n", encoding="utf-8")
        after = path.read_bytes()
        self.assertNotEqual(after, before, "plant: record harness is agy")
        self.assertIn(b'"agy"', after)
        self.assertIn(agy.CONVERSATION_ID.encode("utf-8"), after)
        job_dir = self.the_job_dir()
        brain = agy.brain_dir(job_dir / "home" / "agy", agy.CONVERSATION_ID)
        self.assertFalse(brain.exists(), "plant: agy store is absent")
        self.witness.unlink(missing_ok=True)
        self.start_witness.unlink(missing_ok=True)
        try:
            code, out, err = self.run_main(["resume", rec["id"]])
        except Exception as exc:
            self.fail(f"agy resume raised {type(exc).__name__}: {exc}")
        text = self.combined(out, err).lower()
        self.assertEqual(code, ls.REFUSAL_EXIT, text)
        self.assertTrue(
            "resume-store" in text or "unsupported-capability" in text,
            f"missing agy resume store must be a declared refusal: {text!r}",
        )
        self.assert_not_started()

    def test_missing_resume_does_not_block_a_fresh_read_argv(self):
        argv = agy.call_argv(
            self.launch, model=agy.MODEL, resume=False,
            executable=str(self.bin / "agy"),
        )
        self.assertIsInstance(argv, list, argv)
        self.assertNotIn(agy.CONVERSATION_FLAG, argv, argv)
        self.assertEqual(agy.print_tokens(argv), [agy.PRINT_EQUALS], argv)


class AgyTerminalUsage(_AgyLaunch):
    """Terminal result.usage is the spend; resume does not add it twice."""

    def _spend_from(self, usage, *, conversation_id=agy.CONVERSATION_ID,
                    status="SUCCESS"):
        raw = agy.framed_stdout(
            usage=usage, status=status, conversation_id=conversation_id,
        )
        job_dir = self.home / "spend-job"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "raw.out").write_bytes(raw)
        self.assertIn(b'"event": "result"', raw)
        self.assertIn(
            str(usage["total_tokens"]).encode("utf-8"), raw, "plant: total",
        )
        session = {
            "id": conversation_id,
            "stream": str(agy.transcript_path(job_dir, conversation_id)),
        }
        payload = agy.call_spend(
            self.launch, job_dir, agy.HARNESS, session,
        )
        if payload is None:
            payload = agy.call_spend(
                self.launch, job_dir, harness=agy.HARNESS, session=session,
            )
        return payload, raw

    def test_fresh_terminal_usage_does_not_fold_thinking_or_cache_into_total(self):
        payload, raw = self._spend_from(agy.FRESH_USAGE)
        self.assertIsInstance(payload, dict, payload)
        self.assertNotIn("unresolved", payload, payload)
        tokens = agy.spend_tokens(payload)
        self.assertIsInstance(tokens, dict, payload)
        self.assertEqual(tokens.get("input"), agy.FRESH_TOKENS["input"], payload)
        self.assertEqual(tokens.get("cached"), agy.FRESH_TOKENS["cached"], payload)
        self.assertEqual(tokens.get("output"), agy.FRESH_TOKENS["output"], payload)
        self.assertEqual(tokens.get("total"), agy.FRESH_TOKENS["total"], payload)
        self.assertNotEqual(tokens.get("total"), agy.THINKING_FOLDED_TOTAL)
        self.assertNotEqual(tokens.get("total"), agy.CACHE_FOLDED_TOTAL)
        self.assertIn(b'"thinking_tokens": 5', raw)
        self.assertIn(b'"cache_read_tokens": 40', raw)

    def test_canceled_result_usage_is_still_the_terminal_figure(self):
        payload, raw = self._spend_from(agy.FRESH_USAGE, status=agy.CANCELED)
        self.assertIn(b'"status": "CANCELED"', raw, "plant: CANCELED")
        self.assertIsInstance(payload, dict, payload)
        tokens = agy.spend_tokens(payload)
        self.assertIsInstance(tokens, dict, payload)
        self.assertEqual(tokens.get("total"), agy.FRESH_TOKENS["total"], payload)
        self.assertEqual(tokens.get("output"), agy.FRESH_TOKENS["output"], payload)

    def test_resume_terminal_usage_is_not_the_sum_of_both_process_totals(self):
        first, _ = self._spend_from(agy.FRESH_USAGE)
        self.assertIsInstance(first, dict, first)
        first_tokens = agy.spend_tokens(first)
        self.assertIsInstance(first_tokens, dict, first)
        self.assertEqual(first_tokens.get("total"), agy.FRESH_TOKENS["total"], first)
        payload, raw = self._spend_from(agy.RESUME_USAGE)
        self.assertIn(b'"total_tokens": 295', raw, "plant: resume cumulative")
        tokens = agy.spend_tokens(payload)
        self.assertIsInstance(tokens, dict, payload)
        self.assertEqual(tokens.get("total"), agy.RESUME_TOKENS["total"], payload)
        self.assertEqual(tokens.get("output"), agy.RESUME_TOKENS["output"], payload)
        self.assertNotEqual(tokens.get("total"), agy.DOUBLE_COUNTED_TOTAL, payload)
        self.assertNotEqual(
            tokens.get("total"),
            (first_tokens.get("total") or 0) + agy.RESUME_TOKENS["total"],
            payload,
        )


class AgyUnknownProviderIsExplicit(_AgyLaunch):
    """Provider stays unresolved; no guessed id or native field."""

    def test_agy_read_records_provider_unresolved_with_null_id_and_source(self):
        self.plant_auth()
        code, out, err = self.dispatch_agy(
            job="plan", harness=agy.HARNESS, stage="plan",
        )
        self.assertNotEqual(
            self.record_files(), [],
            f"agy read must mint a record: {self.combined(out, err)!r} "
            f"exit={code}",
        )
        rec = self.read_record()
        model = rec.get("model") or {}
        provider = model.get("provider")
        self.assertIsInstance(provider, dict, rec)
        self.assertIsNone(provider.get("id"), provider)
        self.assertIsNone(provider.get("read_from"), provider)
        unresolved = provider.get("unresolved")
        self.assertIsInstance(unresolved, str, provider)
        self.assertTrue(unresolved.strip(), provider)
        self.assertNotEqual(unresolved.strip(), agy.HARNESS)
        self.assertNotEqual(unresolved.strip(), agy.MODEL)
        self.assertNotIn("provider", model.get("ran") or "")

    def test_canceled_stdout_without_provider_stays_unresolved(self):
        raw = agy.framed_stdout(usage=agy.FRESH_USAGE, status=agy.CANCELED)
        self.assertIn(b'"status": "CANCELED"', raw, "plant: CANCELED")
        self.assertNotIn(b'"provider"', raw, "plant: no provider field")
        job_dir = self.home / "provider-job"
        job_dir.mkdir()
        (job_dir / "raw.out").write_bytes(raw)
        session = {"id": agy.CONVERSATION_ID, "stream": None}
        payload = agy.call_spend(
            self.launch, job_dir, agy.HARNESS, session,
        )
        meta = agy.call_harness_meta(
            self.launch, agy.HARNESS, "read", job_dir, os.environ,
        )
        blobs = [payload, meta]
        fn = getattr(self.launch, "_envelope", None)
        self.assertTrue(callable(fn), "launch._envelope parses stdout")
        env = fn(raw, "plan", self.ref, harness=agy.HARNESS)
        blobs.append(env)
        found_id = None
        found_unresolved = None
        for blob in blobs:
            if not isinstance(blob, dict):
                continue
            provider = blob.get("provider")
            if isinstance(provider, dict):
                found_id = provider.get("id")
                found_unresolved = provider.get("unresolved")
                break
            model = blob.get("model")
            if isinstance(model, dict) and isinstance(model.get("provider"), dict):
                provider = model["provider"]
                found_id = provider.get("id")
                found_unresolved = provider.get("unresolved")
                break
        self.assertIsNone(
            found_id,
            f"agy must not invent a provider id from CANCELED stdout: {blobs!r}",
        )
        self.assertTrue(
            isinstance(found_unresolved, str) and found_unresolved.strip(),
            f"agy provider must stay an explicit unresolved reason: {blobs!r}",
        )


class AgyLiveStdoutSupervision(_AgyLaunch):
    """Live cap-out reads observed stdout usage, not a close-only parse."""

    def test_stdout_usage_over_cap_out_kills_the_child_before_it_finishes(self):
        self.plant_auth()
        self.install_live_child()
        done = self.home / "agy-live-done.marker"
        start = self.home / "agy-live-start.marker"
        os.environ["AGY_FAKE_DONE"] = str(done)
        os.environ["AGY_FAKE_START"] = str(start)
        os.environ["AGY_FAKE_SLEEP"] = "8"
        os.environ["AGY_FAKE_OUTPUT"] = str(agy.LIVE_OUTPUT_OVER)
        os.environ["AGY_FAKE_STATUS"] = "SUCCESS"
        os.environ["DISPATCH_TIMEOUT"] = "30"
        self.assertGreater(agy.LIVE_OUTPUT_OVER, agy.LIVE_CAP_OUT)
        started = time.monotonic()
        self.dispatch_agy(self.argv_for(
            job="plan", harness=agy.HARNESS, stage="plan",
            extra=["--cap-out", str(agy.LIVE_CAP_OUT)],
        ))
        elapsed = time.monotonic() - started
        self.assertTrue(
            start.is_file(),
            "plant: child started so stdout usage can be observed",
        )
        self.assertFalse(
            done.is_file(),
            "live stdout output_tokens over cap-out must kill before COMPLETED",
        )
        self.assertLess(
            elapsed, 4,
            f"live cap-out must not wait out the 8s child: elapsed={elapsed}",
        )
        if self.start_witness.is_file():
            pid = self.read_start_witness().get("pid")
            if pid:
                self.assertFalse(ls.pid_is_alive(pid))

    def test_unavailable_live_output_does_not_let_a_capped_child_finish(self):
        self.plant_auth()
        self.install_live_child()
        done = self.home / "agy-nousage-done.marker"
        start = self.home / "agy-nousage-start.marker"
        os.environ["AGY_FAKE_DONE"] = str(done)
        os.environ["AGY_FAKE_START"] = str(start)
        os.environ["AGY_FAKE_SLEEP"] = "6"
        os.environ["AGY_FAKE_OMIT_USAGE"] = "1"
        os.environ["DISPATCH_TIMEOUT"] = "30"
        started = time.monotonic()
        code, out, err = self.dispatch_agy(self.argv_for(
            job="plan", harness=agy.HARNESS, stage="plan",
            extra=["--cap-out", str(agy.LIVE_CAP_OUT)],
        ))
        elapsed = time.monotonic() - started
        if start.is_file():
            self.assertFalse(
                done.is_file(),
                "missing live output evidence must not disable a known cap-out",
            )
            self.assertLess(
                elapsed, 4,
                f"unavailable live usage must stop the child: elapsed={elapsed}",
            )
            return
        self.assert_refusal(
            code, out, err, ident="unsupported-capability",
            phrases=["unsupported-capability", "output"],
        )


if __name__ == "__main__":
    unittest.main()
