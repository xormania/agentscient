# Named-card correction closeout — 2026-09-05

Candidate `ac29ca8f79beb0b285884d7bf7f6635f34275c67`; fix `67e0bc0`.
Measured from canonical records and command logs on 2026-09-05.

- Grok 4.6 quality review `20260905T221346Z-review-grok-7662b2`:
  accepted APPROVE, no findings, all 50 MCP tests passed. Its scratch
  restoration of the old condition reproduced the named/missing lookup
  defect. Additional probes covered 64, 65 and 200 entries, an oversized
  source, CLI/tool/resource parity and the v1 four-tool surface.
- Daybreak security review `20260905T221355Z-review-codex-d51502`:
  accepted APPROVE, no findings. In-memory probes checked named/missing
  reads, list refusal, no-follow reads, prompt withholding and byte bounds.
  Its read-only sandbox could not run fixture tests. Its stated provenance
  inspection limits remain in the canonical record; they are not passes.
- `bash ops/bin/suites.sh` at the candidate: 1,911 tests across nine
  suites, six skips. Ruff, closure, literals, term wall and diff checks
  passed; closure explicitly skips `ops/devlane/infra`.
- [CI run 33995353049](https://github.com/uscient/agentscient/actions/runs/33995353049)
  passed lane and app. Its log records 1,911 lane tests and checkout of
  merge `b50396cf1f2fa0e0e5a4a0c035d27036aeb9f3be`; PHP checks passed,
  while PHPUnit explicitly reported no tests. Actions analysis and CodeQL
  also passed in [run 33995351001](https://github.com/uscient/agentscient/actions/runs/33995351001).
- `git merge-tree --write-tree origin/dev HEAD` at the candidate and
  `git show -s --format=%T b50396c` both yield candidate tree
  `76080efaa63118f17ffa004c1a52dc85f45c6166`, with dev at `7a6a1a7`.
- The fixed-task report's executable Python block was rerun at the candidate.
  Its [captured JSON](mcp-cap-evaluation-ac29ca8-2026-09-05.json) preserves
  current code/source hashes and response bytes; all source answers and
  CLI/tool/resource projections agreed.

These reviews recheck the correction at the new head. Whole-feature reviews
and prior nonblocking dispositions remain historical evidence at `e7558de`.
No new finding needs adjudication. Review records and this evidence live on
retained separate branches, leaving the feature head stationary.
