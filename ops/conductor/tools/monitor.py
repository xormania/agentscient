#!/usr/bin/env python3
"""Configurable lane observations; inherits instrument-conventions.md."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
DEFAULT_CONFIG = HERE.parent.parent / "monitor.example.json"
ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
IDENTITY_RE = re.compile(r".+ <[^<>]+>")
BUCKETS = ("core", "graphql", "search")
READING_KEYS = {
    "subject", "state", "metrics", "generation", "observed_at", "evidence", "reason"
}


class Refusal(ValueError):
    def __init__(self, kind: str, expected: str, found: object, needed: str):
        self.kind = kind
        self.expected = expected
        self.found = found
        self.needed = needed
        super().__init__(self.line())

    @staticmethod
    def _one_line(value: object) -> str:
        return " ".join(str(value).split()) or "empty"

    def line(self) -> str:
        return (
            f"{self.kind}: expected {self._one_line(self.expected)}; "
            f"found {self._one_line(self.found)}; "
            f"needed {self._one_line(self.needed)}"
        )


def refuse(kind: str, expected: str, found: object, needed: str) -> None:
    raise Refusal(kind, expected, found, needed)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            refuse("config", "unique JSON object keys", f"duplicate key {key}", "remove the duplicate")
        result[key] = value
    return result


def _object(value: object, where: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        refuse("config", f"{where} to be an object", type(value).__name__, "use the declared object shape")
    if set(value) != keys:
        refuse("config", f"{where} fields {sorted(keys)}", sorted(value), "add missing and remove unknown fields")
    return value


def _number(value: object, where: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        refuse("config", f"{where} to be a finite number", repr(value), "supply a finite JSON number")
    try:
        result = float(value)
    except OverflowError:
        refuse("config", f"{where} to be a finite number", repr(value), "supply a finite JSON number")
    if not math.isfinite(result):
        refuse("config", f"{where} to be a finite number", repr(value), "supply a finite JSON number")
    if minimum is not None and result < minimum:
        refuse("config", f"{where} >= {minimum:g}", repr(value), "raise the value to the declared bound")
    return result


def _enabled(entry: dict[str, object], where: str) -> None:
    if not isinstance(entry["enabled"], bool):
        refuse("config", f"{where}.enabled to be boolean", repr(entry["enabled"]), "use true or false")


def _registry(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        refuse("config", f"{name} to be an object registry", type(value).__name__, "use identifiers as object keys")
    for ident in value:
        if not isinstance(ident, str) or ID_RE.fullmatch(ident) is None:
            refuse("config", f"{name} identifiers matching {ID_RE.pattern}", repr(ident), "rename the identifier")
    return value


def _consumer(value: object, where: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or not value.isprintable()
        or "/" in value
        or "\\" in value
    ):
        refuse("consumer", f"{where} to be 1..128 printable characters without path separators", repr(value), "supply an isolated consumer id")
    return value


def _path(value: object, where: str, base: Path) -> str:
    if not isinstance(value, str) or not value or not value.isprintable():
        refuse("config", f"{where} to be a nonempty path", repr(value), "supply the explicit source path")
    try:
        os.fsencode(value)
        path = Path(value)
        return str((base / path).resolve() if not path.is_absolute() else path.resolve())
    except (OSError, RuntimeError, UnicodeError, ValueError):
        refuse("config", f"{where} to be a valid path", repr(value), "supply the explicit source path")


def _dispatch_params(value: object, base: Path) -> dict[str, object]:
    params = _object(value, "dispatch params", {"store", "ids"})
    ids = params["ids"]
    valid_id = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}")
    if not isinstance(ids, list) or len(ids) > 256 or any(not isinstance(item, str) or valid_id.fullmatch(item) is None for item in ids):
        refuse("config", "dispatch params.ids to be at most 256 path-safe record ids", repr(ids), "supply explicit record basenames")
    if len(set(ids)) != len(ids):
        refuse("config", "dispatch params.ids to be unique", repr(ids), "remove duplicate record ids")
    return {"store": _path(params["store"], "dispatch params.store", base), "ids": list(ids)}


def _codex_params(value: object, base: Path) -> dict[str, object]:
    params = _object(value, "codex-usage params", {"path", "max_bytes"})
    bound = params["max_bytes"]
    if isinstance(bound, bool) or not isinstance(bound, int) or not 1024 <= bound <= 8_388_608:
        refuse("config", "codex-usage params.max_bytes to be an integer from 1024 through 8388608", repr(bound), "use the declared tail bound")
    return {"path": _path(params["path"], "codex-usage params.path", base), "max_bytes": bound}


def _github_params(value: object, _base: Path) -> dict[str, object]:
    params = _object(value, "github-rate params", {"timeout_s"})
    timeout = _number(params["timeout_s"], "github-rate params.timeout_s")
    if not 0 < timeout <= 30:
        refuse("config", "github-rate params.timeout_s in (0, 30]", repr(params["timeout_s"]), "use the declared subprocess deadline")
    return {"timeout_s": timeout}


def load_config(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        refuse("config", f"a readable UTF-8 registry at {path}", type(exc).__name__, "restore the registry or pass --config FILE")
    try:
        data = json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda value: refuse("config", "finite JSON numbers", value, "replace the nonfinite value"))
    except Refusal:
        raise
    except (json.JSONDecodeError, UnicodeError, ValueError, RecursionError) as exc:
        refuse("config", f"valid JSON at {path}", f"{type(exc).__name__} at line {getattr(exc, 'lineno', '?')}", "repair the registry JSON")
    root = _object(data, "registry", {"version", "monitors", "schedules", "conditions", "routes"})
    if type(root["version"]) is not int or root["version"] != 1:
        refuse("config", "registry version 1", repr(root["version"]), "set version to 1")
    schedules = _registry(root["schedules"], "schedules")
    monitors = _registry(root["monitors"], "monitors")
    conditions = _registry(root["conditions"], "conditions")
    routes = _registry(root["routes"], "routes")
    normalized: dict[str, object] = {"version": 1, "schedules": {}, "monitors": {}, "conditions": {}, "routes": {}}
    for ident, raw in schedules.items():
        entry = _object(raw, f"schedules.{ident}", {"enabled", "every_s"})
        _enabled(entry, f"schedules.{ident}")
        every = _number(entry["every_s"], f"schedules.{ident}.every_s", minimum=1)
        normalized["schedules"][ident] = {"enabled": entry["enabled"], "every_s": every}
    base = path.resolve().parent
    for ident, raw in monitors.items():
        entry = _object(raw, f"monitors.{ident}", {"enabled", "adapter", "schedule", "params"})
        _enabled(entry, f"monitors.{ident}")
        adapter = entry["adapter"]
        if not isinstance(adapter, str) or adapter not in ADAPTERS:
            refuse("config", f"monitors.{ident}.adapter in {sorted(ADAPTERS)}", repr(adapter), "choose a registered observation adapter")
        schedule = entry["schedule"]
        if not isinstance(schedule, str) or schedule not in schedules:
            refuse("reference", f"monitors.{ident}.schedule to name a schedule", repr(schedule), "add the target or correct the reference")
        normalized["monitors"][ident] = {
            "enabled": entry["enabled"], "adapter": adapter, "schedule": schedule,
            "params": ADAPTERS[adapter][0](entry["params"], base),
        }
    for ident, raw in conditions.items():
        entry = _object(raw, f"conditions.{ident}", {"enabled", "monitor", "op", "field", "threshold", "cooldown_s"})
        _enabled(entry, f"conditions.{ident}")
        monitor = entry["monitor"]
        if not isinstance(monitor, str) or monitor not in monitors:
            refuse("reference", f"conditions.{ident}.monitor to name a monitor", repr(monitor), "add the target or correct the reference")
        op = entry["op"]
        if not isinstance(op, str) or op not in {"changed", "gt", "lt", "unavailable"}:
            refuse("config", f"conditions.{ident}.op to be changed, gt, lt, or unavailable", repr(op), "choose a declared operator")
        field = entry["field"]
        threshold = entry["threshold"]
        if op == "unavailable":
            if field is not None or threshold is not None:
                refuse("config", f"conditions.{ident} unavailable field and threshold to be null", repr((field, threshold)), "set both values to null")
        else:
            if not isinstance(field, str) or not field:
                refuse("config", f"conditions.{ident}.field to be nonempty", repr(field), "name a reading metric")
            if op == "changed" and threshold is not None:
                refuse("config", f"conditions.{ident}.threshold to be null for changed", repr(threshold), "set threshold to null")
            if op in {"gt", "lt"}:
                threshold = _number(threshold, f"conditions.{ident}.threshold")
        cooldown = _number(entry["cooldown_s"], f"conditions.{ident}.cooldown_s", minimum=0)
        normalized["conditions"][ident] = {
            "enabled": entry["enabled"], "monitor": monitor, "op": op,
            "field": field, "threshold": threshold, "cooldown_s": cooldown,
        }
    for ident, raw in routes.items():
        entry = _object(raw, f"routes.{ident}", {"enabled", "condition", "adapter", "consumer"})
        _enabled(entry, f"routes.{ident}")
        condition = entry["condition"]
        if not isinstance(condition, str) or condition not in conditions:
            refuse("reference", f"routes.{ident}.condition to name a condition", repr(condition), "add the target or correct the reference")
        adapter = entry["adapter"]
        if not isinstance(adapter, str) or adapter not in {"queue", "stdout", "unsupported"}:
            refuse("config", f"routes.{ident}.adapter to be queue, stdout, or unsupported", repr(adapter), "choose a declared delivery adapter")
        normalized["routes"][ident] = {
            "enabled": entry["enabled"], "condition": condition,
            "adapter": adapter, "consumer": _consumer(entry["consumer"], f"routes.{ident}.consumer"),
        }
    return normalized


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _reading(subject: str, state: str, now: datetime, *, metrics: dict[str, object] | None = None, generation: object = None, evidence: object = None, reason: str | None = None) -> dict[str, object]:
    return {"subject": subject, "state": state, "metrics": metrics or {}, "generation": generation, "observed_at": _stamp(now), "evidence": evidence, "reason": reason}


def _json_file(path: Path) -> tuple[str, dict[str, object] | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "missing", None
    except (OSError, UnicodeError):
        return "unavailable", None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError):
        return "unavailable", None
    return ("ok", value) if isinstance(value, dict) else ("unavailable", None)


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _finite_number(value: object) -> bool:
    try:
        return type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        return False


def _process_status(pid: object, rec: dict[str, object]) -> str:
    if not _positive_int(pid):
        return "unknown"
    harness = rec.get("harness") if isinstance(rec.get("harness"), dict) else {}
    argv = harness.get("argv") if isinstance(harness.get("argv"), list) else []
    expected = argv[0] if argv and isinstance(argv[0], str) and argv[0] else None
    proc = Path("/proc") / str(pid)
    if proc.is_dir():
        if expected is None:
            return "unknown"
        try:
            cmdline = [os.fsdecode(token) for token in (proc / "cmdline").read_bytes().split(b"\0") if token]
        except OSError:
            return "unknown"
        matches = any(token == expected or Path(token).name == Path(expected).name for token in cmdline)
        return "running" if matches else "unknown"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "death" if expected else "unknown"
    except PermissionError:
        return "unknown"
    except OSError:
        return "unknown"
    return "unknown"


def read_dispatch(params: dict[str, object], now: datetime) -> list[dict[str, object]]:
    store = Path(params["store"])
    rows = []
    for ident in params["ids"]:
        record_path = store / ident / "record.json"
        state_path = store / ident / "state.json"
        exit_path = store / ident / "exit"
        status, rec = _json_file(record_path)
        evidence = str(record_path)
        if status == "missing":
            rows.append(_reading(ident, "unknown", now, evidence=evidence, reason="record missing"))
            continue
        if status != "ok" or rec is None:
            rows.append(_reading(ident, "unavailable", now, evidence=evidence, reason="record unreadable or malformed"))
            continue
        state_status, state = _json_file(state_path)
        state = state or {}
        result = rec.get("result") if isinstance(rec.get("result"), dict) else {}
        envelope = result.get("envelope") if isinstance(result.get("envelope"), dict) else {}
        changed = result.get("changed_paths")
        metrics: dict[str, object] = {}
        if isinstance(changed, list):
            metrics["changed"] = len(changed)
        spend = rec.get("session") if isinstance(rec.get("session"), dict) else {}
        spend = spend.get("spend") if isinstance(spend.get("spend"), dict) else {}
        for key in ("input", "cached", "output", "total"):
            value = spend.get(key)
            if type(value) is int and value >= 0:
                metrics[key] = value
        env_status = envelope.get("status")
        if env_status in {"invalid", "tripped"}:
            observed = "invalid"
        elif rec.get("status") == "died":
            observed = "death"
        elif rec.get("status") == "closed" and env_status == "ok":
            observed = "no-op" if rec.get("role") == "write" and changed == [] else "completion"
        elif exit_path.is_file():
            observed = "settling"
        elif state_status == "unavailable":
            rows.append(_reading(ident, "unavailable", now, metrics=metrics, evidence=str(state_path), reason="state unreadable or malformed"))
            continue
        else:
            observed = _process_status(state.get("pid"), rec)
        metrics["status"] = observed
        attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        at = rec.get("at") if isinstance(rec.get("at"), dict) else {}
        launched = attempts[-1].get("launched") if attempts and isinstance(attempts[-1], dict) else at.get("launched")
        attempt = state.get("attempt") if _positive_int(state.get("attempt")) else len(attempts)
        generation = {"attempt": attempt, "launched": launched}
        reading_state = "unknown" if observed == "unknown" else "ok"
        rows.append(_reading(ident, reading_state, now, metrics=metrics, generation=generation, evidence=evidence, reason="worker identity not provable" if observed == "unknown" else None))
    return rows


def _usage_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def read_codex_usage(params: dict[str, object], now: datetime) -> list[dict[str, object]]:
    path = Path(params["path"])
    bound = params["max_bytes"]
    try:
        with path.open("rb") as source:
            size = source.seek(0, os.SEEK_END)
            offset = max(0, size - bound)
            source.seek(offset)
            data = source.read(bound)
    except FileNotFoundError:
        return [_reading(str(path), "unknown", now, generation=str(path), evidence=str(path), reason="rollout missing")]
    except OSError:
        return [_reading(str(path), "unavailable", now, generation=str(path), evidence=str(path), reason="rollout unreadable")]
    if offset:
        split = data.find(b"\n")
        data = b"" if split < 0 else data[split + 1 :]
    if data and not data.endswith(b"\n"):
        split = data.rfind(b"\n")
        data = data[: split + 1] if split >= 0 else b""
    last: dict[str, object] | None = None
    for raw in data.splitlines():
        try:
            entry = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(entry, dict) or entry.get("type") != "event_msg":
            continue
        payload = entry.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "token_count":
            last = entry
    if last is None:
        return [_reading(str(path), "unknown", now, generation=str(path), evidence=str(path), reason="no complete token_count row in bounded tail")]
    payload = last["payload"]
    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
    totals = info.get("total_token_usage") if isinstance(info.get("total_token_usage"), dict) else {}
    recent = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
    names = {"input": "input_tokens", "cached": "cached_input_tokens", "output": "output_tokens", "total": "total_tokens"}
    metrics = {name: value for name, key in names.items() if (value := _usage_int(totals.get(key))) is not None}
    if "input" in metrics and metrics.get("cached", 0) > metrics["input"]:
        metrics.pop("cached", None)
    last_input = _usage_int(recent.get("input_tokens"))
    last_cached = _usage_int(recent.get("cached_input_tokens"))
    if last_input is not None and last_cached is not None and last_cached > last_input:
        last_cached = None
    window = _usage_int(info.get("model_context_window"))
    if last_input is not None:
        metrics["last_input"] = last_input
    if last_cached is not None:
        metrics["last_cached"] = last_cached
    if window is not None:
        metrics["context_window"] = window
    if metrics.get("input", 0) > 0 and "cached" in metrics:
        metrics["cache_fraction"] = metrics["cached"] / metrics["input"]
    if last_input is not None and window is not None and window > 0:
        metrics["context_fraction"] = last_input / window
    event_at = last.get("timestamp") if isinstance(last.get("timestamp"), str) else None
    state = "ok" if any(key in metrics for key in names) else "unknown"
    evidence = {"path": str(path), "event_at": event_at}
    return [_reading(str(path), state, now, metrics=metrics, generation=str(path), evidence=evidence, reason=None if state == "ok" else "retained usage fields invalid or absent")]


def read_github_rate(params: dict[str, object], now: datetime) -> list[dict[str, object]]:
    def unavailable(reason: str) -> list[dict[str, object]]:
        return [
            _reading(bucket, "unavailable", now, evidence="gh api rate_limit", reason=reason)
            for bucket in BUCKETS
        ]

    executable = shutil.which("gh")
    if executable is None:
        return unavailable("gh executable unavailable")
    try:
        proc = subprocess.run(
            [executable, "api", "rate_limit"], capture_output=True,
            timeout=params["timeout_s"], check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return unavailable("rate limit process unavailable")
    if proc.returncode:
        return unavailable(f"rate limit process exited {proc.returncode}")
    try:
        data = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return unavailable("rate limit response malformed")
    resources = data.get("resources") if isinstance(data, dict) and isinstance(data.get("resources"), dict) else {}
    rows = []
    for bucket in BUCKETS:
        value = resources.get(bucket)
        if not isinstance(value, dict):
            rows.append(_reading(bucket, "unknown", now, evidence="gh api rate_limit", reason="bucket missing"))
            continue
        limit = _usage_int(value.get("limit"))
        remaining = _usage_int(value.get("remaining"))
        reset = _usage_int(value.get("reset"))
        if limit is None or limit <= 0 or remaining is None or remaining > limit or reset is None:
            rows.append(_reading(bucket, "unknown", now, generation=reset, evidence="gh api rate_limit", reason="bucket fields invalid"))
            continue
        metrics = {"limit": limit, "remaining": remaining, "reset": reset, "remaining_fraction": remaining / limit}
        rows.append(_reading(bucket, "ok", now, metrics=metrics, generation=reset, evidence="gh api rate_limit"))
    return rows


ADAPTERS = {
    "dispatch": (_dispatch_params, read_dispatch),
    "codex-usage": (_codex_params, read_codex_usage),
    "github-rate": (_github_params, read_github_rate),
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (monitor TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, next_due REAL);
CREATE TABLE IF NOT EXISTS condition_state (
 condition_id TEXT NOT NULL, subject TEXT NOT NULL, fingerprint TEXT NOT NULL,
 generation TEXT NOT NULL, epoch INTEGER NOT NULL, baseline TEXT,
 matching INTEGER NOT NULL, pending INTEGER NOT NULL, last_emit REAL, sequence INTEGER NOT NULL,
 PRIMARY KEY(condition_id, subject)
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, route TEXT NOT NULL, consumer TEXT NOT NULL,
 condition_id TEXT NOT NULL, monitor TEXT NOT NULL, subject TEXT NOT NULL,
 state TEXT NOT NULL, summary TEXT NOT NULL, evidence TEXT, observed_at TEXT NOT NULL,
 delivery TEXT NOT NULL, dedup_key TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS cursors (consumer TEXT PRIMARY KEY, event_id INTEGER NOT NULL);
"""


