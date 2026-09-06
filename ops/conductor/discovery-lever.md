# Discovery lever — contract

Standing: corrected step-1 proposal under the
[review ruling](reports/discovery-contract-review-20260905.md), awaiting
independent review. Authorization to write is not admission or self-approval.
The v3 instrument is ABSENT until step 2. The
[sequence](conductor-start-plan.md) and this contract inherit
[instrument conventions](instrument-conventions.md) and the
[wire](../../docs/wire.md).

## Audience and ownership

This is the conductor discovery surface. Role (conductor/worker), work
profile (dev/prod/additional configured profiles), and harness are independent.
Trusted launch/configuration selects the audience and its allowed sources;
there is no caller-supplied role, repository, path, command, or consumer switch.
`conduct` starts conductors; the existing dispatcher starts workers for named
jobs. A worker must not inherit conductor sources through a shared harness or
profile. A separately bounded worker context/MCP follow-up belongs to the
[task contract](../devlane/task/CONTRACT.md) and
[harness context](../devlane/harness/context.cue): brief, authorized inputs,
relevant contracts, diagnostics/checks and outputs, with withheld material
excluded. Both roles reuse services with different catalogues and source grants.

These are existing dev-lane services under `ops/`, independent of the Symfony
application and never awaiting replacement by it. The latest owner scope in
the [reconciliation note](reports/discovery-reconciliation-20260906.md)
supersedes earlier framework targets in this draft and its cited reports.
Prod discovery describes application ownership; it imposes no application
dependency on discovery, dispatch, policy or worker tooling.

Two role-specific MCP server entrypoints/instances from one codebase remain
a proposed deployment boundary; writable conductor tools remain a separate
proposal requiring explicit revision of the standing read-only MCP contract.
Neither is admitted here. The parallel worker consolidation track precedes
conduct startup, not discovery; its contract still needs admission. The
`lane/lane-boundary-20260905` enforcement track is pending, not implemented
policy that discovery can claim to provide.

Extend `tools/lane_read.py` and `tools/lane_mcp.py`, not a second backend.
[lane-mcp-lever.md](lane-mcp-lever.md) and [lane-mcp-v2.md](lane-mcp-v2.md)
remain the v1/v2 baselines, including their existing limitations and payloads.
The four new queries are the only v3 extension. MCP stays read-only:
`readOnlyHint=true`, `destructiveHint=false`. Reads require no identity.
MCP visibility is not enforcement through other harness tools. CLI/API
actions, harness enforcement, lifecycle and ratification retain their owners.

No writes, database origination, ref updates, network, credential/user-home
exploration, source-controlled executable/import/expression, or writer-module
imports. Disable bytecode writes at entry. No policy engine, job runner,
session store, copied authority, or competing records namespace is introduced.

## Trusted configuration and bounded profiles

v1 has exactly `version, dispatch_store, job_ids, monitor_state, consumer,
usage_rollout`; v2 adds `job_registry`. v3 adds exactly `profiles, discovery`
to v2. Their tool counts are 4, 7, 11 respectively. Old config validation and
all seven old queries keep their existing semantics even under v3.
Only new discovery reads use the anchors below; this does not harden or
silently broaden the old rollout/record readers.

Config remains one regular, nonblocking file, at most 65536 bytes, loaded
once per process; duplicate/extra/missing keys, invalid types or constraints
refuse `config` before sources. `check` reads config only and returns exactly
`{"valid":true,"tools":11}` for v3. Reload requires restart.
For v3 configuration/new-source JSON, reject nesting deeper than 32, non-finite
numbers and integers outside signed 64-bit range before materialization;
malformed source JSON is a reading, not a server crash. No old reader changes.

Identifiers `ID`: `^[a-z][a-z0-9-]{0,31}$`; concepts:
`^[a-z][a-z0-9-]{0,63}$`; Git object IDs: 40 lowercase hex (SHA-1 repositories
only in this slice). Paths: printable ASCII, at most 1024 bytes, no empty,
dot or dot-dot components, backslashes, control bytes, tilde expansion or
glob expressions. Relative file paths have no leading/trailing slash; roots
are relative directory prefixes ending in slash. Absolute anchor paths begin
with slash and obey the same component restrictions. Labels: printable ASCII,
1..128 bytes. Bool is never int.

`profiles`: object of 2..16 ID keys, including dev and prod; every value has
exactly `label, work_roots, homes, startup_homes, source_ids, lineage`.
Roots: 1..16 unique roots; homes: 1..64 unique declared concepts in configured
order; startup_homes: 1..3 unique members of homes, in presentation order.
source_ids: unique subset of `repo, retained, dispatch/ID` (ID here is an
existing `job_ids` identifier with v1 grammar); repo is required; retained is
allowed only with a configured retained prefix; dispatch IDs need a non-null
dispatch binding. lineage is an ID naming the trusted work lineage, not a
branch-name heuristic. At most 22 source IDs per profile. No profile-specific
code branch or index column is allowed.

Shipped default declarations (all concepts remain reachable via homes):

| profile | label / roots | startup_homes | homes |
|---|---|---|---|
| dev | development machinery / `["ops/"]` | `["lane-mcp","dispatch","onboard"]` | all index concepts except mapping, packages, projections |
| prod | Symfony application / `["src/","packages/","config/","public/"]` | `["mapping","packages","projections"]` | all index concepts except wf-runtime, dispatch, harness, jobs, ci-store, ladder |

The homes lists above expand in index order; source_ids default to
`["repo"]`, lineage to the profile ID. A valid additional profile is
`{"label":"documentation","work_roots":["docs/"],"homes":["wire","onboard"],
"startup_homes":["wire"],"source_ids":["repo"],"lineage":"docs"}`.
Same algorithms, limits and resources apply. Config may override defaults;
acceptance uses the shipped declarations. Profiles are neither Git branches
nor deployment environments.

`discovery` has exactly these fields:

