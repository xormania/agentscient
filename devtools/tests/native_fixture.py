#!/usr/bin/env python3
"""Protocol fixture, NOT a native-model acceptance run.

Holds a tool call open while accepting another live message. Grok's fixture
uses a real child MCP server; Codex calls the launcher's real MCP proxy.
"""

import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from devtools.rpc import RPC


class Fixture:
    def __init__(self):
        self.harness = "codex" if "app-server" in sys.argv else "grok"
        self.pending = {}
        self.count = 0
        self.session = "fixture-native-" + uuid.uuid4().hex
        self.mcp = None
        self.tasks = set()
        self.command = False
        self.organized = False
        self.onboarded = False

    def write(self, packet):
        print(json.dumps(packet), flush=True)

    async def request(self, method, params):
        self.count += 1
        ident = "fixture-" + str(self.count)
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        self.write({"id": ident, "method": method, "params": params})
        try:
            return await future
        finally:
            self.pending.pop(ident, None)

    async def ignore(self, method, params):
        return {}

    async def tool(self, capability, arguments):
        args = arguments
        if self.harness == "codex":
            result = await self.request(
                "item/tool/call",
                {
                    "threadId": self.session,
                    "tool": capability,
                    "arguments": args,
                    "callId": f"call-{self.count}",
                },
            )
            if not result["success"]:
                raise ValueError(result)
            return json.loads(result["contentItems"][0]["text"])
        result = await self.mcp.request("tools/call", {"name": capability, "arguments": args})
        if result.get("isError"):
            raise ValueError(result)
        return json.loads(result["content"][0]["text"])

    async def accept(self, text, hold):
        if not self.onboarded:
            onboard = await self.tool("onboard", {})
            self.role = onboard["role"]
            self.planned = bool(onboard["context"]["plan_revision"])
            await self.tool("skill_read", {"name": "agentscient-" + self.role.replace("_", "-")})
            self.onboarded = True
        ident = int(re.search(r"Live message #(\d+)", text)[1])
        if self.role == "planner":
            await self.tool("work_report", {"kind": "result", "text": "Fixture plan ready", "evidence": {
                "name": "fixture-plan.md", "content": "One job: demonstrate the live command path using a coder."}})
            return
        if self.command and "result: Fixture plan ready" in text and not self.planned:
            reference = re.search(r"Reference: (update:\d+)", text)[1]
            await self.tool("plan_adopt", {"plan": reference, "jobs": [{"name": "Fixture implementation",
                "objective": "Demonstrate the live command path", "done_when": "Direction received", "constraints": "Protocol fixture only"}]})
            self.planned = True
            # The planner's native process is stopped asynchronously before its
            # fixed slot can be reused by the implementation role.
            for attempt in range(100):
                try:
                    await self.tool("orchestrate", {"work": [{"name": "Fixture implementation", "role": "coder"}]})
                    return
                except ValueError as error:
                    if "No available" not in str(error):
                        raise
                    await asyncio.sleep(0.05)
            raise AssertionError("Planner slot did not become reusable")
        if self.harness == "codex":
            self.write({"method": "turn/started", "params": {"threadId": self.session, "turn": {"id": "held-turn"}}})
            self.write(
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "threadId": self.session,
                        "tokenUsage": {"last": {"inputTokens": 23, "outputTokens": 7}},
                    },
                }
            )
        else:
            self.write(
                {
                    "method": "session/update",
                    "params": {
                        "sessionId": self.session,
                        "update": {"sessionUpdate": "agent_message_chunk", "content": {"text": ""}},
                    },
                }
            )
        if self.command and "progress: Received message" in text:
            await self.tool("work_report", {"text": "Collaborator receipt observed"})
            return
        await self.tool("work_report", {"text": f"Received message {ident}", "responding_to": f"message:{ident}"})
        if self.command and not self.organized and "control-plane direction" in text:
            self.organized = True
            await self.tool(
                "orchestrate",
                {
                    "work": [
                        {
                            "name": "Fixture implementation" if self.planned else "Fixture planning",
                            "role": "coder" if self.planned else "planner",
                            "objective": "Demonstrate the live command path",
                            "done_when": "Direction received",
                            "constraints": "Protocol fixture only",
                        }
                    ]
                },
            )
        if hold:
            # The native turn remains unfinished while a second message is handled.
            await asyncio.sleep(10)

    def background(self, awaitable):
        task = asyncio.create_task(awaitable)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def handle(self, packet):
        method, params = packet["method"], packet.get("params", {})
        try:
            if method == "initialize":
                result = {"protocolVersion": 1, "authMethods": []}
            elif method == "thread/start":
                assert params["sandbox"] == "read-only"
                names = {row["name"] for row in params["dynamicTools"]}
                self.command = "orchestrate" in names
                expected = {"work_context", "work_report", "guidance_request", "onboard", "skill_read"}
                assert names == expected | ({"plan_adopt", "orchestrate", "monitor", "steer"} if self.command else set())
                result = {"thread": {"id": self.session}, "model": "fixture-model", "reasoningEffort": "high"}
            elif method == "session/new":
                server = params["mcpServers"][0]
                process = await asyncio.create_subprocess_exec(
                    server["command"],
                    *server["args"],
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self.mcp = RPC(process, self.ignore, self.ignore)
                await self.mcp.request(
                    "initialize",
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "fixture", "version": "1"},
                    },
                )
                await self.mcp.notify("notifications/initialized")
                catalogue = (await self.mcp.request("tools/list", {}))["tools"]
                self.command = "orchestrate" in {row["name"] for row in catalogue}
                result = {"sessionId": self.session, "models": {"currentModelId": "fixture-model"}}
            elif method == "turn/start":
                assert params["threadId"] == self.session
                assert params["input"] == []
                self.background(self.accept(params["toolOutput"]["output"], hold=True))
                result = {"turn": {"id": "held-turn"}}
            elif method == "session/prompt":
                assert params["sessionId"] == self.session
                await self.accept(params["prompt"][0]["text"], hold=True)
                result = {"stopReason": "end_turn"}
            elif method == "_x.ai/interject":
                assert params["sessionId"] == self.session
                await self.accept(params["text"], hold=False)
                result = {"accepted": True}
            else:
                raise ValueError("Unsupported fixture method " + method)
            self.write({"id": packet["id"], "result": result})
        except Exception as error:
            self.write({"id": packet["id"], "error": {"code": -32603, "message": str(error)}})

    async def run(self):
        reader = asyncio.StreamReader()
        await asyncio.get_running_loop().connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
        try:
            while line := await reader.readline():
                packet = json.loads(line)
                if "method" in packet and "id" in packet:
                    self.background(self.handle(packet))
                elif "method" not in packet and packet.get("id") in self.pending:
                    future = self.pending[packet["id"]]
                    if "error" in packet:
                        future.set_exception(ValueError(packet["error"]))
                    else:
                        future.set_result(packet["result"])
        finally:
            for task in list(self.tasks):
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            if self.mcp:
                await self.mcp.close()


if __name__ == "__main__":
    if "generate-json-schema" in sys.argv:
        if "--help" in sys.argv:
            print("--out <DIRECTORY> --experimental")
        else:
            output = Path(sys.argv[sys.argv.index("--out") + 1])
            (output / "TurnStartParams.json").write_text(
                json.dumps({"title": "TurnStartParams", "properties": {"input": {}, "threadId": {}, "toolOutput": {}}})
            )
    else:
        asyncio.run(Fixture().run())
