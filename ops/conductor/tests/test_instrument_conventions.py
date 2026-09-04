"""The conformance gate of instrument-conventions.md.

Every instrument that declares inheritance of the conventions document
is listed here with one hermetic refusal-provoking invocation, and the
refusal wire is asserted on all of them identically: exit 2, a single
non-empty stderr line, the class token, expected / found / needed in
order, and an empty stdout.

The registry is the document's list made executable — a new instrument
joins in the PR that lands it. skills.py and co_doc.py predate the
wire and join as they adopt it (the document says so).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
AGENT = "Conventions Referee <noreply@anthropic.com>"

# (tool file, argv, expected refusal class, needs identity)
REGISTRY = (
    ("decisions.py", ["add", "bad-id", "should this stand as recorded",
                      "--home", "x.md"], "id-shape", True),
    ("hand.py", ["declare", "some act", "a reason of at least four words",
                 "nonsense"], "class", True),
    ("watch.py", ["pr", "0"], "number", False),
    ("land.py", ["NOSUCH-RECORD"], "record", True),
    ("onboard.py", ["unexpected"], "arguments", False),
    ("ci.py", ["report"], "store", False),
    ("branches.py", ["census", "unexpected"], "arguments", False),
    ("findings.py", ["disposition", "NOSUCH#1", "fixed", "why"], "key", True),
)


class TheRefusalWireIsUniform(unittest.TestCase):
    def invoke(self, tool: str, argv: list[str], *, identity: bool):
        with tempfile.TemporaryDirectory(prefix="conventions-") as home:
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": home,
                "LC_ALL": "C",
                "LANG": "C",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if identity:
                env["WF_AGENT"] = AGENT
            return subprocess.run(
                [sys.executable, str(TOOLS / tool), *argv],
                cwd=home,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )

    def test_every_registered_instrument_exists(self):
        for tool, _argv, _cls, _ident in REGISTRY:
            with self.subTest(tool=tool):
                self.assertTrue(
                    (TOOLS / tool).is_file(),
                    f"registered instrument missing: {tool}",
                )

    def test_every_registered_instrument_speaks_the_wire(self):
        for tool, argv, cls, ident in REGISTRY:
            with self.subTest(tool=tool, refusal=cls):
                proc = self.invoke(tool, argv, identity=ident)
                err = proc.stderr or ""
                self.assertEqual(proc.returncode, 2, err or proc.stdout)
                lines = [ln for ln in err.splitlines() if ln.strip()]
                self.assertEqual(
                    len(lines), 1, f"refusal must be one line: {err!r}"
                )
                self.assertIn(cls, lines[0].lower())
                lower = lines[0].lower()
                for word in ("expected", "found", "needed"):
                    self.assertIn(word, lower, lines[0])
                self.assertLess(
                    lower.index("expected"), lower.index("found"), lines[0]
                )
                self.assertLess(
                    lower.index("found"), lower.index("needed"), lines[0]
                )
                self.assertEqual(
                    (proc.stdout or "").strip(), "",
                    "refusal text belongs on stderr, not stdout",
                )

    def test_identity_refusal_is_uniform_for_writing_instruments(self):
        for tool, argv, _cls, ident in REGISTRY:
            if not ident:
                continue
            with self.subTest(tool=tool):
                proc = self.invoke(tool, argv, identity=False)
                err = (proc.stderr or "").lower()
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn("identity", err)


if __name__ == "__main__":
    unittest.main()
