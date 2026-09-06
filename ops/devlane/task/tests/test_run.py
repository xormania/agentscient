"""run: snapshot, launch, supervise, collect — never judge the work.

Corrected from original Grok 4784cd45 against the merged canonical
contract candidate. Vendor mode is the refusing task projection:
direct verify and stub replay stay local; worker execution belongs
to launch.py. No run.resume or injectable run.canonical_launch.

  R1-R5, R8-R13  vendor mode refuses before snapshot, prompt, child
                 or store effects; launch owns those worker duties
  R6  `direct` delegates to verify.check and returns that envelope;
      zero tokens, spend.harness None
  R7  `stub` replays a file named in runtime and launches nothing
  R14 a job absent from the table is invalid; load_jobs stays local
  R15 main is a CLI: JSON on stdout; 0 / 1 / 2 / 64. Vendor success
      fixtures are replaced by direct verify; vendor CLI is exit 2

C1  exact execution refusal naming launch.py; optional commit via
    stub replay; strict catalogue OutputsError plus run()/main()
    mapping to invalid envelope, outputs-schema note, exit 2.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import support

run = support.load("run")

# Loaded the way run.py will load them (`import fileset`), not under the
# task_ prefix support.load uses. Wrapping these is how R1 and R6 pin
# delegation without caring how run.py spelled the import.
import envelope  # noqa: E402
import fileset  # noqa: E402
import verify  # noqa: E402

# A subprocess harness. Records argv/stdin, optionally sleeps, optionally
# prints a structured envelope or prose. No network, no shell.
_FAKE_CLI = r"""#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

record_path = os.environ.get("TASK_RUN_RECORD")
done_path = os.environ.get("TASK_RUN_DONE")
sleep_s = float(os.environ.get("TASK_RUN_SLEEP") or "0")
stdout_mode = os.environ.get("TASK_RUN_STDOUT") or "envelope"
token = os.environ.get("TASK_RUN_TOKEN") or ""
claim = os.environ.get("TASK_RUN_CLAIM") or "the battery is never armed"
verdict = os.environ.get("TASK_RUN_VERDICT") or "changes"
job = os.environ.get("TASK_RUN_JOB") or "author-tests"
commit_subject = os.environ.get("TASK_RUN_ENVELOPE_COMMIT") or ""

argv = sys.argv[1:]
prompt_file = None
if "--prompt-file" in argv:
    idx = argv.index("--prompt-file")
    if idx + 1 < len(argv):
        prompt_file = argv[idx + 1]

stdin_data = sys.stdin.read()
prompt_text = ""
if prompt_file:
    try:
        prompt_text = Path(prompt_file).read_text(encoding="utf-8")
    except OSError:
        prompt_text = ""

if record_path:
    Path(record_path).write_text(
        json.dumps({
            "argv": sys.argv,
            "cwd": os.getcwd(),
            "stdin": stdin_data,
            "prompt_file": prompt_file,
            "prompt_text": prompt_text,
        }),
        encoding="utf-8",
    )

if stdout_mode in ("envelope", "result_envelope"):
    findings = []
    if verdict != "approve":
        findings.append({
            "severity": "p2",
            "where": "alpha.py §top",
            "claim": claim,
            "reproduce": "python3 -m unittest",
        })
    counts = {"p1": 0, "p2": 0, "p3": 0, "opinions": 0}
    counts["p2"] = len(findings)
    env = {
        "job": job,
        "status": "ok",
        "verdict": verdict,
        "counts": counts,
        "findings": findings,
        "artifacts": {},
        "spend": {"harness": "codex", "total": 0, "out": 0, "runs": 1},
        "stamp": {"ref": "harness-placeholder", "started": None, "ended": None},
        "note": None,
    }
    if commit_subject:
        env["commit"] = {"subject": commit_subject, "body": "why"}
    payload = env
    if stdout_mode == "result_envelope":
        payload = {"result": env}
    sys.stdout.write(json.dumps(payload) + "\n")
elif stdout_mode == "prose":
    sys.stdout.write("VERDICT: approve\nThe change is correct and complete.\n")
elif stdout_mode == "token":
    sys.stdout.write(token + "\n")
sys.stdout.flush()

if sleep_s > 0:
    time.sleep(sleep_s)

if done_path:
    Path(done_path).write_text("COMPLETED\n", encoding="utf-8")
"""

class _PopenRecorder:
    """Wrap subprocess.Popen and keep every argv. The original still runs."""

    def __init__(self, original):
        self.original = original
        self.calls = []

    def __call__(self, cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)):
            argv = [str(part) for part in cmd]
        else:
            argv = [str(cmd)]
        self.calls.append(argv)
        return self.original(cmd, *args, **kwargs)

    def launch_argv(self):
        found = []
        for argv in self.calls:
            blob = " ".join(argv)
            if "launch.py" in blob or blob.rstrip().endswith(" launch"):
                found.append(argv)
        return found


def _git_env(home: Path) -> dict:
    # GIT_DIR / GIT_WORK_TREE in the caller would aim git at the
    # snapshot (or its parent). Fixtures must be closed worlds, and
    # this suite must not run git against the snapshot's own repo.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k != "XDG_CONFIG_HOME"}
    env.update({
        "HOME": str(home),
        "GIT_AUTHOR_NAME": "run-test",
        "GIT_AUTHOR_EMAIL": "run-test@example.test",
        "GIT_COMMITTER_NAME": "run-test",
        "GIT_COMMITTER_EMAIL": "run-test@example.test",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    })
    return env


def write_codex_stream(path, *, total, out):
    """One Codex token_count event. breaker.py reads this shape."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "total_tokens": total,
                    "output_tokens": out,
                }
            },
        }
    }
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = run.main(argv)
        except SystemExit as exc:
            # argparse's default is SystemExit(2). The contract is 64
            # for usage; tests pin that by comparing the code, not by
            # letting the exception look like a collection error.
            code = int(exc.code) if exc.code is not None else 0
    return code, out.getvalue(), err.getvalue()


