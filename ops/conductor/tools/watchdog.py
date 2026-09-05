#!/usr/bin/env python3
"""The session watchdog: one line per condition worth acting on.

Reads the live dispatch store and the forge; never writes. Every tick
it classifies each job directory by what is on disk and prints, once
per record, the lines the contract (`ops/conductor/watchdog-lever.md`)
names: a record closed, a harness process gone with no exit written,
an exit written that the launcher never collected, a run past its
warning fraction of the wall, a record it cannot judge, CI red or
cancelled on an open pull request into the trunk, mechanical deviations
from the declared plan, and a heartbeat on cadence. A tick that raises
prints the error as a line and the loop goes on: silence is never the
report of a crash.
"""
from __future__ import annotations

import argparse
import codecs
import contextlib
import json
import os
import re
import selectors
import shutil
import stat as stat_mode
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
JOBS_JSON_CANDIDATES = (
    HERE.parents[2] / "devlane" / "task" / "jobs.json",
    Path.cwd() / "ops" / "devlane" / "task" / "jobs.json",
)
TERMINAL = {"closed", "died"}
DEFAULT_TICK = 300.0
DEFAULT_HEARTBEAT = 6
DEFAULT_FORGE_EVERY = 1
DEFAULT_WARN_FRACTION = 2 / 3
FORGE_LIMIT = 200
FORGE_TIMEOUT = 10
JOB_INPUT_LIMIT = 64 * 1024 * 1024
PROCESS_OUTPUT_LIMIT = 1024 * 1024
CHECK_NAME_LIMIT = 512
FALLBACK_WARN_MIN = 40
SETTLING_TICKS = 2
ASSUMPTION_WORDS = (
    "assumption",
    "assume",
    "substitute",
    "stub",
    "hermetic substitute",
)
LOCK_FILES = ("composer.lock", "Cargo.lock", "requirements.lock", "symfony.lock")
REFUSAL_CLASSES = ("empty-comparison", "scope-cap", "conf-key", "toolchain")
ERROR_TEXT_RE = re.compile(
    r"\berrored\b|\berrors\s*=\s*[1-9]\d*\b",
    re.IGNORECASE,
)
REFUSAL_BYTES_RE = re.compile(
    rb"(?m)^\s*(?:" + b"|".join(
        re.escape(item).encode() for item in REFUSAL_CLASSES
    ) + rb"):"
)
BUCKET_LIMITS = {
    "S": {"files": 3, "lines": 2_000},
}
BUCKET_OVERRUN_FACTOR = 4
MINUTES_OVERRUN_FACTOR = 4
CALIBRATION_MINUTES = {
    "S": {"implement": 4, "author-tests": 21, "check-tests": 10},
}
ROUND_JOBS = {"implement", "author-tests"}
CHECK_BUCKETS = {"pass", "fail", "pending", "skipping", "cancel"}
SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


def _laneconf():
    """The conf reader beside this file, or beside the working directory
    when this file runs as a staged copy; None when neither holds it."""
    for tools in (HERE.parent, Path.cwd() / "ops" / "conductor" / "tools"):
        if (tools / "laneconf.py").is_file():
            if str(tools) not in sys.path:
                sys.path.insert(0, str(tools))
            try:
                import laneconf
            except ImportError:
                return None
            return laneconf
    return None


def conf_value(key):
    """A key through the conf reader; a missing key is refusal class
    conf-key, never a literal here."""
    reader = _laneconf()
    if reader is not None:
        try:
            return reader.get(key)
        except reader.ConfigError as error:
            refuse("conf-key", f"{key} in the lane conf", str(error), "define it")
    refuse("conf-key", "the lane conf reader beside this file or the working directory", "neither", "run from the repository root or set LANE_CONF and keep laneconf.py beside the conf")
    return None


def refuse(cls, expected, found, needed):
    print(f"{cls}: expected {expected}; found {found}; needed {needed}", file=sys.stderr)
    sys.exit(2)


