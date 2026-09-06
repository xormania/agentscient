"""C2 adoption: commit transport, catalogue decode, reservations, OutputsError.

Corrected from original Grok 4784cd45. Launch.main is the existing
canonical supervisor. No run.resume, run.canonical_launch, --profile
CLI oracle, adapter.reservations or policy bind_launch.

  A1  optional commit survives envelope.validate and launch acceptance
  A2  whole-catalogue JSON refuses duplicate members before dict collapse
  A3  complete reservations reach outputs_from_job, render/append, and
      launch admission before any grant or child
  A4  outputs-handle is an OutputsError, same family as schema and path
  F*  canonical trip, refusal, resume and result through launch.main
  P   named profile agreement, conflict, default and absence
"""

from __future__ import annotations

import contextlib
import importlib.util
import inspect
import io
import json
import os
import stat
import sys
import unittest
import uuid

import launch_support as ls

TASK = ls.APP.parent / "task"
if str(TASK) not in sys.path:
    sys.path.insert(0, str(TASK))

_spec = importlib.util.spec_from_file_location(
    "adopt_envelope", TASK / "envelope.py",
)
envelope = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(envelope)

NATIVE = {
    "plan": [{"kind": "file", "path": "PLAN.md", "artifact": "plan"}],
    "check-tests": [
        {"kind": "file", "path": "SKEPTIC.md", "artifact": "skeptic"},
        {"kind": "scratch", "path": "tmp"},
    ],
}
OUT_ROOT = "/jobs/example/out"
STAMP = {
    "ref": "f0b8bb3",
    "started": "2026-08-22T12:00:00Z",
    "ended": "2026-08-22T12:04:00Z",
}
DUP_OUTPUTS = (
    '[{"kind":"file","path":"A.md","artifact":"a","path":"B.md"}]'
)
COLLIDING = {
    "kind": "file",
    "path": "adapter-state.json",
    "artifact": "state",
}


def require_outputs_error(test):
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


def call_reserved(test, fn, *args, reserved):
    name = getattr(fn, "__name__", "callable")
    try:
        return fn(*args, reserved=reserved)
    except TypeError as exc:
        msg = str(exc)
        if "unexpected keyword" in msg or "positional" in msg:
            test.fail(f"{name} does not accept reserved=; {msg}")
        raise


def require_callable(test, name):
    fn = getattr(envelope, name, None)
    test.assertTrue(callable(fn), f"missing public seam envelope.{name}")
    return fn


PROFILE_DEV = "dev"
PROFILE_PROD = "prod"

POLICY_PROFILES = {
    "dev": {
        "write_roots": ["ops/"],
        "forbidden_dependency_roots": ["src/"],
        "authority_maintenance": False,
        "allow_declared_outputs": True,
    },
    "prod": {
        "write_roots": ["src/"],
        "forbidden_dependency_roots": ["ops/"],
        "authority_maintenance": False,
        "allow_declared_outputs": True,
    },
}


def policy_document(*, default_profile=None):
    doc = {
        "schema": "agentscient.lane-policy/v1",
        "standing": "proposal",
        "shared_read_roots": ["AGENTS.md"],
        "protected_authority_paths": ["ops/bin/dispatch.sh"],
        "profiles": dict(POLICY_PROFILES),
    }
    if default_profile is not None:
        doc["default_profile"] = default_profile
    return doc


def worker_selection(*, harness="grok", model=ls.REQUESTED_MODEL, effort=None,
                     role="worker", job_role="read", profile=None):
    return {
        "harness": harness,
        "model": model,
        "effort": effort,
        "role": role,
        "job_role": job_role,
        "profile": profile,
    }


def launch_declarations(*, selection=None, outputs=None, reservations=None):
    return {
        "selection": selection if selection is not None else worker_selection(),
        "requested_scope": {"repository": [], "outputs": []},
        "job_grants": {"repository": [], "outputs": []},
        "role_grants": {"repository": [], "outputs": []},
        "adapter_grants": {"repository": [], "outputs": []},
        "outputs": list(outputs or []),
        "reservations": list(reservations or []),
        "sources": [],
    }


def trusted_context(*, profile=None, policy=None, extra=None):
    ctx = {
        "profile": profile,
        "policy": policy if policy is not None else policy_document(),
    }
    if extra:
        ctx.update(extra)
    return ctx


_MISSING = object()


def run_trusted(test, argv, *, trusted_context=_MISSING, declarations=_MISSING):
    """Invoke launch.main with unit1a in-process trusted transport.

    trusted_context is the contract-named seam. declarations is an
    explicitly provisional keyword for complete LaunchDeclarations. The
    contract still names only launch.main(argv=None) -> int and transport
    as direct in-process arguments or an inherited read-only descriptor.
    This test-chosen name awaits the contract owner's narrow declaration
    and is not a second production API.

    TypeError on unexpected keywords is an assertion failure so a missing
    keyword cannot hide as a collection or TypeError red.
    """
    launch = test.load_launch()
    kwargs = {}
    if trusted_context is not _MISSING:
        kwargs["trusted_context"] = trusted_context
    if declarations is not _MISSING:
        kwargs["declarations"] = declarations
    if not kwargs:
        return test.run_main(argv)
    params = inspect.signature(launch.main).parameters
    accepts_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )
    for key in kwargs:
        if key not in params and not accepts_kwargs:
            test.fail(
                f"launch.main does not accept {key}= in-process argument "
                "named by unit1a trusted transport"
            )
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    try:
        os.chdir(test.repo)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = launch.main(list(argv), **kwargs)
            except TypeError as exc:
                msg = str(exc)
                if "unexpected keyword" in msg or "positional" in msg:
                    test.fail(
                        "launch.main does not accept trusted_context=/"
                        f"declarations=; {msg}"
                    )
                raise
            except SystemExit as exc:
                code = int(exc.code) if exc.code is not None else 0
    finally:
        os.chdir(old)
    if code is None:
        code = 0
    return int(code), out.getvalue(), err.getvalue()


def argv_has_profile_flag(argv):
    return any(str(part) == "--profile" or str(part).startswith("--profile=")
               for part in argv)


@contextlib.contextmanager
def scoped_environ(key, value):
    """Set one environment name for a block and restore the prior mapping."""
    missing = key not in os.environ
    old = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if missing:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


def sandbox_token(argv):
    items = [str(part) for part in argv]
    if "--sandbox" in items:
        idx = items.index("--sandbox")
        if idx + 1 < len(items):
            return items[idx + 1]
    if "--always-approve" in items:
        return "always-approve"
    if "--permission-mode" in items:
        idx = items.index("--permission-mode")
        if idx + 1 < len(items):
            return items[idx + 1]
    return None


