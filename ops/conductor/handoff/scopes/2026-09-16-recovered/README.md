# Scopes recovered after the 2026-09-16 host fault

These four dispatch scopes were drafted before the WSL2 fault of
2026-09-16 (between 15:28Z and 15:31Z) and were lost with `/tmp`, where the
harness scratchpads live. They were reconstructed on 2026-09-16 by the
recovery session (branch `lane/session-20260916-recover`, grant 285) from
the writing commands recorded in the drafting sessions' transcripts, byte
for byte as last written there. None had been launched. LD-92 is the row.

| file | drafted by | transcript | last written | bytes |
|---|---|---|---|---|
| scope-branchcensus.txt | the XO, agentscient-09 (PT-7) | 7ae721d7-debe-44da-8718-e937f3290bd7 | 15:01:02Z | 1039 |
| scope-delete-tests.txt | the XO, agentscient-09 (PT-7) | 7ae721d7-debe-44da-8718-e937f3290bd7 | 15:23:11Z | 1061 |
| scope-delete-impl.txt | the XO, agentscient-09 (PT-7) | 7ae721d7-debe-44da-8718-e937f3290bd7 | 15:23:53Z | 1028 |
| scope-a87-relaunch.txt | the Dispatcher, agentscient-c8 (PT-3) | 6748e545-7972-4da5-9601-54a2b6ebd924 | 14:43:03Z | 712 |

Their order, as the Lead (agentscient-11, PT-2) had it at 15:24Z: the
A-87 relaunch after #254 merges; the census seat as one dispatch; the
delete-refusal row as two dispatches, codex `author-tests` on
scope-delete-tests.txt first, then grok `implement` on
scope-delete-impl.txt with the test file outside its scope. The
delete-row scopes name wall paths (`ops/devlane/hooks/tests/`,
`boundaries.json`) and so run in their own worktrees under a wall grant.
