# Harness and CLI capability contract — first draft

Standing: PROPOSED. Born 2026-09-01 from the owner's inventory ask
("produce the inventory as the first contract draft - in fact -
inventory of everything is on the docket"); the triangle it anchors
is the contract-verified-mock idea in the intake. Rows are
RELIANCES, not catalogs: each declares a surface the lane actually
depends on, which is what the probe re-checks and a mock must
implement. Every row is true of one version on one day — the
isolation probe's doctrine governs the whole file. Status markers:
MEASURED (with the day's evidence), DOCTRINE (standing recorded
law), UNPROBED (relied on without a probe yet — a named gap, never
a silent one).

## Claude Code — the maximally capturable runtime

| reliance | why the lane needs it | status |
|:--|:--|:--|
| settings files and precedence (user, project, local) | law and guards installed from files we own | MEASURED 2026-09-01 (guard install; both hooks verified by jq) |
| lifecycle hooks: pre-tool, post-tool, stop | the lane's law firing natively: trailer guard, clipped-sweep guard, backtick guard, delegation refusal, context guard | MEASURED 2026-09-01 (each fired at least once today) |
| stop-hook wire: transcript_path, stop_hook_active, last_assistant_message; block-decision JSON; platform block cap | the context guard's whole mechanism | MEASURED 2026-09-01 (adversarial review verified fields against the live version) |
| permission rules plus the auto-mode classifier | the acting surface's gate; the classifier is stochastic call-by-call | MEASURED 2026-09-01 (same command allowed then denied; one deterministic allow rule) |
| project MCP registration (.mcp.json), read-only servers | the context-and-diagnostics plane ruling | DOCTRINE (workflow server precedent); probe UNPROBED |
| skills and commands directories; description injection | the pipeline's entry points for two of three harnesses | DOCTRINE (AGENTS.md records the reach) |
| cross-session messaging and idle notices | the baton; teammate coordination | MEASURED 2026-09-01 (delivery works; held-then-dropped failure mode measured once) |
| background tasks with completion notifications | every watch and dispatch wait today | MEASURED 2026-09-01 (dozens of cycles) |
| session transcript JSONL shape (assistant rows, typed content parts) | the context guard's fallback path; future mining | MEASURED 2026-09-01 (19.8MB parsed in 0.095s) |
| headless and SDK invocation | the capture path for driving this harness as a worker | UNPROBED here (dispatch drives the other harnesses; this one unexercised today) |

## Codex CLI

| reliance | why | status |
|:--|:--|:--|
| reads AGENTS.md cwd-upward at session start | the only law it sees — repo skills are invisible to it | DOCTRINE, load-bearing (AGENTS.md records it) |
| dispatchable headless via the pinned launcher, model set at dispatch | the pipeline's implementer and reviewer seat | MEASURED 2026-09-01 (multiple runs) |
| self-stamp may diverge from the model that ran | evidence law: record what ran, quote what it stamps | MEASURED 2026-09-01 (stamped one name, ran another, then aligned) |
| envelope harvested into the record's out/ | reading verdicts without scraping stdout | MEASURED 2026-09-01 (consistent all day) |

## Grok CLI

| reliance | why | status |
|:--|:--|:--|
| claude-compat: reads CLAUDE.md and AGENTS.md, sees repo skills | law reach and test-author seat | DOCTRINE |
| dispatchable headless via the pinned launcher | test author, adversarial reviewer, hunter | MEASURED 2026-09-01 (multiple runs) |
| envelope harvest GAP: final message lands on stdout, out/ stays empty | exit 0 with empty out/ must read as a finding, never a pass | MEASURED TWICE 2026-09-01 — proposed register row demands the launcher-side fix |
| owner customizations exist and are not to be probed | owner's standing rule | DOCTRINE — this row records a deliberate non-probe |

## gh

| reliance | why | status |
|:--|:--|:--|
| pr list --json returns every requested field on every row (isCrossRepository included) | the census's row validation and the stub's fidelity | MEASURED 2026-09-01 (reviewer-driven; the stub now models it — the first partially contract-verified mock) |
| exit 1 means any failure whatsoever | absence is proved only by a silent empty run | MEASURED 2026-09-01 (drove the probes-contract fix) |
| a full page at the listing limit is an unmeasured total | the false-total law | DOCTRINE (two contracts carry it); probe UNPROBED |
| checks output, watch mode; graphql thread resolution; merge with merge commit | the review loop's plumbing | MEASURED 2026-09-01 (used end to end) |

## git

| reliance | why | status |
|:--|:--|:--|
| trailer parsing requires the blank-line-separated final block | the attribution law's machine readability | MEASURED 2026-09-01 (CI red; local hook and CI gate diverge — a two-contract state awaiting agreement) |
| update-ref with empty old-value is create-only | retire's idempotence semantics | MEASURED 2026-09-01 (the stuck-retry fix) |
| worktree add is a lock grab; one owner per worktree | multi-session safety | DOCTRINE, measured 2026-08-21 |
| merge-tree --write-tree for merged-floor checks | the merged-tree rule made cheap | MEASURED 2026-09-01 |

## The docket

The owner's words widen this beyond harnesses: "inventory of
everything is on the docket." Sibling inventories queued for the
same triangle treatment, each a registry with a probe: the levers
and their verbs; the stores and their schemas; installed hooks;
dispatch jobs; concern rows; contract-and-gate coverage (which
promises have which checkers — the coupling census). Each lands as
its own contract draft; this file is the pattern's first instance.


## Conduct adapter interface

Adoption unit 1b, contract-only. The dated inventory above remains historical
reliance evidence; it does not admit installed versions today. The
[startup descriptor](conductor-start-plan.md#trusted-conductor-launch-descriptor)
and [shared policy](lane-policy.md) supply selection and authority. Adapter
mechanics belong to the existing harness owner; configurable Claude, Codex and
Grok implementations share this interface and never duplicate policy decisions.
No installed option spelling is certified by the synthetic examples below.

`compile_launch(selection, grants, transport, forwarded_tokens, operation)`
returns exactly `{argv, environment, reservations, capability, binding}` or a
wire refusal. It is deterministic and performs no launch, write, model selection
or grant derivation. `selection` uses startup's LaunchSelection (worker calls
use their task-owned role/job declaration); `grants` is the verified policy/task result,
never scope prose; `transport` holds verified executable/configuration, adapter
manifest, canonical paths and, for resume only, the retained session binding.
`operation` is launch or resume and must agree with the binding.

- `argv`: exact nonempty string vector beginning with the admitted absolute
  executable. No shell evaluation, shell joining or reparsing by a shell.
- `environment`: closed name-to-string map compiled from trusted declarations;
  no inherited PATH/config/environment overlays. Secret authentication transport
  remains under existing custody and is never a forwarded option or logged value.
- `reservations`: existing C2 transport declarations, distinct from model output
  grants; admitted scratch alone supplies its TMPDIR, never a parent grant.
- `capability`: required tuple from
  [C2 freshness](../devlane/dispatch/CONTRACT.md#capability-evidence-and-freshness),
  extended by grammar, tool-normalizer and MCP binding digests for conduct.
- `binding`: exactly `{invariant_sha256,argv_sha256,operation}`; digests use the
  startup canonical encoding. argv_sha256 hashes the complete final vector.
  invariant_sha256 hashes `{selection,grants,adapter,forwarded_tokens,mcp}`
  from verified transport, with adapter equal to the complete startup descriptor
  adapter object, excluding only the operation-specific session segment.

On resume, compare invariant_sha256 to retained launch evidence and require a
fresh matching resume witness. Recompile the entire vector and verify exact
launcher-owned session segment against retained session identity. A resume
argv digest normally differs from launch; it must equal its independently
compiled expected resume vector. Repeated resume with identical inputs must
produce identical bytes. Record both digests and the operation, not a false
claim that launch and resume vectors are byte-identical. Relocation permitted
by C2 rebinds canonical output paths through its custody checks; it cannot widen
grants, change source anchors or bypass conductor stationary-binding checks.

## Safe argv grammar

Each measured executable/version/operation declares a closed grammar in the
existing adapter declaration, digest-bound to its configuration. A declaration
has exactly `{schema:"adapter-argv/1",options:[Option,...]}`. Each Option is
exactly `{name,forms,values,repeatable}`: name matches `--[a-z][a-z0-9-]*`;
forms is a nonempty unique subset of `flag,split,equals`; values is null for
flag-only or a nonempty unique array of literal safe values for split/equals;
repeatable is boolean. Flag cannot coexist with value forms. Values are
printable ASCII, 1..128 bytes, must not start with `-`, and must come from an
independently reviewed harmless finite vocabulary. Names are unique. Empty
options explicitly allows only an empty forwarded vector. No permissive regex,
free-text value, path, URL, arbitrary number, positional argument or opaque blob
is admitted by this initial grammar. Safe value-bearing options remain usable.

Parse the caller's already separated tokens once, left to right. Match only
exact declared names and forms. Consume exactly one following token for split
and exactly the suffix after the first equals for equals. Count repetitions by
option identity across forms; refuse a second occurrence unless repeatable.
Reject short aliases, bundles, abbreviations, missing/extra values, bare `--`,
response-file forms and any token not consumed by a rule. Maximum 64 tokens,
each at most 256 UTF-8 bytes, total at most 8192 bytes; reject NUL/control bytes.
These are argv token bytes after the invoking shell, not its source quotation.
Preserve every accepted token byte-for-byte, in original order and form, as one
contiguous segment at the adapter's measured insertion point; no equals/split
conversion, deduplication, escaping, truncation or silent dropping.

The manifest must never admit options affecting permissions/approval/sandbox,
write roots, settings/config files, environment/headers/credentials, hooks/tools,
MCP servers, executable/plugins, working directory, session/resume, role/profile,
model/effort or launcher transport/output. Their aliases, repetition, indirect
config/response-file forms and future equivalents are reserved too. They belong
only to trusted compilation. Manifest review and verified mock/live probes must
prove semantic classification against the exact installed syntax; a name-based
blacklist alone cannot establish safety. Unknown installation syntax means no
measured grammar and prevents capability admission. A token rejected by an
available closed grammar is a deterministic refusal, not UNREACHABLE.

Synthetic grammar and admissible vector (fixture executable only):

```json
{"schema":"adapter-argv/1","options":[{"name":"--display","forms":["split","equals"],"values":["compact","plain"],"repeatable":false},{"name":"--quiet","forms":["flag"],"values":null,"repeatable":false}]}
```

```json
["--display=compact","--quiet"]
```

`["--display","plain"]` also passes and keeps its two tokens. Repeated display
across forms, `--dis`, `-q`, `--display=SECRET`, `@file`, `--config=x`, or trailing
positional text refuses. These examples grant no real vendor option.

The documentary checker counts two document-present positive vectors and seven
document-described negative vectors (the repetition and positional descriptions
are materialized as concrete tokens by the checker). It additionally synthesizes
one positive empty vector and two negatives, bare `--` and missing display value.
Thus its three positive and nine negative cases include synthetic additions;
none is live vendor evidence. A successor receipt must supply the checker, label
these origins and bind the actual checked bytes and revision/tree with UTC.
The earlier unstamped receipt remains historical evidence, not a current check.

Reject before prompt assembly, record/attempt creation, subprocess invocation or
logging raw input. Never interpolate rejected option names/values, raw vendor
parse errors or a hash of rejected secret material into diagnostics. Return
`conduct-argv: expected declared safe tokens; found invalid token at index N;
needed use the measured adapter grammar or run the independent doctor`, where
N is the zero-based numeric index (0 for a vector-level violation). Record only
admitted non-secret tokens and effective-vector digests. The credential-canary
acceptance scope is this input pipeline: prompt, stderr/stdout, diagnostics,
state/records and Git objects; it does not promise censorship of arbitrary
future model prose. Controlled environment credentials are never serialized.

## Capability admission and independent cases

Shared policy calls the normalized request interface in
[permission-surface.md](permission-surface.md#normalized-conductor-tool-interface).
An adapter must mediate every admitted effective tool surface before effects and
translate the shared decision without asking the user to approve it. Required
interception may be a verified hook or the closed capability relay below; a
missing required interceptor, malformed decision, tool bypass or unavailable
deterministic mediation makes that harness/operation unavailable for conduct.
Settings, CLI help and
synthetic argv alone are insufficient. Launch and resume need separate positive,
negative and prompt-observation arms in the
[live extension](probes-lever.md#conduct-live-diagnostics).

C2's G=D and actual A=D, source isolation, transport separation, freshness,
configured age limit and verified mock requirements remain unchanged. Conductor
restriction evidence additionally binds policy evaluator, normalizer, safe
grammar, effective configuration and actual MCP connection. Changed tuple means
stale evidence; missing measurement means unresolved; an observed failed control
is failed evidence. All prevent admission with an owning capability refusal;
UNREACHABLE describes a probe's inability to measure, not permission to run.

### Conduct capability identity encoding

For independent producers, `capability` above and a non-null live report
`identity` use this exact closed object. This encodes C2's required tuple for
conduct; it does not change worker output declarations or their admission.
All keys are required. SHA256, ID, LaunchSelection and digest encoding come from
startup. Text fields are nonempty printable ASCII, at most 128 bytes. Paths
are verified absolute paths from trusted transport, not caller locators.

| field | closed shape |
|---|---|
| harness | `{name:ID,version:text,executable:{path:absolute-path,sha256:SHA256}}` |
| adapter | `{revision:SHA256,mechanism:text,config_sha256:SHA256,grammar_sha256:SHA256,normalizer_sha256:SHA256}` |
| platform | `{os:text,sandbox:{name:text,version:text},filesystem:{name:text,alias_semantics:text}}` |
| role | literal conductor for this interface; no inherited worker grants |
| operation | launch or resume, equal to the report/compile input |
| policy | `{blob_sha256:SHA256,evaluator_sha256:SHA256}`; current admitted policy and evaluator closure |
| scope | `{source_reads:[absolute-path,...],source_write_denials:[absolute-path,...],outputs:[Output,...],limits:[text,...]}` |
| contracts | `{outputs_sha256:SHA256,tools_sha256:SHA256}`; exact owning contract bytes |
| mcp | the startup descriptor's exact mcp object |
| probe | `{revision:SHA256}` |
| mock | `{revision:SHA256,verification:{path:relative-file,sha256:SHA256}}`; retained passing verification under existing evidence custody |

Output is exactly `{kind:"file"|"scratch",path:absolute-path,operations:[Op,...]}`;
Op is `create,write,delete,rename,chmod`. The operations list is nonempty,
unique and sorted, and records the exact admitted operations, never implied
parent rights. File means one leaf; scratch means that subtree. All path/text
lists are sorted unique; outputs sort by path with unique paths. Empty lists
are explicit empty grants/limits, not unavailable analysis. The witness must
prove complete source coverage and the C2 grant equality; matching a list alone
is not containment proof. Unavailable tuple members make identity null with an
unreachable reason, never an invented version such as unknown. A measured
absence of OS sandbox may be described explicitly as name/version none, but
cannot satisfy a required OS boundary.

The live report supplies checked_at, results and digest-backed evidence;
retained mock verification must independently pass. Compare the current tuple
and scope before each operation under C2 freshness. Every descriptor adapter
field must equal the following capability identity field byte-for-byte:

| descriptor field | capability identity field |
|---|---|
| adapter.revision | adapter.revision |
| adapter.mechanism | adapter.mechanism |
| adapter.grammar_sha256 | adapter.grammar_sha256 |
| adapter.normalizer_sha256 | adapter.normalizer_sha256 |
| adapter.executable_sha256 | harness.executable.sha256 |
| adapter.config_sha256 | adapter.config_sha256 |

This covers both closed adapter objects completely, including the executable
digest at its harness-owned location. The descriptor digest bound by each tool
Request and the compiled invariant digest therefore cover the pinned normalizer
and mechanism as well as grammar, executable and configuration. A changed field
requires renewed matching evidence before launch/resume. The descriptor's policy
binding must resolve to this policy. Probe/mock changes invalidate the edge;
this encoding is not an extra capability registry or an authority record.

Independent test_adapter_argv.py/test_output_capability.py cases cover every
form, byte/order preservation, duplicates across forms, reserved aliases and
indirect channels, invalid manifests, secret canary non-persistence, all selection
axes, unsupported combinations, changed bindings and legitimate operation-owned
resume tokens. Existing dispatch admission cases remain the C1/C2 owners' duty.
Live observation format and diagnostic bootstrap are owned by probes-lever.md;
this contract does not create another witness authority or implementation.

## Codex sole-client relay — declared mechanism

Standing: contract-only, UNPROBED; no runtime admission. This resolves the supplied
native-prerequisites report `20260906T115721Z-plan-codex-52cd87`, mediation report
`20260906T123030Z-plan-codex-0fdfa5`, recording-scope ruling and security disposition
`20260906T124459Z-review-codex-ed048d`. Stock PreToolUse remains rejected as the
enforcement mechanism: reported fail-open parsing, missing write_stdin/code-mode
coverage and incomplete Bash execution context cannot satisfy the common API.
Approvals alone cannot close these gaps. The accepted recording ruling removes
the mediation report's mandatory vendor recording patch; it does not remove any
effect, credential or resume proof. See [record custody](permission-surface.md#relay-record-custody).
Historical reports keep their provenance and are not rewritten by this choice.

The selected mechanism is `codex-sole-client-relay/1`. Existing canonical
[launch.py](../devlane/dispatch/launch.py) owns admission, process creation,
supervision, settlement and the conductor record. Harness owns protocol
translation and isolated configuration; policy alone owns evaluate_tool. Native
`codex app-server --listen stdio://` has exactly one upstream client, the relay,
over launcher-created anonymous pipes. Native `codex --remote
unix:///ABS/conduct.sock` connects only to the relay's Unix WebSocket listener.
ABS is a canonical launcher reservation, never user input. There is no upstream
TCP/Unix listener and no sidecar client alongside the TUI. The relay neither
spawns workers nor implements a job/envelope engine: an allowed delegation calls
the pinned dispatch frontend and thus the existing canonical worker service.
All three processes are created and reaped by canonical launch, never by a
second executor or the Symfony application.

### Trusted relay transport

The common compile_launch signature, five return keys, normalizer/Decision
shapes and LaunchSelection axes stay unchanged. For this mechanism `argv` and
`environment` are the **app-server** vector and closed environment. Native TUI
argv/environment and relay runtime closure are verified launch-side transport,
not extra return keys, forwarded tokens or model tool parameters. Safe forwarded
tokens have one measured insertion point in the app-server vector; initial real
grammar is `{"schema":"adapter-argv/1","options":[]}`. The earlier display
example remains synthetic. Model/effort travel in sealed thread/turn settings,
not an invented app-server CLI option or a default model table.

Transport holds exactly `{schema,processes,endpoint,configuration,rpc,targets,
deadlines,resume}` for its relay specification; schema is `codex-relay/1`.
Startup strict JSON/canonical encoding applies; every object is closed and every
listed key required. This specification is passed by trusted in-process handle
or inherited read-only descriptor. No path/env toggle supplied by the TUI,
workspace or model can select it. Digest equality does not establish custody.

| member | frozen shape and owner |
|---|---|
| processes | `{server:Process,relay:Process,tui:Process}`; Process is `{executable:{path,sha256},argv:[string,...],environment:{name:string,...},cwd:absolute-path}`; executable/runtime/import closure is verified by launch, argv begins with its absolute executable; relay code is harness-owned and has no public launch entry point |
| endpoint | `{path:absolute-path,transport:"unix-websocket",clients:1,control:"inherited-unix-socketpair"}`; parent mode 0700, socket 0600, no symlink ancestors; peer PID/UID and launch-owned process handle checked; containment must defeat same-UID access through procfs, inherited FDs, aliases and socket races, modes alone are insufficient |
| configuration | `{server:{path,sha256},tui:{path,sha256},registry_sha256:SHA256}`; paths are sealed non-secret configuration leaves under reserved transport; registry hashes the complete effective direct AND nested tool declarations with their schemas |
| rpc | `{source_revision:string,schema_sha256:SHA256}`; source_revision equals the exact source pin below, digest covers the complete pinned protocol schema closure plus the [closed relay rules](permission-surface.md#codex-relay-protocol) |
| targets | sorted unique array of `{namespace:string,tool:ID,kind:"read"|"delegate"|"coordinate",target:ID,declaration:{path,sha256}}`; namespace is literal `conductor`; target owner supplies the closed argument/effect schema and executable/cwd/environment closure; no undeclared target is synthesized |
| deadlines | `{frame_ms:5000,request_ms:5000,effect_ms:60000,shutdown_ms:2000,pending:64,queue_bytes:1048576}`; positive integer constants, shorter remaining canonical wall wins; no timeout reset on replay or partial bytes |
| resume | null on launch, otherwise `{thread_id:string,session_binding_sha256:SHA256,receipts:[{path,sha256},...]}`; verified retained handles under existing attempt transport, sorted by path, not raw vendor resume data |

Process environments are closed maps of admitted non-secret synthetic values.
Authentication is a separately held server-only custody handle, never bytes in
this object. FDs are handed directly to their sole intended process and marked
close-on-exec elsewhere. Relay gets the two upstream pipes; TUI gets its terminal
and access only to the downstream socket; neither gets authentication handles.
One inherited anonymous Unix socketpair connects relay to canonical launch for
effect invocation/receipts and health; it is never exposed at a filesystem path.
Only launch creates the admitted frontend/lever subprocess and owns its receipt.
The [control frames](permission-surface.md#replay-and-effect-reconciliation)
carry validated common Request/Decision, not executable text or new authority.
Canonical launch owns signal/wall/spend/stream supervision for the entire group.
Relay readiness plus authenticated TUI attachment and verified native MCP
onboarding precede conversational input. Loss of any required child or channel
stops input, closes the listener, interrupts the thread, then terminates and
reaps all descendants within shutdown_ms; surviving descendants prevent success.
Raw server/TUI stderr is drained under a bound and filtered, never copied to lane
logs. Relay health/control events carry fixed codes, no raw frames.

The existing adapter.config_sha256 binds the canonical relay specification with
resume set to null, server/TUI config byte digests, registry and protocol digests;
adapter.revision binds relay/runtime code. No new descriptor/capability fields
are added. Both process vectors therefore enter invariant_sha256 through the
existing adapter object, while argv_sha256 continues to hash the app-server vector
alone. Resolve paths and compare all held bytes before creating reservations.
The resume segment is separately covered by startup's session binding digest;
it cannot change the invariant or select another thread. Reservations include
socket, pipes/control handles, sealed configs, credential mount, private vendor
history and existing receipts, disjoint from source/model output grants. They
grant no model write authority. The existing credentials-only build_home and
worker-only argv assumptions cannot implement this transport by ignoring fields:
until launch/isolation/record support it and its witnesses pass, refuse capability.
This declaration does not alter those owners' APIs or grant permission to edit
their implementation in this slice.

### Sealed registry and authentication

Host initialize uses experimentalApi=true; host thread/start explicitly supplies
environments=[], selectedCapabilityRoots=[] and only dynamicTools compiled from
the trusted targets. approvalPolicy=never and approvalsReviewer=user are sealed,
with restrictive filesystem/network permissions, no command allow rules, no
terminal restoration and no sandbox/approval bypass flag. Retain required ordinary
hook trust; hooks are not the enforcement boundary. An untrusted required hook
refuses; optional ambient user/project hooks and settings cannot be discovered.

Registry closure requires agents.enabled=false, multi_agent_v2=false and
multi_agent=false; disabling the last alone is insufficient. Disable apps,
plugins/install suggestions, browser/computer/image generation, web search,
memory, goals, token-budget/history-note tools and unnecessary environment
discovery. orchestrator.skills.enabled=false and empty capability roots close
skill sources. Only the exact bound read-only lane MCP catalogue, declared
dynamic targets and schema-pinned inert utility tools may remain. No unnamed
utility allowance: an empty utility list is valid, absent inventory is unresolved.
Model metadata may select code mode; any available wrapper must resolve every
nested call through this same registry, with no independent shell, filesystem,
network or agent authority. Forced direct/nested forbidden calls must be denied
at the measured resolution gate; omitted advertisements alone prove nothing.
Fresh, resumed and later turn registries/configuration must match the sealed
inventory. Any override, extension reload or unknown effective tool refuses.

Authentication stays solely in trusted app-server plumbing. TUI has a separate
credentialless home, no local auth/login fallback or access to vendor history.
Model-facing tools, relay target invocations, hooks, MCP and helper descendants
have closed credentialless environments and independently contained filesystem,
network and process views. Deny credential targets AND aliases, symlink/hardlink
paths, inherited handles, procfs and environment-file indirection; authentication
symlinks and shell_environment_policy alone do not establish this boundary.
Hooks may inherit the server environment and spawn outside the shell sandbox;
an enabled hook needs its own proven custody or the operation stays unavailable.
No real credential is copied into a diagnostic fixture. Failed custody requires
host containment or removal of the capability, never secret redaction after
exposure or permission widening. The relay's RPC protocol is not writable MCP;
the lane MCP read-only boundary and actual-client lane_start obligation stand.

### Research pins and verification frontier

Source baseline supplied by research: Codex `0.153.4`, target
`x86_64-unknown-linux-musl`, tag `rust-v0.153.4`, commit
`3d2ee51ca2d5db578f328aa75e20aa22c0197c9a`; reported executable SHA256
`56ef98ab4032d317ab26e9b5e5a175650717351edb16ed9cde0cb6d1734d62da`.
These are **reported source/version pins, not a local binary measurement**,
release-asset attestation, reproducible-build proof or successful live control.
The app-server, TUI and protocol closure must all match this pin. Experimental
API/config/schema or executable changes void evidence; do not track main/latest.

Versioned source locators (supplied research, not independent live witnesses):
[protocol methods/types](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/app-server-protocol/src/protocol/common.rs),
[dynamic transport](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/app-server/README.md),
[native remote TUI](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/tui/src/lib.rs),
[approval ownership/replay](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/app-server/src/outgoing_message.rs),
[registry construction](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/core/src/tools/spec_plan.rs),
[configuration](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/core/config.schema.json).
Source establishes a candidate route; only [independent mock/live acceptance](probes-lever.md#codex-relay-acceptance)
can establish the installed registry, sole-client ownership, native TUI usability,
credential containment, canonical delegation and crash reconciliation.