def say(line):
    print(line, flush=True)


def now():
    return datetime.now(timezone.utc)


def store_root(explicit):
    """The same rule as launch.py `_jobs_root`: DISPATCH_JOBS, then
    XDG_STATE_HOME, then HOME/.local/state."""
    if explicit:
        return Path(explicit)
    if os.environ.get("DISPATCH_JOBS"):
        return Path(os.environ["DISPATCH_JOBS"])
    state = os.environ.get("XDG_STATE_HOME")
    base = Path(state) if state else Path(os.environ.get("HOME", "")) / ".local/state"
    return base / conf_value("LANE_NAME") / "dispatch"


def parse_stamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def stamp_of(name):
    try:
        return datetime.strptime(name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class InputUnavailable(OSError):
    """A per-job input exists but cannot produce a safe reading."""


class InitialExtent:
    """A binary stream capped at the regular file's size when opened."""

    def __init__(self, stream, size):
        self.stream = stream
        self.remaining = size

    def read(self, size=-1):
        if self.remaining <= 0:
            return b""
        amount = self.remaining if size < 0 else min(size, self.remaining)
        chunk = self.stream.read(amount)
        self.remaining -= len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.stream.close()


def _open_directory(path, *, dir_fd=None):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags, dir_fd=dir_fd)
    except FileNotFoundError:
        raise
    except OSError:
        raise InputUnavailable("job input unavailable") from None


def _open_job_file(job_path, relative):
    """Open a bounded regular file beneath a no-follow job directory."""
    parts = Path(relative).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise InputUnavailable("job input unavailable")
    directories = []
    file_fd = None
    try:
        directories.append(_open_directory(job_path))
        for part in parts[:-1]:
            directories.append(_open_directory(part, dir_fd=directories[-1]))
        flags = os.O_RDONLY | os.O_NONBLOCK
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            file_fd = os.open(parts[-1], flags, dir_fd=directories[-1])
        except FileNotFoundError:
            raise
        except OSError:
            raise InputUnavailable("job input unavailable") from None
        file_stat = os.fstat(file_fd)
        if (
            not stat_mode.S_ISREG(file_stat.st_mode)
            or file_stat.st_size > JOB_INPUT_LIMIT
        ):
            raise InputUnavailable("job input unavailable")
        stream = os.fdopen(file_fd, "rb")
        file_fd = None
        return InitialExtent(stream, file_stat.st_size), file_stat
    except FileNotFoundError:
        raise
    except InputUnavailable:
        raise
    except OSError:
        raise InputUnavailable("job input unavailable") from None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for directory in reversed(directories):
            os.close(directory)


def _read_job_text(job_path, relative):
    stream, _ = _open_job_file(job_path, relative)
    with stream:
        return stream.read().decode("utf-8", "replace")


def _read_job_json(job_path, relative):
    try:
        data = json.loads(_read_job_text(job_path, relative))
    except FileNotFoundError:
        return None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def read_json(path):
    """A dict, or None when the file is absent or not a JSON object. Any
    other failure to read (a directory in its place, a permission) is
    raised, so the tick guard reports it rather than inferring absence."""
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def job_caps():
    """The catalogue beside this file, or beside the working directory
    when this file runs as a staged copy."""
    data = {}
    for candidate in JOBS_JSON_CANDIDATES:
        if candidate.is_file():
            data = read_json(candidate) or {}
            break
    caps = {}
    for name, job in data.items():
        if isinstance(job, dict) and isinstance(job.get("caps"), dict):
            timeout = job["caps"].get("timeout")
            if isinstance(timeout, (int, float)):
                caps[name] = float(timeout)
    return caps


