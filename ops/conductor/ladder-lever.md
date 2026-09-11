# The ladder lever — contract

Standing: PROPOSED. Source of demand: D-LADDER-1 and the measured lane
batch whose twelve hand-driven stage boundaries added about forty-five
minutes of session latency. This instrument automates those boundaries;
it does not replace the dispatcher, launcher, land lever, findings
ledger, or process law.

## Conventions

This instrument inherits `ops/conductor/instrument-conventions.md`:
the refusal wire, identity rule, four-class exits, instrument shape,
and lint duty apply as written here.

## Instrument

`ops/bin/ladder.sh SCOPE BRANCH [PLAN] [--input PATH]...` starts a
ladder in the worktree that owns `BRANCH`. Each `--input PATH` names a
file handed to every stage beside the scope and plan, so the work order a
scope sentence cites reaches every worker as a supplied input; each is
recorded with its digest and re-verified on resume. `ops/bin/ladder.sh
resume LADDER_ID [--rescope]` resumes the named record at its first stage
not recorded `ok`. A scope, plan or input whose bytes changed since the
record refuses `record` unless `--rescope` is given, in which case the
change is recorded as an event, `rescoped: [{label, path, from, to, at,
stage}]`, the digest updated, and the stages from `stage` on receive the
new bytes; earlier stage rows keep the digests they were given. The conf
is never rescoped. `--rescope` with nothing changed refuses `arguments`. Every launch uses
that worktree's `ops/bin/dispatch.sh --detach`; every wait, landing,
ledger update, push, and PR action uses that same worktree.

An implementation run covers at most one declared S bucket. Multiple
S buckets are separate implementation stages, each landed and green
before the next. The skeptic runs once on the first tests, never again
after a test fix. The security and adversarial audits run once, after
the batch's final implementation; their single fix round and the
security re-audit also run once for the batch.

## Stage table

The table is data in the driver. Models and efforts are resolved by the
dispatcher from the lane configuration, never carried in this table.

| stage | job | harness | stage flag | input | condition |
|---|---|---|---|---|---|
| `tests` | `author-tests` | grok | `tests` | scope, plan | always |
| `check-tests` | `check-tests` | codex | `check-tests` | scope, plan, tests envelope | always |
| `tests-fix` | `author-tests` | grok | `tests` | scope, plan, skeptic envelope and `SKEPTIC.md` | skeptic says `changes` |
| `code` | `implement` | codex | `code` | scope, plan, derived test command | once per S bucket |
| `security` | `security-audit` | codex | `review` | scope, plan | after the final bucket |
| `adversarial` | `adversarial-review` | grok | `review` | scope, plan | after the final bucket |
| `fix-tests` | `author-tests` | grok | `tests` | scope, plan, both audit envelopes, extracted from their records (a whole record names the implementation it follows) | either audit says `changes` |
| `fix-code` | `implement` | codex | `code` | scope, plan, both audit envelopes, test command | after `fix-tests` |
| `security-re` | `security-audit` | codex | `review` | scope, plan, original security envelope | after the audit fix round |
| `pr` | `gh pr create --draft` | none | none | body built from records | audits approve |

Security and adversarial audit dispatches are started back to back and
waited in table order. No other stages run concurrently. Test commands
come only from test artifacts in the first test envelope: each path
under a `tests/` directory becomes a `python3 -m unittest discover`
invocation, joined in order with `&&`. No such artifact is an
`artifacts` stop, never an invented command.

Write stages (`tests`, `tests-fix`, each `code`, `fix-tests`, and
`fix-code`) land through `land.py` with `--author` from the worktree's
git identity and `--co-author` from `model.ran` plus the configured
harness address. Review stages import their envelope through
`findings.py import`, export the ledger to
`ops/conductor/findings/findings.jsonl`, and commit that export. The
branch is pushed once immediately before the draft PR is opened.

## Preconditions and refusals

All preconditions are checked before the first dispatch. A refusal is
one stderr line, stdout empty, and exit 2.

