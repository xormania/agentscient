# The coordination core — contract

Standing: proposed, package B of the agent-coordination objective, at
the owner's word relayed by the Lead session (owner, 2026-09-16: "hand
grant ok'd", relayed by agentscient-11 on 2026-09-16 with the six
decisions this page implements). Source of demand: the objective's §6,
durable coordination state, and §7, one domain implementation behind
two projections. Measured 2026-09-16 at `46639344`: the lane binds a
handoff thread (`handoff-lever.md`) and a deliverable lock
(`deliverable.py`) and has nothing that binds a participant, carries an
assignment between sessions, or keeps a message an agent still owes an
answer to.

Package B is this core and its CLI projection. The MCP action
projection is built over the same module by another session.

**The seam.** Every verb of the core is one function taking typed
arguments and the resolved participant, returning a dict, and raising
`instrument.Refusal` with expected, found and needed. The authority
checks — participant, role, holder, generation, revision, producer —
live in those functions, so they run whoever calls them: a projection
cannot reach the store around them, and a hook the MCP plane is blind to
is never where authority sits. Both projections are therefore thin and
neither holds authority of its own; the CLI verb parses argv, calls the
function and prints, and the MCP action does the same with a result
shape instead of a print.

**The tables.** The core is reached through `CORE`, keyed by the verb's
wire name, so a projection calls `CORE["return"]` by the string and
never imports a function named for a verb — `return` is a Python keyword
and a projection guessing `return` then `return_` is two guesses wearing
a refusal (ruled by the Lead session, 2026-09-16). The functions behind
the table are spelled `core_<verb>` and that spelling is private; the
table is the entry point. `VERBS` keys the CLI wrappers by the same wire
names, and `set(CORE) == set(VERBS)` is asserted by the suite, so a verb
cannot be added to one projection and quietly missed by the other.

A read verb takes the store connection and returns `{"store": "absent",
...}` when there is nothing to read, so "could not look" stays
distinguishable from "looked and found nothing"; the CLI prints `no
store` for the first and `no <things>` for the second.

## Conventions

Inherits `ops/conductor/instrument-conventions.md`: the refusal wire,
the four exit classes, the instrument shape, the identity rule and the
lint duty. Runs on the state engine (`machine-lever.md`): every row
lives in `state.db`, never in a file. Writing verbs require an identity
and a bound participant; reads require neither and never create the
store.

**Authority is enforced inside the core, never by a hook.** Measured by
the wall session, 2026-09-16: the hook engine cannot see MCP tool calls
from any server but serena, and the grant escape is inert on them. A
check that lives in a hook does not run when package C calls the same
function, so every role, holder, generation and revision check below is
a gate inside the function it guards. Hooks are feedback only.

## Ids

`PT-n` a participant, `A-n` an assignment, `M-n` a message, `E-n` an
observation, `DC-n` a coordination decision, `R-n` a resource claim.
`P-` is not used: it is the probe corpus row id the evidence shapes
already accept. `D-` is not used: it is the owner-decision register of
`decisions.py`, whose ids are `D-WORD-n`. A coordination decision is
not an owner decision and never enters that register; when one needs
the owner's word, the link is recorded and the register keeps its own
row.

## Participants

A **participant** is one session acting in the lane, not a model and
not a display name. The table:

    participants(id INTEGER PRIMARY KEY AUTOINCREMENT,
                 session_id TEXT NOT NULL UNIQUE, agent TEXT NOT NULL,
                 harness TEXT, roles TEXT NOT NULL, endpoint TEXT,
                 probe TEXT, bound_at TEXT NOT NULL)

`session_id` is `instrument.session()` and is unique, so two sessions
on one host are two participants; `agent` is `instrument.identity()`
and is attribution only. This is the defect the core exists to close:
the engine's holder is the agent string (`machine.py:255` compares
`row["holder"] == agent`), so three sessions sharing one `WF_AGENT`
value satisfy each other's holder checks. The participant is the
authority everywhere below; the agent string never is.

`resolve()` reads `instrument.session()`, refuses class `session` when
the harness set none, and refuses class `participant` when no row is
bound to it. **No verb takes the acting participant as an argument.** A
caller-supplied participant or role is refused class `arguments`, so
neither a CLI flag nor an MCP field can confer another participant's
authority (objective §7). Package C resolves the same way at its own
boundary.

`roles` is a comma-separated set drawn from `lead`, `coordinator`,
`dispatcher`, `worker`, `verifier`. A verb whose authority the bound
roles do not carry refuses class `role`, naming the roles held and the
role needed.

### A participant for a session that cannot bind itself

