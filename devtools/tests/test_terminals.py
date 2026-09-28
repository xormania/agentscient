import subprocess
import unittest
from unittest.mock import Mock, patch

from devtools import terminals


class TerminalTests(unittest.TestCase):
    def test_owned_server_and_session_are_isolated_and_argv_is_quoted(self):
        store = Mock(directory="/private/team one")
        absent = subprocess.CompletedProcess([], 1, "", "no server running")
        created = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch("devtools.terminals.shutil.which", return_value="/bin/tmux"),
            patch("devtools.terminals.subprocess.run", side_effect=[absent, created]) as run,
        ):
            result = terminals.start(store, "coder", ["/python", "file with spaces.py", "$(no-shell)"], "/work path")
        argv = run.call_args.args[0]
        self.assertEqual("/bin/tmux", argv[0])
        self.assertEqual("-L", argv[1])
        self.assertIn("/dev/null", argv)
        self.assertEqual("exec /python 'file with spaces.py' '$(no-shell)'", argv[-1])
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
