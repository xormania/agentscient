"""Exercise the protocol fixture's tool contract even when tmux is unavailable."""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fixtures.control import ControlFixture
from native_fixture import Fixture

from devtools.api import API
from devtools.rpc import RPC


class NativeFixtureTests(unittest.IsolatedAsyncioTestCase):
    setUp = ControlFixture.setUp
    client = ControlFixture.client

    async def test_current_xo_catalog_starts_the_native_fixture(self):
        fixture = Fixture()
        tools = API(self.state, "xo").tools()
        self.assertIn("conclude", {tool["name"] for tool in tools})
        with patch.object(fixture, "write") as output, patch.object(fixture, "tool", new=AsyncMock(return_value=API(self.state, "xo").call("onboard", {}))):
            await fixture.handle({"id": 1, "method": "thread/start", "params": {
                "sandbox": "read-only", "dynamicTools": tools,
            }})
        packet = output.call_args.args[0]
        self.assertEqual(1, packet["id"])
        self.assertEqual(fixture.session, packet["result"]["thread"]["id"])
        self.assertTrue(fixture.command)

    async def test_native_fixture_rejects_an_unapproved_tool(self):
        fixture = Fixture()
        tools = [*API(self.state, "xo").tools(), {"name": "exec_command"}]
        with patch.object(fixture, "write") as output, patch.object(fixture, "tool", new=AsyncMock(return_value=API(self.state, "xo").call("onboard", {}))):
            await fixture.handle({"id": 2, "method": "thread/start", "params": {
                "sandbox": "read-only", "dynamicTools": tools,
            }})
        packet = output.call_args.args[0]
        self.assertEqual(2, packet["id"])
        self.assertNotIn("result", packet)
        self.assertEqual(-32603, packet["error"]["code"])

    async def test_native_fixture_rejects_a_missing_declared_mcp_tool(self):
        fixture = Fixture()
        api = API(self.state, "xo")
        tools = [tool for tool in api.tools() if tool["name"] != "plan_adopt"]
        with patch.object(fixture, "write") as output, patch.object(fixture, "tool", new=AsyncMock(return_value=api.call("onboard", {}))):
            await fixture.handle({"id": 3, "method": "thread/start", "params": {
                "sandbox": "read-only", "dynamicTools": tools,
            }})
        self.assertNotIn("result", output.call_args.args[0])

    async def test_subprocess_fixture_checks_mcp_surface_during_startup(self):
        api = API(self.state, "xo")
        requests = []

        async def proxy(method, params):
            requests.append((method, params["tool"]))
            self.assertEqual("item/tool/call", method)
            value = api.call(params["tool"], params["arguments"])
            return {"success": True, "contentItems": [{"text": json.dumps(value)}]}

        async def ignore(method, params):
            return None

        process = await asyncio.create_subprocess_exec(
            sys.executable, str(Path(__file__).with_name("native_fixture.py")), "app-server",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        rpc = RPC(process, proxy, ignore, jsonrpc=False)
        try:
            result = await rpc.request("thread/start", {"sandbox": "read-only", "dynamicTools": api.tools()}, timeout=10)
            self.assertTrue(result["thread"]["id"].startswith("fixture-native-"))
            self.assertEqual([("item/tool/call", "onboard")], requests)
        finally:
            await rpc.close()


if __name__ == "__main__":
    unittest.main()
