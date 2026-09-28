"""Verified synthetic counterparties for independent conduct startup tests.

Contracts (only): `ops/conductor/conductor-start-plan.md`,
`ops/conductor/permission-surface.md`, `ops/conductor/harness-capabilities.md`,
plus the closed shapes those documents cite in discovery-lever.md,
lane-mcp-lever.md, lane-mcp-v2.md, probes-lever.md, lane-policy.md,
dispatch/CONTRACT.md, task/CONTRACT.md, ladder-lever.md, CONTRACT.md
(board) and go.sh.

Implementation unread. No live harness, credentials, host settings or
admission. Counterparties are test-owned sealed bootstrap slots, an
in-memory reservation, an effects log over actual temporary bytes, a
client child on bound pipes, and a separate server-query receipt that
is not connection proof.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "conduct.py"
BIN = REPO / "ops" / "bin" / "conduct"
POLICY_TOOL = REPO / "ops" / "conductor" / "tools" / "lane_policy.py"
ADAPTERS = REPO / "ops" / "devlane" / "harness" / "adapters.py"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
DISPATCH_ID_RE = re.compile(
    r"^[0-9]{8}T[0-9]{6}Z-conduct-[a-z][a-z0-9-]{0,31}-[0-9a-f]{6}$"
)
REFUSAL_RE = re.compile(
    r"^(?P<cls>[a-z]+(?:-[a-z0-9]+)*): expected .+; found .+; needed .+$"
)
PRINTABLE_ASCII = re.compile(r"^[\x20-\x7e]+$")

SCHEMA_LAUNCH = "conductor-launch/1"
SCHEMA_ARGV = "adapter-argv/1"
SCHEMA_TOOL = "conductor-tool/1"
SCHEMA_DECISION = "conductor-decision/1"
SCHEMA_POLICY = "agentscient.lane-policy/v1"
SCHEMA_LANE = "agentscient.lane/v1"
SCHEMA_DIAGNOSTIC = "conduct-observations/1"
SCHEMA_RELAY = "codex-relay/1"
MECHANISM_SYNTHETIC = "synthetic-display/1"
MECHANISM_CODEX = "codex-sole-client-relay/1"
CODEX_NAMESPACE = "conductor"

BOOTSTRAP_SLOTS = (
    "custody.json",
    "declarations.json",
    "binding.json",
    "transport.json",
    "discovery.json",
    "parent.json",
)
BOOTSTRAP_FD_START = 3
BOOTSTRAP_FD_END = 8
BOOTSTRAP_DEADLINE_S = 10
BOOTSTRAP_SLOT_MAX = 1_048_576
BOOTSTRAP_TOTAL_MAX = 4_194_304
DESCRIPTOR_MAX = 65_536
NESTING_MAX = 32
OBSERVATION_MAX = 65_536
MCP_QUEUE_MAX = 1_048_576
MCP_DEADLINE_S = 10

SYNTHETIC_GRAMMAR = {
    "schema": SCHEMA_ARGV,
    "options": [
        {
            "name": "--display",
            "forms": ["split", "equals"],
            "values": ["compact", "plain"],
            "repeatable": False,
        },
        {
            "name": "--quiet",
            "forms": ["flag"],
            "values": None,
            "repeatable": False,
        },
    ],
}
EMPTY_GRAMMAR = {"schema": SCHEMA_ARGV, "options": []}
GRAMMAR = SYNTHETIC_GRAMMAR
ADMITTED_EQUALS = ["--display=compact", "--quiet"]
ADMITTED_SPLIT = ["--display", "plain"]
ADMITTED_FLAG = ["--quiet"]
ADMITTED_EMPTY: list[str] = []

SECRET_CANARY = "display-SECRET-canary-9f3c-NOT-A-CREDENTIAL"
CANARY_EQUALS = f"--display={SECRET_CANARY}"

REASONS = (
    "direct-edit",
    "git-mutation",
    "shell-escape",
    "raw-vendor",
    "in-session-agent",
    "unknown-tool",
    "malformed-request",
    "binding-mismatch",
)
CONFIG_REASONS = (
    "bootstrap-missing",
    "bootstrap-invalid",
    "bootstrap-untrusted",
    "descriptor-invalid",
    "input-mismatch",
)
DELEGATE_TARGETS = ("dispatch", "go", "ladder")
V3_TOOL_NAMES = (
    "lane_record",
    "lane_alerts",
    "lane_usage",
    "lane_brief",
    "lane_findings",
    "lane_changes",
    "lane_jobs",
    "lane_start",
    "lane_homes",
    "lane_handoffs",
    "lane_actions",
)
V3_TOOLS = 11
OMISSIONS = (
    "no host activation",
    "no live readiness",
    "no role enforcement",
    "no lifecycle publication",
    "no raw documentation dump",
    "HEAD tree only; dirty and untracked files excluded",
    "register ledger prs local readings unavailable",
)
PROFILES = ("dev", "prod", "docs")
WORKER_STAGES = (
    "plan",
    "tests",
    "check-tests",
    "code",
    "review",
    "adjudicate",
)
BOARD_VERBS = ("branches", "prs", "decisions", "dispatches", "all")
GO_INTENTS = (
    "sweep",
    "audit",
    "security",
    "review",
    "plan",
    "tests",
    "check",
    "implement",
    "adjudicate",
)

DESCRIPTOR_KEYS = (
    "schema",
    "launch_id",
    "operation",
    "selection",
    "custody_sha256",
    "policy_binding_sha256",
    "discovery",
    "adapter",
    "forwarded_tokens",
    "mcp",
    "resume",
)
SELECTION_KEYS = (
    "harness",
    "model",
    "effort",
    "role",
    "job_role",
    "profile",
)
ADAPTER_KEYS = (
    "revision",
    "mechanism",
    "grammar_sha256",
    "normalizer_sha256",
    "executable_sha256",
    "config_sha256",
)
MCP_KEYS = ("server_sha256", "config_sha256", "catalogue_sha256")
COMPILED_KEYS = (
    "argv",
    "environment",
    "reservations",
    "capability",
    "binding",
)
LAUNCH_BINDING_KEYS = ("invariant_sha256", "argv_sha256", "operation")
PREPARE_KEYS = ("descriptor", "compiled_launch")
OBSERVATION_KEYS = ("seq", "request", "response")
REQUEST_KEYS = (
    "schema",
    "id",
    "binding_sha256",
    "kind",
    "target",
    "arguments",
)
DECISION_KEYS = (
    "schema",
    "id",
    "binding_sha256",
    "outcome",
    "refusal",
)
DIAGNOSTIC_KEYS = (
    "schema",
    "candidate_sha256",
    "bootstrap_sha256",
    "descriptor_sha256",
    "checked_at",
    "selection",
    "operation",
    "identity",
    "cases",
    "counts",
    "cleanup",
)
DYNAMIC_CALL_KEYS = (
    "threadId",
    "turnId",
    "callId",
    "namespace",
    "tool",
    "arguments",
)
CONDUCTOR_BINDING_KEYS = (
    "policy",
    "selection",
    "dispatch",
    "stage",
    "job",
    "lineage",
    "snapshot_ref",
    "template",
    "declarations_sha256",
    "custody_sha256",
)

HEAD_OID = "0123456789abcdef0123456789abcdef01234567"
SNAPSHOT_REF = "89abcdef0123456789abcdef0123456789abcdef"
POLICY_REF = "fedcba9876543210fedcba9876543210fedcba98"
TEMPLATE_PATH = "ops/conductor/conductor-start-plan.md"
THREAD_ID = "thread-fixture"
TURN_ID = "turn-fixture"
CALL_ID = "call-fixture"

ABSENT_CLI = (
    b"#!/usr/bin/env python3\n"
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)
ABSENT_PREPARE = (
    "def prepare_conductor(trusted_context, selection,"
    " forwarded_tokens, operation):\n"
    "    return None\n"
)
ABSENT_POLICY = (
    "def evaluate_tool(bound_role, normalized_request):\n"
    "    return None\n"
    "def bind_launch(trusted_context, declarations):\n"
    "    return None\n"
)
ABSENT_ADAPTER = (
    "def normalize_tool(bound_context, native_request):\n"
    "    return None\n"
    "def compile_launch(selection, grants, transport,"
    " forwarded_tokens, operation):\n"
    "    return None\n"
)
FAKE_HARNESS = (
    b"#!/usr/bin/env python3\n"
    b"import json, os, pathlib, sys\n"
    b"path = pathlib.Path(os.environ['CONDUCT_TEST_RECEIPT'])\n"
    b"path.write_text(json.dumps({'argv': sys.argv[1:]},"
    b" separators=(',', ':')), encoding='utf-8')\n"
    b"sys.exit(0)\n"
)

_ISSUE = object()


def canonical_dumps(value: object) -> bytes:
    """Startup canonical digest encoding: sorted keys, ASCII, compact, no NL."""
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value: object) -> str:
    return sha256_hex(canonical_dumps(value))


def empty_grant() -> dict:
    return {"repository": [], "outputs": []}


def json_schema_object(
    properties: dict,
    required: list[str] | None = None,
) -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required is not None:
        schema["required"] = required
    return schema


def _string_schema() -> dict:
    return {"type": "string"}


def _id_schema() -> dict:
    return {"type": "string", "pattern": ID_RE.pattern}


def _sha_schema() -> dict:
    return {"type": "string", "pattern": SHA256_RE.pattern}


# Exact owner argument schemas for the eleven v3 tools.
V3_TOOL_SCHEMAS = {
    "lane_record": json_schema_object({"id": _string_schema()}, ["id"]),
    "lane_alerts": json_schema_object(
        {
            "after": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        }
    ),
    "lane_usage": json_schema_object({}),
    "lane_brief": json_schema_object({}),
    "lane_findings": json_schema_object(
        {"id": _string_schema(), "cursor": _string_schema()},
        ["id"],
    ),
    "lane_changes": json_schema_object(
        {"checkpoint": {"type": "object", "additionalProperties": _string_schema()}}
    ),
    "lane_jobs": json_schema_object({"name": _string_schema()}),
    "lane_start": json_schema_object(
        {
            "profile": _id_schema(),
            "snapshot": _sha_schema(),
            "cursor": _string_schema(),
        },
        ["profile"],
    ),
    "lane_homes": json_schema_object(
        {
            "profile": _id_schema(),
            "snapshot": _sha_schema(),
            "concept": _string_schema(),
            "cursor": _string_schema(),
        },
        ["profile"],
    ),
    "lane_handoffs": json_schema_object(
        {
            "profile": _id_schema(),
            "snapshot": _sha_schema(),
            "key": _string_schema(),
            "cursor": _string_schema(),
        },
        ["profile"],
    ),
    "lane_actions": json_schema_object(
        {
            "profile": _id_schema(),
            "snapshot": _sha_schema(),
            "name": _id_schema(),
        },
        ["profile"],
    ),
}


def conduct_config_line(reason: str) -> str:
    if reason not in CONFIG_REASONS:
        raise AssertionError(f"undeclared conduct-config reason {reason!r}")
    return (
        "conduct-config: expected trusted conductor configuration; "
        f"found {reason}; needed run the independent doctor and "
        "restore admitted startup inputs"
    )


def conduct_mcp_line() -> str:
    return (
        "conduct-mcp: expected bound client connection; found unavailable; "
        "needed run the independent doctor and restore verified "
        "connection evidence"
    )


def conduct_argv_line(index: int) -> str:
    return (
        "conduct-argv: expected declared safe tokens; "
        f"found invalid token at index {index}; "
        "needed use the measured adapter grammar or run the independent doctor"
    )


def load_module(path: Path, name: str, stub: str) -> types.ModuleType:
    if path.is_file():
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise AssertionError(f"could not load {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    mod = types.ModuleType(name)
    exec(stub, mod.__dict__)  # noqa: S102  test-owned absent stand-in
    sys.modules[name] = mod
    return mod


def unpack_prepare(result: object) -> tuple[object, object]:
    """Success packaging is exactly {descriptor, compiled_launch}."""
    if not isinstance(result, dict):
        return result, None
    if tuple(sorted(result)) != tuple(sorted(PREPARE_KEYS)):
        return result, None
    return result["descriptor"], result["compiled_launch"]


def _seal_memfd(name: str, data: bytes) -> int:
    flags = os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING
    fd = os.memfd_create(name, flags)
    if data:
        os.write(fd, data)
    os.lseek(fd, 0, os.SEEK_SET)
    seals = (
        fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    )
    fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
    os.lseek(fd, 0, os.SEEK_SET)
    return fd


def json_nesting(value: object) -> int:
    if isinstance(value, dict):
        if not value:
            return 1
        return 1 + max(json_nesting(item) for item in value.values())
    if isinstance(value, list):
        if not value:
            return 1
        return 1 + max(json_nesting(item) for item in value)
    return 0


class EffectsLog:
    """Filesystem, executor calls and reservation effects under the fixture."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.claimed: list[str] = []
        self.children: list[list[str]] = []
        self.prompts: list[str] = []
        self.records: list[Path] = []
        self.executor_calls: list[tuple[str, object]] = []
        self.mcp_calls: list[object] = []
        self.hooks: list[object] = []
        self.transport_writes: list[str] = []
        self.baseline: dict[str, str] = {}

    def capture(self) -> None:
        self.baseline = self._digest_tree()

    def note(self, kind: str, payload: object = None) -> None:
        self.executor_calls.append((kind, payload))

    def _digest_tree(self) -> dict[str, str]:
        found: dict[str, str] = {}
        if not self.root.exists():
            return found
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                rel = str(path.relative_to(self.root))
                found[rel] = sha256_hex(path.read_bytes())
        return found

    def delta(self) -> tuple[list[str], list[str], list[str]]:
        now = self._digest_tree()
        added = sorted(set(now) - set(self.baseline))
        removed = sorted(set(self.baseline) - set(now))
        changed = sorted(
            key
            for key in set(now) & set(self.baseline)
            if now[key] != self.baseline[key]
        )
        return added, removed, changed

    def record_paths(self) -> list[Path]:
        found = []
        if not self.root.exists():
            return found
        for path in sorted(self.root.rglob("record.json")):
            if path.is_file() and not path.is_symlink():
                found.append(path)
        return found


