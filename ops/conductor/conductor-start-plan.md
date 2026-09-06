# Conductor start sequence

Standing: authorized documentation of the four-step sequence. Owner,
2026-09-05: "document it and start on step 1". The earlier pause on
contract work is superseded for this bounded step. This file is the
sequence and the bounded launch-interface contract below, not an implementation.

The discovery contract is [`discovery-lever.md`](discovery-lever.md), with
[non-executable payload examples](discovery-examples.md). This correction
implements the [first review ruling](reports/discovery-contract-review-20260905.md)
as documentation; it awaits independent review and does not approve itself.
The [correction disposition](reports/discovery-contract-correction-20260906.md)
is the preserved prior producer report, not current measurements or admission.
The [2026-09-06 reconciliation](reports/discovery-reconciliation-20260906.md)
records the latest owner scope and this recovery's evidence separately.
Discovery and C1/C2 contract acceptance are recorded in the linked owning
reports. Executable steps remain subject to their acceptance duties. The
[launch interface below](#trusted-conductor-launch-descriptor) completes adoption
unit 1b; it neither reopens those boundaries nor declares runtime activation.

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
conduct <harness> dev [-- <adapter-token>...]
conduct <harness> prod [-- <adapter-token>...]
conduct <harness> test [-- <adapter-token>...]
conduct <harness> <profile> test [-- <adapter-token>...]
```

The optional `--` follows all conduct positionals, including `test` when present;
it may have zero following tokens. No conduct positional is parsed after it.
Forwarding is admitted on all four forms. Unprofiled test validates the same
vector for every enumerated profile before any diagnostic effects; a rejection
in any profile refuses the invocation. Tokens after the first `--` must satisfy
the adapter [closed safe grammar](harness-capabilities.md#safe-argv-grammar). Accepted tokens
are forwarded exactly, in order; rejected tokens never reach launch records.
`test` exercises live harness enforcement; a profile before `test` narrows
that diagnostic. The command stays thin: policy,
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

The owner authorized this track in parallel with discovery. Its C1/C2 contract
acceptance is [recorded](reports/worker-launch-contract-acceptance-20260906.md).
Executable consolidation must complete before step 3 conduct
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

## Symfony mapping, preserved historical measurement

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

1. Shared-policy implementation and activation under
   [lane-policy.md](lane-policy.md#bootstrap-and-minimum-complete-activation),
   which owns the evaluator at `ops/conductor/tools/lane_policy.py`.
2. Adapter internals: closed git subprocess versus reading git objects
   (step 2; the contract allows either behind `lane_refs`).
3. Adding these two paths to onboard's law table (smallest extension,
   declared in the discovery contract, not applied here so the
   onboard instrument does not drift from its contract).
4. Executable proof of the accepted worker consolidation and lane-policy
   contracts before conduct startup; contract acceptance is not runtime proof.
5. Worker context/MCP and two role-specific server entrypoints; writable MCP
   requires a separately admitted change to the standing read-only boundary.


## Trusted conductor launch descriptor

Adoption unit 1b freezes this interface for independent construction. It is
contract-only, under the owner assignment of 2026-09-06 and GPT-6 adoption
review `20260906T102712Z-plan-codex-bc6012`, unit 1b. Accepted
[discovery](reports/discovery-contract-acceptance-20260906.md),
[C1/C2](reports/worker-launch-contract-acceptance-20260906.md) and
[policy](lane-policy.md) retain their owners and acceptance requirements.
The descriptor is transport between trusted startup, shared policy and adapters;
it creates no authority, configuration registry, executor or session store.

`prepare_conductor(trusted_context, selection, forwarded_tokens, operation)`
is the startup composition interface. It returns the descriptor below and the
adapter's compiled launch, or a refusal before durable state or child creation.
`trusted_context` is supplied by the admitted caller through a direct in-process
argument or inherited read-only descriptor, never a caller path, environment
variable, model tool argument or MCP parameter. It contains the policy owner's
verified binding, declaration sources, custody anchor and discovery boot inputs.

The held discovery boot inputs cross into the existing discovery process
through the declared
[`--discovery-boot-fd FD` transport](discovery-lever.md#trusted-discovery-boot-transport),
alongside `--config FILE`: an inherited launcher-opened read-only directory
descriptor for the retained runtime artifact, separate from the inspected repo.
It grants only the discovery contract and lane_read/lane_mcp/lane_refs files
named there, with the same 1 MiB per-file, 4 MiB total and 10-second boot limits.
No new v3 key, query argument, store or executor is introduced.

The trusted launch owner must bind actual execution inputs, including the entry
module, to those held bytes. The lane_mcp boot custodian checks the
[executed-byte binding gate](discovery-lever.md#executed-byte-binding-gate)
before acquisition, repository anchors or fingerprints; a matching descriptor
digest or server self-report cannot replace load evidence. D-A47 requires
independent A/B mismatch and missing-load-evidence refusals, A/A and B/B clean
controls, and receipts binding process, artifact hashes and observed execution.
The runtime producer, trusted launch owner, independent test producer, reviewer
and integrator retain the responsibilities assigned there. Resume must meet
the same gate for its discovery process. Missing/rejected boot keeps discovery's
condition-specific refusal; startup applies its pre-effect/late timing below.
Discovery's independent recheck is pending; this reciprocal link claims no
acceptance, runtime completion or startup admission.

A digest is only an equality check against these held inputs, never proof of
trusted origin. Resolve executable/configuration identities and selection first,
reserve the canonical dispatch identity in memory on launch (reuse it on resume),
validate policy/grants/capability, then let the
canonical dispatch/harness owner prepare transport and invoke the child.

The serialized descriptor is strict UTF-8 JSON, at most 65536 bytes, nesting
at most 32; reject duplicate/unknown/missing keys, non-finite numbers, wrong
types (boolean is not integer) and control characters in strings. All objects
below are closed and all keys required, including nullable keys. `SHA256` is
64 lowercase hex; `ID` and repository/anchor types are exactly
[discovery's types](discovery-lever.md#trusted-configuration-and-bounded-profiles).
Canonical digest encoding for these new interfaces is sorted object keys,
ASCII JSON escaping, compact separators, UTF-8, no trailing newline; arrays
retain order. Exact file-byte digests and policy `show` digests retain their
owning recipes. Do not substitute this encoder for them.

`DispatchID` is the canonical execution record's `id` under the
[dispatch job directory](../devlane/dispatch/CONTRACT.md#the-job-directory):
`<UTC stamp>-<stage>-<harness>-<6 hex>`, for example
`20260906T120000Z-conduct-codex-a1b2c3` for a conductor. Stage is literal
`conduct`; role is conductor; job and brief are null under dispatch's
[complete canonical variant](../devlane/dispatch/CONTRACT.md#canonical-conductor-record-variant-proposed).
Worker stages and read/write job roles stay distinct. This declared extension
awaits runtime/validator support; it is not discovery's `ID` or a worker job.
`launch_id` equals that record's id byte-for-byte: launch reserves a fresh id
through the canonical dispatch owner before admission, and resume retains the
same id from the trusted record and parent descriptor. Model observations,
custody and receipts resolve through that record; no second id or correlation
store is introduced. Refuse a mismatched record/descriptor binding before effects.

`LaunchSelection` is exactly
`{harness:ID,model:string,effort:string|null,role:"conductor",job_role:null,profile:ID}`.
Model and non-null effort are nonempty, at most 128 printable ASCII bytes.
This named launch type is distinct from discovery's handoff `Selection`.

| field | type / obligation |
|---|---|
| schema | literal `conductor-launch/1` |
| launch_id | DispatchID, bound to the canonical execution record as above; no filesystem reservation before admission |
| operation | `launch` or `resume` |
| selection | LaunchSelection |
| custody_sha256 | digest of the retained trusted caller custody evidence; verified against the previously admitted anchor, never supplied by the candidate |
| policy_binding_sha256 | canonical digest of policy's closed ConductorBinding, retained as record.conductor.binding; exact [derivation](lane-policy.md#trusted-binding-input-and-declaration-transport), no fabricated worker brief |
| discovery | `{config_sha256:SHA256,repository:Repository,anchors:[{id:ID,device:int,inode:int},...]}`; config digest is exact v3 file bytes; nonnegative device/inode, unique anchors sorted by id, exactly the config anchor set |
| adapter | `{revision:SHA256,mechanism:string,grammar_sha256:SHA256,normalizer_sha256:SHA256,executable_sha256:SHA256,config_sha256:SHA256}`; mechanism is nonempty printable ASCII, at most 128 bytes; bound effective controlled configuration, not ambient user settings; exact [capability mapping](harness-capabilities.md#conduct-capability-identity-encoding) |
| forwarded_tokens | admitted array of strings under the safe argv grammar, never raw rejected input |
| mcp | `{server_sha256:SHA256,config_sha256:SHA256,catalogue_sha256:SHA256}`; server digest covers pinned server/runtime closure; config equals discovery.config_sha256; catalogue hashes canonical tools/list result including schemas |
| resume | null on launch; otherwise `{parent_descriptor_sha256:SHA256,session_binding_sha256:SHA256}` from trusted retained transport |

`Repository` above is discovery's exact repository object, not a new root
locator. Startup supplies the existing v3 `--config FILE` to lane_mcp from
held, verified bytes and pinned anchor handles. It does not add descriptor
keys to v3 or a profile key to lane.conf. Any configured selection and explicit
selection must agree; no job/model table, infrastructure lane inference or
Daybreak role promotion. The selected profile must exist in both admitted
policy and discovery configuration; discovery work_roots describe relevance,
never effective write grants. Additional configured profiles use the same path.

A structural example fragment (not an entire descriptor or live evidence):

```json
{"harness":"codex","model":"fixture-model","effort":null,"role":"conductor","job_role":null,"profile":"dev"}
```

Independent fixtures supply full descriptors from synthetic trusted inputs,
then change each required field independently. A descriptor with that selection,
operation launch and resume null is structurally compatible; it still requires
all other fields, held input equality and live capability before admission.
Model observation records requested versus actual identity through the existing
execution record. An absent or conflicting observation cannot certify selection.
The descriptor is retained as record.conductor.descriptor; its selection must
equal both ConductorBinding.selection and LaunchDeclarations.selection. Null job
does not skip source/grant/capability checks or select worker defaults. Dispatch
owns record construction, supervision, close/resume and every consumer's variant
handling; startup neither emits a task envelope nor creates a second store.

### Connection, onboarding and resume binding

Before handing control to a conductor, verify the connection from that actual
client: fresh MCP initialize/tools/list and a real tools/call `lane_start` with
`{"profile":"dev"}` for the example. Check catalogue identity, config/anchor
binding and the complete discovery envelope. Bind the client/session and server
transport identities in trusted transport evidence; a separately launched CLI
query proves read-service parity only. A server self-reported digest or a
configured server entry alone cannot prove which server the client reached.
Absent connection evidence prevents startup; a partial but valid discovery
packet may onboard with its explicit unavailable/unknown sources. It must not
invent a handoff, select by filename/time or ask for filesystem hints. Supply
one bounded lane_start packet automatically, then relevant named detail under
its snapshot/cursor rules. Preserve eleven v3 tools and v1/v2 bytes.

An `Invalid params` response requires comparison of actual tools/list and
request bytes from the connected client; it does not establish server absence.
Diagnostics report this without rewriting host settings. MCP stays read-only;
[tool decisions](permission-surface.md#normalized-conductor-tool-interface)
govern other tools and canonical CLI delegation independently.

Resume revalidates custody and stationary policy, selection, source grants,
v3 config/anchors, adapter, safe tokens and MCP catalogue before restoring
session state, clearing markers, incrementing attempts or starting a child.
Recompile with operation resume; verify the recorded invariant launch digest
and the operation-specific vector rules in the adapter contract. Launcher-owned
session tokens may differ only as those rules declare; raw vendor resume flags
are never an alternative route. Reverify the actual client MCP connection and
perform automatic onboarding again. Changed discovery content gets a fresh
snapshot; it cannot silently change bound roots, permissions or profile.
Unbound legacy sessions remain readable; continuation requires a fresh admitted
launch. Existing canonical records carry custody and receipts, no new store.

### Startup refusal and verification boundary

Use the owning lane-profile/lane-policy/lane-resume refusals for those failures.
`conduct-config` covers malformed/untrusted descriptor transport; `conduct-mcp`
covers missing or mismatched actual connection. Both use the wire and
secret-free fixed reasons, with a remedy naming the independent doctor.
For example: `conduct-mcp: expected bound client connection; found unavailable;
needed run the independent doctor and restore verified connection evidence`.
Adapter and tool refusals retain their own classes. No permission prompt,
attended fallback, self-admission or automatic harness substitution is allowed.
The [policy timing boundary](lane-policy.md#pre-effect-rejection-and-late-refusal)
also governs conduct-config/conduct-mcp: before any launch mutation, exit 2,
empty stdout and one refusal line; from the successful canonical directory claim
onward, Abort 3 with retained partials. Actual-client connection checks occur
after child creation and their failure is therefore late, even before control
is handed to the conductor. Resume preflight precedes its first mutation;
reconnection failure after restoring state/starting the client is late.
The refused PolicyResult and conductor result.status carry non-acceptance;
missing evidence uses null, never a fictitious attempt, connection or receipt.

Independent startup cases must cover: full synthetic descriptor round-trip;
unknown/duplicate keys and missing nulls; untrusted matching digests; all five
selection axes independently; positive coordination/delegation; safe forwarding;
missing/mismatched MCP versus partial valid discovery; dev/prod/additional
profiles without path hints; and resume mutation before any transport effects.
Use test_conduct_start.py and test_conduct_enforcement.py under the existing
conductor test owner, with verified fake counterparties. These are construction
targets, not assertions that tests or live mechanisms have already passed.

### Correction custody — 2026-09-06 ruling

The bounded unit1a correction preserves combined commit
`f15ca22c7d0cedb14f8d299fd61d7135f04ea9bc`, invalid worker record
`20260906T111519Z-code-codex-dce07d` and the historical absence checker.
Canonical custody is in `uscient/agentscient`, at commit
`3ee48f0d8e9dc7f76a5ab9d6f600136338973118`:

- [Archive README and retained split artifacts](https://github.com/uscient/agentscient/blob/3ee48f0d8e9dc7f76a5ab9d6f600136338973118/.dev/ladder-inputs/conduct-unit1a-20260906/README.md)
  under `.dev/ladder-inputs/conduct-unit1a-20260906/`.
- [Original invalid dispatch record](https://github.com/uscient/agentscient/blob/3ee48f0d8e9dc7f76a5ab9d6f600136338973118/.dev/records/dispatches/20260906T111519Z-code-codex-dce07d.json)
  under `.dev/records/dispatches/`; its envelope remains `status: invalid`,
  `verdict: null`.

Measured 2026-09-06 against that commit using `git show COMMIT:PATH`, Python
Base64 decoding and SHA-256: the table names decoded original patch bytes and
plain commit-message bytes, not the Base64 storage hashes.

| archived file | original bytes | SHA-256 |
|---|---:|---|
| `01-interface-fix.patch.b64` | 7055 | `3cd7a4838d4181870a3fe67aa89c82cecfa4d809059449ca20c3441d47fc6477` |
| `01-COMMIT_MSG` | 873 | `30ea73a9f71b6a377b4bafc1cae327ec10e9c963d308a2de81cd493d20a1672b` |
| `02-unit1a.patch.b64` | 37212 | `dad3831caa7b480fdb01458bdd60d252892bbee72b23b804989e119ce179c919` |
| `02-COMMIT_MSG` | 1065 | `858833ad25591105db06f170ef07186d9a0fd2bfab6ef33927f6c3764ae93f33` |

Decode with `base64 --decode FILE.patch.b64`. The original record is 15932 bytes,
SHA-256 `80dda3ec259623cbb0fc0a2ae6fc92f2216d12982d3efc28a4ab52613a9223d9`.
Raw capture commit `c35ed64e7154eddbc1bea3511567032813f833f3` and Base64 retention
commit `42c9efee03831f4cfef5044dd3b29672456ed971` retain the archive history.
All four cited commits resolve in this snapshot at
`b15f6904932d134b5e42ee1c9c60708ca8ef48a7`; the earlier review's inaccessible
objects describe its snapshot, not canonical absence. Remote link availability
was not checked; their pinned Git paths were. Custody remains the conductor's
duty; this correction copies no retained artifact. Do not reconstruct a split,
rewrite the combined commit, repair the historical verdict or reuse its checker
as present acceptance. The ruling permits one clean correction commit; runtime,
independent tests, live capability and policy admission remain separate.
