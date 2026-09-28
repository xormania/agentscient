# Historical conductor ruling custody

These four files are preserved evidence of the original session's scope clarifications and dispositions. They are not owner-issued or independent third-harness rulings and do not make the original correction sequences compliant. Their bytes were recovered from the original dispatch inputs and matched the recorded SHA-256 values on 2026-09-06.

| File | Original dispatch input | SHA-256 |
|---|---|---|
| ag-conduct-interface-final-ruling.md | 20260906T111519Z-code-codex-dce07d | d193abd3257eac875378e00da621823e204f34b7787b252da7ccb043d4032605 |
| ag-conduct-unit1a-review-ruling.md | 20260906T113433Z-review-claude-fa4a72 | 1d17da95032687afe25eeee98acd72ab768471f0fe691e4022a79a6cefa4f81c |
| ag-conduct-unit1a-fix-ruling.md | 20260906T114654Z-code-codex-b30b94 | 896b9b8acc5cfaed865ae42c42d2da5b5efa3f00aa93ea28c3ec9128d957e7b0 |
| ag-conduct-discovery-contract-fix-ruling.md | 20260906T123030Z-code-codex-18ec12 | bc48f5139509935060796fe1fc7ae314dd5332efd9cc2e5571094d47c42fd5fd |

Independent cold rulings now exist in canonical dispatch custody as 20260906T135746Z-adjudicate-grok-6e5da5, 20260906T135747Z-adjudicate-grok-71f362, 20260906T135747Z-adjudicate-grok-37ba86 and 20260906T135748Z-adjudicate-grok-6d4469. Each received its original reviewed snapshot and original report, excluding later fixes. They require prospective reconciliation; they do not rewrite the earlier sequence. The custody audit is 20260906T134542Z-review-grok-0ada88 and its independent ruling is 20260906T135745Z-adjudicate-claude-9b169d.

Identity correction: this root conductor session supplied worker labels through `--agent`/`WF_AGENT` on many earlier review dispatches and test land calls. That parameter identifies the invoking or committing agent, not the worker selector. Consequently those `dispatched_by` labels do not establish that the conductor changed harnesses. The root conductor is Codex/GPT-6; future root calls use that identity. Worker harness/model fields and the workers' actual source trailers remain separate. Original records and commit identities remain unchanged as historical evidence.

The original invalid producer envelopes, published commits, split interface artifacts and later independent reviews remain preserved. This archive is neither a runtime admission nor a handoff or AAR.
