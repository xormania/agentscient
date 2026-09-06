# Authorized work: document the sequence and complete discovery contract step 1

Owner, 2026-09-05: "document it and start on step 1 - delegate so i don't get hit with permission questions constantly - you know what the goal is"

This authorizes the plan documentation, the discovery contract and acceptance criteria, independent review, and necessary contract corrections. The earlier pause on contract work is superseded for this bounded step. Root conducts through the existing dispatcher, consumes reports, rules, and lands artifacts. Routine decisions do not require another owner permission question. No runtime implementation or executable tests are requested in this step.

## Agreed sequence to document

1. Define discovery and onboarding for both work lanes: compact context, authoritative homes, usable tools, selected work, relevant handoffs, and missing/stale evidence.
2. Implement the shared CLI/MCP read service through independent tests, implementation and review. Prove a fresh conductor can find the right tools and context without owner-supplied filesystem paths.
3. Build `conduct` with shared enforcement and live diagnostics: profile configuration, separate Claude/Codex/Grok adapters, exact argument forwarding, actual MCP connection verification, and automatic onboarding. Allowed work runs without permission prompts; forbidden work is blocked by declared policy. No attended fallback is admitted.
4. Complete owner-initiated session lifecycle actions, canonical publication/discovery and distinct unfinished checkpoints under the existing workflow contract.

Fresh-session acceptance accompanies each slice. Broader execution-path consolidation and unrelated cleanup remain separately scoped. Do not turn discovery into a dependency on implementing the missing generic workflow runtime.

## Owner requirements

- Two work lanes: `dev` changes development machinery; `prod` develops the Symfony application. These are work profiles, not Git branches, deployment environments, or harnesses. Harness choice and work-profile choice are independent.
- Proposed user interface: `conduct <harness> dev`, `conduct <harness> prod`; `conduct <harness> test` for the full diagnostic and a profile before `test` for a narrowed diagnostic. Everything after `--` belongs to harness arguments, subject to the required conductor policy. This step documents that later interface; it does not implement it.
- Avoid hardcoding: configurable profiles and explicit adapters, with shared policy, lifecycle, discovery and grading. No separate implementation per harness or profile.
- MCP is the main conductor discovery/context interface. Extend the existing shared read-service boundary; retain CLI parity and the declared read-only MCP boundary. It must not become a new authority, job runner, writable session store, or policy enforcement mechanism.
- Handoff and AAR are easy separate in-session actions initiated by the owner, with an explicit combined action. The system handles placement/discovery. Exit/crash/compaction does not manufacture completed handoff/AAR records. These future writes stay outside discovery.
- Keep conductor context small: one bounded startup read plus targeted detail. A full raw documentation dump or whole-tree investigation in every root session fails the goal.

## Step 1 deliverables

Write the agreed sequence in the existing conductor documentation estate and a focused shared discovery contract, using normal lever/contract conventions. Suggested paths are `ops/conductor/conductor-start-plan.md` and `ops/conductor/discovery-lever.md`; choose a different existing home only if its current contract requires it, and explain the choice. Link from the relevant conductor/onboard/MCP documentation so the result is discoverable.

Read the founding docs and remeasure the relevant Symfony mapping before relying on it. Use the recent home-map and MCP-fit reviews to avoid another whole-lane audit. Separate installed/implemented capability from intended Symfony ownership and future projections. Do not add a new Python workflow/kernel responsibility or invent an installed Symfony service.

The contract must be concrete enough for an independent test author: input/output shapes and versions; profile/source configuration; ownership and authoritative-source selection; provenance and freshness; bounded startup and detail reads; relevant work evidence; retained-record handoff/AAR candidate discovery; action-interface guidance; explicit absence, ambiguity, malformed/unreachable source and stale-source behavior; limits, pagination/snapshot semantics, refusal/exit rules, compatibility, and objective acceptance rows.

Ownership cards cite existing contracts, registries and entrypoints. The recent home-map is evidence, not a new authority to copy into a registry. Where metadata is genuinely missing, declare the smallest extension at its owning home and make incompleteness visible. Tool presence, installation, activation and successful live probing are distinct claims.

Preserve source allowlisting and bounded local reads. Current lane_read forbids subprocesses; do not silently bypass that rule to inspect Git refs. Declare the minimal fixed read adapter/projection boundary and how CLI/MCP consume its result, without arbitrary paths/commands, network work, writes, another store, or a competing records namespace. No arbitrary exploration of user directories or credentials.

Fresh-session acceptance covers both work profiles: identify authoritative owners and real tools; recover an unambiguous relevant handoff without a supplied path; distinguish no/one/multiple/unreadable/stale candidates; label unavailable actions honestly; preserve stationary CLI/MCP payload parity; treat record text as data; and leave sources, refs, databases and worktrees unchanged. Discovery does not claim host activation, live readiness, role enforcement or lifecycle publication.

Scope: documentation and contract only. Do not write or change executable tests, source implementation, active settings, dependencies, runtime databases, host configuration, or existing captured records. Do not publish a PR or change remote state. Preserve other work, record actual measurements and limitations, and use parsed Source and actual-model Co-Authored-By trailers. Return the artifact paths, commit, documentation checks and unresolved questions in a compact envelope.

## Reviewer selection

Owner, 2026-09-05: "have codex chatgpt6 review grok's plan"

Use the Codex harness with GPT-6 for the independent review of Grok's plan and discovery contract. The installed Codex model catalogue was read and advertises `gpt-6-astra` as GPT-6-Astra with high reasoning supported. Name that model explicitly at dispatch; preserve the actual-model evidence in the resulting record. No review has yet been performed merely because a reviewer was selected.
