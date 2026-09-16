"""Acceptance tests for the acting coordination MCP server, from the contract.

Contract (only): `ops/conductor/coordination-mcp-lever.md`, with
`docs/wire.md` for the refusal shape and the counterparty contract
`ops/conductor/coordination-lever.md` at 537f3a35 for the core's verb
names and refusal classes. The subject
`ops/conductor/tools/coordination_mcp.py` is not read here.

The subject is invoked as a subprocess through its documented CLI:

    python3 -B coordination_mcp.py [--config FILE] check | serve | call TOOL [JSON]

MCP is exercised as UTF-8 newline-delimited JSON-RPC on that same CLI's
`serve` stdio. No live state store, no network, no credentials, no
harness call: World owns HOME, the XDG roots and TMPDIR, so the core's
own store can never be the host's.

This file was sealed at 333c200f and reopened at the Lead's disposition
of 2026-09-16, which accepted eleven review findings. What changed and
why is in the fix commit, finding by finding; the rows below name their
origin.

The implementation may be absent. `World.stage` plants a no-op
stand-in (exit 0, no output) when it is, so each case fails on the
contract promise rather than on Python's missing-file exit 2; the
absent entrypoint is one red of its own,
`test_the_tool_file_is_present`.

**A case that never executes the subject's behaviour is a declared gap
wearing a pass.** Found by auditing this file's own cases on 2026-09-16
against #242's second review round, and being added to docs/tests.md as a
rule of its own. Six cases here failed it: five asserted something about a
schema or a mock and one about a name, and not one of them ran the server
and looked at what it did. Two of the six no reviewer had found. When a
case pins a key in an inputSchema, a shape the counterparty never returns,
or two vocabularies that cannot collide, it is a gap: rewrite it to run
the subject, or drop it and say so.

Fixture set (docs/tests.md rule 3). Planted faults it must catch: an
unknown verb, an unknown tool, a role supplied as an argument, a
participant supplied as an argument, an unknown argument key, a
malformed config, a config of an unknown version, a config naming a
participant that is not `PT-n`, a config naming a participant the core
does not hold, a generation below the bound the schema advertises, a
call with no binding of any kind, a call whose binding lacks the
capability, a core with no verb table, a verb absent from the table, an
oversized transport line, an unknown JSON-RPC method, a non-string
protocol version, and a payload over the response bound. Clean
neighbours it must pass quietly: a negotiated initialize on each of the
three declared protocols, a ping carrying extra members, a tools/list
carrying every declared tool, a notification answered with silence, a
bounded valid line after an oversized one, and a call whose binding
carries the capability.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from ops.testkit import World, run
from ops.testkit.cases import RefusalCase, refusal_wire, run_table

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "coordination_mcp.py"
SIBLINGS = ("instrument.py",)

TIMEOUT = 30.0
# Renamed from agentscient-coord at the Lead's ruling C1, 2026-09-16:
# the lane literal guard exempts four files by name and laneconf.py is
# wall, so the server carries no lane literal instead.
SERVER = "coordination"
PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
LATEST = "2025-06-18"
MAX_LINE = 65_536
DOMAIN_REFUSAL = -32000
RESPONSE_BYTES = 16_384

SESSION = "ab281ec6-0000-4000-8000-00000000d0d0"
PARTICIPANT = "PT-7"
ABSENT_PARTICIPANT = "PT-9"

# The catalogue of slice one, from the contract's section 3: the tool,
# the core verb's wire name, and whether it mutates.
CATALOGUE = (
    ("coord_brief", "brief", False),
    ("coord_assignments", "assignments", False),
    ("coord_show", "show", False),
    ("coord_draft", "draft", True),
    ("coord_offer", "offer", True),
    ("coord_claim", "claim", True),
    ("coord_release", "release", True),
    ("coord_submit", "submit", True),
    ("coord_verify", "verify", True),
    ("coord_return", "return", True),
    ("coord_accept", "accept", True),
    ("coord_send", "send", True),
    ("coord_inbox", "inbox", False),
    ("coord_ack", "ack", True),
    ("coord_resolve", "resolve", True),
    ("coord_outstanding", "outstanding", False),
    ("coord_observe", "observe", True),
)
TOOL_NAMES = tuple(name for name, _verb, _mutates in CATALOGUE)
MUTATIONS = tuple(name for name, _verb, mutates in CATALOGUE if mutates)
READS = tuple(name for name, _verb, mutates in CATALOGUE if not mutates)
# Every writing tool on an assignment states the generation the caller
# believes; coord_observe joined them at X#2.
GENERATION_TOOLS = (
    "coord_claim", "coord_release", "coord_submit", "coord_verify",
    "coord_return", "coord_accept", "coord_observe",
)
# coord_observe also carries the core's explicit stale flag (05b8aebe).
STALE_TOOL = "coord_observe"
# Every paged read carries an explicit cursor (X#3).
PAGED_TOOLS = ("coord_assignments", "coord_inbox", "coord_outstanding")


def binding(**over) -> dict:
    """A valid acting config, version 1, with its exact key set."""
    row = {
        "version": 1,
        "participant": PARTICIPANT,
        "assignment": "A-3",
        "branch": "lane/session-20260916-d",
        "worktree": "/tmp/nowhere",
        "record": "20260916T000000Z-code-claude-000000",
        "capabilities": ["coord_brief", "coord_submit"],
        "issued_at": "2026-09-16T00:00:00Z",
    }
    row.update(over)
    return row


class Subject:
    """The staged tool and the world it runs in."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.path = world.stage(TOOL, siblings=SIBLINGS if TOOL.is_file() else ())

    def argv(self, *rest: str, config: Path | str | None = None) -> list[str]:
        head = [sys.executable, "-B", str(self.path)]
        if config is not None:
            head += ["--config", str(config)]
        return head + list(rest)

    def env(self, *, session: str | None = None) -> dict[str, str]:
        extra = {} if session is None else {"CLAUDE_CODE_SESSION_ID": session}
        return self.world.env(extra=extra)

    def run(self, *rest: str, config=None, session=None, stdin=None):
        return run(self.argv(*rest, config=config), cwd=self.world.root,
                   env=self.env(session=session), stdin=stdin, timeout=TIMEOUT)

    def config(self, row: dict | str, name: str = "coordination-mcp.json") -> Path:
        text = row if isinstance(row, str) else json.dumps(row, indent=1) + "\n"
        return self.world.plant_text(name, text)

    def core(self, body: str) -> Path:
        """Plant a stub coordination core beside the staged tool."""
        return self.world.plant_text(self.path.parent / "coordination.py", body)


