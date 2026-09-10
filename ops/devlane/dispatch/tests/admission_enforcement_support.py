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


# --- one bound fixture used by every enforcement file ---

BOUND_WO_ID = "WO-admission-aa41"
BOUND_FAIL_WO_ID = "WO-admission-fail-aa41"
BOUND_TEST_REL = "ops/devlane/dispatch/tests/bound_fixture_check.py"
BOUND_PRODUCER_ID = "20260909T120000Z-tests-grok-aa41a1"
BOUND_REVIEW_ID = "20260909T130000Z-review-claude-aa41b2"
BOUND_CORRECTION_ID = "20260909T140000Z-code-codex-aa41c3"
BOUND_SCOPE_NAME = "owner-scope.md"
BOUND_AUTHORITY_NAME = "owner-enforcement-addendum.md"
BOUND_SCOPE_TEXT = "owner scope for admission enforcement tests\n"
BOUND_AUTHORITY_TEXT = "enforce prevention; not guidance\n"
BOUND_TEST_SOURCE = (
    '"""Planted fixture check: explicit empty lists stay empty."""\n'
    "import json\n"
    "assert json.loads('[]') == []\n"
    "print('fixture-empty-list-ok')\n"
)
SUCCESS_FIXTURE_CMD = f"python3 {BOUND_TEST_REL}"
FAIL_FIXTURE_CMD = 'python3 -c "raise SystemExit(1)"'
REVIEW_JOBS = frozenset({
    "check-tests",
    "security-audit",
    "adversarial-review",
})


def bound_reviews():
    return [
        {"slot": "check-tests", "job": "check-tests"},
        {"slot": "security", "job": "security-audit"},
        {"slot": "adversarial", "job": "adversarial-review"},
        {"slot": "security-re", "job": "security-audit"},
    ]


def initial_request(slot="check-tests"):
    return review_request(slot=slot, kind="initial")


class Bound:
    """One planted work-order plus the files and producer it binds."""

    def __init__(self, **fields):
        self.__dict__.update(fields)

    def __getitem__(self, key):
        return self.__dict__[key]


def _closed_producer_record(*, rec_id, ref, rel, digest, root):
    stream = str(root / "home" / "grok" / "sessions" / "stream.json")
    return {
        "id": rec_id,
        "lane": "dev",
        "stage": "tests",
        "unit": "work",
        "lineage": {"branch": "work", "base_sha": ref},
        "follows": [],
        "job": "author-tests",
        "role": "write",
        "dispatched_by": "Bound Producer <bound-producer@example.invalid>",
        "at": {
            "launched": "2026-09-09T12:00:00Z",
            "closed": "2026-09-09T12:01:00Z",
        },
        "snapshot": {
            "mode": "whole",
            "ref_name": ref,
            "ref_sha": ref,
            "behind_tip": 0,
            "root": str(root / "snapshot"),
        },
        "harness": {
            "name": "grok",
            "version": "1.0.5",
            "isolation": {
                "mechanism": "home",
                "env": {"GROK_HOME": str(root / "home" / "grok")},
                "home": str(root / "home" / "grok"),
                "auth_files": ["auth.json"],
                "store": str(root / "home" / "grok" / "sessions"),
                "observed": {"unresolved": "behavioural probe has not run"},
            },
            "sandbox": "always-approve",
            "containment": "policy",
            "argv": ["grok", "-s", "uuid"],
        },
        "model": {
            "requested": "grok-4.6",
            "effort_requested": None,
            "effort_argv": [],
            "ran": "grok-4.6",
            "read_from": stream,
        },
        "session": {
            "id": "00000000-0000-4000-8000-0000000000a1",
            "stream": stream,
            "stream_sha256_at_close": "1" * 64,
        },
        "brief": {
            "template": {
                "path": "ops/devlane/task/jobs.json",
                "sha256": "c" * 64,
            },
            "scope": "bound fixture producer",
            "inputs": [],
            "sha256": "d" * 64,
            "bytes": 24,
        },
        "caps": {"cap-out": 500000, "source": "wires.py"},
        "overrides": [],
        "attempts": [],
        "result": {
            "envelope": {
                "job": "author-tests",
                "status": "ok",
                "verdict": None,
                "counts": {"p1": 0, "p2": 0, "p3": 0, "opinions": 0},
                "findings": [],
                "artifacts": {Path(rel).stem: rel},
                "spend": {"harness": "grok", "total": 0, "out": 0, "runs": 1},
                "stamp": {"ref": ref, "started": None, "ended": None},
                "note": f"synthetic producer of {rel} at {digest}",
            }
        },
        "status": "closed",
    }


