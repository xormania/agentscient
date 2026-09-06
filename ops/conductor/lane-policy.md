# Lane policy — first contract and inert data

Standing: proposed, not activated. This contract and
[`ops/lane-policy.json`](../lane-policy.json) prescribe future behavior; they
install no evaluator, sandbox, settings, hook or acceptance gate. The owner
authorized this contract/data slice after planning, with independent review,
independently authored tests, and implementation still to follow.

Authority: [the owning lane boundary](../../AGENTS.md#lane-boundary-and-precedence),
the [owner history](../../.dev/ladder-inputs/lane-boundary-owner.md), and the
[contract assignment](../../.dev/ladder-inputs/lane-policy-contract-owner.md).
This adopts Grok ruling `20260906T021124Z-adjudicate-grok-8ce9f8`, including
its seven dispositions, as clarified by the contract assignment's P2.
The supplied ruling is evidence, not an executable authority source.
The bounded correction adopts Grok ruling `20260906T023832Z-adjudicate-grok-8cdf11`
and the [correction assignment](../../.dev/ladder-inputs/lane-policy-correction-owner.md).
The [final ruling](../../.dev/ladder-inputs/lane-policy-final-ruling.md) accepts
the three remaining findings from Claude `20260906T025705Z-review-claude-104942`.
It records `D-LANES-1` as the permanent lane boundary's semantic owner evidence
in the conductor decisions register, with a scope-reference note on `D-SYM-1`;
neither is admission of this policy blob, a maintenance grant or runtime activation.

## Ownership and positive scope

Dev tooling is permanent, independent machinery. It must start and operate
without the application's kernel, container, services, or `vendor/`; product
delivery neither replaces nor retires it. Product work retains the application's
Symfony rules. Harness, model, job role, conductor/worker role and work profile
are separate dimensions. `record.lane` and `WF_LANE` remain infrastructure
markers and cannot select work permissions.

The example's mapping keys are configuration, never consumer branches:

| profile | permitted repository writes, before other restrictions |
|:--|:--|
| `dev` | `ops/`, excluding every protected path even with a maintenance record (`authority_maintenance: false`) |
| `prod` | `src/`, `packages/`, `config/`, `public/`, `templates/`, `assets/`, `migrations/`, `tests/`, `bin/`, `translations/`, `composer.json`, `composer.lock`, `symfony.lock`, `phpunit.dist.xml`, `.env`, `.env.dev`, `.env.test` |
| `authority-maintenance` | `ops/`, `docs/`, root/scoped instructions and the explicitly listed shared configuration paths; protected edits additionally require a trusted maintenance authorization |

Thus tooling changes pass in `dev`; application and Composer changes pass in
`prod` and refuse in `dev`; `prod` cannot write `ops/`. Shared-policy maintenance
is an explicit third case, not a union of product and tooling privileges.
Ordinary unprotected tooling maintenance needs no special authority decision.
Profile membership grants no host, network, database or dependency-installation
permission: those capabilities still require launch/task authorization.

Both lanes may read shared contracts and inspect or describe application source,
including Symfony names. Reads remain subject to custody/withholding; this policy
does not reveal withheld paths or credentials. Inspection reads are not runtime
dependencies. Unavailable application observations are reported as unavailable,
while the dev tool itself remains operable. No word ban or prose classifier can
prove architectural independence. Already corrected authority documents and
historical migration, stack, census, idea, AAR, handoff and planning records keep
their bytes and provenance; superseded replacement recommendations never regain
authority through an input, prompt or resumed job.

## Data shape and path rules

The UTF-8 JSON object has exactly `schema`, `standing`, `shared_read_roots`,
`protected_authority_paths`, `profiles`, and optional `default_profile`.
`schema` is `agentscient.lane-policy/v1`; the only allowed `standing` value is
`proposal` (descriptive, never an activation switch). Any other value refuses
`lane-policy`. `profiles` is a nonempty mapping of nonempty ids
matching `[a-z][a-z0-9-]*`. Each value has exactly `write_roots`,
`forbidden_dependency_roots`, `authority_maintenance` (boolean), and
`allow_declared_outputs` (boolean). Root lists contain unique strings; empty
lists explicitly grant nothing or forbid nothing, respectively. Duplicate JSON
keys, unknown keys, wrong types or malformed paths refuse `lane-policy`.
An optional default must be a nonempty existing profile id; this example omits it.

`agentscient.lane-policy/v1` is a fixed policy protocol identity. Following
[lane-mcp-lever.md's exact declaration precedent](lane-mcp-lever.md#coupling-proof-and-installation)
for `agentscient.lane/v1` and `agentscient-lane`, the lane literal guard may
permit, for the `agentscient` token only, the exact stripped line
`POLICY_SCHEMA = "agentscient.lane-policy/v1"` at `ops/devlane/dispatch/record.py`.
Existing outer-whitespace normalization remains. Every other line, path and
token retains detection, including another configured token matching inside
that declaration; the two existing MCP declarations remain allowed. Changed
constant names or values and appended comments or statements are not allowed.
No directory-level exemption or protocol encoding is permitted. Record
validation and its exact schema error text remain unchanged when comparison
and diagnostic use that named constant. Structural binding semantics, policy
data and proposed standing remain unchanged; this declaration neither admits
nor activates policy. Independent guard tests and review follow.

`shared_read_roots` adds shared-document reads to each profile's permitted reads;
it never narrows other profile or inspection reads. In particular the application
inspection grant above permits `src/` and `packages/` even though this list omits
them. All reads still intersect custody/withholding restrictions.

The protected set includes every exclusive dispatch lever and suite/conformance
gate entrypoint named here as exact paths: `ops/bin/dispatch.sh`, its body
`ops/conductor/tools/dispatch.sh`, `ops/bin/go.sh`, `ops/bin/ladder.sh`,
`ops/bin/suites.sh` and `ops/conductor/tools/laneconf.py`. The ladder shim's
`ops/conductor/tools/ladder.py` body remains protected too. Do not replace these
with `ops/bin/` or `ops/devlane/hooks/` prefixes that swallow ordinary tooling.
The register reader and seed are not gate entrypoints; their trusted use is
bound separately below. Unprotected tooling writes require no maintenance grant.

Paths are case-sensitive repository-relative POSIX strings. A trailing `/`
means that directory and descendants; otherwise the match is exact. There are
no globs, absolute paths, empty components, `.`/`..`, backslashes or NULs.
Reject path escapes and symlink traversal beyond the admitted root; check both
lexical and resolved targets, including symlink changes and both rename/copy
endpoints. An unresolvable or unrepresentable path refuses, never disappears.
The Git administrative directory and host paths are never repository grants.
The job's separate `out/` is a launch-owned namespace, not repository `out/` or
a policy path; its isolation and canonical location are launch/task obligations.

## Trusted authority, selection and maintenance

Only the fixed tracked path `ops/lane-policy.json` in the trusted invoking
repository is admissible. The owner admits a full Git commit id and SHA-256 of
that blob's exact bytes through the existing [decisions register](decisions-register.md).
Its host store is `Path.home()/.local/state/<LANE_NAME>/decisions.db`, with the
owner's host HOME, never the worker's isolated HOME. `handwork.db` is a different
grant; `decisions.seed.json` is a birth export, not the live admission store.
Naming this register does not ratify its currently proposed process standing.
The trusted caller supplies the admission decision id from owner custody;
reachability, a worker-created commit, or a matching digest alone is insufficient.
Resolve the canonical repository from trusted invocation, not the worker's cwd
or an environment variable. Read the blob at the admitted commit and verify its
digest; do not read the candidate worktree as authority. Missing/unreadable
admission, mismatched bytes, wrong path or unsupported shape refuses `lane-policy`.

### Reader custody and exact register evidence

Read using the existing `python3 ops/conductor/tools/decisions.py show <id>`
interface. The admitted consumer invokes an independently admitted, immutable
reader checkout, never the current mutable worktree script. Its full Git revision
pins `decisions.py`, its imported `laneconf.py`, `ops/lane.conf` and all repository
imports. Verify these against Git blobs before executing; no candidate files,
bytecode caches, local config or fallback imports may enter this closure.
Use the admitted absolute Python executable and runtime closure, no worker PATH,
PYTHONPATH, startup/site customization or environment overlays. The reader runs
with host HOME supplied by trusted custody; `LANE_CONF`, `LANE_NAME` and all
laneconf environment overrides are absent, and `ops/lane.local.conf` must be
absent in that checkout. Derive the store lane only from its pinned `ops/lane.conf`.
These are caller obligations, not new decisions flags or host settings.

The bootstrap custody anchor binds the owner principal, canonical host HOME and
repository, current admission id, consumer revision and reader tuple
`{"ref": <full Git id>, "runtime_sha256": <digest>}`. The runtime digest hashes
a retained canonical JSON object mapping absolute resolved runtime file paths
to SHA-256 byte digests, sorted keys, UTF-8, no insignificant whitespace. Include
the Python executable, imported standard-library files and loaded native
libraries; independent closure verification must account for all execution
inputs. Verify the retained manifest and files before each read; unavailable
closure evidence refuses `lane-policy`. The reader tuple in admission evidence
must equal this previously trusted tuple; it cannot establish trust in itself.
An owner-admitted replacement is checked by the old consumer/reader before
cutover. Candidate reader, configuration or seed edits may be proposed under
old grants but cannot replace any trusted input or promote themselves at acceptance.
Host custody of the anchor, runtime and live store is an explicit assumption,
not proof of same-UID OS isolation.

`show` returns JSON with exactly `decision` (the existing full row) and `events`
(its ordered history). Require exit 0, empty stderr and strict JSON. A bound
record's digest is SHA-256 of the **exact stdout bytes, including the final
newline and events**, not reserialized JSON or just the evidence field. Re-read
live at every acceptance transition; an event note changes this digest too.
An unchanged authorization can bind a fresh dispatch without a new owner act;
an old dispatch's changed digest cannot be silently refreshed.

For admission and maintenance rows require the requested `id` (register pattern
`^D-[A-Z0-9]+-[0-9]+$`), `home: "ops/lane-policy.json"`, `standing: "ratified"`,
`superseded_by: null`, and `decided_by` equal to the custody anchor's owner
principal. `recorded_by` names the recorder, who may be a conductor; it is not
the deciding principal. Require a nonempty `decided_at` and a matching `ratified`
event (decision id, timestamp, agent = recorded_by, detail = evidence); conflicting
deciding events refuse. A `supersedes` predecessor is allowed only if its live
row is superseded by this id. No candidate or seed row supplies this evidence.

The existing text `evidence` has the exact form `<principal>: <JSON object>`:
the prefix equals `decided_by`, contains no colon or newline, and is followed
by one colon and one space. This respects the existing tool's principal parser.
The remaining bytes parse as one strict JSON object; no prose/hash searching.
All payloads have exactly the common keys `kind`, `policy`, `owner_words` plus
the kind-specific keys below. `policy` has exactly `ref` (full lowercase Git id
for the repository's object format) and `sha256` (64 lowercase hex characters).
They must equal the current admitted policy. `owner_words` is a nonempty verbatim
owner instruction; its authenticity and meaning require trusted recording and
independent review, not a machine claim that arbitrary words grant authority.

| kind | additional evidence keys and checks |
|:--|:--|
| `lane-policy-admission/v1` | `reader` is the tuple above; `standing_grants` is a sorted unique array of existing decision ids, explicitly empty if none. This is the complete standing-grant set for this admission. |
| `lane-policy-standing/v1` | `paths` is a nonempty sorted unique array using the policy's exact/prefix path rules; `purpose` is nonempty text. No job or lineage keys. |
| `lane-policy-job/v1` | `paths` is a nonempty sorted unique array of exact paths (no trailing `/`); `purpose` is nonempty text; `job` equals the dispatch's job name; `dispatch` equals its unique record id; `lineage` has exactly `branch` and `base_sha`, equal to the dispatch lineage. |

These are payload encodings in the existing evidence string, not new register
columns, schema, verbs or flags. Unknown/missing keys, duplicate JSON keys,
non-finite numbers, wrong types, mismatched ref/digest/principal/reader, missing
rows, unreadable output or conflicting evidence refuse `lane-policy`.
Revocation uses the existing supersede transition; there is no invented revoke
verb or status. Proposed, rejected or superseded rows cannot authorize. Notes
neither add nor remove a grant, but change the exact `show` output digest:
existing bindings refuse at the next acceptance transition (`lane-policy`, or
`lane-resume` on write-resume). A fresh dispatch may bind the same unchanged
authority's new digest without a new owner decision; never silently rewrite an
existing bound record. Do not chase a successor as an automatic grant;
the trusted admission must explicitly name the current standing-grant set.
Read and validate every listed standing row before calculating coverage; a
missing or invalid row is not an empty set that licenses a per-job fallback.

Changing the complete standing-grant set requires a fresh ratified admission
listing the replacement set and an update to the custody anchor's current
admission id. Verify both the replacement admission and anchor update using the
previously trusted consumer, reader and authority before cutover; candidate
evidence cannot validate its own replacement. A superseded listed grant refuses
`lane-policy` for protected maintenance until a valid replacement admission and
anchor are in place. Rotation applies to fresh dispatches and never rewrites old
bindings. Dispatching another job already covered by unchanged standing grants
does not rotate the set or require a new owner act.

### Selection and maintenance grants

No `laneconf.get`, `LANE_CONF`, `LANE_POLICY_PATH`, `lane.local.conf`, environment
overlay, scope text or input file can move that authority or select a profile.
Do not add a lane.conf key. The trusted caller's explicit profile selection and
any structured launch/task profile declaration must agree exactly if both are
present. With one, use that one; with neither, use only an explicitly configured
default. Empty, unknown, malformed or conflicting selection refuses `lane-profile`
before a child starts. Never fall back from an invalid explicit value to a default.
Unstructured contradictory prose has no selection effect and requires independent
contract review; a machine must not claim to classify intent from that prose.

Protected writes require both `authority_maintenance: true` and coverage by
verified maintenance evidence. False refuses every protected write (`lane-write`)
even with a valid record. True alone grants nothing. Grant paths must still fit
the admitted profile and every other effective grant term.

For each protected path, first use the union of standing grants named by the
admission. One ratified standing decision records an existing owner instruction
once and applies across jobs while that policy ref/digest and grant remain
current. Its job-specific receipt is derived by the conductor; recording and
applying it is not a fresh owner act. Do not require job/lineage in that standing
decision or ask the owner again for already covered work. The conductor may
record on behalf of the owner only with the owner's actual words attached;
neither this contract nor a recorder can fabricate an owner decision.

Only protected paths outside every standing grant need a per-job decision supplied
by the trusted caller, in the job form above. Its exact paths must be outside the
standing union and bound to that dispatch, job and lineage. Mixed work may use
both forms; an uncovered path with no per-job grant refuses `lane-write`.
Supplied but invalid evidence refuses `lane-policy`, never widens rights. Neither
the worker's scope nor its `Source:` trailer is authorization. Unprotected tooling
requires neither form. Future consumers derive receipts for existing grants;
this assignment creates no live rows or authorization.

Evaluate policy, instruction, job/adapter declaration and gate-source changes
under the *old admitted* policy, declarations and trusted evaluator. Candidate
bytes cannot authorize their own paths, select a new profile, enlarge grants or
replace the evaluator of their result. Independent review/tests must verify the
new boundary and active instruction composition before owner admission of a new
policy ref/digest. The admission applies to fresh launches; it never edits old
bindings. The maintenance profile keeps authorized policy repair possible without
giving ordinary product or tooling jobs all writes. A newly introduced active
instruction source must first be protected by an admitted policy; creating a
file under an ordinary write root cannot promote its instructions to authority.

## Effective grants and dependency evidence

Lane policy owns profile ceilings, dependency exclusions, authority protection,
binding and acceptance requirements. [Launch/task](../devlane/task/CONTRACT.md)
owns job outputs, requested write scope, role limits and adapter capabilities.
Policy consumes those declarations, including outputs **if present**, without a
second job registry, adapter table or jobs schema. Implement the policy side
against contract-verified mock declarations; launch/task can develop its side
independently. Consumer readiness is required only at activation.

For repository paths, effective writes are the intersection of the admitted
profile roots, trusted requested scope, launch/task job grants, role grants and
adapter grants, minus protected paths unless the profile's maintenance boolean
is true and verified standing/per-job evidence covers the path.
For external job outputs, effective writes are declared output paths intersected
with requested scope, role grants and adapter grants, and are empty when the
profile's `allow_declared_outputs` is false. This boolean supplies no path itself.
Every absent grant term contributes the empty set; none means profile roots,
snapshot-wide writes or arbitrary scratch space. In particular, absent output
declarations add no `out/` permission. A job requiring an unavailable grant
refuses before launch (`lane-write`); a read job with no file output may still
return its envelope through stdout. Read roles have no repository writes and
must retain identical snapshot HEAD and no non-exempt residual paths; a declared
and isolatable external output does not relax snapshot immutability.

The caller supplies dependency evidence for runtime imports, autoloaders,
subprocess entrypoints and required services, with source path and resolved
target root, bound to the candidate tree. Check every declared/resolved edge
against `forbidden_dependency_roots`; an edge into a forbidden root refuses
`lane-dependency`. Declared app services resolve to their application source
roots, rather than becoming unclassified permission through a service name.
Evidence must explicitly distinguish measured empty edges from unavailable
analysis; unresolved edges or missing required evidence refuse acceptance.
Static path/entrypoint checks and tests with application/vendor unavailable can
verify concrete couplings. They cannot exhaust dynamic imports, shell-generated
commands or semantic dependencies. Independent review must check closure and
instruction composition under [verified couplings](../../docs/verified-couplings.md).
Literal citations of `vendor/autoload.php` are allowed; requiring that file or
executing application `bin/console` under `dev` is forbidden.

## Binding and acceptance

The proposed `brief.policy` value contains `schema` (as above), `path`
(`ops/lane-policy.json`), `ref` (full admitted Git id), `sha256` (blob bytes),
`admission` (`record`, `sha256`), `profile`, `template_sha256`,
`grants_sha256` and `maintenance` (null or an object with exactly `standing` and
`per_job`, each a list of `{"record": <decision id>, "sha256": <show digest>}`
sorted by unique record id). Null means no protected writes requested; otherwise
bind all admission-listed standing rows (even when none covers this job) and
the per-job rows used for uncovered paths. Empty lists grant nothing.
`admission.record` is the current admission decision id; `admission.sha256` and
every maintenance digest cover the exact trusted `show` stdout defined above.
Digests are 64 lowercase hex characters. The admission digest transitively binds
the reader tuple; retain its runtime manifest with the custody evidence.
`template_sha256` must equal the existing `brief.template.sha256`.
`grants_sha256` hashes the normalized consumed scope, job, role, adapter and output
grants plus maintenance paths: UTF-8 JSON, sorted object keys, sorted unique path
lists, no insignificant whitespace. It is a derived receipt, not a new source of
job declarations. Capture the declaration sources and their digests with the
receipt so the trusted caller can reproduce it. Bind it alongside the existing
job, role, harness, snapshot ref and lineage identity; do not repurpose `lane`.
Render the selected policy summary into the brief whose exact bytes are hashed.

The trusted consumer recomputes this binding from admitted sources before each
transition. Current admitted policy ref/digest, selected profile, template,
declaration sources and effective grants must remain stationary. A worker-supplied
binding or receipt cannot substitute for that comparison.

| transition | obligation before accepting or advancing |
|:--|:--|
| fresh launch | validate admission, selection, required grants and known dependency edges before minting an attempt or starting a child |
| settle/close, including write-resume settlement | validate binding and all committed delta plus residual artifacts before automatic commit or dispatch-ref publication; dependency evidence must match the candidate |
| write-resume | revalidate stationary binding and existing tree before clearing exit/trip markers, restoring stores, changing attempt count or starting a child; re-run full settlement afterward |
| collect | reject unbound/mismatched work before verification; recheck after verification (it may write), before commit/ref/collected-marker mutation; successful verification alone grants nothing |
| land and ladder stage acceptance | independently revalidate admitted policy, binding and artifact evidence against the exact fetched/result head and lineage before cherry-pick or stage advance; missing evidence is non-acceptance, including collected results |

Settlement consumes `launch.py`'s existing `_residual_entries`, including its
`git ls-files --others --ignored --exclude-standard -z` measurement. `git status
-uall` alone does not see ignored files. Preserve NUL-delimited path authority,
binary changes, deletions and both rename/copy endpoints. Check committed changes
from snapshot ref to result head as well as residuals. Retain only the already
enumerated cache-shape exemptions in the [dispatch contract](../devlane/dispatch/CONTRACT.md#collect);
unknown cache layouts and source files in cache-named directories remain checked.
These exemptions do not bless cache contents as trusted execution inputs.

Acceptance evidence is launcher-produced `result.policy`: the full `brief.policy`
binding, checked snapshot ref, result head, SHA-256 of the measured artifact
manifest and dependency evidence, check time and outcome (`pass` or `refused`,
with the refusal line). The manifest covers the checked paths, statuses, modes,
content digests and rename endpoints; the dependency evidence and manifest are
retained beside the record with byte digests, so consumers can rederive them.
An absent or stale receipt never means pass. Consumers verify provenance and
recompute from the bound tree; they do not trust a worker's manifest or verdict.
Failure preserves diagnostic artifacts and marks policy non-acceptance without
publishing an accepted ref. A worker's `status: ok`, `verdict: approve`, exit 0,
or `collect --verify` success cannot override this gate or the existing gates.

## Refusals and containment limits

The new classes use [the wire](../../docs/wire.md#the-refusal-wire): exit 2,
empty stdout, one stderr line per refusal, with nonempty expected/found/needed.
These classes are not overridable. Existing unrelated dispatch refusal exits
are outside this change. A late policy failure also records invalid/non-acceptance
on the durable result; it is not disguised as a pre-launch failure.

| class | condition |
|:--|:--|
| `lane-profile` | missing, empty, unknown or conflicting profile selection |
| `lane-policy` | invalid/untrusted/missing authority, binding or declarations |
| `lane-write` | requested or measured write outside effective grants, including unapproved protected edits |
| `lane-dependency` | forbidden runtime edge or unresolved required dependency evidence |
| `lane-artifact` | incomplete, unreadable or mismatched artifact/acceptance evidence |
| `lane-resume` | missing or changed binding on resume; refuse before attempt mutations |

Example: `lane-write: expected writes within prod grants; found ops/bin/example.sh; needed a fresh tooling dispatch with admitted scope`.
Within one check use authority, selection, grant, dependency, artifact order;
resume maps a missing/changed binding to `lane-resume` first. Name actual paths
and digests in diagnostics, not secrets. A forbidden operation is refused, not
converted to an owner-permission prompt.

Profile path limits are acceptance checks unless a measured adapter enforces
those exact roots before writes. The existing Codex sandbox label alone does
not prove profile-specific prevention. Claude/Grok policy containment must be
reported as detection at acceptance, not OS prevention. Same-UID host access,
transient writes erased before settlement and undeclared dynamic behavior are
not proven contained by an artifact diff. Trusted invocation/custody is an
assumption; hostile work requires the separate isolation boundary.

## Bootstrap and minimum complete activation

This proposal lands using the existing owner authorization and existing process;
it does not require a policy binding that no consumer yet creates. Its record
remains honestly unbound. Contract review, independent tests, implementation and
review of the activation candidate occur under that same explicit bootstrap
custody, without describing their old sessions/worktrees as enforced.

Before switching acceptance on, the owner admits the independently verified
policy blob, trusted consumer revision and reader/runtime custody anchor in a
durable decision identifying the bootstrap candidate, evidence and cutover.
Use the exact admission and standing evidence forms above; the initial reader
is verified under bootstrap custody before it reads that admission. Existing
owner instructions may be recorded once by the conductor with their actual words,
without a new decision on already authorized work. This is the initial trust anchor,
not an environment toggle, a worker bypass or an automatic admission of every
old result. Gate-source changes thereafter are evaluated by the previously
admitted consumer; candidate code cannot validate itself for landing.

The minimum complete activation is one coherent operational boundary: trusted
policy loading and selection, grant/dependency evaluation, `brief.policy` and
`result.policy` validation, pre-launch checks, settle/close, pre-write-resume and
post-resume settlement, collect before/after verification, and land/ladder
refuse-if-unbound. Needed launch/task grants must be available and verified for
each enabled job/adapter combination; absent declarations cannot be synthesized
from profile ceilings. Unsupported combinations refuse while supported ordinary
tooling maintenance remains usable. The evaluator is a stdlib library at future
`ops/conductor/tools/lane_policy.py`, no CLI or profile-id literals, and no
`instrument-conventions.md` docstring marker that would falsely register a CLI.

At cutover, old records keep their bytes and historical status. Reading them
remains legal. They cannot be resumed for writing, collected for acceptance,
landed or used to advance a ladder without policy evidence; do not backfill it.
To continue old work, create a fresh admitted dispatch and independent evaluation
of its proposed delta, retaining the old id as provenance. Old commits already
landed remain history, not retroactive proof of enforcement. Cutover must block
old callers from the acceptance route; partial consumer deployment cannot be
advertised as active. No Symfony runtime is a prerequisite for this process.

Instruction-digest pinning, hooks, doctor, MCP and richer jobs capability rows
may follow. Active instruction composition must already honor current owner
precedence; deferring digest machinery cannot restore replacement doctrine.
Existing suite/conformance gates remain mandatory for executable delivery.
There is no new executor, configuration registry or MCP action here.

## Independent acceptance cases

Future test ownership (none of these tests is authored in this slice): new
`ops/conductor/tests/test_lane_policy.py` for data/selection/grants/dependencies;
new `ops/devlane/dispatch/tests/test_launch_lane_policy.py` for launch/settle/resume;
extend `ops/devlane/dispatch/tests/test_record.py` and `test_launch_collect.py`
for records and recovery, `ops/conductor/tests/test_land_lever.py` and
`test_ladder_lever.py` for acceptance, and `test_onboard_lever.py` for instruction
composition. Use synthetic repositories and mock launch declarations, never
vendor sessions. Run `ops/bin/suites.sh`, including existing laneconf closure,
literal and instrument-conformance gates. Register any new CLI refusal surface
in the same change that introduces it; do not change laneconf's wire here.

| case | prescribed result (all unmentioned grant terms explicitly present) |
|:--|:--|
| P1 | `dev` writes `ops/bin/example.sh` and ordinary hook tooling without maintenance evidence, reads `docs/wire.md` and `src/Example.php` to describe Symfony: pass; repeat tooling with application/vendor absent and tool still operable |
| P2 | `prod` writes `src/Example.php` and `composer.json`: pass; same writes under `dev`: `lane-write`; `prod` writing `ops/bin/example.sh`: `lane-write` |
| P3 | add synthetic profile `fixture-only` with `write_roots: ["unittest/"]`, `forbidden_dependency_roots: ["vendor/"]`, both booleans false, under an admitted fixture policy: `unittest/example.txt` passes; `src/Example.php` and a valid present declared external `out/` write both refuse `lane-write`, consumers unchanged |
| P4 | synthetic host register `show` admission names a ratified standing grant for `ops/lane-policy.json` and `docs/`; `authority-maintenance` changes `ops/lane-policy.json`/`docs/wire.md`: pass under old grants on two distinct jobs with the same standing record and no fresh owner act; `ops/README.md` outside that grant refuses without a per-job row, passes with an exact matching job row; mixed covered/uncovered changes pass with both forms; identical edits with no grants refuse `lane-write` |
| P5 | candidate `decisions.py`/seed edits under ordinary `dev` grants may pass as artifacts; trusted reads still use the admitted reader and host store, never those candidate bytes |
| N1 | absent selection with this default-free policy, unknown/empty id, or flag/spec conflict: `lane-profile` before child/attempt creation; a valid configured default works only when selection is absent |
| N2 | environment, laneconf overrides, scope/input text and resume prompts cannot change policy location, digest or profile; candidate policy widening cannot permit its own product write |
| N3 | `dev` runtime dependency on `vendor/autoload.php`, app service or `bin/console`: `lane-dependency`; textual inspection alone passes; unresolved required edges refuse |
| N4 | committed, untracked and ignored product writes under `dev`, including rename endpoint and symlink escapes, refuse; unknown cache/source layouts are not exemptions |
| N5 | `ok`, `approve`, exit 0 or collected verification cannot override missing/mismatched/refused policy evidence in land or ladder |
| N6 | missing output declaration gives no output grant; read snapshot stays immutable even with isolated declared `out/`; missing job/adapter scope grants never widen rights |
| N7 | `dev` writes any exact gate path `ops/bin/dispatch.sh`, `ops/conductor/tools/dispatch.sh` (actual lever body), `ops/bin/go.sh`, `ops/bin/ladder.sh`, `ops/bin/suites.sh`, `ops/conductor/tools/laneconf.py`, or the already protected `ops/conductor/tools/ladder.py`: `lane-write`; `dev` plus a valid maintenance record writes `ops/README.md`: `lane-write`; true-valued maintenance without coverage also refuses; P1 ordinary tooling still passes |
| N8 | `standing: "active"`, any other non-`proposal` value, duplicate keys, wrong boolean types or malformed shared-read paths: `lane-policy` |
| N9 | forged candidate reader/config/seed output or worker HOME store cannot supply admission; mismatched reader/runtime, output byte digest (including changed events/newline), owner principal, policy ref/digest, malformed evidence, missing/conflicting/rejected/superseded rows: `lane-policy`; no successor chasing or per-job fallback for an invalid standing row |
| N10 | per-job evidence reused for another dispatch/job/lineage, or covering a path inside the standing union: `lane-policy`; absent per-job coverage outside the union: `lane-write`; read permission cannot bypass custody |
| R1 | stationary binding and exact artifact/dependency evidence revalidate on settle/resume/collect/land/ladder |
| R2 | changed admitted policy/profile/template/declarations, or legacy unbound write-resume, refuses before marker/store/attempt mutation; collect verification that introduces a forbidden write cannot commit/publish |
| R3 | unchanged legacy records remain readable but cannot land/advance; fresh dispatch preserves provenance; bootstrap is explicit and candidate evaluator cannot accept itself |
| R4 | supersede a listed standing grant: protected maintenance refuses `lane-policy`, even with a valid per-job row; a replacement admission without the verified anchor update still refuses; ratify a fresh admission listing the complete valid replacement set and verify it and the anchor update using the previously trusted consumer/reader/authority: fresh dispatch with covered paths passes, and a second covered job passes without another owner act; old bindings stay unchanged |
| R5 | add a note to a bound admission or grant: authority is unchanged but exact `show` bytes differ; the existing dispatch refuses `lane-policy` at its next settle/collect/land/ladder transition or `lane-resume` before write-resume mutations; a fresh dispatch binds the unchanged authority's new digest and passes without a new owner decision; the old record and digest remain unchanged |
| I1 | active instructions reintroducing mandatory app twins/retirement or app runtime dependencies fail independent review; superseded historical quotations and legitimate product contracts remain allowed |

Docs/data acceptance here is only `git diff --check`, JSON parsing, changed-link
verification and example consistency. Those checks are not runtime acceptance.

## Measured seams and blast radius

Correction inspection at `16aa2d26df2d3ddb5ece9bc9d067b019a9b147c2`:
`cat ops/conductor/tools/decisions.py ops/conductor/tools/laneconf.py
ops/conductor/decisions-register.md ops/lane.conf` measures the existing row,
principal parser, `show` serialization, host-store path and configuration/import
precedence. No host store was read and no register standing was changed.

Inspection at `b9cec26be704c1ef0f993bf96331c7eeef68785e`: `sed -n
'1614,1695p;1840,1865p;1920,1950p' ops/devlane/dispatch/launch.py` identifies
residual enumeration, settlement, write-resume and collect seams; `sed -n
'195,232p' ops/conductor/tools/land.py` and `sed -n '705,730p'
ops/conductor/tools/ladder.py` show the existing acceptance decisions.
`sed -n '1,90p' ops/devlane/dispatch/record.py` confirms infrastructure identity
and record validation. `sed -n '135,145p;170,198p;310,339p;363,414p'
ops/conductor/tools/laneconf.py` measures environment precedence and conformance
constraints; `sed -n '1,65p' ops/bin/suites.sh` measures the suite entrypoint.
These are source observations, not live enforcement or vendor containment probes.
The verification frontier is those consumers, launch/task declaration adapters,
instruction composition and policy data; a changed endpoint re-demands its
contract-verified mocks and independent tests under the shared coupling law.
