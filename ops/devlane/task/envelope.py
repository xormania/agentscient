#!/usr/bin/env python3
"""The typed envelope every task returns, and the rules it enforces.

`CONTRACT.md` §The envelope states the shape; this module is the only
place that builds one, so the shape cannot vary by caller. The rules
below are not validation for its own sake — each one closes a way the
caller could be misled while reading nothing but this dict:

**A task that could not look must not approve** (§Statuses). `status`
routes and `verdict` judges, and only a task that actually ran — status
`ok` — may carry `approve`. `invalid` carries no verdict at all, and
`tripped` may report what it found but never that the job is clean.

**Counts are derived, never asserted.** A tally accepted from a caller
is a second copy of the findings list, and two copies drift. `build`
computes it, and `validate` refuses an envelope whose tally has stopped
matching its findings — which is what a truncated list from a harness
looks like from the outside.

**A finding with no reproduction is an opinion, and says so.** The
`reproduce` key is always present; absence is `None` in the data rather
than a key the caller has to notice is missing. `counts["opinions"]` is
that same fact where routing can see it.

**Artifacts are handles, not contents.** The property this whole app
exists for is that iteration N costs the caller about what iteration 1
cost, and the way that breaks is prose migrating into the envelope. A
handle is one line and shorter than HANDLE_MAX; anything else is
content, and content belongs in the file the handle names.
"""

from __future__ import annotations

import json
import re
import copy

#: Key order is part of the shape: a caller diffing two envelopes, or a
#: reviewer reading one, sees the same fields in the same places.
FIELDS = ("job", "status", "verdict", "counts", "findings",
          "artifacts", "spend", "stamp", "note")
FINDING_FIELDS = ("severity", "where", "claim", "reproduce")
SPEND_FIELDS = ("harness", "total", "out", "runs")
STAMP_FIELDS = ("ref", "started", "ended")

STATUSES = ("ok", "invalid", "tripped")
VERDICTS = ("approve", "changes")
SEVERITIES = ("p1", "p2", "p3")

#: Longer than any path this lane produces, far shorter than a review.
HANDLE_MAX = 512

CLASSIFICATIONS = ('demonstrated-defect', 'scope-expansion', 'unproven')
REVIEW_JOBS = ('check-tests', 'security-audit', 'adversarial-review', 'adjudicate')
_NONBLANK = {'type': 'string', 'pattern': r'\S'}
_NULLABLE_TEXT = {'type': ['string', 'null'], 'pattern': r'\S'}
_DIGEST = {'type': 'string', 'pattern': r'^[0-9a-f]{64}$'}
EVALUATION_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'classification': {'type': 'string', 'enum': list(CLASSIFICATIONS)},
        'scope_sha256': _DIGEST,
        **{key: _NULLABLE_TEXT for key in ('requirement', 'trigger', 'failure')},
        'evidence': {'type': ['object', 'null'], 'additionalProperties': False,
                     'required': ['kind', 'details'], 'properties': {
                         'kind': {'type': 'string', 'enum': ['reproduction', 'execution-path']},
                         'details': _NONBLANK}},
        'refutation': _NONBLANK,
        'source': {'type': ['object', 'null'], 'additionalProperties': False,
                   'required': ['key', 'sha256'], 'properties': {
                       'key': {'type': 'string', 'pattern': r'^[^#\s]+#[1-9][0-9]*$'},
                       'sha256': _DIGEST}},
        'ruling': {'type': ['string', 'null'], 'enum': [None, 'UPHELD', 'PARTIAL', 'REJECTED']},
    },
    'required': ['classification', 'scope_sha256', 'requirement', 'trigger',
                 'failure', 'evidence', 'refutation', 'source', 'ruling'],
    'allOf': [{
        'if': {'properties': {'classification': {'const': 'demonstrated-defect'}}},
        'then': {'properties': {
            **{key: _NONBLANK for key in ('requirement', 'trigger', 'failure')},
            'evidence': {'type': 'object'},
        }},
    }],
}

