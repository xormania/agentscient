#!/usr/bin/env python3
"""The courier: carries queued coordination messages into a session.

    courier.py watch [--tick N] [--once]

A session arms this as a Monitor. Each pass it asks the coordination core
for its own inbox, prints one line for every message no transport has
carried yet, and records that message delivered through the core's own
verb in the same breath — so the line a session reads and the stamp the
store keeps are one event, and the tick bounds how long a message waits.

It is a transport adapter and it lives outside the core on purpose:
`coordination-lever.md:272` says "The core never sends. Transports are
adapters outside it; the core records intent and receipt." The core keeps
queued, delivered, acknowledged and resolved apart, and this closes
exactly one of those gaps. Printing a line is delivery. It is not
acknowledgment: only the recipient's own `ack` says a session read it,
and this never writes that.

The participant is this process's own, resolved by the core from the
session id in the environment. The courier names no participant and takes
none: a courier that could choose whose messages to carry could deliver
another participant's inbox into this session.
"""

import sys

sys.dont_write_bytecode = True

import time  # noqa: E402

try:
    from instrument import Refusal, refuse, stamp
except ModuleNotFoundError:
    print(
        "tooling: expected instrument.py beside this tool; found absent; "
        "needed restore ops/conductor/tools/instrument.py beside it",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

# The core's own names, settled against coordination.py at b1d868b0. The
# read is `inbox` until package B lands `undelivered`, which answers the
# same question without this filter; nothing waits on it, because a
# message already carries `delivered_at`.
CORE_TABLE = "CORE"
CORE_RESOLVE = "bound_participant"
CORE_WRITER = "writer"
INBOX_VERB = "inbox"
DELIVER_VERB = "deliver"
UNDELIVERED_VERB = "undelivered"
TICK_DEFAULT = 30
REF_PREFIX = "courier"


def core():
    """The coordination core beside this tool, or a reading that it is not."""
    try:
        import coordination
    except ModuleNotFoundError:
        refuse("state", "the coordination core beside this tool",
               "coordination.py absent",
               "land ops/conductor/tools/coordination.py, package B")
    return coordination


def verb(module, wire: str):
    """One core verb by its wire name, never by a lookup on the module."""
    table = getattr(module, CORE_TABLE, None)
    if not isinstance(table, dict):
        refuse("state", f"the core's verb table `{CORE_TABLE}`",
               "absent from coordination.py",
               "land the core's verb table, keyed by each verb's wire name")
    found = table.get(wire)
    if not callable(found):
        refuse("state", f"the core verb `{wire}`", "absent from the verb table",
               f"land the verb `{wire}` in the core's table")
    return found


def undelivered(module, conn, part) -> list:
    """Every message queued to this participant that no transport carried.

    `undelivered` when the core carries it, `inbox` filtered otherwise:
    a message names its own `delivered_at`, so the filter is a reading and
    not a guess.
    """
    table = getattr(module, CORE_TABLE, {})
    if isinstance(table, dict) and callable(table.get(UNDELIVERED_VERB)):
        rows = table[UNDELIVERED_VERB](conn, part).get("messages", [])
        return [row for row in rows if isinstance(row, dict)]
    rows = verb(module, INBOX_VERB)(conn, part).get("messages", [])
    return [row for row in rows
            if isinstance(row, dict) and row.get("delivered_at") is None]


def line(row, at: str) -> str:
    """The one line a session reads, and the only thing this prints."""
    return (f"{at} {row.get('message')} {row.get('purpose')} "
            f"from {row.get('sender')}: {row.get('body')}")


def carry(module) -> int:
    """One pass: every waiting message printed and recorded delivered.

    The store is opened for writing because recording the receipt is a
    write; the read alone would not be enough to close the gap it finds.
    """
    opener = getattr(module, CORE_WRITER, None)
    resolver = getattr(module, CORE_RESOLVE, None)
    if not callable(opener) or not callable(resolver):
        refuse("state", f"the core's `{CORE_WRITER}` and `{CORE_RESOLVE}`",
               "absent from coordination.py",
               "land the store opener and the participant resolver")
    conn = opener()
    part = resolver(conn)
    deliver = verb(module, DELIVER_VERB)
    carried = 0
    for row in undelivered(module, conn, part):
        message = row.get("message")
        if not isinstance(message, str):
            continue
        at = stamp()
        # Printed first, then recorded, which makes this at-least-once and
        # not exactly-once: a courier stopped between the two leaves a line
        # a session has seen and a store that does not know it. The next
        # pass carries it again, because the filter is `delivered_at is
        # None` — a repeated line, never a silent loss. Measured
        # 2026-09-16: a live run terminated the courier in that window and
        # the store held queued and no delivered stamp, which is the
        # property working rather than a defect. The other order would
        # record a delivery no session ever saw, and nothing would carry
        # it again.
        print(line(row, at), flush=True)
        deliver(conn, part, message=message, ref=f"{REF_PREFIX}:{at}:{message}")
        carried += 1
    return carried


def watch(tick: int, once: bool) -> int:
    module = core()
    while True:
        carry(module)
        if once:
            return 0
        time.sleep(tick)


def cli(argv: list[str]) -> tuple[int, bool]:
    if not argv or argv[0] != "watch":
        refuse("arguments", "watch [--tick N] [--once]",
               repr(argv) if argv else "no verb", "use the declared verb")
    rest, tick, once = argv[1:], TICK_DEFAULT, False
    while rest:
        if rest[0] == "--once":
            once, rest = True, rest[1:]
            continue
        if rest[0] == "--tick":
            if len(rest) < 2 or not rest[1].isdigit() or int(rest[1]) < 1:
                refuse("arguments", "--tick as whole seconds, one or more",
                       rest[1] if len(rest) > 1 else "no value",
                       "pass --tick 30")
            tick, rest = int(rest[1]), rest[2:]
            continue
        refuse("arguments", "watch [--tick N] [--once]", repr(rest[0]),
               "use the declared options")
    return tick, once


def main() -> int:
    try:
        tick, once = cli(sys.argv[1:])
        return watch(tick, once)
    except Refusal as exc:
        print(exc.line(), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
