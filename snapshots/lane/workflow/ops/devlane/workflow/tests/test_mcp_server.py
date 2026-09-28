"""The read-only MCP status server (PLAN §9).

Two promises, both asserted rather than assumed: that a read cannot write,
and that what it serves is the surface the CLI serves.
"""

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK

SERVER = support.WF_DIR / "mcp_server.py"


def rpc(*requests):
    return "\n".join(r if isinstance(r, str) else json.dumps(r)
                     for r in requests) + "\n"


class ServerCase(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.seed_project()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "mcp",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.sb.wf("red", "WO-001", "--", *support.Sandbox.GATE_ARGV, check=EXIT_OK)

    def talk(self, *requests):
        proc = subprocess.run(
            [sys.executable, str(SERVER), "--root", str(self.sb.root)],
            input=rpc(*requests), capture_output=True, text=True,
            cwd=str(self.sb.dir),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(l) for l in proc.stdout.strip().splitlines() if l.strip()]

    def read(self, uri, request_id=1):
        [reply] = self.talk({"jsonrpc": "2.0", "id": request_id,
                             "method": "resources/read", "params": {"uri": uri}})
        return reply


class Protocol(ServerCase):
    def test_initialize_announces_resources(self):
        [reply] = self.talk({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {}})
        self.assertIn("protocolVersion", reply["result"])
        self.assertIn("resources", reply["result"]["capabilities"])
        self.assertEqual(reply["result"]["serverInfo"]["name"], "wf-status")

    def test_resources_list_includes_the_work_order(self):
        [reply] = self.talk({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})
        uris = {r["uri"] for r in reply["result"]["resources"]}
        for expected in ("wf://status", "wf://next", "wf://agents", "wf://checks",
                         "wf://log/WO-001", "wf://status/WO-001"):
            self.assertIn(expected, uris)

    def test_a_notification_gets_no_reply(self):
        replies = self.talk({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(replies, [])

    def test_malformed_json_is_an_error_object_not_a_crash(self):
        [reply] = self.talk("{not json")
        self.assertEqual(reply["error"]["code"], -32700)

    def test_one_bad_line_does_not_end_the_session(self):
        replies = self.talk("{not json",
                            {"jsonrpc": "2.0", "id": 2, "method": "ping"})
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[1]["result"], {})

    def test_an_unknown_method_is_minus_32601(self):
        [reply] = self.talk({"jsonrpc": "2.0", "id": 1, "method": "nope/nope"})
        self.assertEqual(reply["error"]["code"], -32601)

    def test_a_non_jsonrpc_object_is_invalid_request(self):
        [reply] = self.talk({"id": 1, "method": "ping"})
        self.assertEqual(reply["error"]["code"], -32600)

    def test_an_unknown_work_order_is_an_error_response(self):
        reply = self.read("wf://log/WO-404")
        self.assertEqual(reply["error"]["code"], -32602)
        self.assertIn("work order exists", reply["error"]["message"])

    def test_an_unknown_resource_is_an_error_response(self):
        for uri in ("wf://nope", "http://elsewhere", "wf://", "wf://log/a/b"):
            with self.subTest(uri=uri):
                self.assertIn("error", self.read(uri))


class SameSurfaceAsTheCli(ServerCase):
    """PLAN §9: "over the same --json surface"."""

    def body(self, uri):
        return self.read(uri)["result"]["contents"][0]["text"]

    def test_next_is_byte_identical(self):
        self.assertEqual(self.body("wf://next/WO-001"),
                         self.sb.wf("--json", "next", "WO-001", check=EXIT_OK)
                         .stdout.strip())

    def test_log_is_byte_identical(self):
        self.assertEqual(self.body("wf://log/WO-001"),
                         self.sb.wf("--json", "log", "WO-001", "--attempts",
                                    check=EXIT_OK).stdout.strip())

    def test_checks_is_byte_identical(self):
        self.assertEqual(self.body("wf://checks"),
                         self.sb.wf("--json", "status", "--checks", check=EXIT_OK)
                         .stdout.strip())

    def test_status_matches_the_cli_on_everything_that_is_recorded(self):
        # Not byte-identical, and honestly so: `sessions` is live presence, so
        # last_seen moves on every call — two consecutive CLI runs differ from
        # each other too. What is recorded must match exactly.
        mine = json.loads(self.body("wf://status"))
        theirs = json.loads(self.sb.wf("--json", "status", check=EXIT_OK).stdout)
        self.assertEqual(mine["work_orders"], theirs["work_orders"])
        self.assertEqual(sorted(mine), sorted(theirs))

    def test_every_body_is_canonical_json(self):
        for uri in ("wf://status", "wf://next", "wf://agents", "wf://checks",
                    "wf://status/WO-001", "wf://log/WO-001"):
            with self.subTest(uri=uri):
                text = self.body(uri)
                self.assertEqual(text, canonical.dumps(json.loads(text)))


class ReadOnlyByConstruction(unittest.TestCase):
    """A property of the import graph, not of the read path's luck."""

    FORBIDDEN = {"wf", "gitio", "receipts"}

    def tree(self):
        return ast.parse(SERVER.read_text(), filename=str(SERVER))

    def test_it_imports_no_module_that_can_write(self):
        imported = set()
        for node in ast.walk(self.tree()):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & self.FORBIDDEN, set(),
                         "the append layer must not be reachable from here")
        self.assertIn("query", imported, "it must use the query layer")

    def test_it_never_names_an_appending_call(self):
        source = SERVER.read_text()
        for forbidden in ("chain.append", "do_commit", "maybe_commit",
                          "insert_event", "upsert_state", "touch_session",
                          "migrate("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_context_hands_out_a_chain_that_cannot_append(self):
        # The strong form: not "it does not call append" but "there is no
        # append to call". A Chain carries one; the reader's does not.
        sys.path.insert(0, str(support.WF_DIR))
        import importlib

        mcp = importlib.import_module("mcp_server")
        import chain as chainmod

        self.assertTrue(hasattr(chainmod.Chain, "append"))
        self.assertFalse(hasattr(mcp.ReadOnlyChain, "append"),
                         "a reader's chain must not expose append")
        for method in ("project", "verify"):
            self.assertTrue(hasattr(mcp.ReadOnlyChain, method), method)

    def test_the_query_layer_itself_imports_nothing_that_writes(self):
        # If query could write, importing only query would prove nothing.
        layer = support.WF_DIR / "query.py"
        imported = set()
        for node in ast.walk(ast.parse(layer.read_text())):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & self.FORBIDDEN, set())


class OriginatesNothing(ServerCase):
    def snapshot(self):
        import hashlib

        state = {}
        for name in ("chains", "attempts", "objects"):
            root = self.sb.root / name
            state[name] = sorted(
                (p.relative_to(root).as_posix(),
                 hashlib.sha256(p.read_bytes()).hexdigest())
                for p in root.rglob("*") if p.is_file()) if root.exists() else []
        state["db"] = hashlib.sha256(self.sb.db.read_bytes()).hexdigest()
        state["head"] = self.sb.head()
        state["porcelain"] = self.sb._git("status", "--porcelain")
        import sqlite3

        conn = sqlite3.connect(str(self.sb.db))
        try:
            state["tables"] = {
                t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("events", "attempts", "sessions", "claims", "artifacts",
                          "work_orders", "wo_state")
            }
            state["sessions"] = conn.execute(
                "SELECT agent, last_seen FROM sessions ORDER BY agent").fetchall()
        finally:
            conn.close()
        return state

    def test_a_whole_session_of_reads_changes_nothing_at_all(self):
        before = self.snapshot()
        self.talk(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
            *[{"jsonrpc": "2.0", "id": 10 + i, "method": "resources/read",
               "params": {"uri": uri}}
              for i, uri in enumerate((
                  "wf://status", "wf://next", "wf://agents", "wf://checks",
                  "wf://status/WO-001", "wf://next/WO-001", "wf://log/WO-001"))],
        )
        after = self.snapshot()
        for key in before:
            self.assertEqual(before[key], after[key], f"a read changed {key}")

    def test_not_even_the_database_file_bytes(self):
        before = self.snapshot()["db"]
        self.read("wf://status")
        self.assertEqual(self.snapshot()["db"], before)

    def test_it_records_no_session_of_its_own(self):
        before = self.snapshot()["sessions"]
        self.read("wf://agents")
        self.assertEqual(self.snapshot()["sessions"], before,
                         "a reader must not appear as an active agent")


class ReadsRecordPresenceAndNothingElse(ServerCase):
    """What a read is allowed to write, made a decision rather than an accident.

    An independent audit of the Slice 3 test drafts pointed out that `wf log`
    and `wf agents` write a session row — a read that writes. That is the
    presence feature working (§9's per-agent visibility needs to know who is
    active, and only a command can tell it), but it had never been stated, so
    it was indistinguishable from a bug.

    The line is: a CLI read records presence and touches nothing else. The
    MCP server and --verify-only record nothing at all, because neither is a
    person working.
    """

    READER = "Reader <reader@example.invalid>"

    def sessions(self):
        import sqlite3

        conn = sqlite3.connect(str(self.sb.db))
        try:
            return sorted(conn.execute(
                "SELECT agent, last_seen FROM sessions").fetchall())
        finally:
            conn.close()

    def evidence(self):
        import hashlib

        state = {"head": self.sb.head(),
                 "porcelain": self.sb._git("status", "--porcelain")}
        for name in ("chains", "attempts", "objects"):
            root = self.sb.root / name
            state[name] = sorted(
                (p.relative_to(root).as_posix(),
                 hashlib.sha256(p.read_bytes()).hexdigest())
                for p in root.rglob("*") if p.is_file()) if root.exists() else []
        return state

    def test_a_cli_read_records_presence(self):
        before = self.sessions()
        self.sb.wf("log", "WO-001", agent=self.READER, check=EXIT_OK)
        after = self.sessions()
        self.assertNotIn(self.READER, [a for a, _ in before])
        self.assertIn(self.READER, [a for a, _ in after],
                      "presence is the feature; a read is activity")

    def test_and_touches_no_evidence_at_all(self):
        before = self.evidence()
        for argv in (["log", "WO-001"], ["status"], ["next"], ["agents"],
                     ["status", "--checks"]):
            self.sb.wf(*argv, agent=self.READER, check=EXIT_OK)
        self.assertEqual(self.evidence(), before,
                         "a read may record presence and nothing else")

    def test_the_mcp_reader_records_no_presence(self):
        before = self.sessions()
        self.read("wf://agents")
        self.read("wf://log/WO-001")
        self.assertEqual(self.sessions(), before,
                         "a server is not a person working")

    def test_verify_only_records_no_presence_either(self):
        before = self.sessions()
        self.sb.wf("check", "--verify-only", "vocabulary-wall",
                   agent="CI <ci@example.invalid>", check=EXIT_OK)
        self.assertEqual(self.sessions(), before)


class Tools(ServerCase):
    """Resources are MCP-native; tools are what clients actually surface.

    A status server nobody can reach is not a status server, so the same
    query layer is offered both ways — and every tool is a read.
    """

    def call(self, name, arguments=None, request_id=1):
        [reply] = self.talk({"jsonrpc": "2.0", "id": request_id,
                             "method": "tools/call",
                             "params": {"name": name,
                                        "arguments": arguments or {}}})
        return reply

    def text(self, name, arguments=None):
        return self.call(name, arguments)["result"]["content"][0]["text"]

    def test_the_server_announces_tools(self):
        [reply] = self.talk({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {}})
        self.assertIn("tools", reply["result"]["capabilities"])

    def test_every_tool_is_listed_with_a_schema(self):
        [reply] = self.talk({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = reply["result"]["tools"]
        self.assertEqual({t["name"] for t in tools},
                         {"wf_status", "wf_next", "wf_log", "wf_agents",
                          "wf_checks"})
        for tool in tools:
            with self.subTest(tool=tool["name"]):
                self.assertTrue(tool["description"].strip())
                self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_no_tool_can_write(self):
        # The name of every tool, and the absence of any other, is the
        # guarantee. A writing tool would have to be added here to exist.
        [reply] = self.talk({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        for tool in reply["result"]["tools"]:
            for verb in ("open", "red", "green", "advance", "outcome", "claim",
                         "marker", "check", "commit", "release", "init"):
                self.assertNotEqual(tool["name"], f"wf_{verb}", tool["name"])

    def test_a_tool_answers_with_the_same_bytes_as_its_resource(self):
        for tool, uri in (("wf_next", "wf://next/WO-001"),
                          ("wf_checks", "wf://checks"),
                          ("wf_agents", "wf://agents")):
            with self.subTest(tool=tool):
                args = {"wo": "WO-001"} if tool == "wf_next" else {}
                self.assertEqual(
                    self.text(tool, args),
                    self.read(uri)["result"]["contents"][0]["text"],
                )

    def test_wf_log_filters_the_way_the_cli_does(self):
        body = json.loads(self.text("wf_log", {"wo": "WO-001",
                                               "type": ["receipt.red"]}))
        self.assertEqual(body["matched"], 1)
        self.assertGreater(body["considered"], 1)

    def test_a_refusal_comes_back_as_a_result_not_a_transport_error(self):
        # The model should see "no such work order" as an answer it can act
        # on, not as the tool call having failed to happen.
        reply = self.call("wf_log", {"wo": "WO-404"})
        self.assertNotIn("error", reply)
        self.assertTrue(reply["result"]["isError"])
        self.assertIn("work order exists", reply["result"]["content"][0]["text"])

    def test_a_successful_call_is_not_flagged_as_an_error(self):
        self.assertFalse(self.call("wf_checks")["result"]["isError"])

    def test_an_unknown_tool_is_an_error_response(self):
        reply = self.call("wf_delete_everything")
        self.assertEqual(reply["error"]["code"], -32602)
        self.assertIn("unknown tool", reply["error"]["message"])

    def test_a_missing_required_argument_is_reported(self):
        self.assertEqual(self.call("wf_log", {})["error"]["code"], -32602)

    def test_a_wrongly_typed_argument_is_reported(self):
        self.assertEqual(
            self.call("wf_log", {"wo": "WO-001", "n": "two"})["error"]["code"],
            -32602)

    def test_calling_every_tool_changes_nothing(self):
        before = OriginatesNothing.snapshot(self)
        for name, args in (("wf_status", {}), ("wf_status", {"wo": "WO-001"}),
                           ("wf_next", {}), ("wf_log", {"wo": "WO-001"}),
                           ("wf_agents", {}), ("wf_checks", {})):
            self.call(name, args)
        self.assertEqual(OriginatesNothing.snapshot(self), before)


class ProjectRegistration(unittest.TestCase):
    """The server has to be reachable, or none of the above matters."""

    CONFIG = support.WF_DIR.parent.parent.parent / ".mcp.json"

    def test_the_repo_registers_the_server(self):
        self.assertTrue(self.CONFIG.exists(), "no .mcp.json at the repo root")
        config = json.loads(self.CONFIG.read_text())
        self.assertIn("wf", config["mcpServers"])

    def test_the_registered_command_is_the_launcher_that_exists(self):
        config = json.loads(self.CONFIG.read_text())["mcpServers"]["wf"]
        script = self.CONFIG.parent / config["args"][0]
        self.assertTrue(script.exists(), f"{script} is registered but missing")
        self.assertEqual(script.resolve(),
                         (support.WF_DIR / "mcp_launch.py").resolve())

    def test_the_registered_root_is_the_state_root(self):
        config = json.loads(self.CONFIG.read_text())["mcpServers"]["wf"]
        args = config["args"]
        root = (self.CONFIG.parent / args[args.index("--root") + 1]).resolve()
        self.assertEqual(root, support.WF_DIR.resolve())
        self.assertTrue((root / "gate-kinds").is_dir())

    def test_the_registered_command_actually_starts(self):
        config = json.loads(self.CONFIG.read_text())["mcpServers"]["wf"]
        proc = subprocess.run(
            [config["command"], *config["args"]],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n",
            capture_output=True, text=True, cwd=str(self.CONFIG.parent),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        reply = json.loads(proc.stdout.strip().splitlines()[0])
        self.assertEqual(len(reply["result"]["tools"]), 5)



class AFreshCloneWorks(unittest.TestCase):
    """The failure that kept it from being used at all.

    wf.db is a gitignored cache — the tracked export is the evidence (D1) —
    so a clone has no database. The server opened one read-write, which
    CREATED an empty file, and every tool then answered
    `OperationalError: no such table: work_orders`. Two defects in one: dead
    on arrival, and a read that originated state.
    """

    def clone(self):
        import shutil
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="wf-clone-"))
        self.addCleanup(shutil.rmtree, root, True)
        repo = support.WF_DIR.parent.parent.parent
        shutil.copytree(repo / "ops", root / "ops",
                        ignore=shutil.ignore_patterns("wf.db", "__pycache__"))
        shutil.copy(repo / ".mcp.json", root / ".mcp.json")
        self.assertFalse((root / "ops/devlane/workflow/wf.db").exists())
        return root

    def talk(self, root, script, *requests):
        proc = subprocess.run(
            [sys.executable, str(root / "ops/devlane/workflow" / script),
             "--root", str(root / "ops/devlane/workflow")],
            input="".join(json.dumps(r) + "\n" for r in requests),
            capture_output=True, text=True, cwd=str(root),
        )
        return [json.loads(l) for l in proc.stdout.strip().splitlines() if l.strip()]

    def test_the_bare_server_refuses_with_the_command_to_run(self):
        root = self.clone()
        [reply] = self.talk(root, "mcp_server.py",
                            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "wf_status", "arguments": {}}})
        self.assertNotIn("error", reply, "not an internal error")
        self.assertTrue(reply["result"]["isError"])
        text = reply["result"]["content"][0]["text"]
        self.assertIn("init --rebuild", text, "it must say what to run")
        self.assertNotIn("no such table", text)

    def test_reading_creates_no_database(self):
        root = self.clone()
        self.talk(root, "mcp_server.py",
                  {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "wf_status", "arguments": {}}})
        self.assertFalse((root / "ops/devlane/workflow/wf.db").exists(),
                         "a read must not create the cache it reads")

    def test_the_registry_answers_without_a_database(self):
        root = self.clone()
        [reply] = self.talk(root, "mcp_server.py",
                            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "wf_checks", "arguments": {}}})
        self.assertFalse(reply["result"]["isError"],
                         "the registry is tracked files, not a database")

    def test_tools_list_answers_without_a_database(self):
        root = self.clone()
        [reply] = self.talk(root, "mcp_server.py",
                            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(len(reply["result"]["tools"]), 5)

    def test_the_launcher_makes_a_fresh_clone_work_with_no_manual_step(self):
        root = self.clone()
        [reply] = self.talk(root, "mcp_launch.py",
                            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "wf_status", "arguments": {}}})
        self.assertFalse(reply["result"]["isError"],
                         reply["result"]["content"][0]["text"][:200])
        body = json.loads(reply["result"]["content"][0]["text"])
        self.assertEqual(body["work_orders"], [])

    def test_only_the_launcher_can_write(self):
        # The separation is the whole design: the launcher rebuilds the
        # cache, then execs the server, which cannot.
        launcher = (support.WF_DIR / "mcp_launch.py").read_text()
        self.assertIn("os.execv", launcher)
        self.assertIn("init", launcher)
        # The server may *name* the command — that is the whole point of the
        # refusal — but it must not be able to run one.
        server = SERVER.read_text()
        self.assertIn("init --rebuild", server, "it must say what to run")
        self.assertNotIn("subprocess", server, "a reader spawns nothing")
        self.assertNotIn("os.execv", server)


