"""Call compile_launch without turning a missing adapters module into an import error.

Declared seam: ops/devlane/harness/adapters.py::compile_launch
(harness-capabilities.md Conduct adapter interface; dispatch CONTRACT.md
C2; adoption review unit 4). On this ref adapters.py is absent. A missing
file or attribute must not become a collection ERROR; wrappers return a
value that cannot satisfy the contracted assertion, so each test fails on
its own equality or refusal check.

Transport fixture keys map contents named by that interface (executable,
configuration, adapter manifest, canonical paths, resume session binding)
plus the C2 capability witness required for admission. The contract lists
those contents and does not freeze a JSON schema of transport key names;
these names are the test mapping for the listed contents, not a second
public function. In-process wire refusals have no declared exception type;
the wrapper accepts a raised or returned expected-found-needed line.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import tempfile
import types
from copy import deepcopy
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
ADAPTERS_PATH = HARNESS / "adapters.py"
MISSING_LAUNCH = {"_missing_seam": "adapters.compile_launch"}
SUCCESS_KEYS = ("argv", "environment", "reservations", "capability", "binding")
WIRE_LINE = re.compile(
    r"^[a-z0-9-]+: expected .+; found .+; needed .+$",
    re.DOTALL,
)
ARGV_REFUSAL_PREFIX = "conduct-argv:"
CAPABILITY_REFUSAL_PREFIX = "output-capability:"
CANARY_VALUE = "SECRET"
CANARY_LONG = "CANARY_TOKEN_VALUE_9f3a"
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
        and all(key in result for key in SUCCESS_KEYS)
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


def adapter_descriptor(*, grammar=None, mechanism="fixture-argv", extra=None):
    grammar = SYNTHETIC_GRAMMAR if grammar is None else grammar
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


def identity_for(
    selection,
    operation,
    *,
    executable_path,
    executable_sha256,
    adapter,
    outputs=None,
    source_reads=None,
    source_write_denials=None,
    limits=None,
    platform=None,
    role=None,
):
    outputs = list(outputs or [])
    source_reads = sorted(source_reads or [])
    source_write_denials = sorted(source_write_denials or [])
    limits = sorted(set(limits or []))
    outputs_sorted = sorted(outputs, key=lambda item: item["path"])
    platform = platform or {
        "os": "linux",
        "sandbox": {"name": "fixture-sandbox", "version": "1"},
        "filesystem": {"name": "posix", "alias_semantics": "no-follow"},
    }
    return {
        "harness": {
            "name": selection["harness"],
            "version": "fixture-1",
            "executable": {
                "path": executable_path,
                "sha256": executable_sha256,
            },
        },
        "adapter": {
            "revision": adapter["revision"],
            "mechanism": adapter["mechanism"],
            "config_sha256": adapter["config_sha256"],
            "grammar_sha256": adapter["grammar_sha256"],
            "normalizer_sha256": adapter["normalizer_sha256"],
        },
        "platform": platform,
        "role": role if role is not None else selection["role"],
        "operation": operation,
        "policy": {
            "blob_sha256": digest_name("policy-blob"),
            "evaluator_sha256": digest_name("policy-evaluator"),
        },
        "scope": {
            "source_reads": source_reads,
            "source_write_denials": source_write_denials,
            "outputs": outputs_sorted,
            "limits": limits,
        },
        "contracts": {
            "outputs_sha256": digest_name("outputs-contract"),
            "tools_sha256": digest_name("tools-contract"),
        },
        "mcp": mcp_object(),
        "probe": {"revision": digest_name("probe")},
        "mock": {
            "revision": digest_name("mock"),
            "verification": {
                "path": "evidence/mock-verification.json",
                "sha256": digest_name("mock-verification"),
            },
        },
    }


def capability_output(kind, path, operations):
    ops = sorted(set(operations))
    return {"kind": kind, "path": path, "operations": ops}


class FixtureRoot:
    """Disposable synthetic adapter apparatus. Not a real harness or auth."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="adapter-fixture-"))
        self.bin = self.root / "bin"
        self.out = self.root / "out"
        self.evidence = self.root / "evidence"
        self.bin.mkdir()
        self.out.mkdir()
        self.evidence.mkdir()
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
        self.verification_rel = "evidence/mock-verification.json"
        self.passing_verification = canonical_json({
            "kind": "receipt",
            "claim": "synthetic leaf/scratch admission control",
            "control": "leaf-write-and-source-deny",
            "result": "PASS",
        }).encode("utf-8")
        self.verification_path = self.root / self.verification_rel
        plant_bytes(
            self.verification_path,
            self.passing_verification,
            recognisable=b"leaf-write-and-source-deny",
        )
        self.verification_sha256 = sha256_bytes(self.passing_verification)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)

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
    ):
        harness = selection["harness"]
        exe = self.executables[harness]
        grammar = SYNTHETIC_GRAMMAR if grammar is None else grammar
        adapter = adapter_descriptor(grammar=grammar, mechanism=mechanism)
        adapter["executable_sha256"] = exe["sha256"]
        if identity is None and witness_identity == "present":
            identity = identity_for(
                selection,
                operation,
                executable_path=exe["path"],
                executable_sha256=exe["sha256"],
                adapter=adapter,
            )
            identity["mock"]["verification"] = {
                "path": self.verification_rel,
                "sha256": self.verification_sha256,
            }
            identity["mcp"] = mcp_object()
        if witness_identity == "null":
            identity = None
        witness = {
            "checked_at": checked_at,
            "identity": identity,
            "max_age_seconds": max_age_seconds,
            "admission_at": ADMISSION_AT,
        }
        if operation == "launch":
            resume_obj = None
        else:
            resume_obj = resume or {
                "parent_descriptor_sha256": digest_name("parent-descriptor"),
                "session_binding_sha256": digest_name("session-binding"),
            }
        return {
            "executable": {"path": exe["path"], "sha256": exe["sha256"]},
            "configuration": dict(configuration or {}),
            "adapter": adapter,
            "manifest": deepcopy(grammar),
            "canonical_paths": {"out": str(self.out.resolve())},
            "mcp": mcp_object(),
            "resume": resume_obj,
            "witness": witness,
        }


def expected_invariant(selection, grants, transport, forwarded_tokens):
    payload = {
        "selection": selection,
        "grants": grants,
        "adapter": transport["adapter"],
        "forwarded_tokens": forwarded_tokens,
        "mcp": transport["mcp"],
    }
    return sha256_json(payload)


def expected_argv_sha256(argv):
    return sha256_json(argv)


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