def record_created_after(test, before):
    created = [path for path in test.record_files() if path not in before]
    test.assertEqual(
        len(created), 1,
        f"expected one new record, found {created!r}",
    )
    return test.read_record(created[0])


def harness_name(rec):
    harness = rec.get("harness")
    if isinstance(harness, dict):
        return harness.get("name")
    return harness


def requested_model(rec):
    model = rec.get("model") if isinstance(rec.get("model"), dict) else {}
    return model.get("requested")


R8_CACHE_HEAVY_USAGE = [[
    {
        "inputTokens": 6999950,
        "outputTokens": 50,
        "totalTokens": 7000000,
        "cachedReadTokens": 6950000,
        "costUsdTicks": 1,
        "modelCalls": 1,
        "numTurns": 1,
    },
]]


def selection_from_record(rec):
    decls = rec.get("declarations") if isinstance(rec.get("declarations"), dict) else {}
    sel = decls.get("selection") if isinstance(decls.get("selection"), dict) else {}
    if not sel:
        binding = rec.get("binding") if isinstance(rec.get("binding"), dict) else {}
        sel = binding.get("selection") if isinstance(binding.get("selection"), dict) else {}
    if not sel:
        conduct = rec.get("conduct") if isinstance(rec.get("conduct"), dict) else {}
        decls = conduct.get("declarations") if isinstance(conduct.get("declarations"), dict) else {}
        sel = decls.get("selection") if isinstance(decls.get("selection"), dict) else {}
    return sel


# ---------------------------------------------------------------------------
# A1 — optional commit transport
# ---------------------------------------------------------------------------


class OptionalCommitSurvivesValidateAndLaunch(ls._TempLaunch):
    """A1 — commit is optional transport, not an unknown key."""

    def test_envelope_validate_accepts_a_commit_object(self):
        env = dict(envelope.build(
            "implement", status="ok", verdict="approve", stamp=STAMP,
        ))
        env["commit"] = {"subject": "dispatch: pin commit", "body": "why"}
        self.assertIn("commit", env)
        got = envelope.validate(env)
        self.assertEqual(got["commit"]["subject"], "dispatch: pin commit")
        self.assertEqual(got["commit"]["body"], "why")

    def test_envelope_validate_still_refuses_an_unknown_key(self):
        env = dict(envelope.build(
            "implement", status="ok", verdict="approve", stamp=STAMP,
        ))
        env["transcript"] = "the whole conversation"
        with self.assertRaises(envelope.EnvelopeError):
            envelope.validate(env)

    def test_launch_keeps_optional_commit_on_the_accepted_envelope(self):
        os.environ["TASK_LAUNCH_ENVELOPE_COMMIT"] = "1"
        os.environ["TASK_LAUNCH_NOTE"] = "adopt-commit"
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        env = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(env.get("note"), "adopt-commit")
        self.assertEqual(env.get("status"), "ok")
        self.assertIn("commit", env)
        self.assertEqual(env["commit"].get("subject"), "dispatch: pin U10")

    def test_a_counts_mismatch_is_invalid_even_when_schema_shaped(self):
        """Launch must consume envelope.validate, not schema-shape alone."""
        self._install_counts_mismatch_cli()
        code, out, err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        text = self.combined(out, err)
        self.assertNotEqual(
            code, ls.REFUSAL_EXIT,
            f"a completed child with a bad envelope is not a preflight "
            f"refusal: {text!r}",
        )
        rec = self.read_record()
        env = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(
            env.get("status"), "invalid",
            "schema-shaped counts that disagree with findings must not "
            f"be ok: envelope={env!r} cause="
            f"{(rec.get('result') or {}).get('cause')!r}",
        )
        self.assertIsNone(env.get("verdict"))

    def _install_counts_mismatch_cli(self):
        dest = self.bin / "grok"
        dest.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "env = {\n"
            '  "job": "plan", "status": "ok", "verdict": "changes",\n'
            '  "counts": {"p1": 0, "p2": 0, "p3": 0, "opinions": 0},\n'
            '  "findings": [{"severity": "p2", "where": "a.py",\n'
            '    "claim": "counts disagree", "reproduce": "true"}],\n'
            '  "artifacts": {}, "spend": {"harness": "grok",\n'
            '    "total": 0, "out": 0, "runs": 1},\n'
            '  "stamp": {"ref": "x", "started": None, "ended": None},\n'
            '  "note": "counts-mismatch",\n'
            "}\n"
            "sys.stdout.write(json.dumps(env) + '\\n')\n",
            encoding="utf-8",
        )
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# A2 — whole-catalogue duplicate members
# ---------------------------------------------------------------------------


class CatalogueDecodesDuplicatesBeforeDictCollapse(ls._TempLaunch):
    """A2 — json.loads collapse is not a decode."""

    def _plant_duplicate_catalogue(self):
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        jobs["plan"]["outputs"] = ["__DUP__"]
        dumped = json.dumps(jobs)
        self.assertIn('["__DUP__"]', dumped, "plant: placeholder")
        planted = dumped.replace('["__DUP__"]', DUP_OUTPUTS)
        self.assertIn('"path":"A.md"', planted, "plant: first path")
        self.assertIn('"path":"B.md"', planted, "plant: duplicate path")
        collapsed = json.loads(planted)
        self.assertEqual(
            collapsed["plan"]["outputs"][0]["path"], "B.md",
            "plant: json.loads keeps the last member",
        )
        reencoded = json.dumps(collapsed)
        self.assertEqual(
            reencoded.count('"path"'),
            planted.count('"path"') - 1,
            "plant: re-encoding cannot recover the duplicate",
        )
        self.jobs_file.write_text(planted, encoding="utf-8")
        return planted, collapsed

    def test_launch_refuses_duplicate_catalogue_members_before_a_child(self):
        self._plant_duplicate_catalogue()
        code, out, err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        self.assert_wire_refusal(
            code, out, err, ident="outputs-schema",
            phrases=["path", "duplicate"],
        )
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])
        self.assertEqual(self.record_files(), [])

    def test_reencoding_the_collapsed_catalogue_is_a_different_input(self):
        _planted, collapsed = self._plant_duplicate_catalogue()
        self.jobs_file.write_text(
            json.dumps(collapsed) + "\n", encoding="utf-8",
        )
        path = collapsed["plan"]["outputs"][0]["path"]
        self.assertEqual(path, "B.md")
        fn = require_callable(self, "validate_outputs")
        got = fn(collapsed["plan"]["outputs"])
        self.assertEqual(got[0]["path"], "B.md")


# ---------------------------------------------------------------------------
# A3 — complete reservations through every seam
# ---------------------------------------------------------------------------


