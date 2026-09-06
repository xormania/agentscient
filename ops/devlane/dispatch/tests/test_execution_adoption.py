"""C2 adoption: commit transport, catalogue decode, reservations, OutputsError.

Written from task/dispatch CONTRACT.md C2, the adoption ruling, and
Claude review dispositions on commit parse, reserved passthrough,
whole-catalogue duplicate members, and handle-class OutputsError.
Implementation was not read. jobs.json is not edited. No policy or
adapter interface is invented: tests use envelope.validate,
validate_outputs, outputs_from_job, render/append, and launch.main
with synthetic jobs and fake CLIs.

  A1  optional commit survives envelope.validate and launch acceptance
  A2  whole-catalogue JSON refuses duplicate members before dict collapse
  A3  complete reservations reach outputs_from_job, render/append, and
      launch admission before any grant or child
  A4  outputs-handle is an OutputsError, same family as schema and path
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import stat
import sys
import unittest

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
            phrases=["path", "B.md"],
        )
        self.assert_not_started()

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

    def test_native_plan_declaration_is_rendered_into_the_brief(self):
        self._set_plan_outputs(list(NATIVE["plan"]))
        _rec, witness, *_ = self.launch_ok(
            job="plan", harness="grok", stage="plan",
        )
        text = witness.get("prompt_text") or ""
        self.assertIn("Declared job outputs:", text)
        out_root = str((self.the_job_dir() / "out").resolve())
        self.assertIn(out_root, text)
        self.assertIn("PLAN.md", text)
        self.assertIn("artifacts", text)
        self.assertNotIn(
            "None. No additional worker output write grant.", text,
        )
        self.assertTrue(
            self.start_witness.is_file(),
            "a non-colliding declaration must still launch the child",
        )

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


if __name__ == "__main__":
    unittest.main()