| field | exact type and meaning |
|---|---|
| audience | literal `"conductor"`; supplied by trusted launch, never MCP arguments |
| anchors | object of 1..8 ID keys to absolute directory paths; repo is required; paths are trusted capabilities, not discovered from HOME/CWD |
| repository | `{id:ID, root:"repo", gitdir:ID, common_gitdir:ID, head:OID, ref:string\|null}`; both gitdir keys name anchors; head is the trusted launch commit; ref null for detached or a validated full refs/heads name |
| retained_refs | null or exactly `"refs/heads/records/"`; no default/fallback namespace |
| dispatch | null or `{anchor:ID, path:relative-directory}`; binds the same resolved directory as v1 dispatch_store, but only profile-authorized job_ids are read |
| record_bindings | 0..256 entries, exact shape below; trusted metadata owned by handoff custody, not parsed from record prose |
| work_bindings | 0..20 entries `{id:job_id,lineage:ID,work_paths:[relative-file,...]}`; unique configured IDs, 1..64 unique paths |

A record binding has exactly
`{record_id:ID, kind:"handoff"|"aar", revision:SHA256, lineage:ID,
work_paths:[relative-file,...], supersedes:[ID,...]}`.
revision is the FULL 64-hex SHA-256 of record bytes; one unique record_id and
revision pair per entry, with no revision bound to conflicting IDs or metadata.
work_paths has 1..64 unique paths; supersedes has 0..16 unique IDs.
References must exist, have the same kind and lineage, and form an acyclic
graph; multiple revisions of one record_id are allowed only with identical
metadata (a changed revision is still separate evidence).
These are approved config assertions, not authentication inferred from Git.
Config provenance/custody is a launch responsibility. An untrusted branch
cannot install its own config or thereby authorize a record.

Anchors may point at existing state outside the repository; no store moves
are required. Root and gitdir/common-dir device/inode identities are pinned
by trusted launch. For linked worktrees, launch supplies and validates both
gitdirs; do not follow an arbitrary .git or commondir redirection.
All components are opened descriptor-relative beneath these anchors with
no symlink traversal, including ancestors; reject FIFO/device/socket and
unexpected directories. Never re-resolve an anchor through a mutable pathname.
If safe access cannot be established, report unavailable, not a fallback.
Configuration is granted from a similarly trusted launch descriptor.

## Fixed acquisition boundary

The current read core's no-subprocess restriction remains absolute.
`lane_read` accepts immutable readings; it never runs Git or imports
`lane_refs`. Both projections use one acquisition coordinator outside the
core. The proposed `tools/lane_refs.py` is the sole, fixed Git read adapter,
absent until step 2. The projection may call this adapter for v3 acquisition;
the v1/v2 no-subprocess boundary and entry behavior remain unchanged.
No command string or path supplied by a query reaches it.

Closed operations, all bound to the repository capability above:

| operation | input | successful data |
|---|---|---|
| anchor_head | trusted head OID and optional trusted ref | `{head:OID,ref:string\|null,ref_commit:OID\|null}`; verify commit type and ref correspondence |
| list_refs | configured retained prefix only | sorted `[{ref,commit:OID}]`; each ref must directly name a commit |
| list_tree | verified commit from anchor_head/list_refs | sorted `[{path,mode,blob:OID}]` for the two record path patterns |
| tree_entry | verified commit plus a path from list_tree or the fixed document/entrypoint set | `{path,mode,blob:OID}` or null for measured absence |
| read_blob | blob returned by list_tree/tree_entry in this acquisition | exact bytes; no revision expressions or caller OIDs |

Ref grammar here is `refs/heads/` followed by nonempty slash-separated
`[A-Za-z0-9_-][A-Za-z0-9._-]*` components, total ≤256 bytes, with no `..`,
trailing dot or `.lock` suffix in any component. Unexpected enumerated names
make that namespace malformed; they are never echoed into arguments. The
adapter verifies supplied head/ref correspondence; an existing ref pointing
elsewhere is repository-mismatch. Null ref is a declared detached snapshot.

Every operation returns exactly `{state:"ok"|"unavailable",reason:Reason|null,
data:object|array|string|null}`; internal bytes are byte buffers, not public
JSON strings. Failure has data null. Modes 100644/100755 and blob type only;
mode 120000, submodule/tree mismatches and non-commit refs are `object-type`.
Allowed record paths are `ops/conductor/handoff/HANDOFF-*.md` and
`ops/conductor/AAR-*.md`, where star is one or more ASCII letters, digits,
dot, underscore or hyphen. Enumerate paths before reading; a ref-only unknown
filename is discoverable. Other tree entries may be examined only to verify
fixed law/index/registry/entrypoint paths and composer.lock. Never recursively
explore user directories. Records are read from the pinned HEAD tree and
retained commit trees, not untracked or dirty worktree files; this scope is
declared in every startup omission. No filename or commit subject is an
instruction or evidence of relevance.

A Git subprocess implementation must use an absolute trusted Git executable,
fixed argv templates for ref enumeration, commit/type/tree/blob reads only,
no shell, revision syntax from callers, pathspec magic, user aliases or helper
commands. Set explicit gitdir/worktree/common-dir bindings; ignore ambient
CWD and all inherited GIT_* variables. Use an allowlisted environment only,
disable system/global config, replace objects, optional locks, lazy promisor
fetch, external diff/textconv, hooks and pagers; reject repository alternates,
replace/graft redirection, partial/promisor stores or external includes/helpers
that cannot be excluded. Repository-local config must not redirect object
access or execution. Object/pack/ref storage must stay beneath verified
gitdir/common-dir anchors, with no symlink components or special files.
Missing local objects are unavailable; never fetch. A direct-object
implementation must meet the same contract. This is a bounded adapter,
not a sandbox platform or general Git runner.

Bounds apply before materialization: at most 65 ref entries examined to
detect a 64-ref overflow; stable bytewise ref order. At most 257 matching
record occurrences across HEAD and retained trees to detect a 256-occurrence
overflow. Tree enumeration examines at most 4097 entries within the two
fixed directories per unique commit (4096 allowed), 1 MiB enumeration output
per operation, and 1 MiB+1 bytes per blob (1 MiB allowed). At most 16 MiB
aggregate object/file bytes, 512 operations and 10 seconds per acquisition;
each operation gets at most 2 seconds, counting process startup and decode.
Stop on the first exceeded bound; no unbounded sorting or buffering before
the cap. Ref overflow discards the entire retained result, tree overflow
discards that tree, and aggregate overflow invalidates acquisition. No partial
set can prove absence or unique selection. An empty successfully enumerated
namespace is ok empty; a disabled namespace was not searched.