class CompleteReservationsReachEverySeam(unittest.TestCase):
    """A3 — extra reserved leaves must not be dropped at any entry point."""

    def test_outputs_from_job_refuses_a_launch_supplied_reservation(self):
        fn = require_callable(self, "outputs_from_job")
        params = inspect.signature(fn).parameters
        self.assertIn("reserved", params)
        spec = {"role": "read", "outputs": [dict(COLLIDING)]}
        err = require_outputs_error(self)
        with self.assertRaises(err):
            call_reserved(self, fn, spec, reserved=("adapter-state.json",))

    def test_outputs_from_job_without_extra_reserved_admits_the_same_array(self):
        fn = require_callable(self, "outputs_from_job")
        spec = {"role": "read", "outputs": [dict(COLLIDING)]}
        self.assertEqual(spec["outputs"][0]["path"], "adapter-state.json")
        got = fn(spec)
        self.assertEqual(got[0]["path"], "adapter-state.json")

    def test_render_refuses_a_reserved_collision_before_emitting_a_grant(self):
        fn = require_callable(self, "render_declared_outputs")
        params = inspect.signature(fn).parameters
        self.assertIn("reserved", params)
        err = require_outputs_error(self)
        with self.assertRaises(err):
            text = call_reserved(
                self, fn, [dict(COLLIDING)], OUT_ROOT,
                reserved=("adapter-state.json",),
            )
            self.assertNotIn(
                "Required file", text or "",
                "a reserved collision must not render a grant line",
            )

    def test_append_refuses_a_reserved_collision_before_emitting_a_grant(self):
        fn = require_callable(self, "append_declared_outputs")
        params = inspect.signature(fn).parameters
        self.assertIn("reserved", params)
        err = require_outputs_error(self)
        prompt = "Review the tree."
        with self.assertRaises(err):
            text = call_reserved(
                self, fn, prompt, [dict(COLLIDING)], OUT_ROOT,
                reserved=("adapter-state.json",),
            )
            self.assertNotIn(
                "Required file", text or "",
                "a reserved collision must not be appended as a grant",
            )

    def test_native_check_tests_still_render_without_extra_reserved(self):
        fn = require_callable(self, "render_declared_outputs")
        text = fn(list(NATIVE["check-tests"]), OUT_ROOT)
        self.assertIn("Declared job outputs:", text)
        self.assertIn("SKEPTIC.md", text)
        self.assertIn("tmp", text)
        self.assertNotIn("None. No additional worker output write grant.", text)


class LaunchAdmissionCarriesCompleteReservations(ls._TempLaunch):
    """Launch supplies default transport reserved before minting state."""

    def _set_plan_outputs(self, rows):
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        jobs["plan"]["outputs"] = rows
        self.jobs_file.write_text(
            json.dumps(jobs, indent=2) + "\n", encoding="utf-8",
        )

    def test_a_file_named_last_message_json_is_refused_before_a_child(self):
        self._set_plan_outputs([
            {
                "kind": "file",
                "path": "last-message.json",
                "artifact": "message",
            },
        ])
        code, out, err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        self.assert_wire_refusal(
            code, out, err, ident="outputs-schema",
            phrases=["last-message.json"],
        )
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])
        self.assertEqual(self.record_files(), [])
        self.assertFalse(self.witness.is_file())

    def test_a_file_named_commit_msg_is_refused_before_a_child(self):
        self._set_plan_outputs([
            {"kind": "file", "path": "COMMIT_MSG", "artifact": "commit"},
        ])
        code, out, err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        self.assert_wire_refusal(
            code, out, err, ident="outputs-schema",
            phrases=["COMMIT_MSG"],
        )
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])
        self.assertEqual(self.record_files(), [])
        self.assertFalse(self.witness.is_file())

    def test_native_plan_declaration_is_rendered_into_the_brief(self):
        self._set_plan_outputs(list(NATIVE["plan"]))
        argv = self.argv_for(job="plan", harness="grok", stage="plan")
        decls_missing = launch_declarations(
            selection=worker_selection(job_role="read", profile=PROFILE_DEV),
            outputs=list(NATIVE["plan"]),
        )
        code, out, err = run_trusted(
            self, argv,
            trusted_context=trusted_context(profile=PROFILE_DEV),
            declarations=decls_missing,
        )
        self.assert_wire_refusal(
            code, out, err, ident="output-capability",
            phrases=["PLAN.md"],
        )
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])

        decls = launch_declarations(
            selection=worker_selection(job_role="read", profile=PROFILE_DEV),
            outputs=list(NATIVE["plan"]),
        )
        decls["adapter_grants"] = {"repository": [], "outputs": ["PLAN.md"]}
        decls["job_grants"] = {"repository": [], "outputs": ["PLAN.md"]}
        self._install_plan_writer()
        code, out, err = run_trusted(
            self, argv,
            trusted_context=trusted_context(profile=PROFILE_DEV),
            declarations=decls,
        )
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"admitted PLAN.md must launch: {text!r}")
        rec = self.read_record()
        env = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(env.get("artifacts", {}).get("plan"), "PLAN.md")
        plan_path = self.the_job_dir() / "out" / "PLAN.md"
        self.assertTrue(plan_path.is_file(), "fake worker must produce PLAN.md")
        self.assertTrue(self.start_witness.is_file())
        witness = self.read_witness()
        prompt = witness.get("prompt_text") or ""
        self.assertIn("Declared job outputs:", prompt)
        self.assertIn("PLAN.md", prompt)
        self.assertNotIn(
            "None. No additional worker output write grant.", prompt,
        )
        self.assertFalse(argv_has_profile_flag(argv))

    def _install_plan_writer(self):
        dest = self.bin / "grok"
        dest.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "start = Path(" + json.dumps(str(self.start_witness)) + ")\n"
            "start.parent.mkdir(parents=True, exist_ok=True)\n"
            "start.write_text(json.dumps({\"pid\": os.getpid(), "
            "\"argv\": sys.argv, \"cwd\": os.getcwd()}), encoding=\"utf-8\")\n"
            "job_parent = Path(os.getcwd()).parent\n"
            "out_dir = job_parent / \"out\"\n"
            "out_dir.mkdir(parents=True, exist_ok=True)\n"
            "(out_dir / \"PLAN.md\").write_text(\"# plan\\n\", encoding=\"utf-8\")\n"
            "env = {\n"
            "  \"job\": \"plan\", \"status\": \"ok\", \"verdict\": \"approve\",\n"
            "  \"counts\": {\"p1\": 0, \"p2\": 0, \"p3\": 0, \"opinions\": 0},\n"
            "  \"findings\": [], \"artifacts\": {\"plan\": \"PLAN.md\"},\n"
            "  \"spend\": {\"harness\": \"grok\", \"total\": 0, \"out\": 0, "
            "\"runs\": 1},\n"
            "  \"stamp\": {\"ref\": \"x\", \"started\": None, \"ended\": None},\n"
            "  \"note\": None,\n"
            "}\n"
            "sys.stdout.write(json.dumps(env) + \"\\n\")\n",
            encoding="utf-8",
        )
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)

    def test_omission_renders_the_none_grant_line(self):
        jobs = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        jobs["plan"].pop("outputs", None)
        self.jobs_file.write_text(
            json.dumps(jobs, indent=2) + "\n", encoding="utf-8",
        )
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="grok", stage="plan",
        )
        text = witness.get("prompt_text") or ""
        self.assertIn("Declared job outputs:", text)
        self.assertIn("None. No additional worker output write grant.", text)


