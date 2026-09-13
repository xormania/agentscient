# Handoff — 2026-09-13, after the instrument consolidation

Record by Claude Fable 5.1 on `lane/session-20260912-l` at `05236586`
plus the records commit that carries this file. The census that
started the work is `../reports/duplication-census-20260912.md`.
Re-measure before acting.

## Where things stand

- PR #174, draft, `lane/session-20260912-l` into dev, head `05236586`
  before the records commit; checks not yet read at the time of
  writing (the PR was opened minutes before this record). The release
  after it carries the shared module.
- `ops/bin/suites.sh` at `05236586` on the clean worktree: dispatch
  Ran 618 OK; harness 155 OK; task 351 OK; telemetry 227 OK; hooks 280
  OK; fixtures 221 OK (skipped=6); workflow 48 OK; conductor Ran 1054
  OK; pr-overview 8 OK. `probes.py run` at `05236586`: pass 93, fail 0,
  unreachable 0, before the rows this record adds.
- Grant 176 (this session, unscoped, 480 min) is settled with this
  record's sha as evidence when it lands; 178 and 179 belong to the
  sessions on `lane/session-20260912-n`.
- The deliverable lock names `lane/session-20260912-l`, `-n` and `-o`;
  this session's entry stays until #174 lands on dev, and LD-28 says
  why it cannot be removed alone.
- Worktree `../wt/ag-session-20260912-l`, branch pushed; the branch
  carries fourteen commits of this session and one merge from dev
  (`582c4247`) written by the dispatch wrapper while the conductor
  suite ran, LD-29.

## What landed on the branch

Ten of twenty-one conductor tools import `instrument.py`: hand,
deliverable, findings, land, decisions, ci, branches, onboard, watch,
correction. Eleven are named in `PENDING` in
`ops/conductor/tests/test_instrument.py`, and the gate refuses a tool
named in neither list:

- `laneconf.py` and `probes.py` are wall files (owner, 2026-09-12: the
  wall is changed only in isolation); a wall session migrates them.
- `watchdog.py` (1331 lines), `monitor.py` (1377), `ladder.py` (2271)
  and `lane_read.py` (2060, with `lane_mcp.py` and `lane_refs.py`
  importing its `Refusal` and `refuse`) each need their own commit;
  watchdog's in-loop refusals exit the process today and would be
  caught by the tick's own `except Exception` once they raise, which
  is a behaviour change to decide, not to slip in.
- `co_doc.py` reports through a Report object, `control.py` refuses
  through `need()`, and `skills.py` predates the wire; each is a shape
  change, not a copy removal.

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

The next tool is `watchdog.py` or `monitor.py`, one per commit, with
the gate red first (add the name to `MIGRATED`), the tool's suites and
the dispatch suite after, and the behaviour question above decided in
the commit body. `lane_read.py` goes with `lane_mcp.py` and
`lane_refs.py` in one commit, since they import its refusal class.
