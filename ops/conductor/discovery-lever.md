# Discovery lever — contract

Standing: contract admitted for authorized step 1 (owner, 2026-09-05).
The instrument is ABSENT until step 2. This document is the
specification independent test authors write against. It inherits
[`instrument-conventions.md`](instrument-conventions.md): the refusal
wire, four-class exits, and lint duty apply; restating them is drift.

Source of demand: a fresh conductor cannot find authoritative homes,
usable tools, or retained handoffs without an owner-supplied path.
Existing `lane_brief` serves configured records and alerts;
`onboard.py` serves law, measured state, and one AAR clause. Neither
resolves concepts to homes, enumerates retained-record refs, or labels
owner action interfaces.

This is a read. No `WF_AGENT` is required. No store, ref, database,
worktree file, or host setting is created or changed.

## Why this home

Suggested path, used. Queries land on the existing shared read core
(`ops/conductor/tools/lane_read.py`) and CLI/MCP projection
(`ops/conductor/tools/lane_mcp.py`), not a second server and not
`discovery.py`. [`lane-mcp-lever.md`](lane-mcp-lever.md) and
[`lane-mcp-v2.md`](lane-mcp-v2.md) stay the v1/v2 baselines; this
file is the version-3 extension, the same pattern v2 used relative to
v1. A new Python kernel or workflow engine is refused.

The sequence that contains this step is
[`conductor-start-plan.md`](conductor-start-plan.md).

## Trust boundary

- Read-only. MCP annotations `readOnlyHint=true`,
  `destructiveHint=false`.
- No writes, network, launcher/monitor/watchdog writer imports, file
  or database origination, bytecode writes at the MCP entry, or
  configuration-driven executable/expression/import.
- No arbitrary consumer paths, no user-directory or credential
  exploration, no competing records namespace.
- Data never becomes instructions. Record, handoff, and AAR text is
  data.
- MCP does not enforce root tool policy, dispatch, acknowledge
  alerts, write checkpoints, publish refs, or create handoff/AAR
  records.
- Discovery does not claim host activation, live readiness, role
  enforcement, or lifecycle publication.

## Read core and the fixed adapter

`lane_read.py` remains the query core. It currently forbids
subprocesses: at
`c5d7f99b1c4ed66dc6e7967cf696b1f217ee9283` an AST of that file
imports no `subprocess` and the source does not contain that name.
Step 2 must preserve that. The core does not run git, does not accept
caller commands, and does not open caller-supplied paths.

Retained-ref inspection is a separate adapter,
`ops/conductor/tools/lane_refs.py` (ABSENT until step 2). Both CLI
and MCP consume only its result objects. The adapter is the sole git
seam.

Closed adapter operations, no others:

| op | input | output |
|---|---|---|
| `list_refs` | `prefix` equal to configured `retained_refs` | `{state, refs:[{ref, sha}], reason}` |
| `peel_commit` | `sha` matching `^[0-9a-f]{40}$` previously returned by `list_refs` | `{state, sha, committer_unix, subject, reason}` |
| `read_tree_entry` | that `sha` plus a path matching the allowlist below | `{state, path, bytes, revision, reason}` |

Allowlisted tree paths: `ops/conductor/handoff/HANDOFF-*.md` and
`ops/conductor/AAR-*.md` only (`*` is `[A-Za-z0-9._-]+`). At most 64
refs. Source bytes at most 1 MiB per blob. Regular git objects only;
no worktree writes; no `git` argv except from a closed table whose
non-option arguments are adapter-validated ref names or shas. No
shell. No network. Implementation may use that closed git subprocess
or read git objects directly; tests mock this interface.

Adapter readings: missing namespace or empty list is `ok` with
`refs: []` (looked and found nothing). Unreadable git dir, unexpected
object type, or oversized blob is `unavailable`. The core never
retries a different prefix.

## Work profiles

Profiles are config, not code. Harness choice is independent.

