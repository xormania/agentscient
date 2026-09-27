"""Container-only setup for the separately installed Serena MCP process."""

import os
import shutil
from pathlib import Path

Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)
target = Path(os.environ["SERENA_HOME"]) / "language_servers/static/PhpactorServer/phpactor.phar"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile("/opt/phpactor.phar", target)
os.execvp(
    "serena",
    [
        "serena",
        "start-mcp-server",
        "--project",
        "/workspace",
        "--agent-interface",
        "REPL",
        "--context",
        "desktop-app",
        "--mode",
        "editing",
        "--mode",
        "no-onboarding",
        "--enable-web-dashboard",
        "False",
        "--open-web-dashboard",
        "False",
        "--enable-gui-log-window",
        "False",
        "--tool-timeout",
        "90",
    ],
)
