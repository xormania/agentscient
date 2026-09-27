# Handoff — 2026-09-10, after the pull request consolidation

Record by Claude Fable 5.1 on `records/pr-consolidation-20260910`, cut from
dev `d2b11c7`. See the [AAR](../AAR-2026-09-10-pr-consolidation.md).
Re-measure before acting on anything below.

## Where things stand

- dev `d2b11c7` contains master `a665895` (release #85 merged by the owner,
  then master merged back into dev, zero files changed). No open PRs.
- Merged today, in order: #81, #82, #78, #79, #84, #83, #80.
- Retained, not merged: `repair/audit-enforcement-manual-20260910` at
  `055e448`, the withdrawn #79 controller with its full history.
- Graft: pinned install at
  `~/.local/share/agentscient/graft/3a85a2f40e28-node24.21.0`, state ready.
  Enabled machine-wide by `export GRAFT_INSTALL=...` in `~/.profile` and
  `~/.bashrc`; environment outranks the local conf. Shells opened before
  that change do not have it.
- The main checkout `~/projects/uscient/agentscient` is on dev, level with
  origin, with two untracked WIP files under `.dev/wip/` untouched.
- `/tmp/current-work.md` still describes #83 as an unmerged draft; stale.
- Worktrees the killed session left, all clean: `/tmp/ag-manual-enforcement-20260910`,
  `/tmp/ag-audit-enforcement-manual-20260910`, `~/projects/uscient/wt/ag-lost-work-closeout-20260910`.
  Worktrees this session used and left: `/tmp/ag-audit-monitor-recovery-20260910`,
  `/tmp/ag-graft-integration-20260910`.

## Corrections to retain

- #83's controller restores worker home paths; the claim in #79's body
  that it did not was wrong, measured in `worker-environment-probe.json`.
- Git rejects abbreviated long options such as `--outp=`; the hook
  allowlist port suggested in session was withdrawn as unfounded.
- A hand grant must lead every script depth the guard inspects, and its
  scope is matched relative to the session's cwd, not the worktree.

## Next thread: behavioral testing of the workflow and dispatches

Owner, 2026-09-10: "the next thing i want to look into is the behavioral
testing of the workflow and dispatches." Starting points, measured now:

- Contracts: `docs/probes.md` (probe corpus, runner semantics, UNREACHABLE
  is neither pass nor fail), `docs/concerns.md` (a check must fire on
  planted faults and stay quiet on clean neighbors, as measured rates),
  `docs/workflow.md` (transitions with actor class, evidence duty, failure
  class, gate).
- Code and tests: `ops/devlane/workflow/` with 3 test files;
  `ops/devlane/dispatch/tests/` with 32; `ops/devlane/harness/tests/` 9;
  `ops/devlane/task/tests/` 17; `ops/devlane/hooks/tests/` 16;
  `ops/conductor/tests/` 31. `ops/bin/suites.sh` is the one green answer.
- A measured lead from today: of the 41 dispatch records carried by the
  merged PRs, 9 ended invalid with no envelope, by harness timeout or exit
  -15. Both #78 and #84 were finished by hand because of such stalls.
  Behavior under wall, kill and missing-envelope conditions is where the
  pipeline actually failed this week; the records under
  `.dev/records/dispatches/` are the evidence set to test against.
- Two ready-made behavioral fixtures now on dev: the git isolation tests
  in `ops/conductor/tests/test_monitor_git_isolation.py` (plant a command,
  prove it never runs) and the seat probe method in
  `evidence-2026-09-10-manual-enforcement/worker-environment-probe.json`
  (stand-in host, observe the environment boundary).

## Retrieval

```sh
git show records/pr-consolidation-20260910:ops/conductor/AAR-2026-09-10-pr-consolidation.md
git show records/pr-consolidation-20260910:ops/conductor/handoff/HANDOFF-2026-09-10-pr-consolidation.md
```

Left behind on purpose: the session transcript, scratch files under the
session scratchpad, and the stale `/tmp/current-work.md`.