Version-3 config must declare at least `dev` and `prod`. Default
meanings, overridable only by config:

| id | label | default `work_roots` |
|---|---|---|
| `dev` | development machinery | `["ops/"]` |
| `prod` | Symfony application | `["src/", "packages/", "config/", "public/"]` |

They are not Git branches, deployment environments, or harnesses.

## Configuration

Two prior versions remain valid and byte-identical. Version 3 adds
discovery sources. Config is a regular file, nonblocking, at most
64 KiB, loaded once per process, same printable/path rules as
[`lane-mcp-lever.md`](lane-mcp-lever.md). No missing-source fallback,
environment lookup, or default retained-ref path.

| version | exact keys | `check.tools` |
|---|---|---|
| 1 | `version, dispatch_store, job_ids, monitor_state, consumer, usage_rollout` | 4 |
| 2 | those plus `job_registry` | 7 |
| 3 | those plus `profiles, retained_refs` | 11 |

- `version` 3 without the new keys, `version` 1 or 2 with them, any
  other version, duplicate/unknown keys: class `config`.
- `profiles` is an object. Keys match `^[a-z][a-z0-9-]{0,31}$`. `dev`
  and `prod` are required. Each value is an object with exact keys
  `label` (printable ASCII 1..128, no slash or backslash) and
  `work_roots` (unique list, 1..16 strings). Each root matches
  `^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*/$`, is relative, and contains
  no `..`. Other keys in a profile object: `config`.
- `retained_refs` is `null` (disabled) or exactly `refs/heads/records/`.
- `check` validates only and returns `{valid:true,tools:N}`; no
  sources are read.

Example (all sources null except required profile declarations):

```json
{
  "version": 3,
  "dispatch_store": null,
  "job_ids": [],
  "monitor_state": null,
  "consumer": "conductor",
  "usage_rollout": null,
  "job_registry": null,
  "profiles": {
    "dev": {
      "label": "development machinery",
      "work_roots": ["ops/"]
    },
    "prod": {
      "label": "Symfony application",
      "work_roots": ["src/", "packages/", "config/", "public/"]
    }
  },
  "retained_refs": null
}
```

## Schema and projection

`schema` stays `agentscient.lane/v1`. `query` names the tool.
Canonical JSON encoder, CLI `query`, MCP `tools/call`, and matching
resources share exact payloads when source bytes are stationary. No
per-call clock. `params._meta` remains as in v2: object or absent,
ignored, never echoed.

CLI: `python3 -B ops/conductor/tools/lane_mcp.py --config FILE query TOOL [JSON]`.
Successful queries, including explicit `unknown`/`unavailable`
readings, exit 0. Domain refusals: exit 2, one stderr line, empty
stdout. Over MCP: `isError=true` with the same line. Missing data is
a reading, not a transport failure.

Under version 1 or 2, the four discovery names refuse class
`arguments` (unknown tool), the same as today's unknown-tool
handling. v1/v2 payloads, resources, and `check.tools` are unchanged.

## Text, revision, snapshot

Text rule: a string that UTF-8 encodes and is within its cap; else
null. Caps are UTF-8 bytes of the value. Caps: identifiers, concept,
kind, status, label 256; `where`/`path` 1024; `claim`/`reason`/
`one_liner`/`subject` 1024; handoff/AAR `body` 2048. Over cap: field
null, measured length kept where a `*_bytes` field exists; no
fabricated truncation.

`revision` is the first 16 lowercase hex characters of SHA-256 of
the exact bytes read from a file or blob within the 1 MiB bound
(same as v2). Git object ids, when known, are `git_sha` (40 hex),
never mixed into `revision`.

`snapshot` is the first 16 lowercase hex characters of SHA-256 of
the canonical JSON of `{sources:[{id, revision}, ...]}` in `id`
order from one `lane_start` result. Detail reads may pass it.
Mismatch refuses class `cursor`: `expected cursor for snapshot
<current>; found <given>; needed restart from lane_start`. Absent
snapshot means current sources. Grammar `^[0-9a-f]{16}$`.

