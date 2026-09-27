# Independent policy test acceptance gate

The corrected tests from Grok `20260906T034324Z-tests-grok-289d91` landed at `bc50b8c013d67a573b1c23ca30e93cecfad6bff8`. Its author reports 96 tests, 65 intended assertion failures, zero errors, 35 existing passes and nine positive neighbors; that is author evidence until independently rerun.

Two independent checks may proceed in parallel. GPT-6 measurement-only dispatch `20260906T035117Z-check-tests-codex-b79cb9` uses the existing native check-tests execution and report transport to rerun the frozen command and test guard. It neither authors nor approves the tests. Claude independently rechecks the corrected test design against the contract and the accepted bf58a4 findings. Its review-only interpreter limitation need not be exercised again.

This refines F1's sequence in policy-record-test-correction-ruling.md without relaxing its requirement. The conductor may accept the test boundary only after both checks close successfully, the execution report establishes the intended reds and passing neighbors with no import/collection errors, and the reviewed and executed test/contract blobs match. Claude's design verdict alone does not close the execution gap. Any difference or unresolved material finding goes back to the owning producer. The later GPT-6 implementation is a separate dispatch that neither writes nor approves these tests.

No new permissions, job transport, grant or policy activation is created here. Preserve the read-only inline report for Claude and the existing native test workspace for execution. Report evidence precisely; do not call a Python command refusal a test result.
