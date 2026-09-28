# The permission surface — contract for /co-doc

The conductor acts through a stack of things that may refuse it: hooks,
permission rules, levers, the launcher, identity. Each layer below declares
its probe (an oracle that executes), its tier, and its remedy shape. The
doctor (`tools/co_doc.py`) is this contract's instrument: it runs every
probe read-only and reports findings with remedies. It is not the fixer.

**Lockout invariants** (owner + conductor, 2026-08-31):

1. Reads are never gated. Any layer able to refuse a read is itself a
   finding, per se.
2. Every refusal names its remedy; layers under this contract also name
   the doctor.
3. The doctor depends on nothing it diagnoses: stdlib Python, filesystem
   reads, and at most a `--help` subprocess. No launcher, no wrapper, no
   database writes. If everything else is wedged, it still runs.
4. The bypass is the owner, formalized: the doctor proposes; application
   of a remedy happens only with the owner present, one decision at a
   time. (The pre-ratified remedies table that would let it fix
   unattended is **ratification-pending** — until the owner ratifies it,
   v1 applies nothing.)

## Probes

| id | layer | asserts | tier |
|---|---|---|---|
| P-SET-1 | settings | every present settings file (`.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/settings.json`) parses as a JSON object; an absent file is reported absent, never as clean-by-silence | 2 |
| P-PERM-1 | permissions | every `permissions.allow` rule naming an absolute path resolves to an existing file — an allow whose target does not exist is an **inert grant**, the lockout that looks like permission | 2 |
| P-PERM-2 | permissions | no deny rule textually shadows an allow's target (heuristic, stated as such in output) | 3 |
| P-HOOK-1 | hooks | every configured hook's command file exists and is executable | 2 |
| P-HOOK-2 | hooks | every hook matcher names the tools it judges — a `.*` or absent matcher is a finding (the tool-guard lesson, agent-lab rule) | 2 |
| P-LEV-1 | levers | `dispatch.conf` parses; an explicit `LAUNCHER_PIN` or the sibling-default launcher, `dispatch.sh`, and `gate.sh` are each reported live or inert with the path examined | 2 |
| P-ID-1 | identity | `WF_AGENT`, when set, is `Name <address>`; unset is a note with the export line as remedy (reads need no identity) | 2 |
| P-WF-1 | record | `wf.py` exists and `--help` exits 0 | 2 |
| P-DB-1 | ledgers | `handwork.db` and `skills.db` open; open grants past TTL counted and named | 2 |

## Output contract

One line per finding: `[CLASS] probe-id: what was expected / what was found
— remedy: <one sentence>`. CLASS is the four-class taxonomy: Rejection,
Denial, Abort, Finding. A probe that cannot examine its layer reports
INVALID for that probe — an unperformed scan is never a clean result.
Exit 0: every probe ran, no findings. Exit 1: findings present. Exit 2:
one or more probes INVALID.

`--list-probes` prints every probe id above, one per line — the drift
check between this contract and the instrument.

## Remedies (proposed by the doctor; application ratification-pending)

