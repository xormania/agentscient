# The dispatch app — the dev-lane launcher

`launch.py` is the **policy** over the task app's `run.py` mechanism,
and the record it writes is built and validated by `record.py`.

Dispatch is a *composition* app. It reads the task app's job registry
(`ops/devlane/task/jobs.json`) and drives the harness app's isolation and
budget wiring (`ops/devlane/harness/isolation.py`,
`ops/devlane/harness/wires.py`). It was split out of the task app so it may
depend on both without the `task → harness` edge the cross-app import
contract forbids: a launcher that executes `isolation.isolated` and
reads `wires.budget` genuinely depends on `harness`, and the task app
must not. The allowed edges `dispatch → task` and `dispatch → harness`
are declared in `ops/contracts/imports.json`; the reverse would be a
cycle.

| file | job |
|:--|:--|
| `ops/devlane/dispatch/launch.py` | the §Dispatch policy: mint a snapshot, launch, supervise, collect, record |
| `ops/devlane/dispatch/record.py` | build and validate one dispatch record, one implementation per rule |

The rest of this file is the launcher's contract, written before the
launcher existed so its tests could be authored from it. No guide page
is carried here; this contract is the whole specification.

## Dispatch — the dev-lane launcher

`run.py` is the mechanism: snapshot, launch, supervise, collect, parse.
`launch.py` is the policy over it, and the **sole dispatch path for
dev-lane work**: it mints a snapshot from a named ref, keeps every
artifact outside the tree, applies the preconditions below as refusals,
supervises inline, returns the envelope, and writes a dispatch record
into a tracked directory on the branch. This section is its contract.
It is written before the launcher exists, so that the tests can be
authored from it and the implementation judged against it; invocation
examples therefore sit in plain fences until the file they name does.

Vocabulary: the **invoking repository** is the checkout the launcher
is run from; the **lineage branch** is the branch the work unit lives
on; the **job directory** is where one dispatch's snapshot and
artifacts live, outside every repository.

### Verbs

```text
launch.py <job> --harness H --model M [--effort E] --ref R
          [--lineage B] [--unit U] [--stage S] [--scope TEXT]
          [--input PATH]... [--follows ID]... [--override ID:REASON]...
launch.py status [ID] [--json]
launch.py resume ID [--prompt-file PATH]
launch.py collect ID --verify CMD [--reason TEXT] [--timeout SECONDS]
launch.py wait ID [--timeout S] [--interval S]
launch.py close ID
launch.py brief --check ID
```

- `<job>` names a `jobs.json` entry. A job never names a model; `--model`
  is the owner's choice at dispatch and is required.
- `--ref` is resolved to a commit in the invoking repository. `--lineage`
  defaults to the invoking checkout's current branch; `--unit` defaults
  to the lineage branch and groups records when one branch carries
  several work units; `--stage` is one of `plan`, `tests`,
  `check-tests`, `code`, `review`, `adjudicate`.
- `--scope` is the **one free field** the dispatcher may add, capped at
  **1024 bytes**, reproduced verbatim in the record. A job whose
  template has no `{scope}` refuses it.
- `--input PATH` copies a file into the job directory's `in/` and names
  it to the template as `{inputs}`; its digest enters the record.
- `--follows ID` names the records this dispatch was given and follows
  (plan → tests → check-tests → code → review → adjudicate). It is a
  dispatch-graph edge; it is **not** `context.prior`, which stays
  "findings from an earlier call".
- `--override ID:REASON` is accepted only for a refusal marked
  overridable below, and only with a non-empty reason.
- Identity: `WF_AGENT` in the `Name <address>` form, as for `wf`.
  Recording always needs one.
- Jobs root: `$DISPATCH_JOBS`, default
  `${XDG_STATE_HOME:-$HOME/.local/state}/agentscient/dispatch`. There is
  no flag for it; the record carries the path it used.

### Snapshot modes

A job declares one of two modes. They are mutually exclusive by
construction, and a job that needs both is refused.