def process_alive(pid, expect_word):
    """True when the pid is a live process whose command line carries
    the expected word (the harness name), so a reused pid does not read
    as the worker. EPERM means the process exists."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    proc = Path("/proc") / str(pid)
    if proc.is_dir():
        try:
            cmdline = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            return True
        return expect_word in cmdline if expect_word else True
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def run(argv, timeout=90):
    """Stdout of a subprocess, or None when it could not be run or
    exited non-zero. Capture is bounded and never forwarded."""
    exe = shutil.which(argv[0])
    if exe is None:
        return None
    process = None
    selector = selectors.DefaultSelector()
    stdout = []
    captured = 0
    deadline = time.monotonic() + max(0, timeout)
    try:
        process = subprocess.Popen(
            [exe, *argv[1:]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            events = selector.select(remaining)
            if not events:
                return None
            for key, _ in events:
                chunk = os.read(key.fd, 64 * 1024)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                captured += len(chunk)
                if captured > PROCESS_OUTPUT_LIMIT:
                    return None
                if key.data == "stdout":
                    stdout.append(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        returncode = process.wait(timeout=remaining)
        if returncode != 0:
            return None
        return b"".join(stdout).decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    finally:
        selector.close()
        if process is not None:
            if process.poll() is None:
                process.kill()
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            with contextlib.suppress(subprocess.SubprocessError):
                process.wait(timeout=max(0, deadline - time.monotonic()))


class Entry:
    """One job directory, classified by what is on disk."""

    def __init__(self, path, kind, rec, state, has_exit, caps):
        self.path = path
        self.name = path.name
        self.kind = kind
        self.rec = rec
        self.state = state
        self.has_exit = has_exit
        self.error = None
        at = rec.get("at") if isinstance(rec.get("at"), dict) else {}
        self.launched = parse_stamp(at.get("launched")) or stamp_of(self.name)
        self.closed_at = parse_stamp(at.get("closed"))
        job = rec.get("job")
        self.job = job.get("name") if isinstance(job, dict) else job
        harness = rec.get("harness")
        self.harness = harness.get("name") if isinstance(harness, dict) else None
        rec_caps = rec.get("caps") if isinstance(rec.get("caps"), dict) else {}
        timeout = rec_caps.get("timeout")
        if not isinstance(timeout, (int, float)):
            timeout = caps.get(self.job)
        self.wall_min = float(timeout) / 60 if isinstance(timeout, (int, float)) else None

    def minutes(self, until=None):
        if self.launched is None:
            return None
        end = until or now()
        return int((end - self.launched).total_seconds() // 60)

    def summary(self):
        res = self.rec.get("result") if isinstance(self.rec.get("result"), dict) else {}
        env = res.get("envelope") if isinstance(res.get("envelope"), dict) else {}
        changed = res.get("changed_paths")
        n = len(changed) if isinstance(changed, list) else "unknown"
        return f"status={self.rec.get('status')} env={env.get('status')} changed={n}"

    def harness_alive(self):
        pid = self.state.get("pid")
        if pid is None:
            return None
        return process_alive(pid, self.harness)


WATCHED_INPUTS = (
    "record.json",
    "state.json",
    "exit",
    "in/plan.md",
    "raw.out",
    "stdout",
    "stderr",
    "launcher.log",
)


def input_fingerprint(path):
    """Mutation-sensitive metadata for every input used by a closed scan."""
    fingerprint = []
    for name in WATCHED_INPUTS:
        try:
            stream, file_stat = _open_job_file(path, name)
        except FileNotFoundError:
            fingerprint.append((name, None))
            continue
        stream.stream.close()
        fingerprint.append((
            name,
            file_stat.st_dev,
            file_stat.st_ino,
            file_stat.st_mode,
            file_stat.st_size,
            file_stat.st_mtime_ns,
            file_stat.st_ctime_ns,
        ))
    return tuple(fingerprint)


def entries(store, caps, closed_cache=None):
    out = []
    dirs = []
    for path in store.iterdir():
        try:
            path_stat = path.stat(follow_symlinks=False)
        except OSError as exc:
            if closed_cache is not None:
                closed_cache.pop(path.name, None)
            entry = Entry(path, "error", {}, {}, False, caps)
            entry.error = exc
            entry.fingerprint = None
            out.append(entry)
            continue
        if stat_mode.S_ISDIR(path_stat.st_mode) or stat_mode.S_ISLNK(path_stat.st_mode):
            dirs.append(path)
    dirs.sort()
    present = {path.name for path in dirs}
    present.update(entry.name for entry in out)
    if closed_cache is not None:
        for name in set(closed_cache) - present:
            del closed_cache[name]
    for d in dirs:
        try:
            fingerprint = input_fingerprint(d)
            cached = closed_cache.get(d.name) if closed_cache is not None else None
            if cached is not None and cached[0] == fingerprint:
                out.append(cached[1])
                continue
            rec = _read_job_json(d, "record.json")
            state = _read_job_json(d, "state.json") or {}
        except OSError as exc:
            if closed_cache is not None:
                closed_cache.pop(d.name, None)
            entry = Entry(d, "error", {}, {}, False, caps)
            entry.error = exc
            entry.fingerprint = None
            out.append(entry)
            continue
        exit_row = next(row for row in fingerprint if row[0] == "exit")
        has_exit = exit_row[1] is not None
        if rec is None:
            kind = "no-copy"
        elif rec.get("status") in TERMINAL:
            kind = "closed"
        elif has_exit:
            kind = "settling"
        else:
            kind = "running"
        entry = Entry(d, kind, rec or {}, state, has_exit, caps)
        entry.fingerprint = fingerprint
        entry.exit_mtime = exit_row[5] / 1_000_000_000 if has_exit else None
        out.append(entry)
        if closed_cache is not None:
            if kind == "closed":
                closed_cache[d.name] = (fingerprint, entry)
            else:
                closed_cache.pop(d.name, None)
    return out


def text_values(value):
    """Yield only values from a JSON-shaped object, never its keys."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from text_values(item)


