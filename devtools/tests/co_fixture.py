#!/usr/bin/env python3
"""Native TUI fixture: validates launch isolation and exercises real CO MCP."""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

args = sys.argv[1:]
if "--mcp-config" in args:
    harness = "claude"
    servers = json.loads(Path(args[args.index("--mcp-config") + 1]).read_text())["mcpServers"]
    assert args[args.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in args
    Path(args[args.index("--debug-file") + 1]).write_text(
        '2026-09-28T01:00:00.000Z [DEBUG] MCP server "agentscient_dev": Channel notifications registered\n'
    )
elif "--rules" in args:
    harness = "grok"
    assert os.environ["HOME"] == os.environ["GROK_HOME"]
    servers = tomllib.loads((Path(os.environ["GROK_HOME"]) / "config.toml").read_text())["mcp_servers"]
    assert args[args.index("--tools") + 1] == "search_tool,use_tool"
else:
    harness = "codex"
    options = {}
    for index, arg in enumerate(args):
        if arg == "-c":
            options.update(tomllib.loads(args[index + 1]))
    servers = options["mcp_servers"]
    assert options["sandbox_mode"] == "read-only"
    assert options["model"] == "selected-model" and options["model_reasoning_effort"] == "high"

assert set(servers) == {"agentscient_dev"}
assert Path.cwd().name == "console"
server = servers["agentscient_dev"]
assert "--generation" in server["args"] and "--operator" not in server["args"]
process = subprocess.Popen(
    [server["command"], *server["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
)
ident = 0


def call(method, params=None):
    global ident
    ident += 1
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}) + "\n")
    process.stdin.flush()
    while True:
        packet = json.loads(process.stdout.readline())
        if packet.get("id") == ident:
            assert "error" not in packet, packet
            return packet["result"]


def tool(name, arguments):
    result = call("tools/call", {"name": name, "arguments": arguments})
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


try:
    call("initialize", {"clientInfo": {"name": harness + "-tui-fixture", "version": "1"}})
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    process.stdin.flush()
    onboard = tool("onboard", {})
    assert onboard["role"] == "co"
    tool("skill_read", {"name": "agentscient-co"})
    context = tool("work_context", {})
    assert "Preserve this decision" in json.dumps(context)
    tool("work_report", {"text": "CO recovered using " + harness, "kind": "progress"})
    # Separate PTY writes deliberately split a credential before one complete line.
    secret = os.environ["TEST_API_KEY"]
    os.write(1, ("Live CO response " + harness + " " + secret[:7]).encode())
    os.write(1, (secret[7:] + "\n").encode())
finally:
    process.stdin.close()
    process.wait(timeout=5)
