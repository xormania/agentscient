"""Helpers for finding-admission prevention-amendment tests.

Public established interfaces only. New enforcement is not imported.
Empty lists, observation keys, hashes and producer identity are checked
against the baseline consumers named in FINDING-ADMISSION.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LAUNCH = REPO / "ops" / "devlane" / "dispatch" / "launch.py"
RECORD = REPO / "ops" / "devlane" / "dispatch" / "record.py"
ENVELOPE = REPO / "ops" / "devlane" / "task" / "envelope.py"
JOBS = REPO / "ops" / "devlane" / "task" / "jobs.json"
WRAPPER = REPO / "ops" / "conductor" / "tools" / "dispatch.sh"
FINDINGS = REPO / "ops" / "conductor" / "tools" / "findings.py"
LADDER_SH = REPO / "ops" / "bin" / "ladder.sh"
LADDER_PY = REPO / "ops" / "conductor" / "tools" / "ladder.py"
TEST_GUARD = REPO / "ops" / "devlane" / "hooks" / "claude" / "test-guard.py"
SUITES = REPO / "ops" / "bin" / "suites.sh"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REF_RE = re.compile(r"^[0-9a-f]{40}$")
WO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PHASES = ("fixture", "acceptance", "final")
REVIEW_KINDS = ("initial", "followup")
TERMINAL = {"action": "draft-pr", "base": "dev"}

# monitor-lever.md §First observation adapters — established consumer, not a guess.
OBSERVATION_KEYS = (
    "subject",
    "state",
    "metrics",
    "generation",
    "observed_at",
    "evidence",
    "reason",
)
OBSERVATION_STATES = frozenset({"ok", "unknown", "unavailable"})
DISPATCH_METRICS = (
    "status",
    "changed",
    "input",
    "cached",
    "output",
    "total",
)

# FINDING-ADMISSION.md verification receipt closed object.
VERIFICATION_KEYS = (
    "dispatch",
    "attempt",
    "phase",
    "work_order",
    "declaration_sha256",
    "scope_sha256",
    "ref",
    "tests",
    "tests_sha256",
    "executor",
    "by",
    "started",
    "ended",
    "commands",
    "status",
    "reason",
)
ADMISSION_BRIEF_KEYS = (
    "work_order",
    "declaration_sha256",
    "scope_sha256",
    "review",
)
REVIEW_REQUEST_KEYS = ("slot", "kind", "prior", "projection_sha256", "changes")
CHANGE_KEYS = (
    "key",
    "correction_record",
    "before_ref",
    "after_ref",
    "paths",
    "behavior",
)
WORK_ORDER_KEYS = (
    "id",
    "branch",
    "base_ref",
    "scope",
    "authority",
    "test_scope",
    "fixture",
    "acceptance",
    "final",
    "reviews",
    "terminal",
)
COMMAND_ROW_KEYS = ("id", "command", "inputs")
PATH_SHA_KEYS = ("path", "sha256")
PAID_JOBS = (
    "author-tests",
    "check-tests",
    "implement",
    "security-audit",
    "adversarial-review",
    "adjudicate",
)
REFUSAL_LAUNCH = 3
REFUSAL_VERIFY_CLI = 2


def canonical_json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def retain_list(value, *, default=None, name="value"):
    """Keep an explicit list, including [].

    `value or default` substitutes defaults for planted `[]`. That is the
    measured empty-list defect. None is the only missing-list signal.
    """
    if value is None:
        if default is None:
            raise ValueError(
                f"{name}: expected a list; found null; needed an explicit list"
            )
        return list(default)
    if not isinstance(value, list):
        raise TypeError(
            f"{name}: expected a list; found {type(value).__name__}; "
            "needed a JSON array"
        )
    return list(value)


def substituting_list(value, default):
    """The defective helper: explicit [] becomes default."""
    return list(value or default)


def path_sha(path, digest) -> dict:
    rel = str(path)
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("path must be a nonblank string")
    if not SHA256_RE.fullmatch(digest):
        raise ValueError(f"sha256 must be 64 lowercase hex, found {digest!r}")
    return {"path": rel, "sha256": digest}


def command_row(ident: str, command: str, inputs=None) -> dict:
    rows = retain_list(inputs, default=[], name="inputs")
    if not ident or not str(ident).strip():
        raise ValueError("command id must be nonblank")
    if not command or not str(command).strip():
        raise ValueError("command must be nonblank")
    return {
        "id": ident,
        "command": command,
        "inputs": [path_sha(item["path"], item["sha256"]) for item in rows],
    }


def observation(payload: dict) -> dict:
    """Accept only the established monitor observation object."""
    if not isinstance(payload, dict):
        raise TypeError("observation must be an object")
    extra = set(payload) - set(OBSERVATION_KEYS)
    missing = set(OBSERVATION_KEYS) - set(payload)
    if extra or missing:
        raise ValueError(
            "observation keys: expected "
            + ",".join(OBSERVATION_KEYS)
            + f"; found extra={sorted(extra)} missing={sorted(missing)}; "
            "needed the monitor-lever reading object"
        )
    state = payload["state"]
    if state not in OBSERVATION_STATES:
        raise ValueError(
            f"state: expected one of {sorted(OBSERVATION_STATES)}; "
            f"found {state!r}; needed a distinct ok/unknown/unavailable"
        )
    metrics = payload["metrics"]
    if not isinstance(metrics, dict):
        raise TypeError("metrics must be an object")
    return {key: payload[key] for key in OBSERVATION_KEYS}


def guessed_observation(payload: dict) -> dict:
    """A wrong consumer that invented event/metric names. Must not pass."""
    return {
        "event": payload.get("event") or payload.get("subject"),
        "metric": payload.get("metric") or payload.get("metrics"),
        "when": payload.get("when") or payload.get("observed_at"),
    }


def work_order(
    *,
    ident: str,
    branch: str,
    base_ref: str,
    scope: dict,
    authority: list,
    test_scope: list,
    fixture: list,
    acceptance: list,
    final: list,
    reviews: list,
    terminal: dict | None = None,
) -> dict:
    body = {
        "id": ident,
        "branch": branch,
        "base_ref": base_ref,
        "scope": dict(scope),
        "authority": list(authority),
        "test_scope": list(test_scope),
        "fixture": list(fixture),
        "acceptance": list(acceptance),
        "final": list(final),
        "reviews": list(reviews),
        "terminal": dict(terminal or TERMINAL),
    }
    if set(body) != set(WORK_ORDER_KEYS):
        raise ValueError("work-order keys drifted from the contract")
    if not WO_ID_RE.fullmatch(ident):
        raise ValueError(f"work-order id {ident!r} is not the contracted form")
    if not REF_RE.fullmatch(base_ref) and not re.fullmatch(r"[0-9a-f]{64}", base_ref):
        raise ValueError("base_ref must be a full commit object id")
    ids = []
    for phase in ("fixture", "acceptance", "final"):
        for row in body[phase]:
            ids.append(row["id"])
            if set(row) != set(COMMAND_ROW_KEYS):
                raise ValueError(f"command row keys {sorted(row)}")
            retain_list(row["inputs"], name=f"{row['id']}.inputs")
    if len(ids) != len(set(ids)):
        raise ValueError(f"command ids must be unique, found {ids}")
    if body["terminal"] != TERMINAL:
        raise ValueError(f"terminal must be {TERMINAL}, found {body['terminal']}")
    return body


def declaration_bytes(body: dict) -> bytes:
    # Hash declaration bytes without reformatting: callers write these bytes.
    text = json.dumps(body, ensure_ascii=False, indent=2) + "\n"
    return text.encode("utf-8")


def review_request(
    *,
    slot: str,
    kind: str,
    prior=None,
    projection_sha256=None,
    changes=None,
) -> dict:
    if kind not in REVIEW_KINDS:
        raise ValueError(f"kind must be initial or followup, found {kind!r}")
    prior_list = retain_list(prior, default=[], name="prior")
    change_list = retain_list(changes, default=[], name="changes")
    if kind == "initial":
        if prior_list or change_list or projection_sha256 is not None:
            raise ValueError("initial review has prior=[], projection_sha256=null, changes=[]")
    else:
        if not prior_list or not change_list or not projection_sha256:
            raise ValueError(
                "followup needs nonempty prior, projection digest and changes"
            )
    return {
        "slot": slot,
        "kind": kind,
        "prior": prior_list,
        "projection_sha256": projection_sha256,
        "changes": change_list,
    }


def admission_brief(
    work_order_id: str,
    declaration_sha256: str,
    scope_sha256: str,
    review=None,
) -> dict:
    return {
        "work_order": work_order_id,
        "declaration_sha256": declaration_sha256,
        "scope_sha256": scope_sha256,
        "review": review,
    }


def planted_observation(*, subject: str, status: str = "completion") -> dict:
    return observation(
        {
            "subject": subject,
            "state": "ok",
            "metrics": {
                "status": status,
                "changed": 0,
                "input": 0,
                "cached": 0,
                "output": 0,
                "total": 0,
            },
            "generation": {"attempts": 1, "launched": "2026-09-09T00:00:00Z"},
            "observed_at": "2026-09-09T00:00:01Z",
            "evidence": "synthetic dispatch reading",
            "reason": None,
        }
    )


def write_json(path: Path, body: dict) -> str:
    data = declaration_bytes(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    landed = path.read_bytes()
    if landed != data:
        raise RuntimeError(f"plant did not land intact: {path}")
    return sha256_bytes(landed)


def refusal_class(text: str) -> str | None:
    line = (text or "").strip().splitlines()
    if not line:
        return None
    head = line[0].split(":", 1)[0].strip().lower()
    # launch.py prefixes "launch.py: refusal: class: expected ..."
    if "refusal" in head and len(line[0].split(":")) > 2:
        parts = line[0].split(":")
        for part in parts:
            token = part.strip().lower().replace("_", "-")
            if token.startswith("admission-"):
                return token.split()[0]
    token = head.replace("_", "-")
    if token.startswith("admission-") or token in {
        "arguments",
        "identity",
        "conf-key",
        "record",
    }:
        return token
    match = re.search(r"(admission-[a-z]+)", (text or "").lower())
    return match.group(1) if match else None


def jobs_catalogue() -> dict:
    return json.loads(JOBS.read_text(encoding="utf-8"))
