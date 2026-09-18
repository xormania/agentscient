# Serial points in the lane, swept 2026-09-16

Ordered by how many seats each blocks. Booked under the owner's standing
ruling of 2026-09-16, relayed as M-152: "i want to make this clear - we
need to be able to do a shit ton in parallel - we're not a serial shop".

The rule the owner's words set: a host-wide lock, a single-holder role or
a serial gate is a defect unless it protects a measured conflict on one
branch or one record, and then it locks that branch or record and nothing
wider. Each row below carries the conflict it claims to protect, measured
or declared absent. Rows only tonight; assignment is tomorrow's, by model
and effort.

Two rows here are not defects. A sweep that finds only defects has not
looked at the cases where serialization is doing its job, and the next
sweep would re-open them.

## 1. The one-Dispatcher machine — blocks every seat, for every dispatch

**What it serializes.** One session on the host may run `dispatch.sh` or
`go.sh`. The `dispatcher` boundary row reads `holder_note` and compares
it with the session the harness names.

**Conflict claimed.** Two launches on one branch, and a trunk not brought
forward before a launch.

**Measured.** The conflict is real but narrower than the lock. M-153
measured `ops/devlane/dispatch/CONTRACT.md` and `ops/README.md` at
20:29:13Z: each dispatch mints its own snapshot of the tree from a named
ref into a job directory outside every worktree, with its own isolated
home per harness, and `collect` requires HEAD to descend from `ref_sha`;
845 job directories on disk. Worker isolation is already parallel. The
serial point is only the gate in front of the launcher, plus
`dispatch.sh`'s forward merge into the invoking worktree, which is per
branch already because one line of work is one worktree.

**Cost paid tonight.** Every dispatch in the lane is blocked until
02:31:59Z because the machine names a dead session. Two security audits
wait on it, one of them for a p1 on the trunk.

**Status.** Withdrawn on the owner's word (M-151): "fuck that - what if
we need multiple dispatched harnesses?". Wall row, unassigned. Replace
the host-wide gate with a per-session, per-branch check; leave snapshots,
homes and collect alone. Planted faults named in M-151: two seats
dispatching at once on their own branches, a seat dispatching for
another's branch refused, a dead holder not blocking.

## 2. The lock lever's serial measures — blocks every seat, at every stop

**What it serializes.** `deliverable.py show` runs every locked branch's
measure one after another, in one process.

**Measured.** 25 branches in the lock at 2026-09-16 21:0xZ, up from 23
earlier in the day. `MEASURE_TIMEOUT` is 120s per measure, so the worst
case grows with the number of seats and has no ceiling short of 25 times
120s. The lever answered in full at 19:15:5xZ and timed out at 30s at
19:17:59Z from the same directory; a compaction onboard read
`lock: UNREACHABLE: timed out after 5s, retried and timed out after 20s`.
The single-target read answered in 0.02s tonight at exit=0.

**Conflict claimed: none found.** Reading 25 measures in series protects
nothing — the measures do not contend with each other, and the
single-target read is available and fast. This is serialization by
construction rather than by design.

**Cost paid.** The Stop hook demands a lock line from every seat, so a
lever that cannot answer under load blocks every seat's close.

**Status.** Covered in part by LD-96, whose repair — a measure reads
once, never a second live invocation — is about flapping. This row is
about the fan-out, which that repair does not reach.

## 3. Ledger id minting off one ref — blocks any seat filing a row

**What it serializes.** `defects.py next` fetched `origin/<trunk>` and
answered off that ref alone.

**Conflict claimed.** Duplicate ids.

**Measured.** The conflict is real and was hit four times on 2026-09-16.
Three came through the unmerged-branch window: ids on branches not yet on
the trunk are invisible to the lever. The fourth came through a different
window entirely — this session and agentscient-86 both took LD-103, five
seconds apart, at 17:01:32-04:00 and 17:01:37-04:00, each having scanned
all 393 origin refs first and each correct at the moment it read.

