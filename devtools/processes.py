"""Linux process identities retained for recovery after a managed supervisor dies."""

import json
import os
import signal
from pathlib import Path

from .profiles import write_json
from .store import identifier


def identity(pid):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return {"pid": int(pid), "start": fields[19], "session": int(fields[3]),
                "boot": Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def register(store, member, generation, pid, *, group=False):
    record = identity(pid)
    if record:
        path = store.directory / "processes" / identifier(member) / generation / f"{pid}.json"
        temporary = path.with_suffix('.tmp')
        write_json(temporary, {**record, "group": group})
        temporary.replace(path)
    return record


def owned(store, member, generation):
    if not generation:
        return []
    result = {}
    directory = store.directory / "processes" / identifier(member) / generation
    for path in directory.glob("*.json"):
        saved = json.loads(path.read_text())
        current = identity(saved["pid"])
        if not current or any(current[key] != saved[key] for key in current):
            continue  # Never signal a reused PID or an unverifiable old group.
        result[current["pid"]] = current
        if saved["group"] and current["session"] == current["pid"]:
            for entry in Path('/proc').iterdir():
                if entry.name.isdecimal():
                    child = identity(int(entry.name))
                    if child and child["session"] == current["session"]:
                        result[child["pid"]] = child
    return list(result.values())


def alive(records):
    return [row for row in records if identity(row["pid"]) == row]


def signal_owned(records, sig):
    for row in records:
        try:
            # Pin the process before checking its birth identity; PID reuse after
            # this check cannot redirect the signal to an unrelated process.
            fd = os.pidfd_open(row["pid"])
            try:
                if identity(row["pid"]) == row:
                    signal.pidfd_send_signal(fd, sig)
            finally:
                os.close(fd)
        except ProcessLookupError:
            pass
