"""Call compile_launch without turning a missing adapters module into an import error.

Declared seam: ops/devlane/harness/adapters.py::compile_launch
(harness-capabilities.md Conduct adapter interface; dispatch CONTRACT.md
C2 worker encoding and compilation evidence custody; adoption review
unit 4). On this ref adapters.py is absent. A missing file or attribute
must not become a collection ERROR; wrappers return a value that cannot
satisfy the contracted assertion, so each test fails on its own equality
or refusal check.

Transport and evidence are synthetic in-process handles exposing the
closed member sets declared for compile. They are a test counterparty,
not a public dictionary constructor, candidate path, or trusted flag.
In-process wire refusals have no declared exception type; the wrapper
accepts a raised or returned expected-found-needed line.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import types
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

HARNESS = Path(__file__).resolve().parents[1]
ADAPTERS_PATH = HARNESS / "adapters.py"
MISSING_LAUNCH = {"_missing_seam": "adapters.compile_launch"}
SUCCESS_KEYS = ("argv", "environment", "reservations", "capability", "binding")
BINDING_KEYS = ("invariant_sha256", "argv_sha256", "operation")
CONDUCT_CAPABILITY_KEYS = (
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
WORKER_CAPABILITY_KEYS = (
    "harness",
    "adapter",
    "platform",
    "role",
    "operation",
    "scope",
    "contracts",
    "probe",
    "mock",
)
CONDUCT_ADAPTER_KEYS = (
    "revision",
    "mechanism",
    "config_sha256",
    "grammar_sha256",
    "normalizer_sha256",
)
WORKER_ADAPTER_KEYS = (
    "revision",
    "mechanism",
    "config_sha256",
    "grammar_sha256",
)
CONDUCT_MANIFEST_ADAPTER_KEYS = (
    "revision",
    "mechanism",
    "grammar_sha256",
    "normalizer_sha256",
    "executable_sha256",
    "config_sha256",
)
WORKER_MANIFEST_ADAPTER_KEYS = (
    "revision",
    "mechanism",
    "config_sha256",
    "grammar_sha256",
    "executable_sha256",
)
WIRE_LINE = re.compile(
    r"^[a-z0-9-]+: expected .+; found .+; needed .+$",
    re.DOTALL,
)
ARGV_REFUSAL_PREFIX = "conduct-argv:"
CAPABILITY_REFUSAL_PREFIX = "output-capability:"
CANARY_VALUE = "SECRET"
CANARY_LONG = "CANARY_TOKEN_VALUE_9f3a"
TRUSTED_ENV = {
    "FIXTURE_MARK": "admitted-nonsecret",
    "LANG": "C",
}
ENV_CANARIES = {
    "PATH": "/opt/vendor/bin",
    "HOME": "/opt/vendor/home",
    "TMPDIR": "/opt/vendor/tmp",
}
SYNTHETIC_GRAMMAR = {
    "schema": "adapter-argv/1",
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
EMPTY_GRAMMAR = {"schema": "adapter-argv/1", "options": []}
REPEATABLE_GRAMMAR = {
    "schema": "adapter-argv/1",
    "options": [
        {
            "name": "--tag",
            "forms": ["split", "equals"],
            "values": ["alpha", "beta"],
            "repeatable": True,
        },
    ],
}
POSITIVE_VECTORS = (
    ["--display=compact", "--quiet"],
    ["--display", "plain"],
    [],
)
# Documentary checker negatives, materialized as concrete tokens.
NEGATIVE_VECTORS = (
    (["--display=compact", "--display", "plain"], "repetition-across-forms"),
    (["--dis"], "abbreviation"),
    (["-q"], "short-alias"),
    ([f"--display={CANARY_VALUE}"], "unsafe-value"),
    (["@file"], "response-file"),
    (["--config=x"], "reserved-config"),
    (["--quiet", "positional"], "trailing-positional"),
    (["--"], "bare-double-dash"),
    (["--display"], "missing-split-value"),
)
RESERVED_TOKENS = (
    "--permission-mode=accept",
    "--sandbox=workspace-write",
    "--add-dir=/tmp",
    "--settings=x",
    "--config=x",
    "--env=FOO=1",
    "--session=abc",
    "--resume=abc",
    "--role=worker",
    "--profile=prod",
    "--model=other",
    "--effort=high",
)
TRANSPORT_RESERVED = ("last-message.json", "COMMIT_MSG")
CHECKED_AT = "2026-09-06T12:00:00Z"
ADMISSION_AT = "2026-09-06T12:00:30Z"
SESSION_ID = "sess-fixture-01"


def canonical_json(value) -> str:
    """Startup canonical encoding: sorted keys, ASCII, compact, no newline."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value) -> str:
    return sha256_text(canonical_json(value))


