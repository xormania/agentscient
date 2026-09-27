# AAR — 2026-09-10, open pull request consolidation

Session record by Claude Fable 5.1. Measured at write time against dev
`d2b11c7`, master `a665895`, zero open pull requests. The
[handoff](handoff/HANDOFF-2026-09-10-pr-consolidation.md) carries state
and the next thread.

## Request and outcome

The owner asked for a merge strategy over seven open draft PRs, then for a
recommendation between the two rival conductor controllers (#79 and #83),
then for everything fixed and merged in this session without the pipeline:
"keep it simple and precise, and don't create scope creep."

Outcome: all seven merged into dev in order #81, #82, #78, #79, #84, #83,
#80; release #85 (dev into master) opened as a draft and merged by the
owner; master merged back into dev; Graft enabled on this host for every
checkout. Every merged head had all four expected checks green; each PR
carries a ready note naming its head and check readings.

## What was decided and why

- **#83 kept as the single controller; #79 reduced to records.** #83 was
  the designated repair in `/tmp/current-work.md`; #79's own AAR admits it
  "started a second implementation despite the parallel repair". Measured,
  #83 already restores worker home paths for declared actions, which #79's
  description said it lacked. #83's test provenance was complete for a
  bootstrap (independent CHANGES review, author corrections, measured RED);
  #79's was not. The withdrawn implementation is retained on
  `repair/audit-enforcement-manual-20260910` at `055e448`; its evidence is
  retained in #79 under a directory that no longer collides with #83.
- **Carried from #79 into #83:** only the worker-boundary measurement the
  owner had demanded, re-taken against #83's exact bytes with stand-in hosts
  (`worker-environment-probe.json`). Nothing else measured as worth porting.
- **#80's Codex P1 fixed by hand under grant 44.** Git observation now runs
  with inherited `GIT_*` dropped, system and global config disabled,
  `GIT_SSH_COMMAND` fixed to `ssh`, command-bearing keys emptied at highest
  precedence and only file, http, https and ssh transports allowed. Two
  regression tests plant a marker-writing `core.sshCommand` and an `ext::`
  remote and prove neither runs.
- **Conflicts pre-resolved so merge order stopped mattering:** #78 merged
  into #84 with both prompt appends kept; #83's ruff entries moved one line
  away from the line #80 edits, because Git treats adjacent hunks as a
  conflict even when one side's change is identical.

## What went wrong

- **My first recommendation was backwards.** I recommended #79 on the
  strength of its description of #83. Reading #83's code reversed it. A PR
  body's claim about a rival is not evidence; measure the rival.
- **I asserted a hook bypass that does not exist.** I claimed #83's hook
  missed abbreviated `git log --output`. Git 2.43 rejects the abbreviation.
  Withdrawn after measurement, before any change was made.
- **My probe evidence tripped the term wall.** The scratch path embeds the
  machine user outside a home path; CI went red on #83 until scrubbed.
- **Repeated guard refusals cost time, all on my command shapes:** a
  multi-alternation grep with `head`, an unguarded `.replace`, a hand grant
  that must lead the script at every depth, not only the outer command.
  Each refusal stated its remedy; none was a lane defect.
- **The classifier blocked the force-push.** The owner ran it. Two other
  denials were the owner declining a scratch cleanup, not faults.
- **Root cause of the #79/#83 duplicate** was two sessions given
  overlapping work with no single declared implementation owner. The
  controller in #83 now bounds a seat to an owner plan, which addresses the
  runaway; it does not by itself prevent two owners.

## Calibration

- Full suites were not re-run on each merged tree; the owner waived the
  pipeline for this consolidation and the ready notes say so.
- The worker probe uses stand-in host scripts, not native CLIs; it measures
  the seat's environment boundary only.
- The Codex thread on #78 named a commit that exists nowhere; answered with
  the measured trailer check and resolved.
- Grants 44 and 45 are settled with evidence. This session created no
  worktrees before this record; the detached scratch worktree under
  `/tmp/claude-1006/.../c1b9ce7c-.../pr10-wt` belongs to another session.
- Spend was not measured; no cost total is claimed.