# The contract-verified mock of the core, in the shape coordination.py
# carries at 05b8aebe: CORE keyed by wire name, each entry taking a store
# handle and the resolved participant; VERBS beside it for the CLI, which
# is the wrong layer for this server and is planted here so a projection
# that reached for it fails; and bound_participant, the resolver, which
# is not a verb, so the wire name `resolve` is the message verb alone.
STUB_CORE = '''"""A stand-in for the coordination core, in its 05b8aebe shape."""


class Refusal(Exception):
    pass


def _answer(verb, participant, arguments):
    return {"verb": verb, "participant": participant, "arguments": arguments}


def writer():
    return {"store": "writer"}


def reader():
    return {"store": "reader"}


def bound_participant(conn):
    """The participant resolver. Not a verb, and not in CORE.

    It reads the session id from its own environment, as
    instrument.session() does; echoing it proves the id reached this
    process rather than being supplied by the caller.
    """
    import os

    return {"participant": "PT-1", "roles": ["lead", "worker"],
            "store": conn, "session": os.environ.get("CLAUDE_CODE_SESSION_ID", "")}


def _brief(conn, participant, **arguments):
    return _answer("brief", participant, arguments)


def _submit(conn, participant, **arguments):
    return _answer("submit", participant, arguments)


def _message_resolve(conn, participant, **arguments):
    """The core's message verb. Shares its wire name with the resolver
    above and must never be confused with it."""
    return _answer("message-resolve", participant, arguments)


def _participants(conn, participant, **arguments):
    return [{"id": "PT-7", "roles": ["worker"]}]


def _assignments(conn, participant, **arguments):
    """The whole list, ordered by id, exactly as the core returns it: the
    core does not page, so a server that forwarded a cursor to it would
    fail here on an unexpected argument."""
    if arguments:
        raise TypeError(f"the core verb takes no {sorted(arguments)}")
    return {"assignments": [{"id": number, "title": f"t{number}"}
                            for number in range(1, 131)]}


def _show(conn, participant, **arguments):
    """A payload comfortably under the response bound on its own, and over
    it once tools/call carries it twice."""
    return {"blob": "x" * 12000}


CORE = {
    "brief": _brief,
    "submit": _submit,
    "resolve": _message_resolve,
    "participants": _participants,
    "assignments": _assignments,
    "show": _show,
}

# The CLI wrappers live beside the table and are not this server's layer.
VERBS = {"brief": lambda *a, **k: {"verb": "the-cli-wrapper"}}
'''

