"""Independent regression tests: Git observation executes nothing a source configures.

Contract (only): `ops/conductor/monitor-lever.md`, the guarantee that
observation never invokes arbitrary configured commands, and that a remote
needing a configured command, helper or disallowed transport reads as
remote-unavailable. Tests drive the existing CLI through `_GitRefsFixture`;
its git shim passes through to the real Git, so these exercise Git itself.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from test_monitor_git_refs import REMOTE_NAME, _GitRefsFixture


class GitObservationIsolation(_GitRefsFixture):
    """A source repository's configuration cannot make observation run a program."""

    def _plant_marker_script(self, name: str, marker: Path) -> Path:
        script = self.bin / name
        body = f"#!/bin/sh\n: > {str(marker)!r}\nexit 255\n"
        self._plant_bytes(script, body.encode("utf-8"))
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.assertTrue(os.access(script, os.X_OK), script)
        self.assertFalse(marker.exists(), marker)
        return script

    def _assert_unavailable_without_execution(self, marker: Path) -> None:
        proc, counts = self.run_counts()
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        self.assertEqual(counts["observations"], 2, counts)
        self.assertEqual(counts["unavailable"], 2, counts)
        self.assertFalse(marker.exists(), "a configured command ran during observation")
        self.assert_one_ls_remote(self.git_repo)

    def test_repo_core_sshcommand_is_not_executed(self):
        self.plant_pair()
        configured_ran = self.scratch / "configured-ssh-ran"
        default_ran = self.scratch / "default-ssh-ran"
        configured = self._plant_marker_script("configured-ssh", configured_ran)
        self._plant_marker_script("ssh", default_ran)
        self.git(self.git_repo, "remote", "set-url", REMOTE_NAME, "ssh://127.0.0.1:1/none.git")
        self.git(self.git_repo, "config", "core.sshCommand", str(configured))
        self.plant_git_refs()
        self._assert_unavailable_without_execution(configured_ran)
        self.assertTrue(default_ran.exists(), "the default ssh on PATH was not what Git ran")

    def test_ext_transport_is_refused_before_execution(self):
        self.plant_pair()
        marker = self.scratch / "ext-helper-ran"
        self.git(self.git_repo, "remote", "set-url", REMOTE_NAME, f"ext::sh -c \': > {marker}\' %S")
        self.plant_git_refs()
        self._assert_unavailable_without_execution(marker)