A dispatched Codex or Grok worker has no harness session id in its
environment, so `bind` — which binds the calling session — leaves it
with no participant, and every mutation it attempts refuses class
`participant`. Raised by the acting-server session against this contract
at `537f3a35`. The launcher already mints a session id per dispatch, so
the material exists.

`bind-for --session ID --roles R[,R] --for A-n` binds a participant to a
session id the caller names. Only a participant holding `dispatcher` may
issue one; another refuses class `role`. The row records `bound_by`, the
issuing participant, and `bound_for`, the assignment it was issued for,
and `participants` prints both, so a participant nobody dispatched is
visible as such. `bind` is unchanged and stays the interactive session's
verb.

Setting that id into the worker's environment is the launcher's half and
belongs to the MCP package's second slice, not here. It is set as
`CLAUDE_SESSION_ID`, the older key `instrument.session()` already admits
(instrument.py), so `instrument.py` does not change.

## The assignment machine

Places: `drafted`, `offered`, `held`, `submitted`, `verified`,
`accepted`, `superseded`. Declared as data in the tool and read by the
tests:

| transition | from | to | actor | evidence | failure | hold | gate |
|---|---|---|---|---|---|---|---|
| offer | drafted | offered | any | none | `offered` | keep | lead or coordinator |
| claim | offered | held | any | none | `taken` | take | the named recipient; the branch is in the lock; generation |
| release | held | offered | holder-or-lapsed | required (why) | `place` | clear | generation; bumps it |
| reassign | held | offered | any | required (why) | `place` | clear | lead or coordinator; generation; bumps it |
| submit | held | submitted | holder | required (a reading) | `place` | keep | generation; revision |
| verify | submitted | verified | any | required (a reading) | `place` | keep | verifier; not the producer; generation; revision |
| return | submitted | held | any | required (findings) | `place` | keep | verifier or lead; generation |
| accept | verified | accepted | any | required (a reading) | `place` | keep | lead; not the producer; generation |
| reopen | verified | held | any | required (the new revision) | `place` | keep | lead or coordinator; bumps generation; stales evidence |
| supersede | offered | superseded | any | required (the newer id) | `place` | keep | lead or coordinator |

Actor stays `any` wherever the authority is a role rather than the
hold, and the role is checked in the gate; the engine's `gate` callback
(`machine.py:291-292`) runs under the same write lock, before the
UPDATE, and its refusal rolls the whole transaction back
(`machine.py:338-343`). No change to `machine.py` is made by this
package. Widening `subjects.holder` to the participant id is a later
question and is recorded as an idea, not built here.

Submission, verification and acceptance are three separate places
because §11 requires three separate records. `return` keeps the holder,
so a returned candidate goes back to the same participant.

The side table carries what the subject row cannot, and its `id` is the
engine's subject id, the pattern `handoff.py:275-278` already uses:

    assignments(id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                outcome TEXT NOT NULL, requirement TEXT,
                scope TEXT, inputs TEXT, recipient TEXT,
                depends TEXT, revision TEXT, generation INTEGER NOT NULL,
                duty TEXT, thread INTEGER, branch TEXT,
                opened_by INTEGER NOT NULL, opened_at TEXT NOT NULL,
                superseded_by INTEGER)

`thread` is the nullable link to a handoff thread (`T-n`). A thread is
one item of a closing session's package and is not redefined here
(objective §3): an assignment names its recipient before the claim,
carries dependencies, a revision, a generation and an evidence duty,
and has places a thread does not. A claim reuses the thread's own
rule — the branch must be named in the deliverable lock
(`handoff-lever.md:68-72`) — and refuses class `deliverable`
otherwise. The lock stays file-backed and out of this package; the link
is the branch name.

## Generation and revision

The engine's compare-and-swap is on the place alone
(`machine.py:302-307`), so a reassignment that returns a subject to a
place it held before cannot by itself refuse the old holder. Two
columns close it:

- `generation` starts at 1 and is bumped, in the same transaction as
  the move, by `release`, `reassign` and `reopen` — every transition
  that changes who may act. Every writing verb on an assignment states
  the generation it believes; the gate reads the row under the write
  lock and refuses class `generation` with expected, found and needed
  when they differ. A stale holder is refused, not silently applied.
- `revision` is the candidate the work is against. `submit` states the
  revision it produced; `verify` refuses class `revision` when the
  observation it rests on names a different one. `reopen` sets a new
  revision and marks every observation of the assignment `stale`,
  keeping the old rows and their original scope (§11).

## Messages

Four facts, kept apart, because a transport receipt is not an answer:

- **queued** — `queued_at`, written in the same transaction as the
  state change that caused the message.
- **delivered** — `delivered_at` and `delivery_ref`, the transport's
  own receipt; for a Claude peer the `msg_id` the send call returned.