# A core whose table is there but whose participant list holds nobody.
STUB_CORE_NO_ROWS = STUB_CORE.replace(
    'return [{"id": "PT-7", "roles": ["worker"]}]', "return []")
# A core that is present but exposes no verb table at all.
STUB_CORE_NO_TABLE = STUB_CORE.replace("CORE = {", "NOT_THE_TABLE = {")


def answer(answers, identifier=None):
    """The one answer a case reads, or an assertion naming what was absent.

    A stand-in that writes nothing must fail a case on its own promise,
    never on an IndexError: an error is a fixture defect, not a red
    (ops/process/tdd.md).
    """
    if not answers:
        raise AssertionError(
            "the server answered nothing; one JSON-RPC response was expected")
    if identifier is None:
        return answers[0]
    for item in answers:
        if item.get("id") == identifier:
            return item
    raise AssertionError(f"no answer carried id {identifier}: {answers}")


def payload(result):
    """The JSON a verb printed, or an assertion naming an empty stdout."""
    if not result.stdout.strip():
        raise AssertionError(
            f"the verb printed nothing; exit {result.exit}, stderr {result.stderr!r}")
    return json.loads(result.stdout)


class CoordinationMcpPresence(unittest.TestCase):
    def test_the_tool_file_is_present(self):
        self.assertTrue(
            TOOL.is_file(),
            f"the contract's subject is absent: {TOOL.relative_to(REPO)}",
        )


