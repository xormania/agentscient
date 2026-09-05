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

## Independent tests and rulings

Measured from canonical records on 2026-09-05 at
`5f599f8afaab50d0b86f49071a011c463a102460`:

| Dispatch record | Producer | Result |
| --- | --- | --- |
| `20260905T062201Z-code-grok-ee8e0d` | Grok 4.6 | Accepted test-author envelope; 16 new test methods; landed at `a8a8529` |
| `20260905T064157Z-review-codex-159ebd` | gpt-daybreak-blue-latest | Accepted skeptic CHANGES: three P1 and four P2 assertion gaps |
| `20260905T064859Z-code-grok-81b772` | Grok 4.6 | Accepted correction envelope; landed at `c9bf44e` |
| `20260905T071031Z-review-codex-fae2b5` | gpt-daybreak-blue-latest | Accepted independent ruling: UPHELD root's note-removal fixture finding |
| `20260905T071425Z-code-grok-d8ea5f` | Grok 4.6 | Accepted narrow fixture correction; landed at `5f599f8` |

The [skeptic report](mcp-test-skeptic-2026-09-05.md) is verbatim. Its printed
model stamp is retained; the dispatch record identifies the actual model.
GPT-6 produced neither the tests nor the skeptic findings and
[upheld all seven](mcp-test-ruling-2026-09-05.md) before any correction.

Root then found that the note-removal fixture's whole entry fit within
8192 bytes while its reduced entry was larger: 8163 versus 8193 bytes.
The [independent ruling](mcp-note-fixture-ruling-2026-09-05.json) upheld
that error before Grok changed the fixture. The corrected fixture uses
within-cap text and asserts that the whole entry and each reduction exceed
the page bound, while the frame and the no-note fallback fit.

At `5f599f8`, root ran
`python3 -m unittest test_lane_mcp_context.TestLaneMcpContextFindingsGaps.test_lane_findings_note_removal_after_whole_and_intermediate_forms`
from `ops/conductor/tests`. All fixture inequalities passed before the
expected v1 configuration refusal: v2 was not implemented yet. The final
independent test file has SHA-256
`facd775d07bc6eeba6e12e19afd99026b3f80980442d534677f57ab0bc4e9e6e`.
This verifies the targeted correction, not a second skeptic verdict.

## Implementation and final review custody

The implementation producer neither writes nor approves its tests. Final
reviews run from separate worktrees at the candidate commit, so recording
their results cannot move it.

All delegation uses `ops/bin/dispatch.sh`; writes land through `land.py`.
Whole-tree snapshots contain the existing implementation and historical
records. Test and skeptic prompts withhold implementation reads; physical
withholding is not claimed. No new feature implementation exists at the
first test snapshot.

Final evidence will include suites and CI, independent review records,
fixed-task answer checks and serialized response bytes. Bytes are not billed
tokens; tool-schema overhead is reported separately.