- **acknowledged** — `acked_at` and `acked_by`, the recipient's own
  ack verb. Measured 2026-09-16: no channels facility exists in Claude
  Code 2.1.273, so the route of record for Claude peers is native
  cross-session messaging, and for a cross-harness event a management
  session on a scheduled wakeup reading the inbox, its interval
  declared.
- **resolved** — a place, moved by the holder of the obligation, never
  by the ack.

The core never sends. Transports are adapters outside it; the core
records intent and receipt. The latency reading is `acked_at` minus
`queued_at`, both from the core, beside the transport's own stamp where
it gives one.

    messages(id INTEGER PRIMARY KEY, sender INTEGER NOT NULL,
             recipient TEXT NOT NULL, purpose TEXT NOT NULL,
             body TEXT NOT NULL, artifact TEXT, assignment INTEGER,
             decision INTEGER, reply_to INTEGER, queued_at TEXT NOT NULL,
             delivered_at TEXT, delivery_ref TEXT, acked_at TEXT,
             acked_by INTEGER)

The message machine: places `open`, `resolved`, `withdrawn`.

| transition | from | to | actor | evidence | failure | hold | gate |
|---|---|---|---|---|---|---|---|
| resolve | open | resolved | any | required (a reading) | `place` | keep | the recipient, or the holder of the named assignment |
| withdraw | open | withdrawn | any | required (why) | `place` | keep | the sender |

`purpose` is `inform`, `request` or `finding`. A `request` and a
`finding` are obligations and appear in `outstanding` until resolved;
an `inform` does not. `recipient` is a participant id or a role name,
so a finding can be addressed to whoever holds a role.

## Observations, decisions, resources

    observations(id INTEGER PRIMARY KEY AUTOINCREMENT,
                 assignment INTEGER NOT NULL, producer INTEGER NOT NULL,
                 requirement TEXT, execution TEXT, revision TEXT NOT NULL,
                 environment TEXT, observation TEXT NOT NULL,
                 artifact TEXT, applicability TEXT NOT NULL,
                 stale_reason TEXT, at TEXT NOT NULL)

`applicability` is `current` or `stale`; `execution` is a dispatch
record id, `artifact` a sha, `#N` or a record id. An observation is
never edited: `reopen` sets `applicability` and `stale_reason`, and the
row's own text and scope stay as produced.

    decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, asked_by INTEGER NOT NULL,
              question TEXT NOT NULL, alternatives TEXT NOT NULL,
              assignment INTEGER, counter TEXT, unknowns TEXT,
              choice TEXT, rationale TEXT, consequence TEXT,
              decided_by INTEGER, decided_at TEXT, asked_at TEXT NOT NULL)

Only a participant holding `lead` may decide; another refuses class
`role`. A decision with no `counter` and no `unknowns` recorded is a
declared gap on its brief, visible, not a silent pass (§11).

Resource claims need no new machinery: the engine's own hold is a
lease. Machine `resource`, places `free` and `held`; `reserve` takes
the hold with a ttl, `free` clears it under `holder-or-lapsed`
(`machine.py:227-233, 257-258`). The side table is
`resources(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
assignment INTEGER, note TEXT)`. A lapsed lease is evidence that a
reservation ran out, never proof that the previous process stopped
(§6); `reserve` after a lapse prints the previous holder and the
reconciliation the caller still owes.

## Instrument

`python3 ops/conductor/tools/coordination.py <verb>`:

