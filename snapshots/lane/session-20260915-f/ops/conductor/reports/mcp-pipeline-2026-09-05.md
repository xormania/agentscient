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

## Landed implementation and integration

`20260905T072301Z-code-codex-6a6ca4` ran `gpt-5.6-sol` and returned an
accepted implementation envelope. Only the two existing production modules
and the v2 example changed; the launcher committed its preserved COMMIT_MSG
because the worker could not write the snapshot's git metadata. The change
landed at `92be7d1`. The independent test file's SHA-256 remained exactly the
admitted value above.

While this branch was active, `dev` advanced to `56b26b5` with JSON parsing
guards. Merge `572a901` retains those guards. The sole conflict was resolved
by preserving both the upstream depth check and the feature's exact-byte
capture, before decoding in the shared record reader. This integration adds
no new parsing policy. It is included in final independent code review.

At `572a901a503e71ea3b255a8292e30515d5096529`, root ran the MCP discovery
command: all 49 tests passed. `ruff check .`, `laneconf.py closure`,
`laneconf.py literals` and the term wall passed; closure explicitly skips
`ops/devlane/infra`. The [fixed-task evaluation](mcp-context-evaluation-2026-09-05.md)
matched the selected source answers through CLI, tools and resources and
measured full MCP response overhead. The exact executable command and source
hashes are retained there. Final suite and review results are recorded on the
PR at its stationary head, so their records do not move the reviewed tree.


## PR 72 named-card correction

The owner requested correction of the GitHub review's named-card P2.
GPT-6 [upheld the finding](mcp-named-card-cap-ruling-2026-09-05.md)
before resuming this pipeline. The contract already separates named cards
from unnamed listings; no new contract or feature scope was needed.

Measured from the canonical dispatch records on 2026-09-05 at
`67e0bc0219287dc98d7b1b67c3d7b15dbd07ecf5`:

| Dispatch record | Actual producer | Result |
| --- | --- | --- |
| `20260905T215513Z-tests-grok-f2787b` | Grok 4.6 | Accepted; new 65-entry regression red; landed at `868a420` |
| `20260905T220422Z-check-tests-codex-b852fb` | gpt-daybreak-blue-latest | Accepted APPROVE; no findings; reproduced the intended red and checked fixture guards |
| `20260905T220642Z-code-codex-3fe449` | gpt-5.6-sol | Accepted; one production condition changed; all 50 MCP tests and targeted Ruff passed |

The [skeptic report](mcp-named-card-cap-skeptic-2026-09-05.md) is preserved
byte-for-byte (SHA-256 `f3d23cfaeaa1d41ecfe170ea129ee8c42368c1be5cbf85fd027a41a42b37e382`). Its self-printed generic model name
is retained as captured; the actual model above comes from the dispatch
record. The test and skeptic prompts prohibited implementation reads;
whole-tree snapshots were not physically stripped of implementation.

The implementation changed only the listing guard to
`name is None and len(registry) > 64`. The new row covers a known card
through CLI, MCP tool and resource, the unchanged list refusal, and an
ordinary missing-name answer. Source and complete-query bounds remain.
The independent test file's SHA-256 before and after implementation is
`116143b39212518d82ff412b31f9bc862be2f26b82fb83062a2eba5e65336e16`.

The worker's command
`python3 -m unittest discover -s ops/conductor/tests -p 'test_lane_mcp*.py' && ruff check ops/conductor/tools/lane_read.py`
passed all 50 tests at its resulting tree. The launcher committed the
worker's patch because its sandbox denied git metadata writes. Root landed
it through `land.py`, then amended only the unpublished commit message to
retain honest finder/reviewer credit: GitHub does not disclose that bot's
underlying model. The final fix commit is `67e0bc0219287dc98d7b1b67c3d7b15dbd07ecf5`.

Merge `228d3e8` incorporates the owner's released dev history at `7a6a1a7`;
that merge introduced no tree change. PR 71 has been merged by the owner.
Fresh local suite, CI and correction-review evidence will be recorded on
PR 72 at its stationary candidate, with review records on separate retained
branches so their publication cannot move it. Earlier reviews remain
historical evidence at their explicitly named heads.
