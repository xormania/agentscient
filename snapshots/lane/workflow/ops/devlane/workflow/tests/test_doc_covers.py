"""Argv-level pins for the doc-covers header contract.

A helper that returns errors on a string does not prove main() reached
it — the first scanner returned zero hits on the document that
contained the fault. Each case plants a repository, runs the checker
as a subprocess, and asserts the exit code and the printed line.

CONTRACT: three classes of bad input, all exit 1; the printed line is
what tells them apart, and the summary never says clean if any of
them fired.
"""

from __future__ import annotations

import errno
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

CHECK = support.WF_DIR / "checks" / "doc_covers.py"


def doc(covers=None, *, name="x", description="y", close=True, body="body\n"):
    """A shelf document. ``covers`` is the YAML block including the key."""
    lines = ["---"]
    if name is not None:
        lines.append(f"name: {name}")
    if description is not None:
        lines.append(f"description: {description}")
    if covers is not None:
        lines.extend(covers.rstrip("\n").split("\n"))
    if close:
        lines.append("---")
    return "\n".join(lines) + "\n" + body


class CheckerCase(unittest.TestCase):
    def sandbox(self, *, shelf=True):
        raw = tempfile.mkdtemp(prefix="doc-covers-")
        self.addCleanup(shutil.rmtree, raw, ignore_errors=True)
        root = Path(raw)
        if shelf:
            (root / "ops" / "docs").mkdir(parents=True)
        return root

    def shelf(self, root):
        return root / "ops" / "docs"

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, text)
        self.assertGreater(len(landed), 0)
        return path

    def write_bytes(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        landed = path.read_bytes()
        self.assertEqual(landed, payload)
        self.assertGreater(len(landed), 0)
        return path

    def run_check(self, root, *paths, extra=()):
        argv = [
            sys.executable, str(CHECK), "--root", str(root),
            *[str(p) for p in paths],
            *extra,
        ]
        proc = subprocess.run(
            argv, capture_output=True, text=True, check=False)
        return proc.returncode, proc.stdout + proc.stderr

    def top_level_md(self, root):
        return sorted(p.name for p in self.shelf(root).glob("*.md"))


class DocsWithoutCoversAreClean(CheckerCase):
    """Nothing to judge: docs present, no covers: keys → clean, counted."""

    def test_docs_with_no_covers_keys_are_clean_and_counted(self):
        root = self.sandbox()
        self.write(self.shelf(root) / "a.md", doc())
        self.write(self.shelf(root) / "b.md", doc())
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)
        self.assertRegex(out, r"2 doc\(s\), 0 covers: path\(s\)")

    def test_a_repo_relative_covers_path_that_exists_is_clean(self):
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        self.write(
            self.shelf(root) / "note.md",
            doc("covers:\n  - README.md"),
        )
        self.assertTrue((root / "README.md").is_file())
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)
        self.assertRegex(out, r"1 doc\(s\), 1 covers: path\(s\)")

    def test_a_flow_list_covers_value_that_exists_is_clean(self):
        # Live form: `ops/docs/telemetry.md` declares
        # `covers: [ops/devlane/telemetry/]`.
        root = self.sandbox()
        target = root / "ops" / "devlane" / "telemetry"
        target.mkdir(parents=True)
        text = doc("covers: [ops/devlane/telemetry/]")
        self.assertIn("covers: [ops/devlane/telemetry/]", text)
        self.assertNotIn("covers:\n  -", text)
        self.write(self.shelf(root) / "note.md", text)
        self.assertTrue(target.is_dir())
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)
        self.assertNotIn("INVALID —", out)

    def test_an_empty_flow_list_is_clean(self):
        # Near-miss of the quoted empty item: covers: [] is a list with
        # no items, not an empty item. The CONTRACT names the item.
        root = self.sandbox()
        text = doc("covers: []")
        self.assertIn("covers: []", text)
        self.assertNotIn('""', text)
        self.assertNotIn("''", text)
        self.write(self.shelf(root) / "note.md", text)
        landed = (self.shelf(root) / "note.md").read_text()
        self.assertIn("covers: []", landed)
        self.assertNotIn('""', landed)
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)
        self.assertNotIn("empty list item", out)
        self.assertNotIn("INVALID —", out)
        self.assertRegex(out, r"1 doc\(s\), 0 covers: path\(s\)")