Read each object once per acquisition. Re-enumerate enabled ref identities
and verify anchor/head/ref identities at the end, within the same budgets;
mutation yields `changed-during-read`, no snapshot, no selection, no retries.
File sources use the same pinned-descriptor discipline and verify identity,
size and modification metadata before/after; changed reads are unavailable.
Immutable object bytes are verified against their object IDs. No worktree,
Git config/index/ref/object, database, source file or host mutation is allowed.

## Local source composition

No importing or executing onboard, decisions, handwork, gh, launcher, monitor
or watchdog. Discovery reuses onboard's five law entries and five state
labels, not its subprocess acquisition. Each new query acquires the same
profile dependency closure, even a named action query with a startup snapshot.

| source ID | exact binding / derivation |
|---|---|
| config | canonical loaded v3 config, including all profiles, bindings and launch anchor identities |
| contract | compiled card/shape/law/action definitions for this contract revision; digest of their canonical data |
| adapter | acquisition protocol version `discovery-acquisition/1`, adapter implementation SHA-256 and trusted Git executable digest/version (null executable fields for direct objects) |
| repo | pinned HEAD and ref identity; fixed law paths, index homes/contracts/registries/entrypoints, composer.lock, and enumerated HEAD record blobs, all through the adapter |
| retained | configured prefix plus every enumerated ref→commit, tree entry/mode/blob and read outcome; read only when this profile includes retained |
| dispatch/ID | exactly anchored dispatch/ID/record.json, authorized by both job_ids and this profile's source_ids; regular file ≤1 MiB, no directory enumeration |

The latter four are never located by caller input or ambient state. Law
cards use onboard's literal path/one-liner table: `present` when a nonempty
regular tracked blob exists, `missing` for verified absence or empty bytes,
`unavailable` on a failed read. Startup state summaries are exact:

| name | status / summary / evidence |
|---|---|
| register | unavailable / null / []; reason `unsupported-local-reading` |
| ledger | unavailable / null / []; reason `unsupported-local-reading` |
| prs | unavailable / null / []; reason `unsupported-local-reading` |
| dispatches | ok / `{configured:N,readable:N,unknown:N,unavailable:N}` / authorized dispatch source IDs; measured counts, not live running or closed totals |
| branch | ok / `{ref:string\|null,commit:OID}` / ["repo"]; unavailable/null if head/ref acquisition fails |

There is no register/ledger/PR binding in this slice and no SQLite read for
these fields. Their existing stores and onboard output are unchanged.
Dispatch counts classify each existing lane_record-compatible structural
reading using an anchored read, not the old reader's ambient path handling;
they never probe PIDs or list other jobs. N is a non-negative integer;
no authorized dispatch IDs gives four zeros, not a claim about all dispatches.

Work is authorized dispatch summaries only, ordered by configured job_ids,
filtered by work_bindings as below; title null, no prompts/transcripts/PRs.
Branch state is already shown separately. Profile roots classify trusted
work_paths: a record is relevant iff lineage equals profile.lineage and at
least one path has an exact root prefix (directory boundary included).
Mixed-root work is relevant to each intersecting profile only if lineage
also matches; configuration must explicitly choose a common lineage for that.
No timestamps, branch words, titles, filename stems, or body text classify work.
Missing work metadata appears as unknown relevance, never guessed. Known
cross-profile work is excluded before returning any content.
For a readable dispatch, Work.revision is the full byte digest and
recorded_status uses the existing lane_record text rule. Missing work binding
sets lineage null, relevance unknown and reason metadata-missing. A relevant
bound dispatch keeps its lineage/relevance when its file fails; status/revision
are null and reason is the source failure (which takes precedence over missing
metadata). There is no title, live status or selected-work authority implied.

## Record identity, trust and selection

Occurrence identity is `{ref:string|null,commit:OID,path,blob:OID}`.
HEAD occurrences use the trusted ref or null. Deduplicate exact byte-identical
records by FULL SHA-256, across paths/refs/HEAD; retain all sorted occurrences
in internal dependencies. Public key is `record/<64-hex-sha256>`, stable
across identical occurrences; two blobs per ref have different keys unless
their bytes are identical. Same bytes classified as both handoff and AAR are
`metadata-conflict`, never selectable. Record IDs/kinds/relevance are taken
only from matching trusted record_bindings. A filename supplies a provisional
kind for an unbound card, never authority or priority.

Current/stale is evidence-relative, not time freshness. Among completely
observed, relevant bound records, a record is stale iff a readable relevant
candidate's trusted supersedes graph reaches its record_id; otherwise current.
Different revisions of one ID with no superseding record are tied current.
No tie-break by date, path, ref, HEAD location or commit timestamp. An AAR
can supersede only AARs and never becomes the selected handoff.
Non-UTF-8/oversized/unreadable bytes cannot count as readable evidence;
a valid body above the 2048-byte presentation cap is still readable up to
the 1 MiB source bound. Byte-identical deduplication compares bytes as well
as digests; a digest collision is metadata-conflict, never merged evidence.

Candidate cards have `relevance:"relevant"|"unknown"` (known irrelevant cards
are excluded), and `freshness:"current"|"stale"|"unknown"`. Missing bindings,
missing/unreadable bound evidence, metadata conflict or incomplete enabled
scan makes selection `unknown`, even beside one readable current handoff.
A binding for this profile whose bytes are absent from a complete scan is
visible as an unavailable candidate (`missing-bound-record`). Unbound
records remain visible as key/kind/reason only, no body or provenance paths
until relevance is established. This exposes incompleteness without leaking
cross-profile prose. Unknown records do not authorize actions.
Disabled retained refs are outside the declared scan scope: selection may be
one within repo only, with `retained source not searched` explicitly shown.

