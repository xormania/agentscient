"""Corpus for doc_commands: every case runs twice, clean and planted.

Case 1 is the real failure. `ops/docs/cue-aar-equality.md` at 642911f
told a reader to run `./lessons.sh`, no such file existed anywhere in
the repository, and everything reported success: the doc rendered, the
docs-index suite passed 46 tests, the ghost-link check passed because
it only reads markdown links to `.md` files, and CI was green. Two
human-shaped reviewers caught it by reading the prose. Nothing
mechanical looked.

Case 2 is the bug found while building this. A regex pairing ``` to the
next ``` can begin at a CLOSING fence and capture prose as if it were
shell, which made the first scanner return zero hits on the document
that contained the fault. A checker that only ran the clean case would
have shipped catching nothing.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "checks" / "doc_commands.py"


def run(root):
    p = subprocess.run([sys.executable, str(CHECK), "--root", str(root)],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


class TheRealFailure(unittest.TestCase):
    """A fence that names a script the repository does not contain."""

    FENCE = (
        "# doc\n\n"
        "Output of `lessons.sh`, `cue v0.17.1`:\n\n"
        "```sh\n"
        "cue version                     # v0.17.1 when this was measured\n"
        "./lessons.sh\n"
        "```\n"
    )

    def test_clean_when_the_script_is_there(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text(self.FENCE)
            (root / "docs" / "lessons.sh").write_text("#!/bin/sh\n")
            code, out = run(root)
            self.assertEqual(code, 0, out)

    def test_named_when_the_script_is_absent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text(self.FENCE)
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("lessons.sh", out)
            self.assertIn("a.md", out)


class TheFenceBugFoundWhileBuildingThis(unittest.TestCase):
    """A closing fence must never be read as an opening one.

    Two cue fences around prose that mentions a missing script: a regex
    pairing ``` to the next ``` reads the gap between them as shell and
    the real sh fence as prose, and reports clean.
    """

    DOC = (
        "```cue\n#A: {}\n```\n\n"
        "Prose between fences that says ./ghost.sh in passing.\n\n"
        "```cue\n#B: {}\n```\n\n"
        "```sh\n./ghost.sh\n```\n"
    )

    def test_prose_between_two_fences_is_not_shell(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text(
                "```cue\n#A: {}\n```\n\nProse ./not-a-command.sh here.\n\n"
                "```cue\n#B: {}\n```\n")
            code, out = run(root)
            self.assertEqual(code, 0, out)
            self.assertNotIn("not-a-command.sh", out)

    def test_the_real_sh_fence_after_two_cue_fences_is_still_read(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text(self.DOC)
            code, out = run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("ghost.sh", out)


class PrecisionAgainstOrdinaryDocuments(unittest.TestCase):
    """Shapes that occur in this repository's real documents and must
    never fire. Measured: 33 candidate command paths across the tracked
    markdown, of which the only unresolvable ones were relative to a
    directory the scanner was not resolving against."""

    def test_a_path_relative_to_the_documents_own_directory_resolves(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "notes").mkdir()
            (root / "notes" / "extract").mkdir()
            (root / "notes" / "extract" / "schema.py").write_text("")
            (root / "notes" / "n.md").write_text(
                "```sh\npython3 extract/schema.py\n```\n")
            code, out = run(root)
            self.assertEqual(code, 0, out)

    def test_a_variable_is_not_a_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text(
                "```sh\npython3 \"$REPO/ops/devlane/x.py\" --flag\n```\n")
            code, out = run(root)
            self.assertEqual(code, 0, out)

    def test_a_path_that_is_an_argument_is_not_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text(
                "```sh\ngit add ops/devlane/gone.py\n```\n")
            code, out = run(root)
            self.assertEqual(code, 0, out)

    def test_an_unlabelled_fence_is_not_assumed_to_be_shell(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text("```\n./whatever.sh\n```\n")
            code, out = run(root)
            self.assertEqual(code, 0, out)


class ItNeverBlocks(unittest.TestCase):
    def test_a_directory_with_no_markdown_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = run(Path(d))
            self.assertEqual(code, 0, out)

    def test_undecodable_bytes_do_not_crash_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_bytes(b"\xff\xfe```sh\n./x.sh\n```\n")
            code, out = run(root)
            self.assertIn(code, (0, 1), out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
