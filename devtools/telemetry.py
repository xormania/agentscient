"""Local telemetry capture adapted from multi-harness-proof's redacted traces."""

import json
import os
import re
import threading
import time
from pathlib import Path

SENSITIVE = re.compile(
    r"api.?key|authorization|password|credential|private.?key|access.?token|refresh.?token|(^|_)token($|_)|^tokens?$",
    re.I,
)


class Trace:
    def __init__(self, directory, member):
        self.path = Path(directory) / "telemetry" / (member + ".jsonl")
        self.path.parent.mkdir(exist_ok=True, mode=0o700)
        self.handle = self.path.open("a", encoding="utf-8")
        self.path.chmod(0o600)
        self.lock = threading.Lock()
        self.secrets = [v for k, v in os.environ.items() if SENSITIVE.search(k) and len(v) >= 8]

    def clean(self, value):
        if isinstance(value, dict):
            return {key: "[REDACTED]" if SENSITIVE.search(key) else self.clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
        return value

    def record(self, kind, data):
        row = {
            "time": time.time(),
            "monotonic_ns": time.monotonic_ns(),
            "pid": os.getpid(),
            "kind": kind,
            "data": self.clean(data),
        }
        with self.lock:
            if not self.handle.closed:
                self.handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                self.handle.flush()

    def close(self):
        with self.lock:
            self.handle.close()