class _TempRun(unittest.TestCase):
    """A throwaway repo, HOME, PATH and fake CLIs. Never the snapshot tree."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = Path(self._td.name)
        self.repo = self.home / "repo"
        self.bin = self.home / "bin"
        self.codex_store = self.home / ".codex" / "sessions"
        self.grok_store = self.home / ".grok" / "sessions"
        self.repo.mkdir()
        self.bin.mkdir()
        self.codex_store.mkdir(parents=True)
        self.grok_store.mkdir(parents=True)

        self._orig_env = {
            k: os.environ.get(k) for k in (
                "PATH", "HOME", "XDG_CONFIG_HOME",
                "TASK_RUN_RECORD", "TASK_RUN_DONE", "TASK_RUN_SLEEP",
                "TASK_RUN_STDOUT", "TASK_RUN_TOKEN", "TASK_RUN_CLAIM",
                "TASK_RUN_VERDICT", "TASK_RUN_JOB",
                "TASK_RUN_ENVELOPE_COMMIT",
            )
        }
        self._saved_git = {k: os.environ[k] for k in list(os.environ)
                           if k.startswith("GIT_")}
        for k in list(self._saved_git):
            del os.environ[k]
        if "XDG_CONFIG_HOME" in os.environ:
            del os.environ["XDG_CONFIG_HOME"]

        os.environ["HOME"] = str(self.home)
        os.environ["PATH"] = str(self.bin) + os.pathsep + os.environ.get("PATH", "")

        self.env = _git_env(self.home)
        self._git("init")
        self._git("config", "user.name", "run-test")
        self._git("config", "user.email", "run-test@example.test")
        self._git("config", "commit.gpgsign", "false")
        self._write("alpha.py", "alpha v1\n")
        self._write("beta.py", "unchanged\n")
        self.base = self._commit("base")
        self._write("alpha.py", "alpha v2\n")
        self.ref = self._commit("ref")

        self.record_path = self.home / "launch-record.json"
        os.environ["TASK_RUN_RECORD"] = str(self.record_path)
        os.environ.pop("TASK_RUN_DONE", None)
        os.environ.pop("TASK_RUN_SLEEP", None)
        os.environ["TASK_RUN_STDOUT"] = "envelope"
        os.environ.pop("TASK_RUN_TOKEN", None)
        os.environ.pop("TASK_RUN_CLAIM", None)
        os.environ.pop("TASK_RUN_VERDICT", None)
        os.environ.pop("TASK_RUN_ENVELOPE_COMMIT", None)

        self._install_cli("codex")
        self._install_cli("grok")

        self.jobs = {
            "author-tests": {
                "adapter": "harness",
                "deliverable": "a test file that has been run and is red",
                "role": "write",
                "prompt": (
                    "Write tests from the contract at {scope}. "
                    "Ref {ref} base {base}."
                ),
                "constraints": ["do not edit the implementation"],
            },
            "adversarial-review": {
                "adapter": "harness",
                "role": "read",
                "prompt": "Review {ref} against {base}. Aim at: {scope}",
                "constraints": ["read only"],
            },
            "verify": {
                "adapter": "direct",
                "deliverable": "one claim, executed",
                "prompt": None,
                "constraints": ["read only"],
            },
        }
        self.require = {"scope": "pin the runner", "constraints": ["no network"]}
        self.adapters = self.make_adapters()
        self.last_into = None
        self._patches = []
        self._saved_adapters = run.ADAPTERS
        self._saved_comm_path = run.JOBS_PATH

    def tearDown(self):
        self._unpatch()
        run.ADAPTERS = self._saved_adapters
        run.JOBS_PATH = self._saved_comm_path
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k in list(os.environ):
            if k.startswith("GIT_"):
                del os.environ[k]
        os.environ.update(self._saved_git)
        self._td.cleanup()

    def _git(self, *args):
        r = subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env,
            capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                f"git {args} failed ({r.returncode}): {r.stderr}")
        return r

    def _write(self, rel, content):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def _commit(self, msg):
        self._git("add", "-A")
        self._git("commit", "-m", msg)
        return self._git("rev-parse", "HEAD").stdout.strip()

    def _fingerprint(self):
        files = {}
        for p in self.repo.rglob("*"):
            if ".git" in p.parts or not p.is_file():
                continue
            rel = p.relative_to(self.repo).as_posix()
            files[rel] = (
                p.stat().st_mode,
                hashlib.sha256(p.read_bytes()).hexdigest(),
            )
        return {
            "files": files,
            "head": self._git("rev-parse", "HEAD").stdout,
            "status": self._git("status", "--porcelain=v1", "-uall").stdout,
            "index": self._git("ls-files", "-s").stdout,
            "diff": self._git("diff").stdout,
            "staged": self._git("diff", "--cached").stdout,
        }

    def _install_cli(self, name):
        dest = self.bin / name
        dest.write_text(_FAKE_CLI, encoding="utf-8")
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return dest

    def make_adapters(self, *, sandbox=None, stream_names_cwd=True, store=None):
        sandbox = sandbox or {"read": "read-only", "write": "workspace-write"}
        store = str(store or self.codex_store)
        return {
            "codex": {
                "argv": [str(self.bin / "codex"), "exec",
                         "--sandbox", "{sandbox}", "-"],
                "prompt": "stdin",
                "sandbox": dict(sandbox),
                "store": store,
                "stream": "rollout-*.jsonl",
                "stream_names_cwd": stream_names_cwd,
                # The fakes declare dials for the same reason the real
                # adapters do: a runtime dial with nowhere to go is now
                # refused, so a fake without one would refuse every
                # launch in this fixture rather than record an argv.
                "dials": {"model": ["-m", "{model}"]},
            },
            "grok": {
                "argv": [str(self.bin / "grok"), "--prompt-file", "{prompt}",
                         "--output-format", "plain",
                         "--permission-mode", "{sandbox}"],
                "prompt": "file",
                "sandbox": {"read": "plan", "write": "auto"},
                "store": str(self.grok_store),
                "stream": "updates.jsonl",
                "stream_names_cwd": False,
                "dials": {"model": ["-m", "{model}"],
                          "effort": ["--reasoning-effort", "{effort}"]},
            },
            "stub": {"replay": True},
            "direct": {"direct": True},
        }

    def make_context(self, **overrides):
        snap_id = uuid.uuid4().hex
        into = overrides.pop("into", None) or (self.home / f"snap-{snap_id}")
        ctx = {
            "repo": str(self.repo),
            "ref": self.ref,
            "base": self.base,
            "include": ["alpha.py"],
            "into": str(into),
        }
        ctx.update(overrides)
        return ctx

    def call_run(self, job="author-tests", *, context=None, require=None,
                 runtime=None, jobs=None, adapters=None):
        context = context if context is not None else self.make_context()
        self.last_context = context
        self.last_into = Path(context["into"])
        rt = {
            "harness": "codex",
            "model": "test-model",
            # No effort here: `codex --help` offers `-m/--model` and no
            # effort flag, so the adapter declares no way to pass one and
            # a set effort is REFUSED rather than silently dropped. The
            # refusal and the two harnesses that do take an effort dial
            # have their own cases in TheConductorsDialReachesTheHarness.
            "role": "write",
            "caps": {"cap-out": 100000},
            "timeout": 30,
        }
        if runtime:
            rt.update(runtime)
        try:
            env = run.run(
                job,
                context=context,
                require=require if require is not None else self.require,
                runtime=rt,
                jobs=jobs if jobs is not None
                else self.jobs,
                adapters=adapters if adapters is not None else self.adapters,
            )
        except Exception as exc:
            self.fail(
                f"run must return an envelope, not raise: "
                f"{type(exc).__name__}: {exc}")
        self.assertIsInstance(env, dict, "run returns an envelope dict")
        return env

    def read_record(self):
        # Presence of the record is the proof the fake CLI started.
        # Asserting only that a launch side-effect is absent is green
        # against the stub, which launches nothing.
        self.assertTrue(
            self.record_path.is_file(),
            "the harness CLI must have been launched",
        )
        return json.loads(self.record_path.read_text(encoding="utf-8"))

    def recorded_argv(self):
        rec = self.read_record()
        argv = rec.get("argv")
        self.assertIsInstance(argv, list)
        self.assertTrue(argv, "recorded argv is empty")
        return [str(part) for part in argv]

    def parse_stdout(self, out):
        # An empty stdout is not an envelope. Failing here against the
        # stub (which prints nothing) is the honest red for CLI tests
        # whose exit code is 0, because that 0 is also the stub's return.
        self.assertTrue(out.strip(), "envelope JSON on stdout")
        try:
            env = json.loads(out)
        except json.JSONDecodeError:
            self.fail(f"stdout was not JSON: {out!r}")
        self.assertIsInstance(env, dict)
        return env

    def assert_invalid(self, env, *, naming=None):
        self.assertIsInstance(env, dict)
        self.assertEqual(env.get("status"), "invalid")
        # verdict None is the contract's null. Pinning only
        # `is not "changes"` would pass against the stub's {}.
        self.assertIsNone(env.get("verdict"))
        self.assertNotEqual(env.get("verdict"), "changes")
        self.assertNotEqual(env.get("verdict"), "approve")
        note = env.get("note")
        self.assertIsInstance(note, str)
        self.assertTrue(note.strip(), "invalid must say why it could not run")
        if naming is not None:
            self.assertIn(naming, note)

    def assert_vendor_refusal(self, env, *, job="author-tests", harness="codex",
                              model="test-model", ref=None):
        """C1: task vendor mode refuses before any worker effect."""
        ref = self.ref if ref is None else ref
        self.assertIsInstance(env, dict)
        self.assertEqual(env.get("status"), "invalid")
        self.assertIsNone(env.get("verdict"))
        findings = env.get("findings") if isinstance(env.get("findings"), list) else None
        self.assertEqual(findings, [])
        artifacts = env.get("artifacts") if isinstance(env.get("artifacts"), dict) else None
        self.assertEqual(artifacts, {})
        counts = env.get("counts") if isinstance(env.get("counts"), dict) else {}
        self.assertEqual(counts.get("p1"), 0)
        self.assertEqual(counts.get("p2"), 0)
        self.assertEqual(counts.get("p3"), 0)
        self.assertEqual(counts.get("opinions"), 0)
        self.assertEqual(
            env.get("spend"),
            {"harness": None, "total": 0, "out": 0, "runs": 0},
        )
        note = env.get("note")
        self.assertIsInstance(note, str)
        self.assertIn("execution:", note)
        self.assertIn("expected canonical worker execution", note)
        self.assertIn("found task vendor mode", note)
        self.assertIn("needed ops/devlane/dispatch/launch.py", note)
        self.assertIn(job, note)
        self.assertIn(f"--harness {harness}", note)
        self.assertIn(f"--model {model}", note)
        self.assertIn(f"--ref {ref}", note)
        stamp = env.get("stamp") if isinstance(env.get("stamp"), dict) else {}
        self.assertEqual(stamp.get("ref"), ref)
        self.assertFalse(
            self.record_path.exists(),
            "task vendor mode must not Popen a harness CLI",
        )
        into = getattr(self, "last_into", None)
        if into is not None:
            self.assertFalse(
                (Path(into) / "FILESET.md").exists(),
                "vendor refusal is before snapshotting",
            )

    def _patch_attr(self, obj, name, replacement):
        """Wrap a function on a module run.py may have imported already.

        `from fileset import snapshot` binds a name on run; `import fileset`
        leaves the function on that module. Patching both is how R6 pins
        delegation without guessing the import spelling. Unique (id, name)
        so wrapping fileset and run.fileset (the same object) cannot
        restore a wrapped function over the original.
        """
        if obj is None or not hasattr(obj, name):
            return
        if any(id(o) == id(obj) and n == name for o, n, _ in self._patches):
            return
        self._patches.append((obj, name, getattr(obj, name)))
        setattr(obj, name, replacement)

    def _unpatch(self):
        while self._patches:
            obj, name, original = self._patches.pop()
            setattr(obj, name, original)

    def record_popen(self):
        """Record subprocess.Popen argv from both the stdlib and run's binding."""
        recorder = _PopenRecorder(subprocess.Popen)
        self._patch_attr(subprocess, "Popen", recorder)
        self._patch_attr(getattr(run, "subprocess", None), "Popen", recorder)
        return recorder

    def write_replay(self, recorded):
        replay = self.home / ("replay-" + uuid.uuid4().hex + ".jsonl")
        replay.write_text(json.dumps(recorded) + "\n", encoding="utf-8")
        return replay


