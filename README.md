# Legacy records

This branch consolidates 21 records, review, closeout, and recovery branches from Agentscient. Use [dev](https://github.com/uscient/agentscient/tree/dev) for current development.

Each source is retained as an exact Git tree under `snapshots/<source-branch>/`. Full source trees keep records, evidence, saved patches, and their associated files together. Paths inside each snapshot retain their original structure. Separate snapshots preserve differing versions without overwriting them.

All source commits are parents of the archive merge, so their complete histories remain reachable after their source branch names are deleted. This is an archival consolidation; the snapshots are not combined into one runnable application.

## Records index

The 13 branches marked **unmerged records** had only record/evidence changes relative to their merge base with `dev`. The other eight were already merged and were retained for their record or recovery material; some also contain earlier source changes.

| Source branch snapshot | State at consolidation | Contents |
| --- | --- | --- |
| [`lane/session-20260915-f`](snapshots/lane/session-20260915-f/) | Previously merged | Merged session closeout: defects, pitfalls, probes, and an idea record. |
| [`lane/session-20260915-h`](snapshots/lane/session-20260915-h/) | Previously merged | Merged held-change patch bundle and probe reference. |
| [`lane/session-20260915-i`](snapshots/lane/session-20260915-i/) | Previously merged | Merged review record and probe corpus update. |
| [`lane/session-20260916-a`](snapshots/lane/session-20260916-a/) | Unmerged records | Unmerged defect records LD-71–LD-73 and review evidence. |
| [`lane/session-20260916-a87`](snapshots/lane/session-20260916-a87/) | Unmerged records | Unmerged dispatch evidence. |
| [`lane/session-20260916-c`](snapshots/lane/session-20260916-c/) | Previously merged | Merged package B after-action report. |
| [`lane/session-20260916-recover`](snapshots/lane/session-20260916-recover/) | Previously merged | Merged recovery after-action report and probe evidence. |
| [`lane/session-20260916-s2`](snapshots/lane/session-20260916-s2/) | Unmerged records | Unmerged scope and dispatch evidence. |
| [`lane/session-20260916-s3`](snapshots/lane/session-20260916-s3/) | Unmerged records | Unmerged scope and dispatch evidence. |
| [`lane/session-20260922-69`](snapshots/lane/session-20260922-69/) | Unmerged records | Unmerged review evidence and defects LD-140 / LD-148. |
| [`lane/session-20260922-d65f`](snapshots/lane/session-20260922-d65f/) | Unmerged records | Unmerged research handoffs, time-loss report, and session probes. |
| [`lane/session-20260923-87`](snapshots/lane/session-20260923-87/) | Previously merged | Merged history with a records-only probe correction at its tip. |
| [`records/agy-closeout-20260909`](snapshots/records/agy-closeout-20260909/) | Unmerged records | Unmerged after-action report, handoff, measurements, publication and probe evidence. |
| [`records/audit-remediation-20260910`](snapshots/records/audit-remediation-20260910/) | Previously merged | Merged audit remediation report, handoff and evidence. |
| [`records/codex-closeout-20260905`](snapshots/records/codex-closeout-20260905/) | Unmerged records | Unmerged machinery closeout report, handoff and evidence. |
| [`records/codex-machinery-20260904`](snapshots/records/codex-machinery-20260904/) | Unmerged records | Unmerged machinery handoff. |
| [`records/codex-mcp-closeout-20260905`](snapshots/records/codex-mcp-closeout-20260905/) | Unmerged records | Unmerged MCP closeout report, handoff, measurements and probes. |
| [`records/wip-recovery-20260904`](snapshots/records/wip-recovery-20260904/) | Previously merged | Merged WIP recovery archive, scopes, notes and logs; associated source also retained. |
| [`review/mcp-cap-quality-20260905`](snapshots/review/mcp-cap-quality-20260905/) | Unmerged records | Unmerged capability review report and evaluation. |
| [`review/mcp-quality-20260905`](snapshots/review/mcp-quality-20260905/) | Unmerged records | Unmerged review rulings. |
| [`review/mcp-security-20260905`](snapshots/review/mcp-security-20260905/) | Unmerged records | Unmerged security review evidence. |

Within each snapshot, records commonly live in `ops/conductor/handoff/`, `ops/conductor/reports/`, `ops/conductor/AAR-*.md`, `.dev/records/`, or `.dev/wip/`.

Exact source commits and tree IDs are in [sources.json](sources.json). Snapshot tree IDs must match those original trees before the corresponding branch names are removed. Deleting a branch name does not delete the snapshots or their retained commit history.
