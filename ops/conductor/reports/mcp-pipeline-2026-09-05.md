# Conductor MCP pipeline — 2026-09-05

The owner requested research into useful MCP tools from the project's logs,
reports and Internet sources, then "conduct the pipeline and make a new PR
for it". The [scope](../mcp-context-scope.md) and
[research](../MCP-RESEARCH-2026-09-05.md) record that work.

## Contract admission and execution choice

GPT-6 admits [the extension contract](../lane-mcp-v2.md) for this pipeline
under that instruction, after the independent ruling below. Claude Fable 5.1
produced the proposed design; GPT-6 applied the independently upheld
corrections before tests. The founding read-only boundary remains binding.

The Fable plan's multiple PRs and automatic ladder fixes do not match the
authorized route. This work uses one branch and one PR, with dispatch/land
stages and an adjudication pause on changes. The production/config scope is
the two existing MCP modules plus the v2 example: three files, one declared
S implementation bucket. One focused independent test file can cover the
complete surface. This groups the behavior slices without relaxing their
assertions. Actual duration will be recorded rather than inferred from S.

The durable design is discharged into the extension contract. The saved
plan's work order and estimates remain historical dispatch artifacts; future
changes must not cite them as law. No successful planner envelope is created
on a worker's behalf.

## Planning and ruling evidence

| Dispatch record | Producer | Measured result |
| --- | --- | --- |
| `20260905T053939Z-review-claude-29bbe4` | Claude Fable 5.1 | 600-second timeout; saved contract, no plan or envelope |
| `20260905T055149Z-review-claude-895f15` | Claude Fable 5.1 | 600-second timeout; saved corrected contract and complete plan, no final envelope |
| `20260905T060513Z-review-grok-d03ab4` | Grok 4.6 | 300-second timeout; no ruling/verdict; usage unavailable, not zero |
| `20260905T061214Z-review-codex-1e772e` | gpt-daybreak-blue-latest | Exit 0; completed rulings in structured response; self-reported tripped because its read sandbox denied the separate RULING.md write |

The launcher's `_collect` was inspected and accepts only failed write jobs.
These read artifacts were inspected directly. The Daybreak response is
[preserved verbatim](mcp-plan-ruling-2026-09-05.json). It is a recovered
adjudication artifact, not an accepted green review run. The canonical record
has `attempts[0].tripped: false`; the tripped label came from the response,
not a fired supervisor battery.

| Finding | Ruling | Applied disposition |
| --- | --- | --- |
| C1: exact launcher-equivalence claim and withheld predicate | Daybreak UPHELD | Limited structural assessment, actual truthiness, explicit unmeasured launch preconditions |
| C2: fitting frame does not prove an entry fits | Daybreak UPHELD | Remove note if needed; then unavailable if a reduced entry still cannot fit; never skip or advance past it |
| C3: multiple PRs, automatic fixes, global Unicode promise | Daybreak UPHELD | One PR with adjudication pauses; new Unicode promise limited to new returned fields |
| C4: invalid registry keys contradict Unicode guarantee | New Daybreak finding; GPT-6 UPHELD | Null name and false dispatchable mark the invalid row; malformed key is never echoed |

Verification at `f9b4d704c387825349d7cd5aa116cc275d3eb135`:
`launch.py:1092` uses `job.get("withheld")`; `Driver.run` enters fixes
directly on changes; v1 alert evidence can contain surrogate escapes.
A scratch canonical-JSON reproduction measured 8191 bytes for a valid frame
and bounded note, then 8297 after adding a reduced entry. `json.loads`
accepts a surrogate key which fails UTF-8 encoding. C4's adjudicator produced
neither the Fable artifact nor the Daybreak finding.

## Remaining stages and custody

Tests, a test skeptic, implementation, quality review and security review
follow as separate stages. The implementation producer neither writes nor
approves its tests. Final reviews run from separate worktrees at the candidate
commit, so recording their results cannot move it.

All delegation uses `ops/bin/dispatch.sh`; writes land through `land.py`.
Whole-tree snapshots contain the existing implementation and historical
records. Test and skeptic prompts withhold implementation reads; physical
withholding is not claimed. No new feature implementation exists at the
first test snapshot.

Final evidence will include suites and CI, independent review records,
fixed-task answer checks and serialized response bytes. Bytes are not billed
tokens; tool-schema overhead is reported separately.