def _fingerprint(value: object) -> str:
    packed = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(packed.encode()).hexdigest()


def _connect(path: Path, *, write: bool) -> sqlite3.Connection | None:
    db = path / "monitor.db"
    if write:
        try:
            path.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db, timeout=30)
            conn.executescript(SCHEMA)
            return conn
        except (OSError, sqlite3.Error) as exc:
            refuse("state", f"a writable SQLite state at {db}", type(exc).__name__, "repair permissions or pass --state DIR")
    if not db.exists():
        return None
    try:
        return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as exc:
        refuse("state", f"a readable SQLite state at {db}", type(exc).__name__, "repair or replace the state database")


def _claim_due(conn: sqlite3.Connection, config: dict[str, object], now_epoch: float) -> list[str]:
    due = []
    monitors = config["monitors"]
    schedules = config["schedules"]
    try:
        conn.execute("BEGIN IMMEDIATE")
        for ident, monitor in monitors.items():
            schedule = schedules[monitor["schedule"]]
            fingerprint = _fingerprint({"monitor": monitor, "schedule": schedule})
            row = conn.execute("SELECT fingerprint,next_due FROM schedules WHERE monitor=?", (ident,)).fetchone()
            active = monitor["enabled"] and schedule["enabled"]
            if not active:
                conn.execute("INSERT INTO schedules(monitor,fingerprint,next_due) VALUES(?,?,NULL) ON CONFLICT(monitor) DO UPDATE SET fingerprint=excluded.fingerprint,next_due=NULL", (ident, fingerprint))
                continue
            clock_rewound = row is not None and row[1] is not None and row[1] - now_epoch > schedule["every_s"]
            if row is None or row[0] != fingerprint or row[1] is None or now_epoch >= row[1] or clock_rewound:
                due.append(ident)
                conn.execute("INSERT INTO schedules(monitor,fingerprint,next_due) VALUES(?,?,?) ON CONFLICT(monitor) DO UPDATE SET fingerprint=excluded.fingerprint,next_due=excluded.next_due", (ident, fingerprint, now_epoch + schedule["every_s"]))
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        refuse("state", "valid writable monitor state", type(exc).__name__, "repair or replace the state database")
    return due