# ---------------------------------------------------------------------------
# A4 — OutputsError family
# ---------------------------------------------------------------------------


class OutputsErrorIsTheC2RefusalFamily(unittest.TestCase):
    """A4 — schema, path and handle refusals are OutputsError."""

    def test_a_schema_refusal_is_an_outputs_error(self):
        err = require_outputs_error(self)
        fn = require_callable(self, "validate_outputs")
        with self.assertRaises(err) as ctx:
            fn(None)
        self.assertIn("outputs-schema", str(ctx.exception))
        self.assertIsInstance(ctx.exception, envelope.EnvelopeError)

    def test_a_path_refusal_is_an_outputs_error(self):
        err = require_outputs_error(self)
        fn = require_callable(self, "render_declared_outputs")
        self.assertTrue(
            isinstance(getattr(envelope, "HANDLE_MAX", None), int),
            "missing envelope.HANDLE_MAX",
        )
        root = "/" + ("a" * (envelope.HANDLE_MAX + 8))
        self.assertGreater(len(root + "/PLAN.md"), envelope.HANDLE_MAX)
        try:
            fn(list(NATIVE["plan"]), root)
        except err as exc:
            self.assertIn("outputs-path", str(exc))
            return
        except envelope.EnvelopeError as exc:
            self.fail(
                "outputs-path must be an OutputsError, not a bare "
                f"EnvelopeError: {type(exc).__name__}: {exc}"
            )
        self.fail("an unrepresentable bound path must refuse")

    def test_a_handle_mismatch_is_an_outputs_error(self):
        err = require_outputs_error(self)
        env = envelope.build(
            "check-tests",
            status="ok",
            verdict="approve",
            artifacts={"skeptic": "SKEPTIC.md"},
            stamp=STAMP,
        )
        self.assertEqual(env["artifacts"]["skeptic"], "SKEPTIC.md")
        try:
            envelope.validate(
                env,
                outputs=list(NATIVE["check-tests"]),
                out_root=OUT_ROOT,
            )
        except TypeError as exc:
            msg = str(exc)
            if "unexpected keyword" in msg or "positional" in msg:
                self.fail(
                    "envelope.validate does not accept outputs=/out_root=; "
                    f"{msg}"
                )
            raise
        except err as exc:
            self.assertIn("outputs-handle", str(exc))
            self.assertIsInstance(exc, envelope.EnvelopeError)
            return
        except envelope.EnvelopeError as exc:
            self.fail(
                "outputs-handle must be an OutputsError, not a bare "
                f"EnvelopeError: {type(exc).__name__}: {exc}"
            )
        self.fail("handle mismatch must refuse")

    def test_historical_validate_without_outputs_still_accepts_the_relative_handle(
            self):
        env = envelope.build(
            "plan",
            status="ok",
            verdict="approve",
            artifacts={"plan": "PLAN.md"},
            stamp=STAMP,
        )
        got = envelope.validate(env)
        self.assertEqual(got["artifacts"]["plan"], "PLAN.md")


def assert_profile_refusal(test, code, out, err):
    text = test.combined(out, err)
    test.assertEqual(
        code, 2,
        f"lane-profile pre-effect refuses with exit 2, got {code}: {text!r}",
    )
    test.assertEqual(
        (out or "").strip(), "",
        f"lane-profile refusal belongs on stderr: {out!r}",
    )
    lower = (err or "").lower()
    test.assertIn("lane-profile", lower, f"class token missing: {err!r}")
    for word in ("expected", "found", "needed"):
        test.assertIn(word, lower, f"lane-profile names {word}: {err!r}")
    test.assert_not_started()
    test.assertEqual(test.job_dirs(), [])
    test.assertEqual(test.record_files(), [])
    test.assertFalse(test.witness.is_file())


class WhenVendorModeTransfersExplicitSelectionIsIdentical(ls._TempLaunch):
    """Relocated C1: consuming frontends preserve all six TaskSelection members."""

    def test_when_vendor_mode_transfers_explicit_selection_is_identical(self):
        model = "model-" + uuid.uuid4().hex[:12]
        effort = "high"
        argv = self.argv_for(
            job="plan", harness="grok", model=model, stage="plan",
            extra=["--effort", effort],
        )
        self.assertFalse(argv_has_profile_flag(argv))
        sel = worker_selection(
            harness="grok", model=model, effort=effort,
            job_role="read", profile=PROFILE_DEV,
        )
        decls = launch_declarations(selection=sel)
        code, out, err = run_trusted(
            self, argv,
            trusted_context=trusted_context(profile=PROFILE_DEV),
            declarations=decls,
        )
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"agreed selection must launch: {text!r}")
        rec = self.read_record()
        got = selection_from_record(rec)
        self.assertEqual(got.get("harness"), "grok")
        self.assertEqual(got.get("model"), model)
        self.assertEqual(got.get("effort"), effort)
        self.assertEqual(got.get("role"), "worker")
        self.assertEqual(got.get("job_role"), "read")
        self.assertEqual(got.get("profile"), PROFILE_DEV)
        self.assertEqual(rec.get("job"), "plan")
        snap = rec.get("snapshot") if isinstance(rec.get("snapshot"), dict) else {}
        self.assertEqual(snap.get("ref") or rec.get("lineage", {}).get("base_sha"),
                         self.ref)
        lineage = rec.get("lineage") if isinstance(rec.get("lineage"), dict) else {}
        self.assertEqual(lineage.get("branch") or rec.get("unit"), "work")


class FrontendSupervisionIsLaunchs(ls._TempLaunch):
    """F1 — existing launch entrypoint with synthetic over-cap evidence."""

    def test_a_canonical_launch_trip_is_returned_unchanged(self):
        os.environ["TASK_LAUNCH_OVER_OUT"] = "1"
        os.environ["TASK_LAUNCH_SLEEP"] = "8"
        os.environ["TASK_LAUNCH_DONE"] = str(self.home / "completed.marker")
        self.force_id("20260906T120000Z-plan-grok-aaaaaa")
        code, _out, _err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        rec = self.read_record()
        env = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(env.get("status") or rec.get("result", {}).get("status"),
                         "tripped")
        self.assertNotEqual(env.get("verdict"), "approve")
        self.assertNotEqual(code, 0)
        self.assertFalse((self.home / "completed.marker").is_file())

    def test_vendor_mode_does_not_rewrite_a_launch_trip_to_ok(self):
        os.environ["TASK_LAUNCH_OVER_OUT"] = "1"
        _code, _out, _err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        rec = self.read_record()
        env = (rec.get("result") or {}).get("envelope") or {}
        status = env.get("status") or (rec.get("result") or {}).get("status")
        self.assertEqual(status, "tripped")
        self.assertNotEqual(env.get("status"), "ok")
        self.assertNotEqual(env.get("verdict"), "approve")