class FakeDispatch:
    """In-memory DispatchID reservation. No job directory until claim."""

    def __init__(
        self, harness: str = "codex", effects: EffectsLog | None = None
    ) -> None:
        self.harness = harness
        self.reserved: str | None = None
        self.claimed_path: Path | None = None
        self.mutations: list[str] = []
        self.effects = effects

    def reserve(self, *, operation: str) -> str:
        if operation == "resume" and self.reserved:
            return self.reserved
        self.reserved = f"20260906T120000Z-conduct-{self.harness}-a1b2c3"
        self.mutations.append(f"reserve:{self.reserved}")
        if self.effects is not None:
            self.effects.note("reserve", self.reserved)
        return self.reserved

    def claim(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.claimed_path = path
        self.mutations.append(f"claim:{path}")
        if self.effects is not None:
            self.effects.claimed.append(str(path))
            self.effects.note("claim", str(path))


class FakeMcpClient:
    """Actual MCP client child on bound server pipes.

    Observations are {seq,request,response} on the supervisor pipe.
    Absence of those observations is not a server miss.
    """

    def __init__(
        self,
        *,
        connect: bool,
        envelope: dict,
        catalogue: dict,
        invalid_params: bool = False,
        epoch: int = 0,
        endpoint: str = "bound-app-server",
    ) -> None:
        self.connect = connect
        self.envelope = envelope
        self.catalogue = catalogue
        self.invalid_params = invalid_params
        self.epoch = epoch
        self.endpoint = endpoint
        self.calls: list[object] = []
        self.observations: list[dict] = []
        self.reaped = False

    def emit_connection(self, *, profile: str = "dev") -> list[dict]:
        """Run the three-step gate as the actual client child."""
        self.calls = []
        self.observations = []
        if not self.connect:
            return []
        rows = []
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "conduct-client", "version": "0"},
            },
        }
        init_res = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "agentscient-lane", "version": "3"},
                "instructions": (
                    "read-only; evidence not authority; use brief then detail; "
                    "no live readiness."
                ),
            },
        }
        self.calls.append("initialize")
        rows.append({"seq": 0, "request": init_req, "response": init_res})
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        list_res = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": self.catalogue,
        }
        self.calls.append("tools/list")
        rows.append({"seq": 1, "request": list_req, "response": list_res})
        call_args = {"profile": profile}
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "lane_start", "arguments": call_args},
        }
        self.calls.append(("tools/call", "lane_start", call_args))
        if self.invalid_params:
            call_res = {
                "jsonrpc": "2.0",
                "id": 3,
                "error": {"code": -32602, "message": "Invalid params"},
            }
        else:
            call_res = {
                "jsonrpc": "2.0",
                "id": 3,
                "result": self.envelope,
            }
        rows.append({"seq": 2, "request": call_req, "response": call_res})
        for row in rows:
            row["endpoint"] = self.endpoint
            row["epoch"] = self.epoch
        self.observations = rows
        return rows


