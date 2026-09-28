#!/usr/bin/env python3
"""Claude hook/channel/transcript fixture. Never claims authenticated model use."""

import asyncio
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from devtools.rpc import RPC


async def main():
    def option(name):
        return sys.argv[sys.argv.index(name) + 1]

    native_id = option("--session-id")
    transcript = Path.home() / ".claude/projects/fixture" / (native_id + ".jsonl")
    transcript.parent.mkdir(parents=True, exist_ok=True)
    settings = json.loads(Path(option("--settings")).read_text())

    def hook(event, **fields):
        argv = shlex.split(settings["hooks"][event][0]["hooks"][0]["command"])
        payload = {"hook_event_name": event, "session_id": native_id, "transcript_path": str(transcript), **fields}
        subprocess.run(argv, input=json.dumps(payload), text=True, capture_output=True, check=True)

    hook("SessionStart", model="fixture-model")
    server = json.loads(Path(option("--mcp-config")).read_text())["mcpServers"]["agentscient_dev"]
    process = await asyncio.create_subprocess_exec(
        server["command"],
        *server["args"],
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def reject(method, params):
        raise ValueError("No client capability")

    tasks = set()

    async def receive(params):
        text = params["content"]
        ident = int(re.search(r"Live message #(\d+)", text)[1])
        with transcript.open("a") as stream:
            stream.write(json.dumps({"type": "user", "message": {"content": text}}) + "\n")
            stream.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "id": f"reply-{ident}",
                            "model": "fixture-model",
                            "content": "Received live direction",
                            "usage": {"input_tokens": 23},
                        },
                    }
                )
                + "\n"
            )
        arguments = {"text": f"Received message {ident}", "responding_to": f"message:{ident}"}
        hook("PreToolUse", tool_name="mcp__agentscient_dev__work_report", tool_input=arguments)
        result = await rpc.request("tools/call", {"name": "work_report", "arguments": arguments})
        hook("PostToolUse", tool_name="mcp__agentscient_dev__work_report", tool_response=result)

    async def notification(method, params):
        if method == "notifications/claude/channel":
            task = asyncio.create_task(receive(params))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    rpc = RPC(process, reject, notification)
    await rpc.request(
        "initialize",
        {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "claude-fixture", "version": "1"}},
    )
    await rpc.notify("notifications/initialized")
    Path(option("--debug-file")).write_text(
        '2026-09-28T00:00:00.000Z [DEBUG] MCP server "agentscient_dev": Channel notifications registered\n'
    )
    await rpc.dead.wait()


if __name__ == "__main__":
    asyncio.run(main())