def _truncate(text: str, limit: int = 240) -> str:
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", "ignore")


def _event_summary(condition: dict[str, object], reading: dict[str, object]) -> str:
    field = condition["field"]
    if field is None:
        return _truncate(f"state={reading['state']}")
    value = reading["metrics"].get(field)
    return _truncate(f"{field}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))}")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _evaluate(conn: sqlite3.Connection, config: dict[str, object], observations: dict[str, list[dict[str, object]]], now_epoch: float) -> list[dict[str, object]]:
    emitted: list[dict[str, object]] = []
    conditions = config["conditions"]
    monitors = config["monitors"]
    routes = config["routes"]
    try:
        conn.execute("BEGIN IMMEDIATE")
        known_conditions = set(conditions)
        stale = conn.execute("SELECT DISTINCT condition_id FROM condition_state").fetchall()
        for (condition_id,) in stale:
            if condition_id not in known_conditions:
                conn.execute(
                    "UPDATE condition_state SET fingerprint=?,baseline=NULL,matching=0,pending=0,last_emit=NULL WHERE condition_id=?",
                    (_fingerprint({"removed": condition_id}), condition_id),
                )
        for ident, condition in conditions.items():
            monitor_id = condition["monitor"]
            fingerprint = _fingerprint({"condition": condition, "source": monitors[monitor_id]})
            if not condition["enabled"] or not monitors[monitor_id]["enabled"]:
                conn.execute(
                    "UPDATE condition_state SET fingerprint=?,baseline=NULL,matching=0,pending=0,last_emit=NULL WHERE condition_id=?",
                    (_fingerprint({"inactive": fingerprint}), ident),
                )
                continue
            if monitor_id not in observations:
                continue
            for reading in observations[monitor_id]:
                if set(reading) != READING_KEYS:
                    raise ValueError("reader returned an invalid reading shape")
                subject = reading["subject"]
                generation = _canonical(reading["generation"])
                row = conn.execute(
                    "SELECT fingerprint,generation,epoch,baseline,matching,pending,last_emit,sequence FROM condition_state WHERE condition_id=? AND subject=?",
                    (ident, subject),
                ).fetchone()
                if row is None:
                    epoch, baseline, matching, pending, last_emit, sequence = 1, None, False, False, None, 0
                elif row[0] != fingerprint or row[1] != generation:
                    epoch, baseline, matching, pending, last_emit, sequence = row[2] + 1, None, False, False, None, row[7]
                else:
                    epoch, baseline, matching, pending, last_emit, sequence = row[2], row[3], bool(row[4]), bool(row[5]), row[6], row[7]
                op = condition["op"]
                field = condition["field"]
                known = field is None or field in reading["metrics"]
                current = reading["metrics"].get(field) if field is not None else None
                if op in {"gt", "lt"}:
                    numeric = _finite_number(current)
                    matches = bool(reading["state"] == "ok" and known and numeric and (current > condition["threshold"] if op == "gt" else current < condition["threshold"]))
                elif op == "unavailable":
                    matches = reading["state"] == "unavailable"
                else:
                    current_json = _canonical(current) if known else None
                    matches = bool(known and (baseline is None or current_json != baseline))
                entered = matches and not matching
                if entered:
                    pending = True
                    sequence += 1
                if not matches:
                    pending = False
                eligible = last_emit is None or now_epoch - last_emit >= condition["cooldown_s"]
                should_emit = matches and pending and eligible
                if should_emit:
                    active_routes = [
                        (route_id, route) for route_id, route in routes.items()
                        if route["enabled"] and route["condition"] == ident
                    ]
                    while any(
                        conn.execute(
                            "SELECT 1 FROM events WHERE dedup_key=?",
                            (_fingerprint([ident, subject, epoch, sequence, route_id]),),
                        ).fetchone()
                        for route_id, _route in active_routes
                    ):
                        sequence += 1
                    for route_id, route in active_routes:
                        delivery = "unsupported" if route["adapter"] == "unsupported" else ("stdout" if route["adapter"] == "stdout" else "queued")
                        dedup = _fingerprint([ident, subject, epoch, sequence, route_id])
                        evidence = _canonical(reading["evidence"])
                        summary = _event_summary(condition, reading)
                        cursor = conn.execute(
                            "INSERT OR IGNORE INTO events(route,consumer,condition_id,monitor,subject,state,summary,evidence,observed_at,delivery,dedup_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (route_id, route["consumer"], ident, monitor_id, subject, reading["state"], summary, evidence, reading["observed_at"], delivery, dedup),
                        )
                        if cursor.rowcount:
                            event_id = cursor.lastrowid
                            emitted.append({"id": event_id, "route": route_id, "consumer": route["consumer"], "condition": ident, "monitor": monitor_id, "subject": subject, "state": reading["state"], "summary": summary, "evidence": reading["evidence"], "observed_at": reading["observed_at"], "delivery": delivery})
                    pending = False
                    last_emit = now_epoch
                    if op == "changed":
                        baseline = current_json
                        matches = False
                elif op == "changed" and known and not matches:
                    baseline = current_json
                conn.execute(
                    "INSERT INTO condition_state(condition_id,subject,fingerprint,generation,epoch,baseline,matching,pending,last_emit,sequence) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(condition_id,subject) DO UPDATE SET fingerprint=excluded.fingerprint,generation=excluded.generation,epoch=excluded.epoch,baseline=excluded.baseline,matching=excluded.matching,pending=excluded.pending,last_emit=excluded.last_emit,sequence=excluded.sequence",
                    (ident, subject, fingerprint, generation, epoch, baseline, int(matches), int(pending), last_emit, sequence),
                )
        conn.commit()
    except (sqlite3.Error, TypeError, ValueError) as exc:
        conn.rollback()
        refuse("state", "valid monitor state and adapter readings", type(exc).__name__, "repair state or the named reader")
    return emitted


