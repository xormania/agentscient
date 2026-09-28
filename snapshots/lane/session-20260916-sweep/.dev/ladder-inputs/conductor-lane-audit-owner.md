# Owner steering: map the existing lane before advancing the design

Owner, 2026-09-05: "also - before going too much further - make sure you understand all of the current dev-lane systems - see what you may have missed last session - many concepts have homes, you need to know them"

Pause further contract adoption and implementation. Conduct a read-only, evidence-backed inventory of the existing system. Root consumes reports and conducts; workers investigate. No settings changes, implementations, tests, publication, or remediation are authorized by this audit.

Map the current architecture before recommending additions. Each concept needs its authoritative contract/document, implemented service or instrument, operator entrypoint, state and artifact home, and actual activation status. Distinguish measured behavior, static inspection, documented intent, legacy artifacts, and anything that could not be inspected. Use current commands, stamped repository/ref/head and file references; never treat silence as absence. Explain overlapping names and intended ownership, including packages that already provide a capability. Enumerate all relevant subtrees and identify coverage gaps so 'all' is a checkable coverage claim.

The existing proposal is only a question to map against those homes: `conduct <harness>` with automatic onboarding; reusable conductor role enforcement; shared policies, lifecycle and diagnostics separated from harness adapters; transparent CLI argument forwarding without weakening required policy; `conduct <harness> test`; owner-initiated in-session handoff and AAR with automatic canonical placement/discovery; recovery checkpoints distinct from completed handoff/AAR. Do not add a second registry, lifecycle, policy engine, harness abstraction, tool surface, or record store where an existing home can own it.

Read the user's supplied previous-session record and follow its relevant evidence and decisions:
`/home/scientdb/projects/uscient/wt/ag-closeout-mcp-20260905/ops/conductor/handoff/HANDOFF-2026-09-05-codex-mcp-closeout.md`

Earlier reports and draft plans are hypotheses, not governing architecture. Report omissions and contradictions candidly. Recommend reuse, extension, replacement, or a genuinely missing boundary only after locating existing ownership. Return a compact synthesis plus a thorough coverage/evidence artifact. Do not expose credentials, private env values, or tokens.