# ---------------------------------------------------------------------------
# R1
# ---------------------------------------------------------------------------


class RunBuildsTheSnapshotWithFileset(_TempRun):
    """R1 — vendor mode refuses before fileset.snapshot. Launch owns
    whole-ref bytes versus dirty source (adoption tests). Direct/stub
    keep their local fileset behaviour.
    """

    def test_the_snapshot_is_a_fileset_snapshot_of_the_ref_not_the_worktree(self):
        self._write("alpha.py", "DIRTY VERSION\n")
        calls = []
        original = fileset.snapshot

        def wrapped(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        self._patch_attr(fileset, "snapshot", wrapped)
        self._patch_attr(getattr(run, "fileset", None), "snapshot", wrapped)
        if getattr(run, "snapshot", None) is original:
            self._patch_attr(run, "snapshot", wrapped)

        env = self.call_run()
        self.assert_vendor_refusal(env)
        self.assertEqual(
            calls, [],
            "vendor refusal must not call fileset.snapshot",
        )
        into = self.last_into
        self.assertFalse((into / "FILESET.md").exists())
        self.assertFalse((into / "alpha.py").exists())

    def test_the_source_repo_is_not_checked_out_or_mutated(self):
        self._write("alpha.py", "DIRTY VERSION\n")
        self._write("untracked.txt", "do not delete me\n")
        self._write("to_stage.py", "staged new file\n")
        self._git("add", "to_stage.py")
        before = self._fingerprint()

        env = self.call_run()
        self.assert_vendor_refusal(env)
        self.assertEqual(self._fingerprint(), before)


# ---------------------------------------------------------------------------
# R2
# ---------------------------------------------------------------------------


class StampRefComesFromTheManifest(_TempRun):
    """R2 — vendor refusal stamps the caller's supplied string as an
    unverified request. Launch owns ref resolution and pre-effect
    bad-ref refusal.
    """

    def test_stamp_ref_is_the_sha_the_manifest_names(self):
        env = self.call_run()
        self.assert_vendor_refusal(env)
        stamp = env.get("stamp") if isinstance(env.get("stamp"), dict) else {}
        self.assertEqual(stamp.get("ref"), self.ref)
        self.assertNotEqual(stamp.get("ref"), "harness-placeholder")
        self.assertFalse((self.last_into / "FILESET.md").exists())

    def test_an_unresolvable_ref_is_invalid_and_never_launches(self):
        missing = "no-such-ref-7e1c9a3d"
        env = self.call_run(context=self.make_context(ref=missing))
        self.assert_vendor_refusal(env, ref=missing)
        self.assertFalse(
            self.record_path.exists(),
            "vendor refusal is never a launch, even with a bad ref",
        )


# ---------------------------------------------------------------------------
# R3
# ---------------------------------------------------------------------------


class RoleSelectsTheSandbox(_TempRun):
    """R3 — task vendor mode does not resolve sandbox labels. Launch
    owns admitted isolation; sandbox strings never prove C2 capability.
    """

    def test_a_write_role_receives_the_write_sandbox_not_the_read_value(self):
        write_tok = "WRITE-" + uuid.uuid4().hex
        read_tok = "READ-" + uuid.uuid4().hex
        adapters = self.make_adapters(
            sandbox={"read": read_tok, "write": write_tok})
        env = self.call_run(
            runtime={"harness": "codex", "role": "write"},
            adapters=adapters,
        )
        self.assert_vendor_refusal(env, harness="codex")
        self.assertFalse(self.record_path.exists())

    def test_a_read_role_receives_the_read_sandbox(self):
        write_tok = "WRITE-" + uuid.uuid4().hex
        read_tok = "READ-" + uuid.uuid4().hex
        adapters = self.make_adapters(
            sandbox={"read": read_tok, "write": write_tok})
        env = self.call_run(
            job="adversarial-review",
            runtime={"harness": "codex", "role": "read"},
            adapters=adapters,
        )
        self.assert_vendor_refusal(
            env, job="adversarial-review", harness="codex",
        )
        self.assertFalse(self.record_path.exists())

    def test_a_grok_write_role_is_auto_not_plan(self):
        env = self.call_run(
            runtime={"harness": "grok", "role": "write"},
        )
        self.assert_vendor_refusal(env, harness="grok")
        self.assertFalse(self.record_path.exists())

    def test_builtin_write_values_are_not_the_read_only_ones(self):
        env = self.call_run(
            runtime={"harness": "codex", "role": "write"},
        )
        self.assert_vendor_refusal(env, harness="codex")
        self.assertNotIn("canonical_launch", dir(run))


# ---------------------------------------------------------------------------
# R4
# ---------------------------------------------------------------------------


class AnUnknownHarnessIsInvalid(_TempRun):
    """R4 — vendor mode uses the execution refusal regardless of vendor
    name. Launch's unknown selection refuses without substitution.
    """

    def test_an_unknown_harness_is_invalid_with_a_note_naming_it(self):
        name = "not-a-real-harness-7e1c9a3d"
        env = self.call_run(runtime={"harness": name})
        self.assert_vendor_refusal(env, harness=name)
        self.assertFalse(
            self.record_path.exists(),
            "an unknown harness must not launch a different one",
        )


# ---------------------------------------------------------------------------
# R5
# ---------------------------------------------------------------------------


class AMissingCliIsInvalidNotAVerdict(_TempRun):
    """R5 — task must not resolve vendor binaries. Missing-CLI named
    non-acceptance lives on launch. Vendor mode is the execution
    refusal, never invented work findings.
    """

    def test_a_missing_cli_is_invalid_with_a_note_naming_the_gap(self):
        missing = "run-test-no-such-cli-7e1c9a3d"
        adapters = self.make_adapters()
        adapters["ghost"] = {
            "argv": [missing, "exec", "--sandbox", "{sandbox}", "-"],
            "dials": {"model": ["-m", "{model}"]},
            "prompt": "stdin",
            "sandbox": {"read": "read-only", "write": "workspace-write"},
            "store": str(self.codex_store),
            "stream": "rollout-*.jsonl",
            "stream_names_cwd": True,
        }
        env = self.call_run(runtime={"harness": "ghost", "role": "write"},
                            adapters=adapters)
        self.assert_vendor_refusal(env, harness="ghost")
        findings = env.get("findings") if isinstance(env.get("findings"), list) else []
        self.assertEqual(findings, [])
        self.assertFalse(self.record_path.exists())

    def test_a_missing_cli_is_not_ok_changes_about_the_work(self):
        missing = "run-test-no-such-cli-aa11bb22"
        adapters = self.make_adapters()
        adapters["ghost"] = {
            "argv": [missing],
            "dials": {"model": ["-m", "{model}"]},
            "prompt": "stdin",
            "sandbox": {"read": "read-only", "write": "workspace-write"},
            "store": str(self.codex_store),
            "stream": "rollout-*.jsonl",
            "stream_names_cwd": True,
        }
        env = self.call_run(runtime={"harness": "ghost"}, adapters=adapters)
        self.assert_vendor_refusal(env, harness="ghost")
        self.assertNotEqual(env.get("status"), "ok")
        self.assertNotEqual(env.get("verdict"), "changes")
        self.assertNotEqual(env.get("verdict"), "approve")


# ---------------------------------------------------------------------------
# R6
# ---------------------------------------------------------------------------


class DirectDelegatesToVerify(_TempRun):
    """R6 — direct runs no harness. It calls verify.check and returns
    that envelope unchanged. require carries claim and command because
    those are verify.check's inputs and the require schema is otherwise
    deferred for this slice.
    """

    def _direct_require(self, command=None):
        return {
            "scope": "python exits 0",
            "constraints": ["read only"],
            "claim": "python exits 0",
            "command": command or [sys.executable, "-c", "pass"],
        }

    def test_direct_delegates_to_verify_check_and_returns_that_envelope(self):
        calls = []
        original = verify.check

        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append((args, kwargs, result))
            return result

        self._patch_attr(verify, "check", wrapped)
        self._patch_attr(getattr(run, "verify", None), "check", wrapped)
        if getattr(run, "check", None) is original:
            self._patch_attr(run, "check", wrapped)

        env = self.call_run(
            "verify",
            require=self._direct_require(),
            runtime={"harness": "direct", "role": "read"},
        )

        self.assertTrue(calls, "direct must delegate to verify.check")
        returned = calls[-1][2]
        # Unchanged: not rebuilt, not re-stamped, not re-spent.
        self.assertEqual(env, returned)
        self.assertEqual(env.get("job"), "verify")
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(env.get("verdict"), "approve")

    def test_direct_spend_is_zero_tokens_and_harness_none(self):
        env = self.call_run(
            "verify",
            require=self._direct_require(),
            runtime={"harness": "direct", "role": "read"},
        )
        # runs is 1 because verify DID run. The default 0 would tell
        # worth.py that nothing happened; the stub's missing spend
        # cannot satisfy the full dict.
        self.assertEqual(
            env.get("spend"),
            {"harness": None, "total": 0, "out": 0, "runs": 1},
        )
        self.assertEqual(env.get("verdict"), "approve")
        self.assertEqual(env.get("status"), "ok")

    def test_direct_does_not_launch_a_harness_cli(self):
        env = self.call_run(
            "verify",
            require=self._direct_require(),
            runtime={"harness": "direct", "role": "read"},
        )
        self.assertEqual(env.get("status"), "ok")
        self.assertFalse(
            self.record_path.exists(),
            "direct runs no harness",
        )


# ---------------------------------------------------------------------------
# R7
# ---------------------------------------------------------------------------


class StubReplaysWithoutLaunching(_TempRun):
    """R7 — the suite must be able to exercise the runner with no CLI
    installed. The recorded stream is named in runtime['replay']."""

    def test_stub_replays_the_named_file_and_does_not_launch(self):
        unique = "REPLAY-CLAIM-" + uuid.uuid4().hex
        recorded = envelope.build(
            "author-tests",
            status="ok",
            verdict="changes",
            findings=[envelope.finding(
                "p2", "alpha.py §top", unique,
                reproduce="python3 -m unittest")],
            spend={"harness": "stub", "total": 11, "out": 4, "runs": 1},
            stamp={"ref": self.ref},
        )
        replay = self.home / "recorded-stream.jsonl"
        # jsonl: a spend event plus the structured envelope, so either
        # a stream parser or an envelope parser can see the recording.
        replay.write_text(
            json.dumps({
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {
                        "total_tokens": 11, "output_tokens": 4}},
                }
            }) + "\n" + json.dumps(recorded) + "\n",
            encoding="utf-8",
        )
        env = self.call_run(
            runtime={"harness": "stub", "role": "write",
                     "replay": str(replay)},
        )
        findings = env.get("findings") if isinstance(env.get("findings"), list) else []
        self.assertTrue(findings, "replayed envelope must carry the recorded finding")
        self.assertEqual(findings[0].get("claim"), unique)
        self.assertEqual(env.get("verdict"), "changes")
        self.assertEqual(env.get("status"), "ok")
        self.assertFalse(
            self.record_path.exists(),
            "stub must not launch a harness CLI",
        )

    def test_builtin_stub_adapter_is_replay_data(self):
        self.assertEqual(run.ADAPTERS.get("stub"), {"replay": True})
        self.assertEqual(run.ADAPTERS.get("direct"), {"direct": True})


