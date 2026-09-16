---
name: deliverable
description: Name the deliverable and lock it before the first command; check the board for another owner of the same work; route every finding met on the way to a ledger row, never a branch; close it with the close skill and clear the lock. Use at the start of any task and at every finding met while one is open.
---

# deliverable — one named thing at a time, findings to the ledger

Why it exists, measured: on 2026-09-11 the conductor turned every
finding into a work stream ahead of the deliverable, six repairs, six
regression dispatches, a hook row and a proactive read, and the owner
said the same thing about twelve times before the lock was built
(owner, 2026-09-11: "i want an immediate FIX to stop that"). On
2026-09-10 two sessions implemented the same repair with no declared
owner (#79 and #83), a repair loop ran with no overall stop condition
until the owner supplied one, and reviews were dispatched before
direction arrived. The lock refuses the drift mechanically; this page
is what a session does so the refusal never fires.

## At the start

1. **The board.** Who else holds this work:

   ```sh
   ops/bin/board.sh
   gh pr list --state open --json number,headRefName,title
   ```

   A branch or PR already carrying the same repair means this session
   reads it, and does not start a second one.

2. **The lock, then the session branch.** One branch per session
   (owner, 2026-09-12): name `lane/session-<date>-<id>` in the lock
   beside any other session's, then cut it from `origin/dev` in its own
   worktree. The hook refuses the worktree add of a branch the lock
   does not yet name (pitfall 29, 2026-09-13):

   ```sh
   python3 ops/conductor/tools/deliverable.py add lane/session-<date>-<id> --why '<the owner's words, dated>'
   git worktree add ../wt/ag-session-<date>-<id> -b lane/session-<date>-<id> origin/dev
   ```

   Every change and record of the session commits there; the dispatcher
   merges `dev` forward before each launch. The lock, before any other
   branch this session needs:

   When the owner says "hand grant" or "get it done", declare it at once,
   unscoped, with a lifetime that covers the work, and lead every write
   with its id; the owner never runs the lever:

   ```sh
   python3 ops/conductor/tools/hand.py declare '<what>' 'owner <date>: <the words>' other --ttl 480
   ```

   ```sh
   python3 ops/conductor/tools/deliverable.py set <branch>... --why '<the owner's words, dated>'
   ```

   Several branches may be named for parallel work; unnamed work
   refuses. `show` reads it.

   **The target** (owner, 2026-09-15, on a session that reported a
   plan's slices all done with 210 of 226 test modules still off the
   kit: "whatever it says - is the problem we to solve - right fucking
   now"): when the owner's order is a measurable state of the tree,
   the lock carries it as a measure command and the text its output
   must carry, on the same `add` or `set`:

   ```sh
   python3 ops/conductor/tools/deliverable.py add <branch> --why '<the words>' \
       --measure '<command that prints the reading>' --until '<the text the reading must carry>'
   ```

   `show` runs the measure and prints `met` or `short` beside the
   target every time the lock is read; a measure that cannot run reads
   `unreachable`, never met. A plan's slices are how the target is
   reached, never the target: a plan that names a later item still
   leaves the target short.

   **Shown before the first command** (owner, 2026-09-15: the target is
   only as good as the measure the session writes from the words; row
   P-DONEGATE-20260915-shown-line): before any work, the session says
   one line to the owner, with the until text and the live reading from
   `show` in it, in this shape:

       I will count this done when <until>; it reads <reading> now.

   A target the owner has not seen is the session's paraphrase.

   **Then the owner types `/goal`** (row P-DONEGATE-20260915-goal-line).
   Claude Code judges a typed condition after every turn with a separate
   small model and keeps the session working until the judge reads it
   met (`code.claude.com/docs/en/goal`, read 2026-09-15 on 2.1.272). A
   session cannot type it for itself, so the line above ends by asking
   for it, in this shape:

       /goal deliverable.py done <branch> prints done; paste the reading every turn

   The judge reads the conversation and runs nothing, so the session
   runs `deliverable.py done <branch>` and pastes its line every turn;
   while short, the refusal line with the reading is the status. The
   standing form of the same check is the prompt-based Stop hook in
   `.claude/settings.json` (grant 237, row P-DONEGATE-20260915-stop-prompt):
   a reply that reports the deliverable done without that line pasted is
   sent back with the reason, until the line is there.

3. **The estimate,** if one is asked for, is the measured rate from the
   records with its count, never the happy path.

## At every finding met on the way

The question is one line: is this the deliverable? If not, it goes to
its ledger and the session goes back to the deliverable:

| what was found | where it goes |
|---|---|
| a stop or refusal not caused by the change under test | a row written by `python3 ops/conductor/tools/defects.py add`, one file under `ops/conductor/handoff/lane-defects/`. It gets a `repair/` branch named into the lock only when it blocks the deliverable; otherwise the row waits. |
| a reviewer finding on the deliverable's own change | the findings ledger, imported from its record; disposed with a contract citation before any correction is dispatched. |
| a design, a lever that should exist, a bigger repair | `ops/conductor/ideas/`, or `skills.py wish <name> '<what>'` for a skill. |
| a command shape the guards refused | the `refused` skill; a class it does not list is a pitfall row: `python3 ops/conductor/tools/ledger.py add pitfalls --what-bit TEXT --do-instead TEXT`. |

A finding is evidence. It is never, while the deliverable is open, a
branch, a dispatch, a ladder start or a PR.

## At the end

The `close` skill first, then the reading, then the lift:

```sh
python3 ops/conductor/tools/deliverable.py done lane/session-<date>-<id>
python3 ops/conductor/tools/deliverable.py remove lane/session-<date>-<id>
```

`done` prints the reading when the target is met and refuses `target`
while it is short, naming the reading found; "done" in a record, a
message or a PR is that line and nothing else. `remove` refuses a
short target too, unless `--unmet '<the owner's words>'` says why the
work stops short, and prints that reason with the lift.

**One deliverable per session, then a fresh session** (T-56, measured
2026-09-15 at dev 564ab769: two sessions spent 73% and 75% of their
input tokens on requests above 400k context, and a 400k cap would have
cost 77% and 78% of what they did). After `remove`, the session ends;
the next thread is taken by a fresh session, never by this one. The
backstop is `autoCompactWindow` in `.claude/settings.json`; the test is
the next window's `worth.py waste` mean context under 300k.

`remove` lifts this session's branches and leaves every other session's
in place; the last branch removed lifts the lock. `clear` wipes every
session's entry at once and is for a host with one session. The lock is
lifted by its lever when the work has landed on dev, never by a grant,
and never before the close measurements are pasted (owner, 2026-09-13:
"minimize parallel work conflicts"; LD-28 closed).

Record the use: `python3 ops/conductor/tools/skills.py log-use deliverable "<branches>"`
with `WF_AGENT` set.