Whole-query cap 16384 bytes: overflow is `unavailable`, never silent
truncation. `lane_start` is additionally capped at 8192 by the
omission sequence in §Queries.

## Provenance and freshness

Every result lists `sources[]` of `{id, kind, locator, revision,
git_sha, freshness}`. `kind` is `file`, `ref`, `adapter`, or
`index`. `locator` is a configured path or ref, never a
caller-supplied filesystem path. `git_sha` is null for files.

`freshness` is computed from source bytes and adapter results only,
not from the clock:

- `current` — this candidate is the selected member of its stem
  group, or it is ungrouped and readable.
- `stale` — another readable candidate shares the same stem and outranks
  it (worktree file beats a ref; else greater `committer_unix` wins;
  remaining ties are all `stale` and `selection` is `multiple` if they
  are the top rank).
- `unknown` — freshness cannot be determined (peel failed).

Stem: filename stem for tracked files (`HANDOFF-2026-09-04-driver`);
ref suffix after `refs/heads/records/` for refs. Comparison is exact.

## Queries

Closed argument objects. Unknown fields or types refuse `arguments`.
Bool is not int. Discovery tools exist only when `version` is 3.

### `lane_start`

Arguments: `{profile: string, snapshot?: string}`. `profile` is a
configured profile key, else class `profile`.

Result, `state: ok`:

```
{schema, query:"lane_start", state:"ok", reason:null,
 profile:{id, label, work_roots},
 law:[{path, status, one_liner}],
 state_sources:[{name, status, summary, evidence}],
 homes:[ownership_card],
 work:[work_card],
 handoffs:{selection, selected, current, stale, unreadable},
 actions:[action_card],
 sources:[...],
 snapshot: string,
 omissions:[string]}
```

`law` is onboard's law table (paths and one-liners from
[`onboard-lever.md`](onboard-lever.md)), `status` `OK` or `ABSENT`,
no file bodies. `state_sources` are onboard's labelled state names
(`register`, `ledger`, `prs`, `dispatches`, `branch`) as compact
summaries under the 256-byte text rule; a source that cannot be
measured is `status:"unavailable"` with `summary` the reason. These
readings are composed from existing onboard data sources via the
query core and adapter; `onboard.py` is not imported (it uses
subprocess). Until step 2 names the exact composition, tests plant
the same file/registry/db sources onboard already documents and
assert the card fields, not onboard's stdout layout.

`homes` is the concept index rows whose `profiles` include the
requested profile, at most 8, contract order. `work` at most 8
compact cards (current branch; open PRs if the `prs` source is
measurable; configured dispatch ids). More become an omissions
entry, not a silent drop. `handoffs.selected` is the full candidate
card iff `selection` is `one`; otherwise null. Handoff bodies are
not included on the start page (`body: null`, `body_bytes` may be
set). `actions` is the four action cards in contract order.

Omission sequence when encoded size exceeds 8192: drop `work` cards
(keep `work:[]` and an omissions reason), then `homes` to empty,
then handoff lists to empty while keeping `selection` and counts in
`reason`, then `actions` to empty. If the frame still exceeds 8192,
`unavailable` with reason `"page frame exceeds 8192 bytes"`.

Declared omissions, always present as strings:

- `no host activation`
- `no live readiness`
- `no role enforcement`
- `no lifecycle publication`
- `no raw documentation dump`

### `lane_homes`

Arguments: `{concept?: string, profile?: string, snapshot?: string}`.
`concept` grammar `^[a-z][a-z0-9-]{0,63}$`. Unknown concept with
valid grammar is `state: ok`, `home: null`, reason `"concept is not
declared in the index"` — an answer, not a refusal. `profile` when
present must be a configured key.

Without `concept`: `homes` is the matching index rows, at most 16;
more → `unavailable`, reason `"index lists more than 16 homes"`. A
named concept is not blocked by that list cap (same ruling as v2
named job cards).

