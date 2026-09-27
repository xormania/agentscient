# Conductor startup: existing homes and design ruling

This is a conductor review record, not a handoff, AAR, admitted contract, or
implementation. The owner asked for the existing lane to be understood before
the startup design advances. The earlier startup draft is held for revision.

Evidence custody was measured at 2026-09-06T00:30:46Z, at working head
`f08b7c25979456b8f781c7cb1da55e2c91ddf036`. The two architecture audits target
`61b84cacfe0f917e134ce4ad1643541ee96a25e2`, based on dev
`c06ed9442ba51c9e96aa8de9f9bde93d0843a6cc`. Both have accepted terminal
envelopes, CHANGES verdicts on architectural understanding, and no changed or
residual source paths. Their tracked captures were byte-equal to canonical
dispatch records when this ruling was written.

- [Execution audit: GPT-5.6 Sol](../../../.dev/records/dispatches/20260906T001547Z-review-codex-9bab31.json).
  Record SHA-256: `6840e6dfff0d45449b7d91a781bfd896bfadda94df25a035f2a4fa99702d1749`.
- [Conductor and lifecycle audit: Daybreak](../../../.dev/records/dispatches/20260906T001559Z-review-codex-8a836d.json).
  Record SHA-256: `d5bf2cba234bf566b7ca8f90f05d05fb3f8bbf08610d0dcf7dee1e75050b88d6`.
- [Held startup draft: Grok 4.6](../../../.dev/records/dispatches/20260906T001017Z-plan-grok-be3523.json).
  Record SHA-256: `47060f7688eb077d85f93420e2aeef2a9c1d381ca9717dbbe288d54584ade8bb`.

Each audit contains its full HOMES report and coverage artifact inside
`result.envelope.artifacts`. The findings below are a conductor synthesis of
those measured reports, not a claim that every instrument was executed here.

## Ownership map

| Concept | Existing home | Measured status and consequence |
| --- | --- | --- |
| Wire, concerns, external couplings | `docs/` | Governs refusals, declarations, probes and verified mocks. Startup must declare its boundaries here before code. |
| Lifecycle transitions | `docs/workflow.md`, `ops/devlane/workflow/` | A generic workflow is declared; `wf.py` is absent. `ladder.py` implements a separate active pipeline. Session transitions must be an instance of the declared workflow, not another independent lifecycle design. |
| Dispatch and supervision | `ops/bin/go.sh`, `dispatch.sh`, conductor wrapper, `ops/devlane/dispatch/launch.py` | This is the active worker path. The contract describes `task/run.py` beneath it, but the audit found a separate dormant/manual runner. Resolve ownership at this seam before adding execution adaptation. |
| Harness behavior | `ops/devlane/harness/` and existing dispatch adaptation | Isolation and wire support are active; other staging/probe machinery is dormant or manual. Interactive conductor startup has different requirements from a worker snapshot, but does not justify a third independent harness abstraction. |
| Jobs, artifacts, producers | `ops/devlane/task/jobs.json`, envelope contract, `ops/process/`, ladder contract | Job and result validation exist. Producer/stage tables diverge across current surfaces; startup must not add another table. |
| Role policy and hooks | Conductor permission contract; `ops/devlane/hooks/` interception machinery | The conductor guard is unarmed and its command/payload assumptions are stale. Shared policy authority belongs to the conductor role; common interception must be vendor-neutral, with vendor request/response translation in adapters. |
| Configuration and registries | `ops/lane.conf`, `laneconf.py`, task registry, conductor instrument registry | These have distinct purposes. Instrument registry rows describe conformance/refusals; they are not a general session registry. |
| Conductor operation | `ops/conductor/tools/` and each lever contract | Decisions, handwork, findings, skills, CI, branches, watch, land, ladder, monitor, watchdog, onboarding and permission diagnostics already have owners. The earlier five-verb lifecycle summary omitted much of this estate. |
| Onboarding and context | `onboard.py`, onboard contract, compact hook | Existing law/state/AAR assembly should be extended. Initial automatic onboarding and discovery across retained record refs are missing. |
| Handoff and AAR custody | `ops/conductor/handoff/`, adjacent evidence/probes, `ops/conductor/AAR-*`, retained `records/*` branches | Placement is declared. Publication is currently manual; cross-session selection and recovery need a declared workflow/probe boundary. Avoid a competing ref namespace or vendor-owned canonical checkpoint. |
| Diagnostics | `docs/probes.md`, `probes-lever.md` | Corpus, grading and custody already have contracts; the production `probes.py` runner is absent. Diagnostic mode must extend that home. |
| Observation, gates, landing | Monitor/watchdog, `lane_read.py`/`lane_mcp.py`, `suites.sh`, `land.py` | Use the existing evidence and landing surfaces. MCP remains read-only. `board.sh` exists; the separately documented `board.py` does not. |
| Symfony services and projections | `docs/mapping.md`, `packages/`, application composition | Symfony ownership and four projections are binding direction. At the audited tree, packages contains only its README and the relevant shared services are not implemented; the snapshot has no installed vendor tree. Do not call planned services reusable runtime capability. |

## Rulings for the revised discussion

1. Preserve the requested interface: `conduct <harness>` automatically
   onboards; `conduct <harness> test` exercises actual harness enforcement.
   Keep the command thin. Policy, workflow, diagnostics and evidence ownership
   must be declared independently of harness CLI syntax and payload formats.
2. Map startup, recovery and owner-requested publication to the existing
   workflow genus. The missing runtime and launch/run split are design seams
   to resolve with a bounded proposal; this audit does not authorize a lane
   rewrite, wholesale consolidation or retirement campaign.
3. Reuse the existing record paths and publication lineage. The draft's new
   `refs/conductor/closeout/*` authority is not admitted. Older House
   project/session designs are prior art: the clean-start ruling did not
   adopt their records as Agentscient authority.
4. Handoff and AAR remain easy, separate owner-initiated in-session actions,
   including an explicit combined action. Exit, crash and compaction do not
   manufacture completed records. An unfinished checkpoint needs a shared
   workflow owner; harness transcripts are evidence, not that owner.
5. Reject the draft's malformed-payload fail-open rule. Reuse the probe
   contracts for positive, negative and unreachable cases; real tool attempts,
   hook decisions and effects determine diagnostic results. Synthetic payload
   tests alone do not certify a live harness. No manual-approval fallback is
   admitted by the owner request.
6. Resolve shared-policy ownership without placing it under Claude. The
   audits differ on the physical engine location; their common requirement is
   one conductor policy contract, reusable hook machinery, and explicit
   adapters. File placement remains a contract-design question. The existing
   permission contract's ungated-read invariant also needs an explicit,
   bounded update for the owner's conductor-role restriction, preserving
   coordination reads and the independent permission doctor.

## Evidence corrections and limits

The execution audit inspected an older tracked capture of the Grok plan and
the previous-session MCP handoff. Its statements that the plan remains
launched and host activation remains unproved are historical, not current
holdings. The canonical plan is now closed with an accepted envelope. The
conductor audit incorporates this session's saved v2 activation evidence from
a fresh host. That evidence does not prove this already-running chat reloaded
its connection.

Do not carry the conductor audit's process-census statement forward as a
global absence claim: this review used dispatched workers. Coverage of source
trees and contracts is not verification of every live process, installed
dependency, remote state, or interactive harness. Live Claude/Codex role-hook
behavior remains unproved by these audits. Canonical reviewer evidence is
preserved without rewriting these limitations out of its original record.

No implementation is admitted by this ruling. The next discussion should
revise the proposal against this map and identify the smallest missing
couplings before any contract or code is advanced.
