"""Local telemetry capture adapted from multi-harness-proof's redacted traces."""

import fcntl
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

SENSITIVE = re.compile(
    r"api.?key|authorization|password|credential|private.?key|access.?token|refresh.?token|(^|_)token($|_)|^tokens?$",
    re.I,
)


def clean(value):
    """Apply the same credential filter to events, hooks and wire captures."""
    secrets = [v for k, v in os.environ.items() if SENSITIVE.search(k) and len(v) >= 8]

    def scrub(item):
        if isinstance(item, dict):
            return {key: "[REDACTED]" if SENSITIVE.search(key) else scrub(v) for key, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [scrub(v) for v in item]
        if isinstance(item, str):
            # MCP text content frequently contains a serialized result object.
            try:
                decoded = json.loads(item)
            except (ValueError, RecursionError):
                decoded = None
            if isinstance(decoded, (dict, list)):
                item = json.dumps(scrub(decoded), ensure_ascii=False)
            for secret in secrets:
                item = item.replace(secret, "[REDACTED]")
            return re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", item)
        return item

    return scrub(value)


class Trace:
    def __init__(self, directory, member, component="native", context=None):
        self.path = Path(directory) / "telemetry" / (member + ".jsonl")
        self.path.parent.mkdir(exist_ok=True, mode=0o700)
        self.handle = self.path.open("a", encoding="utf-8")
        self.path.chmod(0o600)
        self.lock = threading.Lock()
        self.member, self.component = member, component
        self.connection = uuid.uuid4().hex
        self.context = context

    clean = staticmethod(clean)

    def record(self, kind, data, *, frame_context=None):
        row = {
            "time": time.time(),
            "monotonic_ns": time.monotonic_ns(),
            "pid": os.getpid(),
            "actor": self.member,
            "component": self.component,
            "connection": self.connection,
            "context": self.clean(frame_context if frame_context is not None else self.context() if self.context else {}),
            "kind": kind,
            "data": self.clean(data),
        }
        with self.lock:
            if not self.handle.closed:
                # Native bridge, MCP server and hook processes share this file.
                fcntl.flock(self.handle, fcntl.LOCK_EX)
                try:
                    self.handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    self.handle.flush()
                finally:
                    fcntl.flock(self.handle, fcntl.LOCK_UN)

    def close(self):
        with self.lock:
            self.handle.close()


def context(store, member):
    from .control import REQUEST_BINDING
    from .store import REQUEST_WORK

    row = store.member(member)
    with store.connect() as db:
        scope = db.execute("SELECT role,revision FROM member_bindings WHERE member=?", (member,)).fetchone()
        work_order, job = store.current_work(db, member)
    request = REQUEST_WORK.get()
    bound = REQUEST_BINDING.get()
    if bound and bound[0] == member:
        scope = {k: bound[1][k] for k in ("role", "revision")} if bound[1] else None
    return {
        **{k: row[k] for k in ("generation", "native_id", "harness", "selected_work_order", "selected_job")},
        "harness": row["detail"].get("harness", row["harness"]),
        **(dict(scope) if scope else {}),
        "work_order": work_order,
        "job": job,
        "scope_source": "request" if request and request[0] == member else "selection",
    }


def requested(store, member, config, private=None):
    """Record explicit and inherited choices; neither proves what the vendor ran."""
    import tomllib

    inherited = {}
    if config["harness"] == "codex" and private and (private / "config.toml").is_file():
        values = tomllib.loads((private / "config.toml").read_text())
        inherited = {
            k: values.get(v)
            for k, v in {
                "model": "model",
                "provider": "model_provider",
                "reasoning": "model_reasoning_effort",
            }.items()
        }
    fields = ("harness", "vendor", "model", "reasoning", "provider")
    store.event(
        member,
        "runtime_requested",
        settings={k: config.get(k) or inherited.get(k) for k in fields},
        sources={k: "explicit" if config.get(k) else "inherited" if inherited.get(k) else "unknown" for k in fields},
        selection=config.get("selection"),
    )


def observed(store, member, source, payload):
    """Normalize only fields actually reported by the harness; retain the raw evidence."""
    values = {}
    objects = [payload]
    for key in ("thread", "message", "update"):
        if isinstance(payload.get(key), dict):
            objects.append(payload[key])
    aliases = {
        "model": ("model", "modelId", "model_id"),
        "provider": ("modelProvider", "model_provider", "provider"),
        "reasoning": ("reasoningEffort", "reasoning_effort", "effort"),
        "vendor": ("vendor",),
    }
    for obj in objects:
        for field, keys in aliases.items():
            for key in keys:
                if isinstance(obj.get(key), str) and obj[key]:
                    values[field] = obj[key]
        models = obj.get("models")
        if isinstance(models, dict) and isinstance(models.get("currentModelId"), str):
            values["model"] = models["currentModelId"]
        for option in obj.get("configOptions", []) if isinstance(obj.get("configOptions"), list) else []:
            if isinstance(option, dict) and option.get("category") in {"model", "thought_level"}:
                field = "model" if option["category"] == "model" else "reasoning"
                if isinstance(option.get("currentValue"), str):
                    values[field] = option["currentValue"]
    if values:
        store.event(member, "runtime_observed", source=source, settings=values)
    return values


class Transcript:
    """Tail Claude's native JSONL as it grows, including messages, tools and usage."""

    def __init__(self, store, member, trace):
        self.store, self.member, self.trace = store, member, trace
        self.after, self.path, self.offset, self.inode = 0, None, 0, None

    def poll(self):
        rows = self.store.events(after=self.after, actor=self.member, kind="native_transcript", limit=100)["events"]
        for row in rows:
            self.after = row["id"]
            if row["data"].get("generation") == self.store.member(self.member)["generation"]:
                path = Path(row["data"]["path"])
                if path != self.path:
                    self.path, self.offset, self.inode = path, 0, None
        if not self.path or not self.path.is_file():
            return
        with self.path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            if self.inode != stat.st_ino or stat.st_size < self.offset:
                self.offset, self.inode = 0, stat.st_ino
            stream.seek(self.offset)
            while line := stream.readline():
                if not line.endswith(b"\n"):
                    break
                self.offset = stream.tell()
                try:
                    packet = json.loads(line)
                    if not isinstance(packet, dict):
                        raise ValueError("Expected a transcript object")
                except ValueError as error:
                    self.trace.record("transcript_invalid", {"offset": self.offset, "error": str(error)})
                    continue
                self.trace.record("native_transcript", {"offset": self.offset, "entry": packet})
                observed(self.store, self.member, "claude/transcript", packet)
                message = packet.get("message", {})
                if isinstance(message, dict) and isinstance(message.get("usage"), dict):
                    self.store.event(
                        self.member,
                        "native_usage",
                        source="claude/transcript",
                        observation=message["usage"],
                        message=message.get("id"),
                        transcript_offset=self.offset,
                    )