When all enabled scans are complete and relevant evidence readable:
zero current handoffs gives none; one gives one; two or more gives multiple.
Only one gives selected_key, including when lists span pages. Stale-only
handoffs give none with their stale cards still discoverable. AARs are listed
but excluded from handoff counts. Lexical key ordering is presentation only.
A per-file failure whose key cannot be computed lives in source issues, not
a fabricated candidate key, and still blocks selection.
Incomplete classification gives every returned candidate freshness unknown;
otherwise relevant cards follow the supersedes rule. Only failures in record
enumeration/reading/bindings affect Selection.complete; unavailable law,
lock or dispatch readings do not by themselves invalidate a complete record
scan. AAR metadata gaps conservatively block selection too. Relevant bound
cards have reason null unless their own bytes/presentation fail; unbound
cards use metadata-missing. Synthetic missing cards use missing-bound-record.

Every public candidate carries `trust:"untrusted-record"`. Text returned by
named detail is data, never an instruction channel. Consumers must render it
inside an explicit untrusted-data block naming key, revision and provenance,
followed by an end marker; text cannot close the block via an embedded marker
(the renderer escapes marker tokens). Claims require corroboration against
governing contracts and measured readings. No action is authorized solely by
record prose, even if binding, bytes, provenance and JSON syntax are valid.

## Exact public types and dependency snapshots

All shapes below are closed, all shown keys required. Arrays always exist.
Nullable means exactly the specified type or null, never an omitted key.
Strings are valid Unicode; public paths/IDs satisfy the config grammar.
Source prose is never copied into reasons. Canonical bytes use the existing
encoder (sorted keys, ASCII JSON escaping, compact separators); no call clock.

Reason is null or one of these fixed tokens:

| tokens | application |
|---|---|
| disabled, missing, unsupported-local-reading | explicit source not measured / absent |
| unreadable, unsafe-path, object-type, malformed, oversized, timeout | acquisition failure |
| ref-overflow, tree-overflow, record-overflow, budget-exceeded | incomplete bounded scan |
| changed-during-read, repository-mismatch | acquisition cannot bind stationary repository |
| metadata-missing, metadata-conflict, missing-bound-record | candidate not eligible |
| unknown-concept, unknown-key, unknown-action | successful named miss inside the profile catalogue |
| page-frame-exceeds-cap, item-exceeds-cap, response-exceeds-cap | no silent output truncation |
| body-exceeds-cap | named body omitted with measured byte count |

Missing source state is unknown; disabled/unsupported and failed sources are
unavailable; looked empty is ok. Public query state is ok or unavailable
only: partial source failures remain typed readings in an ok packet.
Acquisition-wide race/budget failure or response overflow gives unavailable.

`Source = {id:string,state:"ok"|"unknown"|"unavailable",reason:Reason,
fingerprint:SHA256}`. Source IDs are the table above, sorted bytewise.
Each source summarizes its whole acquisition: unavailable outranks unknown,
which outranks ok; when several failures occur, its public reason is the
first failure in operation/path/ref bytewise order. The fingerprint still
contains all observed failures. Config, contract and adapter are ok once
validation completes; retained is included with disabled when not granted.
Thus every closure contains these five IDs plus its authorized dispatch IDs.
fingerprint hashes canonical `{id,binding,state,reason,observations}`:
binding contains exact anchor capability identities and configured locators;
observations contain every attempted path, mode, byte revision (full SHA-256
or null), object/ref/commit identities, outcomes and limit/completeness
markers. repo also includes HEAD/ref checks, all card presence inputs and
lock bytes; retained includes the complete sorted ref map, even if every
blob is unchanged. config/contract/adapter observations are their definitions
above. Disabled inputs have explicit null observation inputs/data; no file mtime
or current clock enters a successful fingerprint. Transient OS error text is
normalized to the fixed reason. Exact duplicate observations collapse.

For an independently reproducible encoding, binding is exactly
`{configuration:loaded_v3_config,anchors:[{id,device:int,inode:int},...]}`,
anchors sorted by ID, from trusted launch (never process-local fd numbers).
An observation is exactly `{operation,input,state,reason,data}`. Operation
inputs are `anchor_head:{head,ref}`, `list_refs:{prefix}`,
`list_tree:{commit}`, `tree_entry:{commit,path}`, `read_blob:{blob}`;
successful data is the adapter table's output, except byte buffers normalize
to `{revision:SHA256,bytes:int}`. An anchored dispatch read is operation
`read_record`, input `{id:job_id}`, data `{revision:SHA256,bytes:int}` or null.
Failed operations have data null, including overflow; the reason records
the exact exceeded bound. Source classifications use their completed
observations plus the fixed failure sentinel, never an unbounded partial set.
Definition sources use one `definition` observation, input `{id:source_id}`:
config data is the loaded config; contract data is `{protocol:"discovery/3",
revision:SHA256}` with revision the full hash of this contract's trusted
Markdown bytes; adapter data is `{protocol:"discovery-acquisition/1",
implementation:SHA256,git:{revision:SHA256,version:string}|null}`. implementation
hashes canonical `[{path,revision},...]`, sorted by path, for lane_read.py,
lane_mcp.py and lane_refs.py from trusted launch bytes. All paths here have
the `ops/conductor/tools/` prefix. The direct-object implementation has git
null. Config/adapter source data is supplied by trusted boot, not record text.
Disabled sources use one `disabled` observation with input/data null,
state unavailable and reason disabled. Observation arrays sort by their
complete canonical bytes and deduplicate identical entries. repo and retained
contain their respective Git operations, including both before/after ref
checks; a blob shared between them appears once in each source's dependencies.
No step-2 author chooses another hash recipe or drops failed observations.

`snapshot` is FULL SHA-256 of canonical
`{protocol:"discovery/3",audience:"conductor",profile:ID,
sources:[Source,...]}`. This replaces the draft's inadequate 16-hex snapshot;
v2's 16-hex file revision is unchanged. Every detail query requires profile,
so its dependency closure matches lane_start. Source changes, failures,
adapter/config changes, ref movement to identical blobs, relevance or
supersedes changes invalidate continuation. No snapshot store is written.