**Why both halves are wanted.** The ref-wide read closes the first
window. It cannot close the second, which is the interval between reading
and writing. Only a mint under one transaction closes that. Recorded
because the alternative reading — that the fourth collision is a
recurrence against the repair, and so a row filed against it under
D-PATTERN-1 — is wrong, and would be the natural conclusion for whoever
meets it next.

**Status.** Half of it is in, half is owed. f2 reports the ref-wide read
at 47a7c3d5ed0d6dd83cb25c2708a20ef70e7946c1 in #264, grant 293 settled:
`minted_anywhere` reads every ref in one spawn after a fetch, an origin
it cannot reach refuses class `refs` on `add` as well as `next` rather
than answering off stale refs, and `next defects` answers LD-98 at two
trunk states, 5e707cfa and ee62c3d1. The read-to-write interval is
untouched by that and stays with S2's reservation table, one
`BEGIN IMMEDIATE`; f2 carries it as T-180. Ruled complementary by the CO
in M-155 on design grounds; the five-second collision above is the
measured case.

## 4. `deliverable.json.lock` — blocks any seat writing the lock

**What it serializes.** One lock file per host guards
`~/.local/state/agentscient/deliverable.json`, the file carrying every
branch's target.

**Conflict claimed.** Concurrent writes corrupting one JSON file.

**Measured.** The conflict is real: it is a single file, and two seats
adding targets at once would race. But the lock is host-wide while the
contended unit is one branch's row, which is the shape the owner's rule
names — it may lock that record and nothing wider.

**Status.** No row. Wants one. Ranked below the three above because it is
held briefly and no seat reported blocking on it tonight; the row should
say that the absence of observed cost is why it sits here, not that the
shape is acceptable.

## 5. The single verifier role — blocks any seat needing verification

**What it serializes.** One participant carries the `verifier` role;
measured 2026-09-16, exactly one does, against 6 mentions of the role in
`coordination.py`.

**Conflict claimed: not measured.** The same shape as the Dispatcher
role, and the Dispatcher role turned out on measurement to protect
something much narrower than it locked. Nobody has asked what this one
protects.

**Status.** No row. Wants one, and the first thing that row must do is
name the conflict or declare it absent — not propose a replacement.

## 6. `state.db` single-writer — blocks every seat, and is right

**What it serializes.** SQLite permits one writer at a time.

**Measured.** `journal_mode` reads `wal` and `busy_timeout` reads 5000.
WAL gives concurrent readers alongside the single writer, and a writer
that finds the store busy waits five seconds rather than failing.

**Not a defect.** The conflict is real, measured, and on one record; the
serialization is as narrow as the storage engine allows, and readers are
not blocked at all. Recorded so the next sweep does not re-open it, and
so that "every serial point is a defect" is not the lesson taken from
this page. It is not what the owner's words say.

## 7. `suites.sh` — the inverse case, and it has a real cost

**What it does.** Runs suites concurrently by default; `SUITES_SERIAL=1`
forces serial, at `ops/bin/suites.sh` lines 76 and 82.

**Measured.** This is a parallel point with an unmeasured conflict, which
is the mirror image of everything above and just as much a defect. 86
found it on a merged tree: the four-way sharding of
`ops/conductor/tests` races a HEAD-mutating case in one shard against
`test_dispatch_wrapper`'s HEAD-unchanged assertion in another. Alone, and
in a single-process discover of the whole conductor suite, it reads
1478 of 1478.

**Status.** LD-103, filed by 86 in its own name, in #262, carrying the
single-process reading as its clean neighbour and a planted-fault spec.

**Why it belongs in this sweep.** The owner's ruling asks for parallelism
and this row is what unexamined parallelism costs. A sweep collecting
only serial points would have argued for removing gates while leaving a
race in the one place the lane already runs concurrently.

## 8. Per-host pid files in the launch path — declared absent

`ops/bin/dispatch.sh` carries zero occurrences of `pid`, measured
2026-09-16. Looked and found nothing; this is not an inference from
silence. Concurrency in the launch path — record ids, job directories,
telemetry — was not swept here and remains to be measured before any seat
writes the M-151 wall row, as M-151 itself requires.
