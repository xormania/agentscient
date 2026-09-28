# Worker launch contract acceptance

Measured 2026-09-06 UTC from the canonical dispatch records named below. This records completion of the C1 and C2 contract reviews; it does not activate a new launcher, output grant, harness capability, policy, MCP action, handoff or AAR.

## Accepted boundary

The [dispatch contract](../../devlane/dispatch/CONTRACT.md) owns the proposed single execution authority and admission behavior. The [task contract](../../devlane/task/CONTRACT.md) owns job declarations, rendered deliverables and envelope semantics. Role, work profile, harness and model are separate choices. The dev lane remains independent of the product Symfony application.

C1's final correction is `ec4a55f5959b5667e26ccedbdb9446483d39bc6a`. Independent Grok recheck `20260906T024254Z-review-grok-f82853` approved its capability attribution, fixed measurement ref, proposed outputs declaration and preserved inline exception. Its record is tracked under `.dev/records/dispatches/`; no current executor consolidation was claimed.

C2's contract landed at `a73c5e8c92f62926ca7d1634f043b5d3d1b60bee`. Claude review `20260906T032507Z-review-claude-d157c6`, measured at `1db532d0ad7119467a886eb85bdb5a386e99ce82`, approved all five dispositions of [the C2 ruling](../../../.dev/ladder-inputs/launch-c2-contract-ruling.md) and reported three nonblocking clarity items. The conductor accepted those items in [the final clarity ruling](../../../.dev/ladder-inputs/launch-c2-clarity-ruling.md).

The two-file correction landed at `4b50c0357164f07930c90ee85093ac6fea7a3fe7`. Grok recheck `20260906T034044Z-review-grok-0e71ab`, measured at `9408f1eda89ef4b9f76ab73c27bf967414ffe0b6`, returned `status=ok`, `verdict=approve`, zero findings, zero changed paths and zero residual paths. It measured the exact two-file correction, confirmed those files unchanged at the reviewed ref, obtained a zero diff check, and checked unchanged examples and native rendering.

The accepted clarifications require the concrete mechanism's actual extra write authority to equal the declared outputs; mere inclusion in a generic capability set is insufficient. Admitted scratch owns its TMPDIR subtree at adoption and is not simultaneously a reserved transport path. Newly declared file handles must exactly match the decoded rendered absolute path; historical records and the narrow inline exception retain their existing treatment.

The conductor accepts this completed contract review. Independent test authors now have an explicit target for exact outputs, task-owned semantic validation, transport separation, refusals, attempt custody and configured evidence freshness.

## Required before executable adoption

The contracts themselves retain the adoption dependencies: catalogue and prompt alignment, the single semantic validator's launcher integration, independent tests, bound attempt/resume and settlement behavior, and fresh per-harness capability evidence. Current Codex, Claude and Grok output mechanisms remain unproved under the new grant contract. No declaration authorizes widening a file grant to its parent directory, substituting a harness, or asking the owner for an approval prompt as fallback.

Current direct-execution paths are not declared consolidated by this report. Complete them through the [conductor start plan](../conductor-start-plan.md) and the contract's own bounded adoption dependencies; the lane policy has its separate acceptance record. This is a documentation milestone, with live execution and containment still to be demonstrated.
