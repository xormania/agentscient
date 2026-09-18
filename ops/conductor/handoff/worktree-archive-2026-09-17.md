# The worktree fleet archived, and worktrees split per project (2026-09-17)

Written under hand grant 302, declared on the owner's words of 2026-09-17:
"its not confirmed - but it looks like having so many worktrees combined with
a filesystem tree walking may be suspect - lets address the worktree issue";
then "confirmed - worktrees are the issue - can you move them to files and put
them in one big gzipped tar?"; then "we need to separate worktrees per project
- lets use ag-wt instead of a shared wt dir". Second producer absent: this is a
hand-granted dev-lane change, one producer, the suite the check.

## What the tree held before

| reading | value | command |
|---|---|---|
| registered worktrees | 414 | `git worktree list \| wc -l` |
| inodes under ../wt | 670,299 | `du -s --inodes` |
| size under ../wt | 7.4 G | `du -sh` |
| inodes in the main checkout | 15,332 | `du -s --inodes` |

The fleet was 44 times the repository in files, and the two panics of 09-16 and
09-17 both faulted in `terminate_walk` during a dirfd-relative `newfstatat` —
the syscall shape a tree walk makes. Cause not proven; the fleet is the load
the owner ruled on.

## What was done

1. 379 worktree directories whose commits are on origin were renamed out of
   `../wt` into a staging directory, manifest first
   (`worktree-archive-2026-09-17.tsv`, one row per worktree with its branch,
   head sha and original path). 10 further rows were registrations at `/tmp`
   paths the boot wipe had already deleted — nothing to move.
2. The staged copies were archived into one gzipped tar and verified by entry
   count before the staging was removed: 521552 entries staged,
   521552 entries in the archive, equal.
   `agentscient-worktrees-2026-09-17.tar.gz`, 1286588774 bytes,
   sha256 `12e5805aab9722d810ffdb93b82843f9ab8f89539e438d77332d61fb642ad709`.
3. The 24 worktrees kept — every 2026-09-16 seat and every open PR's branch —
   moved from `../wt` to `../ag-wt` with `git worktree move`, so git's own
   pointers followed. All 24 moved, none refused.
4. `ops/lane.conf` now reads `WORKTREE_ROOT='../ag-wt'`, so every future
   worktree this lane creates lands in its own root. The shared `../wt` is no
   longer shared: what remains there is the previous repository's 91
   worktrees, which this session did not touch.

## What the tree holds now

| reading | value |
|---|---|
| this lane's worktrees, present on disk | 24, under ../ag-wt |
| inodes under ../ag-wt | 58,384 |
| inodes under ../wt (the previous repository's) | 90,364 |
| archive | 1.29 G gzipped, one file, verified |

## Left open, for the owner or a later session

- 379 registrations remain in git pointing at the old `../wt` paths and are
  missing on disk. A prune answers `ask` by the lane's own rule, so it is the
  owner's to run; nothing breaks while they stay.
- The literal `../wt` survives in wall files — `ops/devlane/hooks/boundaries.json`
  (advisory text inside one refusal's `needed`, not an enforcement path),
  `matrix.py` and the hook tests — and in historical records. Changing wall
  paths needs a wall grant in a session whose deliverable is the wall.
- The previous repository's worktrees under `../wt` are that project's to split.
