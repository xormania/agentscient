# The launch offer and successor design

## Current disposition after #286 and #288

Preserved from #277 at 9ab4ea2e68695e6fb4ff16da3726252dfbdeb89c when #285 became
the sole sessions candidate. The original measurements and proposed cases below
are historical; they do not describe the current implementation.

- #288 implements the atomic initial bind/offer and transfers the actual offered
  assignment through the launch receipt. Its assignment handoff regressions
  cover the current supported transition and rollback behavior.
- Automatic dead-worker recall, successor drafting and the proposed eligibility
  verb remain pending design work. F2, F3, F5 and F6 below are proposed acceptance
  cases, not tests claimed green by #285. They must preserve the existing
  assignment authority and generation checks when implemented.
- Problem 3's proposal to execute trusted controls from the candidate snapshot
  is superseded by #286. The runtime is captured separately from the trusted
  launcher source, pinned and immutable. Candidate code never supplies its own
  enforcement. The immutable-runtime tests on dev are the current acceptance
  evidence; do not implement the old source=snapshot proposal below.
- The live sequence below has not been rerun during this queue refresh. The
  original ownership roster records the earlier session; it is not a current
  assignment to an active agent.

Written 2026-09-23 06:5xZ by the Dispatcher session agentscient-69 (PT-22)
under grant 367, at the owner's order of 06:25Z (problems 2 and 3) and the
XO's word of 06:5xZ. Every fact below was read from origin/dev 4c375c6a
with `git show origin/dev:<path>` unless another head is named. Ledger
rows it answers: LD-141, LD-143, LD-151 (problem 2); LD-119, LD-142
(problem 3).

## What is measured

- `coordination.py:999-1055` core_bind_for checks only that A-n exists
  and mints the participant with `bound_for = A-n`. No place, holder or
  recipient check. No offer.
- `coordination.py:1094` core_offer: lead or coordinator, drafted to
  offered only. `:1110` core_claim: refuses class recipient unless the
  participant is the addressed recipient. A worker cannot self-offer.
- The machine (`:202-211`): release and reassign from held only,
  supersede from offered only; nothing leaves offered or held when the
  holder is a dispatched participant whose record has closed; no
  successor from submitted; a drafted row has one exit, offer (LD-151).
- `launch.py:2278` installs enforcement, `:2281-2283` calls bind-for,
  `:725-760` writes coordination-mcp.json with the launch's `--for` text
  as "assignment". `coordination_mcp.py:148` coord_claim takes the
  assignment from the worker's argument. Nothing checks the two agree.
- `launch.py:1918` and `:2278` both call
  `install_enforcement(..., source=APP.parents[2], cwd=snapshot)`;
  `APP` (`:28`) is the launcher's own directory, so the source is the
  launching worktree. `isolation.py:589` reads
  `source/ops/devlane/hooks/profiles.py` and `:600` pins `"source"` to
  that path. The snapshot (`launch.py:430-442`) is a detached checkout
  of the ref, made read-only (`:1895-1899`). `COORD_MCP_PINNED` (`:624`)
  and `COORDINATION` (`:41`) resolve under `APP.parents[1]`, the
  worktree; the lane MCP server (`:704-706`) already resolves under the
  snapshot (`Path(snapshot) / LANE_MCP_REL`).