class FakeMcpServer:
    """Separate CLI/server query. Contract: not connection proof."""

    def __init__(self, envelope: dict, catalogue: dict) -> None:
        self.envelope = envelope
        self.catalogue = catalogue
        self.queries: list[object] = []
        self.self_digest = canonical_digest({"server": "self-reported"})

    def query(self, name: str, arguments: dict) -> dict:
        self.queries.append(("query", name, arguments))
        return self.envelope

    def tools_list(self) -> dict:
        self.queries.append("tools/list")
        return self.catalogue


class BoundTarget:
    """Opaque verified target handle. Views are owner evidence, not JSON."""

    def __init__(
        self,
        *,
        kind: str,
        target: str,
        schema: dict,
        declaration: dict,
        execution: dict,
        grants: dict,
        effects: dict,
        token: object,
    ) -> None:
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_schema", schema)
        object.__setattr__(self, "_declaration", declaration)
        object.__setattr__(self, "_execution", execution)
        object.__setattr__(self, "_grants", grants)
        object.__setattr__(self, "_effects", effects)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("bound target is immutable")

    @property
    def schema(self) -> dict:
        return dict(self._schema)

    @property
    def declaration(self) -> dict:
        return dict(self._declaration)

    @property
    def execution(self) -> dict:
        return dict(self._execution)

    @property
    def grants(self) -> dict:
        return dict(self._grants)

    @property
    def effects(self) -> dict:
        return dict(self._effects)

    def validate_arguments(self, arguments: object) -> bool:
        if not isinstance(arguments, dict):
            return False
        schema = self._schema
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties") is False and any(
            key not in properties for key in arguments
        )
        if extra:
            return False
        return all(key in arguments for key in required)


class BoundRole:
    """Immutable in-process capability. Not JSON and not a duck mapping."""

    def __init__(
        self,
        *,
        descriptor: dict,
        binding: dict,
        tools: dict[tuple[str, str], BoundTarget],
        current: bool,
        token: object,
    ) -> None:
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_descriptor", descriptor)
        object.__setattr__(self, "_binding", binding)
        object.__setattr__(self, "_tools", tools)
        object.__setattr__(self, "_current", current)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("bound role is immutable")

    def descriptor_digest(self) -> str:
        return canonical_digest(self._descriptor)

    def policy_binding(self) -> types.MappingProxyType:
        return types.MappingProxyType(self._binding)

    def is_current(self) -> bool:
        return self._current

    def resolve_tool(self, kind: str, target: str) -> BoundTarget | None:
        return self._tools.get((kind, target))


class BoundContext:
    """Adapter-owned opaque handle: bound_role plus mechanism and intercepts."""

    def __init__(
        self,
        *,
        role: BoundRole,
        mechanism: str,
        token: object,
    ) -> None:
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_role", role)
        object.__setattr__(self, "_mechanism", mechanism)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("bound context is immutable")

    def bound_role(self) -> BoundRole:
        return self._role

    def mechanism(self) -> str:
        return self._mechanism


class TrustedContext:
    """In-process trusted context. Attribute assignment confers no authority."""

    def __init__(self, held: dict, token: object) -> None:
        object.__setattr__(self, "_held", held)
        object.__setattr__(self, "_token", token)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "trusted context is immutable; inject faults at the binder"
        )

    def get(self, name: str, default: object = None) -> object:
        return self._held.get(name, default)


