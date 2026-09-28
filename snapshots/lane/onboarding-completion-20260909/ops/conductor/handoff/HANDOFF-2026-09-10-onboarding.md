# Handoff — onboarding work stopped by the owner

Author: GPT-6 Astra. Measurement: `2026-09-10T03:05:33Z`, integration head
`e1a2ae0267292d0c50b7080ceede1401799c06bf` before these closeout documents.
See the [AAR](../AAR-2026-09-10-onboarding.md) for the causes and
[state capture](evidence-2026-09-10-onboarding/state.json) for exact refs,
commands, dispatch records and source hashes.

## Current instruction and outcome

**STOPPED, not completed.** The owner said, "if its not's close to done -
then stop". The response acknowledged that it was not close and stopped
the task. The subsequent instruction was "do up a AAR and handoff".
That authorizes these documents, not another implementation or review run.
No next session should interpret this handoff as permission to resume.

The requested result remains reliable, quick onboarding using the actual
tools/features/MCP, effective watchdog and monitor use, safe concurrent
sessions with limitations disclosed, and purposeful bounded loops. The
owner did not require a new policy engine, execution replacement or MCP
version redesign. Design choices in drafts are not additional requirements.
The other session owns Git/GitHub synchronization and the general
suggestions-versus-requirements correction; coordinate before adopting its work.

## Where everything is

Worktree parent on this machine:
`/home/scientdb/projects/uscient/wt/`. All branches below are preserved.
Do not switch branches in the main checkout or overwrite another session's
worktree. The full SHA and path for each row is in the state capture.

| Worktree suffix | Branch suffix after `lane/` | Measured tip | Purpose |
|---|---|---|---|
| `ag-onboarding-completion-20260909` | `onboarding-completion-20260909` | `e1a2ae0` | Primary integration; filename fix plus records and proposed startup contract |
| `ag-onboarding-brief-inputs-fix-20260910` | `onboarding-brief-inputs-fix-20260910` | `1601d95` | PR #78 code, corrected tests and later code-review record |
| `ag-onboarding-brief-inputs-20260910` | `onboarding-brief-inputs-20260910` | `846660a` | Independent filename tests and test-review/stop records; no launcher fix |
| `ag-onboarding-contract-20260910` | `onboarding-contract-20260910` | `7c2373c` | Earlier unaccepted startup contract and correction records |
| `ag-onboarding-discovery-20260910` | `onboarding-discovery-20260910` | `9ac5685` | Unfinished discovery attempt; not a mandatory onboarding prerequisite |
| `ag-onboarding-policy-20260910` | `onboarding-policy-20260910` | `ad0b6b9` | Unfinished policy attempt; not a mandatory onboarding prerequisite |

The corresponding `ag-onboarding-discovery-tests-20260910` and
`ag-onboarding-policy-tests-20260910` worktrees are preserved at `31fff00`
and `32e77a0`; no follow-up job was launched from those test worktrees in
this stopped batch. Main checkout was on `dev` at `20f9bca`.
The other session's `lane/dev-freshness-20260909` was at `c334d1e` when
read; this handoff makes no claim that its work is complete or integrated.

Local dispatch custody:
`/home/scientdb/.local/state/agentscient/dispatch/<ID>/` contains
`record.json`, `state.json`, `snapshot/`, `in/`, `out/` and raw captures.
Read the record before considering any snapshot or artifact for adoption.
An `invalid` envelope is not approval; recoverable bytes are not completion.

## Filename fix: useful but still draft

