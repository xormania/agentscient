# I-034 — the state engine's holder is an agent string, not an actor

- recorded: 2026-09-16, session agentscient-c (Claude Opus 5 (1M context),
  lane/session-20260916-c), while building the coordination core
- source: measured, while building package B; ruled out of that deliverable
  by the Lead session the same day: "Write an idea file for widening
  subjects.holder later; it is not this deliverable"
- disposition: open; nothing is proposed to the register yet

## What is measured

`machine.py` holds one column for who holds a subject, `subjects.holder`,
and `_check_actor` compares it to the agent identity string the caller
passes:

    ops/conductor/tools/machine.py:254    if t.actor == "any" or row["holder"] == agent:

The agent string comes from `instrument.identity()`, which falls through
to `WF_AGENT`. `.claude/settings.local.json` binds one `WF_AGENT` value
for every session on this host. Three sessions of the same model
therefore satisfy each other's `holder` and `holder-or-lapsed` checks:
the engine cannot tell them apart, because on its own reading they are
the same actor.

## What package B did instead, and why it is not the fix

`coordination.py` keys a participant on the harness session id and
checks that participant inside every verb, passing the engine's `gate`
callback, which runs under the write lock before the UPDATE. The agent
string stays as attribution. That closes the hole for coordination
subjects and leaves `machine.py` untouched — a deliberate boundary, not
an oversight — but every other machine on the engine still compares
agent strings: the ladder, the deliverable lock, the register, whatever
is declared next.

## What a widening would have to settle

- whether `subjects.holder` becomes an actor reference (a participant
  id, or a pair of agent string and session id), and what it does with
  the rows already written under the old meaning: a migration that
  rewrites them is inventing an actor that was never recorded, and one
  that leaves them is two meanings in one column;
- whether the actor is resolved by the engine or handed to it, which
  decides whether `machine.py` learns about participants — a coupling
  the coordination contract was careful not to create;
- what `holder-or-lapsed` means once holders are distinguishable: today
  a lapsed lease is the only way a second session gets a subject back,
  and it is evidence a reservation ran out, never proof the first
  process stopped;
- what the refusal reads. `holder: expected the holder <who>` has to
  name something the next actor can act on.

Hardens through the register as a D- row if the owner wants the engine
widened; until then this note is the record that the defect is known,
bounded to one instrument, and not repaired everywhere.