class AgentsAreToldTheToolsExist(unittest.TestCase):
    """The last thing keeping it from being used.

    A registered server a model has no reason to call is not much better than
    an unregistered one. AGENTS.md is what every agent reads first, so the
    tools have to be named there — and named accurately, which is what this
    checks.
    """

    AGENTS = support.WF_DIR.parent.parent.parent / "AGENTS.md"

    def test_every_tool_the_server_offers_is_documented(self):
        text = self.AGENTS.read_text()
        sys.path.insert(0, str(support.WF_DIR))
        import importlib

        mcp = importlib.import_module("mcp_server")
        for tool in mcp.TOOLS:
            with self.subTest(tool=tool["name"]):
                self.assertIn(tool["name"], text,
                              f"{tool['name']} is offered but never mentioned")

    def test_no_tool_is_documented_that_does_not_exist(self):
        import importlib
        import re

        sys.path.insert(0, str(support.WF_DIR))
        mcp = importlib.import_module("mcp_server")
        offered = {t["name"] for t in mcp.TOOLS}
        mentioned = set(re.findall(r"\bwf_[a-z_]+\b", self.AGENTS.read_text()))
        self.assertEqual(mentioned - offered, set(),
                         "AGENTS.md promises a tool the server does not have")

    def test_the_cli_fallback_is_named(self):
        text = self.AGENTS.read_text()
        self.assertIn("wf.py", text, "an agent needs the fallback when the "
                                     "server is unavailable")
        self.assertIn("init --rebuild", text)


