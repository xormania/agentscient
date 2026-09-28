#!/usr/bin/env python3
"""A read-only MCP status server over the workflow record (PLAN §9).

"Serves status/next/log as MCP resources over the same --json surface.
Read-only by construction: it imports the query layer, not the append layer."

Both halves of that are load-bearing and both are testable.

**The same --json surface.** Every resource body is built by `query`, the
same functions the CLI calls, and dumped with the same canonical encoder. A
parallel implementation would drift, and drift in a status surface is how an
agent acts on a stale picture.

For `next`, `log` and `checks` that makes a read byte-identical to the
corresponding `wf --json …`, and the suite asserts exactly that. It does NOT
for `status`: its `sessions` block is live presence, so `last_seen` moves on
every call — two consecutive CLI runs are not byte-identical to each other
either. Claiming byte-identity there would be claiming something untrue of
the CLI, so the promise is stated where it holds and the recorded part of
`status` — `work_orders` — is compared exactly.

**Read-only by construction.** This module imports `query`, `store`, `chain`,
`gatekinds`, `coord` and `canonical`. It does not import `wf`, `gitio` or
`receipts`, so nothing that can append to a chain, touch git, or record a
receipt is reachable from here — a property of the import graph, not of this
file happening not to call anything. The suite asserts it from the AST.

Transport is JSON-RPC 2.0 over stdio, newline-delimited, stdlib only.

    python3 mcp_server.py --root ops/devlane/workflow
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import canonical
import chain as chainmod
import gatekinds
import query
from cas import Cas
from errors import EXIT_REFUSED, WfError
from mcp_launch import classify_cache
from store import Store


class CacheMissing(WfError):
    """The rebuilt database is absent. Recoverable, and by one command."""

    exit_code = EXIT_REFUSED
    kind = "refusal"

    def payload(self) -> dict:
        return {"error": "refusal", "precondition": "the database is rebuilt",
                "needed": "python3 ops/devlane/workflow/wf.py init --rebuild",
                "message": str(self)}

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "wf-status", "version": "1"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class ReadOnlyChain:
    """A chain that can be projected and verified, and cannot be appended to.

    `chain.Chain` carries `append`, so handing one to the query layer would
    make "read-only" a fact about what this file happens to call rather than
    about what is reachable. This exposes the two reading methods and nothing
    else, so an append is an AttributeError rather than a code review.
    """

    def __init__(self, store):
        self._chain = chainmod.Chain(store)

    def project(self, wo_id):
        return self._chain.project(wo_id)

    def verify(self, wo_id):
        return self._chain.verify(wo_id)


class ReadOnlyContext:
    """The reading surface `query` needs, and nothing else.

    Deliberately not wf.Context: that carries the agent identity, the source
    list, the commit machinery and the migration runner. None of those mean
    anything to a reader, and having them in reach is how read-only stops
    being true.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.db_path = self.root / "wf.db"
        self.store = None
        self.chain = None
        self.cas = Cas(self.root / "objects")
        self._specs = None
        if self.db_path.exists():
            self.store = Store(self.db_path, read_only=True)
            self.chain = ReadOnlyChain(self.store)

    def require_cache(self):
        """The database is a gitignored cache, so a clone does not have one.

        Opening it read-write would create an empty file and every query
        would then fail on a missing table — which is exactly what happened:
        a fresh clone answered every tool with
        `OperationalError: no such table: work_orders`, and merely reading
        created a zero-byte wf.db, so "originates nothing" was false too.

        A reader cannot fix this, because fixing it is a write. It can say
        precisely what to run.
        """
        # The launcher's classification, deliberately shared — nothing
        # forces the server to be started through the launcher, so it must
        # refuse the same states. "Ahead" gets its own answer: the cache
        # holds recorded events the export does not, which is either
        # un-flushed work or a branch switch, and only the caller knows
        # which — so name both reconciliations and originate neither.
        verdict = ("rebuild" if self.store is None
                   else classify_cache(self.db_path))
        if verdict == "ahead":
            raise CacheMissing(
                f"the database at {self.db_path} holds events the tracked "
                "export does not. If that is your un-flushed work, run: "
                "python3 ops/devlane/workflow/wf.py commit — to discard it "
                "instead (e.g. after a branch switch), run: "
                "python3 ops/devlane/workflow/wf.py init --rebuild"
            )
        if verdict != "match":
            raise CacheMissing(
                f"no rebuilt database at {self.db_path}. The database is a "
                "gitignored cache; the tracked export is the evidence. Run: "
                "python3 ops/devlane/workflow/wf.py init --rebuild"
            )

    def has_schema(self) -> bool:
        row = self.store.one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='work_orders'"
        )
        return row is not None

    @property
    def specs(self) -> dict:
        if self._specs is None:
            self._specs = gatekinds.load_specs(self.root / "gate-kinds")
        return self._specs

    def spec_for(self, wo_row):
        return query.spec_for(self, wo_row)

    def close(self):
        if self.store is not None:
            self.store.close()