#: The wire shape supplied to structured-output capable harnesses.  This is
#: deliberately beside ``FIELDS`` and the constructor: callers do not keep a
#: second, gradually diverging description of an envelope.
ENVELOPE_SCHEMA = {
    "type": "object",
    "properties": {
        "job": {"type": "string"},
        "status": {"type": "string", "enum": list(STATUSES)},
        "verdict": {
            "type": ["string", "null"],
            "enum": [*VERDICTS, None],
        },
        "counts": {
            "type": "object",
            "properties": {
                key: {"type": "integer", "minimum": 0}
                for key in (*SEVERITIES, "opinions")
            },
            "required": [*SEVERITIES, "opinions"],
            "additionalProperties": False,
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                    "where": {"type": "string"},
                    "claim": {"type": "string"},
                    "reproduce": {"type": ["string", "null"]},
                    "evaluation": EVALUATION_SCHEMA,
                },
                "required": list(FINDING_FIELDS),
                "additionalProperties": False,
            },
        },
        "artifacts": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "spend": {"type": "object"},
        "stamp": {
            "type": "object",
            "properties": {
                "ref": {"type": "string"},
                "started": {"type": ["string", "null"]},
                "ended": {"type": ["string", "null"]},
            },
            "required": ["ref"],
            "additionalProperties": False,
        },
        "note": {"type": ["string", "null"]},
        "commit": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["subject", "body"],
            "additionalProperties": False,
        },
    },
    "required": list(FIELDS),
    "additionalProperties": False,
}


class EnvelopeError(ValueError):
    """The envelope would have misled the caller. Refuse, never repair."""


class OutputsError(EnvelopeError):
    """A declaration or bound output path cannot satisfy C2."""


TRANSPORT_RESERVED = frozenset({"COMMIT_MSG", "last-message.json"})
_OMITTED = object()
_PATH_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$"
_ARTIFACT_PATTERN = r"^[a-z][a-z0-9_-]*$"
OUTPUTS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "uniqueItems": True,
    "items": {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "kind": {"const": "file"},
                    "path": {"$ref": "#/$defs/path"},
                    "artifact": {
                        "type": "string", "pattern": _ARTIFACT_PATTERN,
                        "maxLength": 64,
                    },
                },
                "required": ["kind", "path", "artifact"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"const": "scratch"},
                    "path": {"$ref": "#/$defs/path"},
                },
                "required": ["kind", "path"],
                "additionalProperties": False,
            },
        ],
    },
    "$defs": {
        "path": {"type": "string", "maxLength": 240,
                 "pattern": _PATH_PATTERN},
    },
}


def _outputs_refuse(expected, found, *, kind="outputs-schema"):
    raise OutputsError(
        f"{kind}: expected {expected}; found {found}; "
        "needed correct trusted output declaration or canonical output root")


def _output_name(value, pattern, limit, field):
    if (not isinstance(value, str) or len(value) > limit
            or re.fullmatch(pattern, value) is None):
        _outputs_refuse(f"{field} matching {pattern!r}, max {limit}", repr(value))


def _overlaps(left, right):
    return (left == right or left.startswith(right + "/")
            or right.startswith(left + "/"))


def validate_outputs(value=_OMITTED, reserved=TRANSPORT_RESERVED):
    """Validate native declarations without inferring grants or normalizing paths."""
    if value is _OMITTED:
        value = []
    if not isinstance(value, list):
        _outputs_refuse("an outputs array (omission means [])", repr(value))
    if not isinstance(reserved, (list, tuple, set, frozenset)):
        _outputs_refuse("a collection of transport paths", repr(reserved))
    for path in reserved:
        _output_name(path, _PATH_PATTERN, 240, "transport path")
    reservations = TRANSPORT_RESERVED.union(reserved)
    paths, artifacts = [], set()
    scratch = False
    result = []
    for row in value:
        if not isinstance(row, dict) or row.get("kind") not in ("file", "scratch"):
            _outputs_refuse("a file or scratch object", repr(row))
        is_file = row["kind"] == "file"
        keys = {"kind", "path", "artifact"} if is_file else {"kind", "path"}
        if set(row) != keys:
            _outputs_refuse(f"exact members {sorted(keys)}", repr(row))
        path = row["path"]
        _output_name(path, _PATH_PATTERN, 240, "path")
        for other in (*paths, *sorted(reservations)):
            if _overlaps(path, other):
                _outputs_refuse("unique non-overlapping output/transport paths",
                                f"{path!r} overlaps {other!r}")
        paths.append(path)
        if is_file:
            key = row["artifact"]
            _output_name(key, _ARTIFACT_PATTERN, 64, "artifact")
            if key in artifacts:
                _outputs_refuse("unique artifact keys", repr(key))
            artifacts.add(key)
        elif scratch:
            _outputs_refuse("at most one scratch entry", repr(row))
        else:
            scratch = True
        result.append(dict(row))
    return result