class CoordinationMcpCli(unittest.TestCase):
    """The CLI projection: exit 2, one stderr line, stdout empty."""

    def rows(self, subject: Subject):
        good = subject.config(binding())
        unknown_version = subject.config(binding(version=9), "version.json")
        unknown_key = subject.config(dict(binding(), extra="no"), "extra.json")
        bad_participant = subject.config(
            binding(participant="Claude <noreply@anthropic.com>"), "agent.json")
        return (
            RefusalCase(
                id="no-verb", argv=(), cls="arguments",
                named=("check", "serve", "call"),
                origin="contract section 1, the declared command shape"),
            RefusalCase(
                id="unknown-verb", argv=("dispatch",), cls="arguments",
                named=("dispatch",),
                origin="contract section 1"),
            RefusalCase(
                id="call-no-tool", argv=("call",), cls="arguments",
                origin="contract section 3"),
            RefusalCase(
                id="unknown-tool", argv=("call", "coord_nope"), cls="arguments",
                named=("coord_nope",),
                origin="contract section 3, the catalogue is closed"),
            RefusalCase(
                id="role-as-argument",
                argv=("call", "coord_brief", '{"role": "lead"}'),
                cls="arguments", named=("role",),
                origin="AC-02: a caller may not name its own authority"),
            RefusalCase(
                id="participant-as-argument",
                argv=("call", "coord_brief", '{"participant": "PT-1"}'),
                cls="arguments", named=("participant",),
                origin="AC-02, and the core's own rule"),
            RefusalCase(
                id="unknown-argument",
                argv=("call", "coord_brief", '{"nope": 1}'),
                cls="arguments", named=("nope",),
                origin="contract section 3, arguments are a closed object"),
            RefusalCase(
                id="malformed-arguments",
                argv=("call", "coord_brief", "{not json"),
                cls="arguments",
                origin="contract section 1"),
            RefusalCase(
                id="generation-below-the-bound",
                argv=("call", "coord_submit", json.dumps(
                    {"assignment": "A-1", "evidence": "abc1234",
                     "revision": "abc1234", "generation": 0})),
                cls="arguments", named=("generation", "1"),
                origin="G#1, 20260916T075500Z-review-grok-c7a708#1: a declared "
                       "bound the server does not keep makes the next actor guess"),
            RefusalCase(
                id="config-absent",
                argv=("--config", "/dev/null", "call", "coord_brief"),
                cls="config",
                origin="contract section 2.1"),
            RefusalCase(
                id="config-unknown-version",
                argv=("--config", str(unknown_version), "call", "coord_brief"),
                cls="config", named=("9",),
                origin="contract section 2.1, its own version"),
            RefusalCase(
                id="config-unknown-key",
                argv=("--config", str(unknown_key), "call", "coord_brief"),
                cls="config", named=("extra",),
                origin="contract section 2.1, its own exact key set"),
            RefusalCase(
                id="config-participant-not-an-id",
                argv=("--config", str(bad_participant), "call", "coord_brief"),
                cls="config",
                origin="contract section 2.1: a PT-n id, never an agent string"),
            RefusalCase(
                id="no-binding-at-all",
                argv=("call", "coord_brief"), cls="session",
                origin=("contract section 2.3; also the registry's identity "
                        "provocation (G#5 and X#5)")),
            RefusalCase(
                id="capability-not-carried",
                argv=("--config", str(good), "call", "coord_observe"),
                cls="capability", named=("coord_observe",),
                origin="contract section 2.1: the allowlist narrows"),
        )

    def test_the_refusal_wire_on_every_row(self):
        with World() as world:
            subject = Subject(world)
            rows = self.rows(subject)
            run_table(self, rows, lambda row: run(
                subject.argv(*row.argv), cwd=world.root,
                env=subject.env(), timeout=TIMEOUT))

    def test_a_session_with_no_core_refuses_state_not_silence(self):
        """The binding resolves, the core is absent: a reading, never a pass."""
        with World() as world:
            subject = Subject(world)
            result = subject.run("call", "coord_brief", session=SESSION)
            refusal = refusal_wire(
                RefusalCase(id="core-absent", argv=(), cls="state",
                            origin="contract section 7, the core edge"),
                result)
            self.assertIn("coordination", refusal.line)

    def test_an_unauthorised_caller_learns_nothing_about_arguments(self):
        """Pins: a caller whose binding lacks the tool is refused class
        capability whatever it puts in the arguments, so it learns neither
        the argument table nor the forbidden-key table.

        Planted fault: the call carries a forbidden authority key, which
        the server checked first until G2#4
        (20260916T084259Z-review-grok-62fa82#4) ran this very call and got
        class arguments back. Catches any return to that order.
        """
        with World() as world:
            subject = Subject(world)
            config = subject.config(binding())
            for arguments in (None, json.dumps({"role": "lead"}),
                              json.dumps({"assignment": "A-1"})):
                with self.subTest(arguments=arguments):
                    argv = ["call", "coord_observe"]
                    if arguments is not None:
                        argv.append(arguments)
                    result = subject.run(*argv, config=config)
                    refusal = refusal_wire(
                        RefusalCase(id=f"capability-first-{arguments}", argv=(),
                                    cls="capability",
                                    origin="G2#4, 20260916T084259Z-review-grok-62fa82#4"),
                        result)
                    self.assertIn("arguments are checked once the capability is held",
                                  refusal.line)

    def test_a_carried_capability_passes_the_allowlist(self):
        """The clean neighbour of capability-not-carried: same config, a tool
        the allowlist names, so the refusal is no longer `capability`."""
        with World() as world:
            subject = Subject(world)
            config = subject.config(binding())
            result = subject.run("call", "coord_submit", config=config)
            self.assertEqual(result.exit, 2, result.stderr)
            self.assertNotIn("capability:", result.stderr)


