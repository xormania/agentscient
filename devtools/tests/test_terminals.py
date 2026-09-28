import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from devtools import terminals


class TerminalTests(unittest.TestCase):
    def test_owned_server_and_session_are_isolated_and_argv_is_literal(self):
        store = Mock(directory="/private/team one")
        absent = subprocess.CompletedProcess([], 1, "", "no server running")
        created = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch("devtools.terminals.shutil.which", return_value="/bin/tmux"),
            patch("devtools.terminals.subprocess.run", side_effect=[absent, absent, created]) as run,
        ):
            result = terminals.start(store, "coder", ["/python", "file with spaces.py", "$(no-shell)"], "/work path")
        argv = run.call_args.args[0]
        self.assertEqual("/bin/tmux", argv[0])
        self.assertEqual("-L", argv[1])
        self.assertIn("/dev/null", argv)
        self.assertEqual(["set-environment", "-gu", "LD_TRACE_LOADED_OBJECTS"], run.call_args_list[1].args[0][-3:])
        self.assertEqual(["/python", "file with spaces.py", "$(no-shell)"], argv[argv.index("--") + 1:])
        for name in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "PYTHONHOME", "PYTHONPATH"):
            self.assertIn(name + "=", argv)
        self.assertIn(result["server"], result["attach"])
        self.assertNotEqual(terminals.address("/one", "coder"), terminals.address("/two", "coder"))
        with self.assertRaises(ValueError):
            terminals.address("/one", "other:window")

    def test_collision_cannot_kill_existing_terminal_and_missing_tmux_fails(self):
        store = Mock(directory="/private/team")
        with patch("devtools.terminals.command", return_value=Mock(returncode=0)) as command:
            with self.assertRaisesRegex(ValueError, "already has"):
                terminals.start(store, "coder", ["/python"], "/work")
            self.assertEqual(1, command.call_count)
        with patch("devtools.terminals.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "Install tmux"):
                terminals.start(store, "coder", ["/python"], "/work")

    def test_snapshot_environment_is_applied_before_the_application_interpreter_starts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stale, wanted = root / "stale", root / "wanted"
            stale.mkdir()
            wanted.mkdir()
            marker = root / "stale-imported"
            (stale / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').write('stale')\n")
            (wanted / "selected_module.py").write_text("VALUE = 'current-launch'\n")
            snapshot = root / "launch.json"
            intended = {**os.environ, "PYTHONPATH": str(wanted), "TEST_API_KEY": "private-snapshot-secret"}
            intended.pop("PYTHONHOME", None)
            snapshot.write_text(json.dumps({"environment": intended}))
            bootstrap = Path(__file__).resolve().parents[1] / "bootstrap.py"
            application = "import json,os,selected_module; print(json.dumps([selected_module.VALUE,os.environ['TMUX_PANE'],os.environ['TEST_API_KEY']]))"
            argv = [sys.executable, "-I", "-S", str(bootstrap), str(snapshot), sys.executable, "-c", application]
            bad = {**os.environ, "PYTHONHOME": str(stale), "PYTHONPATH": str(stale), "TMUX_PANE": "%42"}
            # Exercise both isolated Python and the exact environment overrides
            # tmux supplies: some loader flags trigger even with an empty value.
            for environment in (bad, {**bad, **dict.fromkeys(terminals.BOOTSTRAP_UNSET, "")}):
                result = subprocess.run(argv, env=environment, capture_output=True, text=True, timeout=10)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(["current-launch", "%42", "private-snapshot-secret"], json.loads(result.stdout))
                self.assertFalse(marker.exists())
            self.assertNotIn("private-snapshot-secret", " ".join(argv))
