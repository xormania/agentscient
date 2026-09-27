# wall-slice-held-items.patch — two wall changes waiting on the owner

Written 2026-09-16 by the wall session on `lane/session-20260915-h`
(Claude Opus 5, 1M context) at the owner's word, relayed through
agentscient-11: "Let's wind this session down - don't throw away useful
work". The work is green and uncommitted, and it lives only in a
worktree, so it is saved here as a patch rather than lost with the
worktree.

## What the patch holds

Four files, all of them wall: `ops/devlane/hooks/boundaries.json`,
`ops/devlane/hooks/claude/engine.py`,
`ops/devlane/hooks/claude/matrix.py`,
`ops/devlane/hooks/tests/test_engine.py`.

**The `wall-state` row (LD-47).** The wall row's PreToolUse half reads
the command's text: it resolves the paths a `python3 -c` writes and reads
the body of a `bash`/`sh`/`source` script, but it never opens a
`python3 <script.py>` file, so a script's `Path.write_text` to a wall
path is invisible to it. The new row is a PostToolUse check on the tree
instead of the command, so it is interpreter-agnostic: `git status
--porcelain -uall` over `matrix.WALL_PATHS`, refused when a wall path
differs from its tracked content with no open `wall` grant in the lane
store. `escape: none`, because an ordinary grant must not skip it. A
`CouldNotLook` is a `hook-error`, never a pass.

**The done gate's freshness bound.** The gate accepted any pasted
`deliverable.py` line on shape alone, so one reading went into six
replies in an evening because nothing had changed. The bound is 300
seconds, read off the line's own `now=` stamp; a line with no stamp is
passed and declared unjudged, which is a declared gap, not a silent one.

## The readings, measured at f44a508f with the patch applied

- `python3 -m unittest discover -s ops/devlane/hooks/tests -p test_engine.py`
  — red for the row: 7 failures, `unknown predicate wall_path_dirty`
  (hook-error, the honest red: the registry named a predicate the engine
  did not have). Red for the bound: 1 failure, `engine let it through`.
  Green, both in: `Ran 38 tests, OK`.
- `python3 -m unittest discover -s ops/devlane/hooks/tests -p 'test_*.py'`
  — `Ran 323 tests, OK`.
- `ruff check ops/devlane/hooks` at ruff 0.16.5 — `All checks passed!`

The patch applies to `f44a508f`, the merge of #232 into `dev`.

## What it waits on

Two things, both the owner's to say, and neither one another session's
to lift:

1. The commit is denied in the session that wrote it by the harness's
   auto-mode classifier, as `[Self-Modification]`: it changes the hook
   engine that governs that session. Only the owner lifts that, in that
   terminal.
2. The wall is changed only in isolation (AGENTS.md, owner 2026-09-12),
   so it lands from a session whose deliverable is the wall, under a
   grant of lever class `wall`.

Three probe corpus rows pin counts this patch moves —
`P-BND-20260912-registry` 23 class rows to 24,
`P-TRUNK-20260912-prose` 8 `"engine": true` to 9,
`P-ENG-20260912-vocab` 13 predicates to 14. They are LD-59, and the
session that lands this patch re-pins them in the same change or its
proof reads red.

## Applying it

    git -C <worktree> apply ops/conductor/handoff/patches/wall-slice-held-items.patch

Under a `wall` grant leading the command, in a session whose deliverable
is the wall. Read the two readings again after applying; a patch's own
green is the writer's word, not the applier's.