Snapshot input grammar: 64 lowercase hex. Reacquire the entire bounded
profile closure for every request. If stationary acquisition is impossible,
return unavailable with snapshot null; do not validate an old cursor against
partial data. Otherwise compare any supplied snapshot before named lookup or
pagination; mismatch refuses cursor. Failure sentinels yield stable snapshots
when their observed failure states remain the same.

`Envelope = {schema:"agentscient.lane/v1",query:Query,state:"ok"|"unavailable",
reason:Reason,profile:ID,snapshot:SHA256|null,sources:[Source,...],data:Data|null}`.
For query-wide unavailable, data is null; sources retain completed bounded
source readings, except response overflow sets sources [] (dependencies still
bound by snapshot if known). Only unavailable may have null snapshot/data.
Successful named misses use reason unknown-* and a null item, not unavailable.

Types used by Data:

- `Home = {concept,home:string|null,contract:string|null,entrypoint:string|null,
  registry:string|null,ownership:"declared"|"unresolved",document_present:bool|null,
  implementation_present:bool|null,locked:bool|null,installed:bool|null,
  activated:bool|null,probed:bool|null,intended:string|null,evidence:[source_id,...]}`.
- `HomeSummary = {concept,home:string|null,entrypoint:string|null,
  document_present:bool|null,implementation_present:bool|null}`.
- `Law = {path,status:"present"|"missing"|"unavailable",one_liner}`.
- `StateSummary = {name,status:"ok"|"unknown"|"unavailable",
  summary:object|null,reason:Reason,evidence:[source_id,...]}`;
  the table in Local source composition defines the only summary objects.
- `Work = {id:job_id,lineage:ID|null,relevance:"relevant"|"unknown",
  recorded_status:string|null,revision:SHA256|null,reason:Reason}`;
  recorded_status follows lane_record's 256-byte text rule; no live status.
- `Candidate = {key,record_id:ID|null,kind:"handoff"|"aar",
  relevance:"relevant"|"unknown",freshness:"current"|"stale"|"unknown",
  trust:"untrusted-record",revision:SHA256,occurrences:int,provenance:
  {ref:string|null,commit:OID,path,blob:OID}|null,body:string|null,
  body_bytes:int|null,reason:Reason}`.
  Provenance is the first sorted occurrence (ref null sorts first, then
  commit/path/blob); occurrences is the total, no loss of identity in the
  fingerprint. Missing-bound-record uses its binding revision/key, zero
  occurrences, null provenance/body/length. Unknown relevance also suppresses
  provenance/body/length. Lists/start never carry body.
- `Selection = {selection:"none"|"one"|"multiple"|"unknown",
  selected_key:string|null,current:int|null,stale:int|null,
  unknown:int|null,complete:bool}`. Counts cover handoffs only and are null
  when any enabled scan/metadata failure prevents a complete classification.
  With complete true all counts are measured, unknown is zero.
- `Action = {name,owner,entrypoint:string|null,implementation_present:bool|null,
  available:bool|null,installed:null,activated:null,probed:null,reason:Reason}`.
- `Page = {offset:int,count:int,total:int,more:bool,next_cursor:string|null}`.

Ownership precedence: founding docs and owning contracts govern; instrument
registries identify entrypoints and conformance only. This index is a routing
projection, not a new authority. home-map and AAR reports are evidence.
A routing disagreement with an owning contract must be corrected by review
at that governing home before regenerating the index; runtime does not parse
prose to decide authority. A missing/unreadable governing document gives
ownership unresolved and entrypoint null; otherwise this index declares
ownership declared. document_present checks the governing
contract blob (directories count only if the row explicitly names a directory).
implementation_present checks only the executable target, never a contract.
For document-only concepts it is null; for declared unbuilt instruments false.
A missing executable is false; a failed check is null.
locked is membership in readable composer.lock for an exact named Composer
package, false on measured absence, null for malformed/unavailable lock or
non-package intended values. installed/activated/probed are always null here:
neither a lock entry nor an executable blob proves installation/live readiness.
Only the intended value exactly equal to symfony/workflow names a Composer
package in this index, describing prod's workflow genus; prose/local
package paths do not trigger inferred package lookups.

## Queries, pages and resources

Closed arguments; every new query requires `profile:ID`, optional
`snapshot:SHA256`. Additional keys:

| query | optional arguments | exact Data on success |
|---|---|---|
| lane_start | none | `{law:[Law],state_sources:[StateSummary],homes:[HomeSummary],work:[Work],handoffs:Selection,actions:[Action],omissions:[string]}` |
| lane_homes | concept, cursor | `{homes:[Home],home:Home\|null,page:Page\|null}` |
| lane_handoffs | key, cursor | `{candidates:[Candidate],candidate:Candidate\|null,handoffs:Selection,page:Page\|null}` |
| lane_actions | name | `{actions:[Action],action:Action\|null}` |

Concept/key/name plus cursor is refused arguments. Key grammar is
`^record/[0-9a-f]{64}$`; name uses ID grammar. Without a name, detail lists
are in configured home order, lexical candidate key order, or action index
order. Named requests have [] list and page null, including misses. A known
concept/key outside the profile is indistinguishable from a named miss.
Named handoff lookup returns that card whether or not it is selected; it never
turns a multiple/unknown selection into one.

Cursor grammar is `<snapshot>:<offset>`, offset a canonical decimal integer
1..255 (no leading zeros), snapshot 64 hex. Page one has offset 0.
cursor binds the profile snapshot and query/list implicitly through a required
matching `snapshot` argument plus query-specific offset bounds; it grants no
access and may be reused as an offset on another list within the same profile
snapshot. Offset must be below total; no cursor for empty lists.
Malformed snapshot/cursor, mismatch or out-of-range offset refuses cursor.
Pagination does not mean incomplete acquisition: enumerate the bounded set
before computing selection, then page presentation.