def run_once(config: dict[str, object], state: Path, now: datetime, *, clock_epoch: float | None = None) -> tuple[dict[str, int], list[dict[str, object]]]:
    conn = _connect(state, write=True)
    try:
        due_clock = now.timestamp() if clock_epoch is None else clock_epoch
        due = _claim_due(conn, config, due_clock)
        observed: dict[str, list[dict[str, object]]] = {}
        for ident in due:
            monitor = config["monitors"][ident]
            try:
                rows = ADAPTERS[monitor["adapter"]][1](monitor["params"], now)
            except (ArithmeticError, LookupError, OSError, TypeError, ValueError) as exc:
                rows = [_reading(ident, "unavailable", now, evidence=ident, reason=f"reader {type(exc).__name__}")]
            observed[ident] = rows
        events = _evaluate(conn, config, observed, due_clock)
        count = sum(len(rows) for rows in observed.values())
        unavailable = sum(row["state"] == "unavailable" for rows in observed.values() for row in rows)
        return {"observations": count, "events": len(events), "unavailable": unavailable}, events
    finally:
        conn.close()


def _event_from_row(row: tuple[object, ...]) -> dict[str, object]:
    return {"id": row[0], "route": row[1], "consumer": row[2], "condition": row[3], "monitor": row[4], "subject": row[5], "state": row[6], "summary": row[7], "evidence": json.loads(row[8]), "observed_at": row[9], "delivery": row[10]}


