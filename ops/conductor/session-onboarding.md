# Deterministic session onboarding and admission

Standing: contract artifact under the owner's 2026-09-09 mandate; ready for
independent construction, not self-approved tests, implemented admission or
activation. The owner requires the complete outcome, not a first deliverable.
This document defines that outcome; this documentation change does not complete
it. [The start plan](conductor-start-plan.md#session-admission-amendment--2026-09-09-owner-boundary)
reciprocally adopts its precedence. Founding authority remains AGENTS.md,
docs/wire.md, docs/workflow.md, docs/probes.md, docs/concerns.md and
docs/verified-couplings.md. Inherit [instrument conventions](instrument-conventions.md).
Dev tooling operates without Symfony, its kernel/container or vendor directory;
docs/mapping.md describes optional prod capabilities, not a runtime dependency.

## Evidence and prerequisites

Inputs read whole: sibling `in/onboarding-request.md`, `owner-clarification.md`,
`inventory-envelope.json`, `host-evidence.md`. The clarification supersedes the
request's initial allocation: the other session is making Git/GitHub agree;
this boundary owns monitoring, discovery and startup. Do not edit or duplicate
`lane/dev-freshness-20260909` or `lane/finding-admission-20260909` here.

Measured 2026-09-10T00:12:37Z at
`20f9bcaf2b3ae2152b9cab766637b5a89b71214b` by Python Path/AST/JSON inspection
and the source commands below. These are snapshot findings, not host readings.

| prerequisite / existing owner | measured standing and admission consequence |
|---|---|
| Discovery: lane_read.py, lane_mcp.py, lane_refs.py; discovery-lever.md | lane_refs exports Acquisition, not the declared public acquire; constructor opens anchors before reading adjacent definitions; lane_mcp CLI lacks discovery-boot-fd handling. D-A31, D-A47 and D-A48 remain blockers, including genuine per-property consultation and executed-byte custody. |
| Canonical execution: dispatch/launch.py, record.py; task/run.py | record validator accepts read/write only; task/run.py retains Popen supervision. Complete the proposed conductor variant and canonical execution consolidation, or refuse every unsupported caller. C1/C2 contract acceptance alone is insufficient. |
| Shared policy: lane-policy.md, permission-surface.md, laneconf.py, decisions.py | ops/lane-policy.json has standing proposal; tools/lane_policy.py is absent. record.py validates binding structure only. Bootstrap custody, evaluator and every launch/resume/tool/settle/collect/land/ladder consumer must be proved before admission. |
| Onboard and hooks | onboard.py remains a read-only brief; SessionStart matches compact only. Brief success neither claims ownership nor proves enforcement. Keep that CLI compatible. |
| Monitor: monitor.py, watchdog.py, watch.py, ci.py | example jobs/context/github monitors all disabled. Existing scheduler, transactions, events and consumer cursors are reusable; no coverage lease or actual-client receipt interface is present among monitor's exported functions. Configuration validity and watchdog startup output do not prove delivery. |
| Freshness and findings integration | Supplied inventory names concurrent branches, not accepted interfaces in this snapshot. findings.REVIEW_JOBS excludes sweep. Bind the completed sync interface and independently admitted findings importer; no substitution with branch names or silent omission. |
| Optional diagnostics and lifecycle | tools/conduct.py, tools/probes.py, workflow/wf.py and vendor/bin/mate are absent here. ops/README.md's claimed wf read projection is an inherited discrepancy. Missing generic workflow runtime does not prevent read discovery; owner-initiated publication retains its separate prerequisite. |

Reproduce the structural observations with `git rev-parse HEAD`,
`sed -n '362,408p' ops/conductor/tools/lane_mcp.py`,
`sed -n '760,805p' ops/conductor/tools/lane_refs.py`,
`sed -n '960,985p' ops/devlane/task/run.py`,
`sed -n '1,155p' ops/devlane/dispatch/record.py`, and
`sed -n '30,45p' ops/conductor/tools/findings.py`; JSON inputs are
`.claude/settings.json`, `ops/lane-policy.json`, `monitor.example.json`.
Path.exists distinguishes absence from unreadability; a failed read is not absence.

The supplied host report records Codex 0.154.0 hook discovery and a successful
ephemeral app-server thread calling agentscient_lane/lane_brief through its own
MCP connection without a model turn. It also records an old seven-tool v2 host,
an older owned server worktree/config, optional codex_apps and available prod
Mate tools. These are attributed host observations, not probes rerun here.
They establish a candidate transport, not current onboarding, hook enforcement,
model identity or alert receipt. Local missing vendor and host Mate availability
are different measured scopes. Never promote the reported 2214-test baseline
to acceptance of this new contract. No session store was read for this artifact.

## One owner for each coupling

| edge | producer → consumer; retained authority |
|---|---|
| Startup composition | proposed tools/conduct.py prepare_conductor → canonical dispatch/launch.py; start-plan descriptor and harness-capabilities compile_launch remain the interfaces |
| Identity, attempts, ownership, admission history | dispatch/launch.py and record.py → policy, status/wait/resume and read projections; existing canonical dispatch directories and retained record handles |
| Policy and instructions | laneconf/decisions plus verified custody → lane_policy.bind_launch/check_transition/evaluate_tool; existing policy, grants and tool Request/Decision schemas |
| Discovery | lane_refs.acquire(config, boot, checkpoint=...) → lane_read → lane_mcp CLI/resources/tools; owning discovery contracts, fixed reads, no subprocess in read core |
| Git/GitHub currency | sync owner's verified counterparty → startup/branches/monitor; Freshness/1 below is the required normalized handover, not a second fetcher |
| Coverage and alerts | monitor scheduler/store plus watchdog/watch/ci observations → dispatch supervision and harness adapter; existing monitor SQLite owns leases, queue, receipts and cursors |
| Client proof | existing harness adapter behind canonical launch → retained probe evidence and startup; no independent app-server executor/session database |
| Findings and review | existing findings importer/ledger → policy admission and bounded discovery; require sweep integration when that evidence is required |

Every edge needs contract-verified mocks, independent fault/clean cases and live
version-bound evidence when external. Missing counterpart means unsupported;
do not manufacture success to get past the dependency graph. Existing record,
monitor and discovery closed schemas require the extensions below to be adopted
by their owners in the implementation frontier; this two-file artifact does not
silently change their readers or claim those extensions shipped.

## Admission state machine and identity

Actor role, job role, work profile, harness, requested model and observed model
are distinct. Use start-plan LaunchSelection for conductors and task-owned
TaskSelection for workers. Session identity is canonical dispatch id plus attempt
number plus observed client session/thread id. Environment variables and a model's
self-report cannot establish it. A worker's isolated snapshot does not grant a
conductor's sources or exclusivity over its invoking worktree.

The following graph is data for the existing workflow genus, composed by the
dispatch owner; it does not introduce a workflow engine. State is recorded in
Admission/1. No model turn or effectful tool is released until admitted.

| transition | actor, required evidence and failure |
|---|---|
| unbound → prepared (memory only) | trusted startup validates identity/selection, descriptor, current instructions/policy, capability witnesses, sources, freshness and budget; failure is pre-effect exit 2 |
| prepared → checking | canonical dispatch claims its directory and work ownership, retains inputs, registers attempt and starts quarantined client through the existing adapter; any subsequent failure is Abort 3 |
| checking → admitted | startup verifies coverage lease, current client MCP, bounded initial delivery, real alert receipt, current source recheck and durable admission commit; all required gates pass |
| admitted → suspended | dispatch supervisor invalidates action permits immediately on event/expired evidence/lease or delivery loss; append evidence; already-started operations use existing late-refusal handling |
| suspended → checking → admitted | trusted resume/revalidation, same dispatch id and verified ownership, new admission epoch and client connection generation; all required gates freshly checked |
| checking/suspended → refused | failed control, timeout, unsupported boundary or unavailable required evidence; no unattended fallback, harness swap or self-admission |
| admitted/suspended/refused → closed | canonical close releases only owned claims/consumer lease, records terminal state; never publishes handoff/AAR automatically |

Reads remain identity-free under the wire: brief, doctor and historical status
continue to serve bounded observations with explicit uncertainty. They confer
no admission. Policy remains the sole tool authority. An admitted session also
needs a fresh once-consumed policy Decision before each effect; a startup pass
does not grant a permanent tool bypass. Understanding prose cannot be proved;
prove delivery of authoritative instruction bytes and mechanical enforcement of
critical source, role, delegation, ownership and publication boundaries instead.

Work ownership is dispatch-owned, distinct from a monitor lease. WorkKey is
`{repository:ID,common:Node,worktree:Node,lineage:ID}`, where Node is
`{device:Int,inode:Int}` from held common-gitdir/worktree-gitdir descriptors.
Same worktree or same repository/lineage conflicts across different live owners;
path spelling, symlink aliases and different profile names do not avoid conflict.
A conductor claim is exclusive. Separate worker snapshot claims are job-bound
and do not steal their parent claim. Concurrent conductor sessions need distinct
owned worktrees and lineages, or one must remain an unadmitted reader.

Use the canonical store's dispatch-owner lock for claim/renew/release, not a new
claim store. Under that lock scan at most 4096 canonical record headers (1 MiB
each, 16 MiB aggregate, 2-second lock wait, 5-second scan deadline); overflow or
unreadable potentially active claim refuses ownership. Persist WorkClaim/1 beside
its canonical record. Lock plus create-only record claim and verified live lease
prevent two winners. Crash after claim is conservative: unfinished claim blocks
until canonical recovery proves owner dead/expired and records fenced takeover.
PID existence alone, wall clock alone and empty scan after a read failure are
insufficient. Renew every 10 seconds, lease 30 seconds; host boot id, PID start
identity and monotonic time bind liveness. Expiry fences old owner before any
new one receives permits; old generation cannot renew or release successor.

## Authoritative inputs and freshness integration

Startup retains exact instruction file bytes/hashes and precedence in the
existing declarations closure: AGENTS.md, applicable scoped instructions,
ops/README.md, wire/workflow/probes/concerns/couplings, owning policy and contracts,
then explicit job/profile material. Reports, handoffs and branch prose remain
untrusted data. Resolve conflicts at their owning instruction boundary; unknown
authority is a refusal, never a ranking guessed from modification time.
Discovery's HEAD-only snapshot cannot prove dirty/untracked instruction currency.
Trusted startup compares actual delivered instruction bytes with admitted sources,
rejecting unbound overrides; it does not parse prose into grants at runtime.

Freshness is a normalized read result from the Git/GitHub sync owner, with its
implementation revision, owning contract and independent verification retained.
The exact local callable is `branches.session_freshness(binding, *, clock)`
returning Freshness/1 or Refusal. This is a proposed adapter in branches.py to
that counterparty; it must not implement another fetch/sync algorithm. Binding is
exactly `{work:WorkKey,repository:Repository,remote:ID,upstream_ref:string,
requirement:"equal"|"contains",policy:Evidence}`, with Repository the discovery
closed object. Startup verifies every value and the policy handle; the adapter
cannot grant or weaken requirements.
Absent or incompatible sync API refuses `onboard-freshness`; integration must
record the actual symbol/version and map every field, with no guessed defaults.

Freshness/1 is exactly
`{schema:"session-freshness/1",work:WorkKey,head:OID,ref:string|null,
remote:ID,upstream_ref:string,upstream:OID|null,forge:OID|null,
fetched_at:UTC|null,checked_at:UTC,requirement:"equal"|"contains",
relation:"equal"|"ahead"|"behind"|"diverged"|"unknown",
dirty:bool|null,untracked:bool|null,state:State,reason:Reason|null,
counterparty:Evidence}`. Refs use discovery's validated full ref grammar.
OID is its SHA-1 type; unsupported repository formats refuse explicitly.
Remote name and expected upstream come from policy, not cwd heuristics.

For this admission, sync must succeed, upstream equal forge, required local
relation hold, and fetch age be 0..60 seconds. Equal requires head=upstream;
contains permits equal/ahead only with verified ancestry. Policy supplies the
requirement, never the caller. Unknown dirty/untracked state refuses. Existing
WIP is preserved: dirty/untracked allowed only when policy explicitly accounts
for all such paths and delivered instruction custody; otherwise refuse, never
reset/stash/delete automatically. Nonzero fetch, authentication/network failure,
future timestamp, stale fetch, stationary remote with behind checkout, wrong
branch or source movement invalidate freshness. Monitoring consumes the same
observation; it does not own Git/GitHub sync. No foreign branch work is assumed
landed or active. Ref movement requires fresh acquisition and renewed evidence.

## Complete discovery with bounded first context

Reuse the existing catalogue/discovery owners; conformance registries are not
the whole inventory. The independent inventory gate compares a retained tree
enumeration against classified routes, including every member of these families:

| family | discovery routes that must be represented |
|---|---|
| Instruments and registries | every public CLI under ops/conductor/tools and every ops/conductor/registry JSON; branches, ci, co_doc, decisions, dispatch, findings, gate, hand, ladder, land, lane_mcp, laneconf, monitor, onboard, skills, watch, watchdog; lane_read/lane_refs classified library owners |
| Project and execution | every ops/bin lever; dispatch/launch/record/levers including preserved vendor launch/selftest/apply paths; task jobs/run/fileset/verify/envelope; harness isolation/probe/vet_context/wires/stage/controls; classify aliases and unsupported legacy launch routes explicitly |
| Checks and infrastructure | workflow/checks entrypoints, fixtures/stores and fixture lever, hook/install and every Claude hook, wiring declarations, infra build/containment/Gitea/lane/runner entrypoints; helpers remain classified, not silently discarded |
| Features, skills and cost | every ops/design/features/**/*.feature and owner/check link; usage, worth, pulse, breaker, jobs budgets, process/worth and token-thrift, skill registry plus declared .claude/.agents skills, dev-subs and pr-overview review-comment routes |
| Work and evidence | jobs and roles, decisions/handwork/findings/review-comments, branch/CI/dispatch status, monitor/watchdog, handoff/AAR/probes and explicit unbuilt workflow/board/probes routes |
| MCP | all configured servers, complete tools/list, resources/list and resource-template listings with pagination, every CLI/tool/resource projection and supported protocol version, connection/error state; external connectors separately classified |
| Native client tools | every effective adapter tool/feature and its normalized policy schema, including shell, edits, delegation, hooks and connection/lifecycle mechanics; measured availability and enforcement are separate |
| Prod route | AGENTS.md and mate/AGENT_INSTRUCTIONS.md → vendor/bin/mate tools:list, tools:inspect, tools:call; bin/console, docs/mapping.md, packages/README.md; enumerate actual Mate tool schemas only when that optional runtime can be inspected |

Inventoried presence is not authority to execute. An enabled feature needs owner,
test/probe and implementation standing; a feature scenario alone is documentation.
All retained files in these roots get a classification, including private helper,
test, captured fixture or document. Compare the complete path set, not grep hits
for main functions alone. Newly added, deleted or renamed paths invalidate the
catalogue fingerprint and require regenerated owner classification. Discovery
does no arbitrary execution to discover verbs. Public command schemas come from
their owners and retained measured help/registry evidence. Unclassified items
make completeness false; a missing executable is a measured unavailable route.

Do not silently expand discovery/3's fixed eleven-tool schemas. Proposed
discovery/4 is the minimal versioned counterpart in lane_mcp/lane_read/lane_refs:
config version 4 has exactly v3's keys, bounds and custody, with protocol tag
discovery/4 in fingerprints. It retains the eleven query shapes and adds only
`lane_catalogue`. v1/v2/v3 validation, output bytes and counts remain unchanged.
Version 4 check reports `{valid:true,tools:12}`; versions below 4 refuse the new
query by the existing unknown-tool wire. Admission requires version 4; old
clients remain supported readers, explicitly unsupported for this admission.

`lane_catalogue` closed arguments: required `profile:ID`; optional
`snapshot:SHA256,cursor:string,id:Concept`. Concept is discovery's concept grammar.
Named id and cursor are mutually exclusive. CLI:
`python3 -B ops/conductor/tools/lane_mcp.py --config FILE --discovery-boot-fd FD query lane_catalogue JSON`.
The boot fd contract and execution evidence remain mandatory for v4. MCP uses
the same tool and `lane://catalogue/PROFILE`, template
`lane://catalogue/{profile}/{id}`; list pages use tool/CLI cursors. Resources
never mutate, acknowledge, run probes or expand roles. Existing eleven routes
and resource templates remain discoverable from the connected client.

Envelope is discovery's exact closed envelope with query additionally permitting
lane_catalogue. Its data is exactly
`{items:[Capability],item:Capability|null,page:Page|null,complete:bool}`.
Named lookup gives items [], page null; missing id gives item null and reason
unknown-key. Capability is closed:
`{id:Concept,kind:Kind,owner:relative-file,paths:[relative-file],
entrypoint:relative-file|null,detail:Detail,effect:"read"|"write"|"none",
standing:"supported"|"unavailable"|"unsupported"|"unclassified",
reason:Reason|null,evidence:[Evidence]}`.
Kind is one of `cli,library,registry,lever,job,hook,feature,skill,telemetry,
review,monitor,native-tool,mcp-tool,mcp-resource,mcp-template,prod,document,test,fixture,infra`.
Detail is exactly `{argv:[Text]|null,tool:Text|null,resource:Text|null,
schema:Evidence|null,alias_of:Concept|null}`. Empty argv is invalid; null means
no executable route. Evidence-backed schemas describe exact arguments/results;
no arbitrary object escape hatch. A supported callable must have non-null
schema and route, and known effect. External routes have entrypoint null and
their exact connected tool/schema, with no inferred permission to act.

Fixed v4 acquisition adds only retained tree enumeration of the table's roots
and explicitly declared support files; 4096 paths/4096 cards, 4 MiB classification
bytes, within the discovery adapter's stricter aggregate/deadline if applicable.
Classification is compiled into lane_read's trusted definition bytes, owned by
existing owner declarations, not a parallel registry/store. Missing classifications
are reported, not created by runtime prose interpretation. Owner paths not yet
defined must use standing unclassified, owner=this contract and no executable
route until reconciled; this placeholder cannot satisfy completeness.

External/Mate catalogue observations are supplied through trusted adapter
evidence in the canonical record, read via authorized dispatch sources; discovery
does not call a vendor or import Symfony. Their Capability cards join the same
derived index. Unavailable optional service creates one explicit unavailable
service card and null list measurement, never an empty successful tool list.
Required service failure blocks admission. All pages of a reachable service
must be measured before claiming complete; unknown permission/effect makes a
tool unsupported, even if visible. Opaque credentials and raw transcripts never
enter the catalogue. Untrusted descriptions are named detail data only.

Fingerprint v4's complete classifications, actual tree paths/modes/blob hashes,
source failure/completeness markers and supplied external schema/connection
evidence into the existing sources/snapshot recipe. Reacquire before each query;
same bytes produce same snapshot, source movement invalidates cursors. New
catalogue cursor is `<snapshot>:<offset>`, canonical decimal 1..4095, offset<total,
requires matching snapshot, no retries on races. Sort unique ids bytewise, page
greedily at most 16 cards/16384 encoded bytes including metadata. A card/frame
that cannot fit returns existing item/page-frame-exceeds-cap, never truncation.
Enumeration overflow is query-wide unavailable/record-overflow. Profile filters
relevance only; catalogue visibility never enlarges grants. Each profile includes
its authorized discovery catalogue route among existing configured homes.

The automatic first packet is Initial/1, at most 12288 encoded UTF-8 bytes,
including newline and adapter framing. It contains exactly
`{schema:"session-initial/1",identity:Session,epoch:Int,instructions:Evidence,
policy:Evidence,admission:"checking",discovery:Envelope,catalogue:Detail,
required:[GateName],optional_gaps:[Gap],delivery_nonce:SHA256}`.
Discovery is one lane_start response capped at 8192 bytes, no nested handoff body.
The remainder has a 4096-byte ceiling; if mandatory context does not fit, refuse
budget. Required gates are all listed below, no silent dropping. At most 16
optional gaps; more uses one explicit aggregate gap and named catalogue detail.
Instructions reference retained authoritative bytes; the actual adapter-delivered
base/developer instruction channel is separately hashed in the receipt. Its
critical rules and this packet together must meet the total first-context cap;
full documents remain named reads. Do not include onboard.calibration's unbounded
thread dump. Current state, law routing, ownership and the next catalogue call
must be discoverable with no owner-provided filesystem hints.

Token counts are recorded from the measured adapter/tokenizer if available;
otherwise null, never byte/4 called measured tokens. Serialization success
certifies a packet only. It is not admitted until the intended actual client
receives it and every gate below is durably committed.

## Monitor coverage, reuse and liveness

Monitor/1 configuration remains compatible. Proposed coverage operations extend
monitor.py, using its existing SQLite database and transaction/dedup machinery.
They do not silently add registry-v1 keys or relocate state. Trusted startup
passes CoverageRequest via inherited read-only input, never an MCP write.
Use one scheduler owner per exact coverage definition; fan out events to explicit
session consumers with separate receipt/cursor state. No model per tick.

CoverageRequest is exactly
`{schema:"session-coverage/1",session:Session,work:WorkKey,
monitor_config:Evidence,definition:SHA256,requirements:[Coverage],
operation:"ensure"|"renew"|"release",generation:Int|null}`.
Coverage is `{id:ID,subject:Text,source:Evidence,required:bool,
every_ms:Int,stale_ms:Int,route:ID}`. At most 64 unique ids, sorted by id;
every_ms 1000..60000, stale_ms between every_ms and 120000. definition hashes
canonical monitor config plus ordered requirements (excluding session and
operation), so identical source/condition/schedule requirements share a scheduler.
Evidence is a held source locator binding, not source contents or a session scan.
Required coverage includes selected dispatch lifecycle/no-op/death, work freshness,
instruction/policy/config/source changes, scheduler health and delivery health.
Usage/context/budget/quota are required only when policy relies on them; otherwise
report explicit unsupported/unavailable, never fabricated zero spend or currency.
Explicit current session rollout/job ids come from canonical records, not newest
filename, cached examples or whole-home scans. Empty selected work may be a valid
measured set; missing selection is unknown and cannot enable a required monitor.

`monitor.ensure_coverage(request, *, store, clock, checkpoint=None)` returns
CoverageResult; same interface handles renew/release. Store is a verified existing
monitor-state handle from launch, not a model-selected path. Clock exposes UTC,
monotonic milliseconds and boot id. Monitor alone migrates its database with a
versioned transaction; existing queue/cursor rows survive unchanged. Unsupported
database schema refuses before mutation. Ensure requires generation null;
renew/release require the currently held positive generation and exact session
binding. New logical rows in that same database:

| row / unique key | exact payload |
|---|---|
| coverage_owner / definition | `{definition:SHA256,process:Process,generation:Int,renewed_ms:Int,expires_ms:Int,config:Evidence}` |
| coverage_consumer / definition, session.dispatch, session.attempt | `{definition:SHA256,session:Session,generation:Int,expires_ms:Int,requirements:[Coverage]}` |
| delivery_receipt / event_id, session.dispatch, session.attempt, connection | DeliveryReceipt below |

Process is `{boot:Text,pid:Int,start:Text,executable:SHA256}`; pid>0, checked via
the platform's measured process-identity mechanism, never basename or kill(0)
alone. Unsupported process identity is explicit. Owner lease renews every 10s,
expires at 30s on the same boot/monotonic clock; consumer renew/release is separate.
Matching healthy coverage reuses the owner and records reused=true. Incompatible
definition may coexist as a distinct requirement only after shared source schedules
are deduplicated; never claim reuse across different source/condition/config bytes.
Concurrent ensure calls atomically select one owner generation. Scheduler creation
is delegated to canonical supervision, not spawned by discovery or another daemon
framework. No process is launched until a unique fenced reservation exists.

Expired/dead owner is fenced by incrementing generation in the same transaction;
old generations cannot enqueue, renew, deliver or release. New owner reuses existing
event dedup/cooldown state; it does not replay all persistent threshold matches.
One consumer closing must not stop coverage required by another; last release
allows the canonical supervisor to stop only the positively identified owned process.
Missing/corrupt DB, disabled required schedules/routes, overdue observations,
all-disabled config, unknown source or scheduler death cannot mean healthy empty
queue. Supervisor checks health every 5s and before each effect. At the earliest
of owner expiry, consumer expiry, observation stale_ms or receipt expiry, permits
are invalid. No monitor can be its sole liveness witness: canonical supervision
observes its process/lease, and the policy gate checks independently on each tool.

CoverageResult is exactly
`{schema:"session-coverage-result/1",state:State,reason:Reason|null,
definition:SHA256,generation:Int|null,reused:bool|null,owner:Process|null,
expires_ms:Int|null,consumer:Session,readings:[CoverageReading]}`.
CoverageReading is `{id:ID,state:State,observed_at:UTC|null,age_ms:Int|null,
reason:Reason|null,evidence:Evidence|null}`. Every requirement gets one reading
in request order; unknown age is null. Healthy requires all required readings ok
and valid owner/consumer leases. Release succeeds with owner null only after
confirmed last release; it is never usable as an admission health result.

## Actual-client connection and delivery proof

The canonical harness adapter owns client transport and quarantine. It exposes
`observe_client(binding, challenge, *, deadline, checkpoint=None)` returning
ClientProof/1 or Refusal, with binding the verified startup descriptor/Session
handle, challenge `{connection:SHA256,nonce:SHA256,event_id:Int|null,
initial:Evidence|null}`, and monotonic deadline from startup's overall budget.
Client connection generation and nonce are fresh launcher-generated 256-bit
values; they are correlation challenges, not model-generated authentication.
No generic caller-supplied URL, command, socket or environment transport is allowed.

For each new actual client, collect initialize identity/capabilities, complete
tool/resource/template listings and one actual lane_start call through that
client's bound connection. Compare retained executable/load evidence, pinned
server/config/anchor identities and actual catalogue/schema digest with the
descriptor. A separately launched CLI, configuration entry, help text or server
self-report cannot substitute. The Codex app-server thread plumbing in the supplied
host report is a candidate implementation of this same adapter only; stale v2
catalogue fails. Hook firing before MCP readiness keeps checking, bounded by
deadline. Missing/fail-open hooks require a separately proved blocking mechanism
or make the operation unsupported. A hook-success exit is not enforcement proof.

After coverage is active, enqueue a synthetic monitor event using normal event
identity, consumer isolation and dedup, with a unique challenge nonce. The adapter
must observe delivery to the intended client instruction/event channel and retain
a transport receipt tied to event, session, connection, nonce and content digest.
Probe an idle client as well as one processing a turn. An unrelated app-server
thread, another session's transcript, stdout, digest fetch or --ack alone fails.
Without a measured idle delivery mechanism, required unattended coverage is
unsupported; explicit pull-only visibility remains useful diagnostic data.

DeliveryReceipt is exactly
`{schema:"session-delivery/1",event_id:Int,session:Session,connection:SHA256,
nonce:SHA256,payload:SHA256,emitted_at:UTC,received_at:UTC,
latency_ms:Int,channel:"client-event"|"client-instruction",
observation:Evidence}`. event_id>0; latency 0..5000, verified by monotonic
observation; both timestamps from the trusted adapter, no client wall-clock trust.
Receipt observation binds process/thread/socket or equivalent actual endpoint
identity and received bytes; server-generated nonce echo alone is insufficient.
Monitor retains the receipt and only then advances that consumer's cursor through
contiguously received events. Existing ack semantics do not become proof of receipt.
Duplicate receipt is idempotent; out-of-order receipt does not skip missing events.
Reconnect uses a new connection, replays pending events to that consumer and
deduplicates presentation by event id; old connection receipts cannot qualify.

ClientProof/1 is exactly
`{schema:"session-client/1",session:Session,connection:SHA256,
descriptor:SHA256,server:SHA256,config:SHA256,catalogue:SHA256,
initialize:Evidence,listings:Evidence,start_call:Evidence,
initial:Evidence,instructions:Evidence,receipt:DeliveryReceipt,
checked_at:UTC,transport:Evidence}`. All are required and equality-checked with
held inputs. Partial proof is retained as separate actual observations, never
filled with fake handles to satisfy this successful shape. Reprobe receipt every
30s with a new nonce; receipt age>35s suspends admission. This proves byte delivery
and route liveness, not human/model comprehension. No external connector action
is authorized by the proof or tool availability.

## Exact startup interfaces, schemas and durable evidence

Keep `conduct <harness> <profile> [-- SAFE-TOKENS...]` and its test forms exactly
as the start plan declares. Proposed executable home is tools/conduct.py, thin
over canonical launch. Add only:

```
python3 -B ops/conductor/tools/conduct.py status DISPATCH_ID
python3 -B ops/conductor/tools/conduct.py resume DISPATCH_ID
python3 -B ops/conductor/tools/monitor.py [--config FILE] [--state DIR] coverage --input-fd FD
```

status is an identity-free, noncreating read returning the latest Admission/1
plus current validity as Status/1 below; unknown record is explicit unavailable.
resume resolves trusted retained selection/descriptor; no role/profile/model/path
override flags. Coverage FD is an already-open read-only regular descriptor,
max 65536 bytes; verify trusted caller custody, not just the fd number. Arbitrary
stdin/JSON/environment is not equivalent. WF_AGENT is required for writing verbs;
it attributes actions and is not proof of caller authority. Unknown/duplicate
flags, malformed IDs and unexpected positionals refuse arguments before state.
Existing onboard.py and monitor check/run/digest syntax stays unchanged.

`conduct.prepare_conductor(trusted_context, selection, forwarded_tokens, operation)`
keeps the start-plan pre-effect return of descriptor plus compiled launch. The
new proposed composition seam is
`conduct.admit_session(context, event, *, clock, checkpoint=None) -> Admission`
inside the same owner. Context is the held canonical launch/record/policy/adapter/
monitor/freshness/discovery capability set, not serializable caller claims.
Event is `{cause:Cause,previous:SHA256|null}`. Cause is
`launch,resume,compaction,reconnect,source-change,config-change,policy-change,
monitor-loss,delivery-loss,expiry,close`.
Launch requires previous null; all others require the exact current retained
admission digest (or explicit recovery of a checking partial by canonical owner).
Repeated identical event/current generation is idempotent; a stale previous
digest refuses revision. Effectful steps are dispatch/monitor methods, never
Popen or persistence implemented again in conduct.py.

New library seams raise the owning Refusal exception on rejection; they never
return a success-shaped object containing an error. The CLI alone renders exits.
admit_session returns Admission only after retaining it; late failures retain a
refused receipt when possible and raise for the canonical Abort handling.

All new JSON objects here are closed and every shown key required. Reject extra,
missing or duplicate keys, booleans as integers, nonfinite values, invalid UTF-8,
control characters, depth>32, integer outside 0..2^63-1 and oversized input.
Canonical encoding is start-plan's sorted-key ASCII escaped compact JSON without
newline; transport adds one newline and counts it. SHA256, ID, OID, relative-file
inherit their exact owning grammars. DispatchID here is the canonical dispatch
record ID grammar; its stage must be conduct for a conductor and the declared
worker stage for a worker. Start-plan's conduct-only specialization is unchanged.
Text is printable ASCII
1..256 bytes, UTC is `YYYY-MM-DDTHH:MM:SS.sssZ` (real calendar/time), Int the above
integer. Arrays preserve defined order, are duplicate-free where identities are
named, and have at most 4096 elements unless a tighter bound is specified.

Supporting closed types:

| type | exact fields |
|---|---|
| Evidence | `{path:relative-file,sha256:SHA256}`; existing policy handle below canonical dispatch custody, never arbitrary path; raw file-byte digest |
| Session | `{dispatch:DispatchID,attempt:Int,client:Text|null,role:"conductor"|"worker",job_role:"read"|"write"|null,profile:ID}`; attempt>0 after registration; conductor null job_role, worker matches record; client null only before observation |
| WorkClaim/1 | `{schema:"session-work/1",work:WorkKey,dispatch:DispatchID,generation:Int,process:Process,renewed_ms:Int,expires_ms:Int}` |
| State | `ok,unknown,unavailable` |
| GateName | `identity,ownership,freshness,instructions,policy,capability,discovery,coverage,connection,delivery,durability` |
| Gap | `{gate:GateName,state:State,reason:Reason,detail:Concept|null}` |
| Gate | `{name:GateName,state:"pass"|"fail"|"unreachable",reason:Reason|null,evidence:[Evidence]}`; pass requires nonempty verified evidence and null reason |
| Refusal | `{class:Class,expected:Text,found:Reason,needed:Text}` |

Admission/1 is exactly
`{schema:"session-admission/1",session:Session,epoch:Int,previous:SHA256|null,
cause:Cause,state:"checking"|"admitted"|"suspended"|"refused"|"closed",
at:UTC,valid_until:UTC|null,work:WorkKey,descriptor:Evidence,
instructions:Evidence,policy:Evidence,freshness:Evidence|null,
ownership:Evidence|null,coverage:Evidence|null,client:Evidence|null,
initial:Evidence|null,gates:[Gate],optional_gaps:[Gap],
measurements:Measurements,refusal:Refusal|null}`.
Gates contain all eleven names in the table order, exactly once. Required gates
are never configured away for admission. Optional gaps refer to optional sources
within a gate; they cannot excuse the gate itself. Unknown handoff selection,
absent prod vendor or unsupported optional quota can remain explicit gaps when
policy does not require them. Missing ownership, required discovery completeness,
required source/freshness, coverage or client delivery can never be optional.

Measurements is `{elapsed_ms:Int,initial_bytes:Int,detail_bytes:Int,
input_bytes:Int,peak_rss_bytes:Int|null,tokens:Int|null,tokenizer:Text|null,
external_calls:Int,monitor_processes_started:Int,monitor_processes_reused:Int}`.
Tokens and tokenizer are both null or both measured. These are per admission,
not inferred session spend. Admission epoch starts at 1 and increments under
canonical record revision lock. No new session ID/correlation namespace.

Status/1 is `{schema:"session-status/1",dispatch:DispatchID,
admission:Admission|null,valid:bool,state:State,reason:Reason|null,checked_at:UTC}`.
Historical admitted receipt alone never sets valid=true; read current leases,
identity, required bindings and expiry without renewal or creating a database.
Unobservable current validity gives false/unavailable, not historical green.

Extend the proposed canonical conductor object's closed keys from
`descriptor,binding,declarations,custody` to those four plus `onboarding` (nullable
Evidence). It points to the latest immutable Admission/1 under the same record;
workers' existing top-level schemas are unchanged and their admission handles
belong to retained LaunchDeclarations evidence, not invented conductor fields.
Canonical record validator/status/wait/resume, read projections, findings and worth
must adopt or explicitly refuse this extension. Until then it is unsupported.

Store immutable receipts at `onboarding/00000001.json` etc. under the existing
dispatch directory, with supporting evidence in that directory's existing custody
area, inaccessible to model writes. Filenames use eight decimal digits (epochs
1..99999999; exhaustion refuses budget). previous chains exact receipt bytes;
retain evidence hashes/producer/checked ref through canonical custody. Hold the
canonical record lock, write exclusive temp, fsync file, rename create-only, fsync
directory, then atomically update/fsync the record handle. Durable receipt and
record pointer must verify before releasing the first action. A crash between
steps leaves checking/partial evidence; recovery never assumes admitted from
an orphan receipt. Reconcile idempotently under the same lock, revalidate, and
append a new receipt. No historical receipt is edited or backfilled.

Evidence handles always name immutable retained bytes. Lease renewals mutate only
their owning live state; each admission retains an immutable observation of that
state. Never hash a mutable WorkClaim file and later present it as a retained receipt.
Admitted requires non-null client identity, all eleven gates pass, non-null required
handles and valid_until, and refusal null. Refused requires a refusal and at least
one nonpassing gate; checking/suspended cannot authorize effects. Successful closed
state preserves its historical gates but grants no current permit.

Durability gate evidence references the already fsynced prerequisite bundle and
verified commit intent, not its own future hash. The canonical owner separately
observes successful receipt and record fsync and rereads the final pointer before
issuing any permit. Status/recovery demand that completed commit and current gates;
a serialized admitted object or commit intent alone never establishes admission.
There is no self-hash cycle or required reference to a not-yet-written receipt.
For a late failure keep unavailable handles null, actual observations intact,
terminal result.status invalid (or existing tripped), result.envelope null and
refused PolicyResult under the canonical variant. A successful terminal result
also needs observed model and ordinary settlement; startup admitted is not task
completion. If storage fails, emit the last reading and explicit unavailable
durability, Abort 3, no receipt claim. Never publish handoff/AAR on compaction,
stop, lease renewal, error or close; those remain owner-initiated.

## Revalidation and measured bounds

Before each effect, policy checks current admission epoch, work/coverage lease,
receipt age, source/config/policy/instruction digest and current selected identity.
Source movement, resume, compaction and reconnect suspend first, then revalidate;
the action waits or refuses. Reconnect always changes connection nonce and proves
MCP plus initial delivery again. Resume preserves role/profile/grants and uses
operation-specific capability evidence. Changing authority, executable, adapter,
grammar, normalizer, source anchors or policy requires fresh capability/custody
verification; forbidden changes require new admitted launch, no automatic upgrade.
Ordinary HEAD movement is permitted only under existing lineage/freshness policy
after fresh source acquisition. Old cursor/Decision/receipt never crosses epochs.

| resource | deterministic acceptance budget |
|---|---|
| Total prepare plus first admission or revalidation | 60000 ms monotonic, one shared deadline; no retries resetting it |
| Trusted boot | existing 10s, 1 MiB/file, 4 MiB total; existing discovery acquisition budgets still bind |
| Actual client connect/catalogue | 15000 ms within total; max 16 servers, 4096 combined entries, 4 MiB aggregate listing bytes, 64 pages/server; cap/timeout required server is unavailable |
| First context / named detail | 12288 / 16384 encoded bytes including framing; measure worst-case escaping and mandatory metadata; no successful truncation |
| Alert delivery / continued health | <=5000 ms delivery; reprobe every 30000 ms, valid through 35000 ms; 5s supervisor checks plus effect-time checks |
| Lease | 10s renew / 30s expiry, same boot monotonic clock; unknown/reversed clock suspends |
| Sync evidence | <=60s age with successful current check; source change invalidates immediately |
| Retained admission input/output | 65536 bytes per request/receipt; 16 MiB aggregate evidence per epoch; overflow refuses before acceptance |
| Poll work | fixed schedules, skip missed intervals; max 4 concurrent observation readers, one source read per due schedule shared across consumers; zero model calls per tick |

Budgets are normative ceilings, not measured performance claims. Independent
acceptance records actual elapsed/byte/call/process readings for each row, pinned
to tree, runtime, adapter and fixture size, with cold/warm runs and boundary-size
controls. Reuse test: ten admitted consumers with identical coverage produce one
scheduler, one observation/source/due tick and ten isolated deliveries; no
tenfold source polling. Oversized catalogues refuse boundedly rather than being
treated as complete. RSS is measured when supported, null otherwise; no invented
RSS threshold or cost/currency. valid_until is the earliest projected UTC expiry
of required evidence; effect gates use original monotonic deadlines, not that
display timestamp. Clock/boot discontinuity demands revalidation.

## Refusals and unsupported states

Class is one of `arguments,identity,conduct-config,conduct-mcp,onboard-ownership,
onboard-freshness,onboard-instructions,onboard-discovery,onboard-monitor,
onboard-delivery,onboard-evidence,onboard-budget,onboard-revision,
onboard-unsupported`, or an unchanged owning policy/adapter refusal class.
Reason is one of `malformed,missing,unreadable,untrusted,mismatch,stale,changed,
conflict,expired,dead,disabled,unsupported,unreachable,timeout,overflow,
unclassified,not-received,replayed,storage,clock,precondition`.
Discovery retains its own more specific reason enum inside its envelope.
Pick the first failed gate in GateName order, preserve all measured evidence;
schema/identity/argument errors precede gates. No raw input, secrets or vendor
stderr enters refusal text. Render exactly the inherited one-line wire, e.g.:

```
onboard-monitor: expected live required coverage; found expired; needed restore coverage and revalidate this session
onboard-delivery: expected actual client receipt; found not-received; needed verify the bound delivery adapter
```

Before the invocation's first durable mutation: exit 2, empty stdout, exactly
one refusal line. After record/lease/attempt/state mutation: Abort 3 with last
reading and retained partials; do not promise exit 2 after a child or reservation
already exists. Resume preflight is pre-effect even with historical attempts.
status returns 0 for valid admission, 1 for completed read with invalid/unknown
admission; malformed invocation is 2. Normal closed conduct uses canonical
settlement exit meanings; admission itself returns 0 only after durable commit
and valid required gates. MCP remains read-only and uses its existing errors.

Unsupported states explicitly include legacy/unbound sessions, unproved harness
launch or resume, missing deterministic interception, fail-open hook without
proved enforcement, no actual-client/idle delivery mechanism, unobservable process
identity, unsafe/unsupported repository storage, unavailable custody boot,
missing policy or sync counterpart, stale selection, unsupported record/database
version, catalogue incompleteness and source/connection mismatch. No attended
fallback or vendor default converts these to admitted. Optional prod diagnostics
remain discoverable with state unavailable when vendor is absent, without
preventing dev tooling from running. An unavailable probe is neither clean nor
a detected fault; retain it separately and do not admit the required edge.

## Independent acceptance and implementation frontier

This producer declares cases only. Independent producers author tests, verified
mocks and reviews; implementation authors neither write nor approve their tests.
Use existing conductor/dispatch/harness test homes and registry rows at runtime
landing, then `ops/bin/suites.sh` on the combined stationary ref. Synthetic proof
precedes real probes but cannot replace them. Each row needs both arms, exact
wire/data/effect assertions and measured budgets. No row is currently passed.

| row | planted fault | clean neighbor / exact required observation |
|---|---|---|
| S01 schema | remove each key including nullable, add key, duplicate key, bool integer, depth/byte overflow | complete minimal and maximum-bound objects round-trip; pre-effect rejection has no files/child/lease |
| S02 identity | spoof env/client id, selection axis or worker grants | canonical conductor and job-bound worker identities; requested/observed model kept distinct, no inherited grants |
| S03 ownership | two synchronized claims, symlink alias, reused PID, stale generation release, unreadable header | one winner/one ownership refusal; separate worktrees/lineages pass; verified dead-owner recovery fences predecessor |
| S04 freshness | fetch failure/no ref movement, behind/diverged HEAD, wrong upstream/forge, age 60001ms, WIP instruction override | equal and policy-authorized ahead at 60000ms pass; preserved WIP; sync mock independently conforms to actual owner interface |
| S05 instructions | changed scoped instruction after preflight, malicious AAR, stale policy grant | exact delivered instruction digest plus allowed/forbidden tool effects under shared policy, read remains possible |
| S06 discovery custody | missing boot, hash-A/execute-B, changed anchor, fabricated Home consultation after HEAD failure | D-A31/D-A47/D-A48 clean witnesses, same-source CLI/MCP parity; races fail with no fabricated absence |
| S07 inventory | omit one CLI, registry, lever, feature, telemetry/review/skill/hook/infra/Mate/MCP route in turn; add new unclassified path | full tree-set classification and complete server pagination; each public route resolves schema/owner or explicit unsupported; no model path hints |
| S08 budgets | mandatory frame one byte over, escaped text, oversized card, cyclic/nonadvancing external cursor, 4097 entries | exact boundary caps pass; stable named details/cursors; source change invalidates; bytes/time/calls measured |
| S09 versions | v2/v3 connection offered as admission; Invalid params without catalogue comparison | old reader bytes preserved, v4 twelve-tool/CLI/resource parity; actual request/schema discrepancy diagnosed |
| S10 coverage | all disabled, missing DB, wrong job/rollout, expired lease, overdue source, mismatched definition | healthy empty queue is distinct; current explicit selection; required observations proven; no irrelevant session reads |
| S11 reuse | simultaneous ensure, owner crash after reservation, stale generation enqueue, one consumer close | one fenced owner; 10 consumers/one due read; restart preserves dedup; remaining consumers continue |
| S12 delivery | digest/ack/stdout-only, wrong thread/nonce/event, missing idle receipt, delayed >5s, disconnected transport | actual intended active and idle client receive unique event <=5s; monotonic latency, endpoint evidence and contiguous cursor |
| S13 reconnect | replay old connection receipt/Decision or skip pending event | new connection/generation, MCP/initial/challenge reproof, ordered pending delivery without duplicate presentation |
| S14 durability | kill after claim, fsync, rename and pointer update; disk full/corrupt handle | no admitted tool before verified durable pointer; idempotent partial recovery; immutable history, no fake attempt/evidence |
| S15 enforcement | disabled/malformed/timeout hook, native tool bypass, shell/MCP escape, untrusted overrides | exact allowed action succeeds unattended; forbidden action has zero effects; missing mechanism unsupported, no permission fallback |
| S16 revalidate | resume/compact/source/config/policy/monitor-loss/delivery-loss/expiry during queued effect | suspend before effect, full current gates then new epoch; old epoch cannot act; harmless optional gap remains typed |
| S17 optional prod/external | absent vendor, unreachable optional connector, action inferred from tool availability | dev startup independent of Symfony; optional route unavailable; actual Mate tools when available are named details with authority unchanged |
| S18 settlement | accepted startup used as worker verdict, conductor fed to collect/land/ladder, missing sweep evidence | canonical consumers handle/refuse variants; required findings imported once; terminal conductor needs ordinary settlement/model evidence |
| S19 lifecycle | crash/compaction/stop tries handoff/AAR publication | only explicit owner publication invokes existing custody owner; startup receipts remain operational evidence |
| S20 activation | old live client assumed reconfigured, wrong server artifact/config, no rollback evidence | pinned config backup/cutover through existing host owner; actual fresh-client proof after cutover for every enabled harness/profile and operation |

Expose deterministic synchronous checkpoints in admit_session at
`prepared,before-claim,after-claim,after-retain,after-client,after-coverage,
after-initial,after-receipt,before-commit,after-receipt-fsync,after-receipt-rename,
after-record-commit,before-release`. Each callback receives exactly
`{phase:Text,dispatch:DispatchID,epoch:Int}` and returns before continuation;
once per eligible phase, ordered as listed, no retries after fault. monitor's
ensure callback phases are `before-lease,after-reservation,before-lease-commit`.
Adapters expose `after-connect,after-listings,before-delivery,after-delivery`.
Callbacks are fixture-only injected trusted callables, no runtime plugin/config
mechanism. Independent fixtures block at each phase, inject mutation/crash, and
assert missing checks would fail the same test; stationary controls pass.

Implementation order: reconcile sync/findings and canonical execution/policy/
discovery custody owners; independent schema/fault tests and verified mocks;
extend catalogue and canonical record/monitor seams; compose quarantine/admission
and all revalidation consumers; independent review and combined suites; live
fresh-client fault/clean controls; versioned host cutover and repeated proof.
Activation must preserve/back up current host configuration and bind executable,
config, policy, adapter, schema, probe and mock revisions. Existing sessions are
unbound until explicitly revalidated; changing disk config is not reconnection.
Record pass/fail/unreachable separately for every enabled harness/profile/operation;
an unsupported combination remains disabled. Approval of this contract never
stands in for implementation, independent acceptance, activation or completion
of the owner's full onboarding request.