List pages greedily append whole cards, at most 16 and at most 16384 encoded
envelope bytes including final page metadata. Empty measured lists have
`{offset:0,count:0,total:0,more:false,next_cursor:null}`.
When items remain, at least one must fit; otherwise item-exceeds-cap, data null.
A frame that cannot fit returns page-frame-exceeds-cap. More implies next
cursor at offset+count, else null. Named cards bypass the 16-item limit but
obey the response cap. No card is silently skipped/reduced.
The assembled candidate set, including missing-bound-record cards, is also
limited to 256: detect a 257th card and return query-wide unavailable with
record-overflow and data null. Named lookup does not bypass acquisition
overflow. The 16-card limit is presentation only and is bypassed by a name.

Startup cap is 8192 encoded bytes. It carries all five law rows, all five
state rows, all configured startup_homes (at most three), all four actions,
and Selection. Work is the first eight eligible/unknown cards; omitted count
is reported. If needed drop work only (all of it); never drop required owners,
state, actions or selection. Oversized mandatory frame is unavailable with
page-frame-exceeds-cap. Profile/anchor limits and compact summaries permit
the shipped defaults; acceptance measures bytes. Full homes are targeted detail.
All other responses cap at 16384. Body only on named handoff, valid UTF-8,
≤2048 bytes; larger body becomes null with length and body-exceeds-cap;
invalid UTF-8 is malformed, no body. Count lengths before JSON escaping.

Startup omissions always contain, in this order: `no host activation`,
`no live readiness`, `no role enforcement`, `no lifecycle publication`,
`no raw documentation dump`, `HEAD tree only; dirty and untracked files excluded`,
`register ledger prs local readings unavailable`.
Append `retained source not searched` when disabled for this profile.
Append `work omitted: N` when cards exceed eight or work is dropped for fit.
No source prose in omissions.

CLI remains `python3 -B ops/conductor/tools/lane_mcp.py --config FILE query TOOL [JSON]`.
Tools and resources project the SAME envelope; _meta remains transport-only
and ignored as in v2. Resource list reads config only, adds one each of
`lane://start/PROFILE`, `lane://homes/PROFILE`,
`lane://handoffs/PROFILE`, `lane://actions/PROFILE` per profile.
Three added templates are `lane://homes/{profile}/{concept}`,
`lane://handoffs/{profile}/record/{digest}`,
`lane://actions/{profile}/{name}`; the v2 job template remains.
Resource first pages omit snapshot/cursor. Continuation is tool-only.
URI segments have the corresponding argument grammars, no decoding into paths;
unknown/malformed resource URIs retain -32602. v1 template handling stays -32601.

## Refusals and exits

Validation order: config; argument object/required keys/types/grammars;
configured profile; cursor grammar and required matching snapshot; acquisition;
snapshot equality; offset bounds; render. Unknown tool under v1/v2 remains
arguments. Refusals are one stderr line and exit 2 with empty stdout; MCP
isError=true carries the same line. Templates (all substitutions bounded,
validated values only; arbitrary malformed input rendered as `invalid`):

| class | exact line template |
|---|---|
| config | `config: expected valid versioned configuration; found invalid; needed supply the declared keys and bindings` (v3 only; v1/v2 keep their existing lines) |
| arguments | `arguments: expected closed arguments for QUERY; found invalid; needed use the declared query schema` |
| profile | `profile: expected configured profile; found ID; needed use a profile from configuration` |
| cursor | `cursor: expected current snapshot and valid page offset; found invalid; needed restart from lane_start` (grammar/offset) |
| cursor | `cursor: expected snapshot CURRENT; found GIVEN; needed restart from lane_start` (mismatch) |

Exit 0 includes unavailable/unknown-source readings; exit 1 unused.
Exit 3 only outer wall/kill, not source timeout (a reading).
No identity refusal. Refusal examples and exact successful envelopes are in
[discovery examples](discovery-examples.md); the document is non-executable.

## Action index

| name | owner | entrypoint | availability derivation |
|---|---|---|---|
| onboard | ops/conductor/onboard-lever.md | ops/conductor/tools/onboard.py | implementation_present and available equal the verified executable-blob presence; missing reason missing, failed check reason unreadable |
| handoff | ops/conductor/handoff/README.md | null | false; disabled |
| aar | ops/conductor/handoff/README.md | null | false; disabled |
| closeout | docs/workflow.md | null | false; disabled |

Here available means a documented implementation entrypoint exists, not an
installed callable handle or permission to act. All installation/activation/
probe fields remain null. Owner-initiated handoff/AAR/combined writes are
step 4; exit, crash and compaction create no completed records.

## Concept index

Routing metadata amended by commit against the existing governing homes.
There is no profile column: profile config chooses membership and priorities.
Paths are repo-relative. The implementation column is an executable target,
`unbuilt`, or `none` for document-only concepts. Intended names are direction.

Framework intentions describe prod application concepts only. Existing dev
tools keep their own service owners; a null intended value gives no replacement
target. `wf-runtime` denotes the unbuilt generic dev-lane runtime, not a future
Symfony implementation. The workflow-genus contract can also describe prod's
Symfony Workflow use without choosing the dev runtime's technology.