### `lane_handoffs`

Arguments: `{key?: string, profile?: string, snapshot?: string}`.
`key` grammar `^(tracked|ref)/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`.

Sources, in this order, no others:

1. Tracked files: `ops/conductor/handoff/HANDOFF-*.md` and
   `ops/conductor/AAR-*.md` in the current work tree, opened as
   `lane_record` opens files (regular, no symlink follow, ≤ 1 MiB).
2. Adapter `list_refs` then `read_tree_entry` for allowlisted paths
   when `retained_refs` is not null.

`key` absent: the candidate lists, no bodies. `key` present: one
card with `body` under the text rule if that key is a listed
candidate; if not listed, `state: ok`, `selected: null`, reason
`"handoff is not a listed candidate"`. Retrieval uses `key`, never a
filesystem path.

`selection` over the `current` list only: `none`, `one`, `multiple`.
`selected` is non-null iff `selection` is `one`. Unreadable
candidates are never dropped. Stale candidates are never selected.
Empty tracked set plus empty adapter list is `selection: none`,
state `ok` (looked and found nothing). Adapter `unavailable`
populates `unreadable` with one synthetic card `key: "ref/namespace"`.

At most 16 cards across `current`, `stale`, and `unreadable`
combined for the list form; more → `unavailable` for the list.
Named lookup of a known key still returns that card.

### `lane_actions`

Arguments: `{name?: string, snapshot?: string}`. `name` grammar
`^[a-z][a-z0-9-]{0,31}$`. Without `name`: the four cards. With
`name`: one card, or `state: ok`, `action: null`, reason `"action is
not declared"` for an unknown name.

## Cards

### Ownership card

```
{concept, home, contract, entrypoint, registry,
 present, installed, activated, probed,
 status, intended, notes, evidence}
```

- `home`, `contract`, `entrypoint`, `registry`: paths or commands
  from the index, else null. Never the home-map report path as
  `home`.
- `present`: the entrypoint or contract path exists as a tracked
  regular file. False is an answer.
- `installed`: named Composer package is in `composer.lock` when
  that is the evidence source; otherwise null (not measured). Never
  inferred from `docs/mapping.md`.
- `activated` and `probed`: always null in this slice. Discovery
  does not claim host registration or a live protocol probe.
- `status`: `owned` when `home` and `contract` are non-null;
  `absent` when the index says the instrument is ABSENT;
  `unresolved` when the index marks it so. Unresolved is visible;
  the service does not guess.
- `intended`: Symfony package or projection name from the index, or
  null. Not a presence claim.
- `notes`: incompleteness, or null.
- `evidence`: `{kind:"index", locator:"ops/conductor/discovery-lever.md", revision, git_sha:null}`
  for index-derived cards.

### Work card

```
{kind, id, title, profile, locator, revision, freshness}
```

`kind` is `branch`, `pr`, or `dispatch`. `locator` is a ref, PR
number string, or configured dispatch id. No prompt text, no
transcript.

### Action card

```
{name, owner, entrypoint, available, reason}
```

`available` is true only when `entrypoint` names an existing tracked
file. `entrypoint` is never a callable handle. Unavailable actions
keep `entrypoint: null` and a fixed reason. No invented command.

### Handoff candidate card

```
{key, kind, stem, locator, git_sha, revision, freshness,
 body, body_bytes, reason}
```

`kind` is `tracked` or `ref`. `body` is null on lists and on start;
filled only on named `lane_handoffs`. Over cap: `body: null`,
`body_bytes` measured. Hostile content is JSON-escaped data.

## Action index

| name | owner | entrypoint | available |
|---|---|---|---|
| `onboard` | this instrument's sibling | `python3 ops/conductor/tools/onboard.py` | true if that file is present |
| `handoff` | owner-initiated; placement declared in `handoff/README.md` | null | false, reason `"no handoff instrument"` |
| `aar` | owner-initiated; AAR files live under `ops/conductor/` | null | false, reason `"no aar instrument"` |
| `closeout` | owner-initiated combined handoff+AAR | null | false, reason `"no closeout instrument"` |

