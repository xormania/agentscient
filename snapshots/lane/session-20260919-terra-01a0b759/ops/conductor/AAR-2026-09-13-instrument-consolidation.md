# AAR — 2026-09-13, the instrument consolidation: one shared module, eleven tools

Session record by Claude Fable 5.1. Measured at write time against dev
after merge #176 (`92d28d13`), which follows merge #174 (`d0778d21`)
and merge #175 (`lane/session-20260912-n`, another session). The
[handoff](handoff/HANDOFF-2026-09-13-instrument-consolidation.md)
carries state and the next thread. The session before this one is
[AAR-2026-09-13-test-census.md](AAR-2026-09-13-test-census.md).

## Request and outcome

The owner asked, in order: "i have a second claude session working on
tests and ci consolidation - i want to do something similar -
consolidate code dulications in the system itself - thoughts?";
"agreed - hand grant ok'd for #1, #2, #3, and #4"; "174 is green -
merge it- continue"; "be careful about token use - other claude session
found some issues - try to avoid"; "merge it - then create AAR and
handoff - new session is needed because of PR 175".

Outcome, all on dev, every merge through the checks on its head:

| PR | merge | what |
|---|---|---|
| #174 | `d0778d21` | the census record and script; `ops/conductor/tools/instrument.py` with its tests, registry row and conventions section; ten tools migrated (hand, deliverable, findings, land, decisions, ci, branches, onboard, watch, correction); the handoff, LD-29 and four corpus rows |
| #176 | `92d28d13` | watchdog migrated; the handoff updated |

The four steps the owner agreed were: the census as a record before any
change; one additive shared module; one tool per commit with the gate
red before and the suites after; the subprocess policies left at the
callers. All four were done as stated. Ten tools remain and each is
named in `PENDING` with its reason in the handoff.

## What was measured, and what it showed

- The census at `729f50a9` (`ops/conductor/reports/duplication-census.py`):
  18 files defining `refuse` with four behaviours, 12 defining
  `identity` with four regexes, 8 lane-name or conf readers each with a
  fallback parser, 11 clocks, 12 subprocess runners, 8 shell refusal
  helpers, 24 literal wire lines in the dispatch wrapper. After the
  eleven migrations: `refuse` 9 files (one the module), `identity` 6
  (one the module, one an inode helper), `lane_name` 1, conductor tools
  spelling the wire literally 3.
- Every migration commit: the gate failed 1 naming the tool's copies,
  then Ran 32 tests OK, and the tool's suites OK with the same command.
  `ops/bin/suites.sh` at `05236586` and `ff0c108a`: every suite OK,
  conductor 1054, dispatch 618. `probes.py run` at `b2350594`: 98 pass.
- Three couplings the definition census could not see were each found
  by a suite: the launcher loading correction.py, which loads
  findings.py (import route, `e71dd866`); correction.py reading
  `FINDINGS.lane_name()` (conformance gate, `e13f24c0`); launch.py
  catching `CORRECTION.Refused` and a dispatch test asserting it
  (`05236586`).
- `laneconf.py literals` refused a lane-name default in the module at
  two lines; the four tools that had carried that default were on the
  reader's deferred list. The module carries no literal, and each
  migrated tool leaves the deferred list by construction.

## What was decided and why

- **A shared module beside the tools, not a package.** The tools are
  standalone scripts and their suites stage byte copies of them; a
  module found beside the tool's own file works for the script, for a
  by-path load from another tool, and for a staged copy with its
  siblings staged. A working-directory route was tried first and
  failed two ways in the dispatch suite (36 failures at `e13f24c0`).
- **The reader is strict.** No lane name stands in for an absent conf;
  a staged copy names its conf through `LANE_CONF`. This is the wire's
  own rule (refuse rather than guess) and the literal scanner's, and
  it cost one fixture line in each of eleven suites.
- **The gate names every tool.** `MIGRATED` or `PENDING`, nothing
  unplaced; a migration is red until the copies are gone, and a new
  tool cannot appear without being placed. This is the verified
  coupling the census asked for, and the census script stays for the
  next reading.
- **Policies stayed at the callers.** onboard's absence-returning
  runner, watchdog's bounded capture and its tolerant stamp read kept
  their behaviour under their own names.

## What went wrong

- The first import route read `os.getcwd()`, which raises when a test
  has removed its own directory (LD-25 class) and misses the tools
  from any other directory; the launcher broke from /tmp. Caught by
  the full suite run, not by the tool suites. Rule kept: run the
  dispatch suite with the conductor suite for any tool the launcher
  loads by path.
- `suites.sh` on the session branch wrote a merge commit from dev onto
  it (`582c4247`) and refused `stale-base` when the worktree was dirty:
  the wrapper suite runs the real dispatcher against the checkout it
  lives in. LD-29, not repaired.
- Four commit messages and one PR body were refused by the claim hook
  for "settled", "holds" and "green" without a reading in the same
  paragraph. Each rewrite put the `Ran N tests` beside the claim; the
  hook did what it says.
- Token use: the session read tool bodies and fixtures one tool at a
  time and ran suites more than once per tool while finding the import
  route; the owner asked for care mid-session. The last two
  migrations used one script per tool and one suite run each.

## Calibration

Stated and held: red then green with one command per commit; every
merge on green checks on its head; findings met on the way to the
ledger, not to branches (LD-29; the vendored isolation copy and the
receipt wire declared in the census record). Stated and corrected
in-session: the hand.py commit added a lane-name default the findings
commit removed. Not measured: the term wall locally (pattern not on
this host; CI read it); the bodies of the eight shell helpers.

The next session starts after #175 changed the onboard brief, the
graft-first rule and the plan defaults; onboard first, then the handoff.
