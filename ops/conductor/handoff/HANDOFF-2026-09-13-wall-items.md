# Handoff — 2026-09-13, after the two wall items

Record by Claude Fable 5.1 on `lane/session-20260913-k`, written at
`2f21512f`. The board, PRs and grants are re-measured by `onboard.py`,
not taken from here. The [AAR](../AAR-2026-09-13-wall-items.md) carries
the readings.

## Where things stand

- Commits on the branch over dev `eaf73b98` (#192): `2f21512f`, the two
  wall items (grant 206, class wall); then the records commit carrying
  this file, the AAR and four corpus rows (grant 207).
- PR: opened as a draft from this branch after the records commit; its
  number, head and checks are in the ready note and `gh pr list`, not
  here. Ready waits on the full check set green on the final head,
  merge state clean, `suites.sh` on that head, and `## Proof` naming the
  `P-WALLITEMS-20260913-*` rows. The owner merges (#192 was merged by
  the owner).
- Grants 206 and 207: settled with a bare sha after the records commit
  (pitfall 32).
- The lock names `lane/session-20260913-i` (session -i lifts it once
  #192's close is done) and `lane/session-20260913-k`; this one is
  removed with `deliverable.py remove` once the PR lands on dev.
- Worktree `../wt/ag-session-20260913-k`.
- Dispatches: none run. Ladders: none. Findings: none produced.

## The wall items, closed

- An `expect` that spans lines refuses class `corpus`
  (`ops/conductor/tools/probes.py`, `ops/conductor/probes-lever.md`).
  A row pins membership, one line; pitfall 30 is now mechanical.
- The deliverable hook's remedy names `deliverable.py add <branch>` and
  `remove`, never `clear` (`ops/devlane/hooks/claude/matrix.py`).

Nothing of the wall stays open from session -h's list. Left as found,
not wall and not this session's: `deliverable.py`'s usage line lists
`clear` (the verb exists, for a host with one session).

## Second thread: the four rulings (grants 210, 211)

- Commits over dev `268065a3` (#194): `9950d14d` (skills.py, co_doc.py,
  control.py on the wire; grant 210) and `2bd810e2` (suites.sh runs ruff;
  test_miss_log.py and test_skill_use.py stage instrument.py and
  laneconf.py beside their copied lever; grant 211, wall); then the
  records commit with this section, the AAR's second thread, seven
  corpus rows and the conventions page sentence.
- PR: a draft from this branch after the records commit; number, head
  and checks in the ready note and `gh pr list`. Ready waits on the full
  check set green, merge state clean, `suites.sh` on the head, and
  `## Proof` naming the `P-WIRE-20260913-*` rows. The owner merges.
- The consolidation gate: 22 migrated, 1 no-wire, 0 pending. Nothing of
  the instrument consolidation is left.
- What a caller sees differently: `skills.py` refuses at exit 2 with one
  line (was exit 1 and a sentence); its store honours XDG_STATE_HOME;
  `co_doc.py --anything` refuses `arguments` on the wire (was a usage
  line); `control.py` refusals lead with `arguments`, `identity`, `plan`,
  `json`, `binding`, `state`, `admission` or `seat` (was `control` for
  all); `suites.sh` prints `== ruff` first and is not OK on a lint fault
  or without ruff on the host.
- The `ledger.py` fetch before minting was already in place (its
  `trunk_ref`, line 89); the previous handoff's line saying it was not
  done was stale.

## Next thread

The test kit plan reading with the owner (record
`20260913T034513Z-plan-claude-892490`; ruling 5 in this session's
explain: approve slices 1 and 2, rule on the kit as wall before slice 5,
import the six findings, dispose the seven census rows with the plan as
citation). The other session's handoff names the first hook-written
skill use once a checkout at or past `268065a3` runs a session, and the
miss-count baseline its three pages are measured against.

## Retrieval

```sh
git show dev:ops/conductor/handoff/HANDOFF-2026-09-13-wall-items.md
gh pr list --state all --head lane/session-20260913-k --json number,state,mergeCommit
python3 -m unittest discover -s ops/conductor/tests -p test_instrument.py
python3 ops/conductor/tools/probes.py run
python3 ops/conductor/tools/hand.py open
```

Left behind on purpose: the session transcript and the scratchpad.
