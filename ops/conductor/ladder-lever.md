# The ladder lever — contract

Standing: PROPOSED. Source of demand: D-LADDER-1 and the measured lane
batch whose twelve hand-driven stage boundaries added about forty-five
minutes of session latency. This instrument automates those boundaries;
it does not replace the dispatcher, launcher, land lever, findings
ledger, or process law.

[Finding admission](../devlane/task/FINDING-ADMISSION.md) narrows the correction
conditions and inputs below. It is the owner-scoped target; source enforcement
requires the later independent tests and implementation described there.

Its [mandatory prevention amendment](../devlane/task/FINDING-ADMISSION.md#mandatory-prevention-amendment)
also governs bound work orders: `--work-order FILE` carries frozen fixture,
acceptance and final commands and the draft-dev terminal action. The driver
forwards this declaration and `--review-request FILE` to canonical dispatch,
uses launcher-executed verification receipts, and reserves review eligibility
through the ledger. The same checks bind manual dispatch and resume. These
are pending implementation obligations, not additional review stages.
The target `ops/bin/ladder.sh finish WORK_ORDER` resolves a manual work order's
registered worktree and consumes the same terminal predicate and existing
push/draft-PR operation, without dispatching another review. Missing bindings
refuse before push; terminal failures retain resumable evidence.

## Conventions

This instrument inherits `ops/conductor/instrument-conventions.md`:
the refusal wire, identity rule, four-class exits, instrument shape,
and lint duty apply as written here.

## Instrument

`ops/bin/ladder.sh SCOPE BRANCH [PLAN]` starts a ladder in the worktree
that owns `BRANCH`. `ops/bin/ladder.sh resume LADDER_ID` resumes the
named record at its first stage not recorded `ok`. Every launch uses
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
| `tests-fix` | `author-tests` | grok | `tests` | scope, plan, admitted skeptic correction projection | evaluated in-scope defects admitted |
| `code` | `implement` | codex | `code` | scope, plan, derived test command | once per S bucket |
| `security` | `security-audit` | codex | `review` | scope, plan | after the final bucket |
| `adversarial` | `adversarial-review` | grok | `review` | scope, plan | after the final bucket |
| `fix-tests` | `author-tests` | grok | `tests` | scope, plan, admitted audit correction projection | evaluated in-scope defects admitted |
| `fix-code` | `implement` | codex | `code` | scope, plan, admitted audit correction projection, test command | after admitted `fix-tests` |
| `security-re` | `security-audit` | codex | `review` | scope, plan, original security envelope | after the audit fix round |
| `pr` | `gh pr create --draft` | none | none | body built from records | audits approve |

Security and adversarial audit dispatches are started back to back and
waited in table order. No other stages run concurrently. For legacy work, test
commands come only from test artifacts in the first test envelope: each path
under a `tests/` directory becomes a `python3 -m unittest discover`
invocation, joined in order with `&&`. No such artifact is an
`artifacts` stop, never an invented command. Bound work orders instead execute
their frozen commands; artifact derivation checks consistency and cannot
replace, expand or drop the declared acceptance set.

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
| `worktree` | the named branch is not checked out in a worktree | add it below configured `WORKTREE_ROOT` |
| `dirty` | that worktree has staged or unstaged changes | commit or stash them |
| `identity` | `WF_AGENT` and the worktree git identity are not full `Name <address>` values | supply both identities |
| `gh-missing` | `gh` cannot be executed | install or expose the GitHub CLI |
| `job` | a stage's named job is absent from the registry | restore the job declaration |
| `record` | the named resume record is absent or invalid | choose or repair the record |

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

Before any fresh correction, including resume, consume the complete batch's
bound ledger projection. An admission refusal stops through the existing stage
stop wire; an empty admitted set skips correction without inventing approval
or another dispatch. Held findings remain visible. No incomplete review becomes
complete because filtration produced no correction. Existing retry limits and
approval requirements are unchanged.

## Record

After every transition the driver commits
`.dev/records/ladders/<id>.json` as `ladder: record <id>`, with
`Source: generated: ops/conductor/tools/ladder.py` and the active
`WF_AGENT` as `Co-Authored-By`. The id is
`<UTC stamp>-ladder-<6 hex>`. The record carries:

- `id`, lane, branch, worktree, `base_sha`, status, and a nullable stop
  and PR result;
- scope, optional plan, and conf paths with SHA-256 digests;
- for bound work, the immutable work-order declaration/digest, consumed review
  request and reservation references, verified receipt hashes and terminal
  evidence specified in the admission amendment; resume revalidates them;
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
   no line from an implementation envelope. The driver verifies both
   directions against the bytes it dispatches and records the proof;
   failure stops as `withheld`.
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
