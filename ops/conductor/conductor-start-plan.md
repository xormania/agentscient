# Conductor start sequence

Standing: authorized documentation of the four-step sequence. Owner,
2026-09-05: "document it and start on step 1". The earlier pause on
contract work is superseded for this bounded step. This file is the
sequence, not a lever contract and not an implementation.

The discovery contract is [`discovery-lever.md`](discovery-lever.md), with
[non-executable payload examples](discovery-examples.md). This correction
implements the [first review ruling](reports/discovery-contract-review-20260905.md)
as documentation; it awaits independent review and does not approve itself.
The [correction disposition](reports/discovery-contract-correction-20260906.md)
is the preserved prior producer report, not current measurements or admission.
The [2026-09-06 reconciliation](reports/discovery-reconciliation-20260906.md)
records the latest owner scope and this recovery's evidence separately.
Step 1 ends only after admission for independent test authors. Steps 2–4
remain future work.

The latest supplied `discovery-contract-owner.md` supersedes earlier framework
assumptions: dev-lane tools evolve independently under `ops/`; the prod Symfony
application neither implements nor eventually replaces them. Discovery may
describe prod's Symfony contracts without depending on that application.
The separate `lane/lane-boundary-20260905` enforcement track is pending
authoritative seed/contract and measurable policy work, not an implemented
dependency or a reason to defer this read contract.

## What this is not

- Not a new workflow engine, Python kernel, or Symfony service.
- Not a second MCP server, job runner, writable session store, or
  policy-enforcement mechanism.
- Not admission of `conduct`, harness adapters, lifecycle publication,
  or executable tests.
- Not a copy of the home-map into a registry. The home-map is evidence.

## Evidence reused

No whole-lane re-audit. These records were read as inputs to this step:

| record | role |
|---|---|
| owner input `discovery-contract-owner.md` | governs this step |
| [`reports/conductor-start-home-map-20260905.md`](reports/conductor-start-home-map-20260905.md) | ownership map and design rulings |
| MCP-fit review `20260906T003931Z-review-codex-2dfe8d` | existing MCP/onboard gaps and the shared-read slice |

Founding law cited, not restated: `docs/wire.md`, `docs/workflow.md`,
`docs/probes.md`, `docs/concerns.md`, `docs/verified-couplings.md`,
`docs/mapping.md`, `AGENTS.md`.

## Work profiles and harnesses

Two configurable work profiles, independent of harness choice and of
Git branches or deployment environments:

| id | work |
|---|---|
| `dev` | development machinery (`ops/` in the default profile config) |
| `prod` | the Symfony application (`src/`, `packages/`, `config/`, `public/` in the default profile config) |

Harness adapters (initially Claude, Codex, Grok) are a separate axis from
profile and role. Shared policy, lifecycle, discovery and grading are not
implemented per harness/profile. Adapter mechanics cover argv, hooks,
parsing, resume and MCP integration; measured capabilities, shared policy
and explicit dispatch choices are distinct inputs.

`conduct` starts the conductor role; the existing dispatcher starts workers
for named jobs. This discovery slice exposes conductor context. Worker tools
and MCP are a separately bounded follow-up through the existing task/harness
owners: the same services, scoped brief/inputs/contracts/checks/outputs,
different catalogues. Trusted launch and job contracts grant source access;
no caller role switch and no conductor-wide worker inheritance. Read-only
MCP visibility does not enforce access through other harness tools.

## Later interface (documented, not implemented)

```
conduct <harness> dev
conduct <harness> prod
conduct <harness> test
conduct <harness> <profile> test
```

Everything after `--` is forwarded as harness arguments, subject to
conductor policy. `test` exercises live harness enforcement; a profile
before `test` narrows that diagnostic. The command stays thin: policy,
workflow, diagnostics, and evidence ownership are declared outside
harness CLI syntax.

## The four steps

### 1. Discovery and onboarding contract (this step)

