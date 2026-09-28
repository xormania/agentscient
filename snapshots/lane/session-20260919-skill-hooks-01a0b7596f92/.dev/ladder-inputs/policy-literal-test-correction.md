# Final bounded guard-test correction

Claude `20260906T042008Z-check-tests-claude-b9e985` returned two P2 coverage gaps and one nonblocking P3 suggestion at `1cd00ab930129caa7505380bd0179a18bf9a4ad8`. Accept the two concrete coverage corrections only; preserve the already reviewed contract and every existing test.

F1: add a positive with the exact permitted declaration after benign lines inside a multiline record.py; it must pass independently of its line number and neighboring benign content. In both composite negative cases, assert that the permitted declaration itself is absent from reported agentscient findings while the intended forbidden occurrence remains reported. These allowance assertions are intended reds before the repair; preserve the distinction from the known current-tree baseline failure.

F2: add two exact-path negative neighbors: the same declaration under a sibling basename in ops/devlane/dispatch/, and under the basename record.py in another scanned directory. Each must report its own token, path and line. Together these reject directory-prefix and basename-only exemptions.

F3 is deferred as a nonblocking wording suggestion. No new occurrence quota is introduced. The existing exact stripped-line predicate remains a per-line predicate; do not invent a one-declaration-per-file constraint or change the contract for this suggestion.

Only Grok edits ops/conductor/tests/test_laneconf.py. Read the contract, existing tests/helpers and supplied review; never read laneconf.py or record.py implementation. Run the same frozen unittest and plant-guard commands. Report all intended allowance assertion reds (including the composite absence assertions), the separate baseline failure, passing negative/MCP controls and zero import/collection errors. No weakening, skips, stand-ins, source/contract edits, host/DB/settings/network change or vendor launches.

Sequence refinement to reduce idle time: once the corrected tests are integrated, a separate GPT-6 worker may prepare the two-source-file repair in its isolated snapshot in parallel with independent Claude design review and GPT-6 execution measurement of the unchanged preimplementation branch. This supersedes only the earlier requirement to delay starting preparation. It does not permit integration or acceptance of the implementation before both test gates succeed on matching test/contract blobs. The implementer neither authors nor approves tests; changed tests require revalidation. Independent final implementation review and the full green gate remain mandatory.
