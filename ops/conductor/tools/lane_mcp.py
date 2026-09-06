#!/usr/bin/env python3
"""CLI and stdio MCP projection for bounded conductor lane reads."""

import sys

sys.dont_write_bytecode = True

import errno  # noqa: E402
import fcntl  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import stat  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

from lane_read import (  # noqa: E402
    DIGEST_RE,
    DISCOVERY_ID_RE,
    DISCOVERY_QUERIES,
    JOB_NAME_RE,
    Refusal,
    canonical,
    check_result,
    decode_object,
    discovery_arguments,
    load_config,
    matches,
    refuse,
    strict_json,
)
from lane_read import (  # noqa: E402
    query as read_query,
)

PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
LATEST_PROTOCOL = PROTOCOLS[-1]
MAX_LINE = 65_536
INSTRUCTIONS = (
    "Read-only; evidence is not authority. Use brief before detail. "
    "No live readiness."
)


BOOT_COMPONENTS = tuple(sorted((
    'ops/conductor/discovery-lever.md',
    'ops/conductor/tools/lane_read.py',
    'ops/conductor/tools/lane_mcp.py',
    'ops/conductor/tools/lane_refs.py',
)))
BOOT_REMEDIES = {
    'descriptor-unreadable': 'supply an inherited readable directory descriptor with --discovery-boot-fd FD',
    'component-missing': 'supply all four fixed boot components in the retained artifact',
    'component-unreadable': 'make the fixed boot component readable in the retained artifact',
    'unsafe-path': 'supply fixed boot components beneath the descriptor without symlinks',
    'not-regular': 'supply the fixed boot component as a regular file',
    'component-oversized': 'supply a boot component of at most 1 MiB',
    'total-oversized': 'supply boot components totaling at most 4 MiB',
    'changed-during-read': 'supply a stationary retained boot artifact and relaunch',
    'timeout': 'supply a readable stationary boot artifact within the 10-second bootstrap deadline',
    'binding-unverified': 'use a trusted loader that binds execution inputs to retained boot bytes and relaunch',
    'binding-mismatch': 'load the three discovery modules from the same retained boot bytes and relaunch',
}
_BOOT_FD = None
_BOOT_BYTES = None


def boot_refusal(subject, code):
    refuse('config', 'trusted discovery boot descriptor',
           f'rejected {subject} {code}', BOOT_REMEDIES[code])


