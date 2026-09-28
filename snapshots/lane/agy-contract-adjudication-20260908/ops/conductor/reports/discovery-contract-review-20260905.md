# Discovery contract: first review ruling

The reviewed documentation is `d99c94fe898b9c2aff787d7800fdd3ce4f06a689`,
landed from Grok's `961da3fd37d207701488f63df6e0c9c908a8afff` in the owned
task branch. This ruling is based on accepted terminal records read on
2026-09-06; it does not report a runtime vulnerability or implementation test.

- [GPT-6 functional/architecture review](../../../.dev/records/dispatches/20260906T010515Z-review-codex-a0b114.json): CHANGES, eight P2 and one P3.
- [Daybreak security review](../../../.dev/records/dispatches/20260906T010516Z-review-codex-dadb85.json): CHANGES, two P1, three P2 and one P3.
- [GPT-6 Loopstrap comparison](../../../.dev/records/dispatches/20260906T010702Z-review-codex-1d530c.json): research, no approval; one requirements finding duplicates the harness-plan gap.

The contract is held for documentation corrections. The findings above are
upheld as requirements/clarity defects and grouped below to avoid duplicate
work. No existing runtime hardening campaign, tests or source implementation
is authorized by this ruling.

## Correction groups

1. **Nominal coverage and extensibility.** Make the bounded startup packet
   expose the required dev and prod owners. Make their complete catalogues
   reachable through bounded listing/detail or pagination. The shipped
   catalogues must not trip their own limits. Configured profile selection,
   source membership and ordering must also work for an additional registered
   profile without a new code branch or a hardcoded index column.
2. **Fixed acquisition boundary.** Declare trusted repository/gitdir and
   source identities, bounded tree-path enumeration, tracked-object
   verification, operation deadlines, and deterministic overflow/refusal.
   Bind reads beneath explicit trusted anchors, reject symlink/special-file
   redirection, and remove ambient CWD/Git environment influence. Configured
   state sources may have their own declared anchor; this is not a mandate to
   move every existing store beneath the repository. Preserve the pure
   read-core subprocess restriction. No arbitrary command/path, network,
   mutation, hidden helper fallback or new sandbox platform.
3. **Complete source composition.** Bind every startup field to an exact
   allowlisted local reading and define the summary derivation. Existing
   onboard behavior that invokes tools, Git or gh is not automatically a
   valid MCP dependency. Unsupported or absent inputs are explicitly
   unavailable; no home/environment/network fallback. Do not defer this
   contract boundary to the implementation author.
4. **Candidate identity and selection.** Define record/blob/ref identity,
   duplicate handling, authoritative relevance inputs, work-profile and
   lineage filtering, unknown-relevance behavior, ordering and ties. Do not
   derive authority from session-controlled timestamps, filenames or branch
   words. Unknown/incomplete/unreadable scans must not falsely prove a
   unique selection. Existing records lacking required metadata remain
   visible with the missing evidence declared; do not invent it.
5. **Complete schemas and snapshots.** Specify all four new query envelopes,
   nullability, unavailable/reason tables, source IDs, dependency fingerprints,
   adapter revisions and continuation behavior. Bind mutable ref identity,
   commit identity and every selection-relevant field. A ref move to a new
   commit with identical blob bytes must not silently reuse a prior selection
   snapshot. Preserve stationary CLI/tool/resource parity and v1/v2 behavior.
6. **Honest standing and availability.** Separate governing-document presence,
   implementation presence, locked dependencies, installation, activation and
   live verification. An AAR is evidence, not its own governing contract.
   Preserve explicit untrusted-data labels and consumer-facing boundaries;
   JSON escaping alone does not prevent instruction promotion. No action is
   authorized solely by record text.
7. **Plan and role boundaries.** Incorporate the current owner brief: harness
   mechanics, measured capabilities, shared policy and explicit recorded
   dispatch choices; enforceable role constraints; the existing Symfony AI
   ownership; configurable owner preferences. Role, work profile and harness
   are independent. This discovery surface is for conductors. Worker-context
   tools/MCP are a separate bounded follow-up through existing task/harness
   owners, with scoped sources and trusted launch configuration, not a
   caller-controlled role switch or another backend.
8. **Acceptance and documentation checks.** Update the non-executable
   acceptance rows and representative exact payloads to cover each correction,
   normal defaults, an added profile, incomplete scans, ref/content races,
   overflow, hostile text, distinct trust/availability states, and no effects.
   Check links and internal definitions. Do not author executable tests.

## Loopstrap use

The comparison inspected `xormania/loopstrap@ca5ab8d363f8822ac5406f5e0bf5c94288102f1a`
through a pinned local object store, without executing its code. Its useful
patterns are validated profile/override compilation, capability and
independence checks, evidence bound to versions and complete observations,
role-scoped context assembly, and idempotent reservations/revision checks.
These map to existing harness, probes, task-context and workflow owners.
Its launcher refusal and doctrinal lane discipline are explicit limits.
Carry bounded recommendations and immutable source links into the plan;
copy no implementation, registry, ledger or certification authority. No
Loopstrap dependency is admitted.

## Production of the correction

The owner now selects GPT-6 for planning and substantial work. A new GPT-6
write dispatch will revise the documents using this ruling and the latest
owner brief. The completed review is not an approval of that later artifact;
the resulting revision requires independent review. Daybreak is reserved for
the security boundary. Root continues to conduct and rule through records.
