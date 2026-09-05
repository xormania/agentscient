#!/usr/bin/env python3
"""CLI and stdio MCP projection for bounded conductor lane reads."""

import sys

sys.dont_write_bytecode = True

import json  # noqa: E402
from pathlib import Path  # noqa: E402

from lane_read import (  # noqa: E402
    Refusal,
    canonical,
    check_result,
    decode_object,
    load_config,
    query,
    refuse,
)

PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
LATEST_PROTOCOL = PROTOCOLS[-1]
MAX_LINE = 65_536
INSTRUCTIONS = (
    "Read-only; evidence is not authority. Use brief before detail. "
    "No live readiness."
)


def _schemas() -> list[dict[str, object]]:
    annotations = {"readOnlyHint": True, "destructiveHint": False}
    return [
        {
            "name": "lane_brief",
            "description": "Read the bounded lane brief before requesting detail.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "annotations": annotations,
        },
        {
            "name": "lane_record",
            "description": "Read one explicitly configured dispatch record summary.",
            "inputSchema": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
            },
            "annotations": annotations,
        },
        {
            "name": "lane_alerts",
            "description": "Read a bounded monitor alert page with an explicit cursor.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "after": {"type": "integer", "minimum": 0, "default": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                },
                "additionalProperties": False,
            },
            "annotations": annotations,
        },
        {
            "name": "lane_usage",
            "description": "Read aggregate token usage from the configured rollout tail.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "annotations": annotations,
        },
    ]


def _resources(config: dict[str, object]) -> list[dict[str, str]]:
    rows = [
        ("lane://brief", "Lane brief", "Bounded lane summary without live readiness"),
        ("lane://alerts", "Lane alerts", "Default bounded monitor alert page"),
        ("lane://usage", "Lane usage", "Aggregate configured rollout usage"),
    ]
    rows.extend(
        (f"lane://record/{ident}", f"Lane record {ident}", "Configured dispatch record summary")
        for ident in config["job_ids"]
    )
    return [
        {"uri": uri, "name": name, "description": description, "mimeType": "application/json"}
        for uri, name, description in rows
    ]


def _resource_query(config: dict[str, object], uri: object) -> dict[str, object]:
    if uri == "lane://brief":
        return query(config, "lane_brief", {})
    if uri == "lane://alerts":
        return query(config, "lane_alerts", {})
    if uri == "lane://usage":
        return query(config, "lane_usage", {})
    if isinstance(uri, str) and uri.startswith("lane://record/"):
        return query(config, "lane_record", {"id": uri.removeprefix("lane://record/")})
    refuse("arguments", "a listed lane resource URI", repr(uri), "select a listed resource")


def _error(identifier: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def _result(identifier: object, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identifier, "result": result}


def _params(request: dict[str, object]) -> dict[str, object]:
    params = request.get("params", {})
    if not isinstance(params, dict):
        raise TypeError
    return params


def _dispatch(config: dict[str, object], request: object) -> dict[str, object] | None:
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
        return _error(identifier, -32602, "Invalid params")
    if notification:
        return None
    if method == "initialize":
        requested = params.get("protocolVersion")
        selected = requested if requested in PROTOCOLS else LATEST_PROTOCOL
        return _result(
            identifier,
            {
                "protocolVersion": selected,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {"name": "agentscient-lane", "version": "1"},
                "instructions": INSTRUCTIONS,
            },
        )
    if method == "ping":
        return _result(identifier, {})
    if method == "tools/list":
        return _result(identifier, {"tools": _schemas()})
    if method == "resources/list":
        return _result(identifier, {"resources": _resources(config)})
    if method == "tools/call":
        if set(params) not in ({"name"}, {"name", "arguments"}) or not isinstance(
            params.get("name"), str
        ):
            return _error(identifier, -32602, "Invalid params")
        arguments = params.get("arguments", {})
        try:
            payload = query(config, params["name"], arguments)
        except Refusal as exc:
            return _result(
                identifier,
                {"content": [{"type": "text", "text": exc.line()}], "isError": True},
            )
        text = canonical(payload)
        return _result(
            identifier,
            {
                "content": [{"type": "text", "text": text}],
                "structuredContent": payload,
                "isError": False,
            },
        )
    if method == "resources/read":
        if set(params) != {"uri"}:
            return _error(identifier, -32602, "Invalid params")
        try:
            payload = _resource_query(config, params["uri"])
        except Refusal:
            return _error(identifier, -32602, "Invalid params")
        return _result(
            identifier,
            {
                "contents": [
                    {
                        "uri": params["uri"],
                        "mimeType": "application/json",
                        "text": canonical(payload),
                    }
                ]
            },
        )
    return _error(identifier, -32601, "Method not found")


def _send(message: dict[str, object]) -> None:
    sys.stdout.write(canonical(message) + "\n")
    sys.stdout.flush()


def _reject_constant(value: str) -> None:
    raise ValueError(value)


def serve(config: dict[str, object]) -> int:
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


def _cli(argv: list[str]) -> tuple[Path, str, list[str]]:
    if len(argv) < 3 or argv[0] != "--config":
        refuse(
            "arguments",
            "--config FILE followed by check, serve, or query",
            repr(argv),
            "use the declared command shape",
        )
    return Path(argv[1]), argv[2], argv[3:]


def main() -> int:
    try:
        config_path, verb, rest = _cli(sys.argv[1:])
        config = load_config(config_path)
        if verb == "check" and rest in ([], ["."]):
            print(canonical(check_result()))
            return 0
        if verb == "serve" and not rest:
            return serve(config)
        if verb == "query" and len(rest) in {1, 2}:
            arguments = decode_object(rest[1]) if len(rest) == 2 else {}
            print(canonical(query(config, rest[0], arguments)))
            return 0
        refuse(
            "arguments",
            "check, serve, or query TOOL [JSON]",
            repr([verb, *rest]),
            "use the declared verb and arguments",
        )
    except Refusal as exc:
        print(exc.line(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