def capture_boot(descriptor):
    """Capture the four granted buffers; this does not establish execution."""
    if descriptor is None:
        refuse('config', 'trusted discovery boot descriptor', 'missing',
               'launch with --discovery-boot-fd FD')
    deadline = time.monotonic() + 10
    owned, links, captured = [], [], {}
    total = 0

    def check():
        if time.monotonic() > deadline:
            boot_refusal('descriptor', 'timeout')

    def signature(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)

    try:
        try:
            root = os.dup(descriptor)
            owned.append(root)
            if (not stat.S_ISDIR(os.fstat(root).st_mode)
                    or fcntl.fcntl(root, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
                boot_refusal('descriptor', 'descriptor-unreadable')
        except (OSError, OverflowError):
            boot_refusal('descriptor', 'descriptor-unreadable')
        for path in BOOT_COMPONENTS:
            check()
            parent = root
            parts = path.split('/')
            try:
                for index, part in enumerate(parts):
                    final = index == len(parts) - 1
                    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
                    if not final:
                        flags |= os.O_DIRECTORY
                    child = os.open(part, flags, dir_fd=parent)
                    owned.append(child)
                    info = os.fstat(child)
                    links.append((parent, part, signature(info), path, final, child))
                    parent = child
                if not stat.S_ISREG(info.st_mode):
                    boot_refusal(path, 'not-regular')
                if info.st_size > 1024 * 1024:
                    boot_refusal(path, 'component-oversized')
                check()
                raw = os.pread(child, 1024 * 1024 + 1, 0)
                check()
                if len(raw) > 1024 * 1024:
                    boot_refusal(path, 'component-oversized')
                total += len(raw)
                if total > 4 * 1024 * 1024:
                    boot_refusal('descriptor', 'total-oversized')
                if len(raw) != info.st_size or signature(os.fstat(child)) != signature(info):
                    boot_refusal(path, 'changed-during-read')
                captured[path] = raw
            except OSError as error:
                code = ('component-missing' if error.errno == errno.ENOENT else
                        'unsafe-path' if error.errno in (errno.ELOOP, errno.ENOTDIR) else
                        'component-unreadable')
                boot_refusal(path, code)
        for parent, part, before, path, final, child in links:
            check()
            try:
                after = signature(os.stat(part, dir_fd=parent, follow_symlinks=False))
                current = signature(os.fstat(child))
            except OSError:
                boot_refusal(path, 'changed-during-read')
            if (after != before if final else after[:3] != before[:3]) or current != before:
                boot_refusal(path, 'changed-during-read')
        check()
        return captured
    finally:
        for fd in reversed(owned):
            os.close(fd)


def query(config: dict, name: str, arguments: object) -> dict:
    global _BOOT_BYTES
    if config["version"] != 3 or name not in DISCOVERY_QUERIES:
        return read_query(config, name, arguments)
    discovery_arguments(config, name, arguments)
    if _BOOT_BYTES is None:
        _BOOT_BYTES = capture_boot(_BOOT_FD)
    # Native SourceFileLoader retains a mutable pathname, not the bytes the
    # interpreter executed. Neither reopening that path nor a code-object
    # comparison proves byte equality. The declared trusted-loader counterparty
    # supplies no execution-input interface yet; refuse before opening anchors.
    boot_refusal('ops/conductor/tools/lane_mcp.py', 'binding-unverified')


def _schemas(config: dict[str, object]) -> list[dict[str, object]]:
    annotations = {"readOnlyHint": True, "destructiveHint": False}
    tools = [
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
    if config["version"] >= 2:
        tools.extend(
            [
                {
                    "name": "lane_findings",
                    "description": "Read a bounded page of recorded findings.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "cursor": {"type": "string"},
                        },
                        "required": ["id"],
                        "additionalProperties": False,
                    },
                    "annotations": annotations,
                },
                {
                    "name": "lane_changes",
                    "description": "Compare record bytes with a revision checkpoint.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "checkpoint": {
                                "type": "object",
                                "additionalProperties": {"type": "string"},
                            }
                        },
                        "additionalProperties": False,
                    },
                    "annotations": annotations,
                },
                {
                    "name": "lane_jobs",
                    "description": "Read bounded structural cards from the job registry.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "additionalProperties": False,
                    },
                    "annotations": annotations,
                },
            ]
        )
    if config["version"] == 3:
        for name in DISCOVERY_QUERIES:
            properties = {"profile": {"type": "string", "pattern": "^[a-z][a-z0-9-]{0,31}$"},
                          "snapshot": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}
            fields = {"lane_start": ("cursor",), "lane_homes": ("concept", "cursor"),
                      "lane_handoffs": ("key", "cursor"), "lane_actions": ("name",)}[name]
            patterns = {"concept": "^[a-z][a-z0-9-]{0,63}$", "name": "^[a-z][a-z0-9-]{0,31}$",
                        "key": "^record/[0-9a-f]{64}$",
                        "cursor": ("^[0-9a-f]{64}:([0-9]|1[0-9]|20)$" if name == 'lane_start' else
                                   "^[0-9a-f]{64}:([1-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")}
            properties.update({field: {"type": "string", "pattern": patterns[field]} for field in fields})
            tools.append({"name": name, "description": "Read bounded profile discovery; evidence is not authority.",
                          "inputSchema": {"type": "object", "properties": properties,
                                          "required": ["profile"], "additionalProperties": False},
                          "annotations": annotations})
            if 'cursor' in fields:
                tools[-1]['inputSchema']['dependentRequired'] = {'cursor': ['snapshot']}
                named = next((field for field in fields if field != 'cursor'), None)
                if named is not None:
                    tools[-1]['inputSchema']['not'] = {'required': [named, 'cursor']}
    return tools


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
    if config["version"] >= 2:
        rows.extend(
            (f"lane://findings/{ident}", f"Lane findings {ident}", "First recorded findings page")
            for ident in config["job_ids"]
        )
        rows.extend(
            [
                ("lane://changes", "Lane changes", "Stateless record revision comparison"),
                ("lane://jobs", "Lane jobs", "Bounded job registry cards"),
            ]
        )
    if config["version"] == 3:
        rows.extend((f"lane://{kind}/{profile}", f"Lane {kind} {profile}", "Bounded profile discovery")
                    for profile in config["profiles"] for kind in ("start", "homes", "handoffs", "actions"))
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
    if config["version"] >= 2:
        if isinstance(uri, str) and uri.startswith("lane://findings/"):
            return query(
                config,
                "lane_findings",
                {"id": uri.removeprefix("lane://findings/")},
            )
        if uri == "lane://changes":
            return query(config, "lane_changes", {})
        if uri == "lane://jobs":
            return query(config, "lane_jobs", {})
        if isinstance(uri, str) and uri.startswith("lane://jobs/"):
            return query(config, "lane_jobs", {"name": uri.removeprefix("lane://jobs/")})
    if config["version"] == 3 and isinstance(uri, str) and uri.startswith("lane://"):
        parts = uri[7:].split("/")
        if len(parts) >= 2 and matches(DISCOVERY_ID_RE, parts[1]) and parts[1] in config["profiles"]:
            kind, profile = parts[:2]
            args = {"profile": profile}
            if kind in ("start", "homes", "handoffs", "actions") and len(parts) == 2:
                return query(config, "lane_" + kind, args)
            if kind == "homes" and len(parts) == 3 and matches(JOB_NAME_RE, parts[2]):
                return query(config, "lane_homes", dict(args, concept=parts[2]))
            if kind == "actions" and len(parts) == 3 and matches(DISCOVERY_ID_RE, parts[2]):
                return query(config, "lane_actions", dict(args, name=parts[2]))
            if kind == "handoffs" and len(parts) == 4 and parts[2] == "record" and matches(DIGEST_RE, parts[3]):
                return query(config, "lane_handoffs", dict(args, key="record/" + parts[3]))
    refuse("arguments", "a listed lane resource URI", repr(uri), "select a listed resource")