class FrontendRefusalsAreLaunchs(ls._TempLaunch):
    """F2 — real launch preflight; no fabricated envelope before effects."""

    def test_a_canonical_launch_refusal_is_invalid_with_the_refusal_text(self):
        argv = self.argv_for(
            job="plan", harness="grok", stage="plan", model=None,
        )
        code, out, err = self.dispatch(argv)
        self.combined(out, err)
        self.assert_wire_refusal(
            code, out, err, ident="model",
            phrases=["needed", "--model"],
        )
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])
        self.assertEqual(self.record_files(), [])
        self.assertNotIn('"status": "invalid"', out)
        self.assertNotIn('"job": "plan"', out)

    def test_a_faulty_synthetic_executor_does_not_launch_a_harness_cli(self):
        (self.bin / "grok").unlink()
        code, out, err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        self.assertNotEqual(code, 0)
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])
        text = self.combined(out, err)
        self.assertTrue(
            "grok" in text.lower() or "isolation" in text.lower()
            or "path" in text.lower() or "missing" in text.lower(),
            f"missing CLI must be named: {text!r}",
        )


class FrontendResumeDelegates(ls._TempLaunch):
    """F3 — launch.main(['resume', id]) keeps the same dispatch id."""

    def test_resume_is_a_public_seam_that_transfers_the_same_id(self):
        rec, first, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        job_id = rec.get("id")
        self.assertIsInstance(job_id, str)
        self.assertTrue(job_id, "fresh launch must mint an id")
        first_attempts = list(rec.get("attempts") or [])
        first_session = rec.get("session") if isinstance(rec.get("session"), dict) else {}
        first_cwd = os.path.realpath(first.get("cwd") or "")
        first_snap = os.path.realpath(self.snapshot_of(rec))
        self.assertEqual(first_cwd, first_snap)
        original_harness = harness_name(rec)
        original_model = requested_model(rec)
        original_lineage = rec.get("lineage") if isinstance(rec.get("lineage"), dict) else {}
        original_brief = rec.get("brief")
        original_job = rec.get("job")
        self.witness.unlink()
        code, out, err = self.run_main(["resume", job_id])
        text = self.combined(out, err)
        self.assertNotEqual(code, ls.REFUSAL_EXIT, f"resume refused: {text!r}")
        self.assertEqual(code, 0, f"canonical resume must succeed: {text!r}")
        resumed = self.read_record()
        self.assertEqual(resumed.get("id"), job_id)
        self.assertEqual(harness_name(resumed), original_harness)
        self.assertEqual(requested_model(resumed), original_model)
        self.assertEqual(resumed.get("job"), original_job)
        self.assertEqual(resumed.get("lineage"), original_lineage)
        self.assertEqual(resumed.get("brief"), original_brief)
        resumed_session = resumed.get("session") if isinstance(resumed.get("session"), dict) else {}
        self.assertEqual(resumed_session.get("id"), first_session.get("id"))
        second = self.read_witness()
        self.assertEqual(os.path.realpath(second.get("cwd") or ""), first_snap)
        self.assertGreater(
            len(resumed.get("attempts") or []),
            len(first_attempts),
            "resume appends an attempt",
        )

    def test_resume_does_not_invent_a_new_dispatch_id(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        job_id = rec.get("id")
        prior_brief = rec.get("brief")
        prior_lineage = rec.get("lineage")
        prior_job = rec.get("job")
        prior_harness = harness_name(rec)
        prior_model = requested_model(rec)
        prior_session = rec.get("session") if isinstance(rec.get("session"), dict) else {}
        prior_snapshot = rec.get("snapshot")
        prior_attempts = list(rec.get("attempts") or [])
        path = self.the_record_path()
        prior_bytes = path.read_bytes()
        bogus = "20260906T010101Z-plan-grok-nope00"
        self.assertNotEqual(bogus, job_id)
        code, _out, _err = self.run_main(["resume", bogus])
        after = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(after.get("id"), job_id)
        self.assertEqual(after.get("brief"), prior_brief)
        self.assertEqual(after.get("lineage"), prior_lineage)
        self.assertEqual(after.get("job"), prior_job)
        self.assertEqual(harness_name(after), prior_harness)
        self.assertEqual(requested_model(after), prior_model)
        self.assertEqual(after.get("snapshot"), prior_snapshot)
        after_session = after.get("session") if isinstance(after.get("session"), dict) else {}
        self.assertEqual(after_session.get("id"), prior_session.get("id"))
        self.assertEqual(after_session.get("stream"), prior_session.get("stream"))
        after_attempts = list(after.get("attempts") or [])
        self.assertEqual(after_attempts, prior_attempts)
        self.assertEqual(path.read_bytes(), prior_bytes)
        self.assertFalse(
            (path.parent / (bogus + ".json")).is_file(),
            "refusal must not mint a new dispatch id",
        )
        self.assertNotEqual(code, 0)


class FrontendResultsAreLaunchs(ls._TempLaunch):
    """F4 — decode canonical result fields by value, not object identity."""

    def test_the_frontend_returns_launchs_envelope_without_rebuilding_it(self):
        os.environ["TASK_LAUNCH_NOTE"] = "RESULT-" + uuid.uuid4().hex
        rec, _witness, _out, _err = self.launch_ok(
            job="plan", harness="grok", stage="plan",
        )
        env = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(env.get("note"), os.environ["TASK_LAUNCH_NOTE"])
        self.assertEqual(env.get("status"), "ok")
        if "commit" in env:
            self.assertIsInstance(env.get("commit"), dict)
        stamp = env.get("stamp") if isinstance(env.get("stamp"), dict) else {}
        self.assertTrue(stamp.get("ref"))
        spend = env.get("spend") if isinstance(env.get("spend"), dict) else {}
        self.assertEqual(spend.get("harness"), "grok")

    def test_requested_model_is_not_copied_onto_observed_spend(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        model = rec.get("model") if isinstance(rec.get("model"), dict) else {}
        self.assertEqual(model.get("requested"), ls.REQUESTED_MODEL)
        self.assertEqual(model.get("ran"), ls.RAN_MODEL)
        self.assertNotEqual(model.get("ran"), model.get("requested"))
        self.assertTrue(model.get("read_from"))
        spend = ((rec.get("result") or {}).get("envelope") or {}).get("spend") or {}
        self.assertEqual(spend.get("harness"), "grok")
        self.assertNotEqual(spend.get("harness"), ls.REQUESTED_MODEL)
        self.assertNotEqual(spend.get("harness"), ls.RAN_MODEL)


class ProfileSelection(ls._TempLaunch):
    """Named profile agreement, conflict, default and absence."""

    def _argv(self):
        argv = self.argv_for(job="plan", harness="grok", stage="plan")
        self.assertFalse(argv_has_profile_flag(argv))
        return argv

    def test_explicit_and_structured_profiles_agree(self):
        argv = self._argv()
        sel = worker_selection(profile=PROFILE_DEV, job_role="read")
        decls = launch_declarations(selection=sel)
        code, out, err = run_trusted(
            self, argv,
            trusted_context=trusted_context(
                profile=PROFILE_DEV,
                policy=policy_document(default_profile=PROFILE_PROD),
            ),
            declarations=decls,
        )
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"agreed profile must launch: {text!r}")
        rec = self.read_record()
        got = selection_from_record(rec)
        self.assertEqual(got.get("profile"), PROFILE_DEV)
        self.assertNotEqual(got.get("profile"), PROFILE_PROD)

        argv_explicit = self._argv()
        decls_null = launch_declarations(
            selection=worker_selection(profile=None, job_role="read"),
        )
        before_explicit = set(self.record_files())
        code, out, err = run_trusted(
            self, argv_explicit,
            trusted_context=trusted_context(
                profile=PROFILE_DEV,
                policy=policy_document(default_profile=PROFILE_PROD),
            ),
            declarations=decls_null,
        )
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"explicit profile alone must launch: {text!r}")
        rec = record_created_after(self, before_explicit)
        self.assertEqual(selection_from_record(rec).get("profile"), PROFILE_DEV)
        self.assertNotEqual(selection_from_record(rec).get("profile"), PROFILE_PROD)

        argv_struct = self._argv()
        decls_only = launch_declarations(
            selection=worker_selection(profile=PROFILE_DEV, job_role="read"),
        )
        before_struct = set(self.record_files())
        code, out, err = run_trusted(
            self, argv_struct,
            trusted_context=trusted_context(
                profile=None,
                policy=policy_document(default_profile=PROFILE_PROD),
            ),
            declarations=decls_only,
        )
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"structured profile alone must launch: {text!r}")
        rec = record_created_after(self, before_struct)
        self.assertEqual(selection_from_record(rec).get("profile"), PROFILE_DEV)
        self.assertNotEqual(selection_from_record(rec).get("profile"), PROFILE_PROD)

    def test_conflicting_profiles_refuse_before_effects(self):
        argv = self._argv()
        decls = launch_declarations(
            selection=worker_selection(profile=PROFILE_PROD, job_role="read"),
        )
        code, out, err = run_trusted(
            self, argv,
            trusted_context=trusted_context(
                profile=PROFILE_DEV,
                policy=policy_document(default_profile=PROFILE_PROD),
            ),
            declarations=decls,
        )
        assert_profile_refusal(self, code, out, err)

        for bad in ("", "not-a-profile", "{", 1):
            with self.subTest(supplied=bad):
                decls_bad = launch_declarations(
                    selection=worker_selection(profile=bad, job_role="read"),
                )
                code, out, err = run_trusted(
                    self, self._argv(),
                    trusted_context=trusted_context(
                        profile=None,
                        policy=policy_document(default_profile=PROFILE_DEV),
                    ),
                    declarations=decls_bad,
                )
                assert_profile_refusal(self, code, out, err)

    def test_absent_selections_use_only_configured_default(self):
        argv = self._argv()
        decls = launch_declarations(
            selection=worker_selection(profile=None, job_role="read"),
        )
        code, out, err = run_trusted(
            self, argv,
            trusted_context=trusted_context(
                profile=None,
                policy=policy_document(default_profile=PROFILE_PROD),
            ),
            declarations=decls,
        )
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"configured default must launch: {text!r}")
        rec = self.read_record()
        got = selection_from_record(rec)
        self.assertEqual(got.get("profile"), PROFILE_PROD)
        self.assertNotEqual(got.get("profile"), None)
        self.assertNotEqual(got.get("profile"), PROFILE_DEV)

    def test_absent_selections_without_default_refuse(self):
        argv = self._argv()
        decls = launch_declarations(
            selection=worker_selection(profile=None, job_role="read"),
        )
        with scoped_environ("WF_LANE", "dev"):
            code, out, err = run_trusted(
                self, argv,
                trusted_context=trusted_context(
                    profile=None,
                    policy=policy_document(),
                ),
                declarations=decls,
            )
        assert_profile_refusal(self, code, out, err)
        text = (err or "").lower()
        self.assertNotIn("inferred", text)