class SealedBootstrap:
    """FD 3 through FD 8 as sealed anonymous buffers of held caller inputs."""

    def __init__(
        self, slots: dict[str, bytes], *, present: tuple[str, ...] | None = None
    ) -> None:
        self.slots = dict(slots)
        self.present = BOOTSTRAP_SLOTS if present is None else present
        self.fds: list[int] = []
        self.kinds: dict[str, str] = dict.fromkeys(BOOTSTRAP_SLOTS, "sealed")

    def open(self, *, kinds: dict[str, str] | None = None) -> list[int]:
        self.close()
        if kinds:
            self.kinds.update(kinds)
        fds: list[int] = []
        for name in BOOTSTRAP_SLOTS:
            if name not in self.present:
                continue
            kind = self.kinds.get(name, "sealed")
            data = self.slots.get(name, b"")
            if kind == "pipe":
                read_fd, write_fd = os.pipe()
                os.write(write_fd, data[: min(len(data), 65536)])
                os.close(write_fd)
                fds.append(read_fd)
            elif kind == "writable":
                fd = os.memfd_create(name, os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
                os.write(fd, data)
                os.lseek(fd, 0, os.SEEK_SET)
                fds.append(fd)
            else:
                fds.append(_seal_memfd(name, data))
        self.fds = fds
        return fds

    def close(self) -> None:
        for fd in self.fds:
            with contextlib.suppress(OSError):
                os.close(fd)
        self.fds = []


class FixtureBinder:
    """Trusted fixture binder. Faults enter at the source/transport boundary."""

    def __init__(self, fixture: ConductFixture) -> None:
        self.fixture = fixture
        self.token = _ISSUE
        self.issued_roles: list[BoundRole] = []
        self.issued_contexts: list[BoundContext] = []

    def mint_role(
        self,
        *,
        descriptor: dict,
        binding: dict,
        tools: dict[tuple[str, str], BoundTarget] | None = None,
        current: bool = True,
    ) -> BoundRole:
        role = BoundRole(
            descriptor=descriptor,
            binding=binding,
            tools=tools or {},
            current=current,
            token=self.token,
        )
        self.issued_roles.append(role)
        return role

    def mint_context_handle(self, role: BoundRole, mechanism: str) -> BoundContext:
        handle = BoundContext(role=role, mechanism=mechanism, token=self.token)
        self.issued_contexts.append(handle)
        return handle

    def lookalike_role(self, role: BoundRole) -> dict:
        return {
            "descriptor_sha256": role.descriptor_digest(),
            "binding": dict(role.policy_binding()),
            "tools": {},
        }

    def issued(self, handle: object) -> bool:
        token = getattr(handle, "_token", None)
        return token is self.token


class ConductFixture(unittest.TestCase):
    """Scratch HOME, planted fake executable, isolated effects."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="conduct-")
        root = Path(self._tmp.name)
        self.root = root
        self.home = root / "home"
        self.work = root / "work"
        self.scratch = root / "scratch"
        self.cwd = root / "cwd"
        self.repo_root = root / "repo"
        for path in (
            self.home,
            self.work,
            self.scratch,
            self.cwd,
            self.repo_root,
        ):
            path.mkdir()
        self.effects = EffectsLog(root)
        self.dispatch = FakeDispatch(effects=self.effects)
        self.receipt = self.work / "harness-receipt.json"
        self.executable = self.work / "fake-harness"
        self.plant_bytes(self.executable, FAKE_HARNESS)
        self.executable.chmod(self.executable.stat().st_mode | stat.S_IEXEC)
        self.config_path = self.work / "lane-mcp-v3.json"
        self.config_obj = self.make_v3_config()
        self.config_bytes = canonical_dumps(self.config_obj)
        self.plant_bytes(self.config_path, self.config_bytes)
        self.boot_contract = b"discovery-lever fixture bytes for D-A47\n"
        self.synthetic_grammar_bytes = canonical_dumps(SYNTHETIC_GRAMMAR)
        self.empty_grammar_bytes = canonical_dumps(EMPTY_GRAMMAR)
        self.grammar_bytes = self.synthetic_grammar_bytes
        self.grammar_sha256 = sha256_hex(self.grammar_bytes)
        self.empty_grammar_sha256 = sha256_hex(self.empty_grammar_bytes)
        self.normalizer_sha256 = sha256_hex(b"pinned-normalizer-fixture\n")
        self.adapter_revision = sha256_hex(b"adapter-revision-fixture\n")
        self.executable_sha256 = sha256_hex(FAKE_HARNESS)
        self.config_sha256 = sha256_hex(self.config_bytes)
        self.custody_bytes = b"trusted-caller-custody-anchor-v1\n"
        self.custody_sha256 = sha256_hex(self.custody_bytes)
        self.catalogue = self.make_catalogue()
        self.catalogue_sha256 = canonical_digest(self.catalogue)
        self.server_sha256 = sha256_hex(b"pinned-server-runtime-closure\n")
        self.envelope = self.make_envelope("dev")
        self.mcp_client = FakeMcpClient(
            connect=True,
            envelope=self.envelope,
            catalogue=self.catalogue,
        )
        self.mcp_server = FakeMcpServer(self.envelope, self.catalogue)
        self.binder = FixtureBinder(self)
        self._bootstrap: SealedBootstrap | None = None
        self.cli_entry = TOOL if TOOL.is_file() else self.scratch / "conduct.py"
        if not TOOL.is_file():
            self.plant_bytes(self.cli_entry, ABSENT_CLI)
            self.cli_entry.chmod(self.cli_entry.stat().st_mode | stat.S_IEXEC)
        self.effects.capture()
        self.assertFalse(
            (self.home / ".local" / "state" / "agentscient" / "dispatch").exists(),
            "plant: isolated store must start absent",
        )

    def tearDown(self) -> None:
        if self._bootstrap is not None:
            self._bootstrap.close()
        self._tmp.cleanup()

    def plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def env(self, extra: dict | None = None) -> dict:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["XDG_STATE_HOME"] = str(self.home / ".local" / "state")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["CONDUCT_TEST_RECEIPT"] = str(self.receipt)
        env.pop("WF_AGENT", None)
        env.pop("CLAUDE_SESSION_ID", None)
        if extra:
            for key, value in extra.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
        return env

    def make_v3_config(self, extra_profile: bool = True) -> dict:
        repo = str(self.repo_root)
        gitdir = str(self.repo_root / ".git")
        (self.repo_root / ".git").mkdir(exist_ok=True)
        dev = {
            "label": "development machinery",
            "work_roots": ["ops/"],
            "homes": ["lane-mcp", "dispatch", "onboard"],
            "startup_homes": ["lane-mcp", "dispatch", "onboard"],
            "source_ids": ["repo"],
            "lineage": "dev",
        }
        prod = {
            "label": "Symfony application",
            "work_roots": ["src/", "packages/", "config/", "public/"],
            "homes": ["mapping", "packages", "projections"],
            "startup_homes": ["mapping", "packages", "projections"],
            "source_ids": ["repo"],
            "lineage": "prod",
        }
        profiles = {"dev": dev, "prod": prod}
        if extra_profile:
            profiles["docs"] = {
                "label": "documentation",
                "work_roots": ["docs/"],
                "homes": ["wire", "onboard"],
                "startup_homes": ["wire"],
                "source_ids": ["repo"],
                "lineage": "docs",
            }
        return {
            "version": 3,
            "dispatch_store": "store",
            "job_ids": ["jobaa41cnd1"],
            "monitor_state": "monitor",
            "consumer": "conductor",
            "usage_rollout": "rollout.jsonl",
            "job_registry": "jobs.json",
            "profiles": profiles,
            "discovery": {
                "audience": "conductor",
                "anchors": {
                    "repo": repo,
                    "gitdir": gitdir,
                    "common": gitdir,
                },
                "repository": {
                    "id": "repo",
                    "root": "repo",
                    "gitdir": "gitdir",
                    "common_gitdir": "common",
                    "head": HEAD_OID,
                    "ref": None,
                },
                "retained_refs": None,
                "dispatch": None,
                "record_bindings": [],
                "work_bindings": [],
            },
        }

    def anchors(self) -> list[dict]:
        rows = []
        for ident, path in (
            ("common", self.repo_root / ".git"),
            ("gitdir", self.repo_root / ".git"),
            ("repo", self.repo_root),
        ):
            info = path.stat()
            rows.append(
                {
                    "id": ident,
                    "device": int(info.st_dev),
                    "inode": int(info.st_ino),
                }
            )
        rows.sort(key=lambda row: row["id"])
        return rows

    def make_catalogue(self) -> dict:
        self.assertEqual(len(V3_TOOL_NAMES), V3_TOOLS)
        tools = []
        for name in V3_TOOL_NAMES:
            schema = V3_TOOL_SCHEMAS[name]
            tools.append(
                {
                    "name": name,
                    "description": name,
                    "inputSchema": schema,
                    "annotations": {
                        "readOnlyHint": True,
                        "destructiveHint": False,
                    },
                }
            )
        return {"tools": tools}

    def make_envelope(
        self,
        profile: str,
        *,
        unavailable: bool = False,
        handoff_complete: bool = False,
        work: list | None = None,
    ) -> dict:
        snapshot = sha256_hex(f"snapshot-{profile}".encode("ascii"))
        selection = {
            "selection": "unknown" if not handoff_complete else "none",
            "selected_key": None,
            "current": None if not handoff_complete else 0,
            "stale": None if not handoff_complete else 0,
            "unknown": None if not handoff_complete else 0,
            "complete": handoff_complete,
        }
        sources = [
            {
                "id": "repo",
                "state": "unavailable" if unavailable else "ok",
                "reason": "unavailable" if unavailable else None,
            }
        ]
        data = {
            "law": [
                {
                    "path": "AGENTS.md",
                    "status": "present",
                    "one_liner": "the operating contract",
                }
            ],
            "state_sources": [
                {
                    "name": "register",
                    "status": "unavailable" if unavailable else "ok",
                    "summary": None,
                    "reason": "unsupported" if unavailable else None,
                    "evidence": [],
                }
            ],
            "homes": [
                {
                    "concept": "wire",
                    "home": "docs/wire.md",
                    "entrypoint": None,
                    "document_present": True,
                    "implementation_present": False,
                }
            ],
            "work": [] if work is None else work,
            "handoffs": selection,
            "actions": [],
            "omissions": list(OMISSIONS),
        }
        return {
            "schema": SCHEMA_LANE,
            "query": "lane_start",
            "state": "ok",
            "reason": None,
            "profile": profile,
            "snapshot": snapshot,
            "sources": sources,
            "data": data,
        }

    def selection(
        self,
        *,
        harness: str = "codex",
        model: str = "fixture-model",
        effort: str | None = None,
        role: str = "conductor",
        job_role: None = None,
        profile: str = "dev",
    ) -> dict:
        body = {
            "harness": harness,
            "model": model,
            "effort": effort,
            "role": role,
            "job_role": job_role,
            "profile": profile,
        }
        self.assertEqual(sorted(body), sorted(SELECTION_KEYS))
        return body

    def declarations(self, selection: dict) -> dict:
        return {
            "selection": selection,
            "requested_scope": empty_grant(),
            "job_grants": empty_grant(),
            "role_grants": empty_grant(),
            "adapter_grants": empty_grant(),
            "outputs": [],
            "reservations": ["last-message.json", "COMMIT_MSG"],
            "sources": [
                {
                    "component": "selection",
                    "kind": "invocation",
                    "path": "selection",
                    "ref": None,
                    "sha256": canonical_digest(selection),
                },
                {
                    "component": "scope",
                    "kind": "absent",
                    "path": None,
                    "ref": None,
                    "sha256": None,
                },
                {
                    "component": "job",
                    "kind": "absent",
                    "path": None,
                    "ref": None,
                    "sha256": None,
                },
                {
                    "component": "role",
                    "kind": "git",
                    "path": TEMPLATE_PATH,
                    "ref": POLICY_REF,
                    "sha256": sha256_hex(b"startup-template\n"),
                },
                {
                    "component": "adapter",
                    "kind": "invocation",
                    "path": "adapter",
                    "ref": None,
                    "sha256": self.adapter_revision,
                },
                {
                    "component": "outputs",
                    "kind": "absent",
                    "path": None,
                    "ref": None,
                    "sha256": None,
                },
                {
                    "component": "reservations",
                    "kind": "invocation",
                    "path": "reservations",
                    "ref": None,
                    "sha256": sha256_hex(b"reservations\n"),
                },
            ],
        }

    def policy_binding(self, profile: str) -> dict:
        grants = {
            "scope": empty_grant(),
            "job": empty_grant(),
            "role": empty_grant(),
            "adapter": empty_grant(),
            "outputs": empty_grant(),
            "maintenance": [],
        }
        template_sha = sha256_hex(b"startup-template\n")
        return {
            "schema": SCHEMA_POLICY,
            "path": "ops/lane-policy.json",
            "ref": POLICY_REF,
            "sha256": sha256_hex(b"lane-policy-blob\n"),
            "admission": {
                "record": "d-lanes-1",
                "sha256": sha256_hex(b"show-stdout\n"),
            },
            "profile": profile,
            "template_sha256": template_sha,
            "grants_sha256": canonical_digest(grants),
            "maintenance": None,
        }

    def conductor_binding(self, selection: dict, launch_id: str) -> dict:
        decls = self.declarations(selection)
        policy = self.policy_binding(selection["profile"])
        return {
            "policy": policy,
            "selection": selection,
            "dispatch": launch_id,
            "stage": "conduct",
            "job": None,
            "lineage": {
                "branch": "lane/conduct-start-tests-20260906",
                "base_sha": SNAPSHOT_REF,
            },
            "snapshot_ref": SNAPSHOT_REF,
            "template": {
                "path": TEMPLATE_PATH,
                "sha256": policy["template_sha256"],
            },
            "declarations_sha256": canonical_digest(decls),
            "custody_sha256": self.custody_sha256,
        }

    def adapter_object(self, *, mechanism: str = MECHANISM_SYNTHETIC) -> dict:
        grammar_sha = (
            self.empty_grammar_sha256
            if mechanism == MECHANISM_CODEX
            else self.grammar_sha256
        )
        return {
            "revision": self.adapter_revision,
            "mechanism": mechanism,
            "grammar_sha256": grammar_sha,
            "normalizer_sha256": self.normalizer_sha256,
            "executable_sha256": self.executable_sha256,
            "config_sha256": self.config_sha256,
        }

    def mcp_object(self) -> dict:
        return {
            "server_sha256": self.server_sha256,
            "config_sha256": self.config_sha256,
            "catalogue_sha256": self.catalogue_sha256,
        }

    def capability(self, selection: dict, operation: str, *, mechanism: str) -> dict:
        adapter = self.adapter_object(mechanism=mechanism)
        return {
            "harness": {
                "name": selection["harness"],
                "version": "fixture-1",
                "executable": {
                    "path": str(self.executable),
                    "sha256": self.executable_sha256,
                },
            },
            "adapter": {
                "revision": adapter["revision"],
                "mechanism": adapter["mechanism"],
                "config_sha256": adapter["config_sha256"],
                "grammar_sha256": adapter["grammar_sha256"],
                "normalizer_sha256": adapter["normalizer_sha256"],
            },
            "platform": {
                "os": "linux",
                "sandbox": {"name": "none", "version": "none"},
                "filesystem": {
                    "name": "posix",
                    "alias_semantics": "literal",
                },
            },
            "role": "conductor",
            "operation": operation,
            "policy": {
                "blob_sha256": sha256_hex(b"lane-policy-blob\n"),
                "evaluator_sha256": sha256_hex(b"evaluator-closure\n"),
            },
            "scope": {
                "source_reads": [str(self.repo_root)],
                "source_write_denials": [str(self.repo_root)],
                "outputs": [],
                "limits": [],
            },
            "contracts": {
                "outputs_sha256": sha256_hex(b"outputs-contract\n"),
                "tools_sha256": sha256_hex(b"tools-contract\n"),
            },
            "mcp": self.mcp_object(),
            "probe": {"revision": sha256_hex(b"probe-rev\n")},
            "mock": {
                "revision": sha256_hex(b"mock-rev\n"),
                "verification": {
                    "path": "ops/conductor/tests/conduct_test_support.py",
                    "sha256": sha256_hex(b"verification\n"),
                },
            },
        }

    def frontend_schema(self, target: str) -> dict:
        if target == "dispatch":
            return json_schema_object(
                {
                    "job": _string_schema(),
                    "harness": _id_schema(),
                    "model": _string_schema(),
                    "effort": {"type": ["string", "null"]},
                    "ref": _string_schema(),
                    "lineage": _string_schema(),
                    "unit": _string_schema(),
                    "stage": {"type": "string", "enum": list(WORKER_STAGES)},
                    "scope": _string_schema(),
                    "input": {"type": "array", "items": _string_schema()},
                    "follows": {"type": "array", "items": _string_schema()},
                    "override": {"type": "array", "items": _string_schema()},
                },
                ["job", "harness", "model", "ref"],
            )
        if target == "go":
            return json_schema_object(
                {
                    "intent": {"type": "string", "enum": list(GO_INTENTS)},
                    "branch": _string_schema(),
                    "scope": _string_schema(),
                },
                ["intent", "branch", "scope"],
            )
        if target == "ladder":
            return json_schema_object(
                {
                    "scope": _string_schema(),
                    "branch": _string_schema(),
                    "plan": _string_schema(),
                    "resume": _string_schema(),
                },
                ["scope", "branch"],
            )
        raise AssertionError(f"undeclared frontend {target}")

    def frontend_request(self, target: str) -> dict:
        if target == "dispatch":
            return {
                "job": "author-tests",
                "harness": "grok",
                "model": "fixture-model",
                "ref": SNAPSHOT_REF,
            }
        if target == "go":
            return {
                "intent": "tests",
                "branch": ".",
                "scope": "author independent startup tests",
            }
        if target == "ladder":
            return {
                "scope": "author independent startup tests",
                "branch": "lane/conduct-start-tests-20260906",
            }
        raise AssertionError(f"undeclared frontend {target}")

    def git_state_schema(self) -> dict:
        return json_schema_object({})

    def board_read_schema(self) -> dict:
        return json_schema_object(
            {
                "section": {"type": "string", "enum": list(BOARD_VERBS)},
                "json": {"type": "boolean"},
                "offline": {"type": "boolean"},
            },
            ["section"],
        )

    def target_handle(
        self,
        *,
        kind: str,
        target: str,
        schema: dict,
        executable: str | None = None,
    ) -> BoundTarget:
        declaration_bytes = canonical_dumps(
            {"kind": kind, "target": target, "schema": schema}
        )
        declaration = {
            "path": f"fixture/{kind}/{target}.json",
            "ref": POLICY_REF,
            "sha256": sha256_hex(declaration_bytes),
        }
        execution = {
            "executable": executable or str(self.executable),
            "cwd": str(self.cwd),
            "environment": {},
        }
        return BoundTarget(
            kind=kind,
            target=target,
            schema=schema,
            declaration=declaration,
            execution=execution,
            grants={"source_reads": [str(self.repo_root)]},
            effects={"writes": []},
            token=self.binder.token,
        )

    def issued_role(
        self,
        *,
        selection: dict | None = None,
        include_frontends: bool = True,
        include_reads: bool = True,
        current: bool = True,
    ) -> BoundRole:
        selection = selection or self.selection()
        launch_id = self.dispatch.reserve(operation="launch")
        descriptor = self.expected_descriptor(
            selection, list(ADMITTED_EMPTY), "launch", launch_id
        )
        binding = self.conductor_binding(selection, launch_id)
        tools: dict[tuple[str, str], BoundTarget] = {}
        if include_frontends:
            for name in DELEGATE_TARGETS:
                tools[("delegate", name)] = self.target_handle(
                    kind="delegate",
                    target=name,
                    schema=self.frontend_schema(name),
                )
        if include_reads:
            tools[("read", "git-state")] = self.target_handle(
                kind="read",
                target="git-state",
                schema=self.git_state_schema(),
            )
            tools[("read", "board")] = self.target_handle(
                kind="read",
                target="board",
                schema=self.board_read_schema(),
            )
        return self.binder.mint_role(
            descriptor=descriptor,
            binding=binding,
            tools=tools,
            current=current,
        )

    def issued_bound_context(
        self,
        *,
        mechanism: str = MECHANISM_CODEX,
        role: BoundRole | None = None,
    ) -> BoundContext:
        role = role or self.issued_role()
        return self.binder.mint_context_handle(role, mechanism)

    def dynamic_tool_call(
        self,
        tool: str,
        arguments: dict,
        *,
        thread_id: str = THREAD_ID,
        turn_id: str = TURN_ID,
        call_id: str = CALL_ID,
    ) -> dict:
        body = {
            "threadId": thread_id,
            "turnId": turn_id,
            "callId": call_id,
            "namespace": CODEX_NAMESPACE,
            "tool": tool,
            "arguments": arguments,
        }
        self.assertEqual(sorted(body), sorted(DYNAMIC_CALL_KEYS))
        return body

    def relay_rpc(self, method: str, params: dict, *, rpc_id: int = 7) -> dict:
        return {"id": rpc_id, "method": method, "params": params}

    def expected_descriptor(
        self,
        selection: dict,
        tokens: list[str],
        operation: str,
        launch_id: str,
        *,
        parent: dict | None = None,
        mechanism: str = MECHANISM_SYNTHETIC,
    ) -> dict:
        binding = self.conductor_binding(selection, launch_id)
        resume = None
        if operation == "resume":
            self.assertIsNotNone(parent)
            resume = {
                "parent_descriptor_sha256": canonical_digest(parent),
                "session_binding_sha256": canonical_digest({"id": "session-fixture"}),
            }
        return {
            "schema": SCHEMA_LAUNCH,
            "launch_id": launch_id,
            "operation": operation,
            "selection": selection,
            "custody_sha256": self.custody_sha256,
            "policy_binding_sha256": canonical_digest(binding),
            "discovery": {
                "config_sha256": self.config_sha256,
                "repository": self.config_obj["discovery"]["repository"],
                "anchors": self.anchors(),
            },
            "adapter": self.adapter_object(mechanism=mechanism),
            "forwarded_tokens": list(tokens),
            "mcp": self.mcp_object(),
            "resume": resume,
        }

    def slot_bytes(
        self,
        *,
        selection: dict,
        operation: str,
        parent: dict | None,
        mechanism: str,
        parent_bytes: bytes | None = None,
        custody_bytes: bytes | None = None,
        discovery_config: bytes | None = None,
        discovery_anchors: list | None = None,
        interception: bool = True,
    ) -> dict[str, bytes]:
        launch_id = self.dispatch.reserved or self.dispatch.reserve(operation=operation)
        decls = self.declarations(selection)
        binding = self.conductor_binding(selection, launch_id)
        transport = {
            "mechanism": mechanism,
            "executable": {
                "path": str(self.executable),
                "sha256": self.executable_sha256,
            },
            "grammar": EMPTY_GRAMMAR
            if mechanism == MECHANISM_CODEX
            else SYNTHETIC_GRAMMAR,
            "interception": interception,
            "relay": None if mechanism != MECHANISM_CODEX else {"schema": SCHEMA_RELAY},
        }
        if parent_bytes is None:
            parent_payload = b"null" if parent is None else canonical_dumps(parent)
        else:
            parent_payload = parent_bytes
        return {
            "custody.json": custody_bytes
            if custody_bytes is not None
            else self.custody_bytes,
            "declarations.json": canonical_dumps(decls),
            "binding.json": canonical_dumps(binding),
            "transport.json": canonical_dumps(transport),
            "discovery.json": discovery_config
            if discovery_config is not None
            else self.config_bytes,
            "parent.json": parent_payload,
        }

    def make_context(
        self,
        *,
        selection: dict | None = None,
        operation: str = "launch",
        parent: dict | None = None,
        mechanism: str = MECHANISM_SYNTHETIC,
        parent_bytes: bytes | None = None,
        custody_bytes: bytes | None = None,
        candidate_origin: bool = False,
        missing_slots: tuple[str, ...] = (),
        slot_kinds: dict[str, str] | None = None,
        discovery_anchors: list | None = None,
        discovery_config: bytes | None = None,
        interception: bool = True,
        extra_profile: bool = True,
    ) -> TrustedContext:
        selection = selection or self.selection()
        if not extra_profile:
            self.config_obj = self.make_v3_config(extra_profile=False)
            self.config_bytes = canonical_dumps(self.config_obj)
            self.config_sha256 = sha256_hex(self.config_bytes)
        launch_id = self.dispatch.reserve(operation=operation)
        binding = self.conductor_binding(selection, launch_id)
        decls = self.declarations(selection)
        present = tuple(name for name in BOOTSTRAP_SLOTS if name not in missing_slots)
        slots = self.slot_bytes(
            selection=selection,
            operation=operation,
            parent=parent,
            mechanism=mechanism,
            parent_bytes=parent_bytes,
            custody_bytes=custody_bytes,
            discovery_config=discovery_config,
            discovery_anchors=discovery_anchors,
            interception=interception,
        )
        held = {
            "binding": binding,
            "declarations": decls,
            "custody_anchor": self.custody_bytes if not candidate_origin else None,
            "custody_sha256": self.custody_sha256,
            "operation": operation,
            "selection": selection,
            "mechanism": mechanism,
            "parent": parent,
            "slots": slots,
            "present": present,
            "slot_kinds": slot_kinds or {},
            "candidate_origin": candidate_origin,
            "interception": interception,
            "discovery_anchors": discovery_anchors
            if discovery_anchors is not None
            else self.anchors(),
            "dispatch": self.dispatch,
            "effects": self.effects,
            "mcp_client": self.mcp_client,
            "mcp_server": self.mcp_server,
        }
        return TrustedContext(held, self.binder.token)

    def open_bootstrap(self, ctx: TrustedContext) -> list[int]:
        slots = ctx.get("slots")
        present = ctx.get("present")
        kinds = ctx.get("slot_kinds")
        assert isinstance(slots, dict)
        assert isinstance(present, tuple)
        if self._bootstrap is not None:
            self._bootstrap.close()
        self._bootstrap = SealedBootstrap(slots, present=present)
        return self._bootstrap.open(kinds=kinds if isinstance(kinds, dict) else None)

    def load_conduct(self) -> types.ModuleType:
        return load_module(TOOL, "conduct_under_test", ABSENT_PREPARE)

    def load_policy(self) -> types.ModuleType:
        return load_module(POLICY_TOOL, "lane_policy_under_test", ABSENT_POLICY)

    def load_adapters(self) -> types.ModuleType:
        return load_module(ADAPTERS, "adapters_under_test", ABSENT_ADAPTER)

    def prepare(
        self,
        *,
        selection: dict | None = None,
        tokens: list[str] | None = None,
        operation: str = "launch",
        ctx: TrustedContext | None = None,
        parent: dict | None = None,
        mechanism: str = MECHANISM_SYNTHETIC,
    ) -> object:
        selection = selection or self.selection()
        tokens = list(ADMITTED_EMPTY if tokens is None else tokens)
        ctx = ctx or self.make_context(
            selection=selection,
            operation=operation,
            parent=parent,
            mechanism=mechanism,
        )
        mod = self.load_conduct()
        fn = getattr(mod, "prepare_conductor", None)
        self.assertTrue(
            callable(fn),
            "prepare_conductor is the startup composition interface",
        )
        before_calls = list(self.mcp_client.calls)
        result = fn(ctx, selection, tokens, operation)
        self.assertEqual(
            self.mcp_client.calls,
            before_calls,
            "prepare_conductor must not call MCP",
        )
        return result

    def _spawn(
        self,
        cmd: list[str],
        *,
        ctx: TrustedContext | None,
        inherit: bool,
        extra_env: dict | None,
    ) -> subprocess.CompletedProcess[str]:
        fds: tuple[int, ...] = ()
        preexec = None
        if inherit:
            ctx = ctx or self.make_context()
            opened = self.open_bootstrap(ctx)
            fds = tuple(opened)

            def relocate() -> None:
                for dest, src in enumerate(opened, start=BOOTSTRAP_FD_START):
                    if src != dest:
                        os.dup2(src, dest)
                keep = set(range(BOOTSTRAP_FD_START, BOOTSTRAP_FD_END + 1))
                for src in opened:
                    if src not in keep:
                        os.close(src)

            preexec = relocate
        return subprocess.run(
            cmd,
            cwd=str(self.cwd),
            env=self.env(extra_env),
            capture_output=True,
            text=True,
            check=False,
            close_fds=True,
            pass_fds=fds,
            preexec_fn=preexec,
        )

    def run_cli(
        self,
        argv: list[str],
        *,
        ctx: TrustedContext | None = None,
        extra_env: dict | None = None,
        inherit: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-B", str(self.cli_entry), *argv]
        return self._spawn(cmd, ctx=ctx, inherit=inherit, extra_env=extra_env)

    def run_bin(
        self,
        argv: list[str],
        *,
        ctx: TrustedContext | None = None,
        extra_env: dict | None = None,
        inherit: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not BIN.is_file():
            return subprocess.CompletedProcess(
                args=["ops/bin/conduct", *argv],
                returncode=127,
                stdout="",
                stderr="ops/bin/conduct is absent\n",
            )
        cmd = [str(BIN), *argv]
        return self._spawn(cmd, ctx=ctx, inherit=inherit, extra_env=extra_env)

    def invoke_conduct(
        self,
        argv: list[str],
        *,
        ctx: TrustedContext | None = None,
        extra_env: dict | None = None,
        inherit: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Public CLI through the trusted parent and canonical launch."""
        return self.run_cli(
            argv,
            ctx=ctx,
            extra_env=extra_env,
            inherit=inherit,
        )

    def claimed_record(self) -> dict | None:
        paths = self.effects.record_paths()
        if not paths:
            return None
        raw = paths[-1].read_bytes()
        return json.loads(raw.decode("utf-8"))

    def retained_descriptor(self, proc: subprocess.CompletedProcess[str]) -> dict:
        record = self.claimed_record()
        self.assertIsNotNone(record, f"canonical launch left no record: {proc}")
        assert record is not None
        conductor = record.get("conductor")
        self.assertIsInstance(conductor, dict)
        assert isinstance(conductor, dict)
        descriptor = conductor.get("descriptor")
        return self.assert_closed_object(descriptor, DESCRIPTOR_KEYS)

    def assert_no_durable_effects(self) -> None:
        added, removed, changed = self.effects.delta()
        self.assertEqual(removed, [])
        self.assertEqual(self.dispatch.claimed_path, None)
        self.assertEqual(self.effects.prompts, [])
        self.assertEqual(self.effects.children, [])
        self.assertEqual(self.effects.hooks, [])
        self.assertEqual(self.effects.transport_writes, [])
        leaked = [
            name
            for name in added
            if name.endswith("record.json") or "/attempts/" in name
        ]
        self.assertEqual(leaked, [])
        self.assertFalse(self.receipt.exists())
        _ = changed

    def assert_prepare_pure(self) -> None:
        self.assert_no_durable_effects()
        self.assertEqual(self.mcp_client.calls, [])
        self.assertEqual(self.mcp_client.observations, [])
        self.assertEqual(self.effects.mcp_calls, [])
        self.assertEqual(self.effects.hooks, [])
        self.assertEqual(self.effects.prompts, [])
        self.assertEqual(self.effects.transport_writes, [])

    def assert_refusal_line(
        self,
        text: str,
        class_token: str,
        *,
        doctor: bool = True,
        found: str | None = None,
        exact: str | None = None,
    ) -> re.Match[str]:
        line = text.strip().splitlines()[0] if text.strip() else ""
        if exact is not None:
            self.assertEqual(line, exact)
        match = REFUSAL_RE.match(line)
        self.assertIsNotNone(
            match,
            f"expected refusal wire, found {text!r}",
        )
        assert match is not None
        self.assertEqual(match.group("cls"), class_token)
        if doctor:
            self.assertIn("independent doctor", line)
        if found is not None:
            self.assertIn(f"found {found};", line)
        self.assertNotIn(";", match.group(0).split(":")[1].split(";")[0])
        self.assertNotIn(SECRET_CANARY, line)
        return match

    def assert_cli_refusal(
        self,
        proc: subprocess.CompletedProcess[str],
        class_token: str,
        *,
        doctor: bool = True,
        found: str | None = None,
        exact: str | None = None,
        exit_code: int = 2,
    ) -> None:
        self.assertEqual(proc.returncode, exit_code)
        self.assertEqual(proc.stdout, "")
        self.assert_refusal_line(
            proc.stderr,
            class_token,
            doctor=doctor,
            found=found,
            exact=exact,
        )
        if exit_code == 2:
            self.assert_no_durable_effects()

    def assert_closed_object(self, value: object, keys: tuple[str, ...]) -> dict:
        self.assertIsInstance(value, dict)
        assert isinstance(value, dict)
        self.assertEqual(tuple(sorted(value)), tuple(sorted(keys)))
        return value

    def assert_prepare_ok(self, result: object) -> tuple[dict, dict]:
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(tuple(sorted(result)), tuple(sorted(PREPARE_KEYS)))
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        compiled_body = self.assert_closed_object(compiled, COMPILED_KEYS)
        self.assert_no_durable_effects()
        return body, compiled_body

    def assert_prepare_refused(
        self,
        result: object,
        class_token: str,
        *,
        found: str | None = None,
        exact: str | None = None,
    ) -> str:
        self.assertIsInstance(
            result,
            str,
            f"expected owning refusal-wire string, found {result!r}",
        )
        assert isinstance(result, str)
        self.assertFalse(result.endswith("\n"), result)
        self.assert_refusal_line(
            result,
            class_token,
            found=found,
            exact=exact,
        )
        self.assert_prepare_pure()
        return result

    def assert_selection_bytes(self, body: dict, selection: dict) -> None:
        actual = self.assert_closed_object(body["selection"], SELECTION_KEYS)
        self.assertEqual(sorted(actual), sorted(SELECTION_KEYS))
        self.assertEqual(canonical_dumps(actual), canonical_dumps(selection))
        self.assertEqual(actual, selection)

    def assert_connection_observations(
        self,
        rows: list[dict],
        *,
        profile: str,
        epoch: int | None = None,
    ) -> None:
        self.assertEqual(len(rows), 3)
        self.assertEqual([row["seq"] for row in rows], [0, 1, 2])
        methods = [row["request"]["method"] for row in rows]
        self.assertEqual(methods, ["initialize", "tools/list", "tools/call"])
        self.assertEqual(rows[2]["request"]["params"]["name"], "lane_start")
        self.assertEqual(
            rows[2]["request"]["params"]["arguments"],
            {"profile": profile},
        )
        listed = rows[1]["response"]["result"]["tools"]
        self.assertEqual([tool["name"] for tool in listed], list(V3_TOOL_NAMES))
        for tool in listed:
            self.assertEqual(tool["inputSchema"], V3_TOOL_SCHEMAS[tool["name"]])
        if epoch is not None:
            self.assertTrue(all(row.get("epoch") == epoch for row in rows))
        for row in rows:
            self.assertEqual(row["request"]["id"], row["response"]["id"])
            raw = canonical_dumps({key: row[key] for key in OBSERVATION_KEYS})
            self.assertLessEqual(len(raw), OBSERVATION_MAX)
            self.assertLessEqual(json_nesting(row), NESTING_MAX)

    def assert_diagnostic_report(
        self, stdout: str, *, profiles: tuple[str, ...]
    ) -> dict:
        payload = json.loads(stdout)
        reports = payload if isinstance(payload, list) else [payload]
        seen = []
        for report in reports:
            body = self.assert_closed_object(report, DIAGNOSTIC_KEYS)
            self.assertEqual(body["schema"], SCHEMA_DIAGNOSTIC)
            self.assert_closed_object(body["selection"], SELECTION_KEYS)
            seen.append(body["selection"]["profile"])
        for profile in profiles:
            self.assertIn(profile, seen)
        return reports[0]

    def tool_request(
        self,
        *,
        kind: str,
        target: str,
        arguments: dict,
        binding_sha256: str,
        req_id: str = "toolreq1",
    ) -> dict:
        return {
            "schema": SCHEMA_TOOL,
            "id": req_id,
            "binding_sha256": binding_sha256,
            "kind": kind,
            "target": target,
            "arguments": arguments,
        }