GRAMMAR_SHA256 = sha256_json(SYNTHETIC_GRAMMAR)
EMPTY_GRAMMAR_SHA256 = sha256_json(EMPTY_GRAMMAR)


def flag_token(length: int) -> str:
    """Declared-shape flag whose UTF-8 length is exactly ``length``."""
    if length < 3:
        raise AssertionError(f"flag token shorter than --x: {length}")
    token = "--b" + ("n" * (length - 3))
    encoded = token.encode("utf-8")
    if len(encoded) != length:
        raise AssertionError(f"flag_token({length}) produced {len(encoded)} bytes")
    return token


FLAG_128 = flag_token(128)
FLAG_129 = flag_token(129)
FLAG_256 = flag_token(256)
FLAG_257 = flag_token(257)
BYTE_BOUND_GRAMMAR = {
    "schema": "adapter-argv/1",
    "options": [
        {"name": FLAG_128, "forms": ["flag"], "values": None, "repeatable": True},
        {"name": FLAG_129, "forms": ["flag"], "values": None, "repeatable": True},
        {"name": FLAG_256, "forms": ["flag"], "values": None, "repeatable": True},
        {"name": FLAG_257, "forms": ["flag"], "values": None, "repeatable": True},
    ],
}
VECTOR_8192 = [FLAG_256] * 32
VECTOR_8193 = [FLAG_128] * 63 + [FLAG_129]


