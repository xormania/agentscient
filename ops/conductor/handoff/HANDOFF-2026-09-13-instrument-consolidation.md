# Handoff — 2026-09-13, after the instrument consolidation

Record by Claude Fable 5.1 on `lane/session-20260912-l`, first at
`05236586` (PR #174), updated at `ff0c108a` (PR #176) and closed with
the [AAR](../AAR-2026-09-13-instrument-consolidation.md) after both
merged. Owner, 2026-09-13: "new session is needed because of PR 175":
#175 (`lane/session-20260912-n`) changed the onboard brief, the
graft-first rule and the plan defaults under this session; the next
session onboards fresh before it reads this. The census that
started the work is `../reports/duplication-census-20260912.md`.
Re-measure before acting.

## Where things stand

- PR #174 merged into dev at `d0778d21` (owner, 2026-09-13: "174 is
  green - merge it- continue"), all five checks passing on its head
  `7702e70f`. PR #176 (watchdog, head `b2350594`) merged into dev at
  `92d28d13`, all five checks passing. The release after them carries
  the shared module.
- `ops/bin/suites.sh` at `05236586` and again at `ff0c108a` on the
  clean worktree: dispatch Ran 618 OK; harness 155 OK; task 351 OK;
  telemetry 227 OK; hooks 280 OK; fixtures 221 OK (skipped=6); workflow
  48 OK; conductor Ran 1054 OK; pr-overview 8 OK. `probes.py run` at
  `360ee046`: pass 97, fail 0, unreachable 0.
- Grants 176 and 184 settled verified (`360ee046`, `b2350594`); the
  records grant that carries this file and the AAR is settled with
  their commit. 178 and 179 belonged to `lane/session-20260912-n`.
- The deliverable lock: this session's entry is dropped by `set`
  naming the other branches with their own words once the records PR
  lands (LD-28, no remove verb); the lock's `by` and `at` then read as
  this session's, as the census session's did.
- Worktree `../wt/ag-session-20260912-l`, branch pushed; the branch
  carried fourteen commits of this session and one merge from dev
  (`582c4247`) written by the dispatch wrapper while the conductor
  suite ran, LD-29, into #174; the owner merged dev into it once more
  (`7702e70f`) before the merge.

## What landed on the branch

Eleven of twenty-one conductor tools import `instrument.py`: hand,
deliverable, findings, land, decisions, ci, branches, onboard, watch,
correction, and watchdog (`ff0c108a`, after #174 merged at `d0778d21`;
owner, 2026-09-13: "174 is green - merge it- continue", grant 184).
Ten are named in `PENDING` in
`ops/conductor/tests/test_instrument.py`, and the gate refuses a tool
named in neither list:

- `laneconf.py` and `probes.py` are wall files (owner, 2026-09-12: the
  wall is changed only in isolation); a wall session migrates them.
- `monitor.py` (1377 lines) and `lane_read.py` (2060, with `lane_mcp.py`
  and `lane_refs.py` importing its `Refusal` and `refuse`) base their
  refusal class on ValueError, and lane_read has nine `except
  ValueError` sites; moving them onto the shared Exception-based class
  changes which handler sees a refusal at each site, a reading per
  site before a commit, not a copy removal. `ladder.py` (2271) reads
  `error.kind` on its `Refused` in two places and needs its own commit.
- `co_doc.py` reports through a Report object, `control.py` refuses
  through `need()`, and `skills.py` predates the wire (`sys.exit` with a
  "refusing:" sentence, exit 1); each is a shape change the owner
  rules on, not a copy removal.

The census after ten migrations (`python3
ops/conductor/reports/duplication-census.py ops` at `05236586`): files
defining `refuse` 18 to 9 (one is instrument.py), `identity` 12 to 6
(one is instrument.py; lane_refs's is an inode pair, not a copy),
`lane_name` 5 to 1, conductor tools spelling the wire literally 12 to
3 (control, watchdog, probes). The eight shell helpers, the vendored
isolation copy (163 lines from the harness module) and the receipt
engine's exit 1 on a refusal are untouched and declared in the census
record.

## Corrections to retain

- **A tool finds the shared module beside its own file**, never under
  the working directory (`e71dd866`): the launcher loads correction.py
  by path, which loads findings.py by path, and `os.getcwd()` raised
  from a test whose directory had been removed.
- **A suite that stages a copy of a tool stages `instrument.py` and
  `laneconf.py` beside it and names a conf through `LANE_CONF`.**
  Eleven suites do, one line each; the list is in the commit bodies.
  The shared reader stands in no lane name for an absent conf, and
  `laneconf.py literals` refuses the literal in the module
  (`e13f24c0`).
- **The definition census misses dynamic couplings.** Three were
  caught by suites, not by the census: correction.py reading
  `FINDINGS.lane_name()`, launch.py catching `CORRECTION.Refused`, and
  a dispatch test asserting that class name. Before migrating a tool,
  read who loads it by path (`importlib.util.spec_from_file_location`
  in the tools and in `ops/devlane/dispatch/launch.py`) and run the
  dispatch suite as well as the conductor suite.
- **Do not run `suites.sh` on a dirty session worktree, and know that
  a clean run writes a merge from dev onto the branch** (LD-29). Commit
  first; read the merge in `git log` before writing the PR body.
- **The claim hook reads commit messages and PR bodies**: the words
  "holds", "settled here", "green" in a paragraph without a reading
  refuse the commit; put the `Ran N tests` beside the sentence.

## Next thread

The next tool is `ladder.py`, one commit, with the gate red first (add
the name to `MIGRATED`), its ladder suites and the dispatch suite
after. `monitor.py` and the `lane_read.py` family wait on the
ValueError reading above; `skills.py`, `co_doc.py` and `control.py`
wait on a ruling about adopting the wire.
