"""Exercise the protocol fixture's tool contract even when tmux is unavailable."""

import unittest
from unittest.mock import patch

import test_control
from native_fixture import Fixture

from devtools.api import API


class NativeFixtureTests(unittest.IsolatedAsyncioTestCase):
    setUp = test_control.ControlTests.setUp
    client = test_control.ControlTests.client

    async def test_current_xo_catalog_starts_the_native_fixture(self):
        fixture = Fixture()
        tools = API(self.state, "xo").tools()
        self.assertIn("conclude", {tool["name"] for tool in tools})
        with patch.object(fixture, "write") as output:
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
        with patch.object(fixture, "write") as output:
            await fixture.handle({"id": 2, "method": "thread/start", "params": {
                "sandbox": "read-only", "dynamicTools": tools,
            }})
        packet = output.call_args.args[0]
        self.assertEqual(2, packet["id"])
        self.assertNotIn("result", packet)
        self.assertEqual(-32603, packet["error"]["code"])


if __name__ == "__main__":
    unittest.main()
