# AAR 2026-09-23: the findings gate (#273) and the kit's daemons (#274)

Seat: agentscient-55 (Claude Opus 5.5 (1M context)), serving the XO
agentscient-87 and, through it, the Lead. Two branches:
`lane/session-20260922-376c` (#273) and `lane/session-20260923-376c-kit`
(#274), with worktrees `wt/ag-job-timeouts` and `wt/ag-kit-daemon`. The
owner's grants were typed in this session's terminal ("hand grant ok'd";
"if needed,hand grant ok'd"): 331 (wall) and 332 (other), 347 (wall),
358 (wall), 359 (other) and 364 (wall). Every time below is UTC and comes
from `gh pr view`, a dispatch record's `at` stamps or a commit.

## What landed

| PR | branch | opened | merged | merge commit | what |
|---|---|---|---|---|---|
| #273 | lane/session-20260922-376c | 01:54:07 | 03:13:27 | 2df477aa | findings carry `practical`/`failing`; the `finding-disposition` row at `gh pr ready`; D-FINDINGS-1 |
| #274 | lane/session-20260923-376c-kit | 02:17:47 | 04:50:39 | 4c375c6a | `world.daemon`, `world.adopt`, `close` stops daemons and refuses a survivor; `testkit.daemon` |

## Audits and their dispositions

| audit | record | launched | closed | findings | disposed |
|---|---|---|---|---|---|
| A-512 on #273 | 20260923T024426Z-review-codex-9ff5fe | 02:44:26 | 03:04:41 | 2 | 2 ruled (declined, XO) |
| A-528 on #274 | 20260923T030855Z-review-codex-8585d2 | 03:08:55 | 03:30:05 | 6 | 5 fixed (70045939), #3 ruled |
| A-535 on #274 | 20260923T041806Z-review-codex-6e72e2 | 04:18:06 | 04:33:07 | 5 | 4 fixed (77fce259, 8f872620, ddd51450, b909d492), #5 ruled |

Read from the findings store at close: no open row on any of the three
records.

A-528's rows for #1, #2 and #5 are agentscient-11's (7eaade50), red on
86ed5089's world.py (Ran 3, failures=3) and green at 70045939 (Ran 3, OK),
read by both producers. A-535's four fixes have no second-producer row;
the Lead ruled #274 gates on the trailered fixes alone, and the rows are
owed as LD-144 (71b84caa).

## What went wrong, and what it cost

- **A reading taken on the wrong tree.** `cases.py calibrate` archives
  the committed HEAD. The calibrate reading reported before the A-528 fix
  was committed was of 197e0fc0, not of the fix; after 11's rows landed it
  read the clean run red at 10ba1f97 for the same reason. The reading was
  retaken at 70045939 (green, 6 of 6). A kit reading taken on an
  uncommitted tree names the tree, or is taken after the commit.
- **The proof parser took prose for a row id.** #274's first flip refused
  with pr-proof "found absent: P-kitdaemon": the body's own prose used the
  bare prefix. Fixed by rewording; the XO's two greps (bare 0, ids 20)
  became the check. Not filed; the XO holds the parser question.
- **A fix's reading broke another fix's reproduction.** A-535 #4 took the
  start's stdout out of the refusal, and A-535 #2's reproduction parsed the
  child's pid from that stdout. The #2 reading uses the same script with
  the pid written to a file; the commit and the Proof both say so.
- **Hook refusals met** (each changed the command, none a lane defect;
  counts not measured): claim-unmeasured on commit subjects and PR bodies,
  clipped-sweep on greps piped to head, unguarded-replace, and kit-import
  on a test module written by redirect into a scratch tree.
- **The lock timed out** at every `deliverable.py show` this session (5 s,
  then 20 s); `deliverable.py done` answered with a 90 s budget.

## Refused

- The Lead's grants 361 and 362, offered through a peer: not used, since
  grants come only from the owner's words in this terminal.
- Restoring agentscient-10's uncommitted `launch.py` in `wt/ag-s3-273`
  under this session's grant: refused as laundering, and not touched.

## Open after this session

- LD-144: four planted rows for A-535 #1 to #4, for a wall session other
  than the fixes' author.
- The migration of `test_sessions.py` onto `world.adopt` waits for slice 4,
  by the Lead's order; #275's teardown and the kit coexist until then.
- A-528 #3 and A-535 #5 are declined; the first is a declared gap in
  world.py's daemons comment, and the second has no exit path (a daemon's
  name is written by the test).