class RunBuildsTheSnapshotWithFileset(ls._TempLaunch):
    """R1 — launch whole-ref bytes versus dirty source."""

    def test_the_snapshot_is_a_fileset_snapshot_of_the_ref_not_the_worktree(self):
        self._write("alpha.py", "DIRTY VERSION\n")
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        snap = self.snapshot_of(rec)
        written = snap / "alpha.py"
        self.assertTrue(written.is_file())
        self.assertEqual(written.read_text(encoding="utf-8"), "alpha v3\n")
        self.assertNotEqual(written.read_text(encoding="utf-8"), "DIRTY VERSION\n")

    def test_the_source_repo_is_not_checked_out_or_mutated(self):
        self._write("alpha.py", "DIRTY VERSION\n")
        before = self.porcelain()
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.assertTrue(self.snapshot_of(rec).is_dir())
        self.assertEqual(self.porcelain(), before)


class StampRefComesFromTheManifest(ls._TempLaunch):
    """R2 — launch owns ref resolution and pre-effect bad-ref refusal."""

    def test_stamp_ref_is_the_sha_the_manifest_names(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        env = (rec.get("result") or {}).get("envelope") or {}
        stamp = env.get("stamp") if isinstance(env.get("stamp"), dict) else {}
        snap = rec.get("snapshot") if isinstance(rec.get("snapshot"), dict) else {}
        self.assertEqual(snap.get("ref") or stamp.get("ref"), self.ref)

    def test_an_unresolvable_ref_is_invalid_and_never_launches(self):
        missing = "no-such-ref-7e1c9a3d"
        code, out, err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan", ref=missing,
        ))
        self.assertNotEqual(code, 0)
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])
        text = self.combined(out, err)
        self.assertTrue(
            missing in text or "ref" in text.lower(),
            f"bad ref must be named: {text!r}",
        )