class ResolvesToNothing(CheckerCase):
    """Repo-relative, does not exist: a finding, not INVALID."""

    def test_a_missing_repo_relative_path_is_a_finding(self):
        root = self.sandbox()
        raw = "no/such/path.py"
        self.write(
            self.shelf(root) / "note.md",
            doc(f"covers:\n  - {raw}"),
        )
        self.assertFalse((root / raw).exists())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn(f"note.md: covers: {raw} does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)


class ResolvesSomewhereItShouldNot(CheckerCase):
    """Absolute is lexical; any .. is lexical; resolved-outside is a finding."""

    def test_an_absolute_path_outside_is_refused_lexically(self):
        # secret.py exists, so a stat would not say "does not exist".
        # The refusal must happen before any filesystem call.
        root = self.sandbox()
        outside = Path(tempfile.mkdtemp(prefix="doc-covers-secret-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        secret = outside / "secret.py"
        self.write(secret, "secret\n")
        raw = str(secret)
        self.assertTrue(Path(raw).is_absolute())
        self.assertTrue(Path(raw).is_file())
        self.write(
            self.shelf(root) / "note.md",
            doc(f"covers:\n  - {raw}"),
        )
        self.assertIn(raw, (self.shelf(root) / "note.md").read_text())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn(raw, out)
        self.assertIn(
            "is absolute; covers: names repo-relative paths", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_an_absolute_path_inside_is_refused_lexically(self):
        root = self.sandbox()
        inside = root / "README.md"
        self.write(inside, "ok\n")
        raw = str(inside.resolve())
        self.assertTrue(Path(raw).is_absolute())
        self.assertTrue(inside.is_file())
        self.assertTrue(inside.resolve().is_relative_to(root.resolve()))
        self.write(
            self.shelf(root) / "note.md",
            doc(f"covers:\n  - {raw}"),
        )
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn(raw, out)
        self.assertIn(
            "is absolute; covers: names repo-relative paths", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_an_absolute_path_whose_stat_raises_is_still_refused_lexically(self):
        # A plant whose stat raises (absolute ELOOP) catches every
        # non-swallowing stat-first mutant without instrumentation.
        root = self.sandbox()
        outside = Path(tempfile.mkdtemp(prefix="doc-covers-absloop-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        loop = outside / "loop"
        loop.symlink_to("loop")
        raw = str(loop)
        self.assertTrue(Path(raw).is_absolute())
        self.assertTrue(loop.is_symlink())
        with self.assertRaises(OSError) as caught:
            Path(raw).stat()
        self.assertEqual(caught.exception.errno, errno.ELOOP)
        self.write(
            self.shelf(root) / "note.md",
            doc(f"covers:\n  - {raw}"),
        )
        self.assertIn(raw, (self.shelf(root) / "note.md").read_text())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn(raw, out)
        self.assertIn(
            "is absolute; covers: names repo-relative paths", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("clean", out)

    @unittest.skipIf(os.geteuid() == 0, "root can stat through chmod 000")
    def test_an_absolute_path_behind_an_unreadable_parent_is_still_refused_lexically(self):
        # chmod-000 parent: the other stat-raising plant in the class.
        root = self.sandbox()
        outside = Path(tempfile.mkdtemp(prefix="doc-covers-hidden-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        parent = outside / "hidden"
        parent.mkdir()
        secret = parent / "secret.py"
        self.write(secret, "secret\n")
        raw = str(secret)
        self.assertTrue(Path(raw).is_absolute())
        os.chmod(parent, 0)
        self.addCleanup(os.chmod, parent, 0o755)
        try:
            Path(raw).stat()
        except OSError:
            pass
        else:
            self.skipTest("stat on chmod-000 parent did not raise")
        self.write(
            self.shelf(root) / "note.md",
            doc(f"covers:\n  - {raw}"),
        )
        self.assertIn(raw, (self.shelf(root) / "note.md").read_text())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn(raw, out)
        self.assertIn(
            "is absolute; covers: names repo-relative paths", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("clean", out)

    def test_a_dotdot_segment_is_refused_even_when_it_lands_inside(self):
        root = self.sandbox()
        self.write(self.shelf(root) / "README.md", "# index\n")
        raw = "ops/docs/../docs/README.md"
        resolved = (root / raw).resolve()
        self.assertTrue(resolved.is_file())
        self.assertTrue(resolved.is_relative_to(root.resolve()))
        self.write(
            self.shelf(root) / "note.md",
            doc(f"covers:\n  - {raw}"),
        )
        self.assertIn(raw, (self.shelf(root) / "note.md").read_text())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn(f"note.md: covers: {raw}", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("resolves outside the repository", out)
        self.assertNotIn("clean", out)

    def test_a_symlink_whose_target_is_outside_is_a_finding(self):
        root = self.sandbox()
        outside = Path(tempfile.mkdtemp(prefix="doc-covers-out-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        secret = outside / "secret.py"
        self.write(secret, "secret\n")
        leak = root / "leak"
        leak.symlink_to(secret)
        self.assertTrue(leak.is_symlink())
        self.assertTrue(leak.exists())
        self.assertFalse(
            leak.resolve().is_relative_to(root.resolve()))
        self.write(
            self.shelf(root) / "note.md",
            doc("covers:\n  - leak"),
        )
        self.assertIn("leak", (self.shelf(root) / "note.md").read_text())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("leak", out)
        self.assertIn("resolves outside the repository", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_symlinked_root_does_not_flag_inside_paths(self):
        # Both sides resolved: a /tmp that is itself a symlink (macOS)
        # must not flag every inside path as outside.
        base = Path(tempfile.mkdtemp(prefix="doc-covers-macos-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        real = base / "real"
        link = base / "link"
        real.mkdir()
        (real / "ops" / "docs").mkdir(parents=True)
        self.write(real / "README.md", "ok\n")
        self.write(
            real / "ops" / "docs" / "note.md",
            doc("covers:\n  - README.md"),
        )
        link.symlink_to(real)
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), real.resolve())
        code, out = self.run_check(link)
        self.assertEqual(code, 0, out)
        self.assertNotIn("resolves outside the repository", out)
        self.assertNotIn("does not exist", out)


class CannotBeResolved(CheckerCase):
    """INVALID: names the subject, distinct line, never clean, exit 1."""

    def test_a_covers_path_that_loops_is_invalid(self):
        root = self.sandbox()
        loop = root / "loop"
        loop.symlink_to("loop")
        self.assertTrue(loop.is_symlink())
        self.assertEqual(os.readlink(loop), "loop")
        with self.assertRaises(OSError) as caught:
            os.stat(loop)
        self.assertEqual(caught.exception.errno, errno.ELOOP)
        self.write(
            self.shelf(root) / "note.md",
            doc("covers:\n  - loop"),
        )
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("INVALID —", out)
        self.assertIn("note.md", out)
        self.assertIn("loop", out)
        self.assertNotIn("clean", out)

    def test_an_undecodable_doc_is_invalid(self):
        root = self.sandbox()
        self.write(self.shelf(root) / "ok.md", doc())
        payload = b"\xff\xfe---\nname: x\ndescription: y\n---\n"
        bad = self.write_bytes(self.shelf(root) / "bad.md", payload)
        with self.assertRaises(UnicodeDecodeError):
            bad.read_bytes().decode("utf-8")
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("INVALID —", out)
        self.assertIn("bad.md", out)
        self.assertNotIn("clean", out)

    @unittest.skipIf(os.geteuid() == 0, "root can read chmod 000 files")
    def test_an_unreadable_doc_is_invalid(self):
        root = self.sandbox()
        self.write(self.shelf(root) / "ok.md", doc())
        secret = self.write(self.shelf(root) / "secret.md", doc())
        os.chmod(secret, 0)
        try:
            self.assertTrue(secret.is_file())
            self.assertFalse(os.access(secret, os.R_OK))
            with self.assertRaises(PermissionError):
                secret.read_text(encoding="utf-8")
            code, out = self.run_check(root)
            self.assertEqual(code, 1, out)
            self.assertIn("INVALID —", out)
            self.assertIn("secret.md", out)
            self.assertNotIn("clean", out)
        finally:
            os.chmod(secret, 0o644)

    def test_a_root_that_is_not_a_directory_is_invalid(self):
        root = self.sandbox()
        target = self.write(root / "not-a-dir", "x\n")
        self.assertTrue(target.is_file())
        self.assertFalse(target.is_dir())
        code, out = self.run_check(target)
        self.assertEqual(code, 1, out)
        self.assertNotIn(code, (2, 3, 64, 70))
        self.assertIn("INVALID —", out)
        self.assertIn(str(target), out)
        self.assertNotIn("clean", out)

    def test_a_missing_shelf_is_invalid(self):
        root = self.sandbox(shelf=False)
        shelf = root / "ops" / "docs"
        self.assertFalse(shelf.exists())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("INVALID —", out)
        self.assertIn("ops/docs", out)
        self.assertNotIn("clean", out)

    def test_a_root_that_cannot_be_resolved_is_invalid(self):
        base = Path(tempfile.mkdtemp(prefix="doc-covers-rootloop-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        loop = base / "loop"
        loop.symlink_to("loop")
        self.assertTrue(loop.is_symlink())
        self.assertEqual(os.readlink(loop), "loop")
        with self.assertRaises(OSError) as caught:
            os.stat(loop)
        self.assertEqual(caught.exception.errno, errno.ELOOP)
        code, out = self.run_check(loop)
        self.assertEqual(code, 1, out)
        self.assertNotIn(code, (2, 3, 64, 70))
        self.assertIn("INVALID —", out)
        self.assertIn(str(loop), out)
        self.assertNotIn("clean", out)


class MalformedDeclaration(CheckerCase):
    """A finding, not silence. Scalar, mapping, and empty item are the fail-opens."""

    def test_a_scalar_covers_value_is_a_finding_even_when_the_path_exists(self):
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        self.assertTrue((root / "README.md").is_file())
        self.write(
            self.shelf(root) / "note.md",
            doc("covers: README.md"),
        )
        landed = (self.shelf(root) / "note.md").read_text()
        self.assertIn("covers: README.md", landed)
        self.assertNotIn("covers:\n  -", landed)
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("note.md", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_block_mapping_covers_value_is_a_finding(self):
        # covers: with an empty inline value, then an indented non-item
        # (`  path: README.md`) is a mapping — a value that is not a list.
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        self.assertTrue((root / "README.md").is_file())
        text = doc("covers:\n  path: README.md")
        self.assertRegex(text, r"(?m)^covers:$")
        self.assertRegex(text, r"(?m)^  path: README.md$")
        self.assertNotRegex(text, r"(?m)^covers:\n  -")
        self.assertNotRegex(text, r"(?m)^path: README.md$")
        self.write(self.shelf(root) / "note.md", text)
        landed = (self.shelf(root) / "note.md").read_text()
        self.assertRegex(landed, r"(?m)^covers:\n  path: README.md$")
        self.assertNotRegex(landed, r"(?m)^path: README.md$")
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("note.md", out)
        self.assertIn("path: README.md is not a list item", out)
        self.assertIn("covers: names a list of paths", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_an_empty_list_item_is_a_finding(self):
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        text = doc("covers:\n  - README.md\n  - ")
        self.assertIn("\n  - \n", text)
        self.write(self.shelf(root) / "note.md", text)
        landed = (self.shelf(root) / "note.md").read_text()
        self.assertIn("README.md", landed)
        self.assertRegex(landed, r"(?m)^  - $")
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("note.md", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_flow_list_empty_quoted_item_is_a_finding(self):
        # covers: [README.md, ""] is an empty list item, not a path
        # that resolves to the repository root.
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        self.assertTrue((root / "README.md").is_file())
        text = doc('covers: [README.md, ""]')
        self.assertIn('covers: [README.md, ""]', text)
        self.assertNotIn("covers:\n  -", text)
        self.write(self.shelf(root) / "note.md", text)
        landed = (self.shelf(root) / "note.md").read_text()
        self.assertIn('covers: [README.md, ""]', landed)
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("note.md", out)
        self.assertIn("empty list item", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_unclosed_frontmatter_is_a_finding(self):
        root = self.sandbox()
        text = doc(close=False)
        self.assertEqual(text.count("---"), 1)
        self.write(self.shelf(root) / "note.md", text)
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("note.md", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_missing_name_is_a_finding(self):
        root = self.sandbox()
        text = doc(name=None)
        self.assertNotIn("name:", text)
        self.assertIn("description:", text)
        self.write(self.shelf(root) / "note.md", text)
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("note.md", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_missing_description_is_a_finding(self):
        root = self.sandbox()
        text = doc(description=None)
        self.assertIn("name:", text)
        self.assertNotIn("description:", text)
        self.write(self.shelf(root) / "note.md", text)
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("note.md", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_second_covers_key_is_not_silence(self):
        # Outcome (judge both vs malformed) is underdetermined; silence
        # is not. First key exists, second does not: dropping the
        # second key would report clean.
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        text = doc("covers:\n  - README.md\ncovers:\n  - no/such/path.py")
        self.assertEqual(text.count("covers:"), 2)
        self.write(self.shelf(root) / "note.md", text)
        landed = (self.shelf(root) / "note.md").read_text()
        self.assertEqual(landed.count("covers:"), 2)
        self.assertIn("no/such/path.py", landed)
        self.assertFalse((root / "no/such/path.py").exists())
        self.assertTrue((root / "README.md").is_file())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertNotIn("clean", out)

    def test_a_second_covers_key_at_column_zero_is_not_a_mapping_finding(self):
        # Near-miss of the indented mapping: the second covers: sits at
        # column 0. Both keys name an existing path, so swallowing the
        # second key as a follow-line would either stay clean on one
        # path or flag a mapping on a document that should be clean.
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        self.write(root / "OTHER.md", "ok\n")
        text = doc("covers:\n  - README.md\ncovers:\n  - OTHER.md")
        self.assertEqual(text.count("covers:"), 2)
        self.assertRegex(
            text, r"(?m)^covers:\n  - README.md\ncovers:\n  - OTHER.md")
        self.assertNotRegex(text, r"(?m)^  covers:")
        self.write(self.shelf(root) / "note.md", text)
        landed = (self.shelf(root) / "note.md").read_text()
        self.assertEqual(landed.count("covers:"), 2)
        self.assertRegex(landed, r"(?m)^covers:\n  - OTHER.md")
        self.assertNotRegex(landed, r"(?m)^  covers:")
        self.assertTrue((root / "README.md").is_file())
        self.assertTrue((root / "OTHER.md").is_file())
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)
        self.assertNotIn("is not a list item", out)
        self.assertNotIn("INVALID —", out)
        self.assertRegex(out, r"1 doc\(s\), 2 covers: path\(s\)")


class NothingToJudge(CheckerCase):
    """Zero .md files under the shelf is INVALID, not a hollow clean."""

    def test_zero_markdown_files_is_invalid(self):
        root = self.sandbox()
        leftover = self.shelf(root) / "not-markdown.txt"
        self.write(leftover, "not a document\n")
        self.assertFalse(list(self.shelf(root).glob("*.md")))
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("INVALID —", out)
        self.assertIn("ops/docs", out)
        self.assertNotIn("clean", out)


class PrintedLinesTellTheClassesApart(CheckerCase):
    """Findings and INVALID are counted separately; never exit 2/3/64/70."""

    def test_a_finding_and_an_invalid_are_both_printed(self):
        root = self.sandbox()
        self.write(
            self.shelf(root) / "miss.md",
            doc("covers:\n  - no/such/path.py"),
        )
        self.assertFalse((root / "no/such/path.py").exists())
        payload = b"\xff\xfe---\nname: x\ndescription: y\n---\n"
        self.write_bytes(self.shelf(root) / "bad.md", payload)
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("does not exist", out)
        self.assertIn("INVALID —", out)
        self.assertIn("miss.md", out)
        self.assertIn("bad.md", out)
        self.assertNotIn("clean", out)


class WalkIsRecursive(CheckerCase):
    """*.md under the shelf includes nested documents; glob('*.md') does not."""

    def test_a_nested_missing_path_is_found_under_the_shelf(self):
        root = self.sandbox()
        self.write(self.shelf(root) / "ok.md", doc())
        nested = self.shelf(root) / "sub" / "nested.md"
        raw = "no/such/nested.py"
        self.write(nested, doc(f"covers:\n  - {raw}"))
        self.assertEqual(self.top_level_md(root), ["ok.md"])
        self.assertTrue(nested.is_file())
        self.assertFalse((root / raw).exists())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("nested.md", out)
        self.assertIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_nested_dotdot_segment_is_found_under_the_shelf(self):
        root = self.sandbox()
        self.write(self.shelf(root) / "ok.md", doc())
        self.write(self.shelf(root) / "README.md", "# index\n")
        raw = "ops/docs/../docs/README.md"
        nested = self.shelf(root) / "sub" / "nested.md"
        self.write(nested, doc(f"covers:\n  - {raw}"))
        self.assertEqual(self.top_level_md(root), ["README.md", "ok.md"])
        self.assertTrue(nested.is_file())
        self.assertTrue((root / raw).resolve().is_file())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("nested.md", out)
        self.assertIn(raw, out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)

    def test_a_nested_malformed_declaration_is_found_under_the_shelf(self):
        root = self.sandbox()
        self.write(root / "README.md", "ok\n")
        self.write(self.shelf(root) / "ok.md", doc())
        nested = self.shelf(root) / "sub" / "nested.md"
        self.write(nested, doc("covers: README.md"))
        landed = nested.read_text()
        self.assertIn("covers: README.md", landed)
        self.assertNotIn("covers:\n  -", landed)
        self.assertEqual(self.top_level_md(root), ["ok.md"])
        self.assertTrue(nested.is_file())
        self.assertTrue((root / "README.md").is_file())
        code, out = self.run_check(root)
        self.assertEqual(code, 1, out)
        self.assertIn("nested.md", out)
        self.assertNotIn("does not exist", out)
        self.assertNotIn("INVALID —", out)
        self.assertNotIn("clean", out)


class NoFrontmatterIsNotJudged(CheckerCase):
    """A doc that does not open with --- is not judged."""

    def test_a_doc_that_does_not_open_with_frontmatter_is_not_judged(self):
        root = self.sandbox()
        self.write(root / "ok.py", "x\n")
        plain = "# just prose, no header\n"
        self.assertFalse(plain.startswith("---"))
        self.write(self.shelf(root) / "plain.md", plain)
        self.write(
            self.shelf(root) / "note.md",
            doc("covers:\n  - ok.py"),
        )
        self.assertTrue((root / "ok.py").is_file())
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)
        self.assertNotIn("INVALID —", out)

    def test_no_frontmatter_docs_alone_are_clean(self):
        root = self.sandbox()
        readme = "# README\nprose\n"
        todo = "# TODO\nprose\n"
        self.assertFalse(readme.startswith("---"))
        self.assertFalse(todo.startswith("---"))
        self.write(self.shelf(root) / "README.md", readme)
        self.write(self.shelf(root) / "TODO.md", todo)
        code, out = self.run_check(root)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)
        self.assertNotIn("INVALID —", out)


class ExitCodesAreOnlyZeroAndOne(CheckerCase):
    """Exit codes only 0 and 1. Never 2, 3, 64 or 70 — those are wf's."""

    def test_an_unknown_flag_exits_only_0_or_1(self):
        root = self.sandbox()
        self.write(self.shelf(root) / "a.md", doc())
        code, out = self.run_check(root, extra=("--definitely-unknown",))
        self.assertIn(code, (0, 1), out)
        self.assertNotIn(code, (2, 3, 64, 70))


if __name__ == "__main__":
    unittest.main(verbosity=2)
