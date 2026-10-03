"""Add an ephemeral Grok CO connection without replacing native configuration.

Grok's interactive CLI discovers project plugins but has no per-session MCP
configuration flag. The generated plugin is additive and uses normal native
project trust. Its commands run only in the operator launch environment.
"""

import copy
import json
import os
import re
import shlex
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

GENERATION_ENV = "AGENTSCIENT_CO_GENERATION"


def _identity(path):
    value = path.lstat()
    return value.st_dev, value.st_ino


@contextmanager
def grok_plugin(private, server, workspace):
    """Expose one generation's connection; preserve existing and edited files.

    The caller sets GENERATION_ENV only on the CO process and removes it from
    managed-worker environments. No global configuration or trust is changed.
    """
    from .api import SERVER

    private, workspace = Path(private).resolve(), Path(workspace).resolve()
    generation = private.name
    if not re.fullmatch(r"[0-9a-f]{32}", generation):
        raise ValueError("The Grok console plugin requires a native session generation.")
    name = "agentscient-co-" + generation
    plugin = workspace / ".grok" / "plugins" / name
    gate = [sys.executable, str(Path(__file__).resolve()), generation]
    hooks = copy.deepcopy(json.loads((private / "observer-hooks.json").read_text()))
    if "PreToolUse" in hooks:
        raise ValueError("Operator plugin hooks must observe without imposing tool permissions.")
    for groups in hooks.values():
        for group in groups:
            for handler in group["hooks"]:
                handler["command"] = shlex.join([*gate, *shlex.split(handler["command"])])
    connection = {**server, "type": "stdio", "command": sys.executable,
                  "args": [*gate[1:], server["command"], *server.get("args", [])]}
    # A marker written into the plugin would give other sessions the launch
    # identity. Only the environment of the actual CO process supplies it.
    if GENERATION_ENV in connection.get("env", {}):
        raise ValueError("The operator launch marker cannot be configured on an MCP server.")
    # Grok does not namespace plugin MCP server names. A unique name keeps a
    # concurrent console or a stale plugin from hiding this generation's server.
    server_name = SERVER + "_" + generation
    manifest = {"name": name, "version": "1.0.0",
                "description": "Agentscient operator session connection and observation.",
                "mcpServers": {server_name: connection}, "hooks": {"hooks": hooks}}
    data = (json.dumps(manifest, indent=2) + "\n").encode()
    created, files = [], []
    try:
        for directory in (workspace / ".grok", workspace / ".grok" / "plugins", plugin):
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                if directory == plugin or not directory.is_dir():
                    raise
            else:
                created.append((directory, _identity(directory)))
        path = plugin / "plugin.json"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        files.append((path, _identity(path), data))
        yield plugin
    finally:
        for path, identity, contents in files:
            try:
                if (_identity(path) == identity and stat.S_ISREG(path.lstat().st_mode)
                        and path.read_bytes() == contents):
                    path.unlink()
            except OSError:
                pass  # Preserve files changed or replaced by the operator.
        for directory, identity in reversed(created):
            try:
                if _identity(directory) == identity:
                    directory.rmdir()
            except OSError:
                pass  # Remove only our still-empty directories.


def main():
    """Grok invokes this gate for both MCP processes and observer hooks."""
    if len(sys.argv) >= 3 and os.environ.get(GENERATION_ENV) == sys.argv[1]:
        os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