def bucket_from(entry):
    """The first bucket line in the copied plan, or in the record scope."""
    try:
        plan = _read_job_text(entry.path, "in/plan.md")
    except FileNotFoundError:
        brief = entry.rec.get("brief")
        plan = brief.get("scope") if isinstance(brief, dict) else None
    if not isinstance(plan, str):
        return None, set()
    for line in plan.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0].lower() == "bucket":
            return fields[2].upper(), set(fields[3:])
    return None, set()


def held_text(entry, names):
    """Text from held launcher files; absent files are an empty reading."""
    chunks = []
    for name in names:
        try:
            chunks.append(_read_job_text(entry.path, name))
        except FileNotFoundError:
            continue
    return "\n".join(chunks)


def _is_word(char):
    return char == "_" or char.isalnum()


def _is_digit(char):
    return char.isdecimal()


def _error_stream_matches(stream):
    """Match ERROR_TEXT_RE with bounded state over incrementally decoded text."""
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    stem = "error"
    stem_at = 0
    count_state = 0
    errored_pending = False
    previous = None

    def consume(text):
        nonlocal stem_at, count_state, errored_pending, previous
        for char in text:
            word = _is_word(char)
            if errored_pending:
                if not word:
                    return True
                errored_pending = False

            if count_state == 1:
                if char.isspace():
                    pass
                elif char == "=":
                    count_state = 2
                else:
                    count_state = 0
            elif count_state == 2:
                if char.isspace():
                    pass
                elif char in "123456789":
                    count_state = 3
                else:
                    count_state = 0
            elif count_state == 3:
                if _is_digit(char):
                    pass
                elif not word:
                    return True
                else:
                    count_state = 0

            folded = char.casefold()
            if stem_at < len(stem):
                if folded == stem[stem_at]:
                    if stem_at or previous is None or not _is_word(previous):
                        stem_at += 1
                    else:
                        stem_at = 0
                else:
                    stem_at = (
                        1
                        if folded == "e"
                        and (previous is None or not _is_word(previous))
                        else 0
                    )
            elif stem_at == len(stem):
                if folded == "s":
                    count_state = 1
                    stem_at = 0
                elif folded == "e":
                    stem_at += 1
                else:
                    stem_at = 0
            elif folded == "d":
                errored_pending = True
                stem_at = 0
            else:
                stem_at = (
                    1
                    if folded == "e"
                    and (previous is None or not _is_word(previous))
                    else 0
                )
            previous = char
        return False

    while chunk := stream.read(64 * 1024):
        if consume(decoder.decode(chunk)):
            return True
    if consume(decoder.decode(b"", final=True)):
        return True
    return errored_pending or count_state == 3


