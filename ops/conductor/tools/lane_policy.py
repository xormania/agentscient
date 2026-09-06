"""Inert policy evaluator; acquisition and activation belong to trusted callers.

The first argument is an authority-bearing in-process handle, never a JSON
request from a worker. Its anchor and runtime manifest are independently
admitted inputs, not self-authenticating attestations. Extra opaque caller
handles are preserved. This module checks their declared byte identities; it
cannot establish host custody or completeness of a Python runtime manifest.

Bindings are dict-compatible for the closed wire projection, with private
in-memory custody. Copying their public JSON does not copy authority. A caller
may supply ``evidence_handles`` for already retained transition evidence, or
``retain_evidence(kind, bytes)`` to retain it in its existing transport. The
callback returns a verified {path,sha256} handle. Launch instead reserves names
and holds prospective bytes in ``binding.pending_evidence`` without writing.
Tool owners may supply ``validate_tool(kind, target, arguments)`` on their
trusted bound-role handle to validate their closed schemas and effect grants.
None of these callbacks is accepted from candidate evidence or a tool request.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = "agentscient.lane-policy/v1"
_POLICY_PATH = "ops/lane-policy.json"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_ID = re.compile(r"D-[A-Z0-9]+-[0-9]+\Z")
_PROFILE = re.compile(r"[a-z][a-z0-9-]*\Z")
_OUTPUT_PATH = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*\Z"
)
_ARTIFACT = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_TRANSITIONS = {
    "launch",
    "settle",
    "resume",
    "collect-before",
    "collect-after",
    "land",
    "ladder",
}
_COMPONENTS = {
    "selection": "selection",
    "scope": "requested_scope",
    "job": "job_grants",
    "role": "role_grants",
    "adapter": "adapter_grants",
    "outputs": "outputs",
    "reservations": "reservations",
}
_REASONS = {
    "direct-edit",
    "git-mutation",
    "shell-escape",
    "raw-vendor",
    "in-session-agent",
    "unknown-tool",
    "malformed-request",
    "binding-mismatch",
}


class Refusal(ValueError):
    """Owning, single-line refusal without raw untrusted values."""


def _require(condition, expected, found, kind="lane-policy"):
    if not condition:
        raise Refusal(
            f"{kind}: expected {expected}; found {found}; "
            "needed verified stationary inputs from the admitted caller"
        )


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _trusted_copy(value):
    """Snapshot data, retaining opaque custody/provider objects by identity."""
    if type(value) is dict:
        return {key: _trusted_copy(item) for key, item in value.items()}
    if type(value) is list:
        return [_trusted_copy(item) for item in value]
    return value


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "unique JSON keys", "duplicate key")
        result[key] = value
    return result


def _strict(data):
    def nonfinite(_value):
        _require(False, "finite JSON values", "non-finite number")

    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data, object_pairs_hook=_pairs, parse_constant=nonfinite)


def _closed(value, keys, kind="lane-policy"):
    _require(
        isinstance(value, dict) and set(value) == set(keys.split()),
        "closed object with declared keys",
        "missing or unknown fields",
        kind,
    )


def _text(value):
    return isinstance(value, str) and bool(value) and "\x00" not in value


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _path(value, prefix=True, kind="lane-policy"):
    _require(
        _text(value) and "\\" not in value and not value.startswith("/"),
        "relative POSIX path",
        "invalid path",
        kind,
    )
    parts = (
        value[:-1].split("/") if prefix and value.endswith("/") else value.split("/")
    )
    _require(
        all(p not in {"", ".", "..", ".git"} for p in parts)
        and not any(c in value for c in "*?[]"),
        "non-escaping literal path",
        "invalid path components",
        kind,
    )
    return value


def _paths(value, *, sorted_=True, prefix=True, kind="lane-policy"):
    _require(isinstance(value, list), "path array", "wrong type", kind)
    for path in value:
        _path(path, prefix, kind)
    _require(
        len(set(value)) == len(value) and (not sorted_ or value == sorted(value)),
        "unique ordered paths",
        "duplicate or unordered paths",
        kind,
    )
    return value


def _covers(root, path):
    return path == root.rstrip("/") or (root.endswith("/") and path.startswith(root))


def _within(roots, path):
    return any(_covers(root, path) for root in roots)


def _overlaps(a, b):
    return _covers(a, b) or _covers(b, a)


def _absolute(value):
    if isinstance(value, os.PathLike):
        value = os.fspath(value)
    _require(_text(value), "canonical absolute root", "missing root")
    path = Path(value)
    _require(
        path.is_absolute() and path.resolve() == path,
        "canonical absolute root",
        "relative or redirected root",
    )
    return path


def _leaf(root, rel, kind="lane-artifact"):
    _path(rel, False, kind)
    result = root / rel
    _require(
        result.resolve().is_relative_to(root.resolve()),
        "contained retained leaf",
        "escaping resolved path",
        kind,
    )
    for parent in (result, *result.parents):
        if parent == root:
            break
        _require(not parent.is_symlink(), "non-symlink retained path", "symlink", kind)
    _require(
        result.is_file() and result.stat().st_nlink == 1,
        "regular singly linked retained leaf",
        "unavailable or linked leaf",
        kind,
    )
    return result


def _git(repo, *args):
    result = subprocess.run(  # noqa: S603 -- fixed Git executable and read-only verbs
        ["/usr/bin/git", "--no-optional-locks", "-C", str(repo), *args],
        env={
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        },
        capture_output=True,
        timeout=30,
        check=False,
    )
    _require(
        result.returncode == 0 and not result.stderr,
        "readable pinned Git object",
        "Git read unavailable",
    )
    return result.stdout


def _blob(repo, ref, path):
    _require(_matches(_REF, ref), "full Git object id", "invalid ref")
    _path(path, False)
    return _git(repo, "show", f"{ref}:{path}")


def _reader(context):
    anchor, reader = context["custody_anchor"], context["reader"]
    _require(
        context["repository"] == anchor["repository"],
        "anchor repository",
        "repository substitution",
    )
    _require(
        _matches(_REF, anchor["consumer_revision"]),
        "admitted consumer revision",
        "missing consumer",
    )
    _require(
        _text(anchor["owner"])
        and ":" not in anchor["owner"]
        and "\n" not in anchor["owner"],
        "owner principal",
        "invalid principal",
    )
    _absolute(anchor["repository"])
    host = _absolute(anchor["host_home"])
    checkout = _absolute(reader["checkout"])
    _require(
        anchor["reader"] == {k: reader[k] for k in ("ref", "runtime_sha256")},
        "previously admitted reader tuple",
        "reader substitution",
    )
    manifest = reader["runtime_manifest"]
    _require(
        isinstance(manifest, dict)
        and manifest
        and _sha(_canonical(manifest)) == reader["runtime_sha256"],
        "retained runtime manifest digest",
        "runtime mismatch",
    )
    python = Path(reader["python"])
    _require(
        python.is_absolute() and str(python.resolve()) in manifest,
        "admitted absolute Python executable",
        "missing executable custody",
    )
    for name, digest in manifest.items():
        path = _absolute(name)
        _require(
            _matches(_DIGEST, digest)
            and path.is_file()
            and _sha(path.read_bytes()) == digest,
            "stationary runtime file bytes",
            "runtime file mismatch",
        )
    _require(
        not (checkout / "ops/lane.local.conf").exists(),
        "no reader local configuration",
        "local configuration present",
    )
    # Repository execution inputs are checked against the old reader revision.
    code = {
        Path(name).relative_to(checkout).as_posix()
        for name in manifest
        if Path(name).is_relative_to(checkout)
    }
    required = {
        "ops/conductor/tools/decisions.py",
        "ops/conductor/tools/laneconf.py",
        "ops/lane.conf",
    }
    _require(required <= code, "complete pinned reader sources", "missing source")
    for rel in code:
        path = _leaf(checkout, rel, "lane-policy")
        _require(
            path.read_bytes() == _blob(checkout, reader["ref"], rel)
            and str(path.resolve()) in manifest,
            "Git-verified reader closure",
            "changed or unheld source",
        )
        if path.suffix == ".py":
            cached = list((path.parent / "__pycache__").glob(path.stem + ".*.pyc"))
            _require(
                not cached and not path.with_suffix(".pyc").exists(),
                "no cached reader code",
                "unadmitted bytecode input",
            )
    return anchor, reader, checkout, host


def _show(context, record):
    _require(_matches(_ID, record), "decision id", "invalid id")
    _anchor, reader, checkout, host = _reader(context)
    script = checkout / "ops/conductor/tools/decisions.py"
    # -I/-S excludes user site, startup and environment overlays. Only the
    # independently pinned source directory is reintroduced for local imports.
    bootstrap = (
        "import sys,runpy; p=sys.argv.pop(1); "
        "sys.path.insert(0,p.rsplit('/',1)[0]); runpy.run_path(p,run_name='__main__')"
    )
    result = subprocess.run(  # noqa: S603 -- executable and source closure verified above
        [
            reader["python"],
            "-I",
            "-S",
            "-B",
            "-c",
            bootstrap,
            str(script),
            "show",
            record,
        ],
        cwd=checkout,
        env={"HOME": str(host), "LC_ALL": "C", "LANG": "C"},
        capture_output=True,
        timeout=30,
        check=False,
    )
    _require(
        result.returncode == 0 and not result.stderr,
        "successful strict register show",
        "unavailable register evidence",
    )
    value = _strict(result.stdout)
    _closed(value, "decision events")
    _require(
        isinstance(value["decision"], dict) and isinstance(value["events"], list),
        "register row and ordered events",
        "malformed register result",
    )
    return result.stdout, value


def _record(context, retained, kind):
    _closed(retained, "record stdout sha256")
    raw = retained["stdout"]
    raw = raw.encode("utf-8") if isinstance(raw, str) else raw
    _require(
        isinstance(raw, bytes) and _sha(raw) == retained["sha256"],
        "exact show stdout digest",
        "retained show digest mismatch",
    )
    live, value = _show(context, retained["record"])
    _require(live == raw, "unchanged live show bytes", "register evidence changed")
    row, events = value["decision"], value["events"]
    _closed(
        row,
        "id question home standing blocked_on decided_by decided_at evidence recorded_by supersedes superseded_by created_at created_by",
    )
    principal = context["custody_anchor"]["owner"]
    _require(
        row["id"] == retained["record"]
        and row["home"] == _POLICY_PATH
        and row["standing"] == "ratified"
        and row["superseded_by"] is None
        and row["decided_by"] == principal
        and _text(row["decided_at"])
        and _text(row["recorded_by"]),
        "ratified current owner decision",
        "non-authorizing row",
    )
    prefix = principal + ": "
    _require(
        isinstance(row["evidence"], str) and row["evidence"].startswith(prefix),
        "exact principal-prefixed evidence",
        "malformed evidence",
    )
    payload = _strict(row["evidence"][len(prefix) :])
    extra = {
        "admission": "reader standing_grants",
        "standing": "paths purpose",
        "job": "paths purpose job dispatch lineage",
    }[kind]
    _closed(payload, "kind policy owner_words " + extra)
    _require(
        payload["kind"] == f"lane-policy-{kind}/v1" and _text(payload["owner_words"]),
        "typed owner evidence",
        "wrong evidence kind or missing words",
    )
    _closed(payload["policy"], "ref sha256")
    _require(
        _matches(_REF, payload["policy"]["ref"])
        and _matches(_DIGEST, payload["policy"]["sha256"]),
        "exact policy identity",
        "invalid policy identity",
    )
    deciding = []
    for event in events:
        # The existing register calls these verb/decision_id; verified mocks
        # may use the contract's kind/id projection of the same row.
        keys = (
            "id timestamp agent kind detail"
            if "kind" in event
            else "verb decision_id agent timestamp detail"
        )
        _closed(event, keys)
        verb = event.get("kind", event.get("verb"))
        event_id = event.get("id", event.get("decision_id"))
        _require(event_id == row["id"], "same decision event history", "foreign event")
        if verb in {
            "ratified",
            "ratify",
            "rejected",
            "reject",
            "superseded",
            "supersede",
        }:
            deciding.append((verb, event))
    _require(
        len(deciding) == 1 and deciding[0][0] in {"ratified", "ratify"},
        "one matching ratification",
        "conflicting deciding history",
    )
    event = deciding[0][1]
    _require(
        event["timestamp"] == row["decided_at"]
        and event["agent"] == row["recorded_by"]
        and event["detail"] == row["evidence"],
        "ratification matching row",
        "mismatched deciding event",
    )
    if row["supersedes"] is not None:
        _, predecessor = _show(context, row["supersedes"])
        _require(
            predecessor["decision"].get("id") == row["supersedes"]
            and predecessor["decision"].get("standing") == "superseded"
            and predecessor["decision"].get("superseded_by") == row["id"],
            "live superseded predecessor",
            "invalid predecessor",
        )
    return payload


def _policy(data):
    value = _strict(data)
    _require(isinstance(value, dict), "policy object", "wrong type")
    keys = "schema standing shared_read_roots protected_authority_paths profiles"
    _closed(value, keys + (" default_profile" if "default_profile" in value else ""))
    _require(
        value["schema"] == _SCHEMA and value["standing"] == "proposal",
        "supported inert policy protocol",
        "unsupported schema or standing",
    )
    for key in ("shared_read_roots", "protected_authority_paths"):
        _paths(value[key], sorted_=False)
    profiles = value["profiles"]
    _require(
        isinstance(profiles, dict) and profiles, "nonempty profiles", "missing profiles"
    )
    for name, profile in profiles.items():
        _require(_matches(_PROFILE, name), "profile id", "malformed profile")
        _closed(
            profile,
            "write_roots forbidden_dependency_roots authority_maintenance allow_declared_outputs",
        )
        for key in ("write_roots", "forbidden_dependency_roots"):
            _paths(profile[key], sorted_=False)
        for key in ("authority_maintenance", "allow_declared_outputs"):
            _require(type(profile[key]) is bool, "boolean profile flags", "wrong type")
    if "default_profile" in value:
        _require(
            _matches(_PROFILE, value["default_profile"])
            and value["default_profile"] in profiles,
            "existing default profile",
            "invalid default",
        )
    return value


def _source(context, source, component, value=None):
    _closed(source, "component kind path ref sha256")
    _require(
        source["component"] == component,
        "matching source component",
        "source substitution",
    )
    kind = source["kind"]
    if kind == "absent":
        _require(
            all(source[k] is None for k in ("path", "ref", "sha256")),
            "explicit absent source",
            "malformed absence",
        )
        return
    _require(
        _matches(_DIGEST, source["sha256"]), "source byte digest", "invalid digest"
    )
    if kind == "invocation":
        _require(
            source["path"] == component and source["ref"] is None,
            "retained invocation identity",
            "invalid invocation source",
        )
        if value is not None:
            _require(
                source["sha256"] == _sha(_canonical(value)),
                "exact retained invocation bytes",
                "source/value digest mismatch",
            )
    elif kind == "git":
        raw = _blob(context["repository"], source["ref"], source["path"])
        _require(
            _sha(raw) == source["sha256"],
            "pinned declaration bytes",
            "source digest mismatch",
        )
        closure = context.get("declaration_sources")
        _require(
            closure is not None and source in closure,
            "old admitted declaration closure",
            "unheld Git source identity",
        )
    else:
        _require(False, "declared source kind", "unknown source kind")


def _declarations(context, declarations):
    _closed(
        declarations,
        "selection requested_scope job_grants role_grants adapter_grants outputs reservations sources",
    )
    # Round-trip also rejects non-JSON values and non-finite numbers.
    _canonical(declarations)
    selection = declarations["selection"]
    _closed(selection, "harness model effort role job_role profile")
    _require(_matches(_PROFILE, selection["harness"]), "harness id", "invalid harness")
    for key in ("model", "effort"):
        value = selection[key]
        if key == "effort" and value is None:
            continue
        _require(
            isinstance(value, str)
            and 0 < len(value) <= 128
            and all(32 <= ord(c) <= 126 for c in value),
            "explicit printable model and effort",
            "invalid selection",
        )
    conductor = selection["role"] == "conductor"
    _require(
        (
            conductor
            and selection["job_role"] is None
            and context["job"] is None
            and context["stage"] == "conduct"
        )
        or (
            selection["role"] == "worker"
            and selection["job_role"] in {"read", "write"}
            and _text(context["job"])
            and context["stage"] != "conduct"
        ),
        "consistent selection axes",
        "role/job/stage mismatch",
    )
    for key in ("requested_scope", "job_grants", "role_grants", "adapter_grants"):
        grant = declarations[key]
        _closed(grant, "repository outputs")
        _paths(grant["repository"])
        _paths(grant["outputs"], prefix=False)
        _require(
            all(_matches(_OUTPUT_PATH, p) and len(p) <= 240 for p in grant["outputs"]),
            "C2 output path grammar",
            "invalid output grant",
        )
    if selection["job_role"] == "read":
        _require(
            not declarations["role_grants"]["repository"],
            "read role without source grants",
            "repository grant on read role",
        )
    if conductor:
        _require(
            declarations["job_grants"] == {"repository": [], "outputs": []}
            and declarations["role_grants"] == {"repository": [], "outputs": []}
            and declarations["outputs"] == [],
            "conductor without worker grants",
            "worker grants on conductor",
        )
    outputs = declarations["outputs"]
    _require(isinstance(outputs, list), "C2 output array", "wrong type")
    seen, artifacts, scratch = [], set(), 0
    reservations = _paths(declarations["reservations"], prefix=False)
    _require(
        all(_matches(_OUTPUT_PATH, p) and len(p) <= 240 for p in reservations),
        "C2 reservation path grammar",
        "invalid reservation",
    )
    _require(
        {"COMMIT_MSG", "last-message.json"} <= set(reservations),
        "declared transport reservations",
        "missing mandatory reservation",
    )
    for output in outputs:
        _require(isinstance(output, dict), "C2 declaration", "wrong type")
        is_file = output.get("kind") == "file"
        _closed(output, "kind path artifact" if is_file else "kind path")
        _require(
            output["kind"] in {"file", "scratch"}, "C2 output kind", "unknown kind"
        )
        path = _path(output["path"], False)
        _require(
            _matches(_OUTPUT_PATH, path) and len(path) <= 240,
            "C2 output path grammar",
            "invalid output declaration",
        )
        _require(
            not any(_overlaps(p + "/", path + "/") for p in seen + reservations),
            "disjoint output and transport paths",
            "output collision",
        )
        seen.append(path)
        if is_file:
            artifact = output["artifact"]
            _require(
                _matches(_ARTIFACT, artifact) and artifact not in artifacts,
                "unique artifact key",
                "invalid or duplicate artifact",
            )
            artifacts.add(artifact)
        else:
            scratch += 1
    _require(
        scratch <= 1, "at most one scratch subtree", "multiple scratch declarations"
    )
    sources = declarations["sources"]
    _require(isinstance(sources, list), "source array", "wrong type")
    seen = []
    covered = set()
    for source in sources:
        component = source.get("component") if isinstance(source, dict) else None
        _require(
            component in _COMPONENTS, "declared source component", "unknown source"
        )
        value = declarations[_COMPONENTS[component]]
        _source(context, source, component, value)
        identity = tuple(source[k] or "" for k in ("component", "kind", "path", "ref"))
        _require(identity not in seen, "unique source identity", "duplicate source")
        seen.append(identity)
        covered.add(component)
        if source["kind"] == "absent":
            allowed = component in {"scope", "outputs"} or (
                conductor and component == "job"
            )
            empty = value == [] or value == {"repository": [], "outputs": []}
            _require(
                allowed and empty,
                "absence supplying empty grants",
                "unavailable required source",
            )
    _require(
        seen == sorted(seen) and covered == set(_COMPONENTS),
        "complete ordered declaration sources",
        "missing or unordered sources",
    )
    return conductor


class _Bound(dict):
    """Closed serializable projection plus non-serializable trusted custody."""

    __slots__ = ("_state", "pending_evidence")

    def __init__(self, projection, state):
        super().__init__(projection)
        self._state = state
        self.pending_evidence = {}


def _bind(context, declarations):
    _reader(context)
    _require(
        "instruction_source" not in context,
        "old admitted instruction closure",
        "candidate instruction promotion",
    )
    register = context["register_evidence"]
    _closed(register, "admission standing per_job")
    admission = register["admission"]
    _require(
        admission["record"] == context["custody_anchor"]["admission_id"],
        "anchor admission id",
        "admission substitution",
    )
    payload = _record(context, admission, "admission")
    _require(
        payload["reader"] == context["custody_anchor"]["reader"],
        "old admitted reader tuple",
        "self-admitted replacement",
    )
    identity = payload["policy"]
    raw = _blob(context["repository"], identity["ref"], _POLICY_PATH)
    _require(
        _sha(raw) == identity["sha256"],
        "admitted policy blob bytes",
        "policy digest mismatch",
    )
    policy = _policy(raw)
    conductor = _declarations(context, declarations)
    selected = []
    if context.get("selection") is not None:
        _require(
            isinstance(context["selection"], dict)
            and "profile" in context["selection"],
            "explicit selection provenance",
            "malformed selection",
            "lane-profile",
        )
        selected.append(context["selection"]["profile"])
    for value in (
        declarations["selection"]["profile"],
        context.get("declaration_profile"),
    ):
        if value is not None:
            selected.append(value)
    if not selected and "default_profile" in policy:
        selected.append(policy["default_profile"])
    _require(
        bool(selected)
        and all(_matches(_PROFILE, p) and p in policy["profiles"] for p in selected)
        and all(p == selected[0] for p in selected),
        "one existing agreed profile",
        "absent invalid or conflicting selection",
        "lane-profile",
    )
    profile = selected[0]
    _require(
        _matches(_REF, context["snapshot_ref"]),
        "known selected Git ref",
        "invalid snapshot",
    )
    _closed(context["lineage"], "branch base_sha")
    _require(
        _text(context["dispatch_id"])
        and _text(context["lineage"]["branch"])
        and _matches(_REF, context["lineage"]["base_sha"]),
        "reserved dispatch and frozen lineage",
        "missing identity",
    )
    template = context["template"]
    _closed(template, "path sha256")
    _require(
        _sha(_blob(context["repository"], context["snapshot_ref"], template["path"]))
        == template["sha256"],
        "old template bytes",
        "template digest mismatch",
    )
    ids = payload["standing_grants"]
    _require(
        isinstance(ids, list)
        and all(_matches(_ID, i) for i in ids)
        and ids == sorted(set(ids)),
        "complete standing grant set",
        "invalid standing ids",
    )
    _require(
        isinstance(register["standing"], list)
        and isinstance(register["per_job"], list)
        and [r["record"] for r in register["standing"]] == ids,
        "all admission-listed standing rows",
        "missing or substituted standing row",
    )
    maintenance_paths, standing_paths = [], []
    receipts = {"standing": [], "per_job": []}
    for section, kind in (("standing", "standing"), ("per_job", "job")):
        seen = []
        for row in register[section]:
            grant = _record(context, row, kind)
            _require(
                grant["policy"] == identity,
                "same admitted policy",
                "foreign grant policy",
            )
            paths = _paths(grant["paths"], prefix=kind == "standing")
            _require(
                paths and _text(grant["purpose"]),
                "nonempty maintenance coverage and purpose",
                "empty grant",
            )
            if kind == "job":
                _require(
                    not conductor
                    and grant["job"] == context["job"]
                    and grant["dispatch"] == context["dispatch_id"]
                    and grant["lineage"] == context["lineage"]
                    and not any(_within(standing_paths, p) for p in paths),
                    "uncovered paths for this exact job and lineage",
                    "foreign or redundant per-job grant",
                )
            else:
                standing_paths.extend(paths)
            maintenance_paths.extend(paths)
            seen.append(row["record"])
            receipts[section].append({"record": row["record"], "sha256": row["sha256"]})
        _require(
            seen == sorted(set(seen)),
            "unique ordered grant records",
            "duplicate or unordered grants",
        )
    protected_requested = any(
        _overlaps(root, protected)
        for root in declarations["requested_scope"]["repository"]
        for protected in policy["protected_authority_paths"]
    )
    maintenance = (
        receipts
        if any(receipts.values()) and protected_requested and not conductor
        else None
    )
    grants = {
        key: copy.deepcopy(declarations[source])
        for key, source in (
            ("scope", "requested_scope"),
            ("job", "job_grants"),
            ("role", "role_grants"),
            ("adapter", "adapter_grants"),
        )
    }
    grants["outputs"] = {
        "repository": [],
        "outputs": sorted(o["path"] for o in declarations["outputs"]),
    }
    grants["maintenance"] = (
        sorted(set(maintenance_paths)) if maintenance is not None else []
    )
    receipt = {
        "schema": _SCHEMA,
        "path": _POLICY_PATH,
        **identity,
        "admission": {"record": admission["record"], "sha256": admission["sha256"]},
        "profile": profile,
        "template_sha256": template["sha256"],
        "grants_sha256": _sha(_canonical(grants)),
        "maintenance": maintenance,
    }
    selection = copy.deepcopy(declarations["selection"])
    selection["profile"] = profile
    projection = receipt
    if conductor:
        # Opaque provider handles remain private; hash the held, serializable
        # anchor/reader evidence, never runtime objects or callback identities.
        custody = {
            "anchor": {
                key: context["custody_anchor"][key]
                for key in (
                    "owner",
                    "host_home",
                    "repository",
                    "admission_id",
                    "consumer_revision",
                    "reader",
                )
            },
            "reader": {
                key: context["reader"][key]
                for key in ("ref", "runtime_sha256", "runtime_manifest")
            },
            "register": register,
        }
        projection = {
            "policy": receipt,
            "selection": selection,
            "dispatch": context["dispatch_id"],
            "stage": "conduct",
            "job": None,
            "lineage": copy.deepcopy(context["lineage"]),
            "snapshot_ref": context["snapshot_ref"],
            "template": copy.deepcopy(template),
            "declarations_sha256": _sha(_canonical(declarations)),
            "custody_sha256": _sha(_canonical(custody)),
        }
    state = {
        "context": context,
        "declarations": copy.deepcopy(declarations),
        "policy": policy,
        "profile": policy["profiles"][profile],
        "selection": selection,
        "grants": grants,
        "receipt": copy.deepcopy(receipt),
        "projection": copy.deepcopy(projection),
        "conductor": conductor,
    }
    bound = _Bound(projection, state)
    parent = context.get("parent_binding")
    if parent is not None:
        _require(
            isinstance(parent, _Bound) and dict(parent) == dict(bound),
            "stationary parent binding",
            "changed resume binding",
            "lane-resume",
        )
    return bound


def bind_launch(trusted_context, declarations):
    """Bind admitted old authority and closed declarations without effects."""
    try:
        # Copy known data by value while preserving unstructured trusted handles.
        context = dict(trusted_context)
        for key in (
            "custody_anchor",
            "reader",
            "register_evidence",
            "lineage",
            "selection",
            "template",
        ):
            context[key] = _trusted_copy(trusted_context[key])
        return _bind(context, declarations)
    except Refusal:
        raise
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        _require(
            False,
            "available valid trusted binding inputs",
            "malformed or unavailable input",
        )


def _stationary(binding, resume=False):
    kind = "lane-resume" if resume else "lane-policy"
    _require(
        isinstance(binding, _Bound),
        "trusted bound handle",
        "unbound or copied receipt",
        kind,
    )
    state = binding._state
    _require(
        dict(binding) == state["projection"],
        "unchanged held binding",
        "binding mutation",
        kind,
    )
    try:
        fresh = _bind(state["context"], state["declarations"])
        _require(
            dict(fresh) == state["projection"],
            "recomputed stationary binding",
            "binding drift",
        )
    except Refusal as error:
        if resume:
            raise Refusal("lane-resume:" + str(error).split(":", 1)[1]) from error
        raise
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        subprocess.SubprocessError,
    ) as error:
        raise Refusal(
            f"{kind}: expected stationary trusted binding; found unavailable authority; needed verified admitted inputs"
        ) from error
    return state


def _decode(endpoint):
    _closed(endpoint, "path_b64 mode sha256", "lane-artifact")
    encoded = endpoint["path_b64"]
    _require(
        isinstance(encoded, str), "canonical path base64", "wrong type", "lane-artifact"
    )
    try:
        raw = base64.b64decode(encoded, validate=True)
        path = os.fsdecode(raw)
        valid = (
            base64.b64encode(raw).decode("ascii") == encoded
            and os.fsencode(path) == raw
        )
    except (ValueError, UnicodeError):
        valid, path = False, ""
    _require(
        valid, "lossless padded base64 path", "unrepresentable path", "lane-artifact"
    )
    _path(path, False, "lane-artifact")
    _require(
        endpoint["mode"] in {"100644", "100755", "120000"}
        and _matches(_DIGEST, endpoint["sha256"]),
        "supported Git mode and byte digest",
        "invalid endpoint",
        "lane-artifact",
    )
    return path


def _manifest(value, evidence):
    _closed(value, "snapshot_ref head entries", "lane-artifact")
    _require(
        value["snapshot_ref"] == evidence["snapshot_ref"]
        and value["head"] == evidence["head"]
        and isinstance(value["entries"], list),
        "manifest bound to exact candidate",
        "manifest ref mismatch",
        "lane-artifact",
    )
    result, identities = [], []
    for entry in value["entries"]:
        _closed(entry, "layer status before after", "lane-artifact")
        _require(
            entry["layer"] in {"committed", "index", "worktree", "output"}
            and entry["status"] in {"A", "M", "D", "T", "R", "C", "?", "!"},
            "declared layer and status",
            "unsupported artifact",
            "lane-artifact",
        )
        before, after = (
            None if entry[k] is None else _decode(entry[k]) for k in ("before", "after")
        )
        status_ = entry["status"]
        valid = (
            (status_ in {"A", "?", "!"} and before is None and after is not None)
            or (status_ == "D" and before is not None and after is None)
            or (status_ in {"M", "T"} and before is not None and before == after)
            or (
                status_ in {"R", "C"}
                and before is not None
                and after is not None
                and before != after
            )
        )
        _require(
            valid,
            "status-consistent endpoints",
            "malformed artifact endpoints",
            "lane-artifact",
        )
        identities.append(
            (
                entry["layer"],
                os.fsencode(before or ""),
                os.fsencode(after or ""),
                status_,
            )
        )
        result.append((entry, before, after))
    _require(
        len(identities) == len(set(identities)),
        "unique artifact entries",
        "duplicate manifest entry",
        "lane-artifact",
    )
    return result


def _output_allowed(state, path):
    if not state["profile"]["allow_declared_outputs"]:
        return False
    for output in state["declarations"]["outputs"]:
        root = output["path"] + ("/" if output["kind"] == "scratch" else "")
        if _covers(root, path):
            return all(
                output["path"] in state["grants"][k]["outputs"]
                for k in ("scope", "role", "adapter")
            )
    return False


def _writes(state, entries, evidence):
    read = state["selection"]["job_role"] == "read" or state["conductor"]
    if read:
        _require(
            evidence["head"] == state["context"]["snapshot_ref"],
            "immutable read-role snapshot",
            "changed HEAD",
            "lane-write",
        )
    for entry, before, after in entries:
        for key, path in (("before", before), ("after", after)):
            if path is None:
                continue
            endpoint = entry[key]
            if entry["layer"] == "output":
                allowed = _output_allowed(state, path) and endpoint["mode"] != "120000"
                root = Path(state["context"]["job_root"]) / "out"
            else:
                allowed = not read and _within(state["profile"]["write_roots"], path)
                allowed = allowed and all(
                    _within(state["grants"][k]["repository"], path)
                    for k in ("scope", "job", "role", "adapter")
                )
                if _within(state["policy"]["protected_authority_paths"], path):
                    allowed = (
                        allowed
                        and state["profile"]["authority_maintenance"]
                        and _within(state["grants"]["maintenance"], path)
                    )
                # A symlink's digest alone does not prove its resolved target.
                if endpoint["mode"] == "120000":
                    allowed = False
                root = Path(
                    state["context"].get(
                        "candidate_root", state["context"]["repository"]
                    )
                )
            _require(
                allowed, "writes within every admitted grant", ascii(path), "lane-write"
            )
            _require(
                (root / path).resolve().is_relative_to(root.resolve()),
                "contained lexical and resolved target",
                ascii(path),
                "lane-write",
            )


def _dependencies(state, value, manifest, entries):
    kind = "lane-dependency"
    _closed(
        value,
        "snapshot_ref head artifacts_sha256 producer coverage edges unresolved unavailable",
        kind,
    )
    _require(
        value["snapshot_ref"] == manifest["snapshot_ref"]
        and value["head"] == manifest["head"]
        and value["artifacts_sha256"] == _sha(_canonical(manifest)),
        "dependencies bound to exact artifacts",
        "stale dependency evidence",
        kind,
    )
    try:
        producer = value["producer"]
        _source(state["context"], producer, "dependencies")
        _require(producer["kind"] != "absent", "admitted analyzer", "absent analyzer")
        held = state["context"].get("dependency_producer")
        if held is not None:
            _require(
                producer == held,
                "previously admitted analyzer identity",
                "analyzer substitution",
            )
    except Refusal as error:
        raise Refusal(str(error).replace("lane-policy:", kind + ":", 1)) from error
    coverage = _paths(value["coverage"], kind=kind)
    _require(
        value["unavailable"] is None and value["unresolved"] == [],
        "available completely resolved analysis",
        "unavailable or unresolved analysis",
        kind,
    )
    required = list(state["context"].get("dependency_coverage", []))
    # Exact requested leaves and every changed source endpoint are mandatory;
    # transitive/runtime closure is supplied by the admitted analyzer owner.
    required.extend(
        p for p in state["grants"]["scope"]["repository"] if not p.endswith("/")
    )
    required.extend(
        p
        for entry, before, after in entries
        if entry["layer"] != "output"
        for p in (before, after)
        if p is not None
    )
    _require(
        all(_within(coverage, p) for p in required),
        "complete held required coverage",
        "missing inspected source",
        kind,
    )
    edges = value["edges"]
    _require(isinstance(edges, list), "resolved edge array", "wrong type", kind)
    encodings = []
    for edge in edges:
        _closed(edge, "source_b64 kind target_space target_root", kind)
        source = _decode(
            {"path_b64": edge["source_b64"], "mode": "100644", "sha256": "0" * 64}
        )
        _require(
            edge["kind"] in {"import", "autoload", "subprocess", "service"}
            and _within(coverage, source),
            "inspected source and typed runtime edge",
            "uncovered edge",
            kind,
        )
        target = edge["target_root"]
        if edge["target_space"] == "repository":
            _path(target, kind=kind)
            _require(
                not any(
                    _overlaps(root, target)
                    for root in state["profile"]["forbidden_dependency_roots"]
                ),
                "runtime edges outside forbidden roots",
                ascii(target),
                kind,
            )
        else:
            _require(
                edge["target_space"] == "host"
                and isinstance(target, str)
                and target in state["context"].get("dependency_host_roots", [])
                and str(Path(target).resolve()) == target,
                "verified external coupling root",
                "unadmitted host dependency",
                kind,
            )
        encodings.append(_canonical(edge))
    _require(
        encodings == sorted(set(encodings)),
        "unique sorted edges",
        "unordered or duplicate edges",
        kind,
    )


def _handle(state, handle):
    _closed(handle, "path sha256", "lane-artifact")
    _require(
        _matches(_DIGEST, handle["sha256"]),
        "retained byte digest",
        "invalid digest",
        "lane-artifact",
    )
    path = handle["path"]
    _path(path, False, "lane-artifact")
    _require(
        not _covers("out/", path) and not _covers("snapshot/", path),
        "launcher-owned receipt outside worker writes",
        "worker-writable receipt",
        "lane-artifact",
    )
    root = _absolute(state["context"]["job_root"])
    data = _leaf(root, path).read_bytes()
    _require(
        _sha(data) == handle["sha256"],
        "exact retained bytes",
        "receipt digest mismatch",
        "lane-artifact",
    )
    return data


def _outputs(state, value, entries, transition, prior=False):
    kind = "lane-artifact"
    _closed(value, "dispatch attempt files", kind)
    _require(
        value["dispatch"] == state["context"]["dispatch_id"],
        "output receipt for reserved dispatch",
        "foreign dispatch receipt",
        kind,
    )
    attempt = value["attempt"]
    _require(
        isinstance(value["files"], list), "ordered file receipts", "wrong type", kind
    )
    if attempt is None:
        _require(
            transition == "launch" and value["files"] == [],
            "completed registered attempt at acceptance",
            "null preflight attempt",
            kind,
        )
        return
    _require(
        type(attempt) is int and attempt > 0,
        "positive registered attempt",
        "invalid attempt",
        kind,
    )
    declared = [o for o in state["declarations"]["outputs"] if o["kind"] == "file"]
    files = value["files"]
    _require(
        len(files) == len(declared),
        "every declared file exactly once",
        "incomplete file receipts",
        kind,
    )
    for output, receipt in zip(declared, files, strict=True):
        _closed(receipt, "artifact path sha256 bytes production reuse evidence", kind)
        _require(
            all(receipt[k] == output[k] for k in ("artifact", "path"))
            and _matches(_DIGEST, receipt["sha256"])
            and type(receipt["bytes"]) is int
            and receipt["bytes"] > 0,
            "ordered declared nonempty file receipt",
            "invalid file receipt",
            kind,
        )
        handles = receipt["evidence"]
        _require(
            isinstance(handles, list) and handles,
            "nonempty production evidence",
            "missing production evidence",
            kind,
        )
        retained = [_handle(state, h) for h in handles]
        if receipt["production"] == "fresh":
            _require(
                receipt["reuse"] is None,
                "null reuse for fresh production",
                "unexpected reuse",
                kind,
            )
            _require(
                any(
                    len(data) == receipt["bytes"] and _sha(data) == receipt["sha256"]
                    for data in retained
                ),
                "retained accepted file bytes",
                "missing file bytes",
                kind,
            )
        else:
            _require(
                receipt["production"] == "reuse",
                "fresh or verified reuse",
                "unknown production",
                kind,
            )
            reuse = receipt["reuse"]
            _closed(reuse, "attempt receipt", kind)
            _require(
                type(reuse["attempt"]) is int and 0 < reuse["attempt"] < attempt,
                "strictly earlier attempt",
                "future or invalid reused attempt",
                kind,
            )
            earlier = _strict(_handle(state, reuse["receipt"]))
            _require(
                earlier.get("attempt") == reuse["attempt"]
                and earlier.get("dispatch") == value["dispatch"],
                "earlier receipt from this dispatch",
                "foreign or mismatched reuse",
                kind,
            )
            _outputs(state, earlier, [], transition, prior=True)
            matches = [
                f
                for f in earlier["files"]
                if all(
                    f[k] == receipt[k] for k in ("path", "artifact", "sha256", "bytes")
                )
            ]
            _require(
                len(matches) == 1,
                "unchanged prior accepted file",
                "stale reuse digest",
                kind,
            )
        if not prior:
            measured = [
                entry["after"]
                for entry, _, after in entries
                if entry["layer"] == "output" and after == receipt["path"]
            ]
            _require(
                len(measured) == 1
                and measured[0]["sha256"] == receipt["sha256"]
                and measured[0]["mode"] != "120000",
                "receipt matching measured output",
                "missing or stale output artifact",
                kind,
            )


def _retain(binding, kind, value, transition):
    state = binding._state
    raw = _canonical(value)
    digest = _sha(raw)
    if transition == "launch":
        handle = {"path": f"receipts/{kind}-{digest}.json", "sha256": digest}
        binding.pending_evidence[handle["path"]] = raw
        return handle
    context = state["context"]
    retain = context.get("retain_evidence")
    if callable(retain):
        handle = retain(kind, raw)
    else:
        handle = context.get("evidence_handles", {}).get(kind)
    _require(
        handle is not None,
        "retained launcher-owned evidence handle",
        "held but unpersisted evidence",
        "lane-artifact",
    )
    _require(
        _handle(state, handle) == raw,
        "retained current evidence bytes",
        "stale evidence handle",
        "lane-artifact",
    )
    return copy.deepcopy(handle)


def check_transition(binding, candidate_evidence, transition):
    """Recheck old authority and exact candidate evidence; never accept claims."""
    evidence = candidate_evidence if isinstance(candidate_evidence, dict) else {}
    state = binding._state if isinstance(binding, _Bound) else None
    result = {
        "binding": copy.deepcopy(state["projection"]) if state else None,
        "snapshot_ref": state["context"]["snapshot_ref"]
        if state
        else evidence.get("snapshot_ref"),
        "head": evidence.get("head") if _matches(_REF, evidence.get("head")) else None,
        "artifacts": None,
        "dependencies": None,
        "outputs": None,
        "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": "refused",
        "refusal": None,
    }
    try:
        state = _stationary(binding, transition == "resume")
        _require(
            transition in _TRANSITIONS,
            "declared acceptance transition",
            "unknown transition",
        )
        _closed(
            evidence,
            "snapshot_ref head artifacts dependencies outputs",
            "lane-artifact",
        )
        _require(
            evidence["snapshot_ref"] == state["context"]["snapshot_ref"]
            and _matches(_REF, evidence["head"])
            and len(evidence["head"]) == len(evidence["snapshot_ref"]),
            "known matching candidate refs",
            "unavailable or mismatched ref",
            "lane-artifact",
        )
        _require(
            not state["conductor"]
            or transition not in {"collect-before", "collect-after", "land", "ladder"},
            "worker-stage acceptance evidence",
            "conductor record",
            "lane-policy",
        )
        entries = _manifest(evidence["artifacts"], evidence)
        if transition == "launch":
            _require(
                all(
                    _output_allowed(state, output["path"])
                    for output in state["declarations"]["outputs"]
                ),
                "all required C2 output grants",
                "unavailable output grant",
                "lane-write",
            )
        _writes(state, entries, evidence)
        _dependencies(state, evidence["dependencies"], evidence["artifacts"], entries)
        ordering = [
            (
                entry["layer"],
                os.fsencode(before or ""),
                os.fsencode(after or ""),
                entry["status"],
            )
            for entry, before, after in entries
        ]
        _require(
            ordering == sorted(ordering),
            "sorted artifact entries",
            "unordered manifest",
            "lane-artifact",
        )
        _outputs(state, evidence["outputs"], entries, transition)
        for key in ("artifacts", "dependencies", "outputs"):
            result[key] = _retain(binding, key, evidence[key], transition)
        result.update(outcome="pass", refusal=None)
    except Refusal as error:
        result["refusal"] = str(error)
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        result["refusal"] = (
            "lane-artifact: expected complete verifiable evidence; found malformed or unavailable evidence; "
            "needed fresh launcher-owned evidence"
        )
    return result


def _tool_arguments(role, kind, target, args):
    validator = role.get("validate_tool")
    if callable(validator):
        return validator(kind, target, args) is True
    # These narrow structured read projections contain no arbitrary
    # shell execution. Other lever schemas stay with their admitted owners.
    if kind == "read" and target == "inspect":
        if set(args) == {"query"}:
            return _text(args["query"])
        if set(args) == {"path"}:
            _path(args["path"], False)
            return True
    if kind == "read" and target == "git-status":
        return set(args) == {"argv"} and args["argv"] in (
            ["git", "status"],
            ["git", "status", "--short"],
        )
    if kind == "delegate" and target in {"dispatch", "go", "ladder"}:
        return (
            set(args) == {"frontend", "job"}
            and args["frontend"] == f"ops/bin/{target}.sh"
            and _text(args["job"])
        )
    if kind == "coordinate" and target == "board":
        return set(args) == {"query"} and args["query"] in {
            "branches",
            "prs",
            "decisions",
            "dispatches",
            "all",
        }
    if kind == "mcp-read" and target == "lane_start":
        return (
            set(args) == {"profile"}
            and args["profile"] == role["binding"]["selection"]["profile"]
        )
    return False


def evaluate_tool(bound_role, normalized_request):
    """Return one closed, request-bound decision; enforcement remains adapter-owned."""
    request = normalized_request if isinstance(normalized_request, dict) else {}
    result = {
        "schema": "conductor-decision/1",
        "id": request.get("id"),
        "binding_sha256": request.get("binding_sha256"),
        "outcome": "refuse",
        "refusal": None,
    }
    reason = "malformed-request"
    try:
        _closed(request, "schema id binding_sha256 kind target arguments")
        _require(
            len(_canonical(request)) <= 65536
            and request["schema"] == "conductor-tool/1"
            and _text(request["id"])
            and _matches(_DIGEST, request["binding_sha256"])
            and isinstance(request["arguments"], dict)
            and _text(request["target"])
            and request["kind"]
            in {"read", "delegate", "coordinate", "mcp-read", "forbidden"},
            "closed bounded tool request",
            "malformed request",
        )
        reason = "binding-mismatch"
        binding = bound_role["binding"]
        state = _stationary(binding)
        _require(
            state["conductor"]
            and _sha(_canonical(dict(binding))) == request["binding_sha256"],
            "current conductor binding",
            "binding mismatch",
        )
        kind, target, args = request["kind"], request["target"], request["arguments"]
        if kind == "forbidden":
            reason = "malformed-request"
            _require(
                target == "implementation"
                and set(args) == {"reason"}
                and args["reason"] in _REASONS,
                "closed forbidden operation",
                "invalid forbidden request",
            )
            reason = args["reason"]
        else:
            reason = "unknown-tool"
            _require(
                target in bound_role["tools"].get(kind, []),
                "admitted tool target",
                "unknown tool",
            )
            reason = "malformed-request"
            _require(
                _tool_arguments(bound_role, kind, target, args),
                "owner-validated arguments",
                "malformed arguments",
            )
            result["outcome"] = "allow"
            return result
    except (
        Refusal,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        pass
    result["refusal"] = {
        "class": "conductor-tool",
        "expected": "declared conductor operation",
        "found": reason,
        "needed": "use canonical dispatch and run the independent doctor for gate diagnosis",
    }
    return result
