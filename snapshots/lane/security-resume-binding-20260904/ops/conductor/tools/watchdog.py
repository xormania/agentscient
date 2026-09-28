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
import json
import os
import re
import shutil
import subprocess
import sys
import time
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
DEFAULT_WARN_FRACTION = 2 / 3
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
BUCKET_LIMITS = {
    "S": {"files": 3, "lines": 2_000},
}
BUCKET_OVERRUN_FACTOR = 4
MINUTES_OVERRUN_FACTOR = 4
CALIBRATION_MINUTES = {
    "S": {"implement": 4, "author-tests": 21, "check-tests": 10},
}
ROUND_JOBS = {"implement", "author-tests"}


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


def run(argv):
    """Stdout of a subprocess, or None when it could not be run or
    exited non-zero. Executables are resolved to full paths first."""
    exe = shutil.which(argv[0])
    if exe is None:
        return None
    try:
        result = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


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


def entries(store, caps):
    out = []
    try:
        dirs = sorted(p for p in store.iterdir() if p.is_dir())
    except OSError:
        return out
    for d in dirs:
        try:
            rec = read_json(d / "record.json")
            state = read_json(d / "state.json") or {}
        except OSError as exc:
            entry = Entry(d, "error", {}, {}, False, caps)
            entry.error = exc
            out.append(entry)
            continue
        has_exit = (d / "exit").is_file()
        if rec is None:
            kind = "no-copy"
        elif rec.get("status") in TERMINAL:
            kind = "closed"
        elif has_exit:
            kind = "settling"
        else:
            kind = "running"
        out.append(Entry(d, kind, rec or {}, state, has_exit, caps))
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
        plan = (entry.path / "in" / "plan.md").read_text(encoding="utf-8")
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
            chunks.append((entry.path / name).read_text(
                encoding="utf-8", errors="replace"
            ))
        except FileNotFoundError:
            continue
    return "\n".join(chunks)


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
        self.deviations = 0
        if not args.report_existing:
            self.startup_closed = {e.name for e in entries(args.store, self.caps) if e.kind == "closed"}

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
            suite_text = "\n".join(
                filter(None, (
                    envelope.get("note") if isinstance(envelope.get("note"), str) else "",
                    held_text(entry, ("stdout", "stderr", "launcher.log")),
                ))
            )
            if re.search(r"\berrored\b|\berrors\s*=\s*[1-9]\d*\b", suite_text, re.IGNORECASE):
                self.deviation("errors", entry.name)

        refused_text = held_text(entry, ("launcher.log", "stderr"))
        refusal = "|".join(re.escape(item) for item in REFUSAL_CLASSES)
        if re.search(rf"(?m)^\s*(?:{refusal}):", refused_text):
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
        running = []
        settling = 0
        for e in entries(self.args.store, self.caps):
            if e.kind == "error":
                self.once(("error", e.name, type(e.error).__name__), f"watchdog error: {type(e.error).__name__}: {e.error} (tick {self.tick}; the loop continues)")
                continue
            if e.kind == "no-copy":
                self.once(("no-copy", e.name), f"no record copy {e.name}: cannot judge (no record.json in the job directory)")
                continue
            self.scan_deviations(e)
            if e.kind == "closed":
                if e.name not in self.startup_closed:
                    self.once(("closed", e.name), f"closed {e.name} {e.summary()} after {e.minutes(e.closed_at)} min")
                continue
            if e.kind == "settling":
                settling += 1
                first = self.settling_since.setdefault(e.name, self.tick)
                if self.tick - first + 1 >= SETTLING_TICKS:
                    try:
                        since = int((time.time() - (e.path / "exit").stat().st_mtime) // 60)
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
        forge = None if self.args.no_forge else self.forge()
        if self.tick % self.args.heartbeat_every == 0:
            live = ", ".join(f"{e.name} {e.minutes()}m/{int(e.wall_min) if e.wall_min else '?'}" for e in running) or "none"
            launchers_txt = "unreachable" if launchers is None else launchers
            if self.args.no_forge:
                prs = "not watched"
            elif forge is None:
                prs = "unreachable"
            else:
                n, unreachable = forge
                prs = str(n) + (f" (checks unreachable for {', '.join('#' + str(p) for p in unreachable)})" if unreachable else "")
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
        raw = run(["gh", "pr", "list", "--base", self.trunk, "--state", "open", "--json", "number,headRefOid"])
        if raw is None:
            return None
        try:
            prs = json.loads(raw)
        except ValueError:
            return None
        unreachable = []
        for pr in prs:
            number = pr.get("number")
            sha = pr.get("headRefOid") or "unknown"
            checks = run(["gh", "pr", "checks", str(number), "--json", "name,bucket"])
            try:
                rows = json.loads(checks) if checks is not None else None
            except ValueError:
                rows = None
            if rows is None:
                unreachable.append(number)
                continue
            for c in rows:
                bucket = c.get("bucket")
                if bucket in {"fail", "cancel"}:
                    key = (number, sha, c.get("name"))
                    if key not in self.ci_seen:
                        self.ci_seen.add(key)
                        say(f"ci {bucket} #{number} at {sha}: {c.get('name')}")
        return len(prs), unreachable

    def loop(self):
        say(f"watchdog armed: store {self.args.store}, {len(self.startup_closed)} closed records ignored, tick {self.args.tick:g}s")
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
    return Watch(args).loop()


if __name__ == "__main__":
    sys.exit(main())
