"""Ledger 51: Codex check-tests must write out/SKEPTIC.md.

A Codex job whose deliverable is a file under the job out/ directory
passes that out/ path in sandbox_workspace_write.writable_roots even
when the snapshot sandbox stays read-only. TMPDIR for the child is a
directory created under out/ before exec. The snapshot (cwd) is not
switched to workspace-write.

Written from the slice contract. launch.py is not read here.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import launch_support as ls


def _argv_strs(argv) -> list[str]:
    return [str(item) for item in argv]


def _sandbox_value(argv) -> str | None:
    items = _argv_strs(argv)
    if "--sandbox" not in items:
        return None
    idx = items.index("--sandbox")
    if idx + 1 >= len(items):
        return None
    return items[idx + 1]


def _writable_roots_blob(argv) -> str:
    """Config tokens that name sandbox_workspace_write.writable_roots."""
    items = _argv_strs(argv)
    chunks: list[str] = []
    for idx, item in enumerate(items):
        if "writable_roots" in item or "sandbox_workspace_write" in item:
            chunks.append(item)
            if idx + 1 < len(items) and not str(items[idx + 1]).startswith("-"):
                chunks.append(str(items[idx + 1]))
    return " ".join(chunks)


def _writable_roots(argv) -> list[str]:
    blob = _writable_roots_blob(argv)
    roots: list[str] = []
    for match in re.finditer(r"\[[^\]]*\]", blob):
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            roots.extend(str(item) for item in value)
    if not roots:
        roots.extend(re.findall(r"/[^\s,\[\]\"']+", blob))
    return roots


def _real(path) -> str:
    return os.path.realpath(str(path))


class CodexCheckTestsCanWriteTheJobOutDir(ls._TempLaunch):
    """check-tests deliverable is out/SKEPTIC.md; the snapshot stays read-only."""

    def _launch_codex_check_tests(self):
        rec, witness, *_ = self.launch_ok(
            job="check-tests", harness="codex", stage="check-tests",
        )
        self.assertEqual(rec["job"], "check-tests")
        self.assertEqual(rec["role"], "read")
        self.assertEqual(rec["harness"]["name"], "codex")
        argv = _argv_strs(witness["argv"])
        self.assertTrue(argv, "child argv is empty")
        return rec, witness, argv

    def test_codex_check_tests_writable_roots_names_the_job_out_dir(self):
        rec, _witness, argv = self._launch_codex_check_tests()
        out_dir = self.the_job_dir() / "out"
        self.assertTrue(
            out_dir.is_dir(),
            f"job out dir must exist so writable_roots can name it: {out_dir}",
        )
        blob = _writable_roots_blob(argv)
        self.assertIn(
            "sandbox_workspace_write.writable_roots",
            " ".join(argv),
            "check-tests Codex argv must pass "
            "sandbox_workspace_write.writable_roots even when the snapshot "
            f"sandbox is read-only; argv={argv!r}",
        )
        self.assertTrue(
            blob.strip(),
            f"writable_roots config is missing from argv={argv!r}",
        )
        out_real = _real(out_dir)
        roots = _writable_roots(argv)
        self.assertTrue(
            roots,
            f"writable_roots listed no paths; blob={blob!r} argv={argv!r}",
        )
        root_reals = [_real(item) for item in roots]
        self.assertIn(
            out_real,
            root_reals,
            f"writable_roots must name the job out dir {out_real}; "
            f"listed={roots!r} blob={blob!r}",
        )
        self.assertEqual(
            _sandbox_value(argv),
            "read-only",
            "snapshot sandbox stays read-only; do not switch the Codex "
            f"read role to workspace-write; argv={argv!r}",
        )
        self.assertNotEqual(_sandbox_value(argv), "workspace-write")
        snapshot = _real(self.snapshot_of(rec))
        for root in root_reals:
            self.assertFalse(
                snapshot == root or snapshot.startswith(root + os.sep),
                f"writable root {root} makes the snapshot {snapshot} "
                f"writable; argv={argv!r}",
            )

    def test_codex_check_tests_tmpdir_is_a_directory_under_out(self):
        rec, witness, _argv = self._launch_codex_check_tests()
        env = witness.get("env") or {}
        tmpdir = env.get("TMPDIR")
        self.assertTrue(
            tmpdir,
            "TMPDIR must be set on the Codex check-tests child so unittest "
            f"setUp can create temp files; env={env!r}",
        )
        started = self.read_start_witness()
        self.assertEqual(
            started.get("tmpdir"),
            tmpdir,
            "start-witness TMPDIR must match the child env at exec",
        )
        self.assertTrue(
            started.get("tmpdir_is_dir"),
            "TMPDIR must already be a directory at exec "
            f"(created under out/ before the child runs); "
            f"tmpdir={tmpdir!r} witness={started!r}",
        )
        out_real = _real(self.the_job_dir() / "out")
        tmp_real = _real(tmpdir)
        self.assertTrue(
            tmp_real == out_real or tmp_real.startswith(out_real + os.sep),
            f"TMPDIR must point under the job out dir {out_real}; "
            f"got {tmp_real}",
        )
        snapshot = _real(self.snapshot_of(rec))
        self.assertFalse(
            tmp_real == snapshot or tmp_real.startswith(snapshot + os.sep),
            f"TMPDIR must not land in the read-only snapshot {snapshot}; "
            f"got {tmp_real}",
        )
        self.assertTrue(
            Path(tmpdir).is_dir(),
            f"TMPDIR {tmpdir!r} did not remain a directory after the child",
        )