Define compact context for both profiles: authoritative homes, usable
tools, selected work, relevant handoffs, missing and stale evidence.
Write the shared CLI/MCP read contract with objective acceptance rows.
Preserve the current read-core subprocess restriction by declaring a
fixed ref adapter. Link the docs. No executable tests, runtime,
settings, dependencies, stores, or host changes.

Fresh-session bar for this slice: a later implementation, from a newly
started client with no conversational context, can satisfy the
acceptance rows in `discovery-lever.md` for both profiles.

### 2. Shared CLI/MCP read service

Independent tests, then implementation, then review, against
`discovery-lever.md`. Prove a fresh conductor can find the right tools
and context without owner-supplied filesystem paths. Extend
`lane_read.py` / `lane_mcp.py`; add the declared fixed acquisition adapter
outside the subprocess-free read core. Prove shipped dev/prod and an added
profile, complete bounded catalogues, source isolation, ambiguous/incomplete
record recovery and stationary snapshots across projections. Unsupported
register/ledger/PR local readings remain explicitly unavailable; do not
execute onboard or its subprocess dependencies to fill them. Do not require
the missing generic workflow runtime (`wf.py` remains absent).

### Parallel track: worker execution consolidation

The owner authorized this track in parallel with discovery. Its own contract
still needs admission. Consolidation must complete before step 3 conduct
startup; it blocks neither step 1 nor the read-only service in step 2.
The [prior home-map](reports/conductor-start-home-map-20260905.md) reports an
active `launch.py` and a separate `task/run.py` implementation inaccurately
described as underlying it. This is inherited evidence of an ownership seam,
not a fresh claim that multiple live callers were proved.

Use the existing [dispatch](../devlane/dispatch/CONTRACT.md) and
[task](../devlane/task/CONTRACT.md) owners and harness boundaries. First
inventory uniquely supported behaviors; assign snapshots, configurable adapter
mechanics, supervision, resume and collection to one canonical execution
service. Dispatch/go/ladder may remain frontends. Prove the canonical path
through existing conformance, then retire or explicitly refuse obsolete direct
paths. Capability evidence, explicit requested/actual model records and
conductor/worker separation belong to that contract as well as step 3.
This consolidates dev-lane execution within its existing ownership; it adds
no Symfony dependency and authorizes no runtime rewrite in this slice.

### 3. `conduct` with shared enforcement and live diagnostics

Starts after the parallel consolidation contract is admitted and its canonical
execution path is proved. The independent lane-boundary track supplies policy
work for reconciliation and proof before conduct admission, not assumed enforcement.

Profile configuration, separate Claude/Codex/Grok adapters, exact
argument forwarding, actual MCP connection verification, automatic
onboarding. Allowed work runs without permission prompts; forbidden
work is blocked by declared policy. No attended fallback. Shared
policy is not placed under one vendor. Diagnostic mode extends
`docs/probes.md` / `probes-lever.md` (positive, negative, unreachable);
synthetic payload tests alone do not certify a live harness.

Build on the consolidated dev-lane dispatch/harness service and existing
configuration owners. Symfony AI Platform belongs to the prod application's
mapping, not to dev-tool execution or its future replacement. Validate
profile/override compilation into exact token vectors; reject undeclared
overrides and conflicts with required policy. Resume must restore the same
role, profile, source grants and policy, and reverify the actual MCP connection.
Shared enforcement blocks forbidden work without an attended fallback.

Extend [`harness-capabilities.md`](harness-capabilities.md) and existing
probe/evidence contracts with declared versus measured mechanics/capabilities,
version/executable/config-bound evidence, complete observations and explicit
unreachable results. Discovery later projects those declarations, measurements
and applicable constraints from their owners; it does not certify itself or
run probes during reads. Capability absence, stale evidence and unsupported
mechanics must remain distinguishable.