Exit, crash, and compaction do not manufacture these records. Future
writes are step 4, outside discovery.

## Concept index

Amended by commit, like onboard's law table. The home-map is
evidence that informed this list; it is not an authoritative source
and must not appear as `home`. Where a live entrypoint is missing,
`status` is `absent` and `present` is false.

| concept | profiles | home | contract | entrypoint | registry | present target | intended | status |
|---|---|---|---|---|---|---|---|---|
| `wire` | dev, prod | `docs/wire.md` | `docs/wire.md` | null | null | `docs/wire.md` | `packages/wire` (not created) | absent |
| `workflow-genus` | dev, prod | `docs/workflow.md` | `docs/workflow.md` | `ops/devlane/workflow/` | null | `docs/workflow.md` | `symfony/workflow` | owned |
| `wf-runtime` | dev | `docs/workflow.md` | `docs/workflow.md` | `wf.py` | null | null (ABSENT) | `symfony/workflow` | absent |
| `probes` | dev, prod | `docs/probes.md` | `ops/conductor/probes-lever.md` | `ops/conductor/tools/probes.py` | null | null (ABSENT) | null | absent |
| `concerns` | dev, prod | `docs/concerns.md` | `docs/concerns.md` | null | null | `docs/concerns.md` | null | owned |
| `verified-couplings` | dev, prod | `docs/verified-couplings.md` | `docs/verified-couplings.md` | null | null | `docs/verified-couplings.md` | null | owned |
| `mapping` | prod | `docs/mapping.md` | `docs/mapping.md` | null | null | `docs/mapping.md` | four projections | owned |
| `onboard` | dev, prod | `ops/conductor/onboard-lever.md` | `ops/conductor/onboard-lever.md` | `ops/conductor/tools/onboard.py` | `ops/conductor/registry/onboard.py.json` | that tool | Console, TUI, MCP, API | owned |
| `lane-mcp` | dev, prod | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/tools/lane_mcp.py` | null | that tool | `symfony/mcp-bundle` | owned |
| `lane-read` | dev, prod | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/tools/lane_read.py` | null | that tool | same | owned |
| `dispatch` | dev | `ops/devlane/dispatch/CONTRACT.md` | `ops/devlane/dispatch/CONTRACT.md` | `ops/devlane/dispatch/launch.py` | `ops/devlane/task/jobs.json` | that tool | `symfony/ai-platform` | owned |
| `harness` | dev | `ops/devlane/harness/` | `ops/devlane/harness/` | null | null | directory as path prefix | null | owned |
| `jobs` | dev | `ops/devlane/task/jobs.json` | `ops/devlane/task/CONTRACT.md` | `ops/devlane/task/jobs.json` | `ops/devlane/task/jobs.json` | that file | null | owned |
| `handoff` | dev, prod | `ops/conductor/handoff/README.md` | `ops/conductor/handoff/README.md` | null | null | that README | null | absent |
| `aar` | dev, prod | `ops/conductor/` | newest `ops/conductor/AAR-*.md` | null | null | AAR glob | null | absent |
| `decisions` | dev, prod | `ops/conductor/decisions-register.md` | `ops/conductor/decisions-register.md` | `ops/conductor/tools/decisions.py` | `ops/conductor/registry/decisions.py.json` | that tool | Doctrine, Workflow | owned |
| `ledger` | dev, prod | `ops/conductor/handwork-ledger.md` | `ops/conductor/handwork-ledger.md` | `ops/conductor/tools/hand.py` | `ops/conductor/registry/hand.py.json` | that tool | Doctrine, Workflow | owned |
| `watch` | dev, prod | `ops/conductor/watch-lever.md` | `ops/conductor/watch-lever.md` | `ops/conductor/tools/watch.py` | `ops/conductor/registry/watch.py.json` | that tool | HttpClient | owned |
| `land` | dev, prod | `ops/conductor/land-lever.md` | `ops/conductor/land-lever.md` | `ops/conductor/tools/land.py` | `ops/conductor/registry/land.py.json` | that tool | Process, Workflow | owned |
| `ci-store` | dev | `ops/conductor/ci-store.md` | `ops/conductor/ci-store.md` | `ops/conductor/tools/ci.py` | `ops/conductor/registry/ci.py.json` | that tool | HttpClient | owned |
| `branches` | dev, prod | `ops/conductor/branch-census.md` | `ops/conductor/branch-census.md` | `ops/conductor/tools/branches.py` | `ops/conductor/registry/branches.py.json` | that tool | Process | owned |
| `skills` | dev, prod | `.claude/skills/skills/SKILL.md` | that skill | `ops/conductor/tools/skills.py` | null | that tool | null | owned |
| `permission` | dev, prod | `ops/conductor/permission-surface.md` | `ops/conductor/permission-surface.md` | `ops/conductor/tools/co_doc.py` | null | that tool | null | owned |
| `monitor` | dev, prod | `ops/conductor/monitor-lever.md` | `ops/conductor/monitor-lever.md` | `ops/conductor/tools/monitor.py` | `ops/conductor/registry/monitor.py.json` | that tool | null | owned |
| `watchdog` | dev, prod | `ops/conductor/watchdog-lever.md` | `ops/conductor/watchdog-lever.md` | `ops/conductor/tools/watchdog.py` | `ops/conductor/registry/watchdog.py.json` | that tool | null | owned |
| `ladder` | dev | `ops/conductor/ladder-lever.md` | `ops/conductor/ladder-lever.md` | `ops/conductor/tools/ladder.py` | `ops/conductor/registry/ladder.py.json` | that tool | null | owned |
| `onboard-discovery` | dev, prod | `ops/conductor/discovery-lever.md` | this file | `ops/conductor/tools/lane_mcp.py` | null | this contract file | `symfony/mcp-bundle` | absent |
| `conduct` | dev, prod | `ops/conductor/conductor-start-plan.md` | that plan | null | null | that plan | Console adapters | absent |
| `packages` | prod | `packages/README.md` | `packages/README.md` | null | null | that README | bundle gestation | owned |
| `projections` | prod | `AGENTS.md` | `AGENTS.md` | null | null | `AGENTS.md` | CLI, TUI, MCP, API | owned |