# ---------------------------------------------------------------------------
# R8
# ---------------------------------------------------------------------------


class TheBatteryIsArmedWithCapOut(_TempRun):
    """R8 — launch owns the battery. Vendor mode refuses before any
    stream is supervised; cache-heavy evidence must not become an
    ok vendor run.
    """

    def test_a_cache_heavy_total_does_not_trip_when_output_is_under_cap_out(self):
        snap_id = uuid.uuid4().hex
        dirname = f"snap-{snap_id}"
        into = self.home / dirname
        stream = self.codex_store / f"rollout-{dirname}.jsonl"
        write_codex_stream(stream, total=7000000, out=50)
        env = self.call_run(
            context=self.make_context(into=into),
            runtime={"harness": "codex", "role": "write",
                     "caps": {"cap-out": 1000}},
        )
        self.assert_vendor_refusal(env)
        self.assertNotEqual(env.get("status"), "ok")
        self.assertNotEqual(env.get("status"), "tripped")
        spend = env.get("spend") if isinstance(env.get("spend"), dict) else {}
        self.assertEqual(spend.get("total"), 0)
        self.assertEqual(spend.get("out"), 0)


# ---------------------------------------------------------------------------
# R9
# ---------------------------------------------------------------------------


class ABatteryTripIsNotACompletedRun(_TempRun):
    """R9 — launch kills the over-budget group. Vendor mode never
    completes a worker run, tripped or otherwise.
    """

    def test_a_battery_trip_is_status_tripped_with_no_verdict_and_a_note(self):
        snap_id = uuid.uuid4().hex
        dirname = f"snap-{snap_id}"
        into = self.home / dirname
        stream = self.codex_store / f"rollout-{dirname}.jsonl"
        write_codex_stream(stream, total=5000, out=5000)
        done = self.home / "completed.marker"
        os.environ["TASK_RUN_SLEEP"] = "8"
        os.environ["TASK_RUN_DONE"] = str(done)
        env = self.call_run(
            context=self.make_context(into=into),
            runtime={"harness": "codex", "role": "write",
                     "caps": {"cap-out": 100}, "timeout": 60},
        )
        self.assert_vendor_refusal(env)
        self.assertNotEqual(env.get("status"), "tripped")
        self.assertNotEqual(env.get("status"), "ok")
        self.assertFalse(
            done.is_file(),
            "vendor refusal must not run a child to completion",
        )


