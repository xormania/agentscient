import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "run.py"


def runtime_policy():
    """Generic fallback fixture, independent of the maintained operator defaults."""
    from devtools.adapters import names
    from devtools.harnesses import get
    from devtools.role_packages import catalog

    return {
        "version": 1,
        "max_sessions": 12,
        "profiles": {name: {"harness": name, "vendor": get(name).vendor,
                            "model": None, "reasoning": None} for name in names("harness")},
        "roles": {role: list(package["runtime"]["harnesses"])
                  for role, package in catalog()["roles"].items()},
    }


def adopt_plan(xo, jobs):
    """Exercise the actual planner handoff while arranging a command fixture."""
    from devtools.api import API
    from devtools.role_packages import default_role

    revision = xo.call("work_context", {})["plan_revision"]
    selected = default_role("planner")
    assignment = {"name": f"Planning {revision + 1}", "role": selected, "objective": "Inspect and plan the requested jobs",
                  "done_when": "Job requirements and verification are defined", "constraints": "Planning only"}
    xo.call("orchestrate", {"work": [assignment]})
    with xo.store.connect() as db:
        member = db.execute("SELECT member FROM member_bindings WHERE role=? AND reports_to=?", (selected, xo.member)).fetchone()[0]
    planner = API(xo.store.directory, member)
    report = planner.call("work_report", {"kind": "result", "text": "Proposed job breakdown", "evidence": {
        "name": "plan.md", "content": json.dumps(jobs)}})
    adopted = xo.call("plan_adopt", {"plan": report["reference"], "jobs": jobs})
    return adopted, report


def fixture_work(coordinator, work):
    """Trusted existing work for provider/session tests, independent of planning."""
    from devtools.work import Work

    config = coordinator.commands._config()
    with coordinator.store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        scope = coordinator.control.current()
        for item in work:
            old = db.execute("SELECT * FROM jobs WHERE work_order=? AND title=?", (scope["work_order"], item["name"])).fetchone()
            job = old["id"] if old else Work(coordinator.store, coordinator.member).create_in(
                db, "jobs", title=item["name"], objective=item["objective"], done_when=item["done_when"],
                constraints=item["constraints"], work_order=scope["work_order"], select=False)["job"]["id"]
            prior = db.execute("SELECT * FROM member_bindings WHERE job=? AND role=?", (job, item["role"])).fetchone()
            slot = coordinator.commands._slot(db, config, existing=dict(prior) if prior else None, role=item["role"])
            coordinator.control.bind_in(db, slot["name"], item["role"], scope["work_order"], job, coordinator.member)


def require_process_identity():
    from devtools import processes

    try:
        processes.boot_id()
    except RuntimeError as error:
        if os.environ.get("AGENTSCIENT_REQUIRE_TMUX") == "1":
            raise
        raise unittest.SkipTest(str(error)) from error


class Client:
    """A real stdio MCP client, including concurrent requests and notifications."""

    def __init__(self, directory, member, channel=False, env=None, operator=False, provider="mcp", generation=None):
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(ENTRY),
                provider,
                "--state",
                str(directory),
                "--member",
                member,
                *(["--channel"] if channel else []),
                *(["--operator"] if operator else []),
                *(["--generation", generation] if generation else []),
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
        try:
            self.initialization = self.call(
                "initialize",
                {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
            )
        except Exception:
            self.close()
            raise
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


def held_check(directory):
    """A check that cannot complete until the test releases it after disconnect."""
    started, release = Path(directory) / "check-started", Path(directory) / "check-release"
    program = (
        "import sys, time\nfrom pathlib import Path\n"
        "Path(sys.argv[1]).touch()\n"
        "deadline = time.monotonic() + 15\n"
        "while not Path(sys.argv[2]).exists():\n"
        "    if time.monotonic() >= deadline: raise TimeoutError('Test did not release the check')\n"
        "    time.sleep(0.01)\n"
        "print('measured check completed')\n"
    )
    return [sys.executable, "-c", program, str(started), str(release)], started, release


def require_tmux():
    """CI must run real terminals; constrained local containers may explicitly skip."""
    binary = shutil.which("tmux")
    reason = "tmux is not installed"
    if binary:
        socket = "agentscient-test-" + uuid.uuid4().hex
        result = subprocess.run([binary, "-L", socket, "-f", "/dev/null", "new-session", "-d", "sleep 5"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            subprocess.run([binary, "-L", socket, "kill-server"], capture_output=True, timeout=10)
            return
        reason = result.stderr.strip()
    if os.environ.get("AGENTSCIENT_REQUIRE_TMUX") == "1":
        raise RuntimeError("Real tmux acceptance required: " + reason)
    raise unittest.SkipTest("Real tmux unavailable: " + reason)


@contextmanager
def terminal_team():
    """Always reap the actual fixture team's socket, including assertion failures."""
    from devtools import launch, terminals
    from devtools.store import Store

    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary) / "state"
        try:
            yield temporary
        finally:
            try:
                if (state / "live.sqlite3").exists():
                    for row in Store(state).members():
                        if row["harness"] != "external":
                            launch.stop(state, row["name"], grace=0)
            finally:
                terminals.command(state, "kill-server", check=False)


def retain_native(state, label):
    target = os.environ.get("AGENTSCIENT_EVIDENCE_DIR")
    if target:
        destination = Path(target) / label
        destination.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(state / "live.sqlite3") as source, sqlite3.connect(destination / "live.sqlite3") as copy:
            source.backup(copy)
        if (state / "telemetry").exists():
            shutil.copytree(state / "telemetry", destination / "telemetry", dirs_exist_ok=True)
        (destination / "interpretation.txt").write_text(
            "Real tmux and MCP; native protocol fixtures. Not authenticated vendor/model acceptance.\n"
        )