`present target` is what step 2 checks for `present`. `wf.py`,
`probes.py`, handoff/AAR/conduct instruments, and this query surface
are ABSENT. `intended` packages that are absent from `composer.lock`
must keep `installed` null or false, never true.

## Resources

Listed in `resources/list` without reading evidence sources
(config only):

| URI | query |
|---|---|
| `lane://start/PROFILE` | `lane_start {profile}` one per configured profile key |
| `lane://homes` | `lane_homes {}` |
| `lane://handoffs` | `lane_handoffs {}` |
| `lane://actions` | `lane_actions {}` |

Templates (v3 only): `lane://homes/{concept}`,
`lane://handoffs/{kind}/{id}`, `lane://actions/{name}`. Version 1
keeps `resources/templates/list` as `-32601`. Version 2 keeps its
single job-card template. Version 3 returns the v2 template plus
these three. Continuation and snapshot are tool-only.

## Refusals and exits

| class | fires when |
|---|---|
| `config` | version/keys/types/paths as above |
| `arguments` | closed-object violation; discovery tool under v1/v2; bad `concept`/`key`/`name` grammar |
| `profile` | `profile` not a configured key |
| `cursor` | snapshot mismatch or malformed snapshot when present |

Reads need no identity. Class `identity` does not fire.

Exit 0: the query ran, including `unknown`/`unavailable`/`ok` with
empty lists. Exit 2: refusal wire. Abort (3) only on wall/kill; a
source timeout is `unavailable` on that card, not a hang. Exit 1 is
not used.