def load_outputs(text, reserved=TRANSPORT_RESERVED):
    """Strict JSON text seam: reject repeated members before dict collapse."""
    def object_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                _outputs_refuse("unique JSON object members", repr(key))
            obj[key] = value
        return obj

    def constant(value):
        _outputs_refuse("strict JSON", value)

    if not isinstance(text, str):
        _outputs_refuse("JSON text", type(text).__name__)
    try:
        value = json.loads(text, object_pairs_hook=object_pairs,
                           parse_constant=constant)
    except json.JSONDecodeError as exc:
        _outputs_refuse("valid JSON text", str(exc))
    return validate_outputs(value, reserved=reserved)


def outputs_from_job(spec):
    """Only an explicit outputs member supplies declarations, including natives."""
    if not isinstance(spec, dict):
        _outputs_refuse("a job object", repr(spec))
    return validate_outputs(spec.get("outputs", _OMITTED))


def _bound_output(row, out_root):
    # The launcher proves filesystem canonicality and custody. Here we reject
    # noncanonical lexical spellings; never resolve, create or inspect a path.
    if (not isinstance(out_root, str) or not out_root.startswith("/")
            or (out_root != "/" and any(
                part in ("", ".", "..") for part in out_root[1:].split("/")))
            or "\x00" in out_root):
        _outputs_refuse("a canonical absolute output root", repr(out_root),
                        kind="outputs-path")
    path = out_root.rstrip("/") + "/" + row["path"]
    try:
        return _handle(row.get("artifact", "scratch"), path)
    except EnvelopeError as exc:
        _outputs_refuse("a representable output handle", str(exc),
                        kind="outputs-path")


def render_declared_outputs(outputs, out_root):
    """Render the C2 section; this text does not authorize filesystem writes."""
    rows = validate_outputs(outputs)
    lines = ["Declared job outputs:\n"]
    if not rows:
        lines.append("None. No additional worker output write grant.\n")
    for row in rows:
        path = json.dumps(_bound_output(row, out_root), ensure_ascii=True)
        if row["kind"] == "file":
            key = json.dumps(row["artifact"], ensure_ascii=True)
            lines.append(f"Required file: {path}. Write a non-empty document; "
                         f"set artifacts[{key}] to {path}.\n")
        else:
            lines.append(f"Scratch subtree: {path}. Temporary work only; "
                         f"no artifact is required; TMPDIR is {path}.\n")
    return "".join(lines)


def append_declared_outputs(prompt, outputs, out_root):
    return prompt.rstrip("\r\n") + "\n\n" + render_declared_outputs(outputs, out_root)


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeError(f"{field} must be a non-empty string")
    return " ".join(value.split())


def _handle(name, value):
    if not isinstance(value, str):
        raise EnvelopeError(f"artifacts[{name!r}] must be a path string")
    if not value.strip():
        raise EnvelopeError(f"artifacts[{name!r}] is empty")
    if len(value) > HANDLE_MAX:
        raise EnvelopeError(
            f"artifacts[{name!r}] is {len(value)} chars: a handle, not "
            f"contents, is the contract (max {HANDLE_MAX})")
    if "\n" in value or "\r" in value:
        raise EnvelopeError(
            f"artifacts[{name!r}] spans lines: that is the work product, "
            "not a handle to it")
    return value


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnvelopeError(f'duplicate JSON member {key!r}')
        result[key] = value
    return result