def plant_bytes(path: Path, data: bytes, *, recognisable: bytes | None = None) -> bytes:
    """Write ``data`` and prove it landed, still recognisably the fixture."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    landed = path.read_bytes()
    if landed != data:
        raise AssertionError(f"plant did not land at {path}")
    if recognisable is not None and recognisable not in landed:
        raise AssertionError(
            f"plant at {path} is not recognisably the fixture"
        )
    return landed


def plant_mutate(path: Path, mutate, *, recognisable: bytes | None = None) -> bytes:
    """Corrupt an existing fixture and prove the fault landed intact."""
    path = Path(path)
    before = path.read_bytes()
    if not before:
        raise AssertionError(f"fixture {path} was empty before planting")
    after = bytes(mutate(before))
    if after == before:
        raise AssertionError(f"plant changed nothing in {path}")
    if recognisable is not None and recognisable not in after:
        raise AssertionError(
            f"plant left {path} unrecognisable as the fixture"
        )
    path.write_bytes(after)
    landed = path.read_bytes()
    if landed != after:
        raise AssertionError(f"plant did not reach disk for {path}")
    if before == landed:
        raise AssertionError(f"plant of {path} was restored")
    return before


def _load_adapters():
    if not ADAPTERS_PATH.is_file():
        return types.ModuleType("adapters_absent")
    spec = importlib.util.spec_from_file_location(
        "harness_adapters_under_test", ADAPTERS_PATH,
    )
    if spec is None or spec.loader is None:
        return types.ModuleType("adapters_unloadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ADAPTERS = _load_adapters()


def adapters_module():
    return _ADAPTERS


def compile_launch(selection, grants, transport, forwarded_tokens, operation):
    fn = getattr(_ADAPTERS, "compile_launch", None)
    if not callable(fn):
        return MISSING_LAUNCH
    try:
        result = fn(
            selection, grants, transport, forwarded_tokens, operation,
        )
    except Exception as exc:
        text = str(exc).strip()
        if WIRE_LINE.match(text.splitlines()[0] if text else ""):
            return {"_refusal": text.splitlines()[0], "_exc_type": type(exc).__name__}
        if ": expected " in text and "; found " in text and "; needed " in text:
            return {"_refusal": text.splitlines()[0], "_exc_type": type(exc).__name__}
        raise
    if isinstance(result, str) and (
        WIRE_LINE.match(result.splitlines()[0])
        or ": expected " in result
    ):
        return {"_refusal": result.splitlines()[0]}
    return result


def is_success(result) -> bool:
    return (
        isinstance(result, dict)
        and "_missing_seam" not in result
        and "_refusal" not in result
        and set(result) == set(SUCCESS_KEYS)
    )


def is_refusal(result) -> bool:
    if isinstance(result, dict) and "_refusal" in result:
        return True
    return isinstance(result, str) and ": expected " in result


def refusal_text(result) -> str:
    if isinstance(result, dict) and "_refusal" in result:
        return result["_refusal"]
    if isinstance(result, str):
        return result.splitlines()[0]
    return ""


def explain(result) -> str:
    if result == MISSING_LAUNCH:
        return "declared seam adapters.compile_launch is absent"
    text = refusal_text(result)
    if text:
        return text
    return repr(result)


def launch_field(result, name):
    if is_success(result):
        return result[name]
    return result


def digest_name(label: str) -> str:
    return sha256_text(f"fixture:{label}")


def selection_conductor(harness="codex", **overrides):
    value = {
        "harness": harness,
        "model": "fixture-model",
        "effort": None,
        "role": "conductor",
        "job_role": None,
        "profile": "dev",
    }
    value.update(overrides)
    return value


def selection_worker(harness="codex", **overrides):
    value = {
        "harness": harness,
        "model": "fixture-model",
        "effort": None,
        "role": "worker",
        "job_role": "read",
        "profile": "dev",
    }
    value.update(overrides)
    return value


def _source(component, payload):
    if payload is None:
        return {
            "component": component,
            "kind": "absent",
            "path": None,
            "ref": None,
            "sha256": None,
        }
    return {
        "component": component,
        "kind": "invocation",
        "path": component,
        "ref": None,
        "sha256": sha256_json(payload),
    }


def grants_for(
    selection,
    *,
    outputs=None,
    reservations=None,
    requested_scope=None,
    job_grants=None,
    role_grants=None,
    adapter_grants=None,
):
    """LaunchDeclarations: the verified task/policy grant result."""
    outputs = list(outputs or [])
    reservations = list(
        TRANSPORT_RESERVED if reservations is None else reservations,
    )
    empty = {"repository": [], "outputs": []}
    requested_scope = deepcopy(requested_scope or empty)
    job_grants = deepcopy(job_grants or empty)
    role_grants = deepcopy(role_grants or empty)
    adapter_grants = deepcopy(adapter_grants or empty)
    conductor = selection.get("role") == "conductor"
    sources = [
        _source("selection", selection),
        _source("scope", None if conductor else requested_scope),
        _source("job", None if conductor else job_grants),
        _source("role", role_grants),
        _source("adapter", adapter_grants),
        _source("outputs", None if (conductor or not outputs) else outputs),
        _source("reservations", reservations),
    ]
    sources.sort(
        key=lambda row: (
            row["component"],
            row["kind"],
            row["path"] or "",
            row["ref"] or "",
        ),
    )
    return {
        "selection": deepcopy(selection),
        "requested_scope": requested_scope,
        "job_grants": job_grants,
        "role_grants": role_grants,
        "adapter_grants": adapter_grants,
        "outputs": outputs,
        "reservations": reservations,
        "sources": sources,
    }


def adapter_descriptor(*, grammar=None, mechanism="fixture-argv", role="conductor", extra=None):
    grammar = SYNTHETIC_GRAMMAR if grammar is None else grammar
    if role == "worker":
        value = {
            "revision": digest_name("adapter-revision"),
            "mechanism": mechanism,
            "config_sha256": digest_name("config"),
            "grammar_sha256": sha256_json(grammar),
            "executable_sha256": digest_name("executable-placeholder"),
        }
    else:
        value = {
            "revision": digest_name("adapter-revision"),
            "mechanism": mechanism,
            "grammar_sha256": sha256_json(grammar),
            "normalizer_sha256": digest_name("normalizer"),
            "executable_sha256": digest_name("executable-placeholder"),
            "config_sha256": digest_name("config"),
        }
    if extra:
        value.update(extra)
    return value


def mcp_object():
    return {
        "server_sha256": digest_name("mcp-server"),
        "config_sha256": digest_name("mcp-config"),
        "catalogue_sha256": digest_name("mcp-catalogue"),
    }


def default_platform():
    return {
        "os": "linux",
        "sandbox": {"name": "fixture-sandbox", "version": "1"},
        "filesystem": {"name": "posix", "alias_semantics": "no-follow"},
    }


def identity_for(
    selection,
    operation,
    *,
    executable_path,
    executable_sha256,
    adapter,
    outputs=None,
    source_reads,
    source_write_denials,
    limits=None,
    platform=None,
    role=None,
):
    """Closed C2 identity. Isolation lists are required; empty is explicit."""
    outputs = list(outputs or [])
    source_reads = sorted(source_reads)
    source_write_denials = sorted(source_write_denials)
    limits = sorted(set(limits or []))
    outputs_sorted = sorted(outputs, key=lambda item: item["path"])
    platform = platform or default_platform()
    role_value = role if role is not None else selection["role"]
    harness = {
        "name": selection["harness"],
        "version": "fixture-1",
        "executable": {
            "path": executable_path,
            "sha256": executable_sha256,
        },
    }
    scope = {
        "source_reads": source_reads,
        "source_write_denials": source_write_denials,
        "outputs": outputs_sorted,
        "limits": limits,
    }
    mock = {
        "revision": digest_name("mock"),
        "verification": {
            "path": "mock-verification.json",
            "sha256": digest_name("mock-verification"),
        },
    }
    probe = {"revision": digest_name("probe")}
    if role_value == "worker":
        return {
            "harness": harness,
            "adapter": {
                "revision": adapter["revision"],
                "mechanism": adapter["mechanism"],
                "config_sha256": adapter["config_sha256"],
                "grammar_sha256": adapter["grammar_sha256"],
            },
            "platform": platform,
            "role": "worker",
            "operation": operation,
            "scope": scope,
            "contracts": {
                "outputs_sha256": digest_name("outputs-contract"),
            },
            "probe": probe,
            "mock": mock,
        }
    return {
        "harness": harness,
        "adapter": {
            "revision": adapter["revision"],
            "mechanism": adapter["mechanism"],
            "config_sha256": adapter["config_sha256"],
            "grammar_sha256": adapter["grammar_sha256"],
            "normalizer_sha256": adapter["normalizer_sha256"],
        },
        "platform": platform,
        "role": "conductor",
        "operation": operation,
        "policy": {
            "blob_sha256": digest_name("policy-blob"),
            "evaluator_sha256": digest_name("policy-evaluator"),
        },
        "scope": scope,
        "contracts": {
            "outputs_sha256": digest_name("outputs-contract"),
            "tools_sha256": digest_name("tools-contract"),
        },
        "mcp": mcp_object(),
        "probe": probe,
        "mock": mock,
    }


def capability_output(kind, path, operations):
    ops = sorted(set(operations))
    return {"kind": kind, "path": path, "operations": ops}


def capability_keys_for(selection) -> tuple[str, ...]:
    if selection.get("role") == "worker":
        return WORKER_CAPABILITY_KEYS
    return CONDUCT_CAPABILITY_KEYS


def config_digest(configuration, insertion, relay):
    relay_for_digest = None
    if relay is not None:
        relay_for_digest = deepcopy(relay)
        relay_for_digest["resume"] = None
    return sha256_json({
        "configuration": configuration,
        "insertion": insertion,
        "relay": relay_for_digest,
    })


def launch_id_for(selection) -> str:
    harness = selection["harness"]
    if selection.get("role") == "conductor":
        return f"20260906T120000Z-conduct-{harness}-a1b2c3"
    return f"20260906T120000Z-tests-{harness}-a1b2c3"


def session_object(
    selection,
    *,
    launch_id,
    session_id,
    invariant_sha256,
    connection,
    receipts=None,
):
    return {
        "launch_id": launch_id,
        "harness": selection["harness"],
        "id": session_id,
        "invariant_sha256": invariant_sha256,
        "connection": connection,
        "receipts": sorted(list(receipts or []), key=lambda row: row["path"]),
    }


def session_binding_sha256(session) -> str:
    return sha256_json(session)


class ClosedHandle:
    """Copyable closed member set. Test counterparty, not a production constructor."""

    __slots__ = ()

    def __init__(self, **members):
        names = self.__slots__
        missing = [name for name in names if name not in members]
        extra = [name for name in members if name not in names]
        if missing or extra:
            raise AssertionError(
                f"{type(self).__name__} members missing={missing} extra={extra}"
            )
        for name in names:
            setattr(self, name, members[name])

    def __deepcopy__(self, memo):
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        kwargs = {
            name: deepcopy(getattr(self, name), memo) for name in self.__slots__
        }
        copied = type(self)(**kwargs)
        memo[id(self)] = copied
        return copied


class EvidenceHandle(ClosedHandle):
    __slots__ = (
        "admission_at",
        "age_source",
        "checked_at",
        "identity",
        "max_age_seconds",
        "root",
        "selection",
        "verification",
        "witness",
    )


class TransportHandle(ClosedHandle):
    __slots__ = (
        "canonical_paths",
        "configuration",
        "evidence",
        "executable",
        "launch_session",
        "manifest",
        "relay",
        "resume",
    )


class SubprocessSpy:
    """Records subprocess-module invocations without launching a child."""

    def __init__(self):
        self.calls = []

    def _record(self, kind, args, kwargs):
        self.calls.append((kind, args, kwargs))

    def run(self, *args, **kwargs):
        self._record("run", args, kwargs)
        argv = args[0] if args else kwargs.get("args", [])
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    def Popen(self, *args, **kwargs):
        self._record("Popen", args, kwargs)
        raise AssertionError("subprocess.Popen invoked during compile_launch")

    def call(self, *args, **kwargs):
        self._record("call", args, kwargs)
        return 0

    def check_call(self, *args, **kwargs):
        self._record("check_call", args, kwargs)
        return 0

    def check_output(self, *args, **kwargs):
        self._record("check_output", args, kwargs)
        return b""


def attach_subprocess_spy(test_case) -> SubprocessSpy:
    spy = SubprocessSpy()
    for name in ("run", "Popen", "call", "check_call", "check_output"):
        started = patch(f"subprocess.{name}", getattr(spy, name))
        started.start()
        test_case.addCleanup(started.stop)
    return spy


class FixtureRoot:
    """Disposable synthetic adapter apparatus. Not a real harness or auth."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="adapter-fixture-"))
        self.bin = self.root / "bin"
        self.out = self.root / "out"
        self.evidence = self.root / "evidence"
        self.snapshot = self.root / "snapshot"
        self.run = self.root / "run"
        self.bin.mkdir()
        self.out.mkdir()
        self.evidence.mkdir()
        self.snapshot.mkdir()
        self.run.mkdir()
        plant_bytes(
            self.snapshot / "held-source.txt",
            b"synthetic-source\n",
            recognisable=b"synthetic-source",
        )
        self.source_reads = [str(self.snapshot.resolve())]
        self.source_write_denials = [
            str(self.snapshot.resolve()),
            str((self.snapshot / ".git").resolve()),
        ]
        self.executables = {}
        for name in ("claude", "codex", "grok"):
            path = self.bin / f"fixture-{name}"
            body = f"synthetic-{name}-executable\n".encode("utf-8")
            plant_bytes(path, body, recognisable=b"synthetic-")
            os.chmod(path, 0o644)  # not launched; execute bit off on purpose
            self.executables[name] = {
                "path": str(path.resolve()),
                "sha256": sha256_bytes(body),
            }
        settings_body = b'{"fixture":true}\n'
        self.settings_path = str((self.root / "settings.json").resolve())
        plant_bytes(
            self.root / "settings.json",
            settings_body,
            recognisable=b'"fixture":true',
        )
        self.settings_sha256 = sha256_bytes(settings_body)
        # Relative handles resolve beneath the protected evidence root.
        # Do not prefix them with "evidence/" — that component is the root.
        self.verification_rel = "mock-verification.json"
        self.passing_verification = canonical_json({
            "kind": "receipt",
            "claim": "synthetic leaf/scratch admission control",
            "control": "leaf-write-and-source-deny",
            "result": "PASS",
        }).encode("utf-8")
        self.verification_path = self.held_path(self.verification_rel)
        plant_bytes(
            self.verification_path,
            self.passing_verification,
            recognisable=b"leaf-write-and-source-deny",
        )
        self.verification_sha256 = sha256_bytes(self.passing_verification)
        self.witness_rel = "witness.json"
        self.passing_witness = canonical_json({
            "kind": "witness",
            "claim": "synthetic capability witness",
            "control": "source-isolation-and-leaf",
            "result": "PASS",
        }).encode("utf-8")
        self.witness_path = self.held_path(self.witness_rel)
        plant_bytes(
            self.witness_path,
            self.passing_witness,
            recognisable=b"source-isolation-and-leaf",
        )
        self.witness_sha256 = sha256_bytes(self.passing_witness)
        age_body = b'{"max_age_seconds":60}\n'
        self.age_policy_rel = "age-policy.json"
        plant_bytes(
            self.held_path(self.age_policy_rel),
            age_body,
            recognisable=b"max_age_seconds",
        )
        self.age_policy_sha256 = sha256_bytes(age_body)
        self._assert_held_resolves(self.verification_rel, self.verification_path)
        self._assert_held_resolves(self.witness_rel, self.witness_path)
        self._assert_held_resolves(
            self.age_policy_rel, self.held_path(self.age_policy_rel),
        )
        self.reserved_abs = [
            str((self.out / "last-message.json").resolve()),
            str((self.out / "COMMIT_MSG").resolve()),
        ]

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def held_path(self, rel) -> Path:
        """Join a relative evidence handle under the protected evidence root."""
        relative = Path(rel)
        parts = relative.parts
        if relative.is_absolute() or not parts or any(
            part in (".", "..") for part in parts
        ):
            raise AssertionError(
                f"evidence handle {rel!r} is not a relative file under root"
            )
        return (Path(self.evidence.resolve()) / relative).resolve()

    def _assert_held_resolves(self, rel, planted: Path):
        joined = self.held_path(rel)
        if joined != planted.resolve():
            raise AssertionError(
                f"handle {rel!r} joins to {joined}, planted at {planted}"
            )
        if not joined.is_file():
            raise AssertionError(f"held evidence {joined} is missing")

    def isolation(self):
        return list(self.source_reads), list(self.source_write_denials)

    def verification_handle(self):
        return {
            "path": self.verification_rel,
            "sha256": self.verification_sha256,
        }

    def witness_handle(self):
        return {
            "path": self.witness_rel,
            "sha256": self.witness_sha256,
        }

    def declared_config_sha256(
        self,
        selection,
        *,
        configuration=None,
        insertion=None,
        relay=None,
    ):
        """Fixture configuration digest bound to descriptor and identity together."""
        role = selection["role"]
        insertion = dict(insertion or {"launch": 1, "resume": 1})
        configuration = deepcopy(
            configuration
            if configuration is not None
            else self.default_configuration(role),
        )
        return config_digest(configuration, insertion, relay)

    def declared_adapter(
        self,
        selection,
        *,
        grammar=None,
        mechanism="fixture-argv",
        configuration=None,
        insertion=None,
        relay=None,
        extra=None,
    ):
        """Adapter object whose config digest matches this fixture's transport."""
        exe = self.executables[selection["harness"]]
        adapter = adapter_descriptor(
            grammar=grammar,
            mechanism=mechanism,
            role=selection["role"],
            extra=extra,
        )
        adapter["executable_sha256"] = exe["sha256"]
        adapter["config_sha256"] = self.declared_config_sha256(
            selection,
            configuration=configuration,
            insertion=insertion,
            relay=relay,
        )
        return adapter

    def matching_identity(
        self,
        selection,
        operation="launch",
        *,
        outputs=None,
        source_reads=None,
        source_write_denials=None,
        limits=None,
        platform=None,
        role=None,
        grammar=None,
        mechanism="fixture-argv",
        configuration=None,
        insertion=None,
        relay=None,
        extra=None,
    ):
        """Identity whose adapter.config_sha256 matches the declared digest."""
        adapter = self.declared_adapter(
            selection,
            grammar=grammar,
            mechanism=mechanism,
            configuration=configuration,
            insertion=insertion,
            relay=relay,
            extra=extra,
        )
        exe = self.executables[selection["harness"]]
        reads = self.source_reads if source_reads is None else source_reads
        denials = (
            self.source_write_denials
            if source_write_denials is None
            else source_write_denials
        )
        identity = identity_for(
            selection,
            operation,
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=outputs,
            source_reads=reads,
            source_write_denials=denials,
            limits=limits,
            platform=platform,
            role=role,
        )
        identity["mock"]["verification"] = self.verification_handle()
        return identity

    def default_configuration(self, role, extra_env=None):
        environment = dict(TRUSTED_ENV)
        if extra_env:
            environment.update(extra_env)
        return {
            "environment": environment,
            "settings": [
                {"path": self.settings_path, "sha256": self.settings_sha256},
            ],
            "mcp": mcp_object() if role == "conductor" else None,
        }

    def synthetic_relay(self, *, thread_id=None, session_binding=None, receipts=None):
        exe = self.executables["codex"]
        cwd = str(self.root.resolve())
        env = dict(TRUSTED_ENV)

        def process(argv):
            return {
                "executable": dict(exe),
                "argv": list(argv),
                "environment": dict(env),
                "cwd": cwd,
            }

        server_argv = [exe["path"], "app-server", "--listen", "stdio://"]
        relay_argv = [exe["path"], "relay"]
        tui_argv = [exe["path"], "--remote", "unix://" + str(self.run / "conduct.sock")]
        config_leaf = {
            "path": self.settings_path,
            "sha256": self.settings_sha256,
        }
        resume = None
        if thread_id is not None:
            resume = {
                "thread_id": thread_id,
                "session_binding_sha256": session_binding or digest_name("session-binding"),
                "receipts": sorted(list(receipts or []), key=lambda row: row["path"]),
            }
        return {
            "schema": "codex-relay/1",
            "processes": {
                "server": process(server_argv),
                "relay": process(relay_argv),
                "tui": process(tui_argv),
            },
            "endpoint": {
                "path": str((self.run / "conduct.sock").resolve()),
                "transport": "unix-websocket",
                "clients": 1,
                "control": "inherited-unix-socketpair",
            },
            "configuration": {
                "server": dict(config_leaf),
                "tui": dict(config_leaf),
                "registry_sha256": digest_name("relay-registry"),
            },
            "rpc": {
                "source_revision": "fixture-relay-rpc",
                "schema_sha256": digest_name("relay-schema"),
            },
            "targets": [],
            "deadlines": {
                "frame_ms": 5000,
                "request_ms": 5000,
                "effect_ms": 60000,
                "shutdown_ms": 2000,
                "pending": 64,
                "queue_bytes": 1048576,
            },
            "resume": resume,
        }

    def transport(
        self,
        selection,
        operation="launch",
        *,
        grammar=None,
        mechanism="fixture-argv",
        identity=None,
        checked_at=CHECKED_AT,
        max_age_seconds=None,
        resume=None,
        configuration=None,
        witness_identity="present",
        insertion=None,
        launch_session=None,
        relay=None,
        invariant_sha256=None,
        source_reads=None,
        source_write_denials=None,
        outputs=None,
        session_id=SESSION_ID,
        verification=None,
        witness=None,
    ):
        harness = selection["harness"]
        role = selection["role"]
        exe = self.executables[harness]
        grammar = SYNTHETIC_GRAMMAR if grammar is None else grammar
        insertion = insertion or {"launch": 1, "resume": 1}
        configuration = deepcopy(
            configuration
            if configuration is not None
            else self.default_configuration(role),
        )
        adapter = self.declared_adapter(
            selection,
            grammar=grammar,
            mechanism=mechanism,
            configuration=configuration,
            insertion=insertion,
            relay=relay,
        )
        reads = self.source_reads if source_reads is None else source_reads
        denials = (
            self.source_write_denials
            if source_write_denials is None
            else source_write_denials
        )
        if identity is None and witness_identity == "present":
            identity = identity_for(
                selection,
                operation,
                executable_path=exe["path"],
                executable_sha256=exe["sha256"],
                adapter=adapter,
                outputs=outputs,
                source_reads=reads,
                source_write_denials=denials,
            )
            identity["mock"]["verification"] = self.verification_handle()
        if witness_identity == "null":
            identity = None
        if identity is not None:
            identity = deepcopy(identity)
        verification = (
            deepcopy(verification)
            if verification is not None
            else self.verification_handle()
        )
        witness = deepcopy(witness) if witness is not None else self.witness_handle()
        if identity is not None:
            identity["mock"]["verification"] = deepcopy(verification)
        age_source = None
        if max_age_seconds is not None:
            age_source = {
                "path": self.age_policy_rel,
                "sha256": self.age_policy_sha256,
            }
        launch_id = launch_id_for(selection)
        if launch_session is None:
            launch_session = {"launch_id": launch_id, "id": session_id}
        if operation == "launch":
            resume_obj = None
        else:
            connection = None
            if role == "conductor":
                connection = {
                    "client_sha256": digest_name("client"),
                    "server_sha256": digest_name("server"),
                }
            session = session_object(
                selection,
                launch_id=launch_id,
                session_id=session_id,
                invariant_sha256=invariant_sha256 or digest_name("resume-invariant"),
                connection=connection,
            )
            resume_obj = resume or {
                "parent_descriptor_sha256": (
                    None if role == "worker" else digest_name("parent-descriptor")
                ),
                "session_binding_sha256": session_binding_sha256(session),
                "session": session,
            }
        evidence = EvidenceHandle(
            root=str(self.evidence.resolve()),
            admission_at=ADMISSION_AT,
            checked_at=checked_at,
            max_age_seconds=max_age_seconds,
            age_source=age_source,
            selection=deepcopy(selection),
            identity=identity,
            witness=witness,
            verification=verification,
        )
        return TransportHandle(
            executable={"path": exe["path"], "sha256": exe["sha256"]},
            configuration=configuration,
            manifest={
                "adapter": adapter,
                "grammar": deepcopy(grammar),
                "insertion": dict(insertion),
            },
            canonical_paths={
                "cwd": str(self.root.resolve()),
                "out": str(self.out.resolve()),
                "reservations": list(self.reserved_abs),
            },
            evidence=evidence,
            launch_session=launch_session,
            resume=resume_obj,
            relay=deepcopy(relay),
        )

    def resume_transport(self, selection, grants, forwarded_tokens, **kwargs):
        """Resume handle whose session.invariant_sha256 matches the compile inputs."""
        launch = self.transport(selection, "launch", **kwargs)
        inv = expected_invariant(selection, grants, launch, forwarded_tokens)
        return self.transport(
            selection, "resume", invariant_sha256=inv, **kwargs,
        )