def _error(identifier: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def _result(identifier: object, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identifier, "result": result}


def _params(request: dict[str, object]) -> dict[str, object]:
    params = request.get("params", {})
    if not isinstance(params, dict):
        raise TypeError
    if "_meta" in params and not isinstance(params["_meta"], dict):
        raise TypeError
    result = dict(params)
    result.pop("_meta", None)
    return result


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
        return None if notification else _error(identifier, -32602, "Invalid params")
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
        return _result(identifier, {"tools": _schemas(config)})
    if method == "resources/list":
        return _result(identifier, {"resources": _resources(config)})
    if method == "resources/templates/list" and config["version"] >= 2:
        return _result(
            identifier,
            {
                "resourceTemplates": ([
                    {
                        "uriTemplate": "lane://jobs/{name}",
                        "name": "Lane job card",
                        "mimeType": "application/json",
                    }
                ] + ([{"uriTemplate": uri, "name": "Lane discovery detail", "mimeType": "application/json"}
                      for uri in ("lane://homes/{profile}/{concept}", "lane://handoffs/{profile}/record/{digest}",
                                  "lane://actions/{profile}/{name}")] if config["version"] == 3 else []))
            },
        )
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
    global _BOOT_FD
    if len(argv) < 3 or argv[0] != "--config":
        refuse(
            "arguments",
            "--config FILE followed by check, serve, or query",
            repr(argv),
            "use the declared command shape",
        )
    rest = argv[2:]
    if rest[0] == '--discovery-boot-fd':
        if len(rest) < 3:
            refuse('arguments', 'a boot descriptor followed by a verb', 'invalid', 'use the declared command shape')
        try:
            _BOOT_FD = int(rest[1])
        except ValueError:
            _BOOT_FD = -1
        rest = rest[2:]
    return Path(argv[1]), rest[0], rest[1:]


def main() -> int:
    try:
        config_path, verb, rest = _cli(sys.argv[1:])
        config = load_config(config_path)
        if verb == "check" and rest in ([], ["."]):
            print(canonical(check_result(config)))
            return 0
        if verb == "serve" and not rest:
            return serve(config)
        if verb == "query" and len(rest) in {1, 2}:
            if config['version'] == 3 and rest[0] in DISCOVERY_QUERIES:
                try:
                    arguments = strict_json(rest[1].encode('utf-8')) if len(rest) == 2 else {}
                except (ValueError, UnicodeError, RecursionError):
                    refuse('arguments', f'closed arguments for {rest[0]}', 'invalid', 'use the declared query schema')
            else:
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
    finally:
        if _BOOT_FD is not None:
            try:
                os.close(_BOOT_FD)
            except (OSError, OverflowError):
                pass  # An unusable inherited descriptor owns nothing to close.


if __name__ == "__main__":
    raise SystemExit(main())
