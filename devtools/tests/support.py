import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "run.py"


class Client:
    """A real stdio MCP client, including concurrent requests and notifications."""

    def __init__(self, directory, member, channel=False, env=None):
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(ENTRY),
                "mcp",
                "--state",
                str(directory),
                "--member",
                member,
                *(["--channel"] if channel else []),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.condition = threading.Condition()
        self.responses, self.notifications = {}, []
        self.ident = 0
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()
        self.call(
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        )
        self.write({"method": "notifications/initialized"})

    def read(self):
        for line in self.process.stdout:
            packet = json.loads(line)
            with self.condition:
                if "id" in packet:
                    self.responses[packet["id"]] = packet
                else:
                    self.notifications.append(packet)
                self.condition.notify_all()

    def write(self, packet):
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", **packet}) + "\n")
        self.process.stdin.flush()

    def begin(self, method, params=None):
        self.ident += 1
        self.write({"id": self.ident, "method": method, "params": params or {}})
        return self.ident

    def finish(self, ident, timeout=5):
        with self.condition:
            if not self.condition.wait_for(lambda: ident in self.responses, timeout):
                raise TimeoutError(f"MCP response {ident} missing (process={self.process.poll()})")
            packet = self.responses.pop(ident)
        if "error" in packet:
            raise ValueError(packet["error"])
        return packet["result"]

    def call(self, method, params=None):
        return self.finish(self.begin(method, params))

    def tool(self, name, arguments):
        result = self.call("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise ValueError(result["content"][0]["text"])
        return json.loads(result["content"][0]["text"])

    def invoke(self, capability, **arguments):
        return self.tool("capability_invoke", {"capability": capability, "arguments": arguments})

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=3)
        self.reader.join(timeout=2)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


def until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("Expected observation did not arrive before timeout")
