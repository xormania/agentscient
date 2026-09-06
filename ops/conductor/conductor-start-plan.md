# Conductor start sequence

Standing: authorized documentation of the four-step sequence. Owner,
2026-09-05: "document it and start on step 1". The earlier pause on
contract work is superseded for this bounded step. This file is the
sequence, not a lever contract and not an implementation.

The discovery contract is [`discovery-lever.md`](discovery-lever.md).
Step 1 ends when that contract is admitted for independent test
authors. Steps 2–4 remain unbuilt.

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

Harness adapters (Claude, Codex, Grok) are a separate axis. Shared
policy, lifecycle, discovery, and grading are not implemented per
harness or per profile. Adapters translate vendor request/response
only.

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
`lane_read.py` / `lane_mcp.py`; add the declared adapter. Do not
require the missing generic workflow runtime (`wf.py` remains absent).

### 3. `conduct` with shared enforcement and live diagnostics

Profile configuration, separate Claude/Codex/Grok adapters, exact
argument forwarding, actual MCP connection verification, automatic
onboarding. Allowed work runs without permission prompts; forbidden
work is blocked by declared policy. No attended fallback. Shared
policy is not placed under one vendor. Diagnostic mode extends
`docs/probes.md` / `probes-lever.md` (positive, negative, unreachable);
synthetic payload tests alone do not certify a live harness.

### 4. Owner-initiated session lifecycle

Handoff, AAR, and an explicit combined action, each owner-initiated
and easy. Placement and discovery are system responsibilities;
publication is not manufactured by exit, crash, or compaction.
Unfinished checkpoints are an instance of the workflow genus in
`docs/workflow.md`, not a new lifecycle. Existing record paths remain
the publication lineage; `refs/conductor/closeout/*` is not admitted.
Harness transcripts are evidence, not the checkpoint owner.

## Mapping to existing homes

Session start, recovery, and owner-requested publication are instances
of the declared workflow genus. The missing `wf.py` runtime does not
block step 1 or 2. It does matter for creating recovery checkpoints
and publishing handoff/AAR records (step 4).

MCP stays the context-and-diagnostics plane, read-only. CLI parity is
required. MCP does not enforce root tool policy, dispatch, acknowledge
alerts, write checkpoints, or publish refs.

## Symfony mapping, remeasured

Measured 2026-09-06T00:56:13Z at
`c5d7f99b1c4ed66dc6e7967cf696b1f217ee9283`. Commands: `php -r
'echo PHP_VERSION;'`, parse `composer.json` and `composer.lock`,
`find packages`, `test -d vendor`. No Packagist call (no network).

| fact | reading |
|---|---|
| PHP | 8.4.25 |
| composer.json require | php >=8.4; `symfony/console`, `dotenv`, `flex`, `framework-bundle`, `runtime`, `yaml` at 8.1.* / ^2 |
| composer.json require-dev | phpunit ^13.3; `symfony/ai-mate` 0.13.0; `symfony/ai-symfony-mate-extension` 0.13.0; phpunit-bridge 8.1.* |
| lock installed | console v8.1.6, framework-bundle v8.1.6, runtime v8.1.0, yaml v8.1.6, flex v2.11.0, dotenv v8.1.6, phpunit 13.3.2, phpunit-bridge v8.1.6, ai-mate v0.13.0, ai-mate-composer-plugin v0.13.0, ai-symfony-mate-extension v0.13.0 |
| lock absent | `symfony/mcp-bundle`, `mcp/sdk`, `symfony/ai-platform`, `symfony/workflow`, `api-platform/core`, `api-platform/mcp` |
| `packages/` | only `README.md` (empty by declaration) |
| `vendor/` | absent in this snapshot |

`docs/mapping.md` remains the intended-ownership document (Packagist
table dated 2026-09-03; not re-queried). Intended four projections,
`symfony/mcp-bundle` as the later MCP twin, and Workflow as the genus
engine are direction, not installed capability. Discovery must not
report them as present.

## Limits this step keeps

- One bounded startup read plus targeted detail. A full documentation
  dump or whole-tree investigation in every root session fails.
- Current `lane_read.py` does not import or mention `subprocess`
  (AST of that file at the SHA above).
- No competing records namespace.
- No writes, network, arbitrary paths, credentials, or user-directory
  exploration.

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
