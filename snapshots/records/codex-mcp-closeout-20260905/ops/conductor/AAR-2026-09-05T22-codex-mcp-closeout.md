# AAR — Codex README, conductor MCP and review closeout, 2026-09-05

GPT-6, closing at the owner's request to start a new session. Repository
state was remeasured at 2026-09-05T22:39:00.218086+00:00 against dev
`c06ed9442ba51c9e96aa8de9f9bde93d0843a6cc`. The
[measurement record](handoff/evidence-2026-09-05-codex-mcp/measurements.json)
contains commands, selected results, exact refs and correction-run counters.
The [handoff](handoff/HANDOFF-2026-09-05-codex-mcp-closeout.md) is the
next session's entry point. Earlier reports keep their original baselines.

## Outcome against the owner's requests

| Request | Result and evidence |
| --- | --- |
| Onboard from the earlier Codex closeout | Read the retained `records/codex-closeout-20260905` handoff at `ce2bbf9`; treated older queues as history, not an automatic work order. |
| Write an accurate, thorough repository README and merge into dev | [PR70](https://github.com/uscient/agentscient/pull/70), head `5f80cbe`, merged at `c91d47a` on 2026-09-05 05:19:53Z. The feature PR subsequently updated the README for its new MCP surface. |
| Open a draft release from dev into master; owner merges | [PR71](https://github.com/uscient/agentscient/pull/71) was delivered as a green draft. It was subsequently merged at `0b1f1b6` on 2026-09-05 21:24:54Z. This session did not merge master. |
| Research useful MCP tools from project evidence and Internet sources; conduct the pipeline and open a PR | [PR72](https://github.com/uscient/agentscient/pull/72) implemented three opt-in reads and resource projections. It was delivered green and unmerged, then merged at `c06ed94` on 2026-09-05 22:24:46Z. |
| Inspect PR71 comments and resolve review threads | Verified the existing parsing corrections, replied with evidence and resolved both threads. |
| Fix the PR72 named-job finding | Independently upheld the P2, obtained red tests and skeptic approval, landed the one-condition fix, passed fresh reviews and CI, and resolved the thread. |

At close, GitHub returned no open PRs. All three reviewed threads on PR71/72
were resolved. Post-merge dev CI
[33995834974](https://github.com/uscient/agentscient/actions/runs/33995834974)
passed lane and app at `c06ed94`; post-merge CodeQL run
[33995834945](https://github.com/uscient/agentscient/actions/runs/33995834945)
also succeeded. Master remains `0b1f1b6`; the MCP feature is newer dev work.
No subsequent release PR was opened in this closeout.

## What the MCP work established

The [research](MCP-RESEARCH-2026-09-05.md) names fourteen candidates and
keeps its measured corpus boundary: 247 canonical records, 877 selected
artifacts, tracked lane text and deduplicated handoffs. It used full byte
and structured-data scanning plus targeted semantic reading. It does not
claim semantic review of every repeated prompt. Of 2,226 finding entries,
1,698 were implementation command diaries labelled P3; those totals are
not defect counts. Primary Internet sources are cited in the research.

The admitted [v2 contract](lane-mcp-v2.md) adds `lane_findings`,
`lane_changes` and `lane_jobs` to the shared CLI/MCP read service. It keeps
explicit source selection, read-only local access, bounded responses and
v1's four-tool configuration. The implementation also accepts object-valued
request `_meta`. This Python incumbent does not establish new Symfony API
or TUI projections; the four-projection ruling remains the future twin's
boundary, not an unimplemented capability claimed by this PR.

The fixed-task evaluation at `ac29ca8` matched source answers through CLI,
tool and resource. Complete MCP response/raw-source byte pairs were
3,678/7,010 for a finding, 1,042/13,087 for an unchanged checkpoint and
1,334/13,043 for a job card. Tool discovery added 835 bytes. These are
bounded examples, not billed-token savings or a comparison with an optimal
shell filter. The [current capture and closeout](https://github.com/uscient/agentscient/blob/216420e13ebdc6db321b294010e8c1a90e6d6262/ops/conductor/reports/mcp-cap-closeout-ac29ca8-2026-09-05.md)
retain commands, hashes and limitations.

## What worked

- Contracts settled the review dispute. Section 5 separately defines named
  cards and unnamed listings. The 64-entry cap belonged only to listing;
  unrelated jobs must not prevent a bounded named lookup. Fix `67e0bc0`
  changes the guard to `name is None and len(registry) > 64`.
- Independent producers made the correction reviewable. Grok authored the
  regression, Daybreak approved it and reproduced the red, and GPT-5.6 Sol
  changed production. The test-file hash stayed
  `116143b39212518d82ff412b31f9bc862be2f26b82fb83062a2eba5e65336e16`.
  Grok later restored the old guard in a scratch copy and reproduced the bug.
- The final target held still. Fresh Grok quality and Daybreak security
  reviews approved `ac29ca8` with no findings. Their records were published
  on separate retained branches. The full suite passed 1,911 tests across
  nine suites, six skips, locally and in PR CI. The PR merge tree matched
  the candidate tree. Daybreak's inability to run fixture tests in its
  read-only sandbox remained explicit, separately from executable CI proof.
- Review was evidence, not authority to edit. Findings were ruled on before
  changes. Earlier CHANGES verdicts remain visible with their dispositions;
  the final correction did not reopen unrelated P3 hardening.

## What cost too much, and what should change next

The five named-card correction dispatches reported 6,541,390 total tokens
and 65,125 output tokens in their canonical `spend` counters:

| Stage / record | Actual model | Reported total | Reported output |
| --- | --- | ---: | ---: |
| tests / `20260905T215513Z-tests-grok-f2787b` | grok-4.6 | 1,124,143 | 16,034 |
| skeptic / `20260905T220422Z-check-tests-codex-b852fb` | gpt-daybreak-blue-latest | 408,786 | 5,494 |
| code / `20260905T220642Z-code-codex-3fe449` | gpt-5.6-sol | 595,831 | 5,690 |
| quality / `20260905T221346Z-review-grok-7662b2` | grok-4.6 | 2,167,099 | 23,176 |
| security / `20260905T221355Z-review-codex-d51502` | gpt-daybreak-blue-latest | 2,245,531 | 14,731 |

This sum is repeated harness context accounting, including cache activity;
it is neither unique input volume nor normalized billing. It excludes the
root session and the earlier full feature pipeline. Those whole-session
usage totals were not measured. The one-condition correction still caused
substantial onboarding and repeated review context. Narrow input diffs did
not physically restrict the whole-tree snapshots or remove the launcher's
whole-feature diff. The existing tests/skeptic roles prohibited implementation
reads by prompt; physical withholding was not proved and is not claimed.

The next useful improvement is a bounded review/handoff evidence packet:
exact head and base, relevant contract clauses, selected diff, admitted
oracle, prior finding dispositions and missing evidence. It must carry
provenance and explicit omissions, and be assessed against the same task
with measured bytes and upheld findings. This is a proposed follow-up to
the research's packet/artifact-index candidates, not permission to bypass
review or invent a new pipeline. A narrow dispatch-precheck read could also
avoid the unsupported `--base` wrapper attempt seen during this correction.
Polling and wide reads in the root session also need discipline; new tools
only reduce waste if the conductor actually consumes their bounded outputs.

## Authorization and operational lessons

The owner asked Copilot to review PR71 at
[05:32:41Z](https://github.com/uscient/agentscient/pull/71#issuecomment-5549695114).
Copilot authored parsing-fix commit `56b26b5` at 05:35:41Z and
[reported applying it](https://github.com/uscient/agentscient/pull/71#issuecomment-5549721813).
The owner was upset by that write. A review request is not authorization to
push a fix to dev. This session inspected and verified that already-landed
commit, resolved the requested threads, and did not rewrite its history.
Its missing Source/model trailers remain a historical provenance gap.

A green repository is not proof that the host is using its current code.
At close, `agentscient_lane` still pointed to checkout `eb4eb53`, with a v1
configuration selecting seven job IDs and only four advertised tools. The
connected `lane_brief` call returned MCP `-32602 Invalid params`; the saved
entry's direct CLI query exited 0 with state `ok`. The cause of the host
failure was not established. That older checkout predates the merged
metadata handling, which is a concrete place to investigate. No host
configuration or running server was changed in this session.

The earlier handoff's watchdog and monitor liveness must not be inherited.
A close-time process scan found no argv matching the documented
`/tools/watchdog.py` or `/tools/monitor.py` entrypoints. It did not inventory
alternate entrypoints or prove why these processes disappeared. All five
correction dispatches are closed; this is not a claim that the whole machine
has no other actor. No monitor state, branch or worktree was deleted.

## Calibration

- Start with [this handoff](handoff/HANDOFF-2026-09-05-codex-mcp-closeout.md).
  PR72 is merged, not awaiting merge. Re-fetch and measure remote state.
- The main checkout remains `c715b24` with the owner's untracked `.dev/wip/`.
  Use a fresh owned worktree from current origin/dev. Preserve existing data.
- New MCP reads are merged into dev, but the saved host entry is still v1
  on an older checkout and its connected brief failed. Verify the runtime
  and request boundary before claiming those tools are available to a host.
- Keep functionality first. Deferred encoding/depth gaps are named in the
  handoff; they are not automatic blockers or an unsolicited next work order.
- Dispatch through the lane, keep test/implementation producers separate,
  rule on findings, and pin reviews to the actual candidate. Review does not
  authorize a trunk write. Owner alone merges master.
- This closeout is retained on `records/codex-mcp-closeout-20260905`; it is not
  merged into dev. A default dev checkout will not automatically serve this
  newest calibration. Read the retained handoff explicitly.
- The probe corpus covers critical custody facts. The production probe runner
  remains absent. Full transcripts, root usage and private runtime state are
  explicitly left behind as described in the handoff, not silently copied.
