"""Verified synthetic counterparties for independent conduct startup tests.

Contracts (only): `ops/conductor/conductor-start-plan.md`,
`ops/conductor/permission-surface.md`, `ops/conductor/harness-capabilities.md`,
plus the closed shapes those documents cite in discovery-lever.md,
lane-policy.md, dispatch/CONTRACT.md and task/CONTRACT.md.

Implementation unread. No live harness, credentials, host settings or
admission. Counterparties are test-owned: a fake executable, an
in-memory dispatch reservation, an effects log, a client MCP handle
and a separate server-query receipt.

Pins for shapes the contracts name without a closed envelope live in
PIN_* comments. They are reported as undeclared boundaries, not
silently treated as law.
"""

from __future__ import annotations

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

# Contract grammar and the two document-present positive vectors.
GRAMMAR = {
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
DELEGATE_TARGETS = ("dispatch", "go", "ladder")
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
POLICY_BINDING_KEYS = (
    "schema",
    "path",
    "ref",
    "sha256",
    "admission",
    "profile",
    "template_sha256",
    "grants_sha256",
    "maintenance",
)
CAPABILITY_KEYS = (
    "harness",
    "adapter",
    "platform",
    "role",
    "operation",
    "policy",
    "scope",
    "contracts",
    "mcp",
    "probe",
    "mock",
)
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

HEAD_OID = "0123456789abcdef0123456789abcdef01234567"
SNAPSHOT_REF = "89abcdef0123456789abcdef0123456789abcdef"
POLICY_REF = "fedcba9876543210fedcba9876543210fedcba98"
TEMPLATE_PATH = "ops/conductor/conductor-start-plan.md"

ABSENT_CLI = (
    b'#!/usr/bin/env python3\n'
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
    """PIN_PREPARE_RETURN: two named values, packaging unnamed.

    Accept a 2-tuple/list (descriptor, compiled_launch) or a mapping
    with those two keys. Anything else returns (result, None) so the
    caller's assertions fire on the missing descriptor.
    """
    if isinstance(result, (tuple, list)) and len(result) == 2:
        return result[0], result[1]
    if isinstance(result, dict) and "descriptor" in result:
        compiled = result.get("compiled_launch")
        if compiled is None:
            compiled = result.get("compiled")
        return result["descriptor"], compiled
    return result, None


class EffectsLog:
    """Filesystem and reservation effects under the fixture root."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.claimed: list[str] = []
        self.children: list[list[str]] = []
        self.prompts: list[str] = []
        self.records: list[Path] = []
        self.baseline: dict[str, str] = {}

    def capture(self) -> None:
        self.baseline = self._digest_tree()

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


class FakeDispatch:
    """In-memory DispatchID reservation. No job directory until claim."""

    def __init__(self, harness: str = "codex") -> None:
        self.harness = harness
        self.reserved: str | None = None
        self.claimed_path: Path | None = None
        self.mutations: list[str] = []

    def reserve(self, *, operation: str) -> str:
        if operation == "resume" and self.reserved:
            return self.reserved
        self.reserved = f"20260906T120000Z-conduct-{self.harness}-a1b2c3"
        self.mutations.append(f"reserve:{self.reserved}")
        return self.reserved

    def claim(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.claimed_path = path
        self.mutations.append(f"claim:{path}")


class FakeMcpClient:
    """Actual-client handle. Calls are evidence; absence is not a server miss."""

    def __init__(
        self,
        *,
        connect: bool,
        envelope: dict,
        catalogue: dict,
        invalid_params: bool = False,
    ) -> None:
        self.connect = connect
        self.envelope = envelope
        self.catalogue = catalogue
        self.invalid_params = invalid_params
        self.calls: list[object] = []

    def initialize(self) -> dict | None:
        self.calls.append("initialize")
        if not self.connect:
            return None
        return {"protocolVersion": "2025-06-18"}

    def tools_list(self) -> dict | None:
        self.calls.append("tools/list")
        if not self.connect:
            return None
        return self.catalogue

    def tools_call(self, name: str, arguments: dict) -> dict | None:
        self.calls.append(("tools/call", name, arguments))
        if not self.connect:
            return None
        if self.invalid_params:
            return {"error": {"code": -32602, "message": "Invalid params"}}
        return self.envelope


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
        self.dispatch = FakeDispatch()
        self.receipt = self.work / "harness-receipt.json"
        self.executable = self.work / "fake-harness"
        self.plant_bytes(self.executable, FAKE_HARNESS)
        self.executable.chmod(self.executable.stat().st_mode | stat.S_IEXEC)
        self.config_path = self.work / "lane-mcp-v3.json"
        self.config_obj = self.make_v3_config()
        self.config_bytes = canonical_dumps(self.config_obj)
        self.plant_bytes(self.config_path, self.config_bytes)
        self.boot_contract = b"discovery-lever fixture bytes for D-A47\n"
        self.grammar_bytes = canonical_dumps(GRAMMAR)
        self.grammar_sha256 = sha256_hex(self.grammar_bytes)
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
        self.staged_tool = self.scratch / "conduct.py"
        self._stage_tool()
        self.effects.capture()
        self.assertFalse(
            (self.home / ".local" / "state" / "agentscient" / "dispatch").exists(),
            "plant: isolated store must start absent",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertEqual(len(landed), len(data))

    def _stage_tool(self) -> None:
        if TOOL.is_file():
            data = TOOL.read_bytes()
            self.staged_tool.write_bytes(data)
            landed = self.staged_tool.read_bytes()
            self.assertEqual(landed, data, "copy-tool-bytes did not land intact")
            self.assertEqual(len(landed), len(data))
            self.assertNotEqual(landed, ABSENT_CLI)
        else:
            self.staged_tool.write_bytes(ABSENT_CLI)
            landed = self.staged_tool.read_bytes()
            self.assertEqual(landed, ABSENT_CLI, "stub plant did not land intact")
            self.assertEqual(len(landed), len(ABSENT_CLI))
        self.staged_tool.chmod(self.staged_tool.stat().st_mode | stat.S_IEXEC)

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
        names = [
            "lane_record",
            "lane_alerts",
            "lane_usage",
            "lane_brief",
            "lane_jobs",
            "lane_job",
            "lane_findings",
            "lane_start",
            "lane_homes",
            "lane_handoffs",
            "lane_actions",
        ]
        self.assertEqual(len(names), V3_TOOLS)
        tools = []
        for name in names:
            tools.append(
                {
                    "name": name,
                    "description": name,
                    "inputSchema": {"type": "object"},
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
            "work": [],
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
        return {
            "harness": harness,
            "model": model,
            "effort": effort,
            "role": role,
            "job_role": job_role,
            "profile": profile,
        }

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

    def adapter_object(self) -> dict:
        return {
            "revision": self.adapter_revision,
            "mechanism": "fixture-cli",
            "grammar_sha256": self.grammar_sha256,
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

    def capability(self, selection: dict, operation: str) -> dict:
        adapter = self.adapter_object()
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

    def make_context(
        self,
        *,
        selection: dict | None = None,
        operation: str = "launch",
        parent: dict | None = None,
        candidate_custody: bytes | None = None,
    ) -> types.SimpleNamespace:
        # PIN_TRUSTED_CONTEXT: in-process argument holding the named
        # contents (binding, declaration sources, custody anchor,
        # discovery boot inputs). Closed JSON keys are not declared
        # for this handle. Test-owned counterparties hang off the same
        # namespace so a live harness is never required.
        selection = selection or self.selection()
        launch_id = self.dispatch.reserve(operation=operation)
        binding = self.conductor_binding(selection, launch_id)
        decls = self.declarations(selection)
        ctx = types.SimpleNamespace(
            binding=binding,
            declarations=decls,
            custody_anchor=self.custody_bytes,
            custody_sha256=self.custody_sha256,
            boot={
                "config_bytes": self.config_bytes,
                "config_sha256": self.config_sha256,
                "contract_bytes": self.boot_contract,
                "contract_sha256": sha256_hex(self.boot_contract),
                "anchors": self.anchors(),
                "repository": self.config_obj["discovery"]["repository"],
            },
            transport={
                "executable": str(self.executable),
                "executable_sha256": self.executable_sha256,
                "config": str(self.config_path),
                "manifest": GRAMMAR,
                "paths": {"out": str(self.work / "out")},
                "session_binding": None
                if operation == "launch"
                else {"id": "session-fixture"},
            },
            dispatch=self.dispatch,
            mcp_client=self.mcp_client,
            mcp_server=self.mcp_server,
            effects=self.effects,
            candidate_custody=candidate_custody,
            parent_descriptor=parent,
            operation=operation,
        )
        return ctx

    def expected_descriptor(
        self,
        selection: dict,
        tokens: list[str],
        operation: str,
        launch_id: str,
        *,
        parent: dict | None = None,
    ) -> dict:
        binding = self.conductor_binding(selection, launch_id)
        resume = None
        if operation == "resume":
            self.assertIsNotNone(parent)
            resume = {
                "parent_descriptor_sha256": canonical_digest(parent),
                "session_binding_sha256": canonical_digest(
                    {"id": "session-fixture"}
                ),
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
            "adapter": self.adapter_object(),
            "forwarded_tokens": list(tokens),
            "mcp": self.mcp_object(),
            "resume": resume,
        }

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
        ctx: types.SimpleNamespace | None = None,
        parent: dict | None = None,
    ) -> object:
        selection = selection or self.selection()
        tokens = list(ADMITTED_EMPTY if tokens is None else tokens)
        ctx = ctx or self.make_context(
            selection=selection,
            operation=operation,
            parent=parent,
        )
        mod = self.load_conduct()
        fn = getattr(mod, "prepare_conductor", None)
        self.assertTrue(
            callable(fn),
            "prepare_conductor is the startup composition interface",
        )
        return fn(ctx, selection, tokens, operation)

    def run_cli(
        self,
        argv: list[str],
        *,
        extra_env: dict | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-B", str(self.staged_tool), *argv]
        return subprocess.run(
            cmd,
            cwd=str(self.cwd),
            env=self.env(extra_env),
            capture_output=True,
            text=True,
            check=False,
        )

    def run_bin(
        self,
        argv: list[str],
        *,
        extra_env: dict | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if not BIN.is_file():
            return subprocess.CompletedProcess(
                args=["ops/bin/conduct", *argv],
                returncode=0,
                stdout="",
                stderr="",
            )
        cmd = [str(BIN), *argv]
        return subprocess.run(
            cmd,
            cwd=str(self.cwd),
            env=self.env(extra_env),
            capture_output=True,
            text=True,
            check=False,
        )

    def invoke_conduct(
        self,
        argv: list[str],
        *,
        ctx: types.SimpleNamespace | None = None,
        selection: dict | None = None,
        tokens: list[str] | None = None,
        operation: str = "launch",
    ) -> object:
        """PIN_CONDUCT_ENTRY: prefer in-process conduct(ctx, argv).

        CLI inheritance of the read-only descriptor is unnamed (not a
        path, env var, MCP parameter or model argument). Tests therefore
        call the declared in-process composition first.
        """
        ctx = ctx or self.make_context(
            selection=selection,
            operation=operation,
        )
        mod = self.load_conduct()
        fn = getattr(mod, "conduct", None)
        if callable(fn):
            try:
                return fn(ctx, argv)
            except TypeError:
                return fn(argv)
        return self.prepare(
            selection=selection or self.selection(),
            tokens=tokens,
            operation=operation,
            ctx=ctx,
        )

    def assert_no_durable_effects(self) -> None:
        added, removed, changed = self.effects.delta()
        self.assertEqual(removed, [])
        self.assertEqual(self.dispatch.claimed_path, None)
        self.assertEqual(self.effects.prompts, [])
        self.assertEqual(self.effects.children, [])
        leaked = [
            name
            for name in added
            if name.endswith("record.json") or "/attempts/" in name
        ]
        self.assertEqual(leaked, [])
        self.assertFalse(self.receipt.exists())
        _ = changed

    def assert_refusal_line(
        self,
        text: str,
        class_token: str,
        *,
        doctor: bool = True,
    ) -> re.Match[str]:
        line = text.strip().splitlines()[0] if text.strip() else ""
        match = REFUSAL_RE.match(line)
        self.assertIsNotNone(
            match,
            f"expected refusal wire, found {text!r}",
        )
        assert match is not None
        self.assertEqual(match.group("cls"), class_token)
        if doctor:
            self.assertIn("independent doctor", line)
        self.assertNotIn(";", match.group(0).split(":")[1].split(";")[0])
        self.assertNotIn(SECRET_CANARY, line)
        return match

    def assert_cli_refusal(
        self,
        proc: subprocess.CompletedProcess[str],
        class_token: str,
        *,
        doctor: bool = True,
    ) -> None:
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assert_refusal_line(proc.stderr, class_token, doctor=doctor)
        self.assert_no_durable_effects()

    def assert_closed_object(self, value: object, keys: tuple[str, ...]) -> dict:
        self.assertIsInstance(value, dict)
        assert isinstance(value, dict)
        self.assertEqual(tuple(sorted(value)), tuple(sorted(keys)))
        return value

    def assert_prepare_ok(self, result: object) -> tuple[dict, dict]:
        desc, compiled = unpack_prepare(result)
        body = self.assert_closed_object(desc, DESCRIPTOR_KEYS)
        compiled_body = self.assert_closed_object(compiled, COMPILED_KEYS)
        return body, compiled_body

    def assert_prepare_refused(self, result: object) -> object:
        self.assertIsNotNone(
            result,
            "prepare_conductor returned nothing; need a refusal",
        )
        if isinstance(result, str):
            line = result.strip().splitlines()[0] if result.strip() else ""
            self.assertIsNotNone(REFUSAL_RE.match(line), result)
            return result
        desc, compiled = unpack_prepare(result)
        if compiled is not None or isinstance(desc, dict):
            self.fail(f"expected refusal, found descriptor {desc!r}")
        if isinstance(result, dict) and (
            "refusal" in result or "class" in result
        ):
            return result
        self.fail(f"expected a wire refusal, found {result!r}")
        return result

    def native_request(self, surface: str, argv: list[str]) -> dict:
        # PIN_NATIVE_REQUEST: permission-surface names native surfaces
        # without a closed native schema. Tests use this fixture envelope.
        return {
            "surface": surface,
            "argv": argv,
            "cwd": str(self.cwd),
            "environment": {},
            "executable": str(self.executable),
        }

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
