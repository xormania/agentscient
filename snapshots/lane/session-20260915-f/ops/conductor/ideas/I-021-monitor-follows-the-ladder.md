# The monitor follows the ladder — work order after the fixture

Owner, 2026-09-11, in session, after reviewing the two unused
instruments: "#1 - agreed, #2 agreed"; then "agreed - fold the 3 ideas
in #2 WO scope". The watchdog was started long-lived the same day.

Standing: queued, scope written. It starts when the end-to-end fixture
work order (I-020) has landed, so the fixture proves it. The scope is
`.dev/ladder-inputs/scope-monitor-follows-20260911.md`; this record is
the decision and the pointer, not the scope.

## What it is

The ladder driver registers each stage's record id with the monitor as
it mints it, so the queue follows a ladder without a hand-written
config; the digest gives the conductor one of three words per event;
the launcher waits on a set of records; the onboard hook probes the
session's own configuration drift from tracked values; the watchdog
starts quiet. The three session-shaped ideas come from the owner's
retired script at `deprecated/session-watch-20260904@0d5bcde`.

## Why it is after the fixture

The fixture is the only place a following monitor can be asserted end
to end against a planted ladder; this work order adds that scenario
rather than inventing a second harness.