Fixed reason strings only; no source text copied into `reason`.

## Absence, ambiguity, malformed, unreachable, stale

| situation | reading |
|---|---|
| looked, zero candidates | `selection: none`, `state: ok` |
| exactly one current readable | `selection: one`, `selected` filled |
| two or more current readable | `selection: multiple`, `selected: null` |
| unreadable/malformed/oversize/symlink | `unreadable` list, not dropped |
| stale by the stem rule | `stale` list, never `selected` |
| `retained_refs` null | refs omitted; tracked files still searched; omissions includes `retained_refs disabled` |
| git dir missing | adapter `unavailable`; not a crash |
| unknown concept/action/key | `ok` with null card and fixed reason |
| unresolved ownership | `status: unresolved`, no guessed home |
| intended Symfony package | `intended` set, `installed` not true unless lock says so |
| source missing | `unknown` |
| source unreadable | `unavailable` |
| could not look (timeout, EPERM) | `unavailable` with reason; distinct from empty |

## Compatibility

- v1 and v2 configs, tools, resources, and payloads remain
  byte-identical.
- No PHP, API, or TUI parity claim. Four projections remain
  direction (`AGENTS.md`; `docs/mapping.md`).
- `lane_brief` is unchanged and does not include discovery.
- No new store, no `refs/conductor/closeout/*`, no default
  `retained_refs` path.
- `onboard.py` remains the onboard instrument. Discovery composes
  its sources; it does not replace the brief CLI.

## Smallest extensions, not applied in this step

1. Onboard law table: add `ops/conductor/discovery-lever.md` and
   `ops/conductor/conductor-start-plan.md`. Not applied here; applying
   the contract without the instrument would desynchronize
   `onboard.py`. Incompleteness is visible: those paths are ABSENT
   from today's brief.
2. Instrument-conventions registry: join when the version-3 queries
   land, with one hermetic `config` refusal. No registry file in
   this step (no new tool file).
3. Permission-surface ungated-read invariant: bounded update for
   conductor-role restriction is step 3.

## Coupling proof (for step 2 tests)

Counterparties: onboard law/state lists in `onboard-lever.md`;
handoff paths in `handoff/README.md`; AAR glob under
`ops/conductor/`; lane MCP bounds and encoder in
`lane-mcp-lever.md` / `lane-mcp-v2.md`; `composer.lock` package
names; git ref prefix `refs/heads/records/`. Independent tests plant
synthetic trees, refs (via a fake adapter), and configs. They do not
read the live dispatch store, live git records namespace, or this
checkout's AAR bodies as oracles. A change to a counterparty
re-demands the fixture rows of the slice that reads it.

`lane_read.py` must still parse with no `subprocess` import after
implementation. Adapter tests may exercise git behind `lane_refs.py`
only.

## Symfony mapping, remeasured

Same measurement as [`conductor-start-plan.md`](conductor-start-plan.md)
§Symfony mapping, remeasured (2026-09-06T00:56:13Z,
`c5d7f99b1c4ed66dc6e7967cf696b1f217ee9283`). Installed lock
packages that matter: Console, FrameworkBundle, Runtime, Yaml, Flex,
Dotenv, PHPUnit, phpunit-bridge, ai-mate and its plugin and Symfony
extension, all at the versions listed there. Absent from the lock:
`symfony/mcp-bundle`, `mcp/sdk`, `symfony/ai-platform`,
`symfony/workflow`, API Platform. `packages/` contains only
`README.md`. `vendor/` is absent in that snapshot. Packagist was
not queried. Intended ownership stays in `docs/mapping.md` and is
not reusable runtime.

This snapshot's `git for-each-ref` of `refs/heads/records` printed
nothing: the namespace is empty here. That is `selection: none` for
refs, not `unavailable`.

## Objective acceptance rows

