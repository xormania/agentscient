# Add agy worker support

Owner instruction, 2026-09-08: "let's get started - new branch - make sure up-to-date - and let's get it going - i think gemini has some use for certain things".

The owner explicitly excludes agy from conductor use for now. Claude, Codex and Grok retain the conductor seats. This work adds agy as a selectable worker harness in the independent dev lane; it does not depend on the Symfony application or its vendor directory.

The preliminary `.xor/agy-add.md` report supplies capability claims to verify. Its implementation proposals are excluded by the owner's instruction. It is supplied to workers as an input, not adopted as a contract or proof of admission.

Owner clarification, 2026-09-08: "i don't need to find out its roles - just adding it". Do not perform task suitability studies, model benchmarking or role recommendations. Map existing contracts only as needed to implement worker support. Verify headless invocation, model identity, existing read/write restrictions, configuration isolation, prompt/result transport, session identity and live supervision/accounting. Separate harness identity, actual model and model provider. Preserve model choice at dispatch and the existing configurable job roles.

The owner identifies Flash 3.8 for auditing, investigation, review and documentation. These are owner-selected uses, not hypotheses requiring a suitability study. The subsequent instruction is "the goal is to get it installed - and this may be a good time to look at how we configure agent harnesses". Deliver installed, dispatchable worker support and examine configuration as part of that integration. Consolidate necessary harness settings behind existing interfaces; avoid a separate framework rewrite or a fixed model-to-role roster.

Use GPT-6 for planning and substantial implementation, independent producers for tests, and independent reviews recorded as PR comments. Daybreak is reserved for security review. Delegation uses ops/bin/dispatch.sh or go.sh, with existing supervision and watchdog. No new executor, conductor activation, fixed model roster, global settings changes or credential disclosure. Existing harness behavior and the canonical envelope remain compatible.

Deliver working agy worker dispatch through the existing entrypoint, with bounded independent tests, live smoke evidence where required by the existing contract, and reviews on the PR. Keep any planning limited to concrete implementation dependencies. Live probes follow their declared boundary; no capability is admitted merely because the report claims it works. No handoff or AAR is requested.

Baseline measured by git fetch origin and git rev-parse HEAD origin/dev on 2026-09-08: both refs were 3432b5cb8b9e171ecc981efa8409d299a85ec4c0 when this worktree was created.