- The forward merge is `ops/conductor/tools/dispatch.sh:245-262`, law
  (AGENTS.md: "merges dev forward into the branch before every launch
  and refuses only a conflict"). It stays.
- A record names its binding session as `session.binding_id` or inside
  the bind-for receipt `session.bound` (`launch.py` `_binding_session`);
  `participants.session_id` is that same string. That is the join
  between a holder and its dispatch record.

## Problem 2: the offer rides in the launch

### coordination.py (dev lane; agentscient-10 writes 1 to 3, 69 writes 4)

1. `recall A-n --record ID --generation N`. Transition
   `T("recall", "offered", "drafted", "any", "required", "place",
   "clear")` and the same from `held`. Role: dispatcher or lead. Gate:
   the holder or recipient participant's `session_id` equals the binding
   session of dispatch record ID in the dispatch store, and the record
   is closed (an `exit` file, or state.json's pid dead by pid and start
   time). Otherwise refuse class `holder-live`: expected a closed record
   for the holder; found the record id and its state; needed wait for
   its close or stop the worker. Evidence: `record ID exit N`. Holder and
   recipient clear.
2. `draft ... --supersedes A-k`. Admitted when A-k stands in place
   submitted or in one of the two places after it in the machine table
   (`coordination.py:204-207` at 4c375c6a); the new row carries
   `predecessor = A-k` and the note names A-k's submit evidence; A-k is
   unchanged. A-k in another place refuses class `place` naming the
   admitted places. Not measured: this transition does not exist at
   4c375c6a ("supersedes|predecessor" appears once in the file, 10's
   count). `supersede A-k --by A-m` also admits place drafted (LD-151),
   the same transition from `drafted`.
3. `eligible A-n --session ID` (a read, and a core function bind-for
   calls). Answers one word and the reason: `offerable` (drafted),
   `claimable` (offered to this session's participant), `recallable`
   (offered or held by a participant whose record is closed, with the
   record id), `successor` (submitted or later), `held-live` (held or
   offered to a participant whose record is open, with the record id),
   `superseded` (names the successor).
4. `bind-for --session ID --roles worker --for A-n --harness H
   --capability-digest SHA` mints and offers in one `BEGIN IMMEDIATE`
   transaction, by the eligibility read: offerable, offer; recallable,
   recall then offer, the marking naming the record; successor, draft
   the successor with `--supersedes A-n` and offer it; claimable, offer
   already stands; held-live or superseded, refuse class `coordination`:
   expected an assignment offerable to the minted participant; found the
   place, holder and record; needed wait for its close, or name the
   successor. The offer inside bind-for is the issuing dispatcher's act
   and the marking says so. The receipt line names the assignment
   actually offered:
   `participant PT-n bound for session ID by PT-d for A-m` with
   ` supersedes A-k` appended when a successor was drafted. Nothing else
   in the receipt changes, so `_binding_session` keeps reading it.

### launch.py (wall; agentscient-11 writes on this design)

- Read `A-m` from the receipt (`_bound_participant` already reads
  `PT-n`; one more group) and write it as `"assignment"` in
  coordination-mcp.json (`:747`), so the config and the claimable
  assignment agree by construction. Record the launch's `--for` beside
  it as `"requested"` when the two differ.
- A bind-for refusal already refuses on the wire (`_bind_worker`). Move
  the call ahead of the record directory and snapshot creation, or
  remove the job directory on that refusal, so no record exists for a
  run that cannot claim (LD-141's "no record is minted").

### Planted faults and clean neighbours (the case table, 5c's rows)

Store built as `test_coordination.py` does (World, scratch
XDG_STATE_HOME, the real deliverable lever); the dispatch store planted
under the same XDG root with a record directory per case.

- F1 (LD-141): A-n drafted, launch `--for A-n`. Pass: before the worker
  starts, A-n reads offered to the minted PT and the config names A-n;
  the worker's claim succeeds.
- F2 (LD-143 case 1): A-n offered to PT-a whose record has an `exit`
  of -15, relaunch `--for A-n`. Pass: A-n recalled (marking names the
  record) and offered to the new PT; config names A-n.
- F3 (LD-143 case 2): A-n submitted by PT-a, relaunch `--for A-n`.
  Pass: A-m drafted with predecessor A-n, offered to the new PT, config
  names A-m and `requested` A-n; A-n unchanged, its evidence readable.
- F4 (LD-143 case 3): A-n held by PT-a whose record has no `exit` and a
  live pid. Refuse at launch, class `coordination`, exit 2, no record
  directory.
- F5 (LD-151): A-n drafted, nobody; `supersede A-n --by A-m` succeeds;
  a held row still refuses.
- F6: recall by a participant without dispatcher or lead refuses class
  role; recall with a record whose binding session is another
  participant's refuses class `holder-live`.
- Clean neighbours: offer, claim, release, reassign, submit and
  supersede-from-offered unchanged; the existing tables
  (`ops/conductor/tests/test_coordination*.py`, eight modules at
  4c375c6a) read again after the change, their readings quoted in the
  commit that carries it. Not measured here.

### The live sequence (the owner's exercise)

1. Launch a codex security-audit `--for A-n` from an idle worktree; read
   the record's coordination-mcp.json and `coordination.py show A-n`:
   offered to the participant the config names, without a hand offer.
2. `kill -TERM -- -<pgid>` the worker after coord_claim (the record's
   marking shows held); the record closes with exit -15.
3. Relaunch `--for A-n`: A-n recalled and offered to the new
   participant; the worker claims and submits; the record closes 0.
4. Relaunch `--for A-n` once more: A-m drafted with predecessor A-n,
   offered, claimed, submitted; A-n's submission still reads.
5. `watchdog.py` and `tmux ls`: no worker and no server of the four
   runs left.

## Problem 3: the pinned set comes from the snapshot

### launch.py (wall; agentscient-11 writes on this trace)

- Both `install_enforcement` calls (`:1918` resume and `:2278` launch)
  pass `source=snapshot` (the same object as `cwd`). The snapshot is at
  the launch's ref, so the helper bytes equal the worktree's at launch
  and cannot move after.
- `COORD_MCP_PINNED` resolves under the snapshot, as `LANE_MCP_REL`
  does: `Path(snapshot) / "ops/conductor/tools/coordination_mcp.py"`.
  It imports its sibling coordination.py from the same tree.
- `COORDINATION` for bind-for stays the launcher's own: it is the
  dispatcher's act at launch time, not a worker runtime dependency.
- Resume (`:1918`) reads the retained job's snapshot; the pin is
  re-read from that snapshot, never from the worktree the job left.
- `isolation.py` and `profiles.py`: nothing changes in the pin's shape;
  the `"source"` field now names the snapshot, so a reader comparing it
  to a worktree path is the finding, not the fix.

### The proof (LD-119's wanted row)

A fake dispatch under the kit from a world worktree; the worktree moved
forward mid-run by a commit that changes `ops/devlane/hooks/profiles.py`;
the worker's next hook call still admits; coord_submit succeeds; the
record closes 0. Clean neighbour: a worktree that does not move. A second
fault: the snapshot's helper changed by hand mid-run, the guard refuses
hook-unavailable as it did on records 6ed2cb and 8649a7 (LD-142). The
row is wanted, not written: LD-119's tests field reads "none yet" at
4c375c6a.

### The trace of the launch paths (what reads the pinned set, at dev)

- `ops/bin/dispatch.sh` (shim) and `ops/bin/go.sh` run
  `ops/conductor/tools/dispatch.sh`, which runs the launcher named by
  `LAUNCHER_PIN` or the worktree's own; the launcher reads the pin from
  `APP.parents[2]` today. Covered by the change above.
- `ladder.py:653-654, :900, :1177` runs the worktree's dispatch.sh and
  launch.py. The same path. Covered.
- `launch.py resume` (`:1918`). The same call. Covered.
- `hand.py:47-48` maps verbs to lever paths for the hand ledger, no
  launch. `land.py`, `watchdog.py`, `keepalive.py`, `instrument.py`,
  `co_doc.py`, `lane_read.py`, `laneconf.py` read or load; none installs
  enforcement.
- `ops/devlane/dispatch/levers/{grok,codex}-dispatch.sh` and
  `claude/fable-dispatch.sh`, with `selftest.sh`: custody levers with
  their own `--scope-ref` snapshots; zero mentions of install_enforcement,
  profiles.py, binding.json or launch.py. They install no shared guard
  and read no pinned set; whether they should is a separate question,
  not this row.
- `dispatch_actions.py` (the sessions lever's launch, on #277 at
  b30d4e72; absent from origin/dev 4c375c6a, `git show` fatal): not
  traced yet; to trace at b30d4e72.

## Owners

coordination.py: agentscient-10 (1 to 3) and agentscient-69 (4);
launch.py: agentscient-11 on this design; the case table: agentscient-5c;
the live sequence: agentscient-69 as Dispatcher. Grants: 367 (69),
368 (wall, 11). No producer writes the tests of its own implementation.
