# Managed sessions — contract (slice 1: one managed native participant)

Standing: proposed, slice 1 of
`.xor/in/multi-agents/agentscient-dev-lane-multi-harness-integration-plan-2026-09-22.md`
(§6, §9, §11 "Slice 1", §12, §13 I-01, I-02, I-11, I-12), at the owner's
word (owner, 2026-09-22: "i created two other claude sessions you can
use - contact them - you take lead - you're CO"). Written by the Lead
(PT-20, branch lane/session-20260922-af333fa2, grant 320) as the plan
artifact of the pipeline; the tests are written against this page by a
producer that did not write it, the implementation by a third. Baseline
dev `f81be8f1`; the proof adapted from is
`/home/scientdb/projects/poc/multi-harness-proof` at `a944f31` (MIT).

## Conventions

This instrument inherits `ops/conductor/instrument-conventions.md` and
runs on the state engine (`machine-lever.md`): its rows live in
`state.db`, never in a file. Writing verbs require `WF_AGENT`; reads do
not and never create the store. It runs from the repository root with
no Symfony, no `vendor/`, stdlib only. It never edits a global harness
configuration: every native home is the private profile
`profiles.py prepare-interactive` already makes.

## What slice 1 is, and is not

In: `doctor`, `start`, `status`, `attach`, `stop`, `export`; the run and
member rows; tmux ownership; profile composition through the existing
`prepare-interactive → check → run-interactive` path unchanged; the
adapter boundary with one adapter live (`claude`, the native TUI) and
the shared framing module tested offline; `ops/bin/conduct.sh`;
`ops/conductor/team.default.json`.

Out, declared: message delivery (courier native route, `join`,
`recover`, ingress readiness, the correlated startup exchange) is slice
2; the Codex app-server and Grok ACP adapters wait on the transport
projection in `profiles.py`, whose tests live under
`ops/devlane/hooks/tests/` and so are wall work for a separate wall
session; dispatch actions are slice 3. A verb this page does not list
refuses `arguments`. The readiness dimensions slice 2 owns print
`unmeasured` here, never `ok`.

## The shape

A **run** (`R-n`) is one started team: the team file it was read from
and that file's sha256, the tmux socket and session name it owns, who
started it. A **member** (`SM-n`) is one managed native participant of
a run: its name and harness from the team file, the roles the file asks
for, its generation (1 at first launch, +1 per replacement), the
launch identity the supervisor minted, the native identity the hooks
observed, the participant `PT-n` the store bound, the pid and the pid's
start ticks, the tmux pane, the worktree, the profile directory, and
its readiness. The engine owns place, holder and marking; the tool's
own columns sit in `session_run` and `session_member`, keyed by the
engine's subject id.

The member machine, declared as data in the tool:

| transition | from | to | actor | evidence | failure | hold |
|---|---|---|---|---|---|---|
| launch | reserved | launched | starter | the pane id and pid | `place` | keep |
| bind | launched | bound | starter | the observed native id and PT-n | `native` | keep |
| ready | bound | ready | starter | the readiness reading | `readiness` | keep |
| stop | launched, bound, ready | stopped | any | the process outcome | `place` | keep |
| lose | launched, bound, ready | lost | any | what was found missing | `place` | keep |

The run machine: `open → stopping` (stop) `→ stopped` (every member
stopped or lost, evidence the member list). A run with a member still
`launched` or `bound` is not stopped.

### The team file

`ops/conductor/team.default.json` is the default; `--team FILE`
names another; `.dev/coordination/team.json` is a gitignored local
override read only when present. Schema `agentscient-team/1`:

```json
{"schema": "agentscient-team/1",
 "run": {"name": "lane", "tmux": "agentscient"},
 "members": [
   {"name": "co", "harness": "claude", "roles": ["lead"]},
   {"name": "xo", "harness": "claude", "roles": ["coordinator"]},
   {"name": "dispatcher", "harness": "codex", "roles": ["dispatcher"]},
   {"name": "grunt", "harness": "grok", "roles": ["worker"]}]}
```

`name` matches `[a-z][a-z0-9-]{0,31}` and is unique in the file;
`harness` is one of `claude`, `codex`, `grok`; `roles` is a non-empty
subset of the coordination store's `ROLES`; an optional `executable` is
an absolute path. Nothing else is accepted (`team`). A model is never
named in the file. A role in the file is a request the store answers,
never a promotion.

### Readiness, eight dimensions

Each is one of `ok <evidence>`, `waiting <what>`, `refused <class>`, or
`unmeasured <owner slice>`:

| dimension | slice 1 reading |
|---|---|
| process | `ok pid=N start=TICKS` from `/proc/N/stat`, or `waiting`/`refused` |
| profile | `ok <profile dir>` when `profiles.py check` exits 0 on it; its refusal line otherwise |
| identity | `ok <session id>` when a participant bound to the launch id appears in the coordination store; `refused native` when the store shows a participant for this member under another id, or when the member's `pane.log` carries the profile's own `native` refusal line (the profile refuses a mismatched payload before any bind) |
| participant | `ok PT-n` |
| role | `ok <roles>` when the store's roles cover the request; `waiting grant PT-n --roles <missing>` otherwise |
| tools | `unmeasured slice 2` |
| ingress | `unmeasured slice 2` |
| response | `unmeasured slice 2` |

`ready` requires the first five `ok`, except that `role` may read
`waiting` when the request exceeds `worker` and no lead granted; the
member is then `ready` and the line says what it waits on. A living
pane, an existing profile, or a participant row alone never reads
`ready`.

### Identity, without impersonation

The supervisor mints a launch identity (a uuid4) and passes it to the
harness the way that harness accepts one (`claude --session-id`). The
native identity is what the profile's `SessionStart` hook binds through
`initialize` and `instrument.py`, read back from the coordination store
with `create=False`. The two are recorded separately and compared; a
mismatch is `refused native`, never overwritten. The supervisor never
carries a participant's capability, never binds on a member's behalf,
never grants: a role above `worker` is granted by the live lead, either
the operator's own lead capability in `COORDINATION_CAPABILITY` when
`start` runs from the lead's shell, or by the lead's own
`coordination.py grant` afterwards, which `status` then observes. The
first native bind in an empty store is a worker like every other
(`initialize` binds `worker` and the core never promotes); lead comes
only from a lead's grant or an owner-authorized recovery, and the
cold-start row asserts worker and no lead. A populated store is the
ordinary case and is never wiped.

### tmux ownership

One tmux session per run, on the socket `AGENTSCIENT_TMUX_SOCKET` or
`--tmux-socket NAME` (default: the operator's own server, shared; the
tests use a private one). The session is
`<team.run.tmux>-<R-n>` with the session option `@agentscient_owner`
set to the run id, one window per member named by the member, and
`remain-on-exit on`. Option operations target the exact session
component (`=name:`); session commands use their documented target.
A session of that name without the option, or with another run's id,
refuses `ownership`; the supervisor never sets, kills or attaches it.
Never `kill-server`. Output is captured with `pipe-pane` into the
member's evidence directory.

### The adapter boundary

`ops/conductor/tools/session_adapters/` holds one module per harness
and `framing.py`, the JSON-lines framing and request correlation
adapted from the proof's `rpc.py`. An adapter is a class with these
methods and no others the supervisor calls:

| method | returns |
|---|---|
| `argv(member, binding, launch_id)` | the fixed launch argv for the profile's `run-interactive`, never operator text |
| `observe_identity(store, launch_id)` | the native id the store shows for this launch, or `None` |
| `probe(executable)` | `{capability: "ok <reading>" | "unsupported <reading>" | "unmeasured"}`, with the installed version |
| `stop(handle, terminate)` | `stopped <how>` or `unresolved <why>` |
| `diagnostics(member_dir)` | the list of evidence paths it retained |

Slice 1 ships `claude.py` (native TUI; `probe` reports the version and
the channel capability as `unmeasured slice 2`) and `framing.py`. The
framing parser refuses, with a reading that names the line: a
non-JSON line, a response whose id matches no request, two requests
with one id, a result missing its id. Codex and Grok modules are
absent: `doctor` reads `missing adapter` for each codex and grok member
of the default team and so exits 1 in slice 1, the declared absence
slice 2 closes.

## Instrument

`python3 ops/conductor/tools/sessions.py <verb>`; `ops/bin/conduct.sh
<verb> …` is the same call from the repository root.

| verb | effect |
|---|---|
| `doctor [--team FILE]` | read-only; one line per check, `ok|missing|refused <check>: <reading>`: tmux (path, version), bwrap, the state store (`absent` is a reading), the coordination store and whether a lead is bound, python, each member's harness executable with its sha256 and adapter presence; exit 0 when every line is `ok`, 1 (Finding) otherwise |
| `start --member NAME [--team FILE] [--run R-n] [--worktree PATH] [--ready-timeout SEC]` | reserves the run (new unless `--run`) and the member, creates the owned tmux window, runs `prepare-interactive`, `check`, then `run-interactive` in the pane with the adapter's argv, waits up to `--ready-timeout` (default 120) for identity and participant; prints `started <name> SM-n as PT-n in R-n pane %N gen G` and the eight readiness lines; exit 0 when `ready`, 1 when the timeout lapsed with the member `launched` (the row stays, `status` reads it), 2 on a refusal before launch |
| `status [--run R-n] [--member NAME]` | read-only; per member: `R-n <name> SM-n <place> PT-n|- gen G pane %N|- process ok|gone` then the readiness lines; liveness is pid plus start ticks, never pid alone; `no runs` when the store has none; exit 0 |
| `attach --member NAME [--run R-n]` | execs `tmux attach-session` on the run's socket at the member's window after the ownership check; refuses `absent` for no such pane, `ownership` for an unowned session |
| `stop [--run R-n] [--terminate] [--drain SEC]` | moves the run to `stopping` and records the request; without `--terminate` it waits `--drain` (default 0) for members to exit on their own and prints each member's outcome, exit 1 while any is still running; with `--terminate` it signals only a pid whose start ticks still match the record, then the owned window, and records `stopped <how>` or `unresolved <why>` per member; a stale pid is `unresolved stale pid`, never signalled; exit 0 only when every member reads `stopped` |
| `export [--run R-n] --to DIR` | writes `run.json` (the run and member rows, readiness, the team file's sha256, tmux and process identity), each member's pane capture, `launch.json` and adapter diagnostics; a binding's `coordination_capability` and every `credential_environment` value are omitted; the first failure is kept and named, exit 1 for a partial export, `exported <dir> (N members, M files)` exit 0 |

Runtime evidence lives under the state root at
`sessions/<R-n>/<member>/`: `profile/` (the private profile),
`launch.json` (pid, start ticks, pane, launch id, argv with secrets
removed), `pane.log`, `stderr.log`. It is residue and export, never
state, and the placement file says so.

## Refusals

| class | when |
|---|---|
| `identity` | a writing verb without `WF_AGENT` in full form |
| `arguments` | an unknown verb or option, a verb slice 1 does not carry |
| `team` | the team file is malformed, names an unknown harness or role, or `--member` names no member |
| `tmux` | tmux missing, or the server on the named socket cannot be started |
| `ownership` | a tmux session of the run's name without `@agentscient_owner` equal to the run id |
| `profile` | `prepare-interactive` or `check` refused; their line in the found clause |
| `worktree` | `--worktree` is not a git worktree of this repository |
| `native` | a participant bound to the launch id shows another native id |
| `readiness` | `ready` asked while a required dimension is not `ok` |
| `authority` | a role above worker on a member whose start ran with a capability that is not the lead's; the remedy names `coordination.py grant` |
| `place` | a move from the wrong place (`start` on a member already `launched`, `stop` on a stopped run) |
| `absent` | no such run, member or pane |
| `store` | the engine's own refusals, passed through |

## Tests

`ops/conductor/tests/test_sessions.py` and
`ops/conductor/tests/test_session_adapters.py` on `ops/testkit`, run by
`ops/bin/suites.sh`. The world plants a fake harness through the kit's
registry, with `script=`, that reads the `SessionStart` payload its
launcher would send, runs the profile's `guard.sh SessionStart` so the
real `initialize` binds a participant, and then blocks until its stdin
closes; a second spec variant binds a different session id (the
`native` fault). tmux tests use a private socket in the world and skip
with the reason when tmux is absent. The fixture set, each a row with
an origin of this page: tmux absent (`doctor`); malformed team file;
an unowned session of the run's name; native id mismatch; role above
worker with no lead capability; the timeout with no bind; a stale pid
on `stop --terminate` (a pid the world reaped and reused); an
unreadable diagnostics file on `export`; a member already launched;
each framing fault. Clean neighbours: cold start on an empty store,
start on a populated store with a lead already bound, a second member
of the same harness with distinct profile, identity and pane, attach,
a clean stop, a full export. No live harness runs in the suite; the
live trial (plan §13 steps 1 and 7, I-01, I-02, I-11, I-12) is run by
hand and its readings go to probe rows under
`ops/conductor/handoff/probes/`.

## Placement and provenance

`ops/conductor/placement/sessions.py.json` declares
`"state": {"engine": "sqlite", "files": "profiles, pane captures and exports under the state root: residue and export, never state"}`;
`session_adapters/` needs no placement (no state). The commits that
adapt `Tmux`, `rpc.py` and the capture shapes carry
`Source: /home/scientdb/projects/poc/multi-harness-proof@a944f31`, and
`session_adapters/SOURCES.md` lists each adapted function beside its
origin. The proof's test-suite termination policy and its
`queue.Queue` are not adapted.

## Where it sits in the session

`doctor` first, then `start --member <name>`; `attach` shows the real
process; `status` is the board line; `stop` before the terminal is
closed, `export` before a claim about the run. Slice 2 adds the
courier route on the same rows; nothing here is rewritten for it.