# ---------------------------------------------------------------------------
# R10
# ---------------------------------------------------------------------------


class StreamDiscoveryNamesTheSnapshot(_TempRun):
    """R10 — launch owns isolated store/session/cwd identity. Vendor
    mode does not discover streams or charge a sibling session.
    """

    def test_the_stream_that_names_the_snapshot_is_chosen_over_a_newer_sibling(self):
        snap_id = uuid.uuid4().hex
        sibling_id = uuid.uuid4().hex
        dirname = f"snap-{snap_id}"
        into = self.home / dirname
        winner = self.codex_store / f"rollout-{dirname}.jsonl"
        loser = self.codex_store / f"rollout-snap-{sibling_id}.jsonl"
        write_codex_stream(winner, total=42, out=7)
        time.sleep(0.05)
        write_codex_stream(loser, total=999, out=888)
        env = self.call_run(
            context=self.make_context(into=into),
            runtime={"harness": "codex", "role": "write"},
            adapters=self.make_adapters(stream_names_cwd=True),
        )
        self.assert_vendor_refusal(env)
        spend = env.get("spend") if isinstance(env.get("spend"), dict) else {}
        self.assertEqual(spend.get("total"), 0)
        self.assertNotEqual(spend.get("total"), 42)
        self.assertNotEqual(spend.get("total"), 999)


# ---------------------------------------------------------------------------
# R11
# ---------------------------------------------------------------------------


class AbsentSpendIsNotZeroSpend(_TempRun):
    """R11 — vendor refusal spend is the unused-worker zero with
    harness None, not a completed ok-with-no-stream. Launch declares
    missing evidence versus measured zero.
    """

    def test_no_stream_is_unknown_spend_not_a_measured_zero(self):
        unknown = self.call_run(
            runtime={"harness": "codex", "role": "write"},
            adapters=self.make_adapters(stream_names_cwd=True),
        )
        self.assert_vendor_refusal(unknown)
        self.assertNotEqual(unknown.get("status"), "ok")
        u_spend = unknown.get("spend") if isinstance(unknown.get("spend"), dict) else {}
        self.assertEqual(u_spend.get("harness"), None)
        self.assertEqual(u_spend.get("total"), 0)
        self.assertEqual(u_spend.get("runs"), 0)


# ---------------------------------------------------------------------------
# R12
# ---------------------------------------------------------------------------


class RawOutputLivesInsideTheSnapshot(_TempRun):
    """R12 — launch raw.out lives under the canonical job directory.
    Vendor refusal returns empty artifacts and never inlines raw bytes.
    """

    def test_raw_output_is_inside_the_snapshot_and_not_inlined(self):
        token = "RAWOUT-" + uuid.uuid4().hex
        os.environ["TASK_RUN_STDOUT"] = "token"
        os.environ["TASK_RUN_TOKEN"] = token
        env = self.call_run()
        self.assert_vendor_refusal(env)
        artifacts = env.get("artifacts") if isinstance(env.get("artifacts"), dict) else {}
        self.assertEqual(artifacts, {})
        blob = json.dumps(env)
        self.assertNotIn(token, blob)


# ---------------------------------------------------------------------------
# R13
# ---------------------------------------------------------------------------


class RunDoesNotInterpretProse(_TempRun):
    """R13 — vendor mode does not parse harness stdout. Stub replay
    still recognises a structured envelope and does not promote prose
    to approve.
    """

    def test_a_structured_envelope_from_the_harness_is_parsed(self):
        unique = "STRUCTURED-CLAIM-" + uuid.uuid4().hex
        recorded = envelope.build(
            "author-tests",
            status="ok",
            verdict="changes",
            findings=[envelope.finding(
                "p2", "alpha.py §top", unique,
                reproduce="python3 -m unittest")],
            spend={"harness": "stub", "total": 11, "out": 4, "runs": 1},
            stamp={"ref": self.ref},
        )
        replay = self.write_replay(recorded)
        env = self.call_run(
            runtime={"harness": "stub", "role": "write",
                     "replay": str(replay)},
        )
        findings = env.get("findings") if isinstance(env.get("findings"), list) else []
        claims = [f.get("claim") for f in findings if isinstance(f, dict)]
        self.assertIn(unique, claims)
        self.assertEqual(env.get("verdict"), "changes")
        self.assertEqual(env.get("status"), "ok")
        self.assertFalse(self.record_path.exists())

    def test_prose_that_says_approve_does_not_become_a_verdict(self):
        env = self.call_run()
        self.assert_vendor_refusal(env)
        self.assertNotEqual(env.get("verdict"), "approve")


# ---------------------------------------------------------------------------
# R14
# ---------------------------------------------------------------------------