def strict_constant(value):
    raise EnvelopeError(f'non-finite JSON number {value}')


def loads(text):
    return json.loads(text, object_pairs_hook=strict_pairs, parse_constant=strict_constant)


def validate_evaluation(value, reproduce=None):
    """Structural duties only; realism and scope membership are reviewer judgments."""
    if not isinstance(value, dict) or set(value) != set(EVALUATION_SCHEMA['required']):
        raise EnvelopeError('evaluation must be a closed object with all declared fields')
    if value['classification'] not in CLASSIFICATIONS:
        raise EnvelopeError('evaluation.classification is unknown')
    def digest(text, field):
        if not isinstance(text, str) or not re.fullmatch(r'[0-9a-f]{64}', text):
            raise EnvelopeError(f'{field} must be 64 lowercase hex digits')
    digest(value['scope_sha256'], 'scope_sha256')
    _text(value['refutation'], 'refutation')
    for field in ('requirement', 'trigger', 'failure'):
        if value[field] is not None:
            _text(value[field], field)
    evidence = value['evidence']
    if evidence is not None:
        if (not isinstance(evidence, dict) or set(evidence) != {'kind', 'details'}
                or evidence['kind'] not in ('reproduction', 'execution-path')):
            raise EnvelopeError('evidence must be a closed reproduction or execution-path object')
        _text(evidence['details'], 'evidence.details')
        if evidence['kind'] == 'reproduction':
            _text(reproduce, 'reproduce')
    if value['classification'] == 'demonstrated-defect' and any(
            value[field] is None for field in ('requirement', 'trigger', 'failure', 'evidence')):
        raise EnvelopeError('demonstrated-defect requires requirement, trigger, failure and evidence')
    source, ruling = value['source'], value['ruling']
    if source is not None:
        if (not isinstance(source, dict) or set(source) != {'key', 'sha256'}
                or not isinstance(source['key'], str)
                or not re.fullmatch(r'[^#\s]+#[1-9][0-9]*', source['key'])):
            raise EnvelopeError('source must bind an original <record>#<n> and sha256')
        digest(source['sha256'], 'source.sha256')
    if (ruling not in (None, 'UPHELD', 'PARTIAL', 'REJECTED')
            or (source is None) != (ruling is None)):
        raise EnvelopeError('source and ruling must be supplied together')
    if ruling is not None and ((ruling != 'REJECTED') != (
            value['classification'] == 'demonstrated-defect')):
        raise EnvelopeError('ruling disagrees with classification')
    return value


def finding(severity, where, claim, reproduce=None, *, evaluation=_OMITTED):
    """One finding, normalized. A blank reproduction is an absent one."""
    if severity not in SEVERITIES:
        raise EnvelopeError(
            f"severity {severity!r} is not one of {list(SEVERITIES)}")
    if isinstance(reproduce, str) and not reproduce.strip():
        reproduce = None
    if reproduce is not None and not isinstance(reproduce, str):
        raise EnvelopeError("reproduce must be a command string or None")
    result = {"severity": severity,
            "where": _text(where, "where"),
            "claim": _text(claim, "claim"),
            "reproduce": reproduce.strip() if reproduce else None}
    if evaluation is not _OMITTED:
        validate_evaluation(evaluation, result['reproduce'])
        result['evaluation'] = copy.deepcopy(evaluation)
    return result


def tally(findings):
    counts = dict.fromkeys(SEVERITIES, 0)
    counts["opinions"] = sum(1 for f in findings if not f.get("reproduce"))
    for f in findings:
        counts[f["severity"]] += 1
    return counts