class CoordinationMcpTransport(unittest.TestCase):
    """Newline-delimited JSON-RPC 2.0 over stdio, stdout protocol only."""

    def serve(self, subject: Subject, *requests, session=None, raw=None):
        lines = raw if raw is not None else [
            json.dumps(item) for item in requests]
        result = run(subject.argv("serve"), cwd=subject.world.root,
                     env=subject.env(session=session),
                     stdin="".join(line + "\n" for line in lines),
                     timeout=TIMEOUT)
        answers = []
        for line in result.stdout.splitlines():
            if line.strip():
                answers.append(json.loads(line))
        return result, answers

    def initialize(self, identifier=1, protocol=LATEST):
        return {"jsonrpc": "2.0", "id": identifier, "method": "initialize",
                "params": {"protocolVersion": protocol,
                           "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}

    def test_initialize_names_this_server_and_negotiates(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, self.initialize())
            result = answer(answers).get("result", {})
            self.assertEqual(result.get("serverInfo", {}).get("name"), SERVER)
            self.assertEqual(result.get("protocolVersion"), LATEST)
            self.assertIn("instructions", result)

    def test_an_unsupported_protocol_falls_back_to_the_newest_supported(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, self.initialize(protocol="1999-01-01"))
            self.assertEqual(answer(answers)["result"]["protocolVersion"], LATEST)

    def test_a_protocol_version_that_is_not_a_string_is_invalid_params(self):
        """X#4: a malformed request, not an unknown version to negotiate past."""
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, {
                "jsonrpc": "2.0", "id": 12, "method": "initialize",
                "params": {"protocolVersion": []}})
            self.assertEqual(answer(answers)["error"]["code"], -32602)

    def test_every_declared_protocol_is_accepted(self):
        with World() as world:
            subject = Subject(world)
            for wanted in PROTOCOLS:
                with self.subTest(protocol=wanted):
                    _result, answers = self.serve(
                        subject, self.initialize(protocol=wanted))
                    self.assertEqual(
                        answer(answers)["result"]["protocolVersion"], wanted)

    def test_each_method_refuses_a_member_it_does_not_accept(self):
        """Pins: initialize accepts protocolVersion, capabilities and
        clientInfo and nothing else, capabilities and clientInfo are
        objects, and the two list methods accept no members at all.

        Planted faults: an unknown member, a list where an object is
        declared, a string where an object is declared, and a member on a
        list method. Every one was accepted before X2#4
        (20260916T084315Z-review-codex-b317d7#4).
        """
        faults = (
            ("initialize-unknown-member",
             {"protocolVersion": LATEST, "bogus": 1}),
            ("initialize-capabilities-not-an-object",
             {"protocolVersion": LATEST, "capabilities": []}),
            ("initialize-clientinfo-not-an-object",
             {"protocolVersion": LATEST, "clientInfo": "bad"}),
        )
        with World() as world:
            subject = Subject(world)
            for name, params in faults:
                with self.subTest(fault=name):
                    _result, answers = self.serve(subject, {
                        "jsonrpc": "2.0", "id": 20, "method": "initialize",
                        "params": params})
                    self.assertEqual(answer(answers)["error"]["code"], -32602)
            for method in ("tools/list", "resources/list"):
                with self.subTest(fault=f"{method}-with-a-member"):
                    _result, answers = self.serve(subject, {
                        "jsonrpc": "2.0", "id": 21, "method": method,
                        "params": {"bogus": 1}})
                    self.assertEqual(answer(answers)["error"]["code"], -32602)

    def test_a_clean_initialize_still_negotiates(self):
        """The clean neighbour of the case above: every declared member,
        each of the declared type, answers a negotiated result."""
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, {
                "jsonrpc": "2.0", "id": 22, "method": "initialize",
                "params": {"protocolVersion": LATEST, "capabilities": {},
                           "clientInfo": {"name": "t", "version": "1"}}})
            self.assertEqual(
                answer(answers)["result"]["protocolVersion"], LATEST)

    def test_ping_carrying_extra_members_still_answers(self):
        """X#4's other half: JSON-RPC allows them and the contract says so."""
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, {
                "jsonrpc": "2.0", "id": 13, "method": "ping",
                "params": {"bogus": 1}})
            self.assertEqual(answer(answers)["result"], {})

    def test_a_notification_is_answered_with_silence(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject,
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                self.initialize(identifier=2))
            self.assertEqual([item.get("id") for item in answers], [2], answers)

    def test_an_unknown_method_is_a_method_not_found(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject, {"jsonrpc": "2.0", "id": 3, "method": "tools/invent"})
            self.assertEqual(answer(answers)["error"]["code"], -32601)

    def test_an_oversized_line_is_drained_and_the_next_line_still_answers(self):
        with World() as world:
            subject = Subject(world)
            flood = json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping",
                                "params": {"pad": "x" * (MAX_LINE + 2048)}})
            _result, answers = self.serve(
                subject, raw=[flood, json.dumps(self.initialize(identifier=5))])
            codes = [item.get("error", {}).get("code") for item in answers]
            self.assertIn(-32700, codes, answers)
            self.assertIn(5, [item.get("id") for item in answers], answers)

    def test_the_tool_list_is_the_contract_catalogue(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject, {"jsonrpc": "2.0", "id": 6, "method": "tools/list"})
            listed = answer(answers)["result"]["tools"]
            self.assertEqual(
                tuple(sorted(item["name"] for item in listed)),
                tuple(sorted(TOOL_NAMES)))
            for item in listed:
                with self.subTest(tool=item["name"]):
                    self.assertTrue(item.get("description"))
                    self.assertIn("annotations", item)
                    self.assertIn("inputSchema", item)

    def test_a_mutation_is_annotated_as_one_and_a_read_is_not(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject, {"jsonrpc": "2.0", "id": 7, "method": "tools/list"})
            listed = {item["name"]: item for item in answer(answers)["result"]["tools"]}
            for name in MUTATIONS:
                with self.subTest(tool=name, kind="mutation"):
                    self.assertIs(
                        listed[name]["annotations"].get("readOnlyHint"), False)
            for name in READS:
                with self.subTest(tool=name, kind="read"):
                    self.assertIs(
                        listed[name]["annotations"].get("readOnlyHint"), True)
                    self.assertIs(
                        listed[name]["annotations"].get("destructiveHint"), False)

    def test_every_assignment_write_states_a_generation(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject, {"jsonrpc": "2.0", "id": 8, "method": "tools/list"})
            listed = {item["name"]: item for item in answer(answers)["result"]["tools"]}
            for name in GENERATION_TOOLS:
                with self.subTest(tool=name):
                    schema = listed[name]["inputSchema"]
                    self.assertIn("generation", schema.get("properties", {}))
                    self.assertIn("generation", schema.get("required", []))

    def test_every_paged_read_carries_an_explicit_cursor(self):
        """X#3: a page with no cursor is an unbounded list wearing a bound."""
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject, {"jsonrpc": "2.0", "id": 14, "method": "tools/list"})
            listed = {item["name"]: item for item in answer(answers)["result"]["tools"]}
            for name in PAGED_TOOLS:
                with self.subTest(tool=name):
                    self.assertIn(
                        "cursor", listed[name]["inputSchema"].get("properties", {}))

    def test_a_refused_call_carries_the_wire_line_in_the_result(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, {
                "jsonrpc": "2.0", "id": 9, "method": "tools/call",
                "params": {"name": "coord_brief", "arguments": {"role": "lead"}}})
            result = answer(answers)["result"]
            self.assertIs(result["isError"], True)
            text = result["content"][0]["text"]
            self.assertTrue(text.startswith("arguments:"), text)
            for word in ("expected", "found", "needed"):
                self.assertIn(word, text)

    def test_a_refused_resource_read_is_an_error_object_carrying_the_parts(self):
        """G#2: the envelope is asserted, not the words in the raw JSON.

        resources/read has no content field, so a tools/call body hides
        the refusal as surely as the bare -32602 that LD-68 records.
        """
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, {
                "jsonrpc": "2.0", "id": 10, "method": "resources/read",
                "params": {"uri": "coord://brief"}})
            found = answer(answers)
            self.assertNotIn("result", found, found)
            error = found["error"]
            self.assertEqual(error["code"], DOMAIN_REFUSAL)
            self.assertTrue(error["message"].startswith("session:"), error)
            data = error["data"]
            self.assertEqual(data["class"], "session")
            for part in ("expected", "found", "needed"):
                self.assertTrue(str(data[part]).strip(), f"{part} is empty: {data}")

    def test_an_unknown_resource_uri_refuses_the_same_way(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, {
                "jsonrpc": "2.0", "id": 15, "method": "resources/read",
                "params": {"uri": "coord://nothing-of-the-kind"}})
            error = answer(answers)["error"]
            self.assertEqual(error["code"], DOMAIN_REFUSAL)
            self.assertEqual(error["data"]["class"], "arguments")

    def test_resources_never_mutate(self):
        """Contract section 0: mutations travel only through tools/call."""
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject, {"jsonrpc": "2.0", "id": 11, "method": "resources/list"})
            listed = answer(answers)["result"]["resources"]
            for item in listed:
                with self.subTest(uri=item["uri"]):
                    self.assertNotIn(
                        item["uri"].rsplit("/", 1)[-1], MUTATIONS)


