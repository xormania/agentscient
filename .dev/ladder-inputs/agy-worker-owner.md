# agy worker qualification

Owner instruction, 2026-09-08: "let's get started - new branch - make sure up-to-date - and let's get it going - i think gemini has some use for certain things".

The owner explicitly excludes agy from conductor use for now. Claude, Codex and Grok retain the conductor seats. This work qualifies agy as a configurable worker harness in the independent dev lane; it does not depend on the Symfony application or its vendor directory.

The preliminary `.xor/agy-add.md` report supplies capability claims to verify. Its implementation proposals are excluded by the owner's instruction. It is supplied to workers as an input, not adopted as a contract or proof of admission.

Start by mapping reported capabilities onto existing worker contracts and identifying bounded independent probes. Cover headless invocation, model identity, role restrictions, configuration isolation, prompt/result transport, session/resume identity and live supervision/accounting. Separate harness identity, actual model and model provider. Preserve model choice at dispatch and configurable role eligibility. Evaluate Gemini on representative bounded worker tasks before recommending a role from marketing or latency claims.

Use GPT-6 for planning and substantial implementation, independent producers for tests, and independent reviews recorded as PR comments. Daybreak is reserved for security review. Delegation uses ops/bin/dispatch.sh or go.sh, with existing supervision and watchdog. No new executor, conductor activation, fixed model roster, global settings changes or credential disclosure. Existing harness behavior and the canonical envelope remain compatible.

The first deliverable is a measured qualification plan with existing homes, capability/evidence gaps, first disposable probe procedure, acceptance cases and bounded implementation slices. Live probes follow their declared boundary; no capability is admitted merely because the report claims it works. No handoff or AAR is requested.

Baseline measured by git fetch origin and git rev-parse HEAD origin/dev on 2026-09-08: both refs were 3432b5cb8b9e171ecc981efa8409d299a85ec4c0 when this worktree was created.
