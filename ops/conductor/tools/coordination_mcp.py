#!/usr/bin/env python3
"""CLI and stdio MCP projection for acting coordination verbs.

The contract is `ops/conductor/coordination-mcp-lever.md`; the domain is
the coordination core (`coordination.py`, contract
`coordination-lever.md`), which this module projects and never
duplicates. Mutations travel only through `tools/call`; resources are
reads. Every refusal is the wire: one line, class first, then expected,
found and needed.

    coordination_mcp.py [--config FILE] check | serve | call TOOL [JSON]

This module holds no authority of its own. It validates arguments,
resolves the caller's binding from its own environment or from a config
on its own argv, narrows by the binding's capability list, and calls one
core verb. A role or a participant named in a request is refused: a
caller that can name its own authority has none.
"""

import sys

sys.dont_write_bytecode = True

import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

try:
    from instrument import Refusal, refuse, session
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
LATEST_PROTOCOL = PROTOCOLS[-1]
MAX_LINE = 65_536
SERVER_NAME = "agentscient-coord"
CONFIG_VERSION = 1
CONFIG_KEYS = frozenset({
    "version", "participant", "assignment", "branch", "worktree", "record",
    "capabilities", "issued_at",
})
CONFIG_BYTES = 65_536
PARTICIPANT_RE = re.compile(r"PT-[1-9][0-9]{0,8}")
INSTRUCTIONS = (
    "Acting server: these tools change durable state. Every mutation needs a "
    "binding the caller cannot supply. Evidence is not authority; every "
    "refusal carries expected, found and needed."
)
# A caller never names its own authority (contract section 3; the core
# refuses the same fault class `arguments` at its own boundary).
FORBIDDEN_ARGUMENTS = ("role", "roles", "participant", "session", "agent", "identity")


class Tool:
    """One row of the catalogue: the tool, the core verb, the mutation
    flag and the closed argument object it accepts."""

    __slots__ = ("mutates", "name", "properties", "required", "summary", "verb")

    def __init__(self, name, verb, mutates, properties, required, summary):
        self.name = name
        self.verb = verb
        self.mutates = mutates
        self.properties = properties
        self.required = required
        self.summary = summary


def _text(description=None):
    return {"type": "string"} if description is None else {
        "type": "string", "description": description}


_INT = {"type": "integer", "minimum": 1}
_BOOL = {"type": "boolean"}