def _spend(given):
    spend = {"harness": None, "total": 0, "out": 0, "runs": 0}
    for key, value in (given or {}).items():
        if key not in SPEND_FIELDS:
            raise EnvelopeError(f"spend has no field {key!r}")
        spend[key] = value
    if spend["harness"] is not None and not isinstance(spend["harness"], str):
        raise EnvelopeError("spend.harness must be a harness name or None")
    for key in ("total", "out", "runs"):
        value = spend[key]
        if not isinstance(value, int) or isinstance(value, bool):
            raise EnvelopeError(f"spend.{key} must be an integer")
        if value < 0:
            # worth.py prices from these; a negative subtracts from a
            # real cost somewhere else in the ledger.
            raise EnvelopeError(f"spend.{key} is negative")
    return spend


def _stamp(given):
    given = given or {}
    for key in given:
        if key not in STAMP_FIELDS:
            raise EnvelopeError(f"stamp has no field {key!r}")
    # Without a ref the envelope names no state, and a fact with no
    # state behind it cannot be re-checked by anyone, including its
    # author tomorrow.
    ref = given.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        raise EnvelopeError("stamp.ref must name the ref the task read")
    return {"ref": ref.strip(),
            "started": given.get("started"),
            "ended": given.get("ended")}


def build(job, *, status, verdict=None, findings=(), artifacts=None,
          spend=None, stamp=None, note=None):
    """Assemble an envelope, refusing any combination that would lie.

    Every rule about the assembled shape lives in `validate`, which
    this returns through — deliberately, and once. Checking a rule here
    as well would leave two implementations of it, and a suite that
    plants a fault in either one still passes on the other. Measured:
    the approve gate was written in both places and BOTH copies could
    be disabled undetected, because each was covering for the other.
    """
    normalized = []
    for f in findings:
        if (not isinstance(f, dict) or not set(FINDING_FIELDS) <= set(f)
                or set(f) - {*FINDING_FIELDS, 'evaluation'}):
            raise EnvelopeError('finding has missing or extra fields')
        normalized.append(finding(**f))
    env = {
        "job": _text(job, "job"),
        "status": status,
        "verdict": verdict,
        "counts": tally(normalized),
        "findings": normalized,
        "artifacts": {name: _handle(name, value)
                      for name, value in (artifacts or {}).items()},
        "spend": _spend(spend),
        "stamp": _stamp(stamp),
        "note": " ".join(note.split()) if note else None,
    }
    return validate(env)


def invalid(job, note, *, stamp=None, spend=None, artifacts=None):
    """The task could not do its job. `note` says which way, and must.

    The note is required by `validate`, not re-checked here: see
    `build` on why one rule gets exactly one implementation.
    """
    return build(job, status="invalid", verdict=None, stamp=stamp,
                 spend=spend, artifacts=artifacts, note=note)


#: Container fields whose type must be proved before anything iterates
#: or indexes them. `bool` is not accepted for a dict or list by
#: isinstance, so no special case is needed here.
CONTAINER_TYPES = {
    "findings": list,
    "counts": dict,
    "artifacts": dict,
    "spend": dict,
    "stamp": dict,
}


