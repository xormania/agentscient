"""check-envelope verb and registry row, items 3 and 7.

Written from contract items 2, 3 and 7 of
`.dev/ladder-inputs/scope-item31-20260911.md`. The tool is the subject
and is not read here.

Item 7: every new refusal is one stderr line, exit 2, stdout empty,
with one hermetic invocation in the registry. Item 3: a malformed
field is class envelope naming the field. The verb reads a dispatch
record or a bare envelope from a path or stdin.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_instrument_conventions import (  # noqa: E402
    REGISTRY_DIR,
    read_registry,
)
from test_ladder_lever import (  # noqa: E402
    RUN_CAP,
    WELL_FORMED_SKEPTIC_FINDING,
    _LadderFixture,
)

PROSE_CLAIM = "Contract item 9 requires a fresh check"
ZERO_COUNTS = {"p1": 0, "p2": 0, "p3": 0, "opinions": 0}


def _envelope(**overrides) -> dict:
    env = {
        "job": "check-tests",
        "status": "ok",
        "verdict": "approve",
        "counts": dict(ZERO_COUNTS),
        "findings": [],
        "artifacts": {},
        "spend": {"harness": "codex", "total": 0, "out": 0, "runs": 0},
        "stamp": {"ref": "planted", "started": None, "ended": None},
        "note": None,
    }
    env.update(overrides)
    return env


def _record(envelope: dict) -> dict:
    return {
        "id": "20260911T000000Z-check-tests-codex-aa0132",
        "job": "check-tests",
        "status": "closed",
        "result": {"envelope": envelope},
    }


class CheckEnvelopeVerb(_LadderFixture):
    """Item 7 — the verb speaks the envelope refusal on the wire."""

    def run_verb(self, argv: list[str], *, stdin: str = ""):
        return subprocess.run(
            [sys.executable, str(self.staged), *argv],
            cwd=str(self.invoke_cwd),
            env=self.env(),
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def assert_envelope_wire(self, proc, *, field: str | None = None) -> str:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err or proc.stdout)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        line = lines[0]
        head = line.split(":", 1)[0].strip().lower().replace("_", "-")
        self.assertEqual(head, "envelope", line)
        self.assertEqual(
            (proc.stdout or "").strip(),
            "",
            "refusal text belongs on stderr, not stdout",
        )
        lower = line.lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, line)
        self.assertLess(lower.index("expected"), lower.index("found"), line)
        self.assertLess(lower.index("found"), lower.index("needed"), line)
        if field is not None:
            self.assertIn(field, line, line)
        return line

    def test_empty_stdin_refuses_envelope(self):
        proc = self.run_verb(["check-envelope", "-"], stdin="")
        line = self.assert_envelope_wire(proc)
        self.assertIn("empty stdin", line.lower())

    def test_a_valid_record_on_stdin_is_silent_exit_0(self):
        payload = json.dumps(_record(_envelope()))
        proc = self.run_verb(["check-envelope", "-"], stdin=payload)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertEqual((proc.stdout or "").strip(), "")
        self.assertEqual((proc.stderr or "").strip(), "")

    def test_a_prose_claim_on_stdin_names_findings_1_claim(self):
        findings = [
            dict(WELL_FORMED_SKEPTIC_FINDING),
            {
                "severity": "p2",
                "where": "ops/conductor/tests/test_beta.py:1",
                "claim": PROSE_CLAIM,
                "reproduce": (
                    "python3 -m unittest discover -s ops/conductor/tests "
                    "-p test_beta.py"
                ),
            },
        ]
        env = _envelope(
            verdict="changes",
            findings=findings,
            counts={"p1": 0, "p2": 2, "p3": 0, "opinions": 0},
        )
        self.assertEqual(env["findings"][1]["claim"], PROSE_CLAIM)
        proc = self.run_verb(
            ["check-envelope", "-"], stdin=json.dumps(_record(env)),
        )
        line = self.assert_envelope_wire(proc, field="findings[1].claim")
        self.assertIn(PROSE_CLAIM, line)

    def test_a_path_argument_names_findings_1_claim_the_same(self):
        findings = [
            dict(WELL_FORMED_SKEPTIC_FINDING),
            {
                "severity": "p2",
                "where": "ops/conductor/tests/test_beta.py:1",
                "claim": PROSE_CLAIM,
                "reproduce": (
                    "python3 -m unittest discover -s ops/conductor/tests "
                    "-p test_beta.py"
                ),
            },
        ]
        env = _envelope(
            verdict="changes",
            findings=findings,
            counts={"p1": 0, "p2": 2, "p3": 0, "opinions": 0},
        )
        path = self.root / "prose-claim-record.json"
        path.write_text(json.dumps(_record(env), indent=2) + "\n", encoding="utf-8")
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8"))["result"]["envelope"]
            ["findings"][1]["claim"],
            PROSE_CLAIM,
        )
        proc = self.run_verb(["check-envelope", str(path)])
        self.assert_envelope_wire(proc, field="findings[1].claim")

    def test_a_valid_path_argument_is_silent_exit_0(self):
        path = self.root / "valid-record.json"
        path.write_text(
            json.dumps(_record(_envelope()), indent=2) + "\n", encoding="utf-8",
        )
        proc = self.run_verb(["check-envelope", str(path)])
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertEqual((proc.stdout or "").strip(), "")
        self.assertEqual((proc.stderr or "").strip(), "")


class CheckEnvelopeRegistry(unittest.TestCase):
    """Item 7 — the hermetic registry row is check-envelope - class envelope."""

    def test_the_registry_carries_the_check_envelope_row(self):
        rows, failures = read_registry(REGISTRY_DIR)
        self.assertEqual(failures, [], failures)
        pins = [
            (row.argv, row.refusal, row.identity)
            for row in rows
            if row.tool == "ladder.py"
        ]
        self.assertIn(
            (("check-envelope", "-"), "envelope", False),
            pins,
            pins,
        )
        mutant = [(("run",), "arguments", False)]
        self.assertNotIn(
            (("check-envelope", "-"), "envelope", False),
            mutant,
        )


if __name__ == "__main__":
    unittest.main()