Independent tests prove these against a planted tree. Positive
controls sit beside refusals. CLI, tool, and resource payloads are
compared as canonical bytes.

| id | assertion | pass |
|---|---|---|
| D-A1 | v1 config `check.tools` is 4; discovery names refuse `arguments` | exit 2, empty stdout |
| D-A2 | v2 config `check.tools` is 7; v2 payloads unchanged | byte-identical to v2 fixtures |
| D-A3 | v3 config `check.tools` is 11 | `{valid:true,tools:11}` |
| D-A4 | v3 `check` reads no sources | planted missing sources still `valid` |
| D-A5 | unknown config key or missing `dev`/`prod` refuses `config` | wire line, exit 2 |
| D-A6 | `lane_start` without `profile` or with unknown profile refuses `profile` or `arguments` | wire |
| D-A7 | `lane_start` `dev` returns ownership cards whose `home`/`contract` match the index for `lane-mcp`, `dispatch`, `onboard` | those concepts present; home-map path never `home` |
| D-A8 | `lane_start` `prod` returns `mapping`, `packages`, `projections`; `installed` is not true for `symfony/mcp-bundle` | lock-absent package not installed |
| D-A9 | `wf-runtime` and `probes` cards have `present` false and `status` `absent` | no guessed entrypoint |
| D-A10 | unresolved/absent concepts do not invent an entrypoint | `entrypoint` null where the index says null |
| D-A11 | zero handoff sources → `selection: none`, `selected: null`, state `ok` | looked and found nothing |
| D-A12 | one current readable tracked handoff → `selection: one`; `lane_handoffs` with that `key` returns `body` without a filesystem path argument | key only |
| D-A13 | two current readable candidates → `selection: multiple`, `selected: null` | both listed |
| D-A14 | malformed/oversize/symlink candidate appears in `unreadable`, not dropped, not selected | |
| D-A15 | older ref of the same stem as a tracked file is `stale`, not selected | stem rule |
| D-A16 | named lookup still returns a card when 17 list candidates would overflow the list | list `unavailable`; named `ok` |
| D-A17 | `handoff`, `aar`, `closeout` action cards have `available` false and the fixed reasons; `onboard` is available when the tool file exists | no invented command |
| D-A18 | CLI, tools/call, and resource payloads match on stationary sources | byte-identical |
| D-A19 | snapshot mismatch refuses `cursor` | restart message names current snapshot |
| D-A20 | hostile control bytes and prompt-like text in a handoff body are JSON-escaped data | no execution, no instruction promotion |
| D-A21 | before/after of a query: git refs, worktree files, and configured databases unchanged | hash/ref compare |
| D-A22 | `lane_read.py` has no `subprocess` import | AST |
| D-A23 | adapter rejects a prefix other than configured `retained_refs` | no call; core does not pass it |
| D-A24 | caller-supplied absolute path or command in arguments refuses `arguments` | no extra keys |
| D-A25 | reads without `WF_AGENT` succeed | no `identity` refusal |
| D-A26 | MCP tools advertise `readOnlyHint` true and `destructiveHint` false | tools/list |
| D-A27 | `omissions` on `lane_start` includes the five declared strings | exact strings |
| D-A28 | over-cap body is null with `body_bytes` set; query over 16384 is `unavailable` | no silent truncation |
| D-A29 | empty `retained_refs` namespace is `ok` empty, not `unavailable` | adapter `refs: []` |
| D-A30 | `lane_brief` under v3 is unchanged from v2 for the same v2 keys | byte-identical brief |
| D-A31 | discovery does not write checkpoints, publish refs, or create handoff files | before/after plus no writer imports |
| D-A32 | both profiles are accepted as config and as `lane_start` arguments independently of any harness name | no harness field exists |

## What this contract does not do

No executable tests, no `lane_refs.py`, no version-3 parser, no
example config file on disk, no registry row, no PR, no host
activation, no Packagist refresh. Step 2 implements the rows.