| verb | effect |
|---|---|
| `bind --roles R[,R] [--harness H] [--endpoint E] [--probe TEXT]` | binds this session; prints `participant PT-n` |
| `bind-for --session ID --roles R[,R] --for A-n [--harness H]` | a dispatcher binds a participant for a dispatched worker's minted session |
| `who` | this session's participant and roles |
| `participants [--role R]` | one line per participant |
| `draft TITLE --outcome TEXT [--requirement REF] [--revision SHA] [--depends A-n,..] [--duty TEXT] [--scope TEXT] [--inputs REF]` | prints `assignment A-n` |
| `offer A-n --to WHO` | names the recipient |
| `claim A-n --branch B --generation N [--ttl MIN]` | takes the hold |
| `release A-n --why TEXT --generation N` | gives it back; bumps the generation |
| `reassign A-n --to WHO --why TEXT --generation N` | lead or coordinator; bumps the generation |
| `submit A-n --evidence READING --revision SHA --generation N` | the candidate |
| `verify A-n --evidence READING --generation N` | an independent verifier's pass |
| `return A-n --findings REF --generation N` | back to the holder |
| `accept A-n --evidence READING --generation N` | the lead's acceptance |
| `reopen A-n --revision SHA --why TEXT --generation N` | a changed candidate; stales the observations |
| `supersede A-n --by A-m` | an offered assignment replaced |
| `assignments [--state S] [--to WHO] [--mine]` | one line each, oldest first |
| `show A-n` | the row, its marking, its observations and its open messages |
| `send --to WHO --purpose P --body TEXT [--assignment A-n] [--decision DC-n] [--reply-to M-n] [--artifact REF]` | prints `message M-n queued` |
| `deliver M-n --ref REF` | the transport's receipt |
| `ack M-n` | the recipient's acknowledgment |
| `resolve M-n --evidence READING` | the obligation answered |
| `withdraw M-n --why TEXT` | the sender takes it back |
| `inbox [--unresolved]` | messages to this participant or its roles |
| `outstanding [--to WHO]` | requests and findings not yet resolved |
| `observe A-n --observation TEXT --revision SHA [--execution REC] [--artifact REF] [--requirement REF] [--environment TEXT]` | prints `observation E-n` |
| `observations A-n [--all]` | current observations, `--all` includes stale |
| `ask --question TEXT --alternatives TEXT [--assignment A-n]` | prints `decision DC-n` |
| `answer DC-n [--counter TEXT] [--unknowns TEXT] [--consequence TEXT]` | attaches what the brief needs |
| `decide DC-n --choice TEXT --rationale TEXT` | lead only |
| `decision DC-n` | the bounded decision brief |
| `decisions [--open]` | one line each |
| `reserve NAME --for A-n [--ttl MIN]` | takes a lease |
| `free NAME --why TEXT` | releases it |
| `resources` | one line per resource and its holder |
| `coverage [--requirement REF]` | requirement → assignment → candidate → observation → verification → acceptance or gap |
| `brief` | this session's bounded picture: held assignments, unresolved inbox, open decisions, stale observations |

`brief` is what a restarted or compacted participant reads to recover
its obligations (AC-12). Reads print `no store` and exit 0 when the
store is absent: looked and found nothing.

## Refusals

| refusal | fires when |
|---|---|
| arguments | an unknown verb or option, a wrong positional count, a missing required option, or any attempt to supply the acting participant or role |
| identity | a writing verb without an identity |
| session | a bind or a resolve with no session id in the environment |
| participant | no participant bound to this session; a named participant id with no row |
| role | a verb whose authority the bound roles do not carry |
| id | an id not of the form `PT-n`, `A-n`, `M-n`, `E-n`, `DC-n` or `R-n`, or of the wrong kind for the verb |
| unknown | an id the store does not hold |
| generation | a move whose stated generation is not the assignment's |
| revision | a verify whose observation names a revision other than the assignment's |
| producer | a verify or accept by the participant that produced the candidate |
| recipient | a claim by a participant the assignment was not offered to |
| evidence | a reading with no known shape |
| deliverable | a claim whose branch the deliverable lock does not name |
| store | a read while the store exists and cannot be read |
| place, holder, taken, transition | surfaced from the engine unchanged |

The evidence shapes are the ones already pinned: a sha of 7 to 40 hex,
`#N`, a dispatch record id `YYYYMMDDTHHMMSSZ-...`, or a `P-` corpus row
(`handoff-lever.md:73-75`).

## Where it sits in the session

- **Onboard** gains the `brief` section, so a session reads its
  assignments, unresolved messages and open decisions with its other
  current readings.
- **Close** requires `outstanding --to <participant>` to be empty
  before a session calls itself finished, the same duty `handoff.py
  held` already carries: an obligation this session accepted and
  neither resolved nor handed on is the hand-over failing, named.
- The handoff thread stays what it is. An assignment may name one; it
  never replaces one.

## State

`{"placement": "migrated", "state": {"engine": "sqlite"}}`. Rows in
`state.db` beside the other machines, never a file: this is state one
session changes and another must see now (`instrument-conventions.md`
§State). Test state is a testkit `World` with `XDG_STATE_HOME` pointed
at its own root, so no test touches the live host store.

The store is host-local (`machine-lever.md:42-45`). A second host is a
second store; coordination across hosts is not claimed by this
contract. If the host permits writes to `state.db` outside these
functions, this contract does not fence them — it records who wrote
what, and the marking is append-only under the engine's two triggers.

## Lint

Inherited; no per-file row. Registry row:
`ops/conductor/registry/coordination.py.json`. Tests:
`ops/conductor/tests/test_coordination.py`, on the test kit
(`docs/tests.md`). The standing rule is that a module's tests are
another producer's; this package lands under the hand grant instead,
one producer with the second producer's absence declared in the commit
and in the record (AGENTS.md §Ground rules, the dev-lane hand grant),
and independent review follows by dispatched Grok and Codex. Ruled by
the Lead session, 2026-09-16.