class LaunchingPreservesCoordination(SandboxCase):
    """[P1 Codex] Starting a reader must not free work another agent holds.

    mcp_launch ran `init --rebuild` unconditionally. rebuild() unlinks wf.db,
    and claims and sessions are deliberately absent from the export (PLAN §8),
    so merely starting the registered MCP server destroyed live coordination
    state. Reproduced: a two-hour claim was null after one launch.

    Losing coordination on a rebuild is correct when somebody asks for a
    rebuild. It is not correct as a consequence of opening a status server.
    """

    def launch(self):
        return subprocess.run(
            [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
             "--root", str(self.sb.root)],
            input="", capture_output=True, text=True, cwd=str(self.sb.dir))

    def claim(self):
        return json.loads(
            self.sb.wf("--json", "status", "WO-001", check=EXIT_OK).stdout)["claim"]

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)

    def test_a_live_claim_survives_a_launch(self):
        self.sb.wf("claim", "WO-001", "--ttl", "2h", check=EXIT_OK)
        before = self.claim()
        self.assertIsNotNone(before)
        self.launch()
        after = self.claim()
        self.assertIsNotNone(after, "the launcher freed claimed work")
        self.assertEqual(after["agent"], before["agent"])
        self.assertEqual(after["expires_at"], before["expires_at"])

    def test_it_survives_repeated_launches(self):
        self.sb.wf("claim", "WO-001", "--ttl", "2h", check=EXIT_OK)
        for _ in range(3):
            self.launch()
        self.assertIsNotNone(self.claim())

    def test_the_chain_is_untouched_by_a_launch(self):
        before = self.sb.chain_file("WO-001").read_bytes()
        self.launch()
        self.assertEqual(self.sb.chain_file("WO-001").read_bytes(), before)

    def test_it_still_rebuilds_when_there_is_no_cache(self):
        # The whole reason the launcher exists — this must not regress while
        # fixing the claim destruction.
        self.sb.db.unlink()
        proc = subprocess.run(
            [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
             "--root", str(self.sb.root)],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "wf_status",
                                         "arguments": {}}}) + "\n",
            capture_output=True, text=True, cwd=str(self.sb.dir))
        reply = json.loads(proc.stdout.strip().splitlines()[0])
        self.assertFalse(reply["result"]["isError"], proc.stderr[:300])
        self.assertIn("WO-001", reply["result"]["content"][0]["text"])

    def test_it_rebuilds_when_the_cache_has_no_schema(self):
        self.sb.db.write_bytes(b"")
        proc = subprocess.run(
            [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
             "--root", str(self.sb.root)],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "wf_status",
                                         "arguments": {}}}) + "\n",
            capture_output=True, text=True, cwd=str(self.sb.dir))
        reply = json.loads(proc.stdout.strip().splitlines()[0])
        self.assertFalse(reply["result"]["isError"], proc.stderr[:300])