| finding | proposed remedy |
|---|---|
| inert grant | repoint the rule at the resolving path, or complete the step that makes it resolve (e.g. the main checkout's move to dev); never widen |
| broad/absent hook matcher | scope the matcher to named tools; move general policy into `permissions` |
| missing hook file | remove the entry or restore the file — a hook that cannot run is config lying about enforcement |
| malformed settings | restore from the timestamped backup beside it, or fix the JSON; the doctor names the parse error |
| stale lever pin | repoint at the measured current target; record the measurement |
| stuck grants | settle or expire them with reason; a stuck grant is unfinished evidence |

A remedy that would **widen** any permission is never proposed for
unattended application, under any future ratification.

## Registration duty

Any new gate that can refuse the conductor registers here with a probe id
and a remedy shape before it arms, or it is an unproven gate. This table
and `co_doc.py --list-probes` must agree; their drift is itself a finding.

Source: owner doctrine 2026-08-31 (lockout fear, skill bypass, CDD) +
conductor design, this session. Ratified-by: pending owner for the
remedies-application clause; the diagnostic contract is design (conductor).


## Normalized conductor tool interface

Adoption unit 1b defines a future refusal surface; it does not arm the old
conductor guard, modify settings or add current doctor probe ids. Policy lives
once in [lane-policy.md](lane-policy.md#bootstrap-and-minimum-complete-activation).
Adapters translate requests and decisions; the independent doctor above remains
stdlib/read-only and does not depend on startup, policy loading or a vendor
session. A later gate implementation must register its diagnostic and remedy
with the existing doctor before arming; its read scan must work even when that
gate cannot start. Live checks belong to the
[separate diagnostic mode](probes-lever.md#conduct-live-diagnostics).

`normalize_tool(bound_context, native_request)` returns the closed Request
below or refuses. `evaluate_tool(bound_role, normalized_request)` returns the
closed Decision below. These are in-process interfaces, not MCP actions or
another CLI. bound_role is a verified handle to the launch descriptor, policy
binding and admitted tool declarations; the request cannot select it. The
normalizer is pinned adapter code. Never trust a model-supplied classification,
claimed effect list, command substring or tool display name as provenance.

Counterpart ownership: adoption unit 1a supplies the matching declaration of
`evaluate_tool(bound_role, normalized_request)` and its Request/Decision coupling
in [lane-policy.md](lane-policy.md). At review `20260906T110711Z-review-claude-e4968e`
that declaration was pending; the bootstrap citation alone established only
module ownership. Unit 1a closes the documentary edge by binding these exact
shapes. Executable coupling remains unresolved until independent verification;
neither the declaration nor this interface activates it.

Use the startup contract's strict JSON and canonical digest rules, with a
65536-byte request bound and no duplicate/missing/unknown fields. Request is
exactly `{schema:"conductor-tool/1",id:ID,binding_sha256:SHA256,kind,target,
arguments}`. id is allocated by the trusted intercepting adapter; binding_sha256
must equal the held conductor descriptor digest. kind is one of the following;
target and arguments are closed tagged variants, never arbitrary passthrough:

| kind | target | arguments and admitted interpretation |
|---|---|---|
| read | admitted read-operation ID | the target owner's closed read schema; anchored paths/refs only within source/custody grants |
| delegate | canonical frontend ID for dispatch/go/ladder | the frontend owner's validated structured request, transferred to the single worker service; no raw vendor execution |
| coordinate | admitted coordination lever ID | the lever owner's closed verb schema and grants; no implementation editing hidden in coordination |
| mcp-read | bound read-only tool name or resource ID | exactly its existing query schema or resource URI; same descriptor/config/session binding |
| forbidden | literal `implementation` | exactly `{reason:Reason}` |

Read/coordinate/delegate target declarations come from the trusted owner of
that existing lever, including its executable/import closure, allowed verbs,
argument schema, read scope and permitted effect contract. Missing declaration
refuses; this interface creates no registry and no wildcard shell allowance.
The `arguments` value is one strict JSON object verified by that target's schema
before evaluation; its bytes are retained only if admitted as non-secret input.
A model-supplied target label never bypasses resolving the actual executable or
native tool identity. Reads include canonical Git state/diff, contract/application
inspection within custody, board/status/record and handoff discovery. They require
no WF_AGENT, fresh permission grant or new owner prompt. A read outside custody
is not a permitted read. An unavailable read source stays an unavailable reading,
not an implementation-handwork violation. Coordination writes require the lever's
existing authorization; handoff/AAR publication remains owner-requested only.

Reason is exactly one of `direct-edit,git-mutation,shell-escape,raw-vendor,
in-session-agent,unknown-tool,malformed-request,binding-mismatch`. These are
fixed codes, never the original command, path or rejected value. Normalize
native edits/apply_patch, Git mutations such as apply/checkout/reset, direct
vendor or task vendor-launch paths and in-session agents to forbidden. Arbitrary
shell/interpreter programs cannot be represented as a trusted lever invocation.
A shell wrapper may normalize a single exact declared invocation only if the
adapter proves tokenization and the executed program/arguments/environment are
identical: no separators, pipes, redirections, command substitutions, eval,
wrappers, environment assignments or interpreter escape. Anything not provable
refuses shell-escape. The presence of dispatch.sh anywhere in text grants nothing.
Canonical dispatch may itself execute workers under its admitted effect contract;
the conductor cannot launch those vendor processes directly.

Decision is exactly `{schema:"conductor-decision/1",id:ID,
binding_sha256:SHA256,outcome:"allow"|"refuse",refusal:Refusal|null}`.
The id/binding must match Request and the held current binding. On allow,
refusal is null. On refuse it is exactly `{class:"conductor-tool",expected,
found,needed}` with nonempty strings chosen by the evaluator from fixed templates;
no raw request echo. Fixed field values must contain no semicolon, so the wire's
`; ` separators remain unambiguous. It serializes to the wire before effects. Example:

```json
{"class":"conductor-tool","expected":"declared conductor operation","found":"direct-edit","needed":"use canonical dispatch and run the independent doctor for gate diagnosis"}
```

The adapter consumes a matching decision once for that intercepted request only,
checks that native request/executable/cwd/environment and held binding have not
changed, then either executes that exact allowed invocation or blocks it. A
missing, late, malformed, duplicate or mismatched response fails closed before
execution. The adapter cannot turn refusal into permission prompts, automatic
approval, retry under weaker settings or an unrelated allowed request. Transport
failure is recorded as unavailable decision evidence, while the request is
blocked. No durable decision store is added; existing attempt transport retains
admitted non-secret evidence. Unknown/rejected native data never enters
lane-owned records; [relay record custody](#relay-record-custody) defines this
boundary separately from private model-generated vendor history.

### Acceptance duties and bounded refusals

Independent cases COND-HAND-P1/N1/L1 prove canonical delegation and necessary
coordination reads work, and forbidden direct-tool/Git/shell/vendor/sub-agent
attempts block before tree/index/ref effects. Include read commands containing
words such as apply without executing a mutation, and compound commands naming
an allowed lever; classify actual operations, not prose. COND-AXIS-N1 changes
harness, model, role, job role and profile separately. COND-EFFECT-N1 compares
only the declared effects of canonical coordination/delegation. Malformed hook
payloads and decisions, changed/replayed bindings, prompt attempts and missing
interception each prevent conduct admission. Repeat on resume and every supported
harness using the shared policy, with verified mocks and live observations.

These are adoption acceptance duties from the Daybreak input, not claims of an
introduced exploit in this documentary change. Existing lane-policy P1–P5,
N1–N10, R1–R5 and I1 remain binding. In particular shared inspection reads stay
permitted; the older unarmed guard's ban on hand investigation supplies no new
authority. Doctor findings propose bounded remedies; neither a diagnostic run
nor a passing observation can ratify policy or widen permissions.

## Codex relay protocol

This is the closed policy projection for
[codex-sole-client-relay/1](harness-capabilities.md#codex-sole-client-relay--declared-mechanism),
not a replacement normalizer/evaluator API. Native v2 types and their transitive
schema definitions are pinned to `3d2ee51ca2d5db578f328aa75e20aa22c0197c9a` under
[app-server-protocol](https://github.com/openai/codex/tree/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/app-server-protocol).
For every admitted method use exactly that named Params/Response schema,
recursively reject undeclared fields, and apply the narrower rules below.
Optional native fields retain their pinned absence/null semantics; they are not
extra fields in the all-required common Request/Decision. No permissive vendor
deserializer, generic JSON passthrough or future method inheritance is allowed.
The schema closure must be available and digest-verified before launch; a missing
type is unavailable capability, not a guessed shape. This is a frozen subset,
not a claim that every native TUI feature is supported.

### Frames and correlation

Upstream is newline-delimited UTF-8 JSON on private stdio; downstream is one JSON
object per Unix WebSocket text message (fragmentation reassembled under the same
bound). No binary messages, compression, JSON batches, BOM, duplicate members,
trailing values, NaN/Infinity, invalid UTF-8 or nesting above 32. Limit a logical
frame including its line delimiter to 65536 bytes, total queued bytes to 1048576
and pending requests to 64 across both directions. Partial frames expire after
5000ms from their first byte. WebSocket ping/pong/close are transport controls,
bounded by the same queue/deadline; they carry no policy authority. JSON escaping
may represent LF/tab in conversational text only; identifiers/methods reject
controls. Raw control bytes are invalid JSON; no control-containing path or
executable is admitted. Oversize conversation/output is a finite refusal/abort,
never truncation into an apparently valid frame.

The native envelope has no `jsonrpc` member. Closed variants are request
`{id,method,params}`, notification `{method,params}` (params omitted only where
the pinned notification type has no payload), success `{id,result}`, and error
`{id,error:{code,message}}`. Request/response id is a string of 1..128 printable
ASCII bytes or an integer in 0..2147483647; never bool, float or null. The relay
emits negative fixed integer error codes and fixed non-secret messages only;
never error.data or trace/telemetry extensions. Uncorrelatable malformed frames
close the channel without inventing an id. Method is a literal admitted below.
Params/result must pass the method's pinned closed schema and binding rules.

Maintain disjoint upstream-server-request, host-client-request and downstream
TUI id spaces, keyed by connection epoch plus typed id (integer 1 differs from
string "1"). Allocate fresh host ids and map responses back only to the pending
downstream request that originated them; never forward a TUI response upstream.
Server requests are answered only by the relay and never forwarded to the TUI.
An unknown, reused, duplicate or unsolicited response cannot consume a pending
callback. Consume each matching Decision once, before invoking its target; keep
retired-id tombstones for the epoch under the canonical session limits. Exhausted
id/event budgets abort rather than evicting replay protection. A downstream
reconnect requires a new supervised resume/epoch, not transparent replay.

### RPC and capability ownership

| direction / native method | admitted handling |
|---|---|
| TUI initialize, initialized | validate pinned InitializeParams/notification; relay terminates downstream handshake locally, uses its own identity and experimentalApi=true upstream; no caller capability negotiation changes the binding |
| TUI thread/start, thread/resume | accept only the single canonical launch/resume intent matching operation; relay constructs sealed native params from transport, checks every supplied security/selection field for equality and returns the one bound thread; arbitrary creation, path/history resume, fork or another thread refuses |
| TUI turn/start, turn/steer | native TurnStartParams/TurnSteerParams restricted to the held thread and current turn; only bounded text UserInput items, no attachments, file/image paths, skill mentions or capability locators; every model/effort/cwd/environment/approval/sandbox/config field is absent or exactly the sealed value; relay compiles effective settings, never silently drops a conflicting field |
| TUI turn/interrupt | native TurnInterruptParams for the bound active thread/turn only; interruption cancels pending work but cannot roll back a completed effect or delete its receipt |
| TUI thread/read, thread/loaded/list, model/list | pinned respective Params/Response types; only the bound thread and selected model are visible, no foreign history or filesystem locator; sanitize output before native display; model/list conveys no selection authority |
| other TUI requests | fixed error -32601; includes command/exec and stdin/resize, filesystem/process APIs, config read/write/reload, auth/login/logout/token refresh, approval responses, apps/plugins/skills installation, MCP/OAuth mutation, thread fork/rollback/archive, legacy turn APIs and unknown future RPCs |
| server notifications/responses | only pinned response matching a pending admitted host request, or thread/started, thread/status/changed, turn/started, turn/completed, item/started, item/completed, item/agentMessage/delta, turn/plan/updated, turn/diff/updated and error notifications for the held thread/turn; schema/binding validation and redaction precede display; no approval request masquerading as notification; other methods abort as protocol drift |

This list is exact, not a prefix allowlist. Optional TUI features outside it
receive a refusal; if the pinned TUI cannot converse and resume under this
subset, native-TUI acceptance is unresolved/failed and the mechanism is not
admitted. No direct app-server fallback is allowed. Locally synthesized display
responses must use the pinned response type; absent information is explicitly
unavailable, never a fabricated account or thread. Bootstrap lane MCP verification
uses the actual app-server connection and automatic lane_start, not a second
server/client substituted to make onboarding green.

All server request variants from the pinned ServerRequest union have a terminal
disposition. The names below also identify their Params/Response types in
protocol/common.rs; schema validation precedes handling. Approval field payloads
can be decoded privately but cannot confer authority or be echoed.

| server method | fixed relay response / ownership |
|---|---|
| item/commandExecution/requestApproval | CommandExecutionRequestApproval: `{decision:"decline"}`; no execution/session allow or amend-rules choice |
| item/fileChange/requestApproval | FileChangeRequestApproval: `{decision:"decline"}` |
| item/permissions/requestApproval | PermissionsRequestApproval: empty GrantedPermissionProfile, scope `turn`, strictAutoReview true; no filesystem/network grant |
| item/tool/requestUserInput | ToolRequestUserInput: `{answers:{}}`; never wait for a person |
| mcpServer/elicitation/request | McpServerElicitationRequest: action `decline`, content and `_meta` null under its pinned response type; no auth URL visit |
| item/tool/call | DynamicToolCall: strict capability path below, response exactly `{contentItems,success}` |
| currentTime/read | CurrentTimeRead: bound thread only, host clock encoded as pinned CurrentTimeReadResponse; unavailable clock gives -32000 then abort, never model time |
| account/chatgptAuthTokens/refresh | ChatgptAuthTokensRefresh: -32000, fixed `server authentication required`, abort; this mechanism uses server-owned auth, never externally supplied tokens |
| attestation/generate | AttestationGenerate: -32000, fixed `attestation unavailable`, abort; never fabricate attestation |
| applyPatchApproval, execCommandApproval | legacy ApplyPatchApproval/ExecCommandApproval: pinned legacy denied decision, then abort for unexpected legacy surface |
| unknown method | -32601, fixed `method unavailable`, then abort; cannot remain pending |

Malformed known params with a trustworthy correlatable id receive -32602 and
fixed `invalid request`, then abort; untrustworthy id/frame closes the channel.
Typed denials above must complete within request_ms=5000 (attestation failure
within 50ms, external-auth failure within 1000ms, both below reported native
timeouts). A stalled write, evaluator exception, missing/late/malformed decision,
disconnect, queue overflow or supervisor wall closes capability intake and
aborts the session; native disconnect behavior is not assumed to cancel pending
receivers. Launcher kills/reaps the group within shutdown_ms=2000 even when a
terminal response cannot be delivered. No retries with weaker settings or human
approval. Before the canonical first mutation, an unavailable mechanism uses
the owning capability/conduct-config refusal, exit 2; after claim/child creation,
loss is Abort 3 with sanitized partial evidence, as startup requires. An ordinary
refused tool call may complete with success=false while the session continues;
it is not an allowed effect or a successful diagnostic by itself.

DynamicToolCallParams is exactly `{threadId,turnId,callId,namespace,tool,arguments}`.
Native ids are nonempty printable ASCII strings at most 128 bytes, bound to the
held server thread/turn and observed call; namespace must equal `conductor` and
tool must resolve one exact trusted target row. Although native namespace is
nullable, null is refused by this projection. arguments must be one object
matching that target owner's closed schema, not arbitrary native JsonValue.
No model-supplied binding, request id, kind, executable, shell text, credentials,
cwd or environment override is accepted. Owner-declared anchored read parameters
are still permitted. Missing lever schema/closure/effect evidence refuses before
execution; no new generic dispatch argument schema is invented here.

The relay derives kind/target from that row and actual held execution handles,
allocates common Request.id, inserts the descriptor digest, then calls
normalize_tool and evaluate_tool with the existing bound context. Only a fresh
allow for that exact Request, unchanged target bytes/cwd/environment and live
binding invokes the canonical frontend or existing lever. MCP tools remain the
separate pinned read-only catalogue; dynamic delegation is not an MCP action.
Return only text content items `{type:"inputText",text:string}` in contentItems,
with boolean success. On refusal text is the fixed conductor-tool wire, success
false; on success text is the admitted target result, bounded and secret-free.
No raw exception, subprocess stderr or rejected argument is a result. Native
handler aliases and nested code-mode calls cannot select a different target.

Synthetic negative frame and terminal reply (not a live witness):

```json
{"id":7,"method":"item/tool/call","params":{"threadId":"thread-fixture","turnId":"turn-fixture","callId":"call-fixture","namespace":"conductor","tool":"unknown","arguments":{}}}
```

```json
{"id":7,"result":{"contentItems":[{"type":"inputText","text":"conductor-tool: expected declared conductor operation; found unknown-tool; needed use canonical dispatch and run the independent doctor for gate diagnosis"}],"success":false}}
```

The bound fixture thread/turn makes framing valid; the absent target makes the
call refuse with zero invocations. A positive fixture supplies an independently
owned exact target/schema and matching Decision; the empty arguments above do
not declare a usable real delegation capability.

### Replay and effect reconciliation

Relay-to-launch control uses the same strict frame bounds over the inherited
socketpair, with newline framing. Its closed variants are
`{kind:"invoke",native:{thread_id:string,turn_id:string,call_id:string},request:Request,decision:Decision}`,
`{kind:"result",request_id:ID,receipt:{path,sha256}}`,
`{kind:"health",seq:int}` and `{kind:"stop",reason:"protocol"|"timeout"|"disconnect"}`.
Health seq is contiguous from zero, sent every 1000ms; absence for 5000ms aborts.
Only invoke may cause a target operation. Launch verifies current binding,
the held native thread/turn and once-only decision/call association, and pinned
target handles itself, reserves
and durably records the owner operation identity, then invokes its one canonical
frontend/lever. No raw argv, generic spawn verb or supplied output path crosses
this channel. Launch resolves receipt paths under held transport custody; relay
gets only the admitted sanitized result. Invalid controls abort, not a fallback
to execution inside the relay. Both sides' executable closure and inherited FD
custody belong to the same admitted launcher/harness mechanism.

Every effectful admitted call has one stable association in **existing attempt
transport**: original descriptor/session binding, threadId/turnId/callId, adapter
Request.id, canonical admitted request digest, target declaration digest and
canonical dispatch/lever operation identity. Native ids are retained only after
their provenance and non-secret admission; rejected frames retain fixed codes
and a host-allocated numeric event index only. Correlation in memory may inspect
raw rejected input but never persists or hashes it into lane records.

Use closed receipt `{schema:"conductor-effect/1",binding_sha256:SHA256,
request_id:ID,request_sha256:SHA256,target_sha256:SHA256,
native:{thread_id:string,turn_id:string,call_id:string},operation_id:string,
state:"prepared"|"started"|"completed"|"uncertain",result:null|{path,sha256}}`.
Receipt is custody evidence, not authority or a separate decision database.
Write prepared durably before invocation using a canonical reserved operation
identity; started means that same operation was handed to its owner; completed
requires an independently verifiable owner result and retained sanitized reply
handle. result is non-null only on completed. Receipt writes are atomic and
durable before acknowledging their transition; no model can edit them. A failure
to retain preparation permits no invocation; a failure after possible invocation
is uncertain even if the vendor never received a response.

Serialize effect admission per session. An exact duplicate completed call gets
the retained reply under the new RPC id after binding/result verification; it
does not reevaluate or re-execute the consumed decision. A pending duplicate
shares no new decision, timer or effect. Reuse of call identity with changed
admitted arguments/target/binding aborts. After a crash (including effect success
before response, or before completion receipt), query the canonical owner's
operation identity/result. Completed means replay that result; active means
observe that same operation under the remaining bounded deadline; proven
not-started permits invoking **the same reserved identity** only through the
owner's atomic claim/idempotency guarantee. Mere record absence is not proof
that effects never happened. Unknown/conflicting state blocks further effects
and resume with fixed `reconciliation unavailable`; never mint another dispatch
or blindly repeat a coordination write. A lever without such identity and
reconciliation support is unavailable as an effectful target. Read retries need
fresh decisions and may not be substituted for missing write evidence.

Resume verifies the original invariant and fresh resume capability, sealed
config/registry, source/custody grants, policy, MCP and all effect receipts before
restoring vendor state or registering an attempt. Original native thread only;
no supplied history/path, fork, retained terminal or permission override. Restore
private vendor history only through trusted server custody, recheck effective
registry before a turn, and repeat actual-client onboarding. Vendor pending-call
replay does not restore authority: completed/uncertain states reconcile as above;
a newly admitted request needs a new current Decision. Missing receipt coverage,
unbound legacy history or config drift refuses continuation, leaving history
readable under its existing custody. No store migration or receipt backfill is
authorized by this contract.

### Relay record custody

The accepted supplied recording-scope ruling, confirmed by security disposition
`20260906T124459Z-review-codex-ed048d`, governs the earlier unqualified word
records. Rejected **launcher input** is stopped before prompt assembly, vendor
launch, output, diagnostics or attempt creation. Raw rejected/unknown native
payloads never enter lane-authored prompts, command output, relay logs, policy
receipts, attempt records or Git; only fixed non-secret refusal evidence survives.
Do not persist their hashes as a workaround. Forwarded native lifecycle/history
items containing rejected tool arguments must be suppressed or projected to fixed
refusal display before downstream output. The private server stream cannot be
used as a lane logging tee; telemetry consumes sanitized typed facts only.

Model-generated native call history already exists as vendor model output before
host validation. Its private persistence may support native resume and is not a
lane decision store. It grants no execution authority, is never published into
Git, and is not retroactively rewritten by the relay. The contract does not
promise censorship of arbitrary future model prose. This narrow distinction
does not permit forwarding rejected CLI input to that history, exposing credentials
to any capability, or copying raw vendor history into lane evidence. Thus a
mandatory vendor pre-persistence censorship patch is withdrawn for this mechanism;
only a newly declared broader privacy duty could require one. The concrete
remaining blockers are custody, registry/transport closure and effect
reconciliation, each with [independent acceptance](probes-lever.md#codex-relay-acceptance).