Role restrictions (including Daybreak reserved for security) are enforceable
selection constraints in trusted dispatch policy, not conversational memory.
Owner preferences select GPT-6 for planning and substantial work; these are
configurable choices, not a permanent producer/model table in job definitions.
Require explicit model choice at dispatch and record requested and actual
model plus adapter/capability evidence. Keep independent test, implementation
and review producers. Fresh-session acceptance covers an allowed tool attempt,
a forbidden attempt, effects, malformed hooks, conflicting overrides, resume,
actual MCP connection and automatic onboarding. Unreachable is never pass.

### 4. Owner-initiated session lifecycle

Handoff, AAR, and an explicit combined action, each owner-initiated
and easy. Placement and discovery are system responsibilities;
publication is not manufactured by exit, crash, or compaction.
Unfinished checkpoints are an instance of the workflow genus in
`docs/workflow.md`, not a new lifecycle. Existing record paths remain
the publication lineage; `refs/conductor/closeout/*` is not admitted.
Harness transcripts are evidence, not the checkpoint owner.

Within that existing workflow owner, specify idempotent reservations and
revision checks before publication/recovery: duplicate owner requests do not
duplicate records and stale responses cannot publish against a moved lineage.
No transcript, stop hook or draft retrospective becomes canonical closeout.
Fresh-session acceptance recovers an unfinished checkpoint as unfinished and
finds separately published handoff/AAR evidence after explicit owner action.

## Mapping to existing homes

Session start, recovery, and owner-requested publication are instances
of the declared workflow genus. The missing `wf.py` runtime does not
block step 1 or 2. It does matter for creating recovery checkpoints
and publishing handoff/AAR records (step 4).

MCP stays the context-and-diagnostics plane, read-only. CLI parity is
required. MCP does not enforce root tool policy, dispatch, acknowledge
alerts, write checkpoints, or publish refs.

Two role-specific MCP server entrypoints/instances from one codebase and
shared dev-lane services remain a deployment proposal: conduct would connect
the conductor instance; dispatch would bind a worker instance to trusted job
identity and authorized sources. A caller role argument cannot expand grants.
Writable conductor tools are a separate discussion requiring deliberate
admission of a revised MCP contract, typed bounded actions, trusted role/job/
capability authorization, state and duplicate-request checks, recorded outcomes
and live server/host approval diagnostics. Neither proposal changes today's
read-only contract. Tool annotations and catalogue visibility alone cannot
prove unattended operation or enforce access through other harness tools.
Any future handoff/AAR action remains owner-initiated.

## Symfony mapping, remeasured

Historical draft measurement, preserved from invalid producer record
`20260906T011424Z-code-codex-2a2af6`: measured 2026-09-06T01:15:46Z against
`3682a8c58e304e7025036f1b3ec4edb63424832e`: Python parsed composer.json and
composer.lock, enumerated packages and checked vendor/instrument paths and
lane_read's AST. No installation, runtime probe or Packagist refresh.

| fact | reading |
|---|---|
| PHP runtime | not remeasured in this correction; composer requirement is >=8.4 |
| composer.json require | php >=8.4; `symfony/console`, `dotenv`, `flex`, `framework-bundle`, `runtime`, `yaml` at 8.1.* / ^2 |
| composer.json require-dev | phpunit ^13.3; `symfony/ai-mate` 0.13.0; `symfony/ai-symfony-mate-extension` 0.13.0; phpunit-bridge 8.1.* |
| locked/resolved | console v8.1.6, framework-bundle v8.1.6, runtime v8.1.0, yaml v8.1.6, flex v2.11.0, dotenv v8.1.6, phpunit 13.3.2, phpunit-bridge v8.1.6, ai-mate v0.13.0, ai-mate-composer-plugin v0.13.0, ai-symfony-mate-extension v0.13.0 |
| lock absent | `symfony/mcp-bundle`, `mcp/sdk`, `symfony/ai-platform`, `symfony/workflow`, `api-platform/core`, `api-platform/mcp` |
| `packages/` | only `README.md` (empty by declaration) |
| `vendor/` | absent in this snapshot |