def _packed(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def digest(state: Path, consumer: str, limit: int, max_bytes: int, ack: bool) -> bytes:
    conn = _connect(state, write=ack)
    if conn is None:
        return _packed({"events": [], "more": False})
    try:
        try:
            if ack:
                conn.execute("BEGIN IMMEDIATE")
            cursor_row = conn.execute("SELECT event_id FROM cursors WHERE consumer=?", (consumer,)).fetchone()
            cursor = cursor_row[0] if cursor_row else 0
            rows = conn.execute(
                "SELECT id,route,consumer,condition_id,monitor,subject,state,summary,evidence,observed_at,delivery FROM events WHERE consumer=? AND delivery IN ('queued','unsupported') AND id>? ORDER BY id LIMIT ?",
                (consumer, cursor, limit + 1),
            ).fetchall()
            events: list[dict[str, object]] = []
            for row in rows[:limit]:
                candidate = [*events, _event_from_row(row)]
                if len(_packed({"events": candidate, "more": False})) > max_bytes:
                    break
                events = candidate
            more_row = conn.execute(
                "SELECT 1 FROM events WHERE consumer=? AND delivery IN ('queued','unsupported') AND id>? LIMIT 1",
                (consumer, events[-1]["id"] if events else cursor),
            ).fetchone()
            payload = {"events": events, "more": more_row is not None}
            body = _packed(payload)
            if len(body) > max_bytes:
                refuse("arguments", f"--max-bytes large enough for digest metadata ({len(body)})", max_bytes, "raise --max-bytes")
            if ack and events:
                conn.execute(
                    "INSERT INTO cursors(consumer,event_id) VALUES(?,?) ON CONFLICT(consumer) DO UPDATE SET event_id=MAX(cursors.event_id,excluded.event_id)",
                    (consumer, events[-1]["id"]),
                )
            if ack:
                conn.commit()
            return body
        except (sqlite3.Error, TypeError, ValueError, json.JSONDecodeError) as exc:
            if ack:
                conn.rollback()
            refuse("state", "a valid monitor database", type(exc).__name__, "repair or replace the state database")
    finally:
        conn.close()


def _identity() -> None:
    value = os.environ.get("WF_AGENT", "")
    if IDENTITY_RE.fullmatch(value) is None:
        refuse("identity", "WF_AGENT in Name <address> form", value or "unset", "export the acting identity")


def _integer(value: str, option: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except ValueError:
        refuse("arguments", f"{option} to be an integer", value, "supply a decimal integer")
    if not minimum <= number <= maximum:
        refuse("arguments", f"{option} from {minimum} through {maximum}", number, "use the declared bound")
    return number


def _clock(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        refuse("arguments", "--now to be an ISO timestamp with timezone", value, "supply an injected UTC clock")
    if parsed.tzinfo is None:
        refuse("arguments", "--now to include a timezone", value, "append Z or an offset")
    return parsed.astimezone(timezone.utc)


def _global(argv: list[str]) -> tuple[Path, Path | None, str, list[str]]:
    config = DEFAULT_CONFIG
    state = None
    index = 0
    while index < len(argv) and argv[index] in {"--config", "--state"}:
        option = argv[index]
        if index + 1 >= len(argv):
            refuse("arguments", f"a value after {option}", "missing", "supply the path")
        if option == "--config":
            config = Path(argv[index + 1]).resolve()
        else:
            state = Path(argv[index + 1]).resolve()
        index += 2
    if index >= len(argv):
        refuse("arguments", "check, run, or digest", "no verb", "choose one documented verb")
    return config, state, argv[index], argv[index + 1 :]


def _state_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    tools = HERE.parent
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    try:
        import laneconf

        lane = laneconf.get("LANE_NAME")
    except (ImportError, AttributeError) as exc:
        refuse("conf-key", "LANE_NAME through laneconf", type(exc).__name__, "keep laneconf.py beside monitor.py")
    except laneconf.ConfigError as exc:
        refuse("conf-key", "LANE_NAME in the lane conf", exc.kind, "define the lane setting")
    base = Path(os.environ["XDG_STATE_HOME"]) if os.environ.get("XDG_STATE_HOME") else Path.home() / ".local" / "state"
    return base / lane / "monitor"


def _parse_run(args: list[str]) -> tuple[bool, str | None]:
    once = args.count("--once")
    loop = args.count("--loop")
    if once + loop != 1:
        refuse("arguments", "exactly one of --once or --loop", repr(args), "choose one run mode")
    rest = [item for item in args if item not in {"--once", "--loop"}]
    now = None
    if rest:
        if len(rest) == 2 and rest[0] == "--now":
            now = rest[1]
        else:
            refuse("arguments", "run --once|--loop [--now ISO]", repr(args), "use documented run options")
    if loop and now is not None:
        refuse("arguments", "--now only with --once", "--loop --now", "remove the injected clock")
    return bool(loop), now


def _parse_digest(args: list[str]) -> tuple[str, int, int, bool]:
    consumer = None
    limit, max_bytes, ack = 10, 4096, False
    index = 0
    while index < len(args):
        option = args[index]
        if option == "--ack":
            if ack:
                refuse("arguments", "--ack at most once", "duplicate --ack", "remove the duplicate")
            ack = True
            index += 1
            continue
        if option not in {"--consumer", "--limit", "--max-bytes"} or index + 1 >= len(args):
            refuse("arguments", "digest --consumer ID [--limit N] [--max-bytes N] [--ack]", repr(args), "use documented digest options")
        value = args[index + 1]
        if option == "--consumer":
            if consumer is not None:
                refuse("arguments", "one --consumer", "duplicate --consumer", "remove the duplicate")
            consumer = value
        elif option == "--limit":
            limit = _integer(value, "--limit", 1, 1000)
        else:
            max_bytes = _integer(value, "--max-bytes", 32, 8_388_608)
        index += 2
    if consumer is None:
        refuse("consumer", "--consumer ID", "missing", "name the isolated consumer")
    return _consumer(consumer, "--consumer"), limit, max_bytes, ack


def main(argv: list[str] | None = None) -> int:
    try:
        config_path, explicit_state, verb, args = _global(list(sys.argv[1:] if argv is None else argv))
        if verb not in {"check", "run", "digest"}:
            refuse("arguments", "check, run, or digest", verb, "choose one documented verb")
        config = load_config(config_path)
        if verb == "check":
            if args:
                refuse("arguments", "check with no verb options", repr(args), "remove the extra arguments")
            print(json.dumps({"valid": True, "monitors": len(config["monitors"]), "schedules": len(config["schedules"]), "conditions": len(config["conditions"]), "routes": len(config["routes"])}, separators=(",", ":")))
            return 0
        if verb == "digest":
            consumer, limit, max_bytes, ack = _parse_digest(args)
            if ack:
                _identity()
            sys.stdout.buffer.write(digest(_state_path(explicit_state), consumer, limit, max_bytes, ack))
            return 0
        loop, injected = _parse_run(args)
        _identity()
        state = _state_path(explicit_state)
        if not loop:
            counts, events = run_once(config, state, _clock(injected) if injected else datetime.now(timezone.utc))
            for event in events:
                if event["delivery"] == "stdout":
                    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
            print(json.dumps(counts, separators=(",", ":")))
            return 0
        # Persist epoch-shaped deadlines, but advance the live clock only by
        # monotonic elapsed time. A restart translates them through wall time.
        wall_anchor = datetime.now(timezone.utc).timestamp()
        monotonic_anchor = time.monotonic()
        while True:
            try:
                cycle = load_config(config_path)
            except Refusal as exc:
                print(exc.line(), file=sys.stderr)
                return 3
            now = datetime.now(timezone.utc)
            live_epoch = wall_anchor + time.monotonic() - monotonic_anchor
            counts, events = run_once(cycle, state, now, clock_epoch=live_epoch)
            for event in events:
                if event["delivery"] == "stdout":
                    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)
            time.sleep(1 if counts["observations"] == 0 else 0.1)
    except KeyboardInterrupt:
        return 3
    except Refusal as exc:
        print(exc.line(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
