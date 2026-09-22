# AAR — time lost to constraints, 2026-09-22 21:00Z–23:20Z

Ordered by the Lead, relayed by the XO (PT-21), owner 2026-09-22: "have a
grunt look into where we're wasting time because of stupid constraints - i
have to get this done - we're running out of time - the prod-lanes are
almost done - this system has to ready when they are". Written by PT-23
(Grunt) under hand grant 330 (owner, this terminal, this session: "hand
grant ok'd"). Reading, not memory: dispatch records under
`~/.local/state/agentscient/dispatch/`, `ops/conductor/tools/ledger.py list
defects`, `ops/conductor/tools/hand.py open`, and the XO's
`aar-notes.md`. Absence is declared where looked and not found, not
inferred.

## Stalls, refusals, relaunches

| when (UTC) | cause | cost (min) | earned its cost? |
|---|---|---|---|
| 21:56:04–22:12:09 | A-478 check-tests (record `20260922T215604Z-review-codex-f6777b`) ran to completion (exit 0, 26 findings) but its environment was corrupted mid-run: the XO's forward-merge `da40a17d` into branch 69 changed the pinned hook-helper set the worker's sandbox had already bound (LD-119, the defect this session independently confirmed at file:line earlier today). The 26 findings were still used to drive the test revision, so the finding content wasn't lost; what's lost is the audit's own environment-integrity guarantee. | ~16 (the job's full wall time, provenance-tainted, not recomputed) | No. Nothing enforces "don't forward-merge into a branch a live dispatch already snapshotted." This is the second confirmed instance of the same pattern (the other: record `20260922T215604Z-review-codex-f6777b`'s own hook-source pinning bug, found separately this session) — a systemic gap, not a one-off mistake. |
| 22:16:41–22:46:46 | A-483 author-tests (record `20260922T221641Z-code-grok-06f90e`), killed at the 1800s author-tests cap, exit 137. Per the Dispatcher's own reading: 54 insertions / 23 deletions sat uncommitted in `residual.patch` at the sandbox wall when the kill landed; only one commit (`d2a24d8c`) survived. Root cause named, not guessed: `DISPATCH_TIMEOUT` is admitted verbatim and never clamped to the job's own cap (`launch.py:1934-1942`), so the wrong timeout fired the kill. | ~30 (the run) + all of the next run below (the redo) | No. A hard kill with no commit-before-kill drain is a design gap, not a considered tradeoff; the fix is cheap (commit or patch-export before SIGKILL, or clamp the admitted timeout to the job cap) and the cost (a lost ~30 min run plus a full ~25 min redo) is disproportionate to that fix. |
| 22:49:45–23:14:17 | A-483 retry (record `20260922T224945Z-code-grok-a8b48e`), exit 0. This run exists only because the row above killed its predecessor mid-work. | ~25 (pure redo cost of the row above, not double-counted as a separate defect) | N/A — this is the bill for the row above, not its own constraint. |
| 23:15:26–(open at reading time) | A-490 (record `20260922T231526Z-code-grok-312c63`), still running. Anomaly, not yet a confirmed cause: this record's `caps.timeout` reads `None`, unlike its four siblings above which all read `1800.0`. I looked and could not explain why from the record alone — flagging as an open measurement gap, not asserting a cause. | unmeasured (open) | Unmeasured — could not look further in the time available. |
| landed via PR #268 (merged `7de37de6`), diagnosed and fixed same day | LD-117: the amend-published guard judged the main checkout's HEAD instead of the `-C <worktree>` HEAD it was actually asked about, a false positive that blocked a legitimate amend. Worked around with `git reset --soft 17a377af` + a fresh commit `71241d93` instead of the blocked amend. | small (a diagnosis-plus-workaround, not a long stall; exact minutes not in the record) | No. The guard read the wrong HEAD; that's a bug in the guard's own cwd handling, not a policy tradeoff. |
| standing, hit today on A-479 | The unconditional refusal on dispatching Claude with role=write (`launch.py:2112-2114`) meant A-479's implementation could not be parallelized as a dispatch; it had to run synchronously inside this session (Grunt, by hand) instead. | not separately timed — this is why the whole A-479 non-test-pieces task ran in this session rather than in parallel | Yes, provisionally. This reads as a deliberate model-capability policy (consistent with the same day's later, explicit owner rule that Sonnet does not write code), not a bug. Real cost, but likely intended. |
| ~23:0x–23:1x | `coordination.py claim`/`who`/`assignments --mine` refuse class `capability` for a self-bound (non-dispatched) interactive participant (this session, PT-23) with no `COORDINATION_CAPABILITY` in its shell env, because shell env does not persist between tool calls and this session never re-exported it. Cost: one full message round-trip to the XO to locate the credential file (a 65-byte mode-600 file already sitting in this session's own scratchpad the whole time). | ~5–10 (one cross-session round trip) | Partially. The #267 capability hardening itself is sound (it is what stopped an unauthenticated claim); the friction is that an interactive session has no documented, discoverable way to find or re-supply its own already-minted capability across tool calls — that's a usability gap around a correct control, not the control itself. |
| this session, twice, before this window (21:00Z) | Commit-message trailer rejection: a blank line between `Source:` and `Co-Authored-By:` demoted `Source:` to body text, rejected by the `commit-trailers` hook both times, same cause both times. Noted because asked for, but timestamped before 21:00Z, so outside strict scope. | ~1 each (a re-write of the message file) | Yes. The hook is correct; the cost is a session not yet knowing the trailer-block rule, which is exactly what a fix-once, recur-never mechanism should prevent — worth checking whether this pattern has a fixture yet. |
| ~23:2xZ (A-479 handback chain) | After this session released A-479 back to the store (generation 4, "offered"), `offer` and `reassign` both refuse to act on an assignment already in state `offered` — so routing it to the Opus builder required drafting a brand-new assignment, A-491, instead of simply re-offering or reassigning the existing one. | ~5–10 (one extra draft/offer cycle, plus the coordination overhead of two assignment ids now referring to the same work) | No. This is a state-machine gap: "offered" should accept a reassign/re-offer from a lead/coordinator; forcing a fresh assignment id for the same work fragments the audit trail across A-479 and A-491 for no safety benefit. |
| ~23:1xZ | The XO's own attempt to hand the Opus builder (PT-32) a hand grant by having it self-declare from the owner's *relayed* words; the builder correctly refused (a peer message cannot carry a grant). | ~2 (one refused attempt, corrected immediately) | Yes, cleanly. This is the grant boundary working exactly as designed — the low-cost, correct outcome of a control that must not be bypassable by relay. |
| ~23:1xZ | The XO's example `deliverable.py` lock measure used `&&` without `sh -c`; `deliverable.py` runs measures through `shlex.split` with no shell, so it read `unreachable` (exit 129) until the builder re-set it under `sh -c`. | ~2 | Yes/neutral. Not a constraint at all — a one-off authoring mistake in an example, already self-corrected. |
| repeated, this session, small | Hook-classifier denials on this session's own code-search commands: `graft-first` (a two-file `grep` for `ro-bind` refused, redone through `graft.py query`) and `clipped-sweep` (a multi-alternation `grep` refused, redone as a single-pattern `grep`). Each cost one extra tool round-trip. | ~1 each, several times today | Yes, provisionally — both catch a real class of mistake (truncated-evidence greps, ungrafted code search) cheaply; the cost is proportionate to the round-trip, not to lost work. |
| named by the XO, not independently located | LD-116 (99 fixture rows launched write jobs with no `--for` and never met the intended denial; fixed today, author-tests family suite time rose 87.3s→119.5s once the rows went red-then-green) and "the walkthrough row" — both real per the XO's own AAR notes, but I could not independently pin exact clock timestamps for either inside the time this task had. Declaring the gap rather than guessing a number. | unmeasured | LD-116: no, a real enforcement gap now fixed. Walkthrough row: unmeasured, no verdict given. |

LD-116, LD-117, LD-119, LD-120, LD-121, LD-122 are referred to above by the
numbers the Lead/XO used; as of this reading none of LD-116–LD-122 appear
in the shared ledger (`ledger.py list defects` tops out at LD-113). Looked,
not found — the numbers are live in conversation and in the XO's own notes,
not yet filed as store rows. That gap is itself worth a line in the ranked
list below.

## Ranked: loosen or remove

1. **Forward-merge-into-a-live-dispatch's-branch (LD-119 class).** Smallest
   change: before a forward-merge lands on a branch, check the dispatch
   store for an open record whose `unit`/`lineage.branch` names that
   branch, and refuse or warn. Not a wall path (`ops/devlane/dispatch/`
   dispatch-side logic, not `ops/bin/suites.sh` or the hook engine) —
   wait: `launch.py` and the merge-side tooling that would carry this
   check are ordinary lane tools, not the CI/test/hook-registry wall
   list; a guard living in a pre-merge helper script is not wall either.
   Highest-ranked because it struck twice today by two different routes
   (this session's own finding, and the XO's own merge) and taints an
   audit's findings, not just wastes compute.
2. **The 1800s author-tests kill with no drain (A-483 class).** Smallest
   change: on the timeout signal, `git add -A && git stash create` (or an
   equivalent uncommitted-diff export) before SIGKILL, so a killed job's
   work is never simply gone. Not a wall path — this is in `launch.py`'s
   own timeout handling, not the wall list `AGENTS.md` names.
3. **`DISPATCH_TIMEOUT` admitted verbatim, unclamped to the job cap
   (`launch.py:1934-1942`).** Smallest change: `min(DISPATCH_TIMEOUT, job
   cap)` rather than an outright override. Not a wall path.
4. **A-479/A-491-style fragmentation: `offer`/`reassign` refuse from
   `offered`.** Smallest change: let a lead/coordinator's `reassign` or
   `offer` act on an assignment already `offered` (re-target it) instead
   of only on `drafted`/`held`. This is `ops/conductor/tools/
   coordination.py`, not wall.
5. **The interactive capability-discovery gap.** Smallest change: a
   read-only `coordination.py where-is-my-capability` (or a documented,
   fixed scratchpad filename) so a self-bound interactive session doesn't
   need a cross-session round trip to find a file it already wrote for
   itself. Not wall.
6. **LD-116–122 unfiled in the shared ledger.** Smallest change: none to
   any guard — just run `ledger.py add defect` for each once this record
   lands, so the numbers already in use stop being conversation-only.
   Not wall, not even code; a bookkeeping catch-up.

Nothing above argues for loosening the claude-write-dispatch refusal, the
peer-cannot-grant boundary, or the graft-first/clipped-sweep search
guards: each is judged, above, to have earned its cost today. The amend
guard's cwd bug (LD-117) is already fixed on `dev`, so it drops off this
list; it is kept in the table above only because it was asked for by name.