def resources(ctx) -> list:
    """What this server offers. Work-order resources are listed concretely so
    a client can enumerate rather than guess at a URI template."""
    listed = [
        {"uri": "wf://status", "name": "status",
         "description": "every work order, one summary each, plus active agents",
         "mimeType": "application/json"},
        {"uri": "wf://next", "name": "next",
         "description": "the next open work order and the argv that advances it",
         "mimeType": "application/json"},
        {"uri": "wf://agents", "name": "agents",
         "description": "per-agent projection over recorded evidence",
         "mimeType": "application/json"},
        {"uri": "wf://checks", "name": "checks",
         "description": "registered checks and which of them CI runs",
         "mimeType": "application/json"},
    ]
    ctx.require_cache()
    for row in ctx.store.list_work_orders():
        wo = row["wo_id"]
        for kind, note in (("status", "full detail"), ("next", "what advances it"),
                           ("log", "the chain")):
            listed.append({
                "uri": f"wf://{kind}/{wo}", "name": f"{kind} {wo}",
                "description": f"{wo}: {note}", "mimeType": "application/json",
            })
    return listed


def read_resource(ctx, uri: str) -> dict:
    ctx.require_cache()
    if not isinstance(uri, str) or not uri.startswith("wf://"):
        raise ValueError(f"not a wf resource uri: {uri!r}")
    path = uri[len("wf://"):]
    parts = [p for p in path.split("/") if p]
    if not parts:
        raise ValueError("empty resource uri")

    head, rest = parts[0], parts[1:]
    if not rest:
        if head == "status":
            return query.status_body(ctx)
        if head == "next":
            return query.next_body(ctx)
        if head == "agents":
            return query.agents_body(ctx)
        if head == "checks":
            checks = query.registered_checks(ctx)
            return {"checks": checks,
                    "ci_matrix": sorted({c["name"] for c in checks if c["ci"]})}
        raise ValueError(f"unknown resource: {uri}")

    if len(rest) != 1:
        raise ValueError(f"unknown resource: {uri}")
    wo = rest[0]
    if head == "status":
        return query.status_one_body(ctx, wo)
    if head == "next":
        return query.next_body(ctx, wo)
    if head == "log":
        return query.log_body(ctx, wo, attempts=True)
    raise ValueError(f"unknown resource: {uri}")