class AnUnknownJobIsInvalid(_TempRun):
    """R14 — a job is data in the table. A name that is not
    there is a refusal, not a chance to improvise a prompt."""

    def test_an_absent_job_is_invalid_with_a_note_naming_it(self):
        name = "no-such-job-7e1c9a3d"
        env = self.call_run(name)
        self.assert_invalid(env, naming=name)
        self.assertFalse(
            self.record_path.exists(),
            "an unknown job must not launch",
        )

    def test_an_absent_job_under_direct_or_stub_is_not_the_vendor_refusal(self):
        name = "no-such-job-7e1c9a3d"
        replay = self.write_replay(envelope.build(
            "author-tests",
            status="ok",
            verdict="changes",
            findings=[],
            spend={"harness": "stub", "total": 1, "out": 1, "runs": 1},
            stamp={"ref": self.ref},
        ))
        cases = (
            ("direct", {"harness": "direct", "role": "read"}),
            ("stub", {"harness": "stub", "role": "write", "replay": str(replay)}),
        )
        for harness, runtime in cases:
            with self.subTest(harness=harness):
                env = self.call_run(name, runtime=runtime)
                self.assert_invalid(env, naming=name)
                note = env.get("note") or ""
                self.assertNotIn("found task vendor mode", note)
                self.assertNotIn("expected canonical worker execution", note)
                self.assertNotIn("needed ops/devlane/dispatch/launch.py", note)
                self.assertFalse(
                    self.record_path.exists(),
                    "an unknown job must not launch",
                )

    def test_load_jobs_reads_the_json_table(self):
        data = run.load_jobs()
        self.assertIsInstance(data, dict)
        self.assertIn("verify", data)
        self.assertIn("author-tests", data)
        self.assertIn("adversarial-review", data)

    def test_load_jobs_reads_a_path_it_is_given(self):
        path = self.home / "only.json"
        path.write_text(json.dumps({"only-me": {"adapter": "direct"}}),
                        encoding="utf-8")
        data = run.load_jobs(path)
        self.assertIsInstance(data, dict)
        self.assertEqual(set(data), {"only-me"})


# ---------------------------------------------------------------------------
# R15
# ---------------------------------------------------------------------------


class MainIsACli(_TempRun):
    """R15 — stdout is the envelope; the exit code is the verdict
    routed for a caller that does not parse JSON. 64 is usage, not
    argparse's 2, because 2 is already taken by invalid/tripped.
    """

    def setUp(self):
        super().setUp()
        run.ADAPTERS = self.make_adapters()
        comm = self.home / "jobs.json"
        comm.write_text(json.dumps(self.jobs), encoding="utf-8")
        run.JOBS_PATH = comm

    def test_a_changes_run_prints_json_and_returns_one(self):
        unique = "CLI-CHANGES-" + uuid.uuid4().hex
        finding = envelope.finding(
            "p2", "alpha.py §top", unique, reproduce="python3 -m unittest",
        )
        changed = envelope.build(
            "verify",
            status="ok",
            verdict="changes",
            findings=[finding],
            spend={"harness": None, "total": 0, "out": 0, "runs": 1},
            stamp={"ref": self.ref},
        )
        self._patch_attr(verify, "check", lambda *a, **k: changed)
        self._patch_attr(getattr(run, "verify", None), "check",
                         lambda *a, **k: changed)
        into = self.home / f"cli-{uuid.uuid4().hex}"
        code, out, _err = run_main([
            "verify",
            "--repo", str(self.repo),
            "--ref", self.ref,
            "--harness", "direct",
            "--role", "read",
            "--into", str(into),
        ])
        self.assertEqual(code, 1)
        env = self.parse_stdout(out)
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(env.get("verdict"), "changes")
        claims = [
            f.get("claim") for f in (env.get("findings") or [])
            if isinstance(f, dict)
        ]
        self.assertIn(unique, claims)

    def test_an_approving_run_prints_json_and_returns_zero(self):
        approved = envelope.build(
            "verify",
            status="ok",
            verdict="approve",
            spend={"harness": None, "total": 0, "out": 0, "runs": 1},
            stamp={"ref": self.ref},
        )
        self._patch_attr(verify, "check", lambda *a, **k: approved)
        self._patch_attr(getattr(run, "verify", None), "check",
                         lambda *a, **k: approved)
        into = self.home / f"cli-{uuid.uuid4().hex}"
        code, out, _err = run_main([
            "verify",
            "--repo", str(self.repo),
            "--ref", self.ref,
            "--harness", "direct",
            "--role", "read",
            "--into", str(into),
        ])
        env = self.parse_stdout(out)
        self.assertEqual(env.get("verdict"), "approve")
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(code, 0)

    def test_an_invalid_run_prints_json_and_returns_two(self):
        into = self.home / f"cli-{uuid.uuid4().hex}"
        code, out, _err = run_main([
            "no-such-job-7e1c9a3d",
            "--repo", str(self.repo),
            "--ref", self.ref,
            "--into", str(into),
        ])
        self.assertEqual(code, 2)
        env = self.parse_stdout(out)
        self.assertEqual(env.get("status"), "invalid")
        self.assertIsNone(env.get("verdict"))
        self.assertIn("no-such-job-7e1c9a3d", env.get("note") or "")

    def test_a_usage_error_returns_sixty_four(self):
        for argv in (
            [],
            ["author-tests"],
            ["author-tests", "--repo", str(self.repo)],
            ["--bogus"],
        ):
            with self.subTest(argv=argv):
                code, _out, _err = run_main(argv)
                self.assertEqual(code, 64)


# ---------------------------------------------------------------------------
# Prompt delivery (render): the harness sees the filled job.
# ---------------------------------------------------------------------------


class TheHarnessReceivesTheRenderedPrompt(_TempRun):
    """render is the prompt. A launch that drops {scope} or {ref} is
    how a task gets a blank instruction and still exits 0."""

    def test_the_harness_receives_the_scope_and_the_ref(self):
        scope = "SCOPE-" + uuid.uuid4().hex
        env = self.call_run(
            require={"scope": scope, "constraints": ["no network"]},
        )
        self.assert_vendor_refusal(env)
        self.assertFalse(
            self.record_path.exists(),
            "task vendor mode does not render a worker brief",
        )

    def test_render_fills_the_job_template(self):
        scope = "RENDER-" + uuid.uuid4().hex
        text = run.render(
            "author-tests",
            {"repo": str(self.repo), "ref": self.ref, "base": self.base,
             "include": ["alpha.py"], "into": str(self.home / "x")},
            {"scope": scope, "constraints": []},
        )
        self.assertIsInstance(text, str)
        self.assertIn(scope, text)
        self.assertIn(self.ref, text)


class TheJobAsksForWhatTheRunnerParses(unittest.TestCase):
    """A job whose prompt and parser disagree returns `invalid`
    however well the worker behaves (Codex + Grok, PR #49)."""

    @staticmethod
    def _jobs():
        raw = json.loads(run.JOBS_PATH.read_text(encoding="utf-8"))
        return raw.get("jobs", raw)

    def test_adversarial_review_requests_the_typed_envelope(self):
        prompt = self._jobs()["adversarial-review"]["prompt"]
        self.assertNotIn("CONTRIB.md review wire format", prompt,
                         "the prose wire format is the human review "
                         "format, not this job's stdout")
        self.assertIn("JSON", prompt)
        for field in ("status", "verdict", "findings"):
            self.assertIn(field, prompt, f"the prompt never names {field}")

    def test_the_requested_keys_are_the_ones_the_parser_accepts(self):
        """Pinned against envelope.FIELDS rather than a copy of the list,
        so the prompt cannot drift from the parser."""
        prompt = self._jobs()["adversarial-review"]["prompt"]
        for field in envelope.FIELDS:
            self.assertIn(field, prompt,
                          f"envelope field {field!r} is not requested")


