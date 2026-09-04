"""Independent tests for the permission doctor (permission-surface.md).

Contract sources (only): `ops/conductor/permission-surface.md`,
`.claude/skills/co-doc/SKILL.md`, and the author-tests brief. The tool
is copied as unread bytes into a throwaway tree and run with HOME
pointed at a temp dir.

PIN_CLEAN_SURFACE: exit 0 requires every probe to run with no findings.
The fixture plants the layers the contract names (settings objects,
ledgers, a wf.py that answers --help, copies of dispatch.conf /
dispatch.sh). Paths a probe examines that the contract does not name
are filled only if the doctor's own output names them.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "ops" / "conductor" / "tools"
CO_DOC = "co_doc.py"

PROBE_IDS = [
    "P-SET-1",
    "P-PERM-1",
    "P-PERM-2",
    "P-HOOK-1",
    "P-HOOK-2",
    "P-LEV-1",
    "P-ID-1",
    "P-WF-1",
    "P-DB-1",
]

CLASSES = ("Rejection", "Denial", "Abort", "Finding")
FINDING_LINE = re.compile(
    r"^\[(?P<cls>Rejection|Denial|Abort|Finding)\] "
    r"(?P<probe>P-[A-Z]+-\d+): .+"
    r"(—|\u2013|--) *remedy: .+"
)

INERT_PATH = "/no/such/agentscient-inert-grant-9f3c1e2a"
AGENT = "Test Author <noreply@example.invalid>"


def _copy_unread(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    dst.write_bytes(data)
    if dst.read_bytes() != data:
        raise AssertionError(f"copy of {src.name} did not land intact")


def _tree_rel(root: Path) -> set[str]:
    found: set[str] = set()
    if not root.exists():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in filenames:
            full = Path(dirpath) / name
            found.add(str(full.relative_to(root)))
    return found


class DoctorFixture(unittest.TestCase):
    """Temp repo + HOME; live tree, live settings, live ledgers stay put."""

    def setUp(self):
        self._real_home = Path.home()
        self._real_state = self._real_home / ".local" / "state" / "agentscient"
        self._state_listing = None
        if self._real_state.is_dir():
            self._state_listing = frozenset(os.listdir(self._real_state))

        self._tmp = tempfile.TemporaryDirectory(prefix="co-doc-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.repo = root / "repo"
        self.scratch = root / "scratch"
        for path in (self.home, self.repo, self.scratch):
            path.mkdir()
        (self.home / ".local" / "state" / "agentscient").mkdir(parents=True)
        (self.home / ".claude").mkdir()

        src_dir = TOOLS
        tools = self.repo / "ops" / "conductor" / "tools"
        tools.mkdir(parents=True)
        src = src_dir / CO_DOC
        self.assertTrue(src.is_file(), f"missing tool at {src}")
        self.tool = tools / CO_DOC
        _copy_unread(src, self.tool)
        sh = src_dir / "dispatch.sh"
        if sh.is_file():
            _copy_unread(sh, tools / "dispatch.sh")
            (tools / "dispatch.sh").chmod(0o755)
        # P-LEV-1 reports LAUNCHER_PIN / gate.sh live or inert; inert is a
        # finding in this instrument, so a clean surface plants live ones.
        pin = self.scratch / "launch.py"
        pin.write_text(
            "#!/usr/bin/env python3\nprint('launch')\n", encoding="utf-8",
        )
        pin.chmod(0o755)
        gate = tools / "gate.sh"
        gate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        gate.chmod(0o755)
        conf = tools / "dispatch.conf"
        conf.write_text(f"LAUNCHER_PIN='{pin}'\n", encoding="utf-8")
        self.assertIn("LAUNCHER_PIN", conf.read_text(encoding="utf-8"))
        self.assertTrue(pin.is_file() and gate.is_file())

        wf_dir = self.repo / "ops" / "devlane" / "workflow"
        wf_dir.mkdir(parents=True)
        wf_py = wf_dir / "wf.py"
        wf_py.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('usage: wf')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        wf_py.chmod(0o755)

        self.state = self.home / ".local" / "state" / "agentscient"
        self.skills_db = self.state / "skills.db"
        self.handwork_db = self.state / "handwork.db"
        for db in (self.skills_db, self.handwork_db):
            sqlite3.connect(str(db)).close()
            self.assertTrue(db.is_file(), f"plant: {db.name} must exist")

        claude = self.repo / ".claude"
        claude.mkdir(parents=True)
        self.repo_settings = claude / "settings.json"
        self.repo_local = claude / "settings.local.json"
        self.user_settings = self.home / ".claude" / "settings.json"
        empty = "{}\n"
        self.repo_settings.write_text(empty, encoding="utf-8")
        self.repo_local.write_text(empty, encoding="utf-8")
        self.user_settings.write_text(empty, encoding="utf-8")

    def tearDown(self):
        try:
            if self._state_listing is not None:
                self.assertEqual(
                    frozenset(os.listdir(self._real_state)),
                    self._state_listing,
                    "live ~/.local/state/agentscient must be untouched",
                )
        finally:
            self._tmp.cleanup()

    def _env(self, agent=None):
        env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "TMPDIR": str(self.scratch),
            "XDG_STATE_HOME": str(self.home / ".local" / "state"),
        }
        if agent is not None:
            env["WF_AGENT"] = agent
        return env

    def _run(self, *argv, agent=AGENT):
        proc = subprocess.run(
            [sys.executable, str(self.tool), *argv],
            cwd=str(self.repo),
            env=self._env(agent=agent),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc, out

    def _write_settings(self, path: Path, payload) -> bytes:
        before = path.read_bytes() if path.exists() else b""
        text = json.dumps(payload, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        after = path.read_bytes()
        self.assertNotEqual(after, before, f"plant did not change {path.name}")
        loaded = json.loads(after.decode("utf-8"))
        self.assertIsInstance(loaded, dict, "planted settings must still parse")
        return after


class TestListProbes(DoctorFixture):
    def test_list_probes_prints_exactly_the_nine_contract_ids(self):
        # Broken impl that drifts from the table (missing, extra, renamed).
        self.assertEqual(len(PROBE_IDS), 9)
        proc, out = self._run("--list-probes")
        self.assertEqual(proc.returncode, 0, out)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        self.assertEqual(lines, PROBE_IDS)


class TestExitCodes(DoctorFixture):
    def test_exit_0_on_clean_surface(self):
        # Broken impl that exits 1 on notes, or 0 while a probe is INVALID.
        proc, out = self._run()
        self.assertEqual(proc.returncode, 0, out)

    def test_exit_1_when_findings_present(self):
        # Broken impl that still exits 0 after a P-HOOK-2 finding.
        self._plant_dot_star_matcher()
        proc, out = self._run()
        self.assertEqual(proc.returncode, 1, out)
        self.assertIn("P-HOOK-2", out)

    def test_exit_2_when_any_probe_is_invalid(self):
        # Broken impl that reports unparseable settings as a finding (1)
        # rather than INVALID (2).
        self.repo_settings.write_text("{not-json", encoding="utf-8")
        self.assertNotEqual(
            self.repo_settings.read_text(encoding="utf-8").strip(),
            "{}",
            "plant: unparseable settings must differ from the clean object",
        )
        proc, out = self._run()
        self.assertEqual(proc.returncode, 2, out)
        self.assertIn("P-SET-1", out)
        self.assertRegex(out, r"INVALID")

    def _plant_dot_star_matcher(self):
        hook_cmd = self.scratch / "hook.sh"
        hook_cmd.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook_cmd.chmod(0o755)
        payload = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": str(hook_cmd)},
                        ],
                    }
                ]
            }
        }
        self._write_settings(self.repo_settings, payload)
        loaded = json.loads(self.repo_settings.read_text(encoding="utf-8"))
        self.assertEqual(
            loaded["hooks"]["PreToolUse"][0]["matcher"],
            ".*",
            "plant: matcher must still be .*, fixture recognizable",
        )


class TestPSet1(DoctorFixture):
    def test_absent_settings_file_is_reported_not_silent(self):
        # Broken impl that treats an absent file as clean-by-silence.
        self.user_settings.unlink()
        self.assertFalse(self.user_settings.exists(), "plant: user settings gone")
        _proc, out = self._run()
        self.assertTrue(out.strip(), "absent settings must produce a line")
        self.assertRegex(out, r"settings\.json")
        self.assertRegex(out, r"(?i)absent")

    def test_unparseable_settings_makes_probe_invalid(self):
        planted = "this is not json {"
        self.repo_local.write_text(planted, encoding="utf-8")
        self.assertEqual(
            self.repo_local.read_text(encoding="utf-8"),
            planted,
            "plant: unparseable local settings landed",
        )
        proc, out = self._run()
        self.assertEqual(proc.returncode, 2, out)
        self.assertIn("P-SET-1", out)
        self.assertRegex(out, r"INVALID")


class TestPPerm1(DoctorFixture):
    def test_inert_grant_finding_names_the_unresolving_path(self):
        # Broken impl that skips allow rules whose targets do not resolve,
        # or that reports a finding without naming the path.
        clean = {"permissions": {"allow": []}}
        self.repo_settings.write_text(
            json.dumps(clean, indent=2) + "\n", encoding="utf-8",
        )
        before = self.repo_settings.read_bytes()
        planted = {
            "permissions": {
                "allow": [f"Read({INERT_PATH})"],
            }
        }
        after = self._write_settings(self.repo_settings, planted)
        self.assertNotEqual(after, before, "plant: settings must differ from clean")
        self.assertIn(INERT_PATH.encode("utf-8"), after)
        loaded = json.loads(after.decode("utf-8"))
        self.assertEqual(loaded["permissions"]["allow"], [f"Read({INERT_PATH})"])
        proc, out = self._run()
        self.assertEqual(proc.returncode, 1, out)
        self.assertIn("P-PERM-1", out)
        self.assertIn(INERT_PATH, out)
        self.assertRegex(out, r"inert", re.IGNORECASE)


class TestPHook2(DoctorFixture):
    def test_hook_matcher_dot_star_yields_a_finding(self):
        # Broken impl that accepts matcher '.*' as "names the tools".
        hook_cmd = self.scratch / "hook.sh"
        hook_cmd.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook_cmd.chmod(0o755)
        self.repo_settings.write_text("{}\n", encoding="utf-8")
        before = self.repo_settings.read_bytes()
        payload = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": str(hook_cmd)},
                        ],
                    }
                ]
            }
        }
        after = self._write_settings(self.repo_settings, payload)
        self.assertNotEqual(after, before)
        loaded = json.loads(after.decode("utf-8"))
        self.assertEqual(loaded["hooks"]["PreToolUse"][0]["matcher"], ".*")
        proc, out = self._run()
        self.assertEqual(proc.returncode, 1, out)
        self.assertIn("P-HOOK-2", out)


class TestReadOnly(DoctorFixture):
    def test_doctor_creates_no_files_absent_ledger_stays_absent(self):
        # Broken impl that opens ledgers with write/create and mints a db.
        self.skills_db.unlink()
        self.handwork_db.unlink()
        self.assertFalse(self.skills_db.exists(), "plant: skills.db absent")
        self.assertFalse(self.handwork_db.exists(), "plant: handwork.db absent")
        before_home = _tree_rel(self.home)
        before_repo = _tree_rel(self.repo)
        proc, _out = self._run()
        self.assertFalse(
            self.skills_db.exists(),
            "absent skills.db must still be absent after the doctor runs",
        )
        self.assertFalse(
            self.handwork_db.exists(),
            "absent handwork.db must still be absent after the doctor runs",
        )
        self.assertEqual(_tree_rel(self.home), before_home)
        self.assertEqual(_tree_rel(self.repo), before_repo)
        # Read-only is the pin; INVALID (2) is acceptable when the ledger
        # cannot be opened. Creating a file is not.
        self.assertIn(proc.returncode, (0, 1, 2))


class TestFindingShape(DoctorFixture):
    def test_finding_lines_carry_class_probe_id_and_remedy(self):
        # Broken impl that prints bare prose, omits the class, or drops
        # the remedy fragment.
        hook_cmd = self.scratch / "hook.sh"
        hook_cmd.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook_cmd.chmod(0o755)
        self._write_settings(
            self.repo_settings,
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": ".*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": str(hook_cmd),
                                }
                            ],
                        }
                    ]
                }
            },
        )
        proc, out = self._run()
        self.assertEqual(proc.returncode, 1, out)
        classified = [
            ln for ln in out.splitlines() if ln.startswith("[")
        ]
        self.assertTrue(classified, "expected classified finding lines:\n" + out)
        findings = []
        for ln in classified:
            if "INVALID" in ln:
                continue
            match = FINDING_LINE.search(ln)
            self.assertIsNotNone(
                match,
                "finding line must carry class, probe id, and remedy:\n"
                + ln,
            )
            self.assertIn(match.group("cls"), CLASSES)
            self.assertRegex(match.group("probe"), r"^P-[A-Z]+-\d+$")
            self.assertRegex(ln, r"remedy:", re.IGNORECASE)
            findings.append(ln)
        self.assertTrue(findings, "P-HOOK-2 must produce a finding line:\n" + out)
        self.assertTrue(any("P-HOOK-2" in ln for ln in findings))


class TestPLev1(DoctorFixture):
    """P-LEV-1: an unset LAUNCHER_PIN examines the sibling launcher."""

    def _conf(self) -> Path:
        return self.repo / "ops" / "conductor" / "tools" / "dispatch.conf"

    def _sibling_launcher(self) -> Path:
        return self.repo / "ops" / "devlane" / "dispatch" / "launch.py"

    def _plant_conf_without_launcher_pin(self) -> None:
        conf = self._conf()
        before = conf.read_text(encoding="utf-8")
        self.assertIn("LAUNCHER_PIN", before, "plant: default fixture pins")
        body = "# pin unset; sibling default applies\n"
        conf.write_text(body, encoding="utf-8")
        landed = conf.read_text(encoding="utf-8")
        self.assertEqual(landed, body, "plant: conf without pin did not land")
        self.assertNotIn("LAUNCHER_PIN=", landed)

    def _plant_live_sibling_launcher(self) -> Path:
        path = self._sibling_launcher()
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "#!/usr/bin/env python3\nprint('launch')\n"
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        self.assertEqual(path.read_text(encoding="utf-8"), body)
        self.assertTrue(os.access(path, os.X_OK), f"sibling not executable: {path}")
        return path

    def test_unset_pin_with_a_live_sibling_launcher_is_no_finding(self):
        self._plant_conf_without_launcher_pin()
        sibling = self._plant_live_sibling_launcher()
        self.assertTrue(sibling.is_file())
        proc, out = self._run()
        classified = [
            ln for ln in out.splitlines()
            if ln.startswith("[") and "P-LEV-1" in ln and "INVALID" not in ln
        ]
        self.assertEqual(classified, [], "P-LEV-1 must not be a finding:\n" + out)
        self.assertEqual(proc.returncode, 0, out)
        self.assertIn("P-LEV-1", out)
        self.assertRegex(out, r"(?i)live")
        self.assertIn("sibling default", out)
        self.assertIn(str(sibling), out)

    def test_unset_pin_with_an_absent_sibling_is_inert(self):
        self._plant_conf_without_launcher_pin()
        sibling = self._sibling_launcher()
        self.assertFalse(sibling.exists(), "plant: sibling launcher must be absent")
        proc, out = self._run()
        self.assertIn("sibling default", out)
        self.assertIn("P-LEV-1", out)
        self.assertIn(str(sibling), out)
        self.assertRegex(out, r"inert", re.IGNORECASE)
        self.assertEqual(proc.returncode, 1, out)


if __name__ == "__main__":
    unittest.main()
