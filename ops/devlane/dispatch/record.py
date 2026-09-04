#!/usr/bin/env python3
"""Construct and validate dev-lane dispatch records."""

from __future__ import annotations

import copy

FIELDS = (
    "id", "lane", "stage", "unit", "lineage", "follows", "job", "role",
    "dispatched_by", "at", "snapshot", "harness", "model", "session",
    "brief", "caps", "overrides", "attempts", "result", "status",
)


class RecordError(ValueError):
    pass


def build(payload=None, **values):
    source = dict(payload or {})
    source.update(values)
    source["lane"] = "dev"
    source.setdefault("follows", [])
    lineage = source.get("lineage") or {}
    if not str(source.get("unit") or "").strip():
        source["unit"] = lineage.get("branch", "")
    harness = copy.deepcopy(source.get("harness"))
    if isinstance(harness, dict):
        isolation = harness.get("isolation")
        if isinstance(isolation, dict):
            isolation.setdefault(
                "observed", {"unresolved": "behavioural probe has not run"})
        source["harness"] = harness
    if source.get("status") == "launched":
        source["result"] = None
    result = {field: copy.deepcopy(source.get(field)) for field in FIELDS}
    return validate(result)


def _need(condition, field, detail="is invalid"):
    if not condition:
        raise RecordError(f"record field {field} {detail}")


def validate(rec):
    _need(isinstance(rec, dict), "record", "must be an object")
    for field in FIELDS:
        _need(field in rec, field, "is missing")
    _need(rec["lane"] == "dev", "lane", "must be dev")
    _need(rec["status"] in {"launched", "closed", "died"}, "status")
    _need(rec["role"] in {"read", "write"}, "role")
    _need(isinstance(rec["follows"], list), "follows", "must be a list")
    _need(isinstance(rec["unit"], str) and bool(rec["unit"].strip()), "unit")
    lineage = rec["lineage"]
    _need(isinstance(lineage, dict) and bool(lineage.get("branch"))
          and bool(lineage.get("base_sha")), "lineage")
    snapshot = rec["snapshot"]
    _need(isinstance(snapshot, dict), "snapshot")
    _need(snapshot.get("mode") in {"whole", "fileset"}, "snapshot.mode")
    harness = rec["harness"]
    _need(isinstance(harness, dict), "harness")
    _need(harness.get("containment") in {"os", "policy"}, "containment")
    isolation = harness.get("isolation")
    _need(isinstance(isolation, dict), "isolation")
    observed = isolation.get("observed")
    _need(isinstance(observed, dict) and (
        bool(str(observed.get("unresolved") or "").strip()) or
        all(key in observed for key in (
            "operator_config_present", "evidence", "checked_at",
            "harness_version"))), "observed")
    model = rec.get("model")
    _need(isinstance(model, dict), "model")
    effort_argv = model.get("effort_argv")
    _need(isinstance(effort_argv, list), "model.effort_argv")
    effort = model.get("effort_requested")
    if effort:
        carriers = {effort, f'model_reasoning_effort="{effort}"'}
        _need(bool(effort_argv) and any(token in carriers for token in effort_argv),
              "model.effort_argv", "must carry model.effort_requested")
        argv = harness.get("argv")
        _need(isinstance(argv, list), "harness.argv", "must be a list")
        width = len(effort_argv)
        _need(any(argv[index:index + width] == effort_argv
                  for index in range(len(argv) - width + 1)),
              "harness.argv", "must carry model.effort_argv in order")
    else:
        _need(effort_argv == [], "model.effort_argv",
              "must be empty without model.effort_requested")
    if model.get("ran") is None:
        if not (rec.get("note") or model.get("note")):
            model["note"] = "no stream was found; model.ran is null"
    elif not model.get("read_from"):
        _need(model.get("ran") != model.get("requested"), "model.ran",
              "cannot copy requested without a stream")
    if rec["status"] == "launched":
        _need(rec["result"] is None, "result", "must be null while launched")
    result = rec.get("result")
    if isinstance(result, dict) and "collected" in result:
        collected = result["collected"]
        valid = (
            isinstance(collected, dict)
            and all(isinstance(collected.get(key), str)
                    and bool(collected[key].strip())
                    for key in ("at", "by", "head"))
            and isinstance(collected.get("verify"), dict)
            and type(collected["verify"].get("exit")) is int
            and collected["verify"]["exit"] == 0
        )
        _need(valid, "result.collected",
              "must carry at, by, head, and verify.exit equal to 0")
    return rec