#: Read-only tools. Resources are the MCP-native way to expose state, but
#: most clients surface *tools* far more readily — a resource often has to be
#: attached by hand. A status server nobody can reach is not a status server,
#: so the same query layer is offered both ways.
TOOLS = [
    {
        "name": "wf_status",
        "description": "Work orders with their stage, evidence and claim. "
                       "With a work order id: full detail and its event list.",
        "inputSchema": {
            "type": "object",
            "properties": {"wo": {"type": "string",
                                  "description": "optional WO-NNN"}},
        },
    },
    {
        "name": "wf_next",
        "description": "What advances a work order: the stage it is in, the "
                       "evidence still missing, and the exact argv that "
                       "records it. With no id, picks an open one.",
        "inputSchema": {
            "type": "object",
            "properties": {"wo": {"type": "string"}},
        },
    },
    {
        "name": "wf_log",
        "description": "A work order's event chain, filterable by event type, "
                       "recording agent and time, newest last.",
        "inputSchema": {
            "type": "object",
            "required": ["wo"],
            "properties": {
                "wo": {"type": "string"},
                "type": {"type": "array", "items": {"type": "string"},
                         "description": "event types, e.g. receipt.red"},
                "recorded_by": {"type": "string"},
                "since": {"type": "string",
                          "description": "RFC3339 UTC, six fractional digits"},
                "n": {"type": "integer",
                      "description": "only the last n; -1 for all"},
                "full": {"type": "boolean",
                         "description": "complete event payloads instead of"
                                        " the compact lines (default false)"},
                "attempts": {"type": "boolean",
                             "description": "include the refusal history"},
            },
        },
    },
    {
        "name": "wf_agents",
        "description": "Per-agent view of what has been recorded: receipts, "
                       "attempts, work orders touched, claims held.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "wf_checks",
        "description": "Registered checks across every gate kind, and which "
                       "of them CI runs.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(ctx, name: str, arguments: dict) -> dict:
    """Every tool is a read. There is deliberately no writing tool here."""
    arguments = arguments or {}
    if name != "wf_checks":
        ctx.require_cache()      # the registry needs no database
    if name == "wf_status":
        wo = arguments.get("wo")
        return query.status_one_body(ctx, wo) if wo else query.status_body(ctx)
    if name == "wf_next":
        return query.next_body(ctx, arguments.get("wo"))
    if name == "wf_log":
        wo = arguments.get("wo")
        if not isinstance(wo, str) or not wo:
            raise ValueError("wf_log needs a work order id")
        n = arguments.get("n")
        if n is not None and not isinstance(n, int):
            raise ValueError("n must be an integer")
        return query.log_body(
            ctx, wo,
            types=arguments.get("type"),
            recorded_by=arguments.get("recorded_by"),
            since=arguments.get("since"),
            tail=n,
            attempts=bool(arguments.get("attempts", True)),
            full=bool(arguments.get("full", False)),
        )
    if name == "wf_agents":
        return query.agents_body(ctx)
    if name == "wf_checks":
        checks = query.registered_checks(ctx)
        return {"checks": checks,
                "ci_matrix": sorted({c["name"] for c in checks if c["ci"]})}
    raise ValueError(f"unknown tool: {name}")


def error(request_id, code, message, data=None):
    body = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": body}


def result(request_id, payload):
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def handle(ctx, request):
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return error(None, INVALID_REQUEST, "not a JSON-RPC 2.0 request")
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if method == "initialize":
        return result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"resources": {}, "tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method in ("notifications/initialized", "initialized"):
        return None            # a notification: no id, no reply
    if method == "ping":
        return result(request_id, {})
    if method == "resources/list":
        try:
            return result(request_id, {"resources": resources(ctx)})
        except WfError as exc:
            return error(request_id, INVALID_PARAMS, str(exc), exc.payload())
    if method == "resources/read":
        uri = params.get("uri")
        try:
            body = read_resource(ctx, uri)
        except ValueError as exc:
            return error(request_id, INVALID_PARAMS, str(exc))
        except WfError as exc:
            # A refusal or an integrity failure is an answer, not a crash.
            return error(request_id, INVALID_PARAMS, str(exc), exc.payload())
        return result(request_id, {"contents": [{
            "uri": uri, "mimeType": "application/json",
            "text": canonical.dumps(body),
        }]})
    if method == "tools/list":
        return result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        try:
            body = call_tool(ctx, name, params.get("arguments") or {})
        except ValueError as exc:
            return error(request_id, INVALID_PARAMS, str(exc))
        except WfError as exc:
            # A refusal is an answer. isError lets the client show it to the
            # model as a result rather than as a transport failure.
            return result(request_id, {
                "content": [{"type": "text", "text": canonical.dumps(exc.payload())}],
                "isError": True,
            })
        return result(request_id, {
            "content": [{"type": "text", "text": canonical.dumps(body)}],
            "isError": False,
        })
    return error(request_id, METHOD_NOT_FOUND, f"unknown method: {method}")


def serve(ctx, stdin, stdout) -> int:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError as exc:
            response = error(None, PARSE_ERROR, f"invalid JSON: {exc}")
        else:
            try:
                response = handle(ctx, request)
            except Exception as exc:  # noqa: BLE001 — a single bad
                # call must not take the server down with it
                response = error(request.get("id") if isinstance(request, dict)
                                 else None, INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="read-only wf status over MCP")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args(argv)
    ctx = ReadOnlyContext(args.root)
    try:
        return serve(ctx, sys.stdin, sys.stdout)
    finally:
        ctx.close()


if __name__ == "__main__":
    sys.exit(main())
