# AAR — 2026-09-13, GitHub use: the first slice of the pitfall review

Session record on `lane/session-20260913-n`, cut from dev `cccc810b`
(#201) at 2026-09-14T00:46Z, by Claude Opus 5 (1M context). The same
conversation closed `lane/session-20260913-k` (#201) before the owner's
/clear; that close is in `AAR-2026-09-13-wall-items.md`. Closed at the
owner's word ("Close this session") after #202 merged at `d21dfce6`;
§Close is the board measured from 01:40Z to 01:44Z on 2026-09-14. The
[handoff](handoff/HANDOFF-2026-09-13-github-use.md) carries the next
thread. Grant 221.

## Request and outcome

The owner: "PR #201 has handoff - co-ordinate with other claude session -
its re-writing the entire handoff manager - make sure to de-conflict.
We're working on looking at current pitfall records and fixing - github
is the first thing i want to look at - its not smooth the way we're
using it currently".

Onboarded from `onboard.py` (brief complete, exit 0, the main checkout at
dev `3014cb22`). agentscient-5e, on `lane/session-20260913-m`, named its
paths by message (machine.py, handoff.py, onboard.py's handoffs section,
the placement state key, the close and onboard skills, one corpus file)
and wrote nothing under the pitfall or defect ledgers or the GitHub
tools; #202's file list and its list stayed disjoint.

Read: pitfall rows 1 to 29 and 30 to 34, defect rows LD-1 to LD-36, the
AARs with the most GitHub mentions, I-024 and I-029; then measured the
GitHub side live. Put to the owner as eight findings with a proposal. The
answers: "Hand grant, all three"; "Yes, after telling the other session"
(the fast-forward); "Cancel the stuck CodeQL run, Pause Dependabot's
composer job"; "Leave it for a wall session" (#200).

In #202, merged at `d21dfce6`:

- LD-37: watch.py refused gh's `no checks reported` error (exit 1, even
  under `--json`) and so refused in the seconds after every push; it now
  reads that as zero rows. Red at `cccc810b`, 2 FAIL of 3, in
  `12642609`; the same command Ran 3 OK at `63699e5e`, and the whole file
  Ran 29 OK. The contract, the measure page and CONTRIB's ready table
  wait with `watch.py pr N`.
- The root composer entry in `dependabot.yml` paused (`a48edd92`):
  `packages/*` matches no package, and run 34783265531 failed on it.
- LD-38 (the trunk-commit row refuses a fast-forward of the main
  checkout), LD-32's ready half and LD-35 narrowed on live readings,
  pitfall 35 correcting pitfall 27's prose clause, nine corpus rows
  (`6505f786`).

Not done by the session: the fast-forward (refused, LD-38; the owner ran
it, `3014cb22..cccc810b`); the stuck CodeQL run (cancel 409, force-cancel
409, delete 403).

## What was decided and why

- **Fix watch.py rather than write a new wait.** The lane already had the
  lever, with a wall and expected names (`watch-lever.md`); what failed
  was one gh shape, and nothing a session reads named the lever: at
  `cccc810b`, `grep -c watch.py` over the AARs, handoffs, pitfalls, skills
  and CONTRIB found it only in its own contract, discovery-lever.md,
  census-package-map.md and lane-defects.md. Pitfall 34 was a loop
  written by hand beside it.
- **The match is exit 1 and the text prefix,** with a clean neighbour
  test (the same text on exit 4 still refuses). #202's reviewer question
  asks whether a status-rollup read through `gh api` is the better
  reading.
- **LD-32 and LD-35 narrowed, not closed,** because the live pr-proof row
  denied this session's own edit (below).
- **Ledger ids.** `ledger.py` mints from origin/dev, so two sessions'
  unpushed rows get one id. agentscient-5e renumbered its two pitfalls to
  36 and 37 by hand; this session's own pitfall (the typed sha) waits in
  the handoff for #203 to reach dev rather than being minted around the
  lever.
- **Grant 221 waited for the other session's suites run,** because LD-9's
  test snapshots the live grant ledger; that session's message: suites.sh
  exit 0 on `acc18b17`.
- **The fast-forward.** Four options went to the owner: a SessionStart
  fast-forward, LD-38's row repair, hooks run from a separate copy, and a
  warning only; 1 and 2 recommended. The owner: "i'll do options 1 and 2
  on next session".

## What went wrong

- **A reading overstated.** Plain-prose readings through both hook copies
  came back allowed, and pitfall 35 and the LD-32 and LD-35 cells were
  first written as closed. The live pr-proof row then denied this
  session's edit, whose heredoc named the ready command in backticks.
  Backtick readings narrowed all three before commit `6505f786`.
- **An invalid control.** The first trunk-commit readings ran through
  matrix.py, where the row does not live; the control (a real commit on
  dev) came back allowed, which exposed it, and the readings were re-run
  through engine.py.
- **A typed sha.** `gh run list --commit` with a 40-character sha invented
  past `6505f786` printed `[]`; the sha from `git rev-parse` listed ci
  34795348058 and CodeQL 34795347239. The handoff carries it as a pitfall
  to add.
- **The first fetch did not run.** `git fetch origin --prune=false` is an
  invalid option; pitfall 34 was missing from the first listing of
  origin/dev until a second fetch.
- **Refusals on this session's own command shapes:** clipped-sweep twice
  (a multi-alternation grep behind `head`), hand-write once (a python
  write to the scratchpad through a formatted path with no grant leading),
  pr-proof once (above), trunk-commit once (the fast-forward).
- **watch.py's new path did not run live.** Its first poll on #202 at
  01:15:56Z already saw 4 rows. gh's own shape was read live at 01:15:39Z
  (`no checks reported on the 'lane/session-20260913-n' branch`, exit 1,
  twice); watch.py's reading of it rests on the NoChecksReported tests in
  `12642609`.

## Calibration

- Spend: `python3 ops/devlane/telemetry/worth.py waste --repo /home/scientdb/projects/uscient/agentscient --since 2026-09-14T00:40:00Z`
  at 01:42:13Z: session `95d7867a` (this session's scratchpad id) total
  9,767,838 tokens, out 150,876, cached 9,615,938, 45 turns, mean context
  213,710; the other Claude session in the window, `3d19f604`, is not
  this session's. Spend after 01:42Z: not measured.
- Suites at `6505f786`: exit 0 at 01:18:13Z, 3020 tests in nine suites,
  ruff "All checks passed!". Corpus at `6505f786`: pass 185, fail 0,
  unreachable 0.
- Checks on `6505f786`: ci 34795348058 and CodeQL 34795347239, success;
  `watch.py pr 202` started 01:15:56Z and settled at 01:18:57Z.

## Close, measured 2026-09-14T01:40Z to 01:44Z

| worktree | branch | head | uncommitted | unpushed |
|---|---|---|---|---|
| main checkout | dev | cccc810b | 0 | 0 |
| ../wt/ag-session-20260913-k | lane/session-20260913-k | 31d01a2b | 0 | 0 |
| ../wt/ag-session-20260913-n | lane/session-20260913-n | 6505f786 | 0 | 0 |

- PRs (`gh pr list --state all --limit 8` at 01:40:46Z): #202 MERGED
  `d21dfce6` at 01:40:11Z with all five checks pass; #201 MERGED
  `cccc810b`; #203 OPEN (agentscient-5e); #200 OPEN (Dependabot).
- dev push runs on `d21dfce6`: CodeQL 34796668858 success at 01:41:29Z,
  ci 34796668765 success at 01:43:07Z.
- Ladders: none run. Dispatches: `subs.py` found no dispatch snapshots;
  no dispatch record of 2026-09-13 or 2026-09-14 reads `launched`.
- Findings: the one open group of the day is
  `20260913T023636Z-review-codex-bdbe55` (7), from before this session;
  `findings.py export --write` wrote 814 rows and left the tracked file
  unchanged (`git status --short` empty).
- Grants: 221 open at 01:41:02Z, settled after the records commit.
- Lock: `lane/session-20260913-m` and `lane/session-20260913-n` at
  01:41:02Z.
- The main checkout at 01:42Z: `cccc810b`, 5 behind `d21dfce6`, with no
  hook or settings file changed between them.