CATALOGUE = (
    Tool("coord_brief", "brief", False, {}, (),
         "This session's bounded picture: held assignments, unresolved inbox, "
         "open decisions, stale observations."),
    Tool("coord_assignments", "assignments", False,
         {"state": _text(), "to": _text(), "mine": _BOOL}, (),
         "A bounded page of assignments, oldest first."),
    Tool("coord_show", "show", False, {"assignment": _text()}, ("assignment",),
         "One assignment: its row, its marking, its observations and its open messages."),
    Tool("coord_draft", "draft", True,
         {"title": _text(), "outcome": _text(), "requirement": _text(),
          "revision": _text(), "depends": _text(), "duty": _text(),
          "scope": _text(), "inputs": _text()},
         ("title", "outcome"),
         "Create an assignment. It names no recipient: offer does that."),
    Tool("coord_offer", "offer", True,
         {"assignment": _text(), "to": _text()}, ("assignment", "to"),
         "Name the recipient of a drafted assignment."),
    Tool("coord_claim", "claim", True,
         {"assignment": _text(), "branch": _text(), "generation": _INT,
          "ttl": _INT},
         ("assignment", "branch", "generation"),
         "Take the hold. The branch must be named in the deliverable lock."),
    Tool("coord_release", "release", True,
         {"assignment": _text(), "why": _text(), "generation": _INT},
         ("assignment", "why", "generation"),
         "Give the hold back; bumps the generation."),
    Tool("coord_submit", "submit", True,
         {"assignment": _text(), "evidence": _text(), "revision": _text(),
          "generation": _INT},
         ("assignment", "evidence", "revision", "generation"),
         "Submit the candidate with the reading it rests on."),
    Tool("coord_verify", "verify", True,
         {"assignment": _text(), "evidence": _text(), "generation": _INT},
         ("assignment", "evidence", "generation"),
         "An independent verifier's pass. Never the producer's own."),
    Tool("coord_return", "return", True,
         {"assignment": _text(), "findings": _text(), "generation": _INT},
         ("assignment", "findings", "generation"),
         "Return the candidate to its holder with findings."),
    Tool("coord_accept", "accept", True,
         {"assignment": _text(), "evidence": _text(), "generation": _INT},
         ("assignment", "evidence", "generation"),
         "The lead's acceptance. Never the producer's own."),
    Tool("coord_send", "send", True,
         {"to": _text(), "purpose": _text("inform, request or finding"),
          "body": _text(), "assignment": _text(), "decision": _text(),
          "reply_to": _text(), "artifact": _text()},
         ("to", "purpose", "body"),
         "Queue a durable message to a participant or a role."),
    Tool("coord_inbox", "inbox", False, {"unresolved": _BOOL}, (),
         "Messages addressed to this participant or its roles."),
    Tool("coord_ack", "ack", True, {"message": _text()}, ("message",),
         "Acknowledge receipt. An acknowledgment never closes the obligation."),
    Tool("coord_resolve", "resolve", True,
         {"message": _text(), "evidence": _text()}, ("message", "evidence"),
         "Answer the obligation, separately from the acknowledgment."),
    Tool("coord_outstanding", "outstanding", False, {"to": _text()}, (),
         "Requests and findings not yet resolved."),
    Tool("coord_observe", "observe", True,
         {"assignment": _text(), "observation": _text(), "revision": _text(),
          "execution": _text(), "artifact": _text(), "requirement": _text(),
          "environment": _text()},
         ("assignment", "observation", "revision"),
         "Record an observation against an assignment and a revision."),
)
BY_NAME = {tool.name: tool for tool in CATALOGUE}

# The read tools a resource mirrors. Resources are reads by construction:
# a mutation has no URI, so no client can act through resources/read.
RESOURCES = (
    ("coord://brief", "coord_brief", "This session's bounded picture"),
    ("coord://assignments", "coord_assignments", "Assignments in scope"),
    ("coord://inbox", "coord_inbox", "Messages for this participant"),
    ("coord://outstanding", "coord_outstanding", "Unresolved obligations"),
)


def canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


# -- the config binding ----------------------------------------------------

def load_config(path: Path) -> dict:
    """The acting config, validated against its own exact key set.

    Its own file and its own version: the read server's config is not
    extended and its loader is not touched (contract section 2.1).
    """
    absolute = Path(os.path.abspath(path))
    try:
        if not absolute.is_file():
            refuse("config", "a regular acting config file", str(absolute),
                   "pass --config FILE naming the config the launcher wrote")
        raw = absolute.read_bytes()
    except OSError as error:
        refuse("config", "a readable acting config", f"{absolute}: {error}",
               "restore the config the launcher wrote")
    if len(raw) > CONFIG_BYTES:
        refuse("config", f"a config no larger than {CONFIG_BYTES} bytes",
               f"{len(raw)} bytes", "shorten the config")
    try:
        root = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError) as error:
        refuse("config", "valid UTF-8 JSON", type(error).__name__,
               "repair the config")
    if not isinstance(root, dict):
        refuse("config", f"exact keys {sorted(CONFIG_KEYS)}",
               type(root).__name__, "write the declared object")
    if root.get("version") != CONFIG_VERSION or isinstance(root.get("version"), bool):
        refuse("config", f"version {CONFIG_VERSION}", repr(root.get("version")),
               "write a config of a version this server declares")
    unknown = sorted(set(root) - CONFIG_KEYS)
    missing = sorted(CONFIG_KEYS - set(root))
    if unknown or missing:
        refuse("config", f"exact keys {sorted(CONFIG_KEYS)}",
               f"unknown {unknown}, missing {missing}",
               "add missing and remove unknown keys")
    participant = root["participant"]
    if not isinstance(participant, str) or PARTICIPANT_RE.fullmatch(participant) is None:
        refuse("config", "a participant id of the form PT-n", repr(participant),
               "name the participant id the core bound, never an agent string")
    capabilities = root["capabilities"]
    if (not isinstance(capabilities, list)
            or any(not isinstance(item, str) for item in capabilities)):
        refuse("config", "capabilities as a list of tool names",
               repr(capabilities), "write the tool names this binding may call")
    stranger = sorted(set(capabilities) - set(BY_NAME))
    if stranger:
        refuse("config", "capabilities drawn from this server's catalogue",
               f"{stranger}", "remove the names this server does not carry")
    return root


