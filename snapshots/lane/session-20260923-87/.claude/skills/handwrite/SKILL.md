---
name: handwrite
description: The exact command shape for any write under a hand grant - the grant id as the first token of the whole command, absolute paths, no cd, a scratchpad script for edits, git -C for git, a wall grant for wall paths. Use before the first write of any hand-granted work and the moment hand-write or wall-write refuses.
---

# handwrite — the grant leads the command

Why it exists, measured (`skills.py report`, 2026-09-13): 28 hand-write
refusals in three days, none a lane defect; pitfall 27 named the shape
on 2026-09-13 and two more sessions met it the same day. The guard
judges the command text before it runs: a grant it cannot see is a
grant that does not exist.

## The shape

1. **Declare once, at the session's start, unscoped.** The owner's word
   at the start, or the Lead's word on the owner's delegation, is the
   grant (owner 2026-09-23: "i just want to give you the power to declare hand grants as needed for dev-lane work"). The owner
   types nothing, and a later write needs no fresh word:
   `python3 ops/conductor/tools/hand.py declare '<what>' 'owner <date>, relayed by <who>: <the ruling>' other --ttl 1440`.
   Words the owner gave this session directly read
   `'owner <date>: "<the words>"'`. The two classes: `other` for every
   write outside the wall; `wall` for `.github/workflows/`,
   `ops/bin/suites.sh`, `probes.py`, `laneconf.py`, `boundaries.json`,
   `matrix.py`, `engine.py`, `ops/devlane/hooks/tests/`. A wall grant may
   not write a non-wall path and a non-wall grant may not write a wall
   path. A wall session's one declaration covers both classes (owner
   2026-09-23); hand.py at 2df477aa takes one class per declaration, so
   until it takes both, a wall session declares one of each at its start
   and leads each command with the right one.
2. **The id is the first token of the whole command.**
   `HAND_GRANT=<id> python3 /abs/path/script.py` passes;
   `cd <wt> && HAND_GRANT=<id> git ...` refuses (pitfall 27);
   `export HAND_GRANT=<id>; ...` refuses. No `cd`: use `git -C <wt>`
   and absolute paths.
3. **Edit through a script in the scratchpad.** The Write and Edit
   tools cannot carry a grant. Put the edit in `<scratchpad>/edit.py`,
   assert the anchor count is exactly one before replacing (the
   unguarded-replace row), and run `HAND_GRANT=<id> python3 <scratchpad>/edit.py`.
   A heredoc whose prose quotes a guarded verb is read as that verb by
   the deliverable and trunk-commit rows (LD-35, pitfall 27); a script
   file is not scanned.
4. **Stage and commit in two calls, id leading each:**
   `HAND_GRANT=<id> git -C <wt> add <paths>` then
   `HAND_GRANT=<id> git -C <wt> commit -F <scratchpad>/msg.txt`.
   The message names the grant and says the second producer is absent.
   Push the same way.
5. **Settle at close, with a bare sha.** `hand.py settle <id> --evidence <sha>
   --note '<words>'`; prose in `--evidence` reads back "claimed;
   unverified" and cannot be re-settled (pitfall 32).
6. **Two calls for edit-then-create.** A chain of "edit the body, then
   `gh pr create`" is judged on the body as it was before the edit.

## What the guard resolves and what it cannot

A literal path, `Path('...')`, or a script whose target is spelled in
its text resolves. A path built at run time does not; it needs an open
grant of any scope, and the refusal says so. `git checkout -- <file>`
is a write to that file and needs the id too.

Record the use: `python3 ops/conductor/tools/skills.py log-use handwrite "<grant id>"`
with `WF_AGENT` set.