| concept | home | contract | entrypoint | registry | implementation | intended |
|---|---|---|---|---|---|---|
| `wire` | `docs/wire.md` | `docs/wire.md` | null | null | `unbuilt` | `packages/wire` |
| `workflow-genus` | `docs/workflow.md` | `docs/workflow.md` | null | null | `none` | `symfony/workflow` |
| `wf-runtime` | `docs/workflow.md` | `docs/workflow.md` | null | null | `unbuilt` | null |
| `probes` | `docs/probes.md` | `ops/conductor/probes-lever.md` | null | null | `unbuilt` | null |
| `concerns` | `docs/concerns.md` | `docs/concerns.md` | null | null | `none` | null |
| `verified-couplings` | `docs/verified-couplings.md` | `docs/verified-couplings.md` | null | null | `none` | null |
| `mapping` | `docs/mapping.md` | `docs/mapping.md` | null | null | `none` | `four projections` |
| `onboard` | `ops/conductor/onboard-lever.md` | `ops/conductor/onboard-lever.md` | `ops/conductor/tools/onboard.py` | `ops/conductor/registry/onboard.py.json` | `ops/conductor/tools/onboard.py` | null |
| `lane-mcp` | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/tools/lane_mcp.py` | null | `ops/conductor/tools/lane_mcp.py` | null |
| `lane-read` | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/lane-mcp-lever.md` | `ops/conductor/tools/lane_read.py` | null | `ops/conductor/tools/lane_read.py` | null |
| `dispatch` | `ops/devlane/dispatch/CONTRACT.md` | `ops/devlane/dispatch/CONTRACT.md` | `ops/devlane/dispatch/launch.py` | `ops/devlane/task/jobs.json` | `ops/devlane/dispatch/launch.py` | null |
| `harness` | `ops/devlane/harness/` | `ops/devlane/harness/context.cue` | null | null | `none` | null |
| `jobs` | `ops/devlane/task/jobs.json` | `ops/devlane/task/CONTRACT.md` | null | `ops/devlane/task/jobs.json` | `none` | null |
| `handoff` | `ops/conductor/handoff/README.md` | `ops/conductor/handoff/README.md` | null | null | `unbuilt` | null |
| `aar` | `ops/conductor/handoff/README.md` | `ops/conductor/handoff/README.md` | null | null | `unbuilt` | null |
| `decisions` | `ops/conductor/decisions-register.md` | `ops/conductor/decisions-register.md` | `ops/conductor/tools/decisions.py` | `ops/conductor/registry/decisions.py.json` | `ops/conductor/tools/decisions.py` | null |
| `ledger` | `ops/conductor/handwork-ledger.md` | `ops/conductor/handwork-ledger.md` | `ops/conductor/tools/hand.py` | `ops/conductor/registry/hand.py.json` | `ops/conductor/tools/hand.py` | null |
| `watch` | `ops/conductor/watch-lever.md` | `ops/conductor/watch-lever.md` | `ops/conductor/tools/watch.py` | `ops/conductor/registry/watch.py.json` | `ops/conductor/tools/watch.py` | null |
| `land` | `ops/conductor/land-lever.md` | `ops/conductor/land-lever.md` | `ops/conductor/tools/land.py` | `ops/conductor/registry/land.py.json` | `ops/conductor/tools/land.py` | null |
| `ci-store` | `ops/conductor/ci-store.md` | `ops/conductor/ci-store.md` | `ops/conductor/tools/ci.py` | `ops/conductor/registry/ci.py.json` | `ops/conductor/tools/ci.py` | null |
| `branches` | `ops/conductor/branch-census.md` | `ops/conductor/branch-census.md` | `ops/conductor/tools/branches.py` | `ops/conductor/registry/branches.py.json` | `ops/conductor/tools/branches.py` | null |
| `skills` | `.claude/skills/skills/SKILL.md` | `.claude/skills/skills/SKILL.md` | `ops/conductor/tools/skills.py` | null | `ops/conductor/tools/skills.py` | null |
| `permission` | `ops/conductor/permission-surface.md` | `ops/conductor/permission-surface.md` | `ops/conductor/tools/co_doc.py` | null | `ops/conductor/tools/co_doc.py` | null |
| `monitor` | `ops/conductor/monitor-lever.md` | `ops/conductor/monitor-lever.md` | `ops/conductor/tools/monitor.py` | `ops/conductor/registry/monitor.py.json` | `ops/conductor/tools/monitor.py` | null |
| `watchdog` | `ops/conductor/watchdog-lever.md` | `ops/conductor/watchdog-lever.md` | `ops/conductor/tools/watchdog.py` | `ops/conductor/registry/watchdog.py.json` | `ops/conductor/tools/watchdog.py` | null |
| `ladder` | `ops/conductor/ladder-lever.md` | `ops/conductor/ladder-lever.md` | `ops/conductor/tools/ladder.py` | `ops/conductor/registry/ladder.py.json` | `ops/conductor/tools/ladder.py` | null |
| `onboard-discovery` | `ops/conductor/discovery-lever.md` | `ops/conductor/discovery-lever.md` | null | null | `unbuilt` | null |
| `conduct` | `ops/conductor/conductor-start-plan.md` | `ops/conductor/conductor-start-plan.md` | null | null | `unbuilt` | null |
| `packages` | `packages/README.md` | `packages/README.md` | null | null | `none` | `bundle gestation` |
| `projections` | `AGENTS.md` | `AGENTS.md` | null | null | `none` | `CLI, TUI, MCP, API` |

## Smallest extensions and measured boundary