# -- the core edge ---------------------------------------------------------

def _core():
    """The coordination core beside this tool, or a reading that it is not.

    Imported late and by name: a projection that cannot reach its domain
    refuses rather than answering from nothing.
    """
    try:
        # Imported at call time, not at module load: the edge is resolved
        # when a verb needs it, so `check` can report an absent core.
        import coordination
    except ModuleNotFoundError:
        refuse("state", "the coordination core beside this tool",
               "coordination.py absent",
               "land ops/conductor/tools/coordination.py, package B")
    return coordination


def _verb(core, tool: Tool):
    """The core function a tool projects.

    `return` is a reserved word, so the core cannot spell that verb as a
    function of the same name; the trailing-underscore spelling is tried
    after the plain one. A verb the core does not carry is a reading, not
    a guess.
    """
    for spelling in (tool.verb, tool.verb + "_"):
        found = getattr(core, spelling, None)
        if callable(found):
            return found
    refuse("state", f"the core verb `{tool.verb}`", "absent from coordination.py",
           f"land the verb `{tool.verb}` in the core, or withdraw {tool.name}")


# -- the binding -----------------------------------------------------------

def check_capability(config, tool: Tool) -> None:
    """The binding's allowlist, checked before anything about arguments.

    The capability is about the tool, not its shape: a caller whose
    binding does not carry the tool learns that, and not what arguments
    it would have taken. It narrows and never widens — the core's own
    role gate still runs inside every verb (contract section 2.1).
    """
    if config is None:
        return
    if tool.name not in config["capabilities"]:
        refuse("capability", f"a binding carrying {tool.name}",
               f"capabilities {sorted(config['capabilities'])}",
               "ask the dispatcher for a binding that carries this tool")


def resolve_binding(config, tool: Tool):
    """Who is calling, from the launcher's config or from the environment.

    Never from the request: a role or a participant in the arguments is
    refused before this is reached.
    """
    if config is not None:
        # The core binds a participant to the calling session alone, so a
        # config naming another session's participant cannot yet be
        # resolved (contract section 9, divergence 1).
        refuse("state", "a core verb binding a participant for another session",
               f"config names {config['participant']}",
               "land the dispatcher-issued bind of package B, then bind this "
               "worker's session id before launch")
    key = session("")
    if not key:
        refuse("session", "a session id in this server's environment",
               "unset",
               "run under a harness that sets CLAUDE_CODE_SESSION_ID, or pass "
               "--config FILE with a binding the dispatcher issued")
    core = _core()
    resolver = getattr(core, "resolve", None)
    if not callable(resolver):
        refuse("state", "the core verb `resolve`", "absent from coordination.py",
               "land the participant resolution of package B")
    return resolver()


# -- arguments -------------------------------------------------------------

def check_named_authority(tool: Tool, arguments) -> None:
    """A request may not name its own authority, whoever is asking.

    This runs before the binding is resolved, because it is a malformed
    request and not a permission question (AC-02).
    """
    if not isinstance(arguments, dict):
        return
    for name in FORBIDDEN_ARGUMENTS:
        if name in arguments:
            refuse("arguments", f"no caller-supplied `{name}`",
                   f"{name} in the arguments of {tool.name}",
                   "remove it: the binding names the caller, the request never does")