| class | refuses when | needed |
|---|---|---|
| `arguments` | neither `SCOPE BRANCH [PLAN]` nor `resume LADDER_ID` was supplied | choose one documented form |
| `conf-key` | a required lane key is absent | declare it in the named lane conf |
| `scope` | the scope is absent, unreadable, or its stage sentence exceeds `SCOPE_CAP` | supply a bounded readable scope |
| `input` | a `--input` path is absent or unreadable | supply a readable input file |
| `worktree` | the named branch is not checked out in a worktree | add it below configured `WORKTREE_ROOT` |
| `dirty` | that worktree has staged or unstaged changes | commit or stash them |
| `identity` | `WF_AGENT` and the worktree git identity are not full `Name <address>` values | supply both identities |
| `gh-missing` | `gh` cannot be executed | install or expose the GitHub CLI |
| `job` | a stage's named job is absent from the registry | restore the job declaration |
| `record` | the named resume record is absent or invalid, or a recorded scope, plan or input changed without `--rescope` | choose or repair the record, or resume with `--rescope` |

## Stops, retries, and exits

| exit | condition | last output |
|---|---|---|
| 0 | draft PR opened | ladder id and PR URL |
| 1 | `security-re` still says `changes` | `stopped stage=security-re record=<id> verdict=changes` |
| 2 | a precondition refuses | the refusal wire |
| 3 | a stage refuses, trips, dies, records an invalid envelope, violates a guarantee, or an invoked write aborts | the last reading, then `stopped stage=<stage> record=<id-or-none> reason=<class>` |

A stage has at most two attempts. Resume uses the requested ladder id,
never the newest record by implication. If its stopped dispatch record
is now closed with an accepted envelope, resume consumes and lands it
without relaunching. Otherwise it relaunches that stage once. A second
failure stops as `retry-cap`. A tripped or dead stage names
`launch.py collect` as its remedy; the driver never collects on its own.
No second fix round and no second skeptic run exist.

## Record

After every transition the driver commits
`.dev/records/ladders/<id>.json` as `ladder: record <id>`, with
`Source: generated: ops/conductor/tools/ladder.py` and the active
`WF_AGENT` as `Co-Authored-By`. The id is
`<UTC stamp>-ladder-<6 hex>`. The record carries:

- `id`, lane, branch, worktree, `base_sha`, status, and a nullable stop
  and PR result;
- scope, optional plan, start inputs, and conf paths with SHA-256 digests,
  and `rescoped` events for any of the first three accepted on resume;
- ordered stage rows naming job, harness, attempt, input path and
  digest, custody proof, dispatch record, dispatched and recorded model
  and effort, outcome, landed shas, and ledger import/export state;
- for every slice, the plan's declared bucket beside measured files,
  tests, lines, stage minutes, and findings per stage.

Status is `running`, `stopped`, or `done`. A stage that does not run is
still present as `outcome: skipped` with its condition, so absence is
declared rather than inferred.

## Verified guarantees

1. **Custody.** Every input contains the scope's first line and the
   previous stage's record id. Inputs to `tests`, `check-tests`,
   `tests-fix`, and `fix-tests` contain no implementation record id and
   no line from an implementation envelope. A line counts as a marker
   only when it is at least 24 characters and is not a path present in
   the worktree: bare paths, severity tokens and short receipts name
   shared surfaces, and an audit that names the same file is not a leak.
   The driver verifies both directions against the bytes it dispatches
   and records the proof; failure stops as `withheld`.
2. **Lineage.** Every sha printed by landing must satisfy
   `git merge-base --is-ancestor <stage-base> <landed-sha>`. Failure
   stops as `lineage`.
3. **Selection.** Before launch, the driver's dispatcher dry-run records
   the resolved model and effort. The closed record's requested model
   and effort must match those readings; failure stops as `model`.
   `model.ran` remains separate evidence.
4. **Wire.** Every driver return is exactly one of exits 0, 1, 2, or 3
   with the output shape above.

The snapshot half of custody is a declared residue: the current
launcher supports whole-tree snapshots only, so this instrument proves
stage input custody but cannot claim that the test writer's snapshot
withholds implementation.
