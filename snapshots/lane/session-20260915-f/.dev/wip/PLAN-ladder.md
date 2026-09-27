# Plan — lane fix batch 2: the lane conf, then the ladder driver

Planned against the tree at `0dfb24002fd5c820e38211ec0cd358062b3cb23b`
(dev, PR #29 merged). Inputs read whole: `in/scope-lane-conf.md`
(measured by its author on dev at `77f7c1a`) and
`in/scope-ladder-driver.md` (measured at `e566c33`). Every number in
this plan was produced by a command on the snapshot at `0dfb240`; the
command is named in §8. The scope says what and where the boundaries
are; this plan says how. It moves no boundary.

The batch is two units in one lineage, landed in order:

| unit | what | bucket | lands green on its own |
|---|---|---|---|
| 1 | the lane conf: one tracked file every lane name is read from, a reader, two checks | S | yes: every existing suite stays green, the wrapper's rows keep their meaning, no lever changes its argv |
| 2 | the ladder driver: one lever runs a scope from tests to draft PR, reading its names from unit 1 | M | yes: a new instrument beside the existing ones, one additive change to the land lever, no change to any stage's job |

Unit 2 depends on unit 1 and on nothing else new. Unit 1 depends on
batch 1 (merged at `e566c33`) and on nothing else.

## 1. What the scope left open, and how this plan reads it

Decisions the scope did not make. Each is the plan's reading; the owner
can overrule any of them before tests are written.

- **Where the file lives: `ops/lane.conf`**, tracked, with the
  gitignored `ops/lane.local.conf` sourced after it. The seed
  `ops/conductor/tools/dispatch.conf` is moved there with `git mv` and
  its content kept whole; nothing is duplicated. Copying the lane into
  another project is then "copy `ops/`, `.claude/`, `CONTRIB.md`, edit
  `ops/lane.conf`". A measured fact beside the placement:
  `ops/bin/.gitignore` lists `dispatch.conf` under a comment naming a
  `dispatch.conf.example` that does not exist in the tree; that line
  covers `ops/bin/` only and never applied to the tracked seed. It goes
  with the move, and `ops/lane.local.conf` takes its place in
  `ops/.gitignore`.
- **The file's format is the seed's: `KEY='literal'` lines and `#`
  comments, nothing else.** Bash sources it. The Python reader accepts
  exactly that grammar and refuses a line it cannot parse (class
  `syntax`), so the two readers cannot disagree about a value. No
  expansion, no quoting tricks, no derived values in the file.
- **The reader is one instrument, `ops/conductor/tools/laneconf.py`**,
  stdlib only, in the instrument shape: contract at
  `ops/conductor/laneconf.md`, tests at
  `ops/conductor/tests/test_laneconf.py`, a row in the conformance gate.
  Its verbs are `get KEY` (the value on stdout, or a refusal), `closure`
  (check one) and `literals` (check two). Python readers import it by
  path, the way the launcher already loads `wires.py`. That is the
  scope's "reader and two checks" in one file.
- **Required keys refuse; optional keys default.** Precedence is the
  dispatcher's rule, unchanged: environment, then conf, then built-in
  default. A key with no built-in default is required, and a reader that
  needs it refuses on the wire naming the key and the file. Required at
  unit 1: `LANE_NAME`, `TRUNK_BRANCH`, `RELEASE_BRANCH`, `REPO_SLUG`,
  `CHECK_NAME`, `WF_AGENT_DEFAULT`, `MODEL_GROK`, `MODEL_CODEX`,
  `MODEL_CLAUDE_READ`, `MODEL_CLAUDE_PLAN`, `EFFORT_GROK`,
  `EFFORT_CODEX`, `EFFORT_CLAUDE`, `WALL_DEFAULT`, `SCOPE_CAP`. Optional:
  `LAUNCHER_PIN` (default: the sibling launcher), `MODEL_<HARNESS>_<JOB>`
  and `EFFORT_<HARNESS>_<JOB>` (default: the harness value). Unit 2
  adds `WORKTREE_ROOT`, `ADDRESS_GROK`, `ADDRESS_CODEX`,
  `ADDRESS_CLAUDE` (required) and `LADDER_WAIT_GRACE` (optional, default
  300 seconds). Each key is declared in the unit that gives it a reader,
  so closure holds at both landings.
- **The default wall's key is `WALL_DEFAULT`, not `DEFAULT_TIMEOUT`.**
  Batch 1 retired `DEFAULT_TIMEOUT` and the wrapper refuses a conf that
  sets it (`test_a_conf_that_sets_default_timeout_is_refused`). That
  refusal stays. `WALL_DEFAULT` is read by the launcher, which holds the
  literal `"900"` today; the wrapper does not read it, because the wall
  belongs to the job unless `DISPATCH_TIMEOUT` or `--timeout` says
  otherwise. Per-job caps stay in `jobs.json`.
- **The state root is a rule, not a key.** It is
  `${XDG_STATE_HOME:-$HOME/.local/state}/<LANE_NAME>`, stated in the
  conf's header and computed by the reader. A literal root in the file
  would need expansion, which the format forbids. `DISPATCH_JOBS` keeps
  overriding the dispatch store as today.
- **The environment override for the file is `LANE_CONF`.**
  `DISPATCH_CONF` retires with the file it named; the wrapper suite's
  `CONF_ENV` pin flips in the same test slice. This is the one wire
  change in unit 1 and it is named here as such.
- **The local file may not set a name.** `ops/lane.local.conf` is for
  per-machine values (`LAUNCHER_PIN`, a machine's model override, an
  agent identity). If it sets `LANE_NAME`, `TRUNK_BRANCH`,
  `RELEASE_BRANCH`, `REPO_SLUG` or `CHECK_NAME`, both readers refuse
  (class `local-key`). Without this rule a suite's answer would depend
  on which machine ran it.
- **`lane: "dev"` in a dispatch record is not the trunk branch name.**
  It is the record's lane kind (`record.py` line 49, the dispatch
  contract §Lane, `WF_LANE=dev` in every child) and it stays a literal.
  The literals check carries an exemption table naming it, so the
  exemption is a reviewable diff, not a comment.