class TheReadOnlyUriIsEncoded(unittest.TestCase):
    """[P2 Codex] A '?' in the checkout path made read-only mode create a file.

    Interpolating the path into `file:{path}?mode=ro` let SQLite parse a '?'
    or '#' inside the path as URI syntax: a checkout under `a?b/` opened `a`
    instead, creating a writable zero-byte file and reporting the real
    database as schema-less. The mode added to stop a read creating state was
    creating it.
    """

    def setUp(self):
        import shutil
        import tempfile

        self.base = Path(tempfile.mkdtemp(prefix="wf-uri-"))
        self.addCleanup(shutil.rmtree, self.base, True)

    def build(self, dirname):
        sys.path.insert(0, str(support.WF_DIR))
        import store as storemod

        weird = self.base / dirname
        weird.mkdir()
        db = weird / "wf.db"
        conn = __import__("sqlite3").connect(str(db))
        conn.execute("CREATE TABLE work_orders (wo_id TEXT)")
        conn.commit()
        conn.close()
        return storemod, db

    def test_a_question_mark_in_the_path_creates_no_stray_file(self):
        storemod, db = self.build("a?b")
        st = storemod.Store(db, read_only=True)
        self.addCleanup(st.close)
        self.assertFalse((self.base / "a").exists(),
                         "a read-only open created a writable sibling")

    def test_and_the_real_database_is_the_one_opened(self):
        storemod, db = self.build("q?x")
        st = storemod.Store(db, read_only=True)
        self.addCleanup(st.close)
        self.assertIsNotNone(
            st.one("SELECT name FROM sqlite_master WHERE name='work_orders'"),
            "the real database must be the one that was opened")

    def test_a_hash_in_the_path_works_too(self):
        storemod, db = self.build("h#s")
        st = storemod.Store(db, read_only=True)
        self.addCleanup(st.close)
        self.assertIsNotNone(
            st.one("SELECT name FROM sqlite_master WHERE name='work_orders'"))

    def test_read_only_still_refuses_a_write(self):
        storemod, db = self.build("plain")
        st = storemod.Store(db, read_only=True)
        self.addCleanup(st.close)
        import sqlite3

        with self.assertRaises(sqlite3.OperationalError):
            st.q("INSERT INTO work_orders (wo_id) VALUES ('X')")


