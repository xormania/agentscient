"""Fail-open paths in doc_commands: a clean result it has not earned.

A checker that dies on junk gets disabled, so these cases must not
crash. They also must not report a successful scan of a document they
did not actually check.
"""

import errno
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "checks" / "doc_commands.py"
LIVE_GUIDE = Path(__file__).resolve().parents[3] / "guide" / "telemetry.md"
USAGE_LINE = 'python3 ops/devlane/telemetry/usage.py report --repo "$PWD"'


def run(root, extra=()):
    argv = [sys.executable, str(CHECK), "--root", str(root), *extra]
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


class DollarInAnArgumentIsNotATemplate(unittest.TestCase):
    """`$` in an argument does not make the command path uncheckable.

    `ops/guide/telemetry.md` names usage.py with `--repo "$PWD"`. With
    the script removed, the check still exits 0 because any `$` on the
    line skips it. A `$` in the *path* is a template; a `$` later on
    the line is not.
    """

    def test_a_dollar_in_an_argument_does_not_excuse_a_missing_command(self):
        live = LIVE_GUIDE.read_text(encoding="utf-8")
        self.assertIn(USAGE_LINE, live)
        with tempfile.TemporaryDirectory(prefix="doc-cmd-dollar-") as raw:
            root = Path(raw)
            dest = root / "ops" / "guide" / "telemetry.md"
            dest.parent.mkdir(parents=True)
            dest.write_text(live)
            planted = dest.read_text(encoding="utf-8")
            self.assertEqual(planted, live)
            self.assertIn(USAGE_LINE, planted)
            self.assertGreater(len(planted.encode()), 64)
            for sibling in ("breaker.py", "pulse.py", "worth.py"):
                path = root / "ops" / "devlane" / "telemetry" / sibling
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# placeholder so only usage.py is missing\n")
                self.assertTrue(path.is_file())
            missing = root / "ops" / "devlane" / "telemetry" / "usage.py"
            self.assertFalse(missing.exists())
            code, out = run(root)
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertIn("usage.py", out)
            self.assertNotIn("clean", out)

    def test_a_home_dollar_in_an_argument_does_not_excuse_a_missing_command(self):
        # The live line uses $PWD. A $PWD-only guard still reports
        # clean when the same missing command is written with $HOME.
        live = LIVE_GUIDE.read_text(encoding="utf-8")
        self.assertIn(USAGE_LINE, live)
        home_line = USAGE_LINE.replace("$PWD", "$HOME")
        self.assertNotEqual(home_line, USAGE_LINE)
        self.assertIn("$HOME", home_line)
        self.assertNotIn("$PWD", home_line)
        planted_text = live.replace(USAGE_LINE, home_line, 1)
        self.assertIn(home_line, planted_text)
        self.assertNotIn(USAGE_LINE, planted_text)
        with tempfile.TemporaryDirectory(prefix="doc-cmd-home-") as raw:
            root = Path(raw)
            dest = root / "ops" / "guide" / "telemetry.md"
            dest.parent.mkdir(parents=True)
            dest.write_text(planted_text)
            planted = dest.read_text(encoding="utf-8")
            self.assertEqual(planted, planted_text)
            self.assertIn(home_line, planted)
            self.assertNotIn(USAGE_LINE, planted)
            self.assertGreater(len(planted.encode()), 64)
            for sibling in ("breaker.py", "pulse.py", "worth.py"):
                path = root / "ops" / "devlane" / "telemetry" / sibling
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# placeholder so only usage.py is missing\n")
                self.assertTrue(path.is_file())
            missing = root / "ops" / "devlane" / "telemetry" / "usage.py"
            self.assertFalse(missing.exists())
            code, out = run(root)
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertIn("usage.py", out)
            self.assertNotIn("clean", out)


class UnreadableIsNotASuccessfulScan(unittest.TestCase):
    """OSError and UnicodeDecodeError must not become `[]` counted as
    scanned. Survive, but do not report clean."""

    def test_undecodable_utf8_is_not_reported_clean(self):
        payload = b"\xff\xfe```sh\n./x.sh\n```\n"
        with tempfile.TemporaryDirectory(prefix="doc-cmd-utf8-") as raw:
            root = Path(raw)
            (root / "ok.md").write_text("# prose only\n")
            bad = root / "bad.md"
            bad.write_bytes(payload)
            landed = bad.read_bytes()
            self.assertEqual(landed, payload)
            self.assertIn(b"```sh", landed)
            self.assertGreater(len(landed), 8)
            with self.assertRaises(UnicodeDecodeError):
                landed.decode("utf-8")
            code, out = run(root)
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertNotIn("clean", out)
            self.assertIn("bad.md", out)

    def test_a_file_that_cannot_be_read_is_not_reported_clean(self):
        with tempfile.TemporaryDirectory(prefix="doc-cmd-oserror-") as raw:
            root = Path(raw)
            (root / "ok.md").write_text("# prose only\n")
            missing = root / "gone.md"
            self.assertFalse(missing.exists())
            code, out = run(root, extra=(str(missing),))
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertNotIn("clean", out)
            self.assertIn("gone.md", out)

    def test_a_directory_named_like_markdown_is_not_reported_clean(self):
        with tempfile.TemporaryDirectory(prefix="doc-cmd-isdir-") as raw:
            root = Path(raw)
            junk = root / "junk.md"
            junk.mkdir()
            self.assertTrue(junk.is_dir())
            self.assertFalse(junk.is_file())
            code, out = run(root, extra=(str(junk),))
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertNotIn("clean", out)
            self.assertIn("junk.md", out)

    @unittest.skipIf(os.geteuid() == 0, "root can read chmod 000 files")
    def test_an_unreadable_existing_file_is_not_reported_clean(self):
        payload = "# prose only\n```sh\n./x.sh\n```\n"
        with tempfile.TemporaryDirectory(prefix="doc-cmd-chmod-") as raw:
            root = Path(raw)
            (root / "ok.md").write_text("# prose only\n")
            bad = root / "secret.md"
            bad.write_text(payload)
            self.assertEqual(bad.read_text(encoding="utf-8"), payload)
            self.assertGreater(len(bad.read_bytes()), 8)
            os.chmod(bad, 0)
            try:
                self.assertTrue(bad.is_file())
                self.assertFalse(os.access(bad, os.R_OK))
                with self.assertRaises(PermissionError):
                    bad.read_text(encoding="utf-8")
                code, out = run(root)
                self.assertNotEqual(code, 0, out)
                self.assertNotIn("Traceback", out)
                self.assertNotIn("clean", out)
                self.assertIn("secret.md", out)
            finally:
                os.chmod(bad, 0o644)

    def test_a_symlink_loop_is_not_a_traceback_or_clean(self):
        # Explicit-path resolve() is doc_commands.py:100 in main(),
        # not the document-read site at :75. A loop must not crash
        # and must not be reported as a successful scan.
        with tempfile.TemporaryDirectory(prefix="doc-cmd-eloop-") as raw:
            base = Path(raw)
            root = base / "scan"
            root.mkdir()
            (root / "ok.md").write_text("# prose only\n")
            loop = base / "loop.md"
            loop.symlink_to(loop.name)
            self.assertTrue(loop.is_symlink())
            self.assertEqual(os.readlink(loop), "loop.md")
            with self.assertRaises(OSError) as caught:
                os.stat(loop)
            self.assertEqual(caught.exception.errno, errno.ELOOP)
            code, out = run(root, extra=(str(loop),))
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
            self.assertNotIn("clean", out)
            self.assertIn("loop.md", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