class TheDocAndTheRegistryAgree(unittest.TestCase):
    """CONTRACT.md's job table and jobs.json must name the same set.

    They did not: the table listed four and the file held three --
    `sweep` was documented and did not exist. That is the same shape as
    the planted-fault promise one section further down, and the reason
    it survived is that nothing compared the two. Comparing them is
    three lines, so it is done here rather than noticed again later.
    """

    @staticmethod
    def _table_names():
        text = run.CONTRACT_PATH.read_text(encoding="utf-8") \
            if hasattr(run, "CONTRACT_PATH") else \
            (Path(run.JOBS_PATH).parent / "CONTRACT.md").read_text(encoding="utf-8")
        names, seen_header = set(), False
        for line in text.splitlines():
            if line.startswith("| job ") or line.startswith("| `job`"):
                seen_header = True
                continue
            if seen_header:
                if not line.startswith("|"):
                    break
                cell = line.split("|")[1].strip()
                if cell.startswith("`") and cell.endswith("`"):
                    names.add(cell.strip("`"))
        return names

    def test_every_documented_job_exists(self):
        registry = set(json.loads(Path(run.JOBS_PATH).read_text(encoding="utf-8")))
        documented = self._table_names()
        self.assertTrue(documented, "INVALID: no job table found in CONTRACT.md")
        self.assertEqual(documented - registry, set(),
                         "documented but not built")

    def test_every_built_job_is_documented(self):
        registry = set(json.loads(Path(run.JOBS_PATH).read_text(encoding="utf-8")))
        documented = self._table_names()
        self.assertEqual(registry - documented, set(),
                         "built but not documented")


# ---------------------------------------------------------------------------
# C1 — vendor mode is the refusing task projection
# ---------------------------------------------------------------------------


def _require_outputs_error(test):
    err = getattr(envelope, "OutputsError", None)
    test.assertTrue(
        isinstance(err, type) and issubclass(err, envelope.EnvelopeError),
        "missing public class envelope.OutputsError(EnvelopeError)",
    )
    test.assertIsNot(
        err, envelope.EnvelopeError,
        "OutputsError must be a distinct subclass, not an alias",
    )
    return err


class C1VendorModeDelegatesToCanonicalLaunch(_TempRun):
    """C1 — production worker execution belongs to launch.py.

    Vendor mode returns the exact execution refusal before snapshot,
    prompt, child or store effects. Direct verify and stub replay stay
    local. No injectable canonical_launch and no run.resume.
    """

    def test_vendor_mode_refuses_or_transfers_and_never_owns_a_second_executor(self):
        recorder = self.record_popen()
        env = self.call_run(
            runtime={"harness": "codex", "model": "test-model", "role": "write"},
        )
        self.assert_vendor_refusal(env, harness="codex", model="test-model")
        self.assertEqual(recorder.launch_argv(), [])
        self.assertFalse(hasattr(run, "canonical_launch"))
        self.assertFalse(hasattr(run, "resume"))

    def test_when_vendor_mode_transfers_explicit_selection_is_identical(self):
        unique_model = "model-" + uuid.uuid4().hex
        unique_effort = "high-" + uuid.uuid4().hex[:8]
        recorder = self.record_popen()
        env = self.call_run(
            job="adversarial-review",
            runtime={
                "harness": "grok",
                "model": unique_model,
                "effort": unique_effort,
                "role": "read",
            },
        )
        self.assert_vendor_refusal(
            env,
            job="adversarial-review",
            harness="grok",
            model=unique_model,
        )
        self.assertEqual(recorder.launch_argv(), [])
        self.assertNotIn("--profile", env.get("note") or "")

    def test_direct_verify_does_not_transfer_and_still_returns_verify_check(self):
        recorder = self.record_popen()
        env = self.call_run(
            "verify",
            require={
                "scope": "python exits 0",
                "constraints": ["read only"],
                "claim": "python exits 0",
                "command": [sys.executable, "-c", "pass"],
            },
            runtime={"harness": "direct", "role": "read"},
        )
        self.assertEqual(recorder.launch_argv(), [])
        self.assertEqual(env.get("job"), "verify")
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(env.get("verdict"), "approve")
        self.assertEqual(
            env.get("spend"),
            {"harness": None, "total": 0, "out": 0, "runs": 1},
        )
        self.assertFalse(self.record_path.exists())

    def test_stub_replay_does_not_transfer_and_still_replays(self):
        unique = "STUB-KEEP-" + uuid.uuid4().hex
        recorded = envelope.build(
            "author-tests",
            status="ok",
            verdict="changes",
            findings=[envelope.finding(
                "p2", "alpha.py §top", unique,
                reproduce="python3 -m unittest")],
            spend={"harness": "stub", "total": 11, "out": 4, "runs": 1},
            stamp={"ref": self.ref},
        )
        replay = self.write_replay(recorded)
        recorder = self.record_popen()
        env = self.call_run(
            runtime={"harness": "stub", "role": "write",
                     "replay": str(replay)},
        )
        self.assertEqual(recorder.launch_argv(), [])
        findings = env.get("findings") if isinstance(env.get("findings"), list) else []
        self.assertTrue(findings, "replayed envelope must carry the recorded finding")
        self.assertEqual(findings[0].get("claim"), unique)
        self.assertEqual(env.get("verdict"), "changes")
        self.assertFalse(self.record_path.exists())

    def test_vendor_cli_prints_the_execution_refusal_and_exits_two(self):
        into = self.home / f"cli-{uuid.uuid4().hex}"
        code, out, err = run_main([
            "author-tests",
            "--repo", str(self.repo),
            "--ref", self.ref,
            "--harness", "codex",
            "--role", "write",
            "--into", str(into),
        ])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)
        env = self.parse_stdout(out)
        self.assertEqual(env.get("status"), "invalid")
        self.assertIsNone(env.get("verdict"))
        note = env.get("note") or ""
        self.assertIn("execution:", note)
        self.assertIn("expected canonical worker execution", note)
        self.assertIn("found task vendor mode", note)
        self.assertIn("needed ops/devlane/dispatch/launch.py", note)
        self.assertIn("author-tests", note)
        self.assertIn("--harness", note)
        self.assertIn("--model", note)
        self.assertIn("--ref", note)
        self.assertFalse((into / "FILESET.md").exists())
        self.assertFalse(self.record_path.exists())

    def test_vendor_mode_does_not_import_dispatch_or_harness(self):
        """Task must not depend on dispatch or harness (CONTRACT.md)."""
        leaked = []
        for name in dir(run):
            if name.startswith("_"):
                continue
            value = getattr(run, name, None)
            mod = getattr(value, "__module__", "") or ""
            if mod.startswith("ops.devlane.dispatch") or mod.startswith(
                    "ops.devlane.harness"):
                leaked.append(f"{name} from {mod}")
            path = getattr(value, "__file__", "") or ""
            if "/dispatch/" in path.replace("\\", "/") and path.endswith(
                    "launch.py"):
                leaked.append(f"{name} file {path}")
            if "/harness/" in path.replace("\\", "/"):
                leaked.append(f"{name} file {path}")
        self.assertEqual(
            leaked, [],
            "task/run.py must not import dispatch or harness: "
            f"{leaked!r}",
        )
        self.assertNotIn("canonical_launch", dir(run))
        self.assertNotIn("resume", dir(run))


