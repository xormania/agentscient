# The dispatch store, and what was actually loading this host (2026-09-18)

Written under hand grant 305, declared on the owner's words of 2026-09-17, at
head 421b5204 with the store measured that hour: "i'm pissed - i thought they
were fixed - and this is an issue - i don't why they were not - i want this shit
done - if they're archived - what is going on? The worktrees are causing WSL2 to
fail - i'm confused". Second producer absent: this is a hand-granted dev-lane
change, one producer, the lever's own readings the check. Every table below is a
command's output at that head; nothing here is recalled.

## The owner was right, and so was the record

Both worktree cleanups happened and both held, measured at 421b5204: `../wt` is
90,364 inodes and `../ag-wt` 58,384. What neither measured is that the worktrees
were never the largest thing on this disk.

| tree | inodes | share of home |
|---|---:|---:|
| `~/.local/state/agentscient/dispatch` | **1,556,838** | 44% |
| `~/actions-runner` (12 CI runners) | 1,093,786 | 31% |
| `../wt` (the previous repository's 91) | 90,364 | 2.5% |
| `../ag-wt` (this lane's 24) | 58,384 | 1.6% |
| the repository itself | 11,942 | 0.3% |
| **home total, before** | **3,562,444** | |

All six rows are `du -s --inodes` at 421b5204. The dispatch store was outside
every sweep's scope because it lives outside the repository, and the lane's own
law names it once — "runtime residue, job captures, snapshots, isolated homes —
is gitignored" (`ops/README.md`) — and then never sweeps it. 845 job
directories, 47 GB, accumulating since 2026-09-03 with no retention rule.

## What a job directory holds

`du -s --inodes` and `du -sc` over all 845 at 421b5204:

| component | inodes | bytes | what it is |
|---|---:|---:|---|
| `snapshot/` | 1,145,931 | 16.5 GB | a full git checkout of the repo per job |
| `home/` | 379,950 | 28.5 GB | the harness isolation HOME per job |
| `out/` | 18,656 | 0.8 GB | the worker's output — evidence |
| `context/` | 2,310 | 2.7 GB | evidence |

98% of the store is `snapshot/` and `home/`. `record.json` names the sha each
snapshot is of (`snapshot.ref_sha`), so the tree is reproducible from git;
`home/` is throwaway by construction.

## What the readings proved before anything moved

Each numbered line is the output of `dispatch-prune.sh --plan` or of the
verification loops run beside it, at 421b5204:

1. **Every job's record is readable**, in the store (825) or, for the earliest
   jobs whose store record is gone, in the repository's tracked copy
   (16 more). 4 jobs have a record in neither and were **kept whole** — their
   directory is the only trace of them.
2. **Every snapshot's sha is present in this repository**: 841 of 841 planned.
3. **No snapshot holds a commit the repository lacks.** Each staged snapshot
   carries its own `.git`; 417 sit exactly at their recorded sha, and 424 have a
   HEAD advanced past it by the worker's own commits during the job. All 424
   advanced heads resolve here. **Orphans: 0.**
4. **Every pruned job kept its evidence**: 841 of 841 still hold their record
   and their `diff.patch` after the move; 0 short.

The four kept whole, snapshots intact:

    20260903T232328Z-plan-claude-31155a
    20260903T232436Z-plan-claude-537b84
    20260906T134527Z-review-grok-7012f3
    20260906T144159Z-plan-codex-583a0b

## Where it stands

| reading | value |
|---|---:|
| dispatch store, before | 1,556,838 inodes / 47 GB |
| dispatch store, after the move | **34,792 inodes / 3.6 GB** |
| moved aside, awaiting deletion | 1,522,888 inodes / 43 GB |
| home tree, before | 3,562,444 inodes |
| home tree, once the moved-aside tree is deleted | **2,004,764 inodes** |

The bulk sits at `/home/scientdb/dispatch-bulk-staging-20260918`. It is moved,
not deleted: the harness's own permission mode (a finished snapshot is sealed
`555`) and this agent's permission boundary both stop at deletion. The last step
is the owner's hand:

    ops/bin/dispatch-prune.sh --remove

which re-reads the index, refuses unless all 841 still hold their record and
diff, and only then deletes. Not measured: whether that command succeeds, since
this session cannot run it.

## The lever

`ops/bin/dispatch-prune.sh`, in the shape `branch-retire.sh` already uses: three
steps, each refusing without the one before it, on the refusal wire, exit 0/1/2.
`--plan` writes the index, `--stage` moves the bulk aside, `--remove` deletes it
behind the evidence gate. It refuses `running` if any launcher process is alive,
because a live job writes into `snapshot/` and `home/` for the life of the job.
Its refusal wire was exercised on three classes at 421b5204 — `arguments`,
`plan`, `store` — each exit 2, one stderr line, expected/found/needed. Not
measured: a test table with planted faults; the lever has none and that is a
declared gap, the same one T-202 files against `branch-retire.sh`.

The index it writes, one row per job with its sha, its record's source and its
disposition, is `ops/conductor/handoff/dispatch-snapshot-index-20260918.tsv`.

## What this leaves open

- **The store has no retention rule.** This prune is a rescue, exactly like the
  two branch sweeps before it. The mechanism the owner asked for — archive at
  done, not in a sweep — belongs at the close of a dispatch: a job that closes
  keeps its evidence and drops its snapshot and home then, not 15 days later.
  That is T-200's third source, one layer down.
- **`~/actions-runner` is 1,093,786 inodes** across 12 runner work directories,
  not touched here. It is the second-largest tree on this host and nobody has
  ruled on it.
- The 48 stale worktree registrations and the 227 already-merged local branch
  refs remain; both need a delete this agent cannot make.