class RoleSelectsTheSandbox(ls._TempLaunch):
    """R3 — launch admitted isolation; sandbox labels never prove capability."""

    def test_a_write_role_receives_the_write_sandbox_not_the_read_value(self):
        rec, witness, *_ = self.launch_ok(
            job="implement", harness="codex", stage="code",
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        self.assertTrue(argv, "child argv must be recorded")
        self.assertEqual(sandbox_token(argv), "workspace-write")
        self.assertNotEqual(sandbox_token(argv), "read-only")
        self.assertNotIn("read-only", argv)
        self.assertEqual(rec["harness"]["sandbox"], "workspace-write")

    def test_a_read_role_receives_the_read_sandbox(self):
        rec, witness, *_ = self.launch_ok(
            job="plan", harness="codex", stage="plan",
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        self.assertTrue(argv, "child argv must be recorded")
        self.assertEqual(sandbox_token(argv), "read-only")
        self.assertNotEqual(sandbox_token(argv), "workspace-write")
        self.assertEqual(rec["harness"]["sandbox"], "read-only")

    def test_a_grok_write_role_is_auto_not_plan(self):
        _rec, witness, *_ = self.launch_ok(
            job="implement", harness="grok", stage="code",
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        blob = " ".join(argv)
        self.assertNotIn("--permission-mode plan", blob)

    def test_builtin_write_values_are_not_the_read_only_ones(self):
        rec, witness, *_ = self.launch_ok(
            job="implement", harness="codex", stage="code",
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        write = sandbox_token(argv)
        self.assertEqual(write, "workspace-write")
        self.assertNotEqual(write, "read-only")
        self.assertEqual(rec["harness"]["sandbox"], write)
        self.assertNotEqual(rec["harness"]["sandbox"], "read-only")


class AnUnknownHarnessIsInvalid(ls._TempLaunch):
    """R4 — launch unknown selection refuses without substitution."""

    def test_an_unknown_harness_is_invalid_with_a_note_naming_it(self):
        name = "not-a-real-harness-7e1c9a3d"
        code, out, err = self.dispatch([
            "plan", "--harness", name, "--model", ls.REQUESTED_MODEL,
            "--ref", self.ref, "--stage", "plan",
        ])
        text = self.combined(out, err)
        self.assertNotEqual(code, 0)
        self.assertIn(name, text)
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])


class AMissingCliIsInvalidNotAVerdict(ls._TempLaunch):
    """R5 — missing executable is named non-acceptance, not work findings."""

    def test_a_missing_cli_is_invalid_with_a_note_naming_the_gap(self):
        (self.bin / "grok").unlink()
        code, out, err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        text = self.combined(out, err)
        self.assertNotEqual(code, 0)
        self.assert_not_started()
        env = {}
        if self.record_files():
            env = (self.read_record().get("result") or {}).get("envelope") or {}
        self.assertNotEqual(env.get("verdict"), "changes")
        self.assertTrue(
            "grok" in text.lower() or "path" in text.lower()
            or "missing" in text.lower() or "not found" in text.lower(),
            f"missing CLI must be named: {text!r}",
        )

    def test_a_missing_cli_is_not_ok_changes_about_the_work(self):
        (self.bin / "grok").unlink()
        code, _out, _err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        self.assertNotEqual(code, 0)
        if self.record_files():
            env = (self.read_record().get("result") or {}).get("envelope") or {}
            self.assertNotEqual(env.get("verdict"), "changes")
            self.assertNotEqual(env.get("verdict"), "approve")


class TheBatteryIsArmedWithCapOut(ls._TempLaunch):
    """R8 — cache-heavy total under cap-out does not trip."""

    def test_a_cache_heavy_total_does_not_trip_when_output_is_under_cap_out(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        os.environ["TASK_LAUNCH_GROK_USAGE"] = json.dumps(R8_CACHE_HEAVY_USAGE)
        self.witness.unlink()
        code, out, err = self.run_main(
            ["resume", rec["id"], "--cap-out", "1000"],
        )
        text = self.combined(out, err)
        self.assertEqual(code, 0, f"cache-heavy under cap-out must not trip: {text!r}")
        after = self.read_record()
        self.assertEqual(after.get("status"), "closed")
        self.assertEqual((after.get("caps") or {}).get("cap-out"), 1000)
        env = (after.get("result") or {}).get("envelope") or {}
        self.assertNotEqual(env.get("status"), "tripped")
        spend = env.get("spend") if isinstance(env.get("spend"), dict) else {}
        self.assertEqual(spend.get("total"), 7000000)
        self.assertEqual(spend.get("out"), 50)


class ABatteryTripIsNotACompletedRun(ls._TempLaunch):
    """R9 — launch kills the over-budget group and retains partials."""

    def test_a_battery_trip_is_status_tripped_with_no_verdict_and_a_note(self):
        os.environ["TASK_LAUNCH_OVER_OUT"] = "1"
        done = self.home / "completed.marker"
        os.environ["TASK_LAUNCH_DONE"] = str(done)
        os.environ["TASK_LAUNCH_SLEEP"] = "8"
        _code, _out, _err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        rec = self.read_record()
        env = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(env.get("status") or rec.get("result", {}).get("status"),
                         "tripped")
        self.assertNotEqual(env.get("verdict"), "approve")
        self.assertFalse(done.is_file())


class StreamDiscoveryNamesTheSnapshot(ls._TempLaunch):
    """R10 — isolated store/session/cwd beats newer foreign evidence."""

    def test_the_stream_that_names_the_snapshot_is_chosen_over_a_newer_sibling(self):
        stores = ls.load_path(self, ls.STORES_PATH, "task_launch_stores")
        decoy_id = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        operator = self.home / ".grok"
        stores.build_grok_store(
            operator, "/decoy/cwd",
            base_timestamp=ls.STREAM_EPOCH + 50_000,
            session_id=decoy_id, model="decoy-grok-model",
            marker="DECOY-GROK",
            usage_runs=[[
                {
                    "inputTokens": 1,
                    "outputTokens": 1,
                    "totalTokens": 999,
                    "cachedReadTokens": 0,
                    "costUsdTicks": 1,
                    "modelCalls": 1,
                    "numTurns": 1,
                },
            ]],
        )
        decoys = list(operator.glob("sessions/*/*/summary.json"))
        self.assertGreaterEqual(len(decoys), 1, "plant: grok decoy stream")
        decoy_bytes = decoys[0].read_bytes()
        self.assertIn(b"decoy-grok-model", decoy_bytes)
        os.utime(decoys[0], (2_000_000_000, 2_000_000_000))
        rec, witness, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.assertEqual(rec["model"]["ran"], ls.RAN_MODEL)
        self.assertNotEqual(rec["model"]["ran"], "decoy-grok-model")
        stream = rec["session"]["stream"] or ""
        self.assertTrue(stream, "a stream path is recorded")
        isolated = witness["env"].get("GROK_HOME")
        self.assertTrue(isolated)
        self.assertIn(os.path.realpath(isolated), os.path.realpath(stream))
        self.assertNotIn(decoy_id, stream)
        spend = ((rec.get("result") or {}).get("envelope") or {}).get("spend") or {}
        self.assertNotEqual(spend.get("total"), 999)


class AbsentSpendIsNotZeroSpend(ls._TempLaunch):
    """R11 — missing evidence is not a measured zero."""

    def test_no_stream_is_unknown_spend_not_a_measured_zero(self):
        os.environ["TASK_LAUNCH_WRITE_STREAM"] = "0"
        os.environ["TASK_LAUNCH_IGNORE_SESSION"] = "1"
        _code, _out, _err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        if self.record_files():
            rec = self.read_record()
            env = (rec.get("result") or {}).get("envelope") or {}
            self.assertNotEqual(env.get("status"), "ok")


class RawOutputLivesInsideTheSnapshot(ls._TempLaunch):
    """R12 — launch raw.out is under the canonical job directory."""

    def test_raw_output_is_inside_the_snapshot_and_not_inlined(self):
        token = "RAWOUT-" + uuid.uuid4().hex
        os.environ["TASK_LAUNCH_TOKEN"] = token
        os.environ["TASK_LAUNCH_STDOUT"] = "token"
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        job_dir = self.the_job_dir()
        raw = job_dir / "raw.out"
        self.assertTrue(raw.is_file(), "raw.out lives under the job directory")
        self.assertNotIn(token, json.dumps(rec.get("result", {}).get("envelope") or {}))


class RunDoesNotInterpretProse(ls._TempLaunch):
    """R13 — launch extracts structured responses; prose stays invalid."""

    def test_a_structured_envelope_from_the_harness_is_parsed(self):
        note = "STRUCTURED-" + uuid.uuid4().hex
        os.environ["TASK_LAUNCH_NOTE"] = note
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        env = (rec.get("result") or {}).get("envelope") or {}
        self.assertEqual(env.get("note"), note)
        self.assertEqual(env.get("status"), "ok")

    def test_prose_that_says_approve_does_not_become_a_verdict(self):
        os.environ["TASK_LAUNCH_STDOUT"] = "prose"
        _code, _out, _err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        if self.record_files():
            env = (self.read_record().get("result") or {}).get("envelope") or {}
            self.assertNotEqual(env.get("verdict"), "approve")
            self.assertEqual(env.get("status"), "invalid")


class ATrippedRunLeavesNothingBehind(ls._TempLaunch):
    """Orphan termination belongs to the canonical supervisor."""

    def test_the_group_dies_even_when_the_parent_was_already_reaped(self):
        os.environ["TASK_LAUNCH_ORPHAN"] = "1"
        os.environ["TASK_LAUNCH_OVER_OUT"] = "1"
        os.environ["TASK_LAUNCH_SLEEP"] = "2"
        os.environ["TASK_LAUNCH_GRANDCHILD"] = str(self.grandchild)

        def _reap():
            if self.grandchild.is_file():
                gpid = self.grandchild.read_text(encoding="utf-8").strip()
                ls.kill_if_alive(gpid)

        self.addCleanup(_reap)
        _code, _out, _err = self.dispatch(self.argv_for(
            job="plan", harness="grok", stage="plan",
        ))
        self.assertTrue(
            self.grandchild.is_file(),
            "plant: grandchild pid file must exist",
        )
        pid = int(self.grandchild.read_text(encoding="utf-8").strip() or "0")
        self.assertTrue(pid, "plant: grandchild pid must be recorded")
        self.assertFalse(ls.pid_is_alive(pid), "orphan survived")

    def test_the_group_is_recorded_at_launch(self):
        _rec, witness, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.assertTrue(witness.get("pid"))


class TheConductorsDialReachesTheHarness(ls._TempLaunch):
    """Dial encoding is launch's fake argv witness, never run._adapter_argv."""

    def test_grok_receives_both_dials(self):
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="grok", stage="plan",
            extra=["--effort", "high"],
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        self.assertIn(ls.REQUESTED_MODEL, argv)
        self.assertIn("high", argv)

    def test_claude_receives_both_dials(self):
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="claude", stage="plan",
            extra=["--effort", "high"],
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        self.assertIn(ls.REQUESTED_MODEL, argv)

    def test_codex_receives_the_model_dial(self):
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="codex", stage="plan",
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        self.assertIn(ls.REQUESTED_MODEL, argv)

    def test_codex_receives_both_dials(self):
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="codex", stage="plan",
            extra=["--effort", "high"],
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        self.assertIn(ls.REQUESTED_MODEL, argv)
        blob = " ".join(argv)
        self.assertTrue("high" in blob or "effort" in blob.lower(), argv)

    def test_an_unset_dial_adds_nothing(self):
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="grok", stage="plan",
        )
        argv = [str(p) for p in (witness.get("argv") or [])]
        self.assertIn(ls.REQUESTED_MODEL, argv)
        self.assertNotIn("--reasoning-effort", argv)


class TheRealAdaptersBindToTheirEvidence(ls._TempLaunch):
    """Cwd/session attribution and explicit model delivery live on launch."""

    def test_grok_discovery_is_bound_to_the_snapshot(self):
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        session = rec.get("session") if isinstance(rec.get("session"), dict) else {}
        snap = rec.get("snapshot") if isinstance(rec.get("snapshot"), dict) else {}
        root = str(snap.get("root") or "")
        self.assertTrue(root)
        stream = str(session.get("stream") or session.get("path") or "")
        self.assertTrue(stream, "session stream must name this snapshot")
        leaf = root.rstrip("/").split("/")[-1]
        self.assertTrue(
            leaf in stream or root in stream,
            f"stream must name this snapshot, not a sibling: {stream!r}",
        )

    def test_every_live_adapter_can_carry_a_model(self):
        for harness in ("codex", "grok", "claude"):
            with self.subTest(harness=harness):
                rec, witness, *_ = self.launch_ok(
                    job="plan", harness=harness, stage="plan",
                )
                argv = [str(p) for p in (witness.get("argv") or [])]
                self.assertIn(ls.REQUESTED_MODEL, argv)
                model = rec.get("model") if isinstance(rec.get("model"), dict) else {}
                self.assertEqual(model.get("requested"), ls.REQUESTED_MODEL)


class TheHarnessReceivesTheRenderedPrompt(ls._TempLaunch):
    """Scope/ref delivery is launch's prompt witness."""

    def test_the_harness_receives_the_scope_and_the_ref(self):
        scope = "SCOPE-" + uuid.uuid4().hex
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="grok", stage="plan", scope=scope,
        )
        text = witness.get("prompt_text") or ""
        self.assertIn(scope, text)
        self.assertIn(self.ref, text)


if __name__ == "__main__":
    unittest.main()