def _refusal_stream_matches(stream):
    """Match REFUSAL_BYTES_RE with bounded state, including long whitespace."""
    tokens = tuple(f"{item}:".encode() for item in REFUSAL_CLASSES)
    prefix = bytearray()
    at_line_start = True
    whitespace = b" \t\n\r\v\f"
    while chunk := stream.read(64 * 1024):
        for byte in chunk:
            if not at_line_start and not prefix:
                if byte == ord("\n"):
                    at_line_start = True
                continue
            if at_line_start and not prefix and byte in whitespace:
                continue
            prefix.append(byte)
            candidates = [token for token in tokens if token.startswith(prefix)]
            if any(len(prefix) == len(token) for token in candidates):
                return True
            if not candidates:
                at_line_start = byte == ord("\n")
                prefix.clear()
            else:
                at_line_start = False
    return False


def held_matches(entry, names, matcher):
    """Search bounded initial extents of no-follow regular held files."""
    for name in names:
        try:
            stream, _ = _open_job_file(entry.path, name)
            with stream:
                if matcher(stream):
                    return True
        except FileNotFoundError:
            continue
    return False


def _event_name(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        return None
    if len(encoded) > CHECK_NAME_LIMIT:
        return None
    safe = []
    for char in value:
        code = ord(char)
        if unicodedata.category(char).startswith("C") or char in {"\u2028", "\u2029"}:
            if char == "\n":
                safe.append(r"\n")
            elif char == "\r":
                safe.append(r"\r")
            elif char == "\t":
                safe.append(r"\t")
            elif code <= 0xFFFF:
                safe.append(f"\\u{code:04x}")
            else:
                safe.append(f"\\U{code:08x}")
        else:
            safe.append(char)
    return "".join(safe)


def _check_rows(rows):
    if not isinstance(rows, list):
        return None
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            return None
        bucket = row.get("bucket")
        if not isinstance(bucket, str) or bucket not in CHECK_BUCKETS:
            return None
        name = _event_name(row.get("name"))
        if name is None:
            return None
        normalized.append((name, bucket))
    return normalized


class Watch:
    def __init__(self, args):
        self.args = args
        self.caps = job_caps()
        self.trunk = conf_value("TRUNK_BRANCH")
        self.tick = 0
        self.reported = set()
        self.settling_since = {}
        self.launcher_pairs = set()
        self.ci_seen = set()
        self.startup_closed = set()
        self.closed_cache = {}
        self.closed_scanned = {}
        self.forge_reading = None
        self.forge_tick = None
        self.startup_error = None
        self.deviations = 0
        try:
            initial = entries(args.store, self.caps, self.closed_cache)
        except OSError as exc:
            self.startup_error = exc
        else:
            if not args.report_existing:
                self.startup_closed = {
                    entry.name for entry in initial if entry.kind == "closed"
                }

    def once(self, key, line):
        if key not in self.reported:
            self.reported.add(key)
            say(line)
            return True
        return False

    def deviation(self, kind, record_id):
        if self.once(
            ("deviation", kind, record_id),
            f"deviation {kind} {record_id}",
        ):
            self.deviations += 1

    def scan_deviations(self, entry):
        result = entry.rec.get("result")
        result = result if isinstance(result, dict) else {}
        envelope = result.get("envelope")
        envelope = envelope if isinstance(envelope, dict) else {}
        changed = result.get("changed_paths")
        changed = [p for p in changed if isinstance(p, str)] if isinstance(changed, list) else []
        bucket_class, bucket_paths = bucket_from(entry)
        limit = BUCKET_LIMITS.get(bucket_class)

        assumption_text = "\n".join(text_values({
            "note": envelope.get("note"),
            "findings": envelope.get("findings"),
        })).lower()
        if any(word in assumption_text for word in ASSUMPTION_WORDS):
            self.deviation("assumption", entry.name)

        if any(
            Path(path).name in LOCK_FILES and path not in bucket_paths
            for path in changed
        ):
            self.deviation("lock", entry.name)

        if bucket_class is not None and (
            any(path not in bucket_paths for path in changed)
            or (
                limit is not None
                and len(changed) > limit["files"] * BUCKET_OVERRUN_FACTOR
            )
        ):
            self.deviation("bucket", entry.name)

        landed_lines = result.get("landed_lines")
        if entry.job in ROUND_JOBS and limit is not None and (
            len(changed) > limit["files"]
            or (
                isinstance(landed_lines, (int, float))
                and landed_lines > limit["lines"]
            )
        ):
            self.deviation("size", entry.name)

        findings = envelope.get("findings")
        has_findings = isinstance(findings, list) and bool(findings)
        if envelope.get("status") in {"tripped", "invalid"} and (
            has_findings or changed
        ):
            self.deviation("envelope", entry.name)

        if entry.job == "author-tests":
            note = envelope.get("note")
            note_has_errors = isinstance(note, str) and ERROR_TEXT_RE.search(note)
            errors_key = ("deviation", "errors", entry.name)
            if errors_key not in self.reported and (
                note_has_errors
                or held_matches(
                    entry,
                    ("raw.out", "stdout", "stderr", "launcher.log"),
                    _error_stream_matches,
                )
            ):
                self.deviation("errors", entry.name)

        refused_key = ("deviation", "refused", entry.name)
        if refused_key not in self.reported and held_matches(
            entry,
            ("raw.out", "stdout", "stderr", "launcher.log"),
            _refusal_stream_matches,
        ):
            self.deviation("refused", entry.name)

        minutes = entry.minutes(entry.closed_at)
        minute_limit = CALIBRATION_MINUTES.get(bucket_class, {}).get(entry.job)
        if (
            minutes is not None
            and minute_limit is not None
            and minutes > minute_limit * MINUTES_OVERRUN_FACTOR
        ):
            self.deviation("minutes", entry.name)

    def scan_ladders(self):
        ladder_root = self.args.store.parent / "ladders"
        try:
            paths = sorted(ladder_root.glob("*.json"))
        except OSError:
            return
        for path in paths:
            ladder = read_json(path)
            if ladder is None:
                continue
            record_id = ladder.get("id")
            if not isinstance(record_id, str) or not record_id:
                record_id = path.stem
            stages = ladder.get("stages")
            stages = stages if isinstance(stages, list) else []
            retried = any(
                isinstance(stage, dict)
                and isinstance(stage.get("attempt"), (int, float))
                and stage["attempt"] > 1
                for stage in stages
            )
            if ladder.get("status") == "stopped" or retried:
                self.deviation("retry", record_id)

    def run_tick(self):
        self.tick += 1
        if self.startup_error is not None:
            error = self.startup_error
            self.startup_error = None
            raise error
        running = []
        settling = 0
        for e in entries(self.args.store, self.caps, self.closed_cache):
            if e.kind == "error":
                self.deviation("unavailable", e.name)
                self.once(("error", e.name), f"watchdog error: InputUnavailable: job inputs unavailable for {e.name} (tick {self.tick}; the loop continues)")
                continue
            if e.kind == "no-copy":
                self.once(("no-copy", e.name), f"no record copy {e.name}: cannot judge (no record.json in the job directory)")
                continue
            if e.kind != "closed" or self.closed_scanned.get(e.name) != e.fingerprint:
                try:
                    self.scan_deviations(e)
                except InputUnavailable:
                    self.deviation("unavailable", e.name)
                else:
                    if e.kind == "closed":
                        self.closed_scanned[e.name] = e.fingerprint
            if e.kind == "closed":
                if e.name not in self.startup_closed:
                    self.once(("closed", e.name), f"closed {e.name} {e.summary()} after {e.minutes(e.closed_at)} min")
                continue
            if e.kind == "settling":
                settling += 1
                first = self.settling_since.setdefault(e.name, self.tick)
                if self.tick - first + 1 >= SETTLING_TICKS:
                    try:
                        since = int((time.time() - e.exit_mtime) // 60)
                    except OSError:
                        since = "unknown"
                    self.once(("settling", e.name), f"exit written, not collected {e.name}: {since} min since exit, record still {e.rec.get('status')}")
                continue
            m = e.minutes()
            if e.harness_alive() is False:
                self.once(("gone", e.name), f"harness gone {e.name} after {m} min: pid {e.state.get('pid')} dead, no exit written")
                continue
            running.append(e)
            if m is None:
                continue
            if e.wall_min is None:
                if m >= FALLBACK_WARN_MIN * self.args.warn_fraction:
                    self.once(("long", e.name), f"long {e.name}: {m} min running, wall unknown")
            elif m >= e.wall_min * self.args.warn_fraction:
                self.once(("long", e.name), f"long {e.name}: {m} min running, wall {int(e.wall_min)} min")
        self.scan_ladders()
        launchers = self.launcher_count()
        if launchers is not None and launchers < len(running):
            pair = (launchers, len(running))
            if pair not in self.launcher_pairs:
                self.launcher_pairs.add(pair)
                say(f"launchers fewer than running records: {launchers} launch.py processes, {len(running)} running (heuristic: the record does not name its launcher)")
        forge_fresh = False
        if not self.args.no_forge and (self.tick - 1) % self.args.forge_every == 0:
            self.forge_reading = self.forge()
            self.forge_tick = self.tick
            forge_fresh = True
        if self.tick % self.args.heartbeat_every == 0:
            live = ", ".join(f"{e.name} {e.minutes()}m/{int(e.wall_min) if e.wall_min else '?'}" for e in running) or "none"
            launchers_txt = "unreachable" if launchers is None else launchers
            if self.args.no_forge:
                prs = "not watched"
            elif self.forge_reading is None:
                prs = "unreachable"
            else:
                n, unreachable = self.forge_reading
                notes = []
                if n == FORGE_LIMIT:
                    count = f"{FORGE_LIMIT}+"
                    notes.append("page full, total unmeasured")
                else:
                    count = str(n)
                if not forge_fresh:
                    notes.append(f"cached from tick {self.forge_tick}")
                if unreachable:
                    numbers = ", ".join(f"#{number}" for number in unreachable)
                    notes.append(f"checks unreachable for {numbers}")
                prs = count + (f" ({'; '.join(notes)})" if notes else "")
            say(f"heartbeat: running={live}; settling={settling}; launchers={launchers_txt}; open PRs into {self.trunk}={prs}; deviations={self.deviations}")

    def launcher_count(self):
        if shutil.which("pgrep") is None:
            return None
        out = run(["pgrep", "-fc", r"^python3 .*launch\.py "])
        if out is None:
            return 0
        try:
            return int(out.strip() or 0)
        except ValueError:
            return None

    def forge(self):
        deadline = time.monotonic() + FORGE_TIMEOUT
        raw = run([
            "gh", "pr", "list", "--base", self.trunk, "--state", "open",
            "--limit", str(FORGE_LIMIT), "--json", "number,headRefOid",
        ], timeout=max(0, deadline - time.monotonic()))
        if raw is None:
            return None
        try:
            prs = json.loads(raw)
        except ValueError:
            return None
        if (
            not isinstance(prs, list)
            or len(prs) > FORGE_LIMIT
            or any(
                not isinstance(pr, dict)
                or not isinstance(pr.get("number"), int)
                or isinstance(pr.get("number"), bool)
                or pr["number"] <= 0
                or not isinstance(pr.get("headRefOid"), str)
                or SHA_RE.fullmatch(pr["headRefOid"]) is None
                for pr in prs
            )
        ):
            return None
        unreachable = []
        for index, pr in enumerate(prs):
            number = pr.get("number")
            sha = pr.get("headRefOid")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                unreachable.extend(row["number"] for row in prs[index:])
                break
            checks = run(
                ["gh", "pr", "checks", str(number), "--json", "name,bucket"],
                timeout=remaining,
            )
            try:
                rows = json.loads(checks) if checks is not None else None
            except ValueError:
                rows = None
            normalized = _check_rows(rows)
            if normalized is None:
                unreachable.append(number)
                continue
            for name, bucket in normalized:
                if bucket in {"fail", "cancel"}:
                    key = (number, sha, name)
                    if key not in self.ci_seen:
                        self.ci_seen.add(key)
                        say(f"ci {bucket} #{number} at {sha}: {name}")
        return len(prs), unreachable

    def loop(self):
        ignored = (
            "unreachable"
            if self.startup_error is not None
            else str(len(self.startup_closed))
        )
        say(f"watchdog armed: store {self.args.store}, {ignored} closed records ignored, tick {self.args.tick:g}s")
        while True:
            try:
                self.run_tick()
            except Exception as exc:
                # The loop must outlive any one tick; the error is the event.
                say(f"watchdog error: {type(exc).__name__}: {exc} (tick {self.tick}; the loop continues)")
            if self.args.once:
                return 0
            time.sleep(self.args.tick)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Watch the dispatch store and the forge; print one line per condition.")
    parser.add_argument("--store", help="the dispatch store (default: DISPATCH_JOBS, then XDG_STATE_HOME, then HOME)")
    parser.add_argument("--tick", help="seconds between ticks (default: WATCHDOG_TICK or 300)")
    parser.add_argument("--heartbeat-every", type=int, default=DEFAULT_HEARTBEAT, help="ticks between heartbeats")
    parser.add_argument("--forge-every", default=str(DEFAULT_FORGE_EVERY), help="ticks between forge readings")
    parser.add_argument("--warn-fraction", type=float, default=DEFAULT_WARN_FRACTION, help="fraction of the wall at which a run is long")
    parser.add_argument("--once", action="store_true", help="one tick, then exit 0")
    parser.add_argument("--report-existing", action="store_true", help="report records already closed at start")
    parser.add_argument("--no-forge", action="store_true", help="do not ask the forge")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    args.store = store_root(args.store)
    if not args.store.is_dir():
        refuse("store", "a dispatch store directory", f"nothing at {args.store}", "run a dispatch first or pass --store")
    raw_tick = args.tick if args.tick is not None else os.environ.get("WATCHDOG_TICK", str(DEFAULT_TICK))
    try:
        args.tick = float(raw_tick)
    except ValueError:
        args.tick = -1.0
    if args.tick <= 0:
        refuse("tick", "a positive number of seconds", repr(raw_tick), "set --tick or WATCHDOG_TICK to a positive number")
    if args.heartbeat_every <= 0 or not 0 < args.warn_fraction <= 1:
        refuse("arguments", "heartbeat-every above zero and warn-fraction in (0, 1]", f"{args.heartbeat_every}, {args.warn_fraction}", "fix the values")
    raw_forge_every = args.forge_every
    try:
        args.forge_every = int(raw_forge_every)
    except ValueError:
        args.forge_every = 0
    if args.forge_every <= 0:
        refuse("arguments", "forge-every as a positive integer", repr(raw_forge_every), "set --forge-every to a positive integer")
    return Watch(args).loop()


if __name__ == "__main__":
    sys.exit(main())