class ConcurrentLaunchesDoNotDestroyTheCache(SandboxCase):
    """[P1 Codex] Two launchers could both rebuild, over each other.

    `init --rebuild` unlinks the database. Both could pass the cache check and
    then destroy each other's work: 24 simultaneous launchers against a
    tracked work order lost it in 3 runs out of 3, and the schema-only cache
    left behind was then *accepted* by the next launch — so the work order
    stayed hidden permanently.
    """

    LAUNCHERS = 24

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "race",
                   check=EXIT_OK)
        self.sb.wf("export", check=EXIT_OK)

    def work_order_rows(self):
        import sqlite3

        conn = sqlite3.connect(str(self.sb.db))
        try:
            return conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        except Exception:
            return -1
        finally:
            conn.close()

    def storm(self):
        import threading

        barrier = threading.Barrier(self.LAUNCHERS)

        def go():
            barrier.wait()
            subprocess.run(
                [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
                 "--root", str(self.sb.root)],
                input="", capture_output=True, text=True, cwd=str(self.sb.dir))

        threads = [threading.Thread(target=go) for _ in range(self.LAUNCHERS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_a_storm_of_launchers_leaves_the_work_order_intact(self):
        self.sb.db.unlink()
        self.storm()
        self.assertEqual(self.work_order_rows(), 1,
                         "concurrent rebuilds destroyed the cache")

    def test_and_the_server_can_still_see_it(self):
        self.sb.db.unlink()
        self.storm()
        proc = subprocess.run(
            [sys.executable, str(support.WF_DIR / "mcp_server.py"),
             "--root", str(self.sb.root)],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "wf_status",
                                         "arguments": {}}}) + "\n",
            capture_output=True, text=True, cwd=str(self.sb.dir))
        reply = json.loads(proc.stdout.strip().splitlines()[0])["result"]
        self.assertFalse(reply["isError"], proc.stderr[:200])
        body = json.loads(reply["content"][0]["text"])
        self.assertEqual([w["wo"] for w in body["work_orders"]], ["WO-001"])

    def test_the_lock_file_does_not_dirty_the_tree(self):
        self.sb.db.unlink()
        self.storm()
        self.assertNotIn("wf.db.lock", self.sb._git("status", "--porcelain"),
                         "the lock must be gitignored")