The [handoff custody note](handoff/README.md#discovery-metadata-extension)
owns trusted record-binding semantics. Bindings in launch configuration are
a temporary read input, not a new register: future publication must supply
them through the existing record lineage. No old record is rewritten or
assumed to carry that metadata. Work bindings belong to the existing
task/dispatch context. Extending owner schemas and independently verifying
their custody precedes automated production of these bindings.

Step 2 registers the v3 conformance row with a hermetic config refusal and
adds the discovery/sequence paths to onboard's law table and implementation
together. Today's onboard table and CLI remain unchanged. Step 3 extends
[harness capabilities](harness-capabilities.md) and
[permission surface](permission-surface.md) for measured capabilities,
selection constraints and conductor policy; it does not give discovery
permission to probe or enforce. Worker source grants are the separate
task/harness follow-up, not a role switch on these queries.

Historical draft measurement (not reissued as current): 2026-09-06T01:15:46Z against
`3682a8c58e304e7025036f1b3ec4edb63424832e`: parsed composer.json/lock,
enumerated packages, checked vendor and proposed instrument paths, and parsed
lane_read's AST. Relevant locked/resolved versions are in the
[plan](conductor-start-plan.md#symfony-mapping-remeasured).
vendor, lane_refs.py, wf.py and probes.py were absent; packages contained
README.md only; lane_read had zero subprocess mentions. No installed runtime,
Git namespace contents, package release freshness or host activation was
measured. [docs/mapping.md](../../docs/mapping.md) describes prod's Symfony
ownership only; its dev-tool replacement doctrine is superseded. Current
recovery evidence is in the reconciliation note, separately from these prior
readings. No package/dependency change here.

## Non-executable acceptance rows

These are the specification for independently authored step-2 tests, not
tests executed or approved by this correction's author. Plant synthetic
trees/configs/adapter readings; never use live stores, credentials or captured
AAR bodies as oracles. Compare canonical bytes across CLI/tool/resource.
A counterparty change re-demands its coupled rows.

| id | planted case | required observation |
|---|---|---|
| D-A1 | v1 check and a discovery query | tools 4; discovery arguments refusal; all v1 bytes preserved |
| D-A2 | v2 check, tools, resources, _meta and brief | tools 7; existing bytes and limitations unchanged |
| D-A3 | valid v3 including null optional sources | tools 11, no source access during check |
| D-A4 | extra/missing keys, bool counts, invalid paths, conflicting metadata/cycle | config wire, no acquisition |
| D-A5 | missing profile, unknown field, role/path/command argument | arguments; no acquisition |
| D-A6 | valid unknown profile | profile wire; no acquisition |
| D-A7 | shipped dev, all fixed docs readable, bounded normal records | startup ≤8192; lane-mcp, dispatch, onboard present; catalogue fully pageable |
| D-A8 | shipped prod, same fixture | startup ≤8192; mapping, packages, projections present; lock absence distinct from installation |
| D-A9 | added docs profile from config example | wire startup; wire/onboard catalogue; docs-root relevance, no new branch in code |
| D-A10 | catalogue >16 within 64 limit | bounded pages reach every home once; named card works independently |
| D-A11 | complete empty HEAD + enabled empty retained namespace | complete true, none, counts zero; not unavailable |
| D-A12 | one relevant bound handoff exists only at unknown retained filename | enumerated, one selected key; named body without caller path |
| D-A13 | two current relevant handoffs; or two revisions of one ID | multiple, no selected key; no timestamp/path tie-break |
| D-A14 | identical HEAD/ref bytes and two distinct blobs in one ref | one key per digest, all occurrences bound; no stem collisions |
| D-A15 | trusted same-lineage supersedes pair | old stale, new current; AAR never selected as handoff |
| D-A16 | bound stale-only handoffs | none plus visible stale cards |
| D-A17 | unbound old record, unreadable candidate or missing bound record beside one good candidate | unknown, null selected_key/counts, complete false; missing evidence visible |
| D-A18 | dev-only, prod-only and mixed-root bindings | root+lineage filtering; explicit common lineage required; no cross-profile body leak |
| D-A19 | missing work binding | unknown work relevance, no inferred profile from title/ref |
| D-A20 | register/ledger/PR sources unsupported | exact unavailable summaries; no subprocess, DB, gh, home/env fallback |
| D-A21 | zero authorized dispatch IDs; then malformed authorized record | zero scoped counts; then unavailable count, no live-process claim |
| D-A22 | named misses for all three detail queries | exact envelope, null item, fixed unknown-* reason |
| D-A23 | detail with profile and snapshot from start | same source closure and snapshot including actions |
| D-A24 | retained ref moves to new commit with identical blob bytes | snapshot changes; old continuation refuses cursor |
| D-A25 | content, profile roots, binding/supersedes, adapter or source failure changes | snapshot changes; old continuation refuses |
| D-A26 | malformed, wrong-profile or out-of-bounds cursor | cursor wire; no silent restart or skip |
| D-A27 | 65 refs, 257 occurrences, 4097 scanned tree entries, byte/op/time budget | declared overflow, incomplete or unavailable; never unique partial selection |
| D-A28 | namespace unreadable vs empty vs disabled | unavailable/ok/disabled distinguished; disabled omission gives declared scope |
| D-A29 | anchor symlink/ancestor swap, FIFO, malicious .git/commondir/alternates, ambient CWD/GIT_DIR | unsafe/repository failure, no escape/fallback/read effects |
| D-A30 | missing or wrong-type objects, symlink blob, unknown caller OID/path | adapter rejects; only verified operation outputs can become inputs |
| D-A31 | ref/file changes during acquisition | unavailable changed-during-read, snapshot/data null, no retries |
| D-A32 | hostile body including renderer end marker and directives | untrusted-record label, safe data delimiters, corroboration rule; JSON escaping alone insufficient |
| D-A33 | governing document exists but implementation absent | document_present true; implementation_present false; no invented entrypoint |
| D-A34 | Composer package locked, vendor absent | locked true; installed/activated/probed null; AAR contract is custody README |
| D-A35 | onboard executable exists; lifecycle actions absent | onboard available means presence only; other actions false/disabled |
| D-A36 | 2049-byte body or Unicode encoding expansion, oversized frame/item | body null with count/reason or exact unavailable; no truncation or empty non-advancing page |
| D-A37 | 17 candidates within complete scan | page size ≤16; global selection unchanged; named lookup works |
| D-A38 | oversized optional work, mandatory startup owners | work omission only; owners retained or explicit frame failure |
| D-A39 | stationary sources and resource first pages | byte-identical CLI/tool/resource envelopes, no per-call timestamps |
| D-A40 | read without WF_AGENT, tools/list | success; readOnlyHint true, destructiveHint false |
| D-A41 | before/after filesystem, DB, refs/index/config/object tree; import graph | unchanged; no writer imports; read core still no subprocess |
| D-A42 | conductor vs worker launch fixture, same harness/profile | worker cannot obtain conductor catalogue; role arg rejected; separate follow-up, no claim of other-tool enforcement |
| D-A43 | independently started conductor, dev/prod/extra profiles, no path hints | startup then targeted detail identifies owners, tools and relevant handoff or exact uncertainty |
| D-A44 | v3 old seven queries on unchanged v2 inputs | byte-identical; no broader cleanup |
| D-A45 | known irrelevant key requested by another profile | same unknown-key envelope as nonexistent key; no prose/provenance leakage |
| D-A46 | same failed source twice, then recovery | deterministic failure fingerprint; recovery changes snapshot |

No source, settings, dependencies, database/host changes, executable tests,
active config example, registry entry or PR is part of this revision.
Step 2 must prove these promises before any implementation is called usable.
