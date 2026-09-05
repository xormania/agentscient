"""Bounded, read-only queries for the conductor lane MCP projection."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn
from urllib.parse import quote

SCHEMA = "agentscient.lane/v1"
CONFIG_BYTES = 65_536
SOURCE_BYTES = 1_048_576
QUERY_BYTES = 16_384
ALERT_BYTES = 4_096
FINDINGS_BYTES = 8_192
MAX_INTEGER = 9_223_372_036_854_775_807
MAX_JSON_DEPTH = 1_024
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
REVISION_RE = re.compile(r"[0-9a-f]{16}")
CURSOR_RE = re.compile(r"([0-9a-f]{16}):([1-9][0-9]{0,8})")
JOB_NAME_RE = re.compile(r"[a-z][a-z0-9-]{0,63}")
SLOT_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
ALLOWED_SLOTS = {"ref", "base", "diff", "into", "out", "inputs", "scope"}
CONFIG_KEYS = {
    "version",
    "dispatch_store",
    "job_ids",
    "monitor_state",
    "consumer",
    "usage_rollout",
}
CONFIG_KEYS_V2 = CONFIG_KEYS | {"job_registry"}
COUNT_KEYS = ("p1", "p2", "p3", "opinions")
SPEND_KEYS = ("input", "cached", "output", "total", "out", "runs")
EVENT_COLUMNS = (
    "id",
    "route",
    "consumer",
    "condition",
    "monitor",
    "subject",
    "state",
    "summary",
    "evidence",
    "observed_at",
    "delivery",
)


class Refusal(ValueError):
    """A domain refusal in the lane wire shape."""

    def __init__(self, kind: str, expected: object, found: object, needed: object):
        self.kind = kind
        self.expected = _one_line(expected)
        self.found = _one_line(found)
        self.needed = _one_line(needed)
        super().__init__(self.line())

    def line(self) -> str:
        return (
            f"{self.kind}: expected {self.expected}; found {self.found}; "
            f"needed {self.needed}"
        )


def _one_line(value: object) -> str:
    return " ".join(str(value).split()) or "empty"


def refuse(kind: str, expected: object, found: object, needed: object) -> NoReturn:
    raise Refusal(kind, expected, found, needed)


def _pairs(kind: str):
    def collect(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                refuse(
                    kind,
                    "unique JSON object keys",
                    f"duplicate key {key}",
                    "remove the duplicate key",
                )
            result[key] = value
        return result

    return collect


def _json_depth_exceeds(raw: bytes, limit: int = MAX_JSON_DEPTH) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
            continue
        if byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > limit:
                return True
        elif byte in (93, 125):
            depth -= 1
    return False


def decode_object(raw: str, where: str = "arguments") -> dict[str, object]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_pairs(where),
            parse_constant=lambda item: refuse(
                where, "finite JSON values", item, "replace the nonfinite value"
            ),
        )
    except Refusal:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError) as exc:
        refuse(where, "a valid JSON object", type(exc).__name__, "supply valid JSON")
    if not isinstance(value, dict):
        refuse(where, "a JSON object", type(value).__name__, "supply an object")
    return value


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def canonical(value: object) -> str:
    return canonical_bytes(value).decode("ascii")


def _bounded_regular(path: Path, limit: int, *, follow: bool) -> tuple[str, bytes | None]:
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    if not follow:
        flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return "missing", None
    except OSError:
        return "unavailable", None
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > limit:
            return "unavailable", None
        chunks = bytearray()
        while len(chunks) <= limit:
            chunk = os.read(descriptor, min(65_536, limit + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
        if len(chunks) > limit:
            return "unavailable", None
        return "ok", bytes(chunks)
    except OSError:
        return "unavailable", None
    finally:
        os.close(descriptor)


def _source_path(value: object, name: str, base: Path) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or not value.isprintable()
    ):
        refuse(
            "config",
            f"{name} to be null or a printable path of at most 1024 UTF-8 bytes",
            repr(value),
            "supply an explicit bounded source path or null",
        )
    try:
        if len(value.encode("utf-8")) > 1_024:
            raise UnicodeError
        return os.path.abspath(value if os.path.isabs(value) else base / value)
    except (OSError, UnicodeError, ValueError):
        refuse("config", f"{name} to be a valid path", repr(value), "repair the path")


def _consumer(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or not value.isascii()
        or not value.isprintable()
        or "/" in value
        or "\\" in value
    ):
        refuse(
            "config",
            "consumer to be 1..128 printable ASCII characters without path separators",
            repr(value),
            "supply an isolated consumer id",
        )
    return value


def load_config(path: Path) -> dict[str, object]:
    absolute = Path(os.path.abspath(path))
    status, raw = _bounded_regular(absolute, CONFIG_BYTES, follow=True)
    if status != "ok" or raw is None:
        refuse(
            "config",
            f"a regular UTF-8 config no larger than {CONFIG_BYTES} bytes",
            status,
            "restore the config or pass --config FILE",
        )
    try:
        text = raw.decode("utf-8")
        root = json.loads(
            text,
            object_pairs_hook=_pairs("config"),
            parse_constant=lambda item: refuse(
                "config", "finite JSON values", item, "replace the nonfinite value"
            ),
        )
    except Refusal:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError) as exc:
        refuse("config", "valid UTF-8 JSON", type(exc).__name__, "repair the config")
    if not isinstance(root, dict):
        refuse(
            "config",
            f"exact keys {sorted(CONFIG_KEYS)}",
            type(root).__name__,
            "add missing and remove unknown keys",
        )
    version = root.get("version")
    if type(version) is not int or version not in {1, 2}:
        refuse("config", "version 1 or 2", repr(version), "set a supported version")
    expected_keys = CONFIG_KEYS if version == 1 else CONFIG_KEYS_V2
    if set(root) != expected_keys:
        refuse(
            "config",
            f"exact keys {sorted(expected_keys)}",
            sorted(root),
            "add missing and remove unknown keys",
        )
    ids = root["job_ids"]
    if (
        not isinstance(ids, list)
        or len(ids) > 20
        or any(not isinstance(item, str) or ID_RE.fullmatch(item) is None for item in ids)
    ):
        refuse(
            "config",
            f"job_ids to be at most 20 ids matching {ID_RE.pattern}",
            repr(ids),
            "supply the declared unique identifier list",
        )
    if len(set(ids)) != len(ids):
        refuse("config", "unique job_ids", repr(ids), "remove duplicate ids")
    base = absolute.parent
    config = {
        "version": version,
        "dispatch_store": _source_path(root["dispatch_store"], "dispatch_store", base),
        "job_ids": list(ids),
        "monitor_state": _source_path(root["monitor_state"], "monitor_state", base),
        "consumer": _consumer(root["consumer"]),
        "usage_rollout": _source_path(root["usage_rollout"], "usage_rollout", base),
    }
    if version == 2:
        config["job_registry"] = _source_path(
            root["job_registry"], "job_registry", base
        )
    return config


def check_result(config: dict[str, object]) -> dict[str, object]:
    return {"valid": True, "tools": 7 if config["version"] == 2 else 4}


def _base(name: str, state: str, reason: str | None = None) -> dict[str, object]:
    return {"schema": SCHEMA, "query": name, "state": state, "reason": reason}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return value if len(value.encode("utf-8")) <= 256 else None
    except UnicodeError:
        return None


def _aggregate(value: object, keys: tuple[str, ...]) -> dict[str, int | float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int | float] = {}
    for key in keys:
        item = value.get(key)
        valid_int = type(item) is int and 0 <= item <= MAX_INTEGER
        valid_float = (
            type(item) is float and math.isfinite(item) and 0 <= item <= MAX_INTEGER
        )
        if valid_int or valid_float:
            result[key] = item
    return result


def _read_record(
    config: dict[str, object], ident: str
) -> tuple[str, str | None, str | None, bytes | None, dict[str, object] | None]:
    evidence = (
        str(Path(config["dispatch_store"]) / ident / "record.json")
        if config["dispatch_store"] is not None
        else None
    )
    if config["dispatch_store"] is None:
        return "unknown", "dispatch store is not configured", evidence, None, None
    store = Path(config["dispatch_store"])
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        store_fd = os.open(store, flags)
    except FileNotFoundError:
        return "unknown", "dispatch store is missing", evidence, None, None
    except OSError:
        return "unavailable", "dispatch store is unavailable", evidence, None, None
    try:
        try:
            job_fd = os.open(ident, flags, dir_fd=store_fd)
        except FileNotFoundError:
            return "unknown", "record is missing", evidence, None, None
        except OSError:
            return "unavailable", "job directory is unavailable", evidence, None, None
        try:
            file_flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
            file_flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open("record.json", file_flags, dir_fd=job_fd)
            except FileNotFoundError:
                return "unknown", "record is missing", evidence, None, None
            except OSError:
                return "unavailable", "record is unavailable", evidence, None, None
            try:
                details = os.fstat(descriptor)
                if not stat.S_ISREG(details.st_mode) or details.st_size > SOURCE_BYTES:
                    raise ValueError
                raw = bytearray()
                while len(raw) <= SOURCE_BYTES:
                    chunk = os.read(
                        descriptor, min(65_536, SOURCE_BYTES + 1 - len(raw))
                    )
                    if not chunk:
                        break
                    raw.extend(chunk)
                if len(raw) > SOURCE_BYTES:
                    raise ValueError
                if _json_depth_exceeds(raw):
                    raise ValueError
                source = bytes(raw)
                record = json.loads(source)
                if not isinstance(record, dict):
                    raise ValueError
            except (
                json.JSONDecodeError,
                OSError,
                RecursionError,
                UnicodeError,
                ValueError,
            ):
                return (
                    "unavailable",
                    "record is unreadable or malformed",
                    evidence,
                    None,
                    None,
                )
            finally:
                os.close(descriptor)
        finally:
            os.close(job_fd)
    finally:
        os.close(store_fd)
    return "ok", None, evidence, source, record


def _record_summary(
    record: dict[str, object], ident: str, evidence: str | None
) -> dict[str, object]:
    nested = record.get("result") if isinstance(record.get("result"), dict) else {}
    envelope = nested.get("envelope") if isinstance(nested.get("envelope"), dict) else {}
    session = record.get("session") if isinstance(record.get("session"), dict) else {}
    changed = nested.get("changed_paths")
    attempts = record.get("attempts")
    model = record.get("model")
    if isinstance(model, dict):
        model = _text(model.get("ran")) or _text(model.get("requested"))
    else:
        model = _text(model)
    return {
        "id": ident,
        "recorded_status": _text(record.get("status")),
        "model": model,
        "head": _text(nested.get("head")),
        "verdict": _text(envelope.get("verdict")),
        "counts": _aggregate(envelope.get("counts"), COUNT_KEYS),
        "changed_count": len(changed) if isinstance(changed, list) else None,
        "attempt_count": len(attempts) if isinstance(attempts, list) else None,
        "spend": _aggregate(session.get("spend"), SPEND_KEYS),
        "evidence": evidence,
    }


def _record(config: dict[str, object], ident: str) -> dict[str, object]:
    name = "lane_record"
    state, reason, evidence, _raw, record = _read_record(config, ident)
    result = _base(name, state, reason)
    if record is None:
        result["record"] = None
        return result
    summary = _record_summary(record, ident, evidence)
    result = _base(name, "ok")
    result["record"] = summary
    return result


def _monitor_db(config: dict[str, object]) -> tuple[str, Path | None]:
    source = config["monitor_state"]
    if source is None:
        return "disabled", None
    state_path = Path(source)
    try:
        details = state_path.lstat()
    except FileNotFoundError:
        return "missing", None
    except OSError:
        return "unavailable", None
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        return "unavailable", None
    database = state_path / "monitor.db"
    try:
        details = database.lstat()
    except FileNotFoundError:
        return "missing", None
    except OSError:
        return "unavailable", None
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        return "unavailable", None
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(database, flags)
    except OSError:
        return "unavailable", None
    os.close(descriptor)
    return "ok", database


def _event(row: tuple[object, ...]) -> dict[str, object]:
    if len(row) != len(EVENT_COLUMNS):
        raise ValueError
    event = dict(zip(EVENT_COLUMNS, row, strict=True))
    if type(event["id"]) is not int or event["id"] <= 0:
        raise ValueError
    for key in ("route", "consumer", "condition", "monitor", "state"):
        if not isinstance(event[key], str) or len(event[key].encode("utf-8")) > 256:
            raise ValueError
    if (
        not isinstance(event["subject"], str)
        or len(event["subject"].encode("utf-8")) > 1_024
    ):
        raise ValueError
    if (
        not isinstance(event["summary"], str)
        or len(event["summary"].encode("utf-8")) > 240
        or not isinstance(event["observed_at"], str)
        or len(event["observed_at"].encode("utf-8")) > 256
        or event["delivery"] not in {"queued", "unsupported"}
    ):
        raise ValueError
    if not isinstance(event["evidence"], str):
        raise ValueError
    event["evidence"] = json.loads(event["evidence"])
    return event


def _alerts(config: dict[str, object], after: int, limit: int) -> dict[str, object]:
    name = "lane_alerts"
    status, database = _monitor_db(config)
    if status in {"disabled", "missing"}:
        result = _base(name, "unknown", "monitor database is not armed")
        result.update({"events": [], "more": False, "next_after": after})
        return result
    if status != "ok" or database is None:
        result = _base(name, "unavailable", "monitor database is unavailable")
        result.update({"events": [], "more": False, "next_after": after})
        return result
    uri = f"file:{quote(str(database), safe='/')}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=0)
        try:
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                "SELECT id,route,consumer,condition_id,monitor,subject,state,"
                "summary,evidence,observed_at,delivery FROM events "
                "WHERE consumer=? AND delivery IN ('queued','unsupported') "
                "AND id>? ORDER BY id LIMIT ?",
                (config["consumer"], after, limit + 1),
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        result = _base(name, "unavailable", "monitor database is unreadable or corrupt")
        result.update({"events": [], "more": False, "next_after": after})
        return result
    events: list[dict[str, object]] = []
    for row in rows[:limit]:
        try:
            event = _event(row)
        except (json.JSONDecodeError, RecursionError, TypeError, UnicodeError, ValueError):
            if not events:
                result = _base(
                    name, "unavailable", "monitor database is unreadable or corrupt"
                )
                result.update({"events": [], "more": True, "next_after": after})
                return result
            break
        candidate = [*events, event]
        probe = _base(name, "ok")
        probe.update(
            {
                "events": candidate,
                "more": len(rows) > len(candidate),
                "next_after": candidate[-1]["id"],
            }
        )
        if len(canonical_bytes(probe)) > ALERT_BYTES:
            if not events:
                result = _base(name, "unavailable", "next alert exceeds 4096 bytes")
                result.update({"events": [], "more": True, "next_after": after})
                return result
            break
        events = candidate
    result = _base(name, "ok")
    result.update(
        {
            "events": events,
            "more": len(rows) > len(events),
            "next_after": events[-1]["id"] if events else after,
        }
    )
    return result


def _usage_int(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= MAX_INTEGER else None


def _timestamp(value: object) -> tuple[str | None, str | None]:
    reason = "event timestamp invalid or absent"
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isprintable()
        or len(value.encode("ascii")) > 128
    ):
        return None, reason
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None, reason
        normalized = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, ValueError):
        return None, reason
    return (normalized, None) if len(normalized) <= 128 else (None, reason)


def _usage(config: dict[str, object]) -> dict[str, object]:
    name = "lane_usage"
    source = config["usage_rollout"]
    if source is None:
        result = _base(name, "unknown", "usage rollout is not configured")
        result.update({"metrics": {}, "evidence": {"path": None, "event_at": None}})
        return result
    path = Path(source)
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        result = _base(name, "unknown", "usage rollout is missing")
        result.update({"metrics": {}, "evidence": {"path": str(path), "event_at": None}})
        return result
    except OSError:
        result = _base(name, "unavailable", "usage rollout is unavailable")
        result.update({"metrics": {}, "evidence": {"path": str(path), "event_at": None}})
        return result
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise OSError
        offset = max(0, details.st_size - SOURCE_BYTES)
        os.lseek(descriptor, offset, os.SEEK_SET)
        data = bytearray()
        while len(data) <= SOURCE_BYTES:
            chunk = os.read(descriptor, min(65_536, SOURCE_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > SOURCE_BYTES:
            raise OSError
    except OSError:
        result = _base(name, "unavailable", "usage rollout is unavailable")
        result.update({"metrics": {}, "evidence": {"path": str(path), "event_at": None}})
        return result
    finally:
        os.close(descriptor)
    raw = bytes(data)
    if offset:
        split = raw.find(b"\n")
        raw = b"" if split < 0 else raw[split + 1 :]
    if raw and not raw.endswith(b"\n"):
        split = raw.rfind(b"\n")
        raw = raw[: split + 1] if split >= 0 else b""
    last: dict[str, object] | None = None
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, RecursionError, UnicodeError):
            continue
        if not isinstance(entry, dict) or entry.get("type") != "event_msg":
            continue
        payload = entry.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "token_count":
            last = entry
    if last is None:
        result = _base(name, "unknown", "no complete token_count row in bounded tail")
        result.update({"metrics": {}, "evidence": {"path": str(path), "event_at": None}})
        return result
    payload = last["payload"]
    info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
    totals = info.get("total_token_usage") if isinstance(info.get("total_token_usage"), dict) else {}
    recent = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
    names = {
        "input": "input_tokens",
        "cached": "cached_input_tokens",
        "output": "output_tokens",
        "total": "total_tokens",
    }
    metrics = {
        name_: value
        for name_, key in names.items()
        if (value := _usage_int(totals.get(key))) is not None
    }
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
    event_at, timestamp_reason = _timestamp(last.get("timestamp"))
    state = "ok" if any(key in metrics for key in names) else "unknown"
    reason = timestamp_reason if state == "ok" else "retained usage fields invalid or absent"
    result = _base(name, state, reason)
    result.update({"metrics": metrics, "evidence": {"path": str(path), "event_at": event_at}})
    return result


def _revision(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


def _bounded_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return value if len(value.encode("utf-8")) <= limit else None
    except UnicodeError:
        return None


def _finding_entry(value: object, number: int) -> dict[str, object]:
    if not isinstance(value, dict):
        return {
            "n": number,
            "severity": None,
            "where": None,
            "claim": None,
            "reproduce": None,
            "omitted": ["entry"],
        }
    entry: dict[str, object] = {"n": number}
    omitted: list[str] = []
    severity = value.get("severity")
    if isinstance(severity, str) and severity in ("p1", "p2", "p3"):
        entry["severity"] = severity
    else:
        entry["severity"] = None
        if severity is not None:
            omitted.append("severity")
    for field, limit in (("where", 256), ("claim", 1024), ("reproduce", 1024)):
        source = value.get(field)
        projected = _bounded_text(source, limit)
        entry[field] = projected
        if source is not None and projected is None:
            omitted.append(field)
    entry["omitted"] = omitted
    return entry


def _findings_empty(name: str, state: str, reason: str) -> dict[str, object]:
    result = _base(name, state, reason)
    result.update(
        {
            "record": None,
            "note": None,
            "note_bytes": None,
            "findings": [],
            "findings_total": None,
            "page": None,
        }
    )
    return result


def _findings_note(envelope: dict[str, object]) -> tuple[str | None, int | None, str | None]:
    if "note" not in envelope or envelope["note"] is None:
        return None, None, None
    note = envelope["note"]
    if not isinstance(note, str):
        return None, None, "note is not a string"
    try:
        length = len(note.encode("utf-8"))
    except UnicodeError:
        return None, None, "note is not valid Unicode"
    return (note if length <= 2048 else None), length, None


def _findings_page_payload(
    record: dict[str, object],
    note: str | None,
    note_bytes: int | None,
    findings: list[dict[str, object]],
    total: int,
    start: int,
    revision: str,
    reason: str | None,
) -> dict[str, object]:
    count = len(findings)
    last = start + count - 1
    more = last < total
    result = _base("lane_findings", "ok", reason)
    result.update(
        {
            "record": record,
            "note": note,
            "note_bytes": note_bytes,
            "findings": findings,
            "findings_total": total,
            "page": {
                "from": start if count else None,
                "to": last if count else None,
                "count": count,
                "more": more,
                "next_cursor": f"{revision}:{last + 1}" if more else None,
            },
        }
    )
    return result


def _findings(config: dict[str, object], ident: str, cursor: str | None) -> dict[str, object]:
    state, reason, evidence, raw, source = _read_record(config, ident)
    if source is None or raw is None:
        return _findings_empty("lane_findings", state, reason or "record is unavailable")
    revision = _revision(raw)
    nested = source.get("result") if isinstance(source.get("result"), dict) else {}
    envelope = nested.get("envelope") if isinstance(nested.get("envelope"), dict) else {}
    summary = _record_summary(source, ident, evidence)
    record = {
        "id": ident,
        "job": _text(source.get("job")),
        "stage": _text(source.get("stage")),
        "recorded_status": summary["recorded_status"],
        "verdict": summary["verdict"],
        "counts": summary["counts"],
        "revision": revision,
        "evidence": evidence,
    }
    note, note_bytes, note_reason = _findings_note(envelope)
    source_findings = envelope.get("findings")
    if not isinstance(source_findings, list):
        result = _base("lane_findings", "unavailable", "envelope findings is not a list")
        result.update(
            {
                "record": record,
                "note": note,
                "note_bytes": note_bytes,
                "findings": [],
                "findings_total": None,
                "page": None,
            }
        )
        return result
    total = len(source_findings)
    start = 1
    if cursor is not None:
        match = CURSOR_RE.fullmatch(cursor)
        if match is None:
            raise AssertionError
        held_revision, raw_start = match.groups()
        if held_revision != revision:
            refuse(
                "cursor",
                f"cursor for revision {revision}",
                held_revision,
                "restart from the first page",
            )
        start = int(raw_start)
        if start > total:
            refuse(
                "cursor",
                "an index within findings_total",
                start,
                "supply an index within findings_total",
            )
    page_note = note if cursor is None else None
    page_reason = note_reason
    frame = _findings_page_payload(
        record, None, note_bytes, [], total, start, revision, page_reason
    )
    if len(canonical_bytes(frame)) > FINDINGS_BYTES:
        frame.update(
            {
                "state": "unavailable",
                "reason": "page frame exceeds 8192 bytes",
                "page": None,
            }
        )
        return frame
    if page_note is not None:
        with_note = _findings_page_payload(
            record, page_note, note_bytes, [], total, start, revision, page_reason
        )
        if len(canonical_bytes(with_note)) > FINDINGS_BYTES:
            page_note = None
            page_reason = "note exceeds page"
    findings: list[dict[str, object]] = []
    for number in range(start, total + 1):
        entry = _finding_entry(source_findings[number - 1], number)
        candidate = _findings_page_payload(
            record,
            page_note,
            note_bytes,
            [*findings, entry],
            total,
            start,
            revision,
            page_reason,
        )
        if len(canonical_bytes(candidate)) <= FINDINGS_BYTES:
            findings.append(entry)
            continue
        if findings:
            break
        for field in ("reproduce", "claim", "where"):
            if entry[field] is not None:
                entry[field] = None
                if field not in entry["omitted"]:
                    entry["omitted"].append(field)
            candidate = _findings_page_payload(
                record,
                page_note,
                note_bytes,
                [entry],
                total,
                start,
                revision,
                page_reason,
            )
            if len(canonical_bytes(candidate)) <= FINDINGS_BYTES:
                findings.append(entry)
                break
        if findings:
            break
        if page_note is not None:
            page_note = None
            page_reason = "note exceeds page"
            candidate = _findings_page_payload(
                record,
                page_note,
                note_bytes,
                [entry],
                total,
                start,
                revision,
                page_reason,
            )
            if len(canonical_bytes(candidate)) <= FINDINGS_BYTES:
                findings.append(entry)
                break
        failed = _findings_page_payload(
            record, None, note_bytes, [], total, start, revision, None
        )
        failed.update(
            {
                "state": "unavailable",
                "reason": "page frame exceeds 8192 bytes",
                "page": None,
            }
        )
        return failed
    return _findings_page_payload(
        record,
        page_note,
        note_bytes,
        findings,
        total,
        start,
        revision,
        page_reason,
    )


def _dispatch_store_state(config: dict[str, object]) -> tuple[str, str | None]:
    source = config["dispatch_store"]
    if source is None:
        return "unknown", "dispatch store is not configured"
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(Path(source), flags)
    except FileNotFoundError:
        return "unknown", "dispatch store is missing"
    except OSError:
        return "unavailable", "dispatch store is unavailable"
    os.close(descriptor)
    return "ok", None


def _changes(
    config: dict[str, object], checkpoint: dict[str, str]
) -> dict[str, object]:
    ids = config["job_ids"]
    changed: list[dict[str, object]] = []
    unchanged: list[str] = []
    unknown: list[str] = []
    unavailable: list[str] = []
    current: dict[str, str] = {}
    state, reason = _dispatch_store_state(config)
    if state != "ok":
        if state == "unknown":
            unknown.extend(ids)
        else:
            unavailable.extend(ids)
    else:
        for ident in ids:
            rec_state, _rec_reason, evidence, raw, source = _read_record(config, ident)
            if rec_state == "unknown":
                unknown.append(ident)
                continue
            if rec_state != "ok" or raw is None or source is None:
                unavailable.append(ident)
                continue
            revision = _revision(raw)
            current[ident] = revision
            if checkpoint.get(ident) == revision:
                unchanged.append(ident)
                continue
            summary = _record_summary(source, ident, evidence)
            changed.append(
                {
                    "id": ident,
                    "revision": revision,
                    "recorded_status": summary["recorded_status"],
                    "verdict": summary["verdict"],
                    "evidence": evidence,
                }
            )
    result = _base("lane_changes", state, reason)
    result.update(
        {
            "configured_ids": ids,
            "changed": changed,
            "unchanged": unchanged,
            "unknown": unknown,
            "unavailable": unavailable,
            "checkpoint": current,
        }
    )
    return result


def _job_parts(name: object, value: object) -> tuple[str | None, dict[str, object] | None, list[str], bool]:
    try:
        valid_name = isinstance(name, str) and JOB_NAME_RE.fullmatch(name) is not None
        if valid_name:
            name.encode("utf-8")
    except UnicodeError:
        valid_name = False
    if not valid_name or not isinstance(value, dict):
        return None, None, [], False
    prompt = value.get("prompt")
    if isinstance(prompt, str):
        try:
            prompt.encode("utf-8")
            prompt_valid = bool(prompt)
            slots = sorted(set(SLOT_RE.findall(prompt)))
        except UnicodeError:
            prompt_valid = False
            slots = []
    else:
        prompt_valid = False
        slots = []
    dispatchable = (
        value.get("adapter") == "harness"
        and value.get("role") in ("read", "write")
        and value.get("snapshot") == "whole"
        and not value.get("withheld")
        and prompt_valid
        and set(slots).issubset(ALLOWED_SLOTS)
    )
    return name, value, slots, dispatchable


def _job_row(name: object, value: object) -> dict[str, object]:
    projected_name, source, slots, dispatchable = _job_parts(name, value)
    if source is None:
        return {
            "name": None,
            "adapter": None,
            "role": None,
            "dispatchable": False,
            "slots": [],
        }
    return {
        "name": projected_name,
        "adapter": _text(source.get("adapter")),
        "role": _text(source.get("role")),
        "dispatchable": dispatchable,
        "slots": slots,
    }


def _job_card(name: str, value: object) -> dict[str, object]:
    projected_name, source, slots, dispatchable = _job_parts(name, value)
    if source is None:
        source = {}
    prompt = source.get("prompt")
    try:
        prompt_bytes = len(prompt.encode("utf-8")) if isinstance(prompt, str) else None
    except UnicodeError:
        prompt_bytes = None
    constraints = source.get("constraints")
    if isinstance(constraints, list):
        projected_constraints = [
            _bounded_text(item, 256) for item in constraints[:16]
        ]
    else:
        projected_constraints = []
    caps = source.get("caps") if isinstance(source.get("caps"), dict) else {}
    timeout = caps.get("timeout")
    if type(timeout) is int:
        valid_timeout = timeout >= 0
    elif type(timeout) is float:
        valid_timeout = math.isfinite(timeout) and timeout >= 0
    else:
        valid_timeout = False
    return {
        "name": projected_name,
        "adapter": _text(source.get("adapter")),
        "role": _text(source.get("role")),
        "snapshot": _text(source.get("snapshot")),
        "dispatchable": dispatchable,
        "slots": slots,
        "deliverable": _bounded_text(source.get("deliverable"), 512),
        "constraints": projected_constraints,
        "timeout": timeout if valid_timeout else None,
        "prompt_bytes": prompt_bytes,
    }


def _jobs(config: dict[str, object], name: str | None) -> dict[str, object]:
    source = config.get("job_registry")
    path = Path(source) if source is not None else None
    evidence = {"path": str(path) if path is not None else None, "revision": None}
    if path is None:
        result = _base("lane_jobs", "unknown", "job registry is not configured")
        result.update({"evidence": evidence, "jobs": [], "job": None})
        return result
    status, raw = _bounded_regular(path, SOURCE_BYTES, follow=False)
    if status == "missing":
        result = _base("lane_jobs", "unknown", "job registry is missing")
        result.update({"evidence": evidence, "jobs": [], "job": None})
        return result
    if status != "ok" or raw is None:
        result = _base("lane_jobs", "unavailable", "job registry is unavailable")
        result.update({"evidence": evidence, "jobs": [], "job": None})
        return result
    try:
        registry = json.loads(raw.decode("utf-8"))
        if not isinstance(registry, dict):
            raise ValueError
    except (json.JSONDecodeError, RecursionError, UnicodeError, ValueError):
        result = _base("lane_jobs", "unavailable", "job registry is unreadable or malformed")
        result.update({"evidence": evidence, "jobs": [], "job": None})
        return result
    evidence["revision"] = _revision(raw)
    if len(registry) > 64:
        result = _base("lane_jobs", "unavailable", "registry lists more than 64 jobs")
        result.update({"evidence": evidence, "jobs": [], "job": None})
        return result
    result = _base("lane_jobs", "ok")
    if name is None:
        result.update(
            {
                "evidence": evidence,
                "jobs": [_job_row(key, value) for key, value in registry.items()],
                "job": None,
            }
        )
    else:
        result.update(
            {
                "evidence": evidence,
                "jobs": [],
                "job": _job_card(name, registry[name]) if name in registry else None,
            }
        )
        if name not in registry:
            result["reason"] = "job is not declared in the registry"
    return result


def _arguments(value: object, keys: set[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not set(value).issubset(keys):
        found = sorted(value) if isinstance(value, dict) else type(value).__name__
        refuse(
            "arguments",
            f"{name} fields drawn from {sorted(keys)}",
            found,
            "remove unknown fields and use the declared types",
        )
    return value


def query(config: dict[str, object], name: str, arguments: object) -> dict[str, object]:
    if name == "lane_record":
        args = _arguments(arguments, {"id"}, name)
        if set(args) != {"id"} or not isinstance(args.get("id"), str):
            refuse("arguments", "lane_record object with string id", repr(args), "supply {\"id\":ID}")
        ident = args["id"]
        if ID_RE.fullmatch(ident) is None or ident not in config["job_ids"]:
            refuse("arguments", "id in configured job_ids", repr(ident), "select a configured id")
        result = _record(config, ident)
    elif name == "lane_alerts":
        args = _arguments(arguments, {"after", "limit"}, name)
        after = args.get("after", 0)
        limit = args.get("limit", 5)
        if type(after) is not int or after < 0:
            refuse("arguments", "after integer >= 0", repr(after), "supply a nonnegative cursor")
        if type(limit) is not int or not 1 <= limit <= 10:
            refuse("arguments", "limit integer from 1 through 10", repr(limit), "supply a bounded page size")
        result = _alerts(config, after, limit)
    elif name == "lane_usage":
        args = _arguments(arguments, set(), name)
        if args:
            raise AssertionError
        result = _usage(config)
    elif name == "lane_brief":
        args = _arguments(arguments, set(), name)
        if args:
            raise AssertionError
        records = [_record(config, ident) for ident in config["job_ids"]]
        result = _base(name, "ok")
        result.update(
            {
                "configured_ids": config["job_ids"],
                "records": records,
                "alerts": _alerts(config, 0, 5),
                "omissions": [
                    "no live PR/CI/review readiness",
                    "no watchdog stdout history",
                    "no automatic discovery of other jobs",
                    "no idle-agent wakeup",
                ],
            }
        )
    elif name == "lane_findings" and config["version"] == 2:
        args = _arguments(arguments, {"id", "cursor"}, name)
        if set(args) not in ({"id"}, {"id", "cursor"}) or not isinstance(
            args.get("id"), str
        ):
            refuse(
                "arguments",
                "lane_findings object with string id and optional cursor",
                repr(args),
                "supply a configured id and bounded cursor",
            )
        ident = args["id"]
        if ID_RE.fullmatch(ident) is None or ident not in config["job_ids"]:
            refuse(
                "arguments",
                "id in configured job_ids",
                repr(ident),
                "select a configured id",
            )
        cursor = args.get("cursor")
        if "cursor" in args and (
            not isinstance(cursor, str) or CURSOR_RE.fullmatch(cursor) is None
        ):
            refuse(
                "arguments",
                f"cursor matching {CURSOR_RE.pattern}",
                repr(cursor),
                "supply a bounded findings cursor",
            )
        result = _findings(config, ident, cursor)
    elif name == "lane_changes" and config["version"] == 2:
        args = _arguments(arguments, {"checkpoint"}, name)
        checkpoint = args.get("checkpoint", {})
        if not isinstance(checkpoint, dict) or any(
            key not in config["job_ids"]
            or not isinstance(value, str)
            or REVISION_RE.fullmatch(value) is None
            for key, value in checkpoint.items()
        ):
            refuse(
                "arguments",
                "checkpoint mapping configured ids to revisions",
                repr(checkpoint),
                "supply only configured ids and bounded revisions",
            )
        result = _changes(config, checkpoint)
    elif name == "lane_jobs" and config["version"] == 2:
        args = _arguments(arguments, {"name"}, name)
        job_name = args.get("name")
        if "name" in args and (
            not isinstance(job_name, str) or JOB_NAME_RE.fullmatch(job_name) is None
        ):
            refuse(
                "arguments",
                f"name matching {JOB_NAME_RE.pattern}",
                repr(job_name),
                "supply a bounded declared job name",
            )
        result = _jobs(config, job_name)
    else:
        count = "seven" if config["version"] == 2 else "four"
        refuse(
            "arguments",
            f"one of the {count} lane tools",
            repr(name),
            "select a listed tool",
        )
    if len(canonical_bytes(result)) > QUERY_BYTES:
        return _base(name, "unavailable", "complete query exceeds 16384 bytes")
    return result
