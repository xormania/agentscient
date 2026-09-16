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

The implementation may be absent. `World.stage` plants a no-op
stand-in (exit 0, no output) when it is, so each case fails on the
contract promise rather than on Python's missing-file exit 2; the
absent entrypoint is one red of its own,
`test_the_tool_file_is_present`. A run of this file claims no later
green.

Fixture set (docs/tests.md rule 3). Planted faults it must catch: an
unknown verb, an unknown tool, a role supplied as an argument, a
participant supplied as an argument, an unknown argument key, a
malformed config, a config of an unknown version, a config naming a
participant that is not `PT-n`, a call with no binding of any kind, a
call whose binding lacks the capability, an oversized transport line,
an unknown JSON-RPC method. Clean neighbours it must pass quietly: a
negotiated initialize, a tools/list carrying every declared tool, a
notification answered with silence, a bounded valid line after an
oversized one, and a call whose binding carries the capability.
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
SERVER = "agentscient-coord"
PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
LATEST = "2025-06-18"
MAX_LINE = 65_536

SESSION = "ab281ec6-0000-4000-8000-00000000d0d0"
PARTICIPANT = "PT-7"

# The catalogue of slice one, from the contract's section 3. Each row is
# the tool, the core verb it projects, and whether it mutates.
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
# Assignment-writing tools state the generation the caller believes
# (contract section 3; the core refuses class `generation` otherwise).
GENERATION_TOOLS = (
    "coord_claim", "coord_release", "coord_submit", "coord_verify",
    "coord_return", "coord_accept",
)


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


STUB_CORE = '''"""A stand-in for the coordination core: it records the call and answers."""

import json
import sys


class Refusal(Exception):
    pass


def _answer(verb, participant, arguments):
    return {"verb": verb, "participant": participant, "arguments": arguments}


def resolve():
    """The core reads the session id from its own environment, as
    instrument.session() does; echoing it proves the id reached this
    process rather than being supplied by the caller."""
    import os

    return {"participant": "PT-1", "roles": ["lead", "worker"],
            "session": os.environ.get("CLAUDE_CODE_SESSION_ID", "")}


def brief(participant, **arguments):
    return _answer("brief", participant, arguments)


def submit(participant, **arguments):
    return _answer("submit", participant, arguments)
'''


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
                origin="contract section 2.3"),
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
            self.assertEqual(len(answers), 1, answers)
            result = answer(answers).get("result", {})
            self.assertEqual(result.get("serverInfo", {}).get("name"), SERVER)
            self.assertEqual(result.get("protocolVersion"), LATEST)
            self.assertIn("instructions", result)

    def test_an_unsupported_protocol_falls_back_to_the_newest_supported(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, self.initialize(protocol="1999-01-01"))
            self.assertEqual(answer(answers)["result"]["protocolVersion"], LATEST)

    def test_every_declared_protocol_is_accepted(self):
        with World() as world:
            subject = Subject(world)
            for wanted in PROTOCOLS:
                with self.subTest(protocol=wanted):
                    _result, answers = self.serve(
                        subject, self.initialize(protocol=wanted))
                    self.assertEqual(
                        answer(answers)["result"]["protocolVersion"], wanted)

    def test_a_notification_is_answered_with_silence(self):
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(
                subject,
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                self.initialize(identifier=2))
            self.assertEqual([answer.get("id") for answer in answers], [2], answers)

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
            codes = [answer.get("error", {}).get("code") for answer in answers]
            self.assertIn(-32700, codes, answers)
            self.assertIn(5, [answer.get("id") for answer in answers], answers)

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

    def test_a_refused_resource_read_carries_the_wire_line_too(self):
        """Contract section 4: unlike the read server, this one never drops
        the line into a bare -32602 (LD-68)."""
        with World() as world:
            subject = Subject(world)
            _result, answers = self.serve(subject, {
                "jsonrpc": "2.0", "id": 10, "method": "resources/read",
                "params": {"uri": "coord://nothing-of-the-kind"}})
            found = answer(answers)
            self.assertNotIn("error", found, found)
            result = found["result"]
            self.assertIs(result["isError"], True)
            text = result["content"][0]["text"]
            self.assertIn("expected", text)
            self.assertIn("found", text)
            self.assertIn("needed", text)

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
        hermetic world, not only by the live reading in the PR. The world
        plants the id in the server's environment; the core echoes what it
        read; the case asserts the planted id came back, so a server that
        invented a participant fails."""
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
        """The other half of the same proof: with the core present and no id
        in the environment, the server refuses rather than resolving to
        whatever row it can find."""
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run("call", "coord_brief")
            refusal_wire(
                RefusalCase(id="session-absent", argv=(), cls="session",
                            origin="contract section 2.2 and 2.3"),
                result)

    def test_a_bound_session_reaches_the_core_verb(self):
        with World() as world:
            subject = Subject(world)
            subject.core(STUB_CORE)
            result = subject.run("call", "coord_brief", session=SESSION)
            self.assertEqual(result.exit, 0, result.stderr)
            self.assertEqual(payload(result).get("verb"), "brief")

    def test_a_core_without_the_verb_refuses_state_and_names_it(self):
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


if __name__ == "__main__":
    unittest.main()
