"""Audit-fix pins for check-tests handoff, written from the envelopes.

Security record 20260904T170030Z-review-codex-10274e and adversarial
record 20260904T170050Z-review-grok-41c1f5 judged the merged slices.
This file pins the ladder.py findings those envelopes named. The
write-path gap lives in ops/devlane/task/tests. The absence-only
envelope methods live in test_ladder_lever.py.

The subject is imported by path as a module, the way the auditor
reproducers invoked it. The tests do not read the tool's source.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
TOOL = TOOLS / "ladder.py"

CHANGES_ENV = {
    "verdict": "changes",
    "counts": {"p1": 1, "p2": 0, "p3": 0, "opinions": 0},
    "findings": [
        {
            "severity": "p1",
            "where": "x",
            "claim": "y",
            "reproduce": "true",
        }
    ],
}


def _load_ladder():
    """Import ops/conductor/tools/ladder.py under a stable module name."""
    tools = str(TOOLS)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    if "ladder" in sys.modules:
        return importlib.reload(sys.modules["ladder"])
    return importlib.import_module("ladder")


def _driver(ladder, *, worktree: Path, inputs_dir: Path):
    """Minimal Driver the ledger_result reproduce constructs."""
    d = object.__new__(ladder.Driver)
    d.worktree = worktree
    d.inputs_dir = inputs_dir
    d.findings = worktree / "findings.py"
    d.stage_by_name = {"check-tests": {}}
    d.commit = lambda *a, **k: None
    d.plan = None
    ladder.run = lambda *a, **k: NS(returncode=0, stdout="", stderr="")
    return d


def _pending(ladder, worktree: Path):
    return ladder.Pending(
        "check-tests", "id", worktree / "r", "m", "e", "b", 0.0,
    )


def _is_stop(exc: BaseException) -> bool:
    return type(exc).__name__ in {"Stopped", "Refused"}


class InputsDirDirectorySymlinkIsNotFollowed(unittest.TestCase):
    """Security P1 and adversarial P1: one declared-versus-practiced gap.

    Declared: the payload must be a regular file inside inputs_dir;
    host target unchanged; no follow; a pre-existing symlink is a
    planted fault, not a destination; the ladder writes under that
    inputs dir, not through a symlink to the host.

    Practiced: replace_text mkstemp(dir=path.parent) then os.replace
    follow a directory symlink at inputs_dir; mkdir(exist_ok=True)
    leaves it; inputs_for then treats the resolved host directory as
    ladder inputs, so tests-fix is given a path outside the worktree.
    """

    def test_payload_write_does_not_follow_inputs_dir_symlink(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")
        ladder = _load_ladder()
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        wt = root / "wt"
        wt.mkdir()
        host = root / "hostdir"
        host.mkdir()
        marker = "HOSTDIR_MARKER_aa32"
        (host / "marker.txt").write_text(marker, encoding="utf-8")
        self.assertEqual(
            (host / "marker.txt").read_text(encoding="utf-8"), marker,
        )
        inputs = wt / "inputs"
        inputs.symlink_to(host, target_is_directory=True)
        self.assertTrue(inputs.is_symlink(), inputs)
        self.assertTrue(inputs.is_dir(), inputs)
        self.assertEqual(inputs.resolve(), host.resolve())
        self.assertFalse(
            str(host.resolve()).startswith(str(wt.resolve()) + os.sep),
            host,
        )
        d = _driver(ladder, worktree=wt, inputs_dir=inputs)
        p = _pending(ladder, wt)
        try:
            d.ledger_result(p, dict(CHANGES_ENV))
        except Exception as exc:
            if not _is_stop(exc):
                raise
        escaped = host / "check-tests-findings.payload.json"
        published = host / "check-tests-findings.json"
        self.assertFalse(
            escaped.is_file(),
            "payload write followed the directory symlink onto the "
            f"host: {escaped} exists",
        )
        self.assertFalse(
            published.exists(),
            "published findings name landed on the host: "
            f"{published}",
        )
        self.assertEqual(
            (host / "marker.txt").read_text(encoding="utf-8"), marker,
        )
        d.row = (
            lambda name: d.stage_by_name["check-tests"]
            if name == "check-tests"
            else {}
        )
        out = d.inputs_for("tests-fix", {"check-tests": "rec"}, None)
        self.assertIsInstance(out, list, out)
        host_prefix = str(host.resolve()) + os.sep
        leaked = [
            str(Path(x).resolve())
            for x in out
            if str(Path(x).resolve()).startswith(host_prefix)
        ]
        self.assertEqual(
            leaked,
            [],
            "tests-fix received a path outside the worktree via the "
            f"inputs_dir directory symlink: {leaked!r} from {out!r}",
        )


class CheckTestsArtifactsStayEmpty(unittest.TestCase):
    """Security P2: check-tests has no file; artifacts must stay empty.

    Declared: check-tests deliverable is the JSON envelope on stdout,
    no file, and the prompt must leave artifacts empty.

    Practiced: validate_check_tests checks findings, counts, and
    verdict, and accepts a schema-valid envelope whose artifacts name
    /etc/passwd; inputs_for then appends the check-tests record to
    tests-fix. The no-file boundary must refuse that handle.
    """

    def test_passwd_artifact_handle_is_not_accepted(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")
        ladder = _load_ladder()
        p = ladder.Pending(
            "check-tests", "id", Path("r"), "m", "e", "base", 0.0,
        )
        env = {
            "job": "check-tests",
            "status": "ok",
            "verdict": "changes",
            "counts": {"p1": 0, "p2": 1, "p3": 0, "opinions": 0},
            "findings": [
                {
                    "severity": "p2",
                    "where": "x:1",
                    "claim": "Declared: d; Practiced: p",
                    "reproduce": "true",
                }
            ],
            "artifacts": {"report": "/etc/passwd"},
            "spend": {},
            "stamp": {"ref": "deadbeef"},
            "note": None,
        }
        self.assertEqual(env["artifacts"], {"report": "/etc/passwd"})
        try:
            ladder.Driver.validate_check_tests(p, env)
        except Exception as exc:
            self.assertTrue(
                _is_stop(exc),
                "passwd artifacts must stop on the wire, not "
                f"{type(exc).__name__}: {exc}",
            )
            return
        self.fail(
            "validate_check_tests accepted a check-tests envelope "
            "whose artifacts name /etc/passwd; the no-file boundary "
            "must refuse that handle before tests-fix is minted"
        )


class SecondFindingsPublishStopsOnTheWire(unittest.TestCase):
    """Adversarial P2: a second publish is findings-file, not a crash.

    Declared: if a stopped dispatch record is now closed with an
    accepted envelope, resume consumes and lands it without
    relaunching. Replacing a planted path with a regular file inside
    inputs, or stopping before the write, are both refusals of the
    bypass.

    Practiced: after a symlink-safe payload replace, the published
    name is created with symlink_to, which neither replaces a
    pre-existing path nor raises Stopped. A second ledger_result
    raises FileExistsError; main catches only Refused and Stopped, so
    the ladder crashes off the wire instead of
    stopped stage=check-tests reason=findings-file.
    """

    def test_second_ledger_result_stops_findings_file_not_file_exists(self):
        self.assertTrue(TOOL.is_file(), f"RED: tool is absent: {TOOL}")
        ladder = _load_ladder()
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        wt = Path(td.name) / "wt"
        wt.mkdir()
        inputs = wt / "inputs"
        inputs.mkdir()
        d = _driver(ladder, worktree=wt, inputs_dir=inputs)
        p = _pending(ladder, wt)
        env = dict(CHANGES_ENV)
        d.ledger_result(p, env)
        payload = inputs / "check-tests-findings.payload.json"
        self.assertTrue(
            payload.is_file(),
            "first ledger_result must write the payload so the second "
            f"publish is the finding, not an absent write: {payload}",
        )
        try:
            d.ledger_result(p, env)
        except FileExistsError:
            self.fail(
                "second ledger_result raised FileExistsError; main "
                "catches only Refused and Stopped, so the ladder "
                "crashes off the wire instead of stopped "
                "stage=check-tests reason=findings-file"
            )
        except Exception as exc:
            self.assertTrue(
                _is_stop(exc),
                "second publish must Stop reason=findings-file, not "
                f"{type(exc).__name__}: {exc}",
            )
            reason = getattr(exc, "reason", None) or str(exc)
            self.assertIn(
                "findings-file",
                str(reason),
                "second publish must name reason=findings-file: "
                f"{type(exc).__name__} {exc}",
            )
            return
        # Replacing the published name and continuing is a refusal of
        # the crash; the payload must still be a regular file inside
        # inputs.
        self.assertTrue(payload.is_file(), payload)
        self.assertFalse(payload.is_symlink(), payload)
        self.assertTrue(
            str(payload.resolve()).startswith(str(inputs.resolve()) + os.sep)
            or payload.resolve().parent == inputs.resolve(),
            payload,
        )


if __name__ == "__main__":
    unittest.main()