- **The driver is `ops/conductor/tools/ladder.py` behind the shim
  `ops/bin/ladder.sh`**, the shape `dispatch.sh` already has. Its stage
  table is data inside the file, one instance of the workflow genus;
  the generic engine is the Symfony twin's, not this lever's.
- **The driver's "named command" for `implement` is derived, not
  typed.** It is built from the `author-tests` envelope's artifacts:
  every artifact path under a `tests/` directory becomes one
  `python3 -m unittest discover -s <dir> -p <file>` invocation, joined
  with `&&`. An envelope naming no test file stops the run (§5).
- **One fix round after the skeptic, then implement, with no re-check
  of the tests.** The scope names the security re-audit as the only
  re-audit; the plan follows that literally and does not add a second
  skeptic run.
- **Re-authoring lands in the land lever, as two optional flags.**
  `land.py RECORD --author 'Name <addr>' --co-author 'Name <addr>'`:
  each cherry-picked commit is amended to the given author and carries
  the `Co-Authored-By:` trailer once. The author is the worktree's own
  `git config user.name`/`user.email` (the owner's checkout); the
  co-author is the record's `model.ran` with the harness's vendor
  address from the conf. Doing this after landing would mean a rebase
  in the driver; doing it in the lever is one amend per pick on the
  tip. Without the flags the lever behaves exactly as today.
- **The release branch's name is measured at implementation, not
  here.** `AGENTS.md` says `master`; `launch.py` line 799 and
  `branches.py` lines 271 to 305 say `main`; the snapshot has no remote
  refs to settle it (§8). The implementer measures
  `git symbolic-ref refs/remotes/origin/HEAD` in the worktree and writes
  that value as `RELEASE_BRANCH`. Every `main` literal becomes a read of
  that key, which is the defect that falls out of the unit.

## 2. Unit 1 — the lane conf (S)

### What it unblocks

- The driver (unit 2), which would otherwise carry the trunk name, the
  worktree root, the check name, the models, the efforts and the
  security model itself.
- The batch 2 fixes that follow, which read the conf from the start
  instead of adding literals to be scrubbed later.
- The lane's copy into the fixture repository (the driver's proving
  ground after its first lane run), which the scope makes a one-file
  edit.

### Edges it touches, and the guarantees each must declare or keep