class CoordinationMcpCore(unittest.TestCase):
    """The seam to the coordination core, with a stub standing in for it."""

    def test_the_binding_resolves_from_the_inherited_session_id(self):
        """The Lead's ruling 5, 2026-09-16: the binding is proven here, in a
        hermetic world, not only by the live reading in the PR."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run("call", "coord_brief", session=SESSION)
            self.assertEqual(result.exit, 0, result.stderr)
            answered = payload(result)
            self.assertEqual(
                answered.get("participant", {}).get("session"), SESSION,
                f"the binding did not come from the environment: {answered}")

    def test_an_absent_session_id_refuses_session_and_never_guesses(self):
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run("call", "coord_brief")
            refusal_wire(
                RefusalCase(id="session-absent", argv=(), cls="session",
                            origin="contract section 2.2 and 2.3"),
                result)

    def test_the_message_verb_is_not_the_participant_resolver(self):
        """X#1's surviving half, 20260916T075518Z-review-codex-c22c2d#1: the
        core's message verb and its participant resolver share the word
        `resolve`. A projection that looked the verb up on the module
        would answer a message resolution with the resolver."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run(
                "call", "coord_resolve",
                '{"message": "M-1", "evidence": "abc1234"}', session=SESSION)
            self.assertEqual(result.exit, 0, result.stderr)
            self.assertEqual(payload(result).get("verb"), "message-resolve")

    def test_a_config_naming_a_participant_the_core_lacks_refuses_participant(self):
        """G#3: a missing row and the slice-one bind gap are different
        faults and must not share a class."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE_NO_ROWS)
            config = subject.config(binding(participant=ABSENT_PARTICIPANT,
                                            capabilities=["coord_brief"]))
            result = subject.run("call", "coord_brief", config=config)
            refusal = refusal_wire(
                RefusalCase(id="participant-absent", argv=(), cls="participant",
                            named=(ABSENT_PARTICIPANT,),
                            origin="G#3, 20260916T075500Z-review-grok-c7a708#3"),
                result)
            self.assertIn(ABSENT_PARTICIPANT, refusal.line)

    def test_a_config_whose_participant_exists_still_meets_the_bind_gap(self):
        """The clean neighbour: the row is there, so the refusal moves on to
        the declared limit of slice one rather than staying `participant`."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            config = subject.config(binding(capabilities=["coord_brief"]))
            result = subject.run("call", "coord_brief", config=config)
            refusal_wire(
                RefusalCase(id="bind-gap", argv=(), cls="state",
                            origin="contract section 2.3, the declared limit"),
                result)

    def test_a_core_with_no_verb_table_refuses_state_and_names_it(self):
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE_NO_TABLE)
            result = subject.run("call", "coord_brief", session=SESSION)
            refusal = refusal_wire(
                RefusalCase(id="table-absent", argv=(), cls="state",
                            named=("CORE",),
                            origin="X#1 and the seam ruling, 2026-09-16"),
                result)
            self.assertIn("CORE", refusal.line)

    def test_the_cli_wrapper_table_is_not_this_server_s_layer(self):
        """The core keeps VERBS beside CORE for its own CLI. A projection
        that reached for it would call a wrapper that prints and exits."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run("call", "coord_brief", session=SESSION)
            self.assertEqual(result.exit, 0, result.stderr)
            self.assertNotEqual(payload(result).get("verb"), "the-cli-wrapper")

    def test_the_store_handle_reaches_the_verb(self):
        """The core owns the store; this server opens none and passes the
        handle the core gave it, a writer for a mutation and a reader for
        a read (05b8aebe)."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run("call", "coord_brief", session=SESSION)
            self.assertEqual(
                payload(result).get("participant", {}).get("store"),
                {"store": "reader"})

    def test_a_verb_absent_from_the_table_refuses_state_and_names_it(self):
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run("call", "coord_outstanding", session=SESSION)
            refusal = refusal_wire(
                RefusalCase(id="verb-absent", argv=(), cls="state",
                            named=("outstanding",),
                            origin="contract section 7, the core edge"),
                result)
            self.assertIn("outstanding", refusal.line)

    def test_a_response_over_the_bound_answers_the_unavailable_reading(self):
        """Pins: the bound is measured on the serialised JSON-RPC response,
        not on the payload inside it.

        Planted fault: a payload of about 12,000 bytes, which is under the
        16,384 bound on its own and over it once tools/call carries it
        twice, as content text and as structuredContent. Measured at
        40d340b2: payload 12,013 bytes, response 24,140 bytes, and the
        server answered it whole (G2#1 and X2#3).
        """
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = run(subject.argv("serve"), cwd=world.root,
                         env=subject.env(session=SESSION),
                         stdin=json.dumps({
                             "jsonrpc": "2.0", "id": 30, "method": "tools/call",
                             "params": {"name": "coord_show",
                                        "arguments": {"assignment": "A-1"}}}) + "\n",
                         timeout=TIMEOUT)
            answered = json.loads(result.stdout.splitlines()[0])
            self.assertLessEqual(
                len(json.dumps(answered, separators=(",", ":")).encode("utf-8")),
                RESPONSE_BYTES,
                "the whole response is over the bound it declares")
            self.assertEqual(
                answered["result"]["structuredContent"].get("state"),
                "unavailable")

    def test_a_paged_read_returns_one_page_and_a_cursor(self):
        """Pins: the server pages the verb's whole list itself, ordered by
        id, and returns the last id as the cursor while rows remain.

        Planted fault: the stub verb raises TypeError on any argument, so a
        server that forwarded the cursor to the core fails here; and it
        returns 130 rows, so a server that returned the list whole fails on
        the count. Before this, cursor was a schema word nothing read
        (X2#3).
        """
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            first = payload(subject.run("call", "coord_assignments",
                                        session=SESSION))
            self.assertEqual(len(first["assignments"]), 50)
            self.assertEqual(first["assignments"][0]["id"], 1)
            self.assertEqual(first["cursor"], "50")
            second = payload(subject.run(
                "call", "coord_assignments", json.dumps({"cursor": "50"}),
                session=SESSION))
            self.assertEqual(second["assignments"][0]["id"], 51)
            self.assertEqual(second["cursor"], "100")
            last = payload(subject.run(
                "call", "coord_assignments", json.dumps({"cursor": "100"}),
                session=SESSION))
            self.assertEqual(len(last["assignments"]), 30)
            self.assertIsNone(last["cursor"])

    def test_a_cursor_that_is_not_digits_refuses_arguments(self):
        """The planted fault beside the page above: a cursor the server
        cannot have issued."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run(
                "call", "coord_assignments", json.dumps({"cursor": "../etc"}),
                session=SESSION)
            refusal_wire(
                RefusalCase(id="cursor-not-digits", argv=(), cls="arguments",
                            origin="X2#3, the cursor is the server's own"),
                result)


if __name__ == "__main__":
    unittest.main()