def validate(env, *, outputs=_OMITTED, out_root=None,
             inline_planning_exception=False):
    """Re-check a built or parsed envelope. Returns it, or raises."""
    if not isinstance(env, dict):
        raise EnvelopeError("an envelope is a dict")
    if tuple(key for key in env if key != "commit") != FIELDS:
        raise EnvelopeError(
            f"envelope fields {list(env)} are not the contract's "
            f"{list(FIELDS)}")
    if "commit" in env:
        commit = env["commit"]
        if (not isinstance(commit, dict) or set(commit) != {"subject", "body"}
                or not all(isinstance(commit[key], str) for key in commit)):
            raise EnvelopeError("commit must contain exactly subject and body strings")
    # A worker's JSON arrives here unvalidated, and every check below
    # either iterates or indexes one of these. A wrong type has to raise
    # EnvelopeError -- which the parser turns into an `invalid` envelope
    # -- rather than a TypeError, which escapes the parser and kills the
    # run instead of reporting it (Codex, PR #49: `"findings": null`
    # raised TypeError at the findings loop). Typed here rather than at
    # the one field reported, because the same hole is under every
    # container the contract names.
    for field, want in CONTAINER_TYPES.items():
        if not isinstance(env[field], want):
            raise EnvelopeError(
                f"{field} is {type(env[field]).__name__}, not "
                f"{want.__name__}")
    for f in env["findings"]:
        if not isinstance(f, dict):
            raise EnvelopeError(
                f"a finding is {type(f).__name__}, not dict")
    if env["status"] not in STATUSES:
        raise EnvelopeError(f"status {env['status']!r} is not a status")
    if env["verdict"] is not None and env["verdict"] not in VERDICTS:
        raise EnvelopeError(f"verdict {env['verdict']!r} is not a verdict")
    if env["verdict"] == "approve" and env["status"] != "ok":
        raise EnvelopeError(
            f"a {env['status']!r} task did not do its job and cannot "
            "approve one")
    if env["status"] == "invalid" and env["verdict"] is not None:
        raise EnvelopeError("an invalid task carries no verdict")
    if env["status"] == "invalid" and not env["note"]:
        raise EnvelopeError(
            "an invalid envelope must say why it could not look")
    for f in env["findings"]:
        if (not set(FINDING_FIELDS) <= set(f)
                or set(f) - {*FINDING_FIELDS, 'evaluation'}):
            raise EnvelopeError(
                f"finding fields {list(f)} are not {list(FINDING_FIELDS)}")
        if 'evaluation' not in f and tuple(f) != FINDING_FIELDS:
            raise EnvelopeError('legacy finding fields are not in contract order')
        # `finding` is the one place a finding's rules live; re-running
        # it is how they get checked here without being restated here.
        if finding(**f) != f:
            raise EnvelopeError(f"finding {f} is not in normal form")
    evaluated = [f for f in env['findings'] if 'evaluation' in f]
    if evaluated and env['job'] in REVIEW_JOBS:
        if (not isinstance(env['stamp'].get('ref'), str)
                or not re.fullmatch(r'[0-9a-f]{40}', env['stamp']['ref'])):
            raise EnvelopeError('evaluated review requires a full stamp.ref')
        for f in evaluated:
            if (env['job'] == 'adjudicate') != (f['evaluation']['source'] is not None):
                raise EnvelopeError('evaluation source must match review/adjudicate job')
        if env['status'] == 'ok':
            if len(evaluated) != len(env['findings']):
                raise EnvelopeError('completed evaluated review contains unevaluated findings')
            defects = any(f['evaluation']['classification'] == 'demonstrated-defect'
                          for f in evaluated)
            if env['verdict'] != ('changes' if defects else 'approve'):
                raise EnvelopeError('completed review verdict disagrees with evaluation')
    if env["counts"] != tally(env["findings"]):
        # The list is what the task found; the tally is a copy of it.
        # When they disagree the list is short, which is exactly what a
        # truncated harness reply looks like from out here.
        raise EnvelopeError(
            f"counts {env['counts']} disagree with the findings "
            f"{tally(env['findings'])}: the list is not the tally")
    inline_plan = inline_planning_exception is True and env["job"] == "plan"
    for name, value in env["artifacts"].items():
        if inline_plan and name == "plan":
            _text(value, "artifacts['plan']")
        else:
            _handle(name, value)
    for row in validate_outputs(outputs):
        path = _bound_output(row, out_root)
        if row["kind"] != "file":
            continue
        key = row["artifact"]
        # Partial/invalid envelopes may lack the deliverable. Supplied file
        # references still have to match, and an ok result must carry every key.
        if env["status"] != "ok" and key not in env["artifacts"]:
            continue
        value = env["artifacts"].get(key)
        if inline_plan and key == "plan" and row["path"] == "PLAN.md":
            _text(value, "artifacts['plan']")
        elif value != path:
            raise EnvelopeError(
                f"outputs-handle: expected artifacts[{key!r}] equal {path!r}; "
                f"found {value!r}; needed the exact declared output handle")
    _spend(env["spend"])
    _stamp(env["stamp"])
    return env
