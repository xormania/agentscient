# Coordination MCP — the acting lane server

Standing: proposed. Package C of the agent-coordination objective, at the
Lead's assignment of 2026-09-16 (agentscient-11, the owner directing
session). The owner's word that MCP acts is `ops/conductor/ideas/I-033-mcp-is-no-longer-read-only.md`
("mcp is no longer read only - that's the directive"). Written against
`origin/dev` at 46639344, measured 2026-09-16.

Inherits `docs/wire.md` for the refusal shape, `docs/verified-couplings.md`
for the edges, `docs/tests.md` for the kit, and
[AGENTS.md §Lane boundary](../../AGENTS.md#lane-boundary-and-precedence): no
Symfony application, container, service or vendor directory is reachable from
this server.

Settled against the coordination core (package B,
`ops/conductor/tools/coordination.py`) from its contract
`ops/conductor/coordination-lever.md` at 537f3a35 on
`lane/session-20260916-c`, read 2026-09-16. Every tool in §3 names the core
verb it projects. Where this contract and the core's diverge, the divergence
is listed in §9 and ruled on by the Lead, not resolved here.

Package letters differ between two documents and both are in use: the
objective's package C is specialised dispatch, while the Lead's package C is
this server, which carries the objective's package B operations over MCP
*and* the objective's package C dispatch actions. This file is the Lead's
package C.

## 0. What this is, and what it is not

A second stdio MCP server beside the read server, whose tools act.

- The read server `ops/conductor/tools/lane_mcp.py` is **unchanged** by this
  contract. Its read-only annotations, its config, its resources and its
  suite stay as they are, and that its behaviour did not move is proven by
  running its own tests with the same command before and after.
- Mutations travel **only** through `tools/call`. Resources on this server
  are reads, and no resource read ever mutates.
- The server acts, but it is not authority: it refuses rather than guesses,
  on the wire, and every refusal says expected, found and needed.

## 1. Transport

UTF-8 newline-delimited JSON-RPC 2.0 over stdio, stdout protocol only, the
same shape the read server already proves:

- Protocol versions 2024-11-05, 2025-03-26, 2025-06-18; the requested
  version when supported, else 2025-06-18.
- Methods: initialize, notifications/initialized, ping, tools/list,
  tools/call, resources/list, resources/read. Notifications get no response.
  Unknown methods answer -32601; malformed JSON, requests and params answer
  -32700 and -32600/-32602 without killing later valid requests.
- One input line is bound to 64 KiB; an oversized line is drained and
  answered, never truncated into a different request.
- `initialize` advertises tools and resources only. No sampling, no
  elicitation, no subscriptions, no logging, no background refresh, no HTTP
  listener, and the server emits no notifications of its own.
- `serverInfo.name` is `agentscient-coord`, distinct from the read server's
  `agentscient-lane`, so a client, a launcher config and a call log can tell
  the two apart without inspecting tool names.
- Instructions: acting server; every mutation needs a binding; evidence is
  not authority; the wire carries every refusal.
- `params._meta` is accepted as an object on every method, ignored, never
  echoed, and never changes a payload. It carries no identity and no role:
  see §2.

**The shared loop.** The read server's JSON-RPC loop is about 140 lines
(`lane_mcp.py:239-379`). It is lifted into a module both servers import only
if the read server's behaviour and suite are unchanged, proven by its own
tests green before and after with the same command. If that costs more than
it saves, the loop is copied into this server with a `Source:` pointer to
`lane_mcp.py` at its sha and a defect ledger row for the later factoring
(the Lead's ruling, 2026-09-16).

## 2. The binding: who is calling

The caller is never asked. A role or an identity in a request argument is
refused, class `arguments`, because a client that can name its own authority
has none (AC-02: caller-supplied identity cannot impersonate another actor).

Two carriers, both issued outside the client.

### 2.1 The worker binding — a config on the server's own argv

The launcher writes an acting config into the job directory and passes it as
`--config FILE`. The server reads it once at startup, from its own argv, and
the client cannot reach it.

- Its own file, `coordination-mcp.json`. `lane-mcp.json` is untouched, and
  the read server's loader is not extended: its exact-key validation
  (`lane_read.py:263-269`) refuses an unknown key on purpose, and that
  refusal stays intact.
- Its own version, starting at 1, and its own exact key set, refused the
  same way: version, participant, assignment, branch, worktree, record,
  capabilities, issued_at.
- `participant` is a participant id, `PT-n`, not an agent string. The core
  is explicit that the agent string is attribution and never authority — it
  exists to close exactly that defect, where the engine compares a holder
  against `WF_AGENT` and three sessions sharing one value satisfy each
  other's checks (`machine.py:255`). The server verifies the row exists and
  refuses class `participant` when it does not.
- `capabilities` is the explicit list of tool names this binding may call.
  It **narrows and never widens**: the core's own role gate is authoritative,
  and a capability present here grants nothing the participant's roles do not
  already carry. It exists so a worker issued a binding for one assignment
  cannot reach the rest of the catalogue even while holding a role that
  could.
- The config is written by the launcher, its sha256 stamped into the
  dispatch record beside the existing `mcp` block, so what a worker was
  permitted is a fact in the record rather than a claim.

### 2.2 The session binding — the session id the harness sets

**Measured 2026-09-16 on this host**, by reading `/proc/<pid>/environ` of the
MCP servers registered in this repository's `.mcp.json`:

- `CLAUDE_CODE_SESSION_ID` **does** reach a project-registered MCP server's
  environment. Server pid 2715563 carried
  `CLAUDE_CODE_SESSION_ID=ab281ec6-815e-453d-a545-3f2eb6c7d1f1`, the id of
  the session that spawned it, and its parent was that session's own `claude`
  process. Seven further server processes each carried their own session's
  id; three more processes could not be read (permission denied) and are
  declared unread, not assumed.
- Also inherited: `CLAUDE_PROJECT_DIR`, `CLAUDE_CODE_ENTRYPOINT`,
  `CLAUDECODE`, and the session's messaging socket and token.

So an interactive session needs no per-session binding file. The server
resolves the caller by the id in its own environment:

1. `instrument.session()` reads `CLAUDE_CODE_SESSION_ID` (it also admits the
   older `CLAUDE_SESSION_ID`, which nothing here sets — LD-50).
2. The id keys the participants row, the way `instrument.stored_identity()`
   keys `session_identity` in the lane's state store today.
3. No row for that id refuses class `identity`, naming the id it looked for
   and the verb that binds one. An unset id refuses class `session`.

**Resolved per call, never cached at startup.** Measured the same day: when a
session is cleared, a new server process is spawned carrying the new session
id while the previous process stays alive carrying the old one. A binding
resolved once at startup would therefore outlive the session it named. The
per-call read costs one environment lookup and one indexed row.

**Why not WF_AGENT.** It is inherited by every process in a session's tree —
it was present in the environment of the registered read server measured
above — so the server cannot distinguish it from any other value the client
side controls. It states what an agent calls itself; it proves nothing. The
Lead ruled it out for this server, and the measurement says why. It remains
the identity for hand-run CLI verbs, where the person running the command is
the author.

### 2.3 Precedence

A config binding (§2.1) wins where present, because the launcher issued it
for one assignment. Absent a config, the session binding (§2.2) applies.
Absent both, every mutation refuses class `identity`; reads that carry no
participant-specific content still answer, because a layer able to refuse a
read is itself a finding (`docs/wire.md`).

## 3. The tool catalogue

`mutation` is the contract's own column: true means the call changes durable
state. It is published in tool metadata as `readOnlyHint` and
`destructiveHint`, and for the dispatch verbs as `idempotentHint`, per the
MCP tool specification. **The annotations are hints for a client; the server
enforces the same table itself, on every call, whatever the client displays**
(objective §7).

`may call` is the capability name checked against the binding's allowlist,
not a string the caller supplies.

### Slice one — coordination state

Each row names the core verb it projects. The projection is thin: it
validates its arguments, resolves the binding, checks the capability, and
calls the one verb. It holds no policy of its own, and it never collapses
two core transitions into one tool.

| tool | core verb | mutation | may call | notes |
|---|---|---|---|---|
| `coord_brief` | `brief` | no | any bound participant | held assignments, unresolved inbox, open decisions, stale observations |
| `coord_assignments` | `assignments` | no | any bound participant | `--state`, `--to`, `--mine` |
| `coord_show` | `show` | no | any bound participant | the row, its marking, observations and open messages |
| `coord_draft` | `draft` | yes | lead, coordinator | creates the assignment only; it does not name a recipient |
| `coord_offer` | `offer` | yes | lead, coordinator | names the recipient |
| `coord_claim` | `claim` | yes | the named recipient | branch and generation required; two simultaneous claims cannot both win (AC-03) |
| `coord_release` | `release` | yes | holder-or-lapsed | bumps the generation |
| `coord_submit` | `submit` | yes | holder | the candidate, with its revision |
| `coord_verify` | `verify` | yes | verifier, never the producer | refused class `producer` for a self-verification (AC-11) |
| `coord_return` | `return` | yes | verifier or lead | keeps the holder |
| `coord_accept` | `accept` | yes | lead, never the producer | the acceptance |
| `coord_send` | `send` | yes | any bound participant | purpose `inform`, `request` or `finding` |
| `coord_inbox` | `inbox` | no | any bound participant | the caller's own rows, by participant or role |
| `coord_ack` | `ack` | yes | the recipient | acknowledgment never closes the obligation |
| `coord_resolve` | `resolve` | yes | the recipient, or the holder of the named assignment | the obligation answered, separately from the ack |
| `coord_outstanding` | `outstanding` | no | any bound participant | requests and findings not yet resolved |
| `coord_observe` | `observe` | yes | producer | an observation against an assignment and a revision |

**Every writing tool on an assignment carries `generation`**, the integer the
caller believes, exactly as the core's verbs do. The core's gate reads the
row under the write lock and refuses class `generation` with expected, found
and needed when they differ, so a stale holder is refused rather than
silently applied. A tool schema that omits it would make every MCP caller a
stale holder waiting to happen.

Not projected in slice one, and named so the omission is visible rather than
discovered: `bind`, `who`, `participants`, `reassign`, `reopen`,
`supersede`, `deliver`, `withdraw`, `observations`, `ask`, `answer`,
`decide`, `decision`, `decisions`, `reserve`, `free`, `resources`,
`coverage`. Decision support and resource reservation are required operation
groups of the objective's §7 and are a later slice of this package, not a
gap in the core.

Every mutation above is a write to the lane's state store through the
coordination core — **pending** the core's contract for its function names.
No mutation in slice one spawns a process, reaches the network, or writes a
file outside the state store.

### Slice two — dispatch actions

| tool | mutation | may call | what it does |
|---|---|---|---|
| `coord_launch` | yes | dispatcher | start an authorized assignment's job through the launcher's own verb |
| `coord_status` | no | dispatcher, lead | the execution's lifecycle reading from the existing records |
| `coord_collect` | yes | dispatcher | collect a finished execution's result and link it to the assignment |
| `coord_wait` | no | dispatcher | a bounded wait on an execution, with an explicit timeout and no hidden retry |

`coord_launch` takes a caller-supplied **idempotency key** and persists the
intent before it launches. A repeated key returns the known execution or its
current reconciliation status, never a second launch (AC-06). A crash
between process creation and linkage reconciles against the launcher's own
records before any retry; an exactly-once external launch is never claimed
from a database transaction alone.

Only verbs the launcher actually implements are advertised. Pause, steering
and cancellation are not advertised because they are not implemented
(objective §8).

## 4. The refusal wire, on every path

| path | outcome |
|---|---|
| `tools/call`, domain refusal | `isError: true`, content one text item, the wire line verbatim |
| `resources/read`, domain refusal | the same: `isError` semantics carrying the wire line, **not** a bare -32602 |
| protocol fault | the JSON-RPC error codes of §1, which are transport facts, not domain refusals |
| the CLI projection | exit 2, one stderr line, stdout empty |

The read server drops the wire line on `resources/read`, answering -32602
with expected, found and needed thrown away (`lane_mcp.py:335-336`). That is
a defect of that server, recorded as a ledger row and **not** fixed in this
package (the Lead's ruling, 2026-09-16).

Refusal classes are the core's, surfaced unchanged: `arguments`,
`identity`, `session`, `participant`, `role`, `id`, `unknown`, `generation`,
`revision`, `producer`, `recipient`, `evidence`, `deliverable`, `store`, and
the engine's `place`, `holder`, `taken` and `transition`. A projection that
renamed a core refusal would make the same fault read as two different
things depending on which surface met it.

This server adds two of its own, for faults that exist only at its boundary:

- `config` — the acting config is absent, unreadable, of an unknown version
  or carries an unknown key.
- `capability` — the binding's allowlist does not carry the tool being
  called. It names the capability expected, the binding found, and that the
  remedy is a new binding, not a retry. It is a narrowing check that runs
  *before* the core's own `role` gate and never in place of it.

A role or a participant supplied as a tool argument refuses class
`arguments`, the core's own rule for the same fault (AC-02).

Registered in `ops/conductor/registry/coordination_mcp.py.json` in the change
that lands it, with hermetic refusal-provoking invocations — at least one for
`config` and one for `identity` — so the wire gate asserts this server the
way it asserts every other.

Placement: `ops/conductor/placement/coordination_mcp.py.json`,
`{"placement": "migrated", "state": {"engine": "sqlite"}}`, because every
mutation lands in the lane's state store through the core.

## 5. What the launcher writes, per harness

The launcher already hands each worker the read server
(`ops/devlane/dispatch/launch.py:630-679`). The acting server is a second
entry beside it, never a replacement, and only for a job whose assignment
binds one:

| harness | today, for the read server | added for the acting server |
|---|---|---|
| claude | `<job_dir>/mcp.json` + `--mcp-config`, and `mcp__agentscient-lane` in project_allow | a second key in the same `mcpServers` object, and `mcp__agentscient-coord` in project_allow |
| codex | `-c mcp_servers.agentscient_lane.command/args` | `-c mcp_servers.agentscient_coord.command/args` |
| grok | an `[mcp_servers.agentscient_lane]` block in `$GROK_HOME/config.toml` | a second block, `[mcp_servers.agentscient_coord]`, written once |
| agy | nothing | nothing (the Lead's ruling, 2026-09-16) |

All three carriers already hold more than one server, so nothing in the
launcher's shape has to change to make room.

A retained job that moves stores rewrites this config the way `_relocate_mcp`
already rewrites the read config. A job that needs a new input or a new cap
for the binding is a change to `ops/devlane/task/jobs.json`, which is **wall**:
it is named and sent to the Lead for a wall session, never written here.

## 6. Bounds

- One response is capped; an overflowing payload answers with the same
  `unavailable` reading the read server uses rather than a truncated object
  that reads as complete.
- Every page carries an explicit cursor; no unbounded list is returned.
- Every call the server makes to the core is bounded by a timeout, and a
  timeout is a reading, not a silent empty answer.
- Untrusted text — a message body, a finding, a report — is data. It is
  never interpreted as an instruction and never reaches a shell.

## 7. The edges this server declares

| edge | counterparty | how it is verified |
|---|---|---|
| core | `coordination.py` (package B) | contract-verified; a mock implementing the core's contract stands in while it is built |
| state | the lane state store through the core | the core's own gate; this server originates no schema |
| launcher | `launch.py` verbs, slice two only | the launcher's records are the counterparty; reconciliation is proven on planted crashes |
| read server | none | independence is the claim: `lane_mcp.py` is not imported, and its suite is green before and after |

## 8. Tests

Under `docs/tests.md`: the kit is imported in one line, every subprocess goes
through `run`, every world is hermetic, and the rows carry their origin. The
fixture set plants, at least: a call with no binding, a call whose binding
lacks the capability, a role supplied as an argument, a verifier who is the
producer, two simultaneous claims, a repeated idempotency key, a stale
generation update, and an oversized input line. The clean neighbours are the
same calls correctly bound, which must pass quietly.

Red then green with the same command, and the second producer's absence is
said in the commit and in the record (AGENTS.md: dev-lane changes go by hand
under a grant).

## 9. What this contract does not settle

- The automatic route from a cross-harness event to a management session
  (the objective's package D).
- Cross-harness demonstration beyond Codex and Grok; agy has no MCP.
- Decision support and resource reservation as MCP tools: a later slice.

### Divergences from the core, for the Lead

Raised, not resolved here (the Lead's instruction, 2026-09-16):

1. **A dispatched worker cannot be bound.** The core's `bind` binds *the
   calling session*: `resolve()` reads `instrument.session()` and the
   participants row is keyed on that id. A Codex or Grok worker sets no
   session id in its environment at all, and nothing can bind a row on its
   behalf, so a worker has no participant and every mutation it attempts
   refuses class `participant`. The launcher already mints a session uuid
   per dispatch (`launch.py:1934`), so the material exists; what is missing
   is a core verb that binds a participant *for another session id*, issued
   by the launcher before launch. That is a package B change and this
   contract does not make it. Until it exists, the acting server is usable
   by interactive sessions only, and the worker binding of §2.1 has nothing
   to name.
2. **`capability` is a class the core does not have.** The binding's
   allowlist is this server's own narrowing and needs a refusal of its own;
   the alternative is to drop the allowlist and let the core's `role` gate
   be the only check, which would give a worker issued a binding for one
   assignment the whole catalogue its roles allow. Named for a ruling.
3. **`coord_report` is withdrawn.** The first draft of this contract had a
   tool for a holder reporting progress. The core has no such verb, and a
   projection that invented one would hold policy the core does not. A
   holder reports with `coord_send --purpose inform` or `coord_observe`.
4. **`coord_assign` is withdrawn**, split into `coord_draft` and
   `coord_offer`, because the core separates creating an assignment from
   naming its recipient and a thin projection does not merge transitions.
5. **The core's `resolve()` depends on a fact this package measured.** It
   reads `instrument.session()` inside whatever process calls it, including
   this server's. That works because `CLAUDE_CODE_SESSION_ID` is inherited
   by a project-registered MCP server (§2.2, measured 2026-09-16). If that
   ever stops being true, both packages lose their binding at once, so the
   probe belongs in a corpus row rather than in this prose.