| edge | obligation declared | guarantee kept |
|---|---|---|
| `ops/lane.conf` → `dispatch.sh` | shape: the required key set; behavior: env beats conf beats default; local file sourced after, name keys refused | wrapper acceptance rows 1 to 12 keep their meaning; argv order unchanged; `--dry-run` JSON unchanged |
| `ops/lane.conf` → `launch.py` | `WALL_DEFAULT`, `SCOPE_CAP`, `LANE_NAME`, `TRUNK_BRANCH`, `RELEASE_BRANCH`; a missing key is refusal `conf-key`, exit 3 | the refusal table gains one row and changes none; `caps.timeout_source` keeps its three tokens (`default` now names the conf's value); the record shape is byte-for-byte the same |
| `ops/lane.conf` → every state-root reader (`land`, `findings`, `decisions`, `hand`, `ci`, `branches`, `co_doc`, `onboard`, `skills`, `worth`, `gate.sh`, `board.sh`, `link-ops.sh`) | each reads `LANE_NAME` through the reader | every store path resolves to the same value as today; the conformance gate's stripped-environment invocations still find the conf, because readers locate it relative to their own file, never the cwd |
| `ops/lane.conf` → `pr_overview.py`, `branches.py`, `commit_trailers.py`, the two hooks that list published refs | `REPO_SLUG`, `TRUNK_BRANCH`, `RELEASE_BRANCH` | the overview's `--repo` default and the trailer check's `--base-ref` default keep their current values |
| `ops/lane.conf` ↔ `.github/workflows/ci.yml` | `CHECK_NAME` equals the workflow's `name:`; the closure check reads both | CI's check set is unchanged; two steps are added |
| `ops/lane.local.conf` → both readers | permission: name keys forbidden; sourced after the tracked file | absent file is not a refusal |
| `laneconf.py closure` over lane code | closure both ways: every key read is declared, every key declared has a reader | runs in CI on every PR into `dev`; a planted fault fails it (fixture in the suite) |
| `laneconf.py literals` over lane code | no literal lane name, branch name, slug, check name, or another machine's home path outside the conf, the reader, the checks and their tests | the exemption table is data in the check; `ops/devlane/infra/` and `ops/archive/` are excluded by name, and the exclusion is printed |

### What it depends on

- Batch 1 merged (`e566c33`): the wrapper's `DEFAULT_TIMEOUT` refusal,
  the relative launcher default, `--detach`, `wait`, `collect`.
- The instrument conventions (`ops/conductor/instrument-conventions.md`)
  and the conformance gate, which the reader joins.
- Nothing from unit 2.

### The readers, by file (measured at `0dfb240`, §8)

| value | file, place | becomes |
|---|---|---|
| `agentscient` as a state or store path | `launch.py:144`, `land.py:45`, `findings.py:65`, `decisions.py:15`, `hand.py:62,158`, `ci.py:52`, `branches.py:113`, `co_doc.py:25`, `onboard.py:102,147`, `skills.py:32`, `worth.py:723`, `dispatch.sh:210`, `gate.sh:27`, `board.sh:12,24`, `link-ops.sh:10` | `LANE_NAME` through the reader (Python) or the sourced conf (bash) |
| `uscient/agentscient`, `uscient` | `pr_overview.py:695`, `board.sh:9,10`, `link-ops.sh:9` | `REPO_SLUG`; the org is its left half |
| `dev` as a branch | `launch.py:799,844`, `branches.py:217,228,232,244,245,271,276,305`, `commit_trailers.py:328,356` | `TRUNK_BRANCH` |
| `main`/`master` as a branch | `launch.py:799`, `branches.py:271,276,305`, `unsafe-command.py:51`, `context-stream.sh:43` | `RELEASE_BRANCH` (measured, §1) |
| `1024` | `dispatch.sh:125`, `go.sh:57`, `launch.py:826,827` | `SCOPE_CAP` |
| `"900"` | `launch.py:747,1451` | `WALL_DEFAULT` |
| `/home/work/...` | `grok-dispatch.sh:186`, `codex-dispatch.sh:256` | removed; the levers keep `PATH` and the operator's own home |
| `ci` as the check name | not found in code at this ref (§8: the overview's three `"ci"` hits are the gate-kind data key); only `ci.yml:1,21` | `CHECK_NAME`; the closure check is its reader in unit 1, the driver's PR body in unit 2 |
| `../wt` | not found in code at this ref (only the hooks' test corpus, as data) | `WORKTREE_ROOT`, declared in unit 2 with the driver as reader |

Not in scope and not touched: the term wall pattern; `lane: "dev"` in
records; the `agentscient-wsl` runner label (a CI variable's home);
`ops/devlane/infra/gitea/bootstrap.sh` (inert, excluded by name and
listed as residue); test fixtures under `ops/devlane/telemetry/tests/`
and `ops/devlane/fixtures/tests/` that hold `/home/work/projects/uscient/agentscient`
as a planted path slug (data, listed as residue, and outside the
literal check's scan because it excludes `tests/` directories).

### Tests, by file, and why each is red at `0dfb240`

Written by the test author from this plan and the contract
`ops/conductor/laneconf.md`, never from the implementation. Each test
plants its own conf through `LANE_CONF` and never writes the tracked
file.

`ops/conductor/tests/test_laneconf.py` (new; red because
`ops/conductor/tools/laneconf.py` and `ops/lane.conf` do not exist, so
every invocation is Python's missing-file exit 2 with no wire line):

- `get KEY` prints the value and exits 0; a missing key refuses class
  `key` naming the key and the file, one stderr line, empty stdout.
- environment beats conf: `KEY=env` in the invoking environment wins
  over the file.
- the local file beside the tracked one is sourced after it and wins
  for an allowed key; a local file setting any of the five name keys
  refuses class `local-key` naming the key and the local file.
- a line that is not `KEY='literal'` or a comment refuses class
  `syntax` naming the line number.
- parity: for the tracked `ops/lane.conf`, `bash -c 'source FILE;
  declare -p KEY'` and `laneconf.py get KEY` agree for every declared
  key (a loop with a count assertion first).
- `closure` exits 0 on the tree; a scratch tree with a declared key no
  code reads exits 1 naming it; a scratch tree whose code reads an
  undeclared key exits 1 naming it and the file; `CHECK_NAME` not equal
  to the workflow's `name:` exits 1 naming both.
- `literals` exits 0 on the tree; a scratch lane file carrying `"dev"`,
  `origin/dev`, `'agentscient'`, `uscient/agentscient` or `/home/work/`
  exits 1 naming file and line; the exemption table entry for
  `record.py`'s lane kind passes and a second `"dev"` in the same file
  fails; `ops/devlane/infra/` is skipped and the skip is printed.
- the tracked `ops/lane.conf` declares every required key of §1 and no
  `DEFAULT_TIMEOUT`.

`ops/conductor/tests/test_dispatch_wrapper.py` (existing; edits in the
fixture and new rows):

- `CONF_ENV` becomes `LANE_CONF`; `_conf_kwargs` gains `LANE_NAME`,
  `TRUNK_BRANCH`, `RELEASE_BRANCH`, `REPO_SLUG`, `CHECK_NAME`,
  `SCOPE_CAP`. Red because the wrapper reads `DISPATCH_CONF` only, so
  every case runs against the real conf instead of the scratch one and
  `Row1` fails on the model.
- new row: `SCOPE_CAP='10'` in the scratch conf and an 11-byte scope
  refuse exit 3 naming `11`; red because the cap is the literal 1024.
- new row: a detached launch with `LANE_NAME='lanex'` creates the job
  directory under `<xdg>/lanex/dispatch`; red because the path is the
  literal `agentscient`.
- new row: a sibling `lane.local.conf` overriding `MODEL_GROK` wins in
  the dry-run argv; one setting `LANE_NAME` refuses naming `local-key`.
  Red because nothing is sourced after the conf.
- new row: a conf missing `SCOPE_CAP` refuses naming the key and the
  file; red because the key is unknown to the wrapper.

`ops/devlane/dispatch/tests/test_launch_lane_conf.py` (new, on the
existing `launch_support` fixtures):

- a job without `caps` and a scratch conf with `WALL_DEFAULT='7'`
  records `caps.timeout` 7.0 and `timeout_source` `default`; red
  because the launcher holds `"900"`.
- `SCOPE_CAP='10'` and an 11-byte `--scope` refuse `scope-cap` naming
  11; red because the launcher holds 1024.
- `LANE_NAME='lanex'` puts the jobs root at `<xdg>/lanex/dispatch`; red
  because the launcher holds the literal.
- `TRUNK_BRANCH='trunkx'` and a checkout on `trunkx` refuse
  `record-target`; a checkout on `dev` with that conf is not refused
  for that reason. Red because the set is `{"detached", "dev", "main"}`.
- a conf missing `WALL_DEFAULT` refuses `conf-key` naming the key and
  the file, exit 3, before anything is minted (the fake harness's
  start witness is absent). Red because no such refusal exists.
- the existing `test_launch_verbs.py:28,43` and `test_record_paths.py:42`
  keep pinning `agentscient` and stay green: the tracked conf says so.

`ops/conductor/tests/test_instrument_conventions.py` (existing): a
registry row `("laneconf.py", ["get", "NO_SUCH_KEY"], "key", False)`;
red because the file is absent.

`ops/conductor/tests/test_land_lever.py`, `test_handwork_ledger.py`,
`test_decisions_register.py`, `test_ci_store.py`,
`test_branch_census.py`, `test_onboard_lever.py`,
`test_skills_registry.py`, `test_co_doc.py`, the telemetry and
pr-overview suites: unchanged and green before and after; the plan
lists them so the implementer runs `ops/bin/suites.sh` and reports the
count, not so anything is added.

### Order of implementation

1. `git mv ops/conductor/tools/dispatch.conf ops/lane.conf`; add the
   new required keys with today's values; drop the `dispatch.conf`
   lines from `ops/bin/.gitignore` and add `lane.local.conf` to
   `ops/.gitignore`.
2. `laneconf.py` with `get`, the parser, the local-file rule, the
   contract `ops/conductor/laneconf.md`, the registry row.
3. `dispatch.sh`: source `../../lane.conf` then the local file, `LANE_CONF`
   override, `SCOPE_CAP`, `LANE_NAME` in the jobs root, the name-key
   guard after sourcing the local file. `go.sh`: `SCOPE_CAP` from the
   sourced conf.
4. `launch.py`: load the reader by path; `WALL_DEFAULT`, `SCOPE_CAP`,
   `LANE_NAME`, `TRUNK_BRANCH`, `RELEASE_BRANCH`; refusal `conf-key`.
5. The state-root readers, the slug readers, the branch-name readers,
   the two hooks, the two levers' `/home/work` removal, one file at a
   time, each followed by its own suite.
6. `closure` and `literals` verbs with the exemption table; two steps
   in `ci.yml` after the term wall.
7. Docs that name the old file: `ops/README.md` (levers table, "the
   rules the lane binds"), `ops/conductor/README.md` (tools row),
   `AGENTS.md` §The lane if it names `dispatch.conf`. Hand-off records
   are history and are not edited.
8. `bash ops/bin/suites.sh`, `ruff check .`, the copy-into-scratch
   proof, the draft PR.

### Acceptance, mapped to proof

| acceptance (scope) | proof |
|---|---|
| grep for the lane's name, `dev`, `master`, the slug and the check name over lane code finds them only in the conf, its reader, the checks and their tests | `python3 ops/conductor/tools/laneconf.py literals` exits 0 on the merged tree, in CI and in the PR body with its sha; the raw grep is also run and its remaining hits are listed as the residue of §7 |
| `dispatch.sh --dry-run` and `launch.py` resolve models, efforts, wall and pin from the same file, shown in the record's `caps` and `model` | the wrapper's dry-run JSON and a real `--detach` dispatch's record, both quoted in the PR body; `test_dispatch_wrapper.py` rows 1, 8, 9, 11 and `test_launch_lane_conf.py` |
| a conf missing a required key makes each reader refuse in one line naming the key and the file | `test_laneconf.py`, the wrapper's missing-key rows, `test_launch_lane_conf.py`'s `conf-key` case, the conformance gate row |
| a copy of the lane into a scratch repository with a one-file edit runs `suites.sh` green and a `--dry-run` dispatch | a command sequence in the PR body: copy `ops/`, `.claude/`, `CONTRIB.md`, `ruff.toml` into a fresh `git init` repository, edit `LANE_NAME` and `REPO_SLUG`, run both; output quoted with the scratch path and the sha copied from |
| every lane suite green on the merged tree; `ruff check .` clean | `bash ops/bin/suites.sh` on a merge of the head with `origin/dev`, and `ruff check .`, both in the ready note |

## 3. Unit 2 — the ladder driver (M)

### What it unblocks

- Unattended runs of the process document's loop: the forty-five
  minutes of session latency per four-hour batch, and the hand errors
  the scope lists, stop being part of every slice.
- The findings ledger fed at every review stage without a hand step, so
  the marginal detection series (`docs/workflow.md`) is produced as a
  byproduct.
- The fixture repository as the proving ground: the driver runs there
  with the lane copied and one file edited.

### The stage table

Declared as data in the driver. Every launch goes through the
worktree's own `ops/bin/dispatch.sh` with `--detach`; the harness, job
and stage are fixed here, the model and effort come from the conf
through the dispatcher, never from the driver.

| # | stage | job | harness | stage flag | input file holds | runs when |
|---|---|---|---|---|---|---|
| 1 | tests | `author-tests` | grok | `tests` | scope, plan | always |
| 2 | check-tests | `check-tests` | codex | `check-tests` | scope, plan, stage 1 envelope | always |
| 3 | tests-fix | `author-tests` | grok | `tests` | scope, plan, stage 2 envelope and its `SKEPTIC.md` | stage 2 verdict `changes` |
| 4 | code | `implement` | codex | `code` | scope, plan; the scope sentence is the derived test command | always |
| 5 | security | `security-audit` | codex | `review` | scope, plan | always |
| 6 | adversarial | `adversarial-review` | grok | `review` | scope, plan | always |
| 7a | fix-tests | `author-tests` | grok | `tests` | scope, plan, stage 5 and 6 envelopes | stage 5 or 6 verdict `changes` |
| 7b | fix-code | `implement` | codex | `code` | scope, plan, stage 5 and 6 envelopes; the same test command | stage 5 or 6 verdict `changes` |
| 8 | security-re | `security-audit` | codex | `review` | scope, plan, stage 5 envelope | after 7 |
| 9 | pr | `gh pr create --draft` | none | none | body built from the records | stage 8 `approve`, or stages 5 and 6 both `approve` |

Stages 5 and 6 are launched back to back and waited in order; nothing
else runs concurrently. The security model is `MODEL_CODEX_SECURITY_AUDIT`
already in the seed, resolved by the dispatcher's per-job rule, so the
driver names no model.

After every write stage (1, 3, 4, 7a, 7b) the driver runs the land
lever in the worktree with `--author` from the worktree's git identity
and `--co-author` from the record's `model.ran` and `ADDRESS_<HARNESS>`.
After every review stage (2, 5, 6, 8) it runs `findings.py import`,
then `findings.py export` into `ops/conductor/findings/findings.jsonl`,
and commits the export on the branch. Before stage 9 it pushes the
branch once; landing does not push per stage.

### Stop, exit classes, resume

| condition | exit | what is printed |
|---|---|---|
| draft PR opened | 0 | the ladder record id and the PR URL |
| a verdict the rules cannot resolve: `changes` at stage 8 | 1 | `stopped stage=security-re record=<id> verdict=changes`; the findings are in the ledger; no further dispatch |
| a precondition fails before the first launch: missing conf key, scope file absent or over `SCOPE_CAP` for the stage sentence, branch has no worktree, dirty worktree, identity, `gh` absent | 2 | one refusal line on the wire, stdout empty |
| a stage refuses at mint, trips, dies, or its envelope is `invalid`; a landing aborts; a landed commit does not descend from the stage base; the record's model or effort differs from the conf's | 3 | the last reading, then `stopped stage=<name> record=<id or none> reason=<class>`; the ladder record is committed with `status: stopped` |

`ladder.py resume LADDER_ID` reads the ladder record, finds the first
stage that is not `ok`, and continues there. If that stage's dispatch
record exists and is closed with an `ok` envelope, it is landed and the
ladder continues without a relaunch. Otherwise the stage is relaunched
once; the ladder record counts attempts per stage, and a stage already
at attempt 2 stops the resume with exit 3 naming `retry-cap`. A tripped
or died stage's remedy names `launch.py collect`, which the driver
never runs on its own.

### The ladder record

One file per run at `.dev/records/ladders/<id>.json`, id
`<UTC stamp>-ladder-<6 hex>`, committed on the branch after every stage
transition as `ladder: record <id>` with `Source: generated:
ops/conductor/tools/ladder.py` and `Co-Authored-By: $WF_AGENT`. Fields:
`id`, `lane` (`dev`), `branch`, `worktree`, `base_sha` (the branch tip
at start), `scope {path, sha256}`, `plan {path, sha256} | null`,
`conf {path, sha256}`, `stages [{name, job, harness, attempt,
input {path, sha256, proof {given, withheld}}, record, dispatched
{model, effort}, recorded {model_requested, model_ran, effort}, outcome,
landed [shas], ledger {imported, exported}}]`, `stopped {stage, record,
reason} | null`, `pr {number, url} | null`, `status`
(`running | stopped | done`). Absence is declared: a stage that did not
run has `outcome: skipped` with the condition that skipped it.

### Guarantees the driver declares (docs/verified-couplings.md)

1. **A stage's input never contains the withheld artifact.** For stages
   1, 2, 3 and 7a the withheld set is every `implement` record id and
   every line of an `implement` envelope; for every stage the given set
   is the scope's first line and the previous stage's record id. The
   driver proves both before launch: no withheld string is in the file,
   every given string is, and writes the proof into the stage row. A
   failed proof is exit 3, class `withheld`. The snapshot half of
   D-FIREWALL-1 is not this unit's: the launcher refuses any snapshot
   mode but `whole` (`mode-unavailable`) and every job declares `whole`,
   so a fix-round test writer at stage 7a sees the implementation in its
   tree. Named as residue in §7.
2. **A landed commit descends from the stage's base.** After landing,
   `git merge-base --is-ancestor <base> <landed>` for every `LANDED`
   sha, where base is the branch tip recorded before the launch; a
   failure is exit 3, class `lineage`.
3. **A stage runs the model and effort the conf names.** Before each
   launch the driver takes the dispatcher's `--dry-run` JSON and keeps
   `--model` and `--effort` from its argv; after close it compares them
   to the record's `model.requested` and `model.effort_requested`, and
   records `model.ran`. A mismatch is exit 3, class `model`.
4. **The driver's exit classes are the wire's four**, and nothing else
   is ever returned.

### Edges it touches

| edge | what the driver relies on | checked by |
|---|---|---|
| `dispatch.sh` | the flag set, `--detach` printing `record: <id>` and `launcher-pid:`, `--dry-run` JSON with `argv` | the wrapper suite (existing), the driver's own tests with a stub wrapper |
| `launch.py wait` | exit 0 clean, 1 other terminal, 2 wall; the summary line | the launcher suite (existing) |
| `land.py` | `LANDED\t<sha>\t<subject>` lines, `landed n=N`, exits 0, 1, 2, 3; the two new flags | `test_land_lever.py` (existing rows plus the new class) |
| `findings.py import`, `export` | identity from `WF_AGENT`; the export's stdout | existing behavior |
| `jobs.json` | the six job names and their `caps.timeout` | the task suite (existing); the driver refuses at start if a named job is absent, class `job` |
| the dispatch record | `status`, `result.envelope.{status,verdict,artifacts}`, `model.{requested,effort_requested,ran}`, `caps.timeout` | the record contract; the driver's wait wall is the record's `caps.timeout` plus `LADDER_WAIT_GRACE`, falling back to the job's cap, then `WALL_DEFAULT` |
| `ops/lane.conf` | `TRUNK_BRANCH`, `REPO_SLUG`, `CHECK_NAME`, `WORKTREE_ROOT`, `WF_AGENT_DEFAULT`, `ADDRESS_*`, `LADDER_WAIT_GRACE`, `SCOPE_CAP` | `laneconf.py closure` |
| `gh pr create` | `--draft --base <TRUNK_BRANCH> --head <branch> --repo <REPO_SLUG> --title --body-file` | a stub `gh` on `PATH` in the tests; the real call once, in the first lane run |
| the worktree | the branch is checked out in some worktree of the invoking repository; the driver runs every lever from that worktree, so the branch's own launcher, conf and levers are the ones used | `git worktree list --porcelain`, the dispatcher's own rule |

### What it depends on

- Unit 1 landed: the conf, the reader, `SCOPE_CAP` and `LANE_NAME` in
  the dispatcher and the launcher.
- The land lever's two new flags (part of this unit, landed first).
- Batch 1's levers: `--detach`, `wait`, `collect`, `land.py`, the
  branch's own launcher.
- The owner's pick of the first lane S slice for the real run; the plan
  does not choose it.

### Tests, by file, and why each is red at `0dfb240`

Every case seeds a scratch repository whose `ops/` carries stub levers
(`ops/bin/dispatch.sh`, `ops/devlane/dispatch/launch.py`,
`ops/conductor/tools/land.py`, `ops/conductor/tools/findings.py`) and a
stub `gh` on `PATH`; each stub records its argv to a file and produces
the planted outcome (a record file with a planted envelope, a `wait`
summary, `LANDED` lines). The driver locates levers relative to the
worktree, so no environment knob selects the stubs. The live dispatch
store and this repository are asserted untouched in `tearDown`, the
land suite's way.

`ops/conductor/tests/test_ladder_lever.py` (new; red because
`ops/conductor/tools/ladder.py` and `ops/bin/ladder.sh` do not exist):

- presence of both files; the shim execs the instrument.
- refusals before the first launch: no arguments (`arguments`), scope
  file absent (`scope`), branch without a worktree (`worktree`, the
  remedy naming `git worktree add <WORKTREE_ROOT>/ag-<slug> <branch>`),
  dirty worktree (`dirty`), a conf missing `ADDRESS_GROK` (`conf-key`),
  `gh` absent (`gh-missing`); each one line, exit 2, stdout empty.
- `--dry-run` prints the stage table with each stage's dispatcher argv
  and no stub is invoked; the argv carries the scratch conf's model and
  effort for every stage, and the security stages carry
  `MODEL_CODEX_SECURITY_AUDIT`.
- happy path, every verdict `approve`: stages 1, 2, 4, 5, 6 run, 3, 7a,
  7b, 8 are `skipped` with their conditions, the PR stub receives
  `--draft --base <TRUNK_BRANCH> --repo <REPO_SLUG>`, exit 0, the ladder
  record is committed with `status: done`.
- planted `changes` at stage 2: stage 3 runs once, stage 4 follows, no
  second stage 2.
- planted `changes` at stage 6 only: 7a then 7b then 8; 8 `approve`
  opens the PR.
- planted `changes` at stage 8: exit 1, the findings stub was called
  with `import` then `export`, no dispatch after 8, the ladder record
  says `stopped` with the verdict.
- the derived test command: with stage 1 artifacts naming two test
  files the stage 4 scope sentence is the two `discover` invocations
  joined with `&&`; with no test artifact the run stops, exit 3, class
  `artifacts`.
- withholding: the input files of stages 1, 2, 3 and 7a do not contain
  the stage 4 record id or any line of its envelope; stage 7b's does;
  each stage row carries `proof.given` and `proof.withheld` with the
  strings checked; a planted leak (the stub returns an `implement`
  envelope line inside a stage 5 envelope) stops with class `withheld`.
- landing: the land stub is called after stages 1 and 4 with `--author`
  equal to the scratch repository's `user.name <user.email>` and
  `--co-author` equal to the planted `model.ran` plus `ADDRESS_GROK` or
  `ADDRESS_CODEX`; it is not called after read stages.
- lineage guarantee: a land stub that prints a `LANDED` sha not
  descending from the base stops with class `lineage`, exit 3.
- model guarantee: a record whose `model.requested` differs from the
  dry-run's `--model` stops with class `model`, exit 3.
- a planted dispatcher refusal at stage 5 (the stub exits 3 with a wire
  line, no record): exit 3, stderr's last line names `stage=security`
  and `record=none`; `resume <id>` relaunches stage 5 exactly once and,
  with the stub now succeeding, continues to the PR; a second planted
  refusal on resume stops with `retry-cap` and the stub's call count
  for stage 5 is exactly 2.
- a planted trip (`wait` exits 1 with `tripped=true`): exit 3, the
  remedy names `launch.py collect`; `resume` after the stub's record is
  planted closed and `ok` lands it without a relaunch.
- every exit observed across the suite is in `{0, 1, 2, 3}`.
- the driver's source contains none of: `dev`, `master`, `main`,
  `../wt`, `ci`, any model id from the scratch conf, as quoted literals
  (the literals check run over the driver file).

`ops/conductor/tests/test_land_lever.py` (existing; a new class
`Reauthor`): `--author` sets the author of each landed commit and keeps
the committer from `WF_AGENT`; `--co-author` appends the trailer once
and does not duplicate one already present; both flags absent leaves
every existing assertion unchanged (the whole class is additive). Red
because argparse rejects the flags with exit 2 and a usage line that is
not the wire.

`ops/conductor/tests/test_instrument_conventions.py`: a row
`("ladder.py", ["run"], "arguments", False)`; red because the file is
absent.

`ops/conductor/tests/test_laneconf.py`: the tracked conf declares
`WORKTREE_ROOT`, `ADDRESS_GROK`, `ADDRESS_CODEX`, `ADDRESS_CLAUDE`, and
`closure` finds the driver as their reader; red until this unit's conf
change lands.

### Order of implementation

1. The contract `ops/conductor/ladder-lever.md`: the stage table, the
   refusal table, the exit mapping, the record shape, the four
   guarantees. Contracts first.
2. `land.py --author` and `--co-author`, with their rows in
   `ops/conductor/land-lever.md`. Landed as the unit's first commit so
   the driver's tests can stub a lever whose contract already exists.
3. The conf keys of §1 with today's values (`ADDRESS_GROK='noreply@x.ai'`,
   `ADDRESS_CODEX='noreply@openai.com'`,
   `ADDRESS_CLAUDE='noreply@anthropic.com'`, `WORKTREE_ROOT='../wt'`).
4. `ladder.py`: conf load and preconditions; the stage table; the input
   builder with its proof; the dispatch, wait, land and ledger calls;
   the ladder record; stop and resume; the PR body from the records in
   the `CONTRIB.md` template (What, Sources, Evidence with each stage's
   record id, model, effort and verdict produced by reading the records
   at write time, For reviewers listing the audits' open findings).
5. `ops/bin/ladder.sh` shim; the levers table in `ops/README.md`; the
   tools row in `ops/conductor/README.md`; the registry row.
6. Suites, ruff, the draft PR for the unit.
7. The first real run on the lane S slice the owner names, from tests to
   draft PR with no session action between stages; its ladder record and
   the PR are the evidence.

### Acceptance, mapped to proof

| acceptance (scope) | proof |
|---|---|
| `ladder.sh <scope> <branch>` on a lane S slice runs from tests to draft PR with no session action between stages; every stage launched through the dispatcher with the conf's model and effort; every landed commit authored by the owner | the first real run's ladder record, committed on its branch: every stage row's `dispatched` equals its `recorded`; `git log --format='%an <%ae>%n%(trailers:only)' origin/dev..HEAD` on that branch quoted in the PR body |
| a planted refusal at any stage stops the driver on the wire naming the stage and the record; `resume` continues from there | the planted-refusal and resume cases in `test_ladder_lever.py`, and the stub call counts |
| a planted second `changes` verdict after the fix round stops the driver with the findings in the ledger and no further dispatch | the stage 8 case: exit 1, `findings.py import` observed, no later dispatch observed |
| every name the driver uses is read from the conf; grep for the trunk name, the worktree root, the check name and any model id over the driver finds none | `laneconf.py literals` over the driver file, in the suite and in CI |
| every lane suite green; `ruff check .` clean | `bash ops/bin/suites.sh` on the merged tree and `ruff check .` in the ready note |

## 4. Order across the batch

1. Unit 1, all of §2, to a draft PR into `dev`; ready when its lineage
   is stationary and checks are green; merged by the owner.
2. Unit 2 branched from `dev` after that merge, §3 steps 1 to 6, to its
   own draft PR.
3. Unit 2 step 7, the first real run, on a branch of the owner's pick,
   using the merged driver; its PR is the run's own.

Neither unit is split further. Unit 1 is small in each edit and wide
in file count (twenty-six files change, §8); it lands as one PR because
half a conf, with some readers on the file and some on their literals,
is the state the scope exists to end.

## 5. What each unit produces, and who

Per `ops/process/pipeline.md`: this plan is Fable's; the tests are
Grok's from this plan and the two contracts; Codex checks the tests;
Codex writes the code; Grok and Codex review. The contracts
(`laneconf.md`, `ladder-lever.md`, the land lever's two rows) are
written before the tests, by the session with the owner, so the test
author reads a contract and not this plan's prose alone.

## 6. Bucket check

- Unit 1, S: one new instrument of three verbs, one file move, one
  gitignore line, single-line reads in twenty-odd files, two CI steps,
  three docs touched. No lever changes its interface except the
  environment variable's name.
- Unit 2, M: one new instrument with a stage table, an input builder, a
  record, resume and a PR body; two additive flags on the land lever;
  five conf keys; one shim. No new kernel responsibility: it calls the
  levers and reads the records.

## 7. Residue, declared

- **The snapshot half of D-FIREWALL-1.** Unit 2's guarantee 1 covers
  the input file only. The launcher mints `whole` snapshots and refuses
  `fileset` (`mode-unavailable`); at stage 7a the test writer's tree
  contains the implementation. Not this batch's; the plan
  `20260904T000335Z-plan-claude-28b1a2` §1 and §4 already name the
  fileset work.
- **`lane: "dev"` stays a literal** in `record.py`, `launch.py` and the
  record contract: the lane kind, exempted by name in the literals
  check.
- **`ops/devlane/infra/gitea/bootstrap.sh`** carries `agentscient` as
  the Gitea user and repository name; the infra is inert and runs in a
  container without the conf. Excluded from the literals scan by name;
  the exclusion is printed.
- **Test fixtures** in `ops/devlane/telemetry/tests/` and
  `ops/devlane/fixtures/tests/` hold `/home/work/projects/uscient/agentscient`
  as a planted path slug for the Claude project-directory encoding. Data
  under `tests/`, outside the scan. The scope's raw `grep` acceptance
  will still find them; the PR body lists these hits with this reason.
- **The `agentscient-wsl` runner label** lives in the CI variable
  `CI_RUNNER`'s default, per D-CI-1; not a lane-code literal.
- **`CHECK_NAME` has no reader in code at this ref** other than the
  closure check's agreement with `ci.yml`, and the driver's PR body in
  unit 2. The scope's table attributed it to the PR overview; measured
  here, the overview's `"ci"` is the gate-kind data key.
- **`WORKTREE_ROOT` has no reader at this ref**; declared in unit 2.
- **The release branch name** is measured at implementation (§1).
- **`caps.timeout_source` keeps the token `default`** for the conf's
  `WALL_DEFAULT`; renaming it would change the record contract for no
  reader's benefit.

## 8. Evidence

Every row below was produced on the snapshot at `0dfb240` during this
planning run.

| claim | command |
|---|---|
| the seed conf is tracked; the only ignore line naming it is scoped to `ops/bin/` | `git ls-files ops/conductor/tools/dispatch.conf` → listed; `grep -n dispatch.conf ops/.gitignore ops/bin/.gitignore ops/devlane/.gitignore` → `ops/bin/.gitignore:1,2` only |
| the snapshot has no remote refs; the release name cannot be measured here | `git for-each-ref --format='%(refname)' refs/remotes refs/heads` → `refs/heads/lane/ladder-driver` only |
| `.dev/wip/` is absent from the snapshot; the conf scope is read from `in/` | `ls .dev` → `records` only |
| the lane-name literal's code sites | `grep -rn --include='*.py' --include='*.sh' --include='*.json' agentscient ops .claude`, non-test lines: the sixteen files of §2's table |
| the branch-name literal's code sites | `grep -rn -E "['\"/]dev['\"/]|\bmaster\b|origin/dev" ops .claude`, non-test, non-archive: `launch.py:420,799,844,910`, `record.py:22,49`, `branches.py:217,228,232,244,245,271,276,305`, `commit_trailers.py:271-273,328,356`, `unsafe-command.py:51`, `context-stream.sh:43` |
| the slug's code sites | `grep -rn uscient ops .claude .github` → `pr_overview.py:695`, `board.sh:9,10`, `link-ops.sh:9`; the rest are test fixtures |
| the scope cap's code sites | `grep -rn -E "\b1024\b" ops .claude` non-test → `dispatch.sh:125`, `go.sh:57`, `launch.py:826,827` (`breaker.py:193` is a byte unit, not the cap) |
| the default wall's code sites | `launch.py:747` (`"900"`) and `launch.py:1451` (`or 900`) |
| the other machine's home path | `grep -rn /home/work ops .claude` non-test → `grok-dispatch.sh:186`, `codex-dispatch.sh:256` |
| the check name is not a code literal at this ref | `grep -c "'ci'" pr_overview.py` → 0; `grep -c '"ci"'` → 3, at lines 226, 248, 255, all the gate-kind entry key; `ci.yml:1` `name: ci`, `ci.yml:21` job `ci` |
| the worktree root is not a code literal at this ref | `grep -rn -E "\.\./wt|wt/ag-" ops .claude` → only `ops/devlane/hooks/tests/corpus.py` and `test_boundary_match.py`, as test data |
| the record's lane kind is a schema constant | `record.py:22` sets `lane = "dev"`, `record.py:49` requires it; the dispatch contract §Lane |
| the wrapper's required keys and its `DEFAULT_TIMEOUT` refusal | `dispatch.sh:17` (`keys=`), `dispatch.sh:34-38` |
| `wait` exits 0 clean, 1 other terminal, 2 wall | `launch.py:1506-1541` |
| the land lever preserves authorship and has no author flag | `land.py:303-318`, `land.py:330-335` |
| the envelope's verdict values | `envelope.py:43` → `("approve", "changes")`, null allowed |
| the launcher refuses every mode but `whole` | `launch.py:823` (`mode-unavailable`); every `jobs.json` harness job declares `"snapshot": "whole"` |
| the conformance registry's shape | `test_instrument_conventions.py:28-39` |
| the suites the runner knows | `suites.sh:17`: seven devlane suites, `ops/conductor/tests`, `.claude/skills/pr-overview/tests` |
| files unit 1 changes | the sixteen state-root files, `pr_overview.py`, `branches.py`, `commit_trailers.py`, `unsafe-command.py`, `context-stream.sh`, `go.sh`, the two levers, `ops/.gitignore`, `ci.yml`, plus the moved conf and the new instrument: twenty-six existing files, counted from §2's table |