def attach_bound(
    test,
    *,
    ident=BOUND_WO_ID,
    fixture_command=SUCCESS_FIXTURE_CMD,
    fixture_id="fx-bound",
    acceptance_id="ac-bound",
    final_id="fn-bound",
    slot="check-tests",
):
    """Plant one coherent bound work-order on a `_TempLaunch` test.

    Tracks the fixture-check file, binds a synthetic independent
    author-tests producer to that commit, and writes the frozen
    declaration plus an initial review request. Empty command inputs
    stay empty.
    """
    rel = BOUND_TEST_REL
    path = test._write(rel, BOUND_TEST_SOURCE)
    landed = path.read_text(encoding="utf-8")
    if landed != BOUND_TEST_SOURCE:
        raise RuntimeError(f"bound test plant did not land: {path}")
    producer_ref = test._commit(f"tests: plant {rel}")
    test.ref = producer_ref
    digest = sha256_file(path)
    producer_root = test.home / "producer" / BOUND_PRODUCER_ID
    (producer_root / "home" / "grok" / "sessions").mkdir(parents=True)
    (producer_root / "snapshot").mkdir(parents=True)
    (producer_root / "home" / "grok" / "sessions" / "stream.json").write_text(
        "{}\n", encoding="utf-8",
    )
    rec = _closed_producer_record(
        rec_id=BOUND_PRODUCER_ID,
        ref=producer_ref,
        rel=rel,
        digest=digest,
        root=producer_root,
    )
    rec_path = (
        test.repo / ".dev" / "records" / "dispatches" / f"{BOUND_PRODUCER_ID}.json"
    )
    write_json(rec_path, rec)
    test.ref = test._commit("records: bind independent test producer")

    scope_path = test.home / BOUND_SCOPE_NAME
    scope_path.write_text(BOUND_SCOPE_TEXT, encoding="utf-8")
    if scope_path.read_text(encoding="utf-8") != BOUND_SCOPE_TEXT:
        raise RuntimeError("scope plant did not land")
    scope_sha = sha256_text(BOUND_SCOPE_TEXT)

    authority_path = test.home / BOUND_AUTHORITY_NAME
    authority_path.write_text(BOUND_AUTHORITY_TEXT, encoding="utf-8")
    authority_sha = sha256_file(authority_path)

    body = work_order(
        ident=ident,
        branch=test.lineage,
        base_ref=test.root_sha,
        scope={"path": BOUND_SCOPE_NAME, "sha256": scope_sha},
        authority=[{"path": BOUND_AUTHORITY_NAME, "sha256": authority_sha}],
        test_scope=[rel],
        fixture=[command_row(fixture_id, fixture_command, [])],
        acceptance=[command_row(
            acceptance_id,
            "python3 -m unittest discover -s ops/devlane/dispatch/tests "
            "-p test_admission_enforcement_verify.py",
            [],
        )],
        final=[command_row(final_id, "ops/bin/suites.sh", [])],
        reviews=bound_reviews(),
    )
    if body["fixture"][0]["inputs"] != []:
        raise RuntimeError("bound fixture inputs must stay empty")
    wo_path = test.home / "work-order.json"
    declaration_sha256 = write_json(wo_path, body)

    request = initial_request(slot=slot)
    request_path = test.home / "review-request.json"
    request_sha256 = write_json(request_path, request)
    if request["prior"] != [] or request["changes"] != []:
        raise RuntimeError("initial request prior/changes must stay empty")

    return Bound(
        ident=ident,
        wo_path=wo_path,
        body=body,
        digest=declaration_sha256,
        scope_path=scope_path,
        scope_sha=scope_sha,
        authority_path=authority_path,
        request_path=request_path,
        request=request,
        request_sha256=request_sha256,
        producer_id=BOUND_PRODUCER_ID,
        producer_ref=producer_ref,
        test_rel=rel,
        test_sha=digest,
        fixture_command=fixture_command,
    )


def bound_extra(bound, job, extra=(), *, unit=None, request_path=None):
    flags = ["--work-order", str(bound.wo_path), "--input", str(bound.scope_path)]
    if job in REVIEW_JOBS:
        flags = [
            "--review-request",
            str(request_path or bound.request_path),
            *flags,
        ]
    if unit is not None:
        flags.extend(["--unit", unit])
    flags.extend(list(extra))
    return flags


def write_followup_request(
    dest,
    *,
    slot,
    prior,
    projection,
    key,
    correction_record,
    before_ref,
    after_ref,
    paths,
    behavior,
):
    digest = sha256_text(canonical_json(projection))
    req = review_request(
        slot=slot,
        kind="followup",
        prior=list(prior),
        projection_sha256=digest,
        changes=[{
            "key": key,
            "correction_record": correction_record,
            "before_ref": before_ref,
            "after_ref": after_ref,
            "paths": list(paths),
            "behavior": behavior,
        }],
    )
    write_json(dest, req)
    return req, digest


def plant_stdout_handle(directory: Path, name: str, text: str) -> dict:
    path = Path(directory) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    if path.read_bytes() != data:
        raise RuntimeError(f"process-byte plant did not land: {path}")
    return {"path": str(path), "sha256": sha256_bytes(data)}


def verification_entry(
    *,
    dispatch,
    attempt,
    phase,
    work_order_id,
    declaration_sha256,
    scope_sha256,
    ref,
    tests,
    commands,
    executor_path=str(LAUNCH),
    by="Launch Test <noreply@example.invalid>",
    status="ok",
    reason=None,
):
    tests_list = list(tests)
    entry = {
        "dispatch": dispatch,
        "attempt": attempt,
        "phase": phase,
        "work_order": work_order_id,
        "declaration_sha256": declaration_sha256,
        "scope_sha256": scope_sha256,
        "ref": ref,
        "tests": tests_list,
        "tests_sha256": sha256_text(canonical_json(tests_list)),
        "executor": {
            "path": executor_path,
            "sha256": sha256_file(Path(executor_path)) if Path(executor_path).is_file() else "e" * 64,
        },
        "by": by,
        "started": "2026-09-09T00:00:00Z",
        "ended": "2026-09-09T00:00:01Z",
        "commands": list(commands),
        "status": status,
        "reason": reason,
    }
    if set(entry) != set(VERIFICATION_KEYS):
        raise ValueError(f"verification keys drifted: {sorted(entry)}")
    return entry