**`whole`** — a fresh repository minted from the invoking one:
`git init`, then `git -c core.logAllRefUpdates=false fetch <invoking
repo> refs/heads/<lineage>:refs/heads/<lineage>`, then `FETCH_HEAD`
removed, then `checkout --detach <ref_sha>`. Guaranteed, and pinned by
test: `HEAD` equals `ref_sha`; the ref's full history is present, so
`merge-base` questions are answerable; `git remote` is empty;
`objects/info/alternates` does not exist; `logs/` does not exist; the
invoking repository's path occurs in **no byte** under `.git`; `git
status --porcelain` is empty before launch. It is not `git worktree
add` (that registers in the live repository's worktree list, which is
what the `live-target` refusal exists to catch) and not `git clone
--shared` (that leaves the source path in `alternates` and the reflogs
after `origin` is removed, and makes the source object store writable
by absolute path).

**`fileset`** — `fileset.snapshot` with `include` and `withheld`,
proved by `stage.prove` in both directions, and **no `.git`**: a
withheld file is one `git show HEAD:path` away in any snapshot with
history. Its manifest and diff live in the job directory, not at the
snapshot root. This mode lands after `whole`; until it does, a job that
declares it is refused by name.

`direct` jobs (`verify`) take the caller's fileset as today and declare
no mode.

### The job directory

```text
<jobs-root>/<id>/
  snapshot/      the tree, and nothing that is not the tree
  prompt.txt     the rendered brief, exactly the bytes handed over
  in/            copies of every --input, by basename
  out/           where a job writes a document deliverable ({out})
  raw.out        the harness's stdout, byte for byte
  stderr         the harness's stderr
  launcher.log    detached wrapper output, when launched with --detach
  breaker.log    the battery's stderr
  TRIPPED.md     written by the battery on a trip
  state.json     pid, pgid, session id, stream path, attempt
  exit           the harness's exit status, written last
  home/codex     minimal home for codex (auth.json only)
  home/grok      minimal home for grok (auth.json only)
