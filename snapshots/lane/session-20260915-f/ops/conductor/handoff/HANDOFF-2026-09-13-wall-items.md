# Handoff — 2026-09-13, after the two wall items

Record on `lane/session-20260913-k` by Claude Fable 5.1, written at
`2f21512f`, and closed by Claude Opus 5 (1M context) on 2026-09-14 after
#196 merged at `bdf8cf0c`. The board, PRs and grants are re-measured by `onboard.py`,
not taken from here. The [AAR](../AAR-2026-09-13-wall-items.md) carries
the readings.

## Where things stand

- Commits on the branch over dev `eaf73b98` (#192): `2f21512f`, the two
  wall items (grant 206, class wall); then the records commit carrying
  this file, the AAR and four corpus rows (grant 207).
- PR #193, merged by the owner at `25b48ed5`.
- Grants 206 and 207: settled with a bare sha after the records commit
  (pitfall 32).
- The lock: see §Close.
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
  corpus rows and the conventions page sentence; then the fix commit
  (grant 213) after `suites.sh` read red at `a20ffde9`:
  `test_skills_registry.py` stages instrument.py, laneconf.py and a
  lane conf beside its copy, and the four fixture app tests write the
  lane contract as a nested `ops/ruff.toml` in their scratch.
- PR #196, merged into dev at `bdf8cf0c` by this session at the owner's
  word ("as soon as CI green - merge to dev"; "finish PR 196", "its
  yours"), head `5ea006ac`, ci run 34752566609 and CodeQL passing. Two
  records commits (`2a0b7e0a`, `5ea006ac`) moved the head after GitHub's
  outage stalled CI and CodeQL; the AAR carries the readings.
- After #196, `skills.py` redacts secret-shaped event details before the
  store (`06240f98`, #198, a fix from the release review); its refusal
  wire is as #196 left it.
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

## Close, measured 2026-09-14T00:16Z

- PRs: #193 at `25b48ed5`, #196 at `bdf8cf0c`; the release #197 (dev into
  master) at `d3a9e8a6`; dev at `8acab9aa` (#199). Open: dependabot #200
  only, not this session's.
- Grants 206, 207, 210, 211, 213, 215, 216 settled and verified; 219 open
  for the close records, settled against their commit.
- The lock names `lane/session-20260913-k` alone, re-added for the close
  records; `deliverable.py remove lane/session-20260913-k` once their PR
  reaches dev (not measured at this writing).
- Worktree `../wt/ag-session-20260913-k`. Dispatches and ladders: none.
  Findings: 7 open on `20260913T023636Z-review-codex-bdbe55`, from before
  this session.

## Next thread

- The test kit plan reading with the owner (record
  `20260913T034513Z-plan-claude-892490`; ruling 5 in this session's
  explain: approve slices 1 and 2, rule on the kit as wall before slice
  5, import the six findings, dispose the seven census rows with the
  plan as citation).
- The four rulings had no reviewer. Two questions from #196's body wait
  on one: whether `state` is the right default class for control.py's
  `need()` at every site that names none, and whether co_doc.py's report
  at exit 2 on stdout is the next wire ruling.
- The release review session's handoff
  (`HANDOFF-2026-09-13-release-review.md`) carries its own open items.

## Retrieval

```sh
git show dev:ops/conductor/handoff/HANDOFF-2026-09-13-wall-items.md
gh pr list --state all --head lane/session-20260913-k --json number,state,mergeCommit
cat ops/conductor/handoff/pitfalls/34.md
python3 -m unittest discover -s ops/conductor/tests -p test_instrument.py
python3 ops/conductor/tools/probes.py run
python3 ops/conductor/tools/hand.py open
```

Left behind on purpose: the session transcript and the scratchpad.