def expected_invariant(selection, grants, transport, forwarded_tokens):
    role = selection.get("role")
    adapter = transport.manifest["adapter"]
    mcp = None if role == "worker" else transport.configuration["mcp"]
    payload = {
        "selection": selection,
        "grants": grants,
        "adapter": adapter,
        "forwarded_tokens": forwarded_tokens,
        "mcp": mcp,
    }
    return sha256_json(payload)


def expected_argv_sha256(argv):
    return sha256_json(argv)


def expected_environment(transport, *, tmpdir=None):
    env = dict(transport.configuration["environment"])
    if tmpdir is not None:
        env["TMPDIR"] = tmpdir
    return env


def contiguous_segment(argv, tokens):
    if not tokens:
        return []
    n = len(tokens)
    for i in range(0, len(argv) - n + 1):
        if argv[i:i + n] == list(tokens):
            return argv[i:i + n]
    return None


def secret_leaked(text, *secrets) -> list[str]:
    found = []
    for secret in secrets:
        if secret and secret in text:
            found.append(secret)
    return found


def observation_sinks(result) -> str:
    """Serialize declared observation material: result object and refusal line."""
    parts = [refusal_text(result), explain(result), repr(result)]
    if isinstance(result, dict):
        try:
            parts.append(canonical_json(result))
        except TypeError:
            parts.append(str(result))
    return "\n".join(parts)
