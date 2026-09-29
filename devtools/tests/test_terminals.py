import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from support import require_tmux

from devtools import terminals
from devtools.bootstrap import send


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
        with (patch("devtools.terminals.command", return_value=Mock(returncode=0)) as command,
              patch("devtools.terminals.status", return_value={"panes": [{"pid": 123, "dead": False}]})):
            with self.assertRaisesRegex(ValueError, "already has"):
                terminals.start(store, "coder", ["/python"], "/work")
            self.assertEqual(1, command.call_count)
        with patch("devtools.terminals.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "Install tmux"):
                terminals.start(store, "coder", ["/python"], "/work")

    def test_socket_environment_is_applied_before_application_imports_without_a_secret_file(self):
        require_tmux()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stale, wanted = root / "stale", root / "wanted"
            stale.mkdir()
            wanted.mkdir()
            marker = root / "stale-imported"
            (stale / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').write('stale')\n")
            (wanted / "selected_module.py").write_text("VALUE = 'current-launch'\n")
            intended = {**os.environ, "PYTHONPATH": str(wanted), "TEST_API_KEY": "private-snapshot-secret"}
            intended.pop("PYTHONHOME", None)
            bootstrap = Path(__file__).resolve().parents[1] / "bootstrap.py"
            application = "import json,os,selected_module; print(json.dumps([selected_module.VALUE,os.environ['TMUX_PANE'],os.environ['TEST_API_KEY']]))"
            bad = {**os.environ, "PYTHONHOME": str(stale), "PYTHONPATH": str(stale), "TMUX_PANE": "%42"}
            # Exercise both isolated Python and the exact environment overrides
            # tmux supplies: some loader flags trigger even with an empty value.
            for environment in (bad, {**bad, **dict.fromkeys(terminals.BOOTSTRAP_UNSET, "")}):
                address = "agentscient-test-" + uuid.uuid4().hex
                argv = [sys.executable, "-I", "-S", str(bootstrap), address, sys.executable, "-c", application]
                with socket.socket(socket.AF_UNIX) as listener, ThreadPoolExecutor(max_workers=1) as pool:
                    listener.bind("\0" + address)
                    listener.listen(1)
                    listener.settimeout(5)

                    def handoff():
                        stream, _ = listener.accept()
                        with stream:
                            send(stream, intended)

                    transfer = pool.submit(handoff)
                    result = subprocess.run(argv, env=environment, capture_output=True, text=True, timeout=10)
                    transfer.result()
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(["current-launch", "%42", "private-snapshot-secret"], json.loads(result.stdout))
                self.assertFalse(marker.exists())
            self.assertNotIn("private-snapshot-secret", " ".join(argv))
            self.assertFalse(any("private-snapshot-secret" in path.read_text()
                                 for path in root.rglob('*') if path.is_file() and path.suffix == '.json'))
