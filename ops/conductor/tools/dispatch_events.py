#!/usr/bin/env python3
"""The follow-through: a launched job's change becomes a message.

Contract: ops/conductor/sessions-lever.md, "Slice 3 — Dispatcher
integration", the follow-through paragraph. Inherits
ops/conductor/instrument-conventions.md: the refusal wire, the four exit
classes, identity for writes.

    dispatch_events.py route --consumer C [--once] [--tick N]

Each pass writes a monitor config under the state directory naming the
launched intents' record ids (the dispatch adapter reads a static id
list), runs `monitor.py run --once` over it, reads `digest --consumer C`
and sends by the dispatch metric's own word: `completion` and `no-op`
an `inform` to the requester, `invalid` and `death` a `finding` to the
Dispatcher and the requester; every other word, and an event for a
record no intent carries, is acked and never sent. Each send carries
`key event:<event id>:<recipient>`, so a digest served twice sends once;
the cursor is acked only after every send of the batch is committed,
so a failed send leaves the batch to the next pass.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import sqlite3
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    import coordination
    import dispatch_intents as intents
    from instrument import EXIT_DONE, Refusal, emit, identity, refuse, run, state_dir
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py, coordination.py and dispatch_intents.py beside this "
        "tool; found absent; needed restore them beside ops/conductor/tools/dispatch_events.py",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

INFORM = ("completion", "no-op")
FINDING = ("invalid", "death")
WORD = re.compile(r'^status="([^"]*)"')
BATCH = 50
READ_WAIT = 120
MAX_IDS = 256


def usage() -> str:
    return "route --consumer C [--once] [--tick N]"


def config_for(records: list, consumer: str) -> dict:
    return {
        "version": 1,
        "schedules": {"pass": {"enabled": True, "every_s": 1}},
        "monitors": {"jobs": {"enabled": True, "adapter": "dispatch", "schedule": "pass",
                              "params": {"store": str(intents.jobs_root()), "ids": records}}},
        "conditions": {"job_change": {"enabled": True, "monitor": "jobs", "op": "changed",
                                      "field": "status", "threshold": None, "cooldown_s": 0}},
        "routes": {"jobs": {"enabled": True, "condition": "job_change", "adapter": "queue",
                            "consumer": consumer}},
    }


def monitor(program, config, state, *args):
    reading = run([*program, "--config", str(config), "--state", str(state), *args],
                  timeout=READ_WAIT)
    if reading.returncode != 0:
        line = next((text for text in reversed(reading.stderr.splitlines()) if text.strip()),
                    f"exit {reading.returncode}")
        refuse("store", f"monitor.py {args[0]} to answer", line.strip(),
               "repair the monitor state or its config, then run the pass again")
    return reading.stdout


def sender():
    """The core's send, and refuse when it takes no idempotency key yet."""
    send = coordination.CORE["send"]
    if "key" not in inspect.signature(send).parameters:
        refuse("store", "the core's send taking a key (sessions slice 2)", "send without key",
               "land slice 2's send --key before routing events")
    return send


def recipients(found, word: str) -> list:
    requester = f"PT-{found['requester']}"
    if word in INFORM:
        return [("inform", requester)]
    dispatcher = f"PT-{found['dispatcher']}"
    return [("finding", who) for who in dict.fromkeys((dispatcher, requester))]


def exit_of(record: str) -> str:
    try:
        return (intents.jobs_root() / record / "exit").read_text(encoding="utf-8").strip() or "none"
    except OSError:
        return "none"


def one_pass(consumer: str) -> list:
    program = intents.program("DISPATCH_MONITOR", "store")
    base = state_dir() / "dispatch-events" / consumer
    config, state = base / "monitor.json", base / "monitor"
    conn = intents.writer()
    part = coordination.bound_participant(conn)
    send = sender()
    records = [found["record"] for found in intents.in_phases(conn, ("launched",))
               if found["record"]][-MAX_IDS:]
    try:
        base.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(config_for(records, consumer), indent=1) + "\n",
                          encoding="utf-8")
    except OSError as error:
        refuse("store", f"a writable pass config at {config}", error.strerror,
               "make the state directory writable")
    if records:
        monitor(program, config, state, "run", "--once")
    try:
        events = json.loads(monitor(program, config, state, "digest", "--consumer", consumer,
                                    "--limit", str(BATCH)))["events"]
    except (ValueError, KeyError, TypeError):
        refuse("store", "the digest as JSON with events", "unreadable output",
               "repair the monitor, then run the pass again")
    lines = []
    for event in events:
        record = str(event.get("subject") or "")
        match = WORD.match(str(event.get("summary") or ""))
        word = match.group(1) if match else "unknown"
        found = intents.by_record(conn, record) if record else None
        if found is None:
            lines.append(f"event {event.get('id')} {record or 'none'} {word} no intent; acked")
            continue
        if word not in INFORM + FINDING:
            lines.append(f"event {event.get('id')} DI-{found['id']} {word}; acked")
            continue
        body = (f"DI-{found['id']} {found['job']} record {record} {word} "
                f"exit {exit_of(record)}")
        for purpose, to in recipients(found, word):
            sent = send(conn, part, agent=part["agent"], to=to, purpose=purpose, body=body,
                        assignment=f"A-{found['assignment']}",
                        key=f"event:{event.get('id')}:{to}")
            lines.append(f"event {event.get('id')} DI-{found['id']} {word} "
                         f"{purpose} {to} {sent.get('message')}")
    if events:
        # Acked by count from the unmoved cursor: the same events the
        # batch read, never one that arrived after it.
        acked = json.loads(monitor(program, config, state, "digest", "--consumer", consumer,
                                   "--limit", str(len(events)), "--ack"))["events"]
        if not acked or acked[-1].get("id") != events[-1].get("id"):
            refuse("store", f"the ack to end at event {events[-1].get('id')}",
                   f"it ended at {acked[-1].get('id') if acked else 'none'}",
                   "another consumer moved this cursor; give each router its own consumer")
    return lines


def do_route(rest) -> int:
    consumer, once, tick = None, False, 5.0
    index = 0
    while index < len(rest):
        word = rest[index]
        if word == "--once":
            once = True
            index += 1
        elif word in ("--consumer", "--tick") and index + 1 < len(rest):
            if word == "--consumer":
                consumer = rest[index + 1]
            else:
                try:
                    tick = float(rest[index + 1])
                except ValueError:
                    tick = 0.0
                if tick <= 0:
                    refuse("arguments", "--tick in seconds above zero", rest[index + 1],
                           "pass --tick N")
            index += 2
        else:
            refuse("arguments", usage(), word, usage())
    if not consumer or "/" in consumer or not consumer.isprintable():
        refuse("arguments", "--consumer naming this router's own cursor", consumer or "none",
               "pass --consumer dispatch")
    identity()
    while True:
        for line in one_pass(consumer):
            print(line, flush=True)
        if once:
            return EXIT_DONE
        time.sleep(tick)


def main(argv: list[str]) -> int:
    try:
        if argv[:1] != ["route"]:
            refuse("arguments", "the verb route", argv[0] if argv else "none", usage())
        return do_route(argv[1:])
    except Refusal as refusal:
        return emit(refusal)
    except sqlite3.DatabaseError as error:
        return emit(Refusal("store", f"a usable store at {intents.machine.store_path()}",
                            f"{type(error).__name__}: {error}",
                            "the batch stays unacked; run the pass again once the store is free"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