def check_arguments(tool: Tool, arguments) -> dict:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        refuse("arguments", f"a closed object of arguments for {tool.name}",
               type(arguments).__name__, "pass the declared arguments object")
    unknown = sorted(set(arguments) - set(tool.properties))
    if unknown:
        refuse("arguments", f"arguments drawn from {sorted(tool.properties)}",
               f"{unknown}", f"remove the arguments {tool.name} does not take")
    missing = [name for name in tool.required if name not in arguments]
    if missing:
        refuse("arguments", f"the required arguments {list(tool.required)}",
               f"missing {missing}", "supply them")
    for name, value in arguments.items():
        wanted = tool.properties[name].get("type")
        if wanted == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            refuse("arguments", f"{name} as an integer", repr(value),
                   f"pass {name} as a whole number")
        if wanted == "string" and not isinstance(value, str):
            refuse("arguments", f"{name} as a string", repr(value),
                   f"pass {name} as text")
        if wanted == "boolean" and not isinstance(value, bool):
            refuse("arguments", f"{name} as a boolean", repr(value),
                   f"pass {name} as true or false")
    return arguments


def call(config, name, arguments) -> dict:
    """One tool call: arguments, then binding, then the one core verb."""
    tool = BY_NAME.get(name)
    if tool is None:
        refuse("arguments", "a tool this server carries", repr(name),
               f"choose one of {sorted(BY_NAME)}")
    check_named_authority(tool, arguments)
    check_capability(config, tool)
    checked = check_arguments(tool, arguments)
    binding = resolve_binding(config, tool)
    verb = _verb(_core(), tool)
    return verb(binding, **checked)


# -- the transport ---------------------------------------------------------

def _schemas() -> list:
    listed = []
    for tool in CATALOGUE:
        annotations = {
            "readOnlyHint": not tool.mutates,
            "destructiveHint": False,
            "idempotentHint": not tool.mutates,
        }
        listed.append({
            "name": tool.name,
            "description": tool.summary,
            "inputSchema": {
                "type": "object",
                "properties": dict(tool.properties),
                "required": list(tool.required),
                "additionalProperties": False,
            },
            "annotations": annotations,
        })
    return listed


def _resources() -> list:
    return [{"uri": uri, "name": name, "description": description,
             "mimeType": "application/json"}
            for uri, name, description in RESOURCES]