[PR #78](https://github.com/uscient/agentscient/pull/78) targets `dev`.
Published head: `b2c0ce57ee9173d0fbc30f78b9c952131c4e18e4`.
At measurement it was OPEN, draft, with `lane`, `app`, `Analyze (actions)`
and `CodeQL` successful. The local tip `1601d95` adds the review record;
it is not the published head. There is no onboarding-runtime PR in this
handoff; PR #78 covers worker input filenames only.

The final change appends the ordered copied input paths to the worker
prompt in `ops/devlane/dispatch/launch.py`, before its digest is recorded.
It adds nothing for empty inputs. `jobs.json` is unchanged. The earlier
six-template patch broke the task renderer and is not the adopted fix.
Implementation source: `644a96c7507e3e010a8e42a19cf9a0dff542edc4`;
integration commit: `c7b998acd15c1e89229fd2ee7ce1c296e8f525dd`.

| Record | Result and remaining significance |
|---|---|
| `20260910T012416Z-code-codex-25d0b4` | Final implementation; preserved full-suite log reports nine suites OK |
| `20260910T014231Z-review-grok-090298` | APPROVE at published head; zero findings, two explicitly optional observations |
| `20260910T014232Z-check-tests-codex-bf8dfe` | CHANGES against independent tests at `10caff0`; two demonstrated test defects |
| `20260910T013051Z-review-claude-5baf17` | Timed out without a verdict; scope also referred to the earlier implementation shape |
| `20260910T015010Z-tests-grok-f871ba` | Final test correction stopped at owner's instruction; no changed or residual paths |

The remaining test findings are: the empty-input assertion misses an
invented `Input files: in/guessed.md` list; its `Inputs:` regex consumes
newlines and rejects a valid empty header followed by a separate instruction.
The [test report](evidence-2026-09-10-onboarding/filename-test-review.json)
preserves both reproductions. The executable reproducer is
`out/probe_empty_prompt.py` under the test-review dispatch. The
[code report](evidence-2026-09-10-onboarding/filename-code-review.json)
must remain distinct from that test verdict. Do not silently convert its
duplicate-list suggestion into another requirement.

The integration worktree has the runtime filename fix but has not merged
the later independent test corrections and their review records. Re-measure
both branches before combining anything. Review stamps and suite evidence
do not automatically transfer to a new merge.

## Onboarding: what remains unimplemented

`ops/conductor/session-start.md` was added at `0a212e9`. It describes a
possible small session launcher, per-session monitor state, native hooks,
job tracking and an MCP wrapper. **None of its proposed runtime files
exists in the integration tree.** It is unreviewed, not an installed service
or a required architecture. Its 30-minute idle lease and eight-hour ceiling
are chosen draft defaults, not numbers supplied by the owner.

The independent startup test dispatch `20260910T015009Z-tests-grok-9f80d3`
was stopped with no changed or residual paths. It delivered no test suite.
Earlier attempts remain available for reference:

- Contract author `20260910T001134Z-code-codex-712230`; malformed verification
  command failed, authored documents preserved.
- Contract review `20260910T005208Z-review-codex-9b1fec`; CHANGES.
- Correction `20260910T010615Z-code-codex-9e6040`; successful no-op, not a fix.
- Correction `20260910T010956Z-code-codex-cedae4`; timed out, unaccepted draft.
- Discovery `20260910T001358Z-code-codex-6d01cf` and policy
  `20260910T001531Z-code-codex-b9d9bc`; unfinished, not integrated.

Useful earlier observations, requiring fresh verification if resumed:
the existing onboard command prints a brief without starting supervision;
the connected MCP configuration used old explicit job/state bindings and a
shared consumer; native Codex session identifiers were available to tool
processes but absent in the observed MCP children. Local client probes
established some MCP plumbing, not complete onboarding or alert receipt.
Native hook trust and actual host delivery were not completed or validated.
Do not bypass host trust or describe synthetic probes as live host proof.

## Stopped processes and preserved state

Both final workers closed at `2026-09-10T01:53:20Z` after SIGTERM to their
verified owned process groups. Their launchers collected the terminal
records. Watchdog PID `2117176` and monitor PID `2117153` were stopped;
both were absent on recheck. The captured records' worker PIDs were also
absent. These are checks of this task's processes, not a global statement
that no other session has running work. Never reuse these old PID numbers
as instructions to kill a process.

The stopped monitor's config and state remain at
`/home/scientdb/.local/state/agentscient/monitor-onboarding-20260910/`;
its consumer was `onboarding-20260910`. Its existence does not mean it
is running. Stop record:
`/home/scientdb/.local/state/agentscient/onboarding-stopped-20260910.json`.

## Conditional continuation, only after the owner resumes work

First re-measure branches, PR status, open dispatches and ownership. Read
the current `AGENTS.md` and `ops/README.md`; dev tooling does not depend on
the Symfony application or Mate. Use isolated worktrees and the existing
dispatch/landing levers. `--branch` chooses a lineage; it does not change
the dispatch command's working directory.

Then resolve the filename test findings using their preserved reproducer
and the applicable independent-producer rules. Reuse existing artifacts
where justified; do not replay every previous review merely because it
appears in the history. Use `ops/bin/suites.sh` for a fresh suite claim
on the actual candidate. PR readiness still needs its normal evidence;
the stopped task did not earn it.

For onboarding itself, the recommended delivery target is one actual
startup path that discovers existing capabilities, starts and checks its
coverage, delivers a real failure observation, and works with two concurrent
sessions without cross-acknowledgement or cross-shutdown. Determine the
smallest implementation from the current working tools. The abandoned
drafts are evidence to consult, not a backlog to finish automatically.

## Custody limits and explicit items left behind

This handoff includes selected hashed record summaries, exact GitHub query
output, the two final review envelopes and historical suite summaries.
It does not copy raw model transcripts, isolated homes or all snapshots
into Git; those remain in the local dispatch store named above. Original
suite logs remain at the paths and hashes in the state capture. Nothing
was deleted, rebased or cleaned up as part of stopping or documenting.

Scratch materials remain under `/tmp/agentscient-onboarding-20260909/`:
scopes, owner-message excerpts with assistant interpretations, verifier
scripts, host evidence, client probes, schemas and watcher logs. These
are machine-local and may disappear. Their expanded prose must not be
attributed verbatim to the owner. The authoritative stop/resume boundary
is stated above; the original user messages remain the authority.

No new probe corpus or deterministic handoff-runner pass was produced.
The retained capture and explicit custody limits are the handover evidence;
they are not a claim that a new session has successfully onboarded.
