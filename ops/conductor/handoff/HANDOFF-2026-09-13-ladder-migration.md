# Handoff — 2026-09-13, after the ladder migration

Record by Claude Fable 5.1 on `lane/session-20260913-a`, written at
`ba4ad806` and committed in the records commit that follows it. The
owner's words that opened the work, after this session reported the
instrument-consolidation handoff's next thread: "do it - hand grant
ok'd" (2026-09-13). Onboarded fresh first, as that handoff required
(`onboard.py` at `cb716534`: brief complete, exit 0). The
[AAR](../AAR-2026-09-13-ladder-migration.md) carries the readings.
Re-measure before acting.

## Where things stand

- PR #181, draft, `lane/session-20260913-a` into dev, head `ba4ad806`
  at write time, `mergeable: MERGEABLE`. Checks at write time: app
  pass; lane, Analyze (actions) and Analyze (javascript-typescript)
  pending. The head moves to the records commit after this file; the
  checks on that head were not read by this session. Ready waits on
  the full check set green on the final head and the proof gate (the
  four `P-LADDER-20260913-*` rows are named under `## Proof`).
- Worktree `../wt/ag-session-20260913-a`: uncommitted 0, unpushed 0 at
  `ba4ad806` (`git status --short | wc -l`; `git log @{u}..HEAD`); the
  records commit is pushed with this file.
- Commits on the branch: `fef8b1cd` (the migration), `eeef6fc9` (four
  corpus rows, pitfalls 28 and 29, the deliverable skill page), and
  `ba4ad806`, a merge of `origin/dev` at `37750dd0` (#179) written by
  the dispatch wrapper while the first `suites.sh` ran (LD-29).
  After the records commit `0a38531d`, #180 (`23a30592`) landed on dev
  and #181 read CONFLICTING on `lane-defects.md` (LD-34 from that
  branch and LD-35 from this one, both after LD-33); the merge of
  `origin/dev` at `23a30592` that follows this commit keeps both, LD-34
  first, under a grant of its own. The checks on that head were not
  read by this session.
- Grant 187 (`other`, unscoped, "migrate ladder.py onto instrument.py;
  the session records"): settled with the records commit's sha after
  this file is committed. Grants 185 (`lane/session-20260912-n`), 189
  and 190 (`lane/session-20260913-c`, PR #180) are other sessions'.
- The deliverable lock names `lane/session-20260912-n`,
  `lane/session-20260913-a`, `lane/session-20260913-b` and
  `lane/session-20260913-c`. This session's entry stays until #181
  lands; the lever has no remove verb (LD-28), so the next session
  `set`s the branches still open with their own words.
- Findings: 7 rows open on record `20260913T023636Z-review-codex-bdbe55`
  (sqlite, `disposition='open'`), a review dispatched before this
  session began; not this session's to dispose, named here.
  `findings.py export --write` at `ba4ad806` wrote 807 rows and left
  the tree unchanged.
- Dispatches: none running (`subs.py`: no dispatch snapshots; the
  onboard brief: running=none).
- Ladders: none run or resumed.

## What landed on the branch

`ladder.py` imports `instrument.py` beside it: `IDENTITY`, `now`,
`refuse`, `Refusal as Refused`, `conf as conf_value`. Gone: its own
`Refused` class, `refuse()`, identity regex, `_load_laneconf` with the
cwd candidate, `conf_value`, and the `importlib`, `datetime` and
`ModuleType` imports that served only them. `configuration()` reads
its four keys through the shared `conf()`. `utc_stamp()` and the
record-id suffix take their time from `now()`. `test_ladder_lever.py`
stages `instrument.py` and `laneconf.py` beside its staged copy of the
driver. `ladder.py` moved from `PENDING` to `MIGRATED` in
`test_instrument.py`; nine tools remain in `PENDING`.

Kept in `ladder.py` on purpose: `run()` and `git()` with the driver's
argument order, `utc_stamp()`, `full_identity()`. The gate names none
as a copy; `run()`'s signature differs from the shared one and every
call site would move.

## Corrections to retain

- **The lock names the branch before the worktree is cut.** The
  deliverable hook refuses `git worktree add -b` of a session branch
  the lock does not name; the skill page said the reverse and is
  corrected in `eeef6fc9` (pitfall 29).
- **The grant id is the first token of the whole command, and a hook
  judges the command before it runs.** `HAND_GRANT=187 python3
  <script>` with absolute paths; `cd <wt> && git add … && HAND_GRANT=187
  git …` for the commit (pitfall 27 stands). An "edit the body, then
  `gh pr create`" chain is judged on the body as it is before the edit;
  two calls.
- **The deliverable hook reads prose.** A heredoc whose text quoted the
  worktree command to correct the skill page was refused as new work
  (LD-35). Edit records through a script file in the scratchpad.
- **`evgrep.sh` is basic-regex grep.** A `\|` alternation is a literal
  bar and its zero count is a false absence; three such zeros this
  session before the shape was noticed (pitfall 28). One pattern per
  call; `grep -c -E` for the verdict on an alternation.
- **`suites.sh` on a session branch behind dev writes a merge and reads
  red.** The first run at `eeef6fc9` produced `ba4ad806` mid-suite and
  three guards (fixtures 1, conductor 2) reported the HEAD move, LD-29
  again; the second run at `ba4ad806` was clean. Run it twice when dev
  has moved, or merge dev forward by hand first and read `git log`.

## Next thread

Nine tools remain in `PENDING`. `laneconf.py` and `probes.py` are wall
files for a wall session. `monitor.py` and the `lane_read.py` family
(`lane_mcp.py`, `lane_refs.py`) base their refusal class on ValueError
and need the per-site reading the instrument-consolidation handoff
describes before any commit. `skills.py`, `co_doc.py` and `control.py`
wait on the owner's ruling about adopting the wire. The cheapest next
commit is `monitor.py` alone: one tool, the gate red first, its suites
and the dispatch suite after, with each `except ValueError` site read
for which handler now sees the refusal.