class ASchemaOnlyCacheIsNotUsable(SandboxCase):
    """The half of that finding that needs no concurrency at all.

    An interrupted rebuild leaves a database with tables and no rows. Judging
    a cache by its schema alone accepted that, and every recorded work order
    stayed invisible — the next launch saw a schema and left it alone.
    """

    def build(self, with_rows: bool):
        import sqlite3

        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "x",
                   check=EXIT_OK)
        self.sb.wf("export", check=EXIT_OK)
        self.sb.db.unlink()
        chain = (self.sb.root / "chains" / "WO-001.jsonl").read_bytes()
        lines = [l for l in chain.split(b"\n") if l.strip()]
        conn = sqlite3.connect(str(self.sb.db))
        conn.execute("CREATE TABLE work_orders (wo_id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE events (wo_id TEXT, seq INTEGER, hash TEXT)")
        if with_rows:
            conn.execute("INSERT INTO work_orders VALUES ('WO-001')")
            # The export's own events, hashes included: "accounts for the
            # export" means content now, not counts — a cache behind,
            # ahead of, or divergent from the export is not this cache.
            conn.executemany(
                "INSERT INTO events VALUES ('WO-001', ?, ?)",
                [(i + 1, json.loads(l)["hash"]) for i, l in enumerate(lines)])
        conn.commit()
        conn.close()

    def launcher(self):
        sys.path.insert(0, str(support.WF_DIR))
        import importlib

        module = importlib.import_module("mcp_launch")
        importlib.reload(module)
        return module

    def test_a_cache_that_does_not_account_for_the_export_is_rejected(self):
        self.build(with_rows=False)
        self.assertFalse(self.launcher().usable_cache(self.sb.db))

    def test_one_that_does_is_accepted(self):
        self.build(with_rows=True)
        self.assertTrue(self.launcher().usable_cache(self.sb.db))

    def test_the_launcher_heals_it(self):
        self.build(with_rows=False)
        proc = subprocess.run(
            [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
             "--root", str(self.sb.root)],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "wf_status",
                                         "arguments": {}}}) + "\n",
            capture_output=True, text=True, cwd=str(self.sb.dir))
        reply = json.loads(proc.stdout.strip().splitlines()[0])["result"]
        body = json.loads(reply["content"][0]["text"])
        self.assertEqual([w["wo"] for w in body["work_orders"]], ["WO-001"],
                         "a poisoned cache must not stay poisoned")