def _error(identifier, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def _result(identifier, result) -> dict:
    return {"jsonrpc": "2.0", "id": identifier, "result": result}


def _refusal_result(identifier, refusal: Refusal) -> dict:
    """A domain refusal, on every path, carrying its line.

    The read server drops this line on resources/read (LD-68); this
    server never does (contract section 4).
    """
    return _result(identifier, {
        "content": [{"type": "text", "text": refusal.line()}],
        "isError": True,
    })


def _params(request: dict) -> dict:
    params = request.get("params", {})
    if not isinstance(params, dict):
        raise TypeError
    if "_meta" in params and not isinstance(params["_meta"], dict):
        raise TypeError
    result = dict(params)
    result.pop("_meta", None)
    return result


def _dispatch(config, request) -> dict | None:
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    identifier = request.get("id")
    notification = "id" not in request
    method = request.get("method")
    if not isinstance(method, str):
        return _error(identifier, -32600, "Invalid Request")
    try:
        params = _params(request)
    except TypeError:
        return None if notification else _error(identifier, -32602, "Invalid params")
    if notification:
        return None
    if method == "initialize":
        requested = params.get("protocolVersion")
        selected = requested if requested in PROTOCOLS else LATEST_PROTOCOL
        return _result(identifier, {
            "protocolVersion": selected,
            "capabilities": {"tools": {"listChanged": False},
                             "resources": {"subscribe": False, "listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": "1"},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _result(identifier, {})
    if method == "tools/list":
        return _result(identifier, {"tools": _schemas()})
    if method == "resources/list":
        return _result(identifier, {"resources": _resources()})
    if method == "tools/call":
        if set(params) not in ({"name"}, {"name", "arguments"}) or not isinstance(
                params.get("name"), str):
            return _error(identifier, -32602, "Invalid params")
        try:
            payload = call(config, params["name"], params.get("arguments", {}))
        except Refusal as exc:
            return _refusal_result(identifier, exc)
        return _result(identifier, {
            "content": [{"type": "text", "text": canonical(payload)}],
            "structuredContent": payload,
            "isError": False,
        })
    if method == "resources/read":
        if set(params) != {"uri"}:
            return _error(identifier, -32602, "Invalid params")
        try:
            payload = _read_resource(config, params["uri"])
        except Refusal as exc:
            return _refusal_result(identifier, exc)
        return _result(identifier, {"contents": [
            {"uri": params["uri"], "mimeType": "application/json",
             "text": canonical(payload)}]})
    return _error(identifier, -32601, "Method not found")


def _read_resource(config, uri) -> dict:
    for listed, name, _description in RESOURCES:
        if uri == listed:
            return call(config, name, {})
    refuse("arguments", "a listed resource URI", repr(uri),
           f"select one of {[row[0] for row in RESOURCES]}")


def _send(message) -> None:
    sys.stdout.write(canonical(message) + "\n")
    sys.stdout.flush()


def _reject_constant(value):
    raise ValueError(value)


def serve(config) -> int:
    source = sys.stdin.buffer
    while True:
        line = source.readline(MAX_LINE + 1)
        if not line:
            return 0
        if len(line) > MAX_LINE:
            while line and not line.endswith(b"\n"):
                line = source.readline(MAX_LINE + 1)
            _send(_error(None, -32700, "Parse error"))
            continue
        try:
            request = json.loads(line, parse_constant=_reject_constant)
        except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError):
            _send(_error(None, -32700, "Parse error"))
            continue
        response = _dispatch(config, request)
        if response is not None:
            _send(response)


# -- the CLI ---------------------------------------------------------------

def check_result(config) -> dict:
    """What this server would answer with, without answering anything."""
    try:
        _core()
        core = "present"
    except Refusal:
        core = "absent"
    return {
        "server": SERVER_NAME,
        "protocols": list(PROTOCOLS),
        "tools": [tool.name for tool in CATALOGUE],
        "mutations": [tool.name for tool in CATALOGUE if tool.mutates],
        "binding": "config" if config is not None else (
            "session" if session("") else "none"),
        "core": core,
    }


def _cli(argv):
    config_path = None
    rest = list(argv)
    if rest[:1] == ["--config"]:
        if len(rest) < 2:
            refuse("arguments", "--config FILE", "--config with no file",
                   "name the config file")
        config_path = Path(rest[1])
        rest = rest[2:]
    if not rest:
        refuse("arguments", "check, serve, or call TOOL [JSON]",
               "no verb", "name one of check, serve, call")
    return config_path, rest[0], rest[1:]


def main() -> int:
    try:
        config_path, verb, rest = _cli(sys.argv[1:])
        config = load_config(config_path) if config_path is not None else None
        if verb == "check" and not rest:
            print(canonical(check_result(config)))
            return 0
        if verb == "serve" and not rest:
            return serve(config)
        if verb == "call" and len(rest) in (1, 2):
            if len(rest) == 2:
                try:
                    arguments = json.loads(rest[1], parse_constant=_reject_constant)
                except (ValueError, UnicodeError, RecursionError):
                    refuse("arguments", "a JSON object of arguments",
                           "unparseable", "pass the declared arguments as JSON")
            else:
                arguments = {}
            print(canonical(call(config, rest[0], arguments)))
            return 0
        refuse("arguments", "check, serve, or call TOOL [JSON]",
               repr([verb, *rest]), "use the declared verb and arguments")
    except Refusal as exc:
        print(exc.line(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