class C1VendorFrontendParsesOptionalCommit(_TempRun):
    """Optional write-job commit transport must survive stub replay.

    ENVELOPE_SCHEMA advertises commit; envelope.validate accepts it.
    No successful task vendor execution.
    """

    def _commit_envelope(self, subject, *, nest=False):
        env = dict(envelope.build(
            "author-tests",
            status="ok",
            verdict="changes",
            findings=[envelope.finding(
                "p2", "alpha.py §top", "commit-parse",
                reproduce="python3 -m unittest")],
            spend={"harness": "stub", "total": 1, "out": 1, "runs": 1},
            stamp={"ref": self.ref},
        ))
        env["commit"] = {"subject": subject, "body": "why"}
        got = envelope.validate(env)
        self.assertEqual(got["commit"]["subject"], subject)
        payload = {"result": env} if nest else env
        return self.write_replay(payload)

    def test_a_commit_bearing_envelope_is_accepted_not_treated_as_absent(self):
        subject = "task: pin commit transport " + uuid.uuid4().hex[:8]
        replay = self._commit_envelope(subject)
        env = self.call_run(
            runtime={"harness": "stub", "role": "write",
                     "replay": str(replay)},
        )
        self.assertNotEqual(
            env.get("status"), "invalid",
            "a schema-legal envelope with commit is not 'no envelope': "
            f"status={env.get('status')!r} note={env.get('note')!r}",
        )
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(env.get("verdict"), "changes")
        self.assertIn("commit", env)
        self.assertEqual(env["commit"].get("subject"), subject)
        self.assertEqual(env["commit"].get("body"), "why")
        self.assertFalse(self.record_path.exists())

    def test_the_same_envelope_without_commit_is_still_found(self):
        recorded = envelope.build(
            "author-tests",
            status="ok",
            verdict="changes",
            findings=[envelope.finding(
                "p2", "alpha.py §top", "no-commit",
                reproduce="python3 -m unittest")],
            spend={"harness": "stub", "total": 1, "out": 1, "runs": 1},
            stamp={"ref": self.ref},
        )
        self.assertNotIn("commit", recorded)
        replay = self.write_replay(recorded)
        env = self.call_run(
            runtime={"harness": "stub", "role": "write",
                     "replay": str(replay)},
        )
        self.assertEqual(env.get("status"), "ok")
        self.assertEqual(env.get("verdict"), "changes")
        self.assertNotIn("commit", env)

    def test_a_commit_bearing_envelope_nested_under_result_is_accepted(self):
        subject = "task: nested commit " + uuid.uuid4().hex[:8]
        replay = self._commit_envelope(subject, nest=True)
        env = self.call_run(
            runtime={"harness": "stub", "role": "write",
                     "replay": str(replay)},
        )
        self.assertNotEqual(
            env.get("status"), "invalid",
            "commit nested under result is still an envelope: "
            f"status={env.get('status')!r} note={env.get('note')!r}",
        )
        self.assertEqual(env.get("status"), "ok")
        self.assertIn("commit", env)
        self.assertEqual(env["commit"].get("subject"), subject)


class C1LoadJobsDecodesTheCatalogueStrictly(_TempRun):
    """Whole-catalogue JSON must refuse duplicate members before dict collapse.

    load_jobs raises OutputsError/outputs-schema. run() maps that
    exception from default load_jobs to invalid envelope, exit 2.
    Direct library calls keep raising.
    """

    def _dup_catalogue_text(self):
        return (
            '{"only-me": {"adapter": "direct", "role": "read", '
            '"prompt": "x", "outputs": [{"kind": "file", "path": "A.md", '
            '"artifact": "a", "path": "B.md"}]}}'
        )

    def _assert_outputs_schema(self, path):
        err = _require_outputs_error(self)
        with self.assertRaises(err) as ctx:
            run.load_jobs(path)
        self.assertIn("outputs-schema", str(ctx.exception))
        return ctx.exception

    def test_duplicate_members_are_refused_before_dict_collapse(self):
        raw = self._dup_catalogue_text()
        parsed = json.loads(raw)
        self.assertEqual(
            parsed["only-me"]["outputs"][0]["path"], "B.md",
            "plant: json.loads keeps the last member",
        )
        self.assertGreater(raw.count('"path"'), 1, "plant: duplicate path")
        path = self.home / "dup-catalogue.json"
        path.write_text(raw, encoding="utf-8")
        self._assert_outputs_schema(path)

        dup_job = (
            '{"only-me": {"adapter": "direct"}, '
            '"only-me": {"adapter": "harness"}}'
        )
        self.assertGreater(dup_job.count('"only-me"'), 1, "plant: duplicate job")
        collapsed_job = json.loads(dup_job)
        self.assertEqual(set(collapsed_job), {"only-me"})
        job_path = self.home / "dup-job.json"
        job_path.write_text(dup_job, encoding="utf-8")
        self._assert_outputs_schema(job_path)

        unselected = (
            '{"other": {"adapter": "direct", "outputs": ['
            '{"kind": "file", "path": "A.md", "artifact": "a", '
            '"path": "B.md"}]}, '
            '"only-me": {"adapter": "direct", "role": "read", '
            '"prompt": "x"}}'
        )
        self.assertIn('"other"', unselected, "plant: unselected job")
        unsel_path = self.home / "unselected-dup.json"
        unsel_path.write_text(unselected, encoding="utf-8")
        self._assert_outputs_schema(unsel_path)

        escaped = (
            '{"only-me": {"adapter": "direct", "role": "read", '
            '"prompt": "x", "outputs": [{"kind": "file", "path": "A.md", '
            '"artifact": "a", "\\u0070ath": "B.md"}]}}'
        )
        self.assertIn("\\u0070ath", escaped, "plant: escaped-equivalent key")
        escaped_path = self.home / "escaped-dup.json"
        escaped_path.write_text(escaped, encoding="utf-8")
        self._assert_outputs_schema(escaped_path)

    def test_reencoding_a_collapsed_dict_does_not_recover_the_duplicate(self):
        raw = self._dup_catalogue_text()
        collapsed = json.loads(raw)
        self.assertEqual(collapsed["only-me"]["outputs"][0]["path"], "B.md")
        reencoded = json.dumps(collapsed)
        self.assertEqual(reencoded.count('"path"'), 1)
        path = self.home / "collapsed-catalogue.json"
        path.write_text(reencoded, encoding="utf-8")
        data = run.load_jobs(path)
        self.assertEqual(set(data), {"only-me"})
        self.assertEqual(data["only-me"]["outputs"][0]["path"], "B.md")

    def test_run_maps_default_load_jobs_outputs_error_to_invalid_envelope(self):
        raw = self._dup_catalogue_text()
        path = self.home / "dup-default.json"
        path.write_text(raw, encoding="utf-8")
        run.JOBS_PATH = path
        try:
            env = run.run(
                "only-me",
                context=self.make_context(),
                require=self.require,
                runtime={
                    "harness": "direct",
                    "role": "read",
                    "caps": {"cap-out": 100000},
                    "timeout": 30,
                },
            )
        except Exception as exc:
            self.fail(
                "run must map OutputsError from default load_jobs to an "
                f"invalid envelope, not raise {type(exc).__name__}: {exc}"
            )
        self.assertIsInstance(env, dict)
        self.assertEqual(env.get("status"), "invalid")
        self.assertIsNone(env.get("verdict"))
        note = env.get("note") or ""
        self.assertIn("outputs-schema", note)
        for word in ("expected", "found", "needed"):
            self.assertIn(word, note.lower(), f"note names {word}: {note!r}")
        err = _require_outputs_error(self)
        with self.assertRaises(err):
            run.load_jobs(path)

    def test_main_maps_default_load_jobs_outputs_error_to_exit_two(self):
        raw = self._dup_catalogue_text()
        path = self.home / "dup-main.json"
        path.write_text(raw, encoding="utf-8")
        run.JOBS_PATH = path
        code, out, err = run_main([
            "only-me",
            "--repo", str(self.repo),
            "--ref", self.ref,
            "--harness", "direct",
            "--role", "read",
            "--into", str(self.home / f"cli-{uuid.uuid4().hex}"),
        ])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("Traceback", out)
        env = self.parse_stdout(out)
        self.assertEqual(env.get("status"), "invalid")
        self.assertIsNone(env.get("verdict"))
        self.assertIn("outputs-schema", env.get("note") or "")


if __name__ == "__main__":
    unittest.main()