class AFailedRebuildRefusesService(SandboxCase):
    """[P1 Codex] A rebuild that failed partway must not serve what it built.

    With a valid chain and a malformed attempts export, the launcher's
    rebuild exited with an integrity error — and then served anyway. The
    partial database already held the work order row, so `wf_status`
    answered `isError: false` with the broken attempt history silently
    omitted, and the leftover passed `usable_cache()`, so every later
    launch trusted it too. Reproduced 4-for-4 before the fix.
    """

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "partial",
                   check=EXIT_OK)
        self.sb.wf("export", check=EXIT_OK)
        support.plant_bytes(
            self.sb.root / "attempts" / "WO-001.jsonl",
            lambda raw: raw + b"this is not canonical json\n",
            expect="grow",
            recognisable=lambda raw: raw.startswith(b"{"),
        )
        self.sb.db.unlink()

    def launch_status(self):
        proc = subprocess.run(
            [sys.executable, str(support.WF_DIR / "mcp_launch.py"),
             "--root", str(self.sb.root)],
            input=rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "wf_status", "arguments": {}}}),
            capture_output=True, text=True, cwd=str(self.sb.dir))
        return proc, json.loads(proc.stdout.strip().splitlines()[0])

    def test_a_failed_rebuild_refuses_instead_of_serving_partial_evidence(self):
        proc, reply = self.launch_status()
        self.assertIn("init --rebuild exited", proc.stderr,
                      "the fixture must actually fail the rebuild")
        self.assertTrue(reply["result"]["isError"],
                        "a failed rebuild served partial evidence as success")
        self.assertIn("init --rebuild", reply["result"]["content"][0]["text"],
                      "it must say what to run")

    def test_a_failed_rebuild_leaves_nothing_a_later_launch_trusts(self):
        self.launch_status()
        import importlib
        sys.path.insert(0, str(support.WF_DIR))
        launch = importlib.import_module("mcp_launch")
        self.assertFalse(launch.usable_cache(self.sb.db),
                         "the leftover passes for a finished cache")

    def test_a_schema_only_cache_refuses_queries_on_the_server_too(self):
        # Belt to the launcher's braces: nothing forces the server to be
        # started through the launcher, so a schema-only leftover beside a
        # populated export must refuse on the server as well.
        import store as storemod
        st = storemod.Store(self.sb.db)
        st.migrate(support.WF_DIR / "migrations", canonical.now())
        st.close()
        proc = subprocess.run(
            [sys.executable, str(SERVER), "--root", str(self.sb.root)],
            input=rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "wf_status", "arguments": {}}}),
            capture_output=True, text=True, cwd=str(self.sb.dir))
        reply = json.loads(proc.stdout.strip().splitlines()[0])
        self.assertTrue(reply["result"]["isError"],
                        "a schema with no rows served an empty world as truth")
        self.assertIn("init --rebuild", reply["result"]["content"][0]["text"])

class TheDocumentedHappyPathWorks(SandboxCase):
    """AGENTS.md tells agents to run `advances` verbatim. It has to be true.

    It was not: `advances` emitted ["wf", …] and no such binary exists, so an
    agent following the documentation got `wf: command not found`. Then, once
    past that, a refusal for a missing identity — and WF_AGENT appeared zero
    times in AGENTS.md. Two refusals on the documented happy path, on the verb
    the docs say to reach for first.
    """

    def test_following_next_verbatim_advances_the_work_order(self):
        import os

        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o",
                   check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "next", "WO-001",
                                     check=EXIT_OK).stdout)
        support.assert_runnable(self, body["advances"])
        self.assertTrue(body["requires_agent"])
        proc = subprocess.run(
            body["advances"] + ["--root", str(self.sb.root)],
            cwd=str(self.sb.dir), capture_output=True, text=True,
            env=dict(os.environ, WF_AGENT=support.Sandbox.AGENT),
        )
        self.assertEqual(proc.returncode, EXIT_OK, proc.stderr)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "status", "WO-001").stdout)["stage"],
            "red", "the command the docs promised must actually advance it")