These readings describe the prior snapshot only; current recovery checks are
in the reconciliation note. `docs/mapping.md` is a historical package map for
describing prod ownership (Packagist table dated 2026-09-03; not re-queried).
Its earlier dev-tool retirement direction is superseded by the owner scope
above. Symfony's four application projections and Workflow do not prescribe
dev tooling or prove installed capability. Discovery must not report them as
present from a document or a lock entry.

## Limits this step keeps

- One bounded startup read plus targeted detail. A full documentation
  dump or whole-tree investigation in every root session fails.
- Current `lane_read.py` does not import or mention `subprocess`
  (AST of that file at the SHA above).
- No competing records namespace.
- No writes, network, arbitrary paths, credentials, or user-directory
  exploration.

## Bounded Loopstrap recommendations for later slices

Source: `xormania/loopstrap@ca5ab8d363f8822ac5406f5e0bf5c94288102f1a`, as
inspected in the supplied GPT-6 comparison record
`20260906T010702Z-review-codex-1d530c`. These are recommendations drawn from
that pinned-source report, not fresh execution or adoption of external code.

| future slice / existing owner | bounded recommendation and source |
|---|---|
| 2; lane_read and task/harness context | Constrain context during assembly and independently prove custody. [context.py:13–32](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/context.py#L13-L32) excludes artifact labels for test authors; label filtering alone proves neither content isolation nor fresh-session discovery. |
| 3; existing configuration and harness/dispatch contracts | Validate profiles/overrides into launch vectors: [profiles.py:165–219](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/profiles.py#L165-L219), [wrappers.py:120–188](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/wrappers.py#L120-L188). Independently prove exact forwarding, hooks and resume; the comparison supplies no such proof. |
| 3; selection policy and probes | Check required capabilities and producer independence ([harness.py:459–507](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/harness.py#L459-L507)); bind evidence to versions/executable bytes and complete ordered observations ([certification.py:397–425](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/certification.py#L397-L425), [843–883](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/certification.py#L843-L883)). Routing checks are not per-tool enforcement; use existing probe receipts, no new certification authority. |
| 4; workflow genus and record lineage | Specify idempotent reservation and stale-response checks ([recovery.py:39–123](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/recovery.py#L39-L123)); keep owner-initiated publication distinct from unfinished recovery. |

Limits from the supplied comparison: [launch-loop.sh:1–8](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/launch-loop.sh#L1-L8)
refuses startup; [cli.py:43–67](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/loopstrap_core/cli.py#L43-L67)
sets certified=false. Its [.claude/settings.json:2–78](https://github.com/xormania/loopstrap/blob/ca5ab8d363f8822ac5406f5e0bf5c94288102f1a/.claude/settings.json#L2-L78)
describes doctrinal lane discipline and bypassPermissions; that does not meet
the owner's enforced conductor boundary. No dependency, registry, store,
ledger, kernel, certification authority or implementation is copied. Remote
link availability and live compatibility were not reverified here.

## Unresolved, deferred

These are not this step's work. They are named so they are not
silently closed:

1. Physical file placement of the shared-policy engine (step 3; the
   audits differ; one conductor policy contract plus adapters is the
   common requirement).
2. Adapter internals: closed git subprocess versus reading git objects
   (step 2; the contract allows either behind `lane_refs`).
3. Adding these two paths to onboard's law table (smallest extension,
   declared in the discovery contract, not applied here so the
   onboard instrument does not drift from its contract).
4. Admission and proof of the parallel worker consolidation contract before
   conduct startup; authoritative lane-boundary enforcement remains pending.
5. Worker context/MCP and two role-specific server entrypoints; writable MCP
   requires a separately admitted change to the standing read-only boundary.