```

Nothing the launcher, the battery or the harness writes for its own
bookkeeping goes under `snapshot/`. Two incidents sit behind that
line: report files at a snapshot root tripped the vocabulary wall
twice, and bookkeeping files counted as repository changes.

`id` is `<UTC stamp>-<stage>-<harness>-<6 hex>`.

### Template values

`render` receives, beyond `context` and `require`: `ref` and `base`
(shas), `diff` (path, or absent), `into` (the snapshot root), `out`
(the absolute path of the job's `out/`), `inputs` (the absolute paths
of the copied inputs, space-separated, in the order given), and
`scope`. A template naming a value the launcher did not supply is a
refusal at render, never a brief with a hole in it.
For harnesses whose argv carries no schema (codex and grok), the
rendered brief ends with the envelope JSON Schema. Claude continues to
receive the same schema through `--json-schema` instead.

### The child's environment

Applied to the harness process only, never exported by the launcher
for itself: unset `CLICOLOR_FORCE` and `FORCE_COLOR` (they beat
`NO_COLOR`; measured, 525 escape bytes in `gh` JSON); set `NO_COLOR=1
CLICOLOR=0 TERM=dumb PAGER=cat GH_PAGER=cat GIT_PAGER=cat LESS=FRX
CI=true GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true EDITOR=true
PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 LC_ALL=C.UTF-8`, plus
`WF_LANE=dev` and `DISPATCH_JOB=<id>`, plus whatever
`isolation.dispatch_env` returns. The working directory is `snapshot/`.

### Isolation, per harness

`isolation.isolated()` runs on every new launch; there is no argument that
turns it off, and a harness with no entry is refused. A relocated record
re-derives its home environment, flags, and stream store from that same
entry at the canonical current job path; a live recorded home or store at
a foreign path is refused. The stream store
is read from the same entry's `sessions` spec, because a relocated
`CODEX_HOME` or `GROK_HOME` relocates the stream and a launcher looking
in `~/.codex/sessions` would report "no stream" and run unsupervised.

| harness | isolation | read sandbox | write sandbox | containment | model that ran |
|:--|:--|:--|:--|:--|:--|
| claude | flags `--setting-sources project,local --strict-mcp-config --disable-slash-commands`; HOME untouched | `plan` | **not admitted** — no write row until the containment probe below has passed | policy | `~/.claude/projects/<slug>/<session-id>.jsonl`, `assistant` records, `message.model` |
| codex | `CODEX_HOME=<job>/home/codex` holding exactly `auth.json` | `read-only`; check-tests exception below | `workspace-write` | os | `$CODEX_HOME/sessions/Y/M/D/rollout-*.jsonl`, `turn_context.payload.model` (id and cwd from `session_meta`) |
| grok | `GROK_HOME` **and** `HOME` at `<job>/home/grok`, holding exactly `auth.json`; prompt via `--prompt-file` from the job directory | `plan` | `auto` | policy, until an owner-named `--sandbox` profile is added to the row | `$GROK_HOME/sessions/<url-encoded cwd>/<session-id>/summary.json`, `current_model_id`; read-role `head_commit` equals `snapshot.ref_sha`; write-role `head_commit` equals either that immutable ref or the actual local `HEAD`, which is always verified as its descendant; every other hash is rejected |

**Proposed Codex check-tests alignment, for owner review — not an
approved security guarantee.** The check-tests job remains role `read`,
but its Codex process uses the `workspace-write` sandbox label so it can
write its document and scratch files under the job `out/`, which is added
as a writable root; `TMPDIR` is a real, non-symlinked `out/tmp`. Before the
attempt the launcher strips Unix write bits from the snapshot as hardening,
but mode bits alone are not a hostile-process security boundary. After the
attempt, normal read-role settlement invalidates a changed HEAD or any
residual snapshot path. Other Codex read jobs remain `read-only`; this
exception does not provide generic file-output support to plan or
adjudicate. Live vendor containment proof for this path has not run.

For Claude, the snapshot's `.claude/settings.json`
`permissions.allow` and `permissions.deny` strings are carried on argv
and recorded under `harness.permissions`. Allow rules beginning
`Bash(gh `, `Bash(composer `, `Bash(git `, `Bash(php `, or
`Bash(bash ops/bin/` are dropped because they admit network access, an
interpreter, or worker-editable scripts; malformed or absent project
settings are declared `unresolved`.

`containment` says what stops a write role reaching outside its
snapshot: `os` when the harness's own sandbox enforces it, `policy` when
only the harness's permission mode does. It is recorded, not judged.

The session handle is minted at launch — `claude --session-id <uuid>`,
`grok -s <uuid>` — and codex's is read from `session_meta` once the
stream is found. A harness that ignores the minted id is recorded as a
mismatch, never silently accepted.

**Containment probe (admits a claude write row).** Two arms, both
dispatched, both must answer on their own terms: arm A runs the
candidate write mode with a brief that runs the snapshot's test suite
and edits a file, and must succeed at both; arm B runs the same mode
with a brief that writes a file at an absolute path outside the
snapshot, and must fail to. An arm that did not run is INVALID, not a
pass. The result is recorded verbatim in the adapter row's
`containment` entry and in every record that row produces.

**Behavioural observation, per harness**, recorded verbatim under
`harness.isolation.observed`: claude asks the model whether the
operator's probe phrase is in its instructions (unisolated YES,
isolated NO); grok reads `grok inspect` (unisolated ≥1 instruction
file, isolated 0); codex asks for the names of the skills available to
it, one per line, or NONE (unisolated arm lists ≥1 or the run is
INVALID because the machine cannot demonstrate the leak; isolated arm
must answer NONE). Each is true of one harness version on one day and
carries `checked_at` and `harness_version`. A record for a harness
whose observation has not run carries `observed: {"unresolved":
<why>}` — never a manufactured `false`.

### Refusals

Exit 3, before anything is minted unless the table says otherwise. The
text of each names what was expected, what was found, and what would
satisfy it. `override` marks the only overridable one.

| id | refuses when | expected / found / satisfy |
|:--|:--|:--|
| `identity` | `WF_AGENT` unset or not `Name <address>` | expected an identity in the `Name <address>` form; found `<value or unset>`; export `WF_AGENT='Your Model Name <noreply@vendor>'` |
| `live-target` | the destination is inside any entry of the invoking repository's `git worktree list --porcelain` or its common dir | expected a job directory outside every worktree of `<repo>`; found `<path>` inside `<worktree>`; set `DISPATCH_JOBS` to a directory outside the repository |
| `ref` | `--ref` does not resolve to a commit | expected a ref naming a commit in `<repo>`; found `<ref>` (`<git's message>`); commit the work, then name the commit — uncommitted work is never dispatched |
| `record-target` | the invoking checkout is detached, on `dev` or `main`, or on a branch other than `lineage.branch`; re-checked at close | expected the checkout on `<lineage>`; found `<branch or detached>`; run from a worktree of `<lineage>` (at close: the record file is left in place, nothing is committed, and `close ID` is re-run from the right branch) |
| `stale-base` (**override**) | `ref_sha` is not an ancestor of `lineage.branch` | expected `<ref_sha>` reachable from `<lineage>`; found it is not (`<lineage>` is at `<tip>`); name a commit on the branch, or `--override stale-base:<reason>` |
| `model` | no `--model`; or `--effort` on a harness whose adapter cannot pass it | expected a model — a job never names one and the launcher never defaults one; found none; pass `--model` (effort is forwarded through each harness adapter) |
| `isolation` | no `HARNESSES` entry, a credential missing, or a minimal home that is not empty | `isolation.NotIsolated`'s own text |
| `history-vs-withheld` | the job declares `withheld` and mode `whole` | expected one of history or withholding; found both on `<job>`; a withheld file is recoverable from `.git`, so declare `fileset` |
| `mode-unavailable` | the job declares a mode the launcher does not yet mint (`fileset`) | expected `whole`; found `fileset` on `<job>`; stage it by hand with `stage.py` and name the dispatch in the PR body until fileset mode lands |
| `write-role-unadmitted` | a write role on a harness whose adapter row has no write sandbox (claude) | expected a write row with a containment entry; found none for `<harness>`; run the containment probe and add the row, or dispatch the role on codex or grok |
| `scope-cap` | `--scope` over 1024 bytes, or given to a job with no `{scope}` | expected ≤ 1024 bytes on a job that takes a scope; found `<n>` bytes / a scope on `<job>`, which takes none; shorten it — a scope that needs more is a brief, and briefs are derived — or drop it |
| `caps` | an unknown wire, or `cap` and `total` (or `cap_out` and `out`) both given | `run.py`'s own text |
| `off-lineage-head` (at close or collect, write roles) | the snapshot's `HEAD` is not a descendant of `ref_sha` | expected `HEAD` to descend from `<ref_sha>`; found `<head>`; nothing is fetched, and the close record says so or collect refuses |
| `resume-store` | a codex or grok resume has no session store in either its live or archived home | expected the store for `<session id>` under both named paths; found neither; resume a job whose store survived, or launch afresh |
| `collect-role` | `collect` names a read role | expected a write role; found read; collect only a failed write job |
| `collect-state` | `collect` names a job with no failed or tripped attempt, a result without residue, or a result already collected | expected an uncollected write job with a failed attempt and residue; found the recorded state; use the normal result or name the recoverable job |
| `verify` | the collection verification exits non-zero or reaches its wall | expected the named command to exit 0 within the recorded job wall or a larger `--timeout`; found its exit or timeout and stderr tail; fix the residual tree and rerun collect |
| `wait-target` | `wait` names no record | expected a record for `<id>`; found none; name a launched dispatch |

Runtime outcomes that are not refusals, and still produce a record:
`unsupervised` (no session stream under the isolated store within the
grace period, 120 seconds until measured, while the process lives →
terminated, `invalid`), `harness-cli`, `envelope-parse`, `timeout`,
`trip` — as `run.py` returns them today. An override on any id not
marked overridable, or with an empty reason, is itself refused.

### Collect

Write roles: the snapshot's `HEAD` must descend from `ref_sha`; it is
fetched into the invoking repository as `refs/dispatch/<id>` with
`--no-write-fetch-head`; `changed_paths` is `git diff --name-only
ref_sha head --` (the same endpoint semantics without an option-sensitive
record-sourced range); `residual_paths` is a human rendering derived from
`git status --porcelain=v1 -z` records in the snapshot. Read roles: `head`
must equal `ref_sha`; a non-empty
`residual_paths` is recorded; a changed head or non-empty residual makes the
envelope invalid.

Residual settlement exempts only declared cache artifacts: `.ruff_cache`
markers and extensionless keys at its root or under one numeric version
directory; pytest's three markers and its built-in `v/cache/{lastfailed,
nodeids,stepwise}` values; mypy's two markers, `missing_stubs`, and its named
JSON, fixed-format or SQLite artifacts under one numeric Python-version
directory; and `.pyc` files below `__pycache__`. Unknown layouts and source
files under any cache-named directory remain residual. The same classifier
selects both `residual_paths` and every path preserved in `residual.patch`,
including ignored files, binary files, deletions and both sides of renames;
there is no broader patch exclusion. These exemptions are a named residual
policy, not evidence that bytecode, caches, or other data written by a
same-UID worker are trustworthy, and not a strong filesystem-isolation
guarantee.

Git path authority remains NUL-delimited bytes through classification and
patch selection; C-quoted display is output only and is never parsed back.
Rename and copy records retain both source and destination. Before settlement
mutates an index, every path must round-trip through the filesystem encoding.
The temporary-index `git add` uses `--literal-pathspecs` plus `--`, so leading
dashes, wildcard characters, and `:(...)` syntax are filename data and cannot
select unchanged collateral paths. The invoking and snapshot indexes remain
untouched.

`collect ID --verify CMD [--timeout SECONDS]` is the recovery path for a
write job with residual files and any tripped or non-zero attempt, including
one later resumed successfully. It runs the verification in the snapshot
with an isolated home and no ambient operator variables, under the recorded
wall or a larger explicit wall, verifies that `HEAD` still descends from
`ref_sha`, commits the residual with the
harness's message and running-model attribution, advances
`refs/dispatch/<id>`, retains `residual_patch`, and records
`result.collected {at, by, head, verify {command, exit: 0}, reason}`.
Every failed precondition leaves the snapshot commit, ref, and record
unchanged.

### The record

One file per dispatch at `.dev/records/dispatches/<id>.json`, written
at launch with `status: launched` and no `result`, finalized at close,
and committed on the lineage branch as one commit containing only that
file — `git commit --only -- <path>` — with the message `dispatch:
record <id>`, `Source: generated: ops/devlane/dispatch/launch.py`, and
`Co-Authored-By: $WF_AGENT`. `record.py` builds and validates it, one
implementation per rule as `envelope.py` does; a record that fails
validation is never committed and the launcher exits non-zero naming
the field.

Fields, in this order:

```text
id, lane ("dev"), stage, unit, lineage {branch, base_sha}, follows [ids],
job, role (read|write), dispatched_by, at {launched, closed},
snapshot {mode, ref_name, ref_sha, behind_tip, root},
harness {name, version, permissions?,
         isolation {mechanism, flags | env, home?, auth_files?, store,
                    observed {operator_config_present, evidence,
                              checked_at, harness_version}
                    | {unresolved}},
         sandbox, containment (os|policy), argv},
model {requested, effort_requested, effort_argv, ran, read_from},
session {id, stream, stream_sha256_at_close},
brief {template {path, sha256}, scope, inputs [{path, sha256}], sha256, bytes},
caps {..., source},
overrides [{refusal, reason, by}],
attempts [{n, launched, ended, exit, tripped}],
result {head, changed_paths, residual_paths, residual_patch?, envelope,
        collected? {at, by, head, verify {command, exit}, reason}},
status (launched|closed|died)
```

- `model.requested` is the alias the owner chose; `model.ran` is what
  the harness's own stream says, read from `read_from`; with no stream
  it is `null` with a note, and never the alias copied over.
- `brief.sha256` is the digest of the exact bytes handed to the
  harness; `brief --check ID` re-renders from `jobs.json` at `ref_sha`,
  the recorded scope and the recorded input digests, and compares.
- `behind_tip` is `rev-list --count ref_sha..lineage`, a fact, not a
  judgement.
- `caps` come from `wires.py` for the role; a per-launch change is
  recorded with its source.
- `caps.timeout` (seconds) resolves in one order: `DISPATCH_TIMEOUT`
  from the invoking environment, else the job's own `caps.timeout` in
  `jobs.json`, else 900 — and `caps.timeout_source` names the layer
  that answered: `DISPATCH_TIMEOUT`, `job`, or `default`. The job
  layer exists because runtime is a property of the job, not of the
  session that happens to launch it: author-tests proves every
  assertion red before green, its successful runs measure p50 928s
  against the flat 900s default, and five of seven wall-kills in the
  record store were that class, each launched bare after the session
  that knew the `DISPATCH_TIMEOUT` compensation had ended (finding:
  20260901T004909Z-tests-grok-3a7479).
- `result.envelope.spend` is filled by the launcher from resolved
  `session.spend`; the harness's zero placeholder is never the record's
  measured figure. An unresolved spend begins `UNREACHABLE:` and names
  the store roots examined.

**The permitted delta to the invoking repository**, and nothing else:
one new file at the record path; one commit containing only it, on the
current branch, which equals `lineage.branch` at launch and at close;
for write roles, one new ref `refs/dispatch/<id>` and its reflog line.
The index and worktree are otherwise untouched, `FETCH_HEAD` is not
written, and every other ref is byte-identical before and after.

What makes the record expensive to fake after the fact — not
impossible, and the owner is the backstop: the brief digest re-derives;
`ref_sha` is a full object id that must resolve to its exact commit in the
bound snapshot and must be reachable from the branch; `result.head` must descend
from `ref_sha` and is a fetched commit with its own dates and trailers;
spend and `model.ran` must agree with a stream in the harness's own
store; and the record is a commit, so changing it is a diff.

### Watching, and picking up after a kill

The launcher prints `record: <id>` as soon as the launched record is
written. `state.json` carries `pid`, `pgid`, the
session id, the stream path and the attempt number; `exit` is written
last. `status` reports `running` (pid alive), `finished` (exit file),
`tripped` (`TRIPPED.md`), **`DIED`** (pid gone and no exit file — never
reported as finished), `unlaunched` (refused before launch). `close ID`
finalizes and commits a DIED job's record as `invalid`.

`wait ID` polls that record until `closed` or `died`, writes poll lines
to stderr, and prints one terminal summary. A clean, untripped, schema-
valid close exits 0; another terminal result exits 1; the wait wall
exits 2.

`resume ID` relaunches in the same snapshot directory — grok scopes
sessions by cwd — with `claude -p -r <id>`, `grok -r <id>`, or `codex
exec resume <id>`, clears the previous exit and trip markers before
registering, appends output rather than truncating it, re-arms the
battery, and appends an `attempts` entry. A job the battery tripped
resumes only with a changed cap or a stated reason, recorded.
Before a codex or grok resume the archived session store is restored to
the harness home, then moved forward again after the attempt. A failed
resume cannot downgrade the prior stream, model, spend, or cause, and
every completed attempt commits the updated record.

### Proposed lane-policy coupling — inert until complete activation

[Lane policy](../../conductor/lane-policy.md) owns the profile ceiling,
protected authority, dependency exclusions and policy acceptance requirements;
its [proposed data](../../lane-policy.json) lives at the fixed tracked path
`ops/lane-policy.json`, bound to an owner-admitted Git ref and byte digest.
Environment, laneconf, candidate output and prose cannot relocate authority
or reclassify work. Launch/task retains ownership of job output, requested
scope, role and adapter declarations. Policy consumes outputs if present as
an intersection term; absence adds no root and never falls back to profile
roots. A read role retains an immutable snapshot, even with declared,
adapter-isolated external `out/` writes. No jobs schema is introduced here.

Future records bind nested `brief.policy` and launcher-produced `result.policy`
as specified by that contract; `lane` and `WF_LANE` stay infrastructure markers.
The minimum complete activation checks fresh launch, settlement (including
write-resume settlement), write-resume before attempt/marker/store mutations,
and collect both before and after verification, before commit/ref publication.
It consumes existing `_residual_entries`, including ignored-file enumeration
and the existing narrow cache exemptions. Land and ladder must independently
refuse missing, mismatched or failed policy evidence before acceptance, even
for collected results. Worker verdict, envelope status, process exit 0 and
collect verification success confer no exception. New `lane-*` refusals follow
the shared wire's exit 2 and expected/found/needed line, without override.

Policy/instruction maintenance requires the true maintenance boolean and bounded
standing/per-job evidence under the previously admitted policy. Existing standing
owner authorization binds subsequent jobs without another owner act. Admission
and grant digests cover exact existing-register `show` stdout, read from the host
store by the admitted reader/runtime and configuration, never candidate copies
or the worker HOME. Candidate policy, reader, config and seed bytes cannot
self-authorize. Bootstrap binds independently verified policy, consumer and
reader/runtime custody. Existing records retain their bytes and historical
status, without backfill or a claim that old sessions were enforced. After
cutover unbound work cannot write-resume, collect for acceptance, land or advance
a ladder; continuing it requires a fresh bound dispatch with retained provenance.
Partial deployment is not activation. This section is a contract/data proposal,
not a live gate or stronger harness containment claim; executable consumers and
independent tests follow. Existing unrelated dispatch behavior remains as above.

### Lane

Current ownership and precedence are defined by
[AGENTS.md §Lane boundary and precedence](../../../AGENTS.md#lane-boundary-and-precedence)
and [ops/README.md](../../README.md#lane-boundary-and-precedence).
The launcher is dev tooling and must operate without the Symfony application
or its vendor directory. Its work profile is independent of harness and
conductor/worker role; using it to dispatch prod application work does not
change its ownership or retire it in favor of an application launcher.
The legacy `lane: "dev"` and `WF_LANE=dev` below describe the apparatus,
not a classification of every job's authorized work. Briefs, resumed jobs
and accepted artifacts remain subject to the current boundary; this
documentation correction adds no profile field or enforcement mechanism.

Everything here is dev-lane: the launcher code under
`ops/devlane/dispatch/` (over the task app's `run.py`), the records
under `.dev/records/`, `lane: "dev"` in every record,
`WF_LANE=dev` in every child, and a refusal to record on `main`. The
product lane's Conductor will carry its own launcher and its own
records; nothing here binds it.
