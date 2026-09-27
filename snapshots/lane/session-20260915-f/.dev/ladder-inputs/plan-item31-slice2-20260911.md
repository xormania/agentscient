<!-- Ladder input for slice 2 (skeptic-driver) of item 31. The plan is
record 20260911T212110Z-plan-claude-866a60 (out/PLAN.md) verbatim; the
machine lines are trimmed to this slice, as for slice 1. -->

# Plan: the skeptic's report on the wire, the driver in custody (item 31)

Tree: `ea9ccf2621d3e3fcf5bf0f1bb57c06ea9cdccd43` (`git rev-parse HEAD`, this
job, 2026-09-11). Inputs read whole: `in/scope-item31-20260911.md` and
`in/scope-discipline.md`; both are byte-identical to the tracked copies
under `.dev/ladder-inputs/` (`md5sum`, this job: `1fa692df…` and
`fe99ae2f…` on both sides). The requirements are the eight numbered
Contract items of the work order and nothing else. Boundaries as listed
there; this plan does not widen them. Every claim below is either measured
by a command in this job (`measured:`), taken from a tracked contract
(`contract:`), or turned into a refusal the run will hit (`refusal:`). A
claim that is none of these is a finding against this plan and is listed
in §7; the plan says so of itself.

Reading fixed here, because the scope and the driver name the stage
differently: the scope's "fix-tests stage's input for the skeptic's
findings" (item 4) is the driver's `tests-fix` stage, the one that today
receives `SKEPTIC.md` (measured: `ladder.py` line 1134 to 1150). The
audit `fix-tests` stage is untouched (boundary: the audit jobs).

## 1. What the tree has today

- `measured: sed -n 66,77p ops/devlane/task/jobs.json` → `check-tests`
  is role `read`, snapshot `whole`, `caps.timeout` 1800, deliverable "a
  skeptic's report at the job's out/SKEPTIC.md; verdict changes when any
  test is refuted", and the prompt says "Write the report to
  {out}/SKEPTIC.md and name that path in artifacts". The prompt names
  `{ref}`, `{inputs}`, `{scope}`, `{out}`.
- `measured: ops/devlane/task/CONTRACT.md` line 178 is the row this work
  order changes: "`check-tests` | a skeptic's report at `out/SKEPTIC.md`;
  verdict `changes` when any test is refuted". Lines 189 to 191 say
  `run.py`'s render refuses `{out}` and `{inputs}` by name; lines 270 to
  272 and 290 to 298 describe the C1 baseline in which the prompt requests
  `{out}/SKEPTIC.md`. Those passages describe the render slots and stay
  as they stand (boundary).
- `measured: ops/devlane/task/envelope.py` lines 317 to 329 and 473 to
  480: a finding has exactly the fields `severity, where, claim,
  reproduce`; `_text` (line 295) collapses all whitespace to single
  spaces; `tally` (line 332) counts a null `reproduce` as an opinion. The
  fields cannot grow without a schema change, which item 6 forbids. So a
  quotation pair is carried inside `claim` (decision D2).
- `measured: ops/conductor/tools/findings.py` lines 42 to 44:
  `REVIEW_JOBS` is five jobs (`check-tests`, `security-audit`,
  `adversarial-review`, `adjudicate`, `sweep`); the scope measured three
  at 4663c9c and the gate work added two. `record_rows` (225 to 243)
  copies `severity`, `where`, `claim`, `reproduce` verbatim. Item 6 holds
  with no change.
- `measured: ops/conductor/tools/ladder.py`: `inputs_for` (1123 to 1173)
  appends the `check-tests` record path to `tests-fix` and then any
  artifact named `SKEPTIC.md` that exists (1145 to 1150), the one
  `SKEPTIC.md` reference in the file; `make_input` (642 to 646) writes
  with `Path.write_text` and no symlink or containment check; `finish`
  (1106 to 1121) runs `ledger_result` for every review stage with no shape
  check beyond `load_envelope` (825 to 885: record closed, envelope status
  `ok`, binding, model); `execute` (1175 to 1232) relaunches a stopped
  stage on resume until the two-attempt cap, so a malformed envelope is
  today retried like a flake; `mint` records `row["input"]` as the last
  input with its digest (762 to 767); `commit` (572 to 604) adds every file
  under the inputs directory; `main` (1804 to 1910) accepts `resume`,
  `--dry-run` and `SCOPE BRANCH [PLAN]` and nothing else; `Stopped`
  (77 to 105) prints `stopped stage=… record=… reason=…` after the detail.
- `measured: ls .dev/records/ladders/20260911T060939Z-ladder-307788/` →
  only `test-command.md`; the ladder record's `tests-fix` row (line 179)
  names as its input `/home/…/dispatch/20260911T062509Z-check-tests-codex-344d3f/out/SKEPTIC.md`,
  a file the skeptic wrote outside the worktree. That is the defect.
- `measured:` that check-tests record's envelope (`.dev/records/dispatches/20260911T062509Z-check-tests-codex-344d3f.json`
  lines 155 to 189): `artifacts` is `{"skeptic": "…/out/SKEPTIC.md"}`;
  the five findings carry the four fields, and every `claim` is prose
  ("Contract item 9 requires …"), with no quoted declared words and no
  quoted practiced evidence.
- `measured: ops/devlane/dispatch/launch.py`: `_render` (427 to 436)
  refuses only a missing template value; `_launch` resolves `job` and
  `role` at 1402 to 1406, renders at 1529 to 1532 after the job directory
  and snapshot exist (1508 to 1511); the `input` refusals at 1487 to 1501
  use `CORRECTION.refuse`, and `main` (2583 to 2588) prints a
  `CORRECTION.Refused` line and returns 2 while every other `Refused`
  returns `REFUSAL` (3) with a `launch.py: refusal:` prefix. The exit-2
  seam exists; the launcher's own refusals are still off the wire.
- `measured: ops/devlane/dispatch/CONTRACT.md` §Template values (865 to
  872) says `out` and `inputs` are supplied by the launcher; §Refusals
  (980 to 1014) lists `correction` and `arguments` as the two exit-2 rows
  and no `role` row.
- `measured: ops/conductor/registry/ladder.py.json` holds one row
  (`run` → `arguments`); `ops/conductor/tests/test_instrument_conventions.py`
  runs each row in a temporary `HOME`, cwd there, `input=""` (244 to 264),
  admits only tools under `ops/conductor/tools/` (line 200), and pins the
  ten seed files and eleven seed rows (55 to 94); `ladder.py` is not in
  the seed, so its file may gain a row.
- `measured: ops/conductor/tests/test_ladder_lever.py`: the stub
  dispatcher (215 to 491) gives `check-tests` an envelope with
  `findings: []`, zero counts and the planted verdict; the `skeptic_md`
  plant writes `SKEPTIC.md` at the worktree root and under the XDG
  dispatch store (372 to 383); `grep -c '"check-tests": "changes"'` → 7
  tests plant a `changes` verdict with no findings;
  `test_tests_fix_is_given_skeptic_md` (2674 to 2690) asserts a
  `SKEPTIC.md` path reaches `tests-fix`. 66 tests in the file; the ladder
  family was 133 tests at ladder 307788's code stage (record marker, line
  58 of its ladder record).
- `measured: ls ops/devlane/task/write_path.py` → absent.
- `measured: ops/devlane/task/tests/test_jobs.py` → 4 tests; they pin the
  spend clause on every harness prompt and the envelope clause on
  `author-tests` and `security-audit`. `test_job_outputs_render.py` and
  `outputs_support.py` pin the C2 rendering of a declared `SKEPTIC.md`
  output, a contract example, not the prompt; they stay green.
- `measured: ops/process/roles/test-skeptic.md` line 46 to 49: "Report in
  the repo's wire format (CONTRIB.md §Review protocol): VERDICT / STAMP /
  FINDINGS". The card and the prompt already disagree today, since the
  prompt demands one JSON object; the card is outside this work order (§7).
- `measured: wc -c .dev/ladder-inputs/scope-item31-20260911.scope.md` →
  779 bytes (cap 1024, `ops/lane.conf` `SCOPE_CAP`); the work order 8302
  and the discipline clause 1428, both tracked beside it.
- `measured: .github/workflows/ci.yml` → `runs-on: self-hosted`, checkout
  with `persist-credentials: false`, `~/.local/bin` prepended, term wall,
  `ruff check .`, `bash ops/bin/suites.sh`, `laneconf.py closure`,
  `laneconf.py literals`. `ops/bin/suites.sh` runs `python3 -m unittest
  discover -s <dir> -p 'test_*.py'` for `ops/devlane/{dispatch,harness,task,telemetry,hooks,fixtures,workflow}/tests`
  and `ops/conductor/tests`, concurrently, stdlib only.
- `measured:` in this job `python3 --version` → 3.12.3; `which gh` →
  `/usr/bin/gh`; `codex`, `grok`, `claude`, `ruff` under
  `/home/scientdb/.local/bin`; `test -w .git` → writable; `git remote` →
  none; `git branch --show-current` → empty (detached).
- `could not look:` `printenv HOME`, `curl -sI https://github.com` and
  `git show-ref` were refused by this job's sandbox. The isolated home and
  the absence of network are taken from the dispatch contract §Isolation
  (918 to 948) and the brief, cited as `contract:` below.

## 2. Decisions that fix the design

Each decision names the item it serves. A worker that finds one ambiguous
returns status `invalid` and names the line, rather than choosing.

D1. **The job entry (item 1).** `jobs.json` `check-tests` keeps adapter
`harness`, role `read`, snapshot `whole`, caps 1800 and constraints. Its
deliverable becomes "the skeptic's findings on the wire: the JSON envelope
on stdout, verdict `changes` exactly when any finding exists, each finding
a quotation pair; artifacts empty; no file written". Its prompt keeps
`{ref}`, `{inputs}`, `{scope}`, the role card, "Do not read any
implementation", the refute-by-default sentence, the spend clause and the
envelope clause (both pinned by `test_jobs.py`), and drops `{out}`:

    Adopt the role card at ops/process/roles/test-skeptic.md in the tree at {ref}. Judge the tests at {inputs} against the contract named here: {scope}. Do not read any implementation. Refute by default: a test survives only when you can name the broken implementation it would catch. Every refuted or weak test is one finding, a quotation pair: where is the test file and line; claim is `declared (<location>): <the contract or test words, verbatim>; practiced: <the test's evidence, verbatim>; misses: <the broken implementation the test would not catch>`; reproduce is a command against the tree. Verdict is changes exactly when findings is non-empty and approve otherwise; counts are the tally of findings. Write no file: artifacts is an empty object and the envelope on stdout is the whole deliverable. Review only — do not edit.

followed by the three shared clauses verbatim. The CONTRACT.md row (line
178) becomes "`check-tests` | the skeptic's findings on the wire: the JSON
envelope on stdout, verdict `changes` exactly when any finding exists,
each finding a quotation pair (§The skeptic's finding); `artifacts` empty;
no file written". No other job entry changes; a test pins the other eight
entries byte-for-byte against the ref.

D2. **The quotation-pair shape (item 2)** inside the four existing fields:

| field | rule |
|---|---|
| `severity` | `p1`, `p2` or `p3` |
| `where` | the practiced location: no whitespace, contains `/` or `.` (the test file, `:line` optional) |
| `claim` | `declared (<location>): <words verbatim>; practiced: <evidence verbatim>; misses: <the broken implementation the test would not catch>`; the declared location is non-empty and has no parentheses; the three texts are non-empty; the split is the first `; practiced: ` and the last `; misses: ` |
| `reproduce` | a non-empty command; `null` is refused (an opinion is not a finding) |

`where` carries the practiced location so the pair's second half is
located where the ledger already looks; the declared half carries its own
location in the claim. The parse is by `partition` and `rpartition`, not
a regex, because quoted code may contain any delimiter; whitespace is
already single-spaced by `envelope._text`. Verdict is `changes` when
`findings` is non-empty and `approve` when it is empty (status `ok` is
already required by `load_envelope`). Counts equal the tally with
`opinions` 0. `artifacts` is exactly `{}`.

D3. **The check-tests stop (item 3).** `ladder.py` gains
`validate_check_tests(envelope) -> None`, raising `Refused("envelope", …)`
on the first violation in this order: artifacts, findings is a list, each
finding's fields, severity, where, claim, reproduce, counts, verdict. The
line names the field:

    envelope: expected artifacts {} on check-tests (no file is written); found keys ['skeptic']; needed an envelope on stdout and no file
    envelope: expected findings[2].claim as declared (<location>): <words>; practiced: <evidence>; misses: <implementation>; found "Contract item 9 requires a fresh check …"; needed both quotes, the declared location and the missed implementation
    envelope: expected findings[0].reproduce as a command; found null; needed a reproduce command (a finding without one is an opinion)
    envelope: expected counts equal to the tally of findings {'p1': 1, …}; found {'p1': 0, …}; needed counts recomputed from findings
    envelope: expected verdict changes with 3 findings (approve with none); found approve; needed verdict changes exactly when findings is non-empty

`finish` calls it for `check-tests` after `await_result` (or the
already-closed pair on resume) and before `ledger_result`, so a malformed
envelope is never imported and the ladder never advances. The `Refused` is
converted to `Stopped("check-tests", record_id, "envelope", detail=line)`:
exit 3, the wire line as the last reading, then `stopped stage=check-tests
record=<id> reason=envelope`; the stage row gets `reason: envelope` and
`envelope: {"field": "<dotted field>", "refusal": "<line>"}`. Never a
flake: `execute(resume=True)` sees `row["reason"] == "envelope"` and stops
again with the same line instead of relaunching; only `resume LADDER_ID
--retry check-tests --because TEXT` (LD-19, already in the driver) grants
one further attempt, recorded on the row. The exit code is 3 and not 2
because the ladder contract's stops table already classes "records an
invalid envelope" as a mid-act stop with a durable record (ladder-lever.md
line 109); the refusal itself, reached before any act, is exit 2 through
the verb of D4.

D4. **The verb and the registry row (item 7, driver).** `ladder.py` gains
a read verb `check-envelope PATH|-`: reads a dispatch record (uses
`result.envelope`) or a bare envelope, JSON, from the path or from stdin;
exit 0 and no output when D2 and D3 hold; the `envelope` refusal on the
wire (exit 2, one stderr line, empty stdout) otherwise; empty stdin
refuses `envelope: expected a check-tests dispatch record or envelope as
JSON on stdin; found empty stdin; needed pipe the record JSON or name its
path`. `ops/conductor/registry/ladder.py.json` gains the row
`{"argv": ["check-envelope", "-"], "class": "envelope", "identity": false}`,
hermetic by construction (the gate runs rows with `input=""`). The driver
and the verb call one function.

D5. **The custody file (item 4).** `inputs_for("tests-fix")` no longer
appends the check-tests record path or any artifact. It loads the
check-tests record, runs `validate_check_tests` again (a stop, as D3, if
the bytes changed), and writes `<inputs_dir>/skeptic-findings.md`
through `make_input`: first line `check-tests envelope, record <id>`,
then the validated envelope as `json.dumps(indent=2, sort_keys=True)`,
the same shape `audit_envelope_input` gives the audit fix stages. It is
the last input, so `mint` records it as the stage row's `input` with path
and digest, and `commit` carries it with the record. The record id is in
the dispatched bytes twice (the header and `--follows`), so guarantee 1
holds unchanged. `<inputs_dir>` is `.dev/records/ladders/<id>/`, as today.

D6. **The custody refusal (item 4).** `make_input(name, body)` becomes
the guarded writer for all seven of its call sites: `name` must be a bare
basename (no `/`, not `..`); the inputs directory and every path component
between it and the worktree must not be a symlink; the target must not be
a symlink or a non-regular file; the file is opened with
`O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW`; after the write, `lstat` is a
regular file and its resolved path lies under the resolved inputs
directory. A violation raises `Refused("custody", …)`, converted by the
caller to `Stopped(stage, reason="custody", detail=line)`, exit 3, nothing
written and no symlink followed:

    custody: expected a regular file under <worktree>/.dev/records/ladders/<id>; found <path> is a symlink to <target>; needed remove the symlink and resume

D7. **The read-role guard (item 5).** `ops/devlane/task/write_path.py`
(stdlib) exposes `write_instruction(text) -> str | None`: split the
prompt into sentences on `.`, `;`, `!`, `?` and newlines; a sentence is a
positive write instruction when it carries a write verb from the declared
set `write, save, create, store, emit, put, append, dump` as a verb
(sentence start, or after `and`/`then`/`,`), a path-shaped token in the
same sentence (`{out}`-rooted, or containing `/`, or ending in a file
suffix), and no negation token (`not`, `no`, `never`, `don't`, `without`,
`nothing`) before the path token; the first such sentence is returned.
This is shape, not a word list: "SKEPTIC.md" alone, "out/" alone, or
"Write no file" do not fire; "Do not write to {out}/X.md" does not fire;
"Write the report to {out}/SKEPTIC.md and name that path in artifacts"
fires. Its CLI `python3 ops/devlane/task/write_path.py [JOB]` checks one
or every read-role job in `jobs.json`: exit 0 silent, or the wire refusal
`role: expected a read-role prompt with no instruction to write a path;
found job check-tests: "Write the report to {out}/SKEPTIC.md and name that
path in artifacts"; needed drop the sentence from the prompt or declare
the job a write role`, exit 2; an unknown job refuses `job`. `launch.py`
loads it by path beside `CORRECTION` and, right after `role = job.get("role")`
(line 1406) and before any directory exists, refuses through
`CORRECTION.refuse("role", …)` when the role is `read` and a sentence is
found, so the refusal is exit 2 on the founding wire through the existing
seam and no job directory, record or home is made. The template is judged,
not the rendered text, because `{out}` is already path-shaped and the
guard must stand before the mint. `run.py`'s dormant `render` is not
changed: the task contract (lines 198 to 204) names `launch.py` as the
execution service, and `run.render` already refuses `check-tests` for its
`{out}` slot at the ref.

D8. **Consequence of D7 at the ref, declared (see F1).** `plan` and
`adjudicate` are read-role jobs whose prompts say "Write the plan to
{out}/PLAN.md" and "Write the ruling to {out}/RULING.md" (measured,
`jobs.json` lines 60 and 95). Under item 5 as written, both refuse `role`
at the launcher once slice 3 lands, until their deliverables move onto
the wire in a work order of their own (the `plan` job already has the
inline exception in `envelope.validate`, lines 488 to 505). This plan
does not change those prompts (their deliverables are outside items 1 to
8) and orders the guard last, so the owner can hold slice 3 or amend item
5 before it is dispatched. The ladder itself never dispatches `plan` or
`adjudicate`, so slices 1 to 3 run to their draft PRs regardless.

D9. **The contract rows (items 1, 3, 4, 5, 7).** Slice 1 writes: the
task CONTRACT.md row of D1 plus a short subsection "The skeptic's finding"
quoting the D2 grammar once; the ladder-lever.md stage-table row for
`tests-fix` ("scope, plan, `skeptic-findings.md` written by the driver
from the validated check-tests envelope"), a paragraph "The check-tests
stop" (D3, never retried, `--retry` is the only further attempt), the
verb `check-envelope` under §Instrument, stops-table rows `envelope` and
`custody` (exit 3, last output the wire line then the stopped line), and
the record's `envelope` field; the dispatch CONTRACT.md §Refusals row
`role` (exit 2, founding wire; expected, found and needed as in D7).
Nothing else in either contract moves.

D10. **The test fixture (slices 2 and 3).** The frozen sets are authored
by the tests stage. For slice 2 the tests producer extends the shared stub
in `test_ladder_lever.py` (test support, not a bucket file): a
`check-tests` verdict of `changes` carries one well-formed D2 finding with
counts `p2: 1`, and a `skeptic_envelope` plant key overrides envelope
fields for the malformed cases. The seven tests that plant `changes` with
no findings then stay green under the new driver; the salvaged
`test_check_tests_json.py`, `test_jobs.py` (16) and
`test_ladder_audit_fix.py` (3) from `lane/check-tests-json@fe2e474` are
inputs to that producer, never the frozen set by themselves (scope
§Salvage).

D11. **Bucketing.** Three S slices, each its own ladder run and its own
draft PR, ordered contracts first, then the driver with the job entry,
then the guard. The scope declared "S in two buckets: the job definition
with its render guard; the driver's validation and custody write" over
seven files. That split puts five files in one bucket (the job entry, the
guard module, the launcher hook and two contract files), which is not S,
and puts the guard, with the D8 blast radius, in the same PR as the job
entry the ladder needs at once. The declared row stays what these slices
are measured against (§8).

D12. **Interim states, declared.** After slice 1: contracts describe a
driver that does not exist yet; the pins are red only in the tests each
slice lands. After slice 2: the skeptic returns the envelope alone and the
driver validates it; `plan` and `adjudicate` still dispatch. After slice
3: item 5 holds, with D8's consequence.

## 3. Slices

Ordered by value per cost with dependencies respected. Every slice lands
green alone: its tests are red only for the reasons in §6, and its bucket
files are the only paths its implementation may touch.

### Slice 1 — `skeptic-contracts` (S) — its own PR, first

Files: `ops/devlane/task/CONTRACT.md`, `ops/conductor/ladder-lever.md`,
`ops/devlane/dispatch/CONTRACT.md`. Contracts first: the founding rule.

Writes: D9. Unblocks: slices 2 and 3 (their tests are written from these
words). Risk class: contract, so its own slice. Edges touched: none live;
it declares the edges the later slices verify (`ladder.py → dispatch
record envelope` typed by D2; `ladder.py → .dev/records/ladders/<id>/`
typed by D6; `launch.py → write_path.py` typed by D7). Guarantees to keep
from `docs/verified-couplings.md`: closure both directions (every declared
row below has a counterparty slice; the `role` row's counterparty is slice
3, the `envelope` and `custody` rows' counterparty is slice 2). Depends
on: nothing. Green alone: its tests are document pins.

### Slice 2 — `skeptic-driver` (S) — its own PR, the value

Files: `ops/devlane/task/jobs.json`, `ops/conductor/tools/ladder.py`,
`ops/conductor/registry/ladder.py.json`.

Writes: D1 (the `check-tests` entry only), D2 to D6 in the driver, the
verb and the registry row of D4. Unblocks: items 1 to 4, 6 and 7 for the
driver; every ladder after it hands `tests-fix` a file the driver wrote.
Risk class: the driver builds the dispatcher's argv (`dispatch_args`) and
the inputs it names; the job entry is data the launcher renders. Edges:
`ladder.py → dispatch record` (reads `result.envelope`, now typed by D2),
`ladder.py → dispatch.sh` (`--input <inputs_dir>/skeptic-findings.md`
replaces the record path and the artifact path), `ladder.py → findings.py
import` (unchanged; imports only what passed D3), `launch.py → jobs.json`
(the prompt renders with `{ref}`, `{inputs}`, `{scope}` only; `{out}` is
still supplied and simply unused). Guarantees: shape (D2, checked
mechanically at the stop and by the verb), behavior (planted malformed
envelopes stop, a clean one advances; a planted symlink is refused, a
regular file is written), freshness (the registry row runs in CI on every
push), custody 1 (the check-tests id stays in the dispatched bytes; the
skeptic's own text never enters `implementation_markers`), lineage 2 and
selection 3 (untouched), wire 4 (exit 3 with the wire line then the
stopped line; exit 2 through the verb). Depends on: slice 1. Green alone:
the ladder suite stubs `dispatch.sh`, `launch.py`, `land.py` and
`findings.py` (measured 1061 to 1080), and the conventions gate runs the
new row against the real tool with empty stdin.

Interim: between slice 2's landing and slice 3's, a read-role prompt with
a write instruction still renders; only `check-tests` has none.

### Slice 3 — `read-role-guard` (S) — its own PR, held for D8

Files: `ops/devlane/task/write_path.py`, `ops/devlane/dispatch/launch.py`.

Writes: D7. Unblocks: item 5, and item 8's third finding as contract.
Risk class: the launcher, before its argv building (the guard stands
before the mint, so `_argv` is untouched); the task app gains a module.
Edges: `launch.py → write_path.py` (by path, like `CORRECTION`; the task
app imports nothing from dispatch, as its contract requires, lines 700 to
705), `launch.py → jobs.json` (the template is judged before render).
Guarantees: shape (a sentence and a job name in the line), behavior
(planted both ways: the ref's sentence fires, D1's prompt and the negated
forms stay silent), permission (a read role gains no write; the guard
adds no grant), wire 4 (exit 2 through the `CORRECTION.Refused` seam, no
job directory). Depends on: slices 1 and 2 (after slice 2, `check-tests`
is the silent neighbour; before it, the guard would refuse the ladder's
own skeptic stage). Green alone: `launch_support._TempLaunch` fakes the
CLIs; the guard's tests run the module directly. Dispatch after the owner
has read F1.

## 4. Walkthrough of the first run

The first run is slice 1's ladder. Command, from the conductor's main
checkout on `dev`, `WF_AGENT` exported, the branch checked out in
`../wt/ag-skeptic-contracts-20260911` (`WORKTREE_ROOT='../wt'`, measured
`ops/lane.conf`):

    ops/bin/ladder.sh .dev/ladder-inputs/scope-item31-20260911.scope.md \
        lane/skeptic-contracts-20260911 .dev/ladder-inputs/plan-skeptic-contracts.md \
        --input .dev/ladder-inputs/scope-item31-20260911.md \
        --input .dev/ladder-inputs/scope-discipline.md

The plan file for a run carries exactly that slice's two machine lines
(§9), copied by the conductor: a plan carrying every slice's lines gives
the driver three `code` buckets (`parse_plan`, lines 370 to 402, measured).
The two `--input` files reach every stage beside the scope (measured
`inputs_for` line 1129 to 1130), so the work order the scope sentence
cites is in every worker's `in/`.

Preconditions (`validate_preconditions`, 1680 to 1748): scope at most
1024 bytes (779 measured); worktree clean; `WF_AGENT`, `LANE_AUTHOR` and
the worktree git identity in `Name <address>` form; `gh` on PATH
(measured); every stage job in `jobs.json` (measured, nine). A failure is
exit 2 on the wire before any dispatch.

Stage `tests` (grok, `author-tests`). The dispatcher resolves
`MODEL_GROK`/`EFFORT_GROK` from `ops/lane.conf`; the driver records the
dry-run selection and later checks the minted record against it (stop
`model`). The launcher mints a fresh repository: `git init`, fetch of the
lineage branch and the sha, `checkout --detach` (measured `_snapshot`, 408
to 420); the snapshot has no remote and a detached HEAD, exactly as this
job's snapshot measures. Grok runs with `HOME` and `GROK_HOME` at
`<job>/home/grok` holding only `auth.json` (contract: §Isolation, line
922), so it cannot find a global git config (the launcher also sets
`GIT_CONFIG_GLOBAL` to `/dev/null`, measured `_git` 117 to 135), any `gh`
credential, its own settings or skills; `--disable-web-search` is on its
argv (contract, line 947); there is no network (brief; could not look
here). What the worker then cannot do, and the refusal that stands: it
cannot push or call `gh` (no credential, no remote: the commands fail and
the prompt says to commit locally, or write to disk if commit is denied);
it cannot `pip install` (the suites are stdlib by `suites.sh`); it cannot
read the implementation (custody withholds implementation record ids from
the input bytes, `verify_custody` 1362 to 1382, stop `withheld`; Graft is
disabled for the tests and check-tests jobs, `GRAFT_INSTALL=''` and
`_verify_graft` line 87). Its prompt demands each test proven red for its
own assertion and committed at once. For slice 1 the tests are document
pins (§6), red because the rows are absent, measured. Where the worker
could improvise: pin prose it invents instead of D9's words (the skeptic
refutes it; the code stage cannot make an invented pin true without
leaving the bucket); name a test file outside a `tests/` directory (no
command is derived from it: `derive_command`, 1257 to 1311, stop
`artifacts` if none remain); give an absolute path outside a snapshot
(LD-15, stop `artifacts`); edit `ladder-lever.md` itself to make a pin
green (nothing stops a tests stage from landing a bucket file, F9; the
skeptic and both audits are the guard, and the contract pin would be a
finding with the record as evidence).

Stage `check-tests` (codex, skeptic). On slice 1's and slice 2's ladders
the skeptic still runs under the ref's prompt: `CODEX_HOME=<job>/home/codex`
with only `auth.json` (contract, 921), sandbox `workspace-write` with
`out/` the only writable root, snapshot write bits stripped, `TMPDIR` a
real `out/tmp` (contract, 924 to 937; record 344d3f argv measured). It
writes `out/SKEPTIC.md` and names it in artifacts; the old driver reads
it back. The role card demands a named broken implementation per
surviving test and refuses a red that is a collection or import error. A
`changes` verdict runs `tests-fix` once; a leaked implementation marker
stops `withheld`. From slice 3's ladder on (after slice 2 merged), the
skeptic runs under D1's prompt: a worker that writes a file anyway and
names it in `artifacts` is stopped by the driver, `envelope` naming
`artifacts`; a worker that returns prose claims is stopped naming
`findings[i].claim`; a finding without a `reproduce` command is stopped
naming `findings[i].reproduce`; a `changes` with no findings is stopped
naming `verdict`. The stop is not retried; the conductor reads the line,
and either `resume --retry check-tests --because <the worker's, not the
driver's, fault>` or leaves the ladder stopped with the record as
evidence.

Stage `code` (codex, `implement`). The scope handed over is the derived
test command: one `python3 -m unittest discover -s <dir> -p <file>` per
test module the tests envelope named under a `tests/` directory, joined by
`&&` (measured). The worker runs inside the snapshot with `ruff` reachable
only because the conductor's PATH carries `~/.local/bin` (measured here;
CI prepends it). The snapshot's git directory is read-only to a codex
worker (record 307788's code marker: "Git commit was unavailable because
.git is read-only; the launcher fallback message is in out/COMMIT_MSG"),
so the worker writes `out/COMMIT_MSG` and the launcher commits its tree
(prompt, measured `jobs.json` line 84). Improvisations and the refusals:
editing a test file lands a path outside the bucket, stop `bucket`
(measured 1037 to 1064); in slice 2, editing a `plan` or `adjudicate`
prompt "while there" is inside `jobs.json` and so inside the bucket, but
the entry-pinning test of §6 goes red and status must be `invalid`;
making the refusal a `Stopped` with exit 2, or a `Refused` with exit 3,
fails the wire tests; adding a `findings` field to the envelope schema
lands `envelope.py` outside the bucket; in slice 3, exempting `plan` and
`adjudicate` by name is a list, not a shape, and the renamed-job test of
§6 catches it; touching `_argv` is inside `launch.py` and so inside the
bucket, but `test_launch_skeptic_write.py` and the argv witnesses pin the
argv (measured, 181 to 231); a status `ok` with the command failing is
refused at `load_envelope`. The landing goes through `land.py` with the
lane author and the ran model as co-author; a sha not descending from the
stage base stops `lineage`.

Stages `security` and `adversarial` (codex with
`MODEL_CODEX_SECURITY_AUDIT`; grok), back to back, read only. Each finding
without a reproduce command is an opinion by its own prompt. Under the
discipline clause each finding quotes the contract item it violates or is
an observation; item 8 says the three 2026-09-04 findings are measured
against items 2 to 5 here, not rediscovered. The driver imports both
envelopes with `findings.py import` and commits the export. Before
`fix-tests` the driver runs `findings.py cited` on every key and stops
`undisposed` naming the keys until the conductor has disposed each with a
citation (`contract item N of .dev/ladder-inputs/scope-item31-20260911.md: …`);
the correction gate at the launcher refuses `correction` on any key not
disposed before the mint stamp (measured `require_cited` 684 to 705 and
`launch.py` 1477 to 1486).

Stages `fix-tests`, `fix-code`, `security-re`, only if an audit says
`changes`: one fix round, then the re-audit; `changes` there is exit 1
with the ladder stopped at `security-re`.

Stage `pr`: `git push origin` and `gh pr create --draft` from the
conductor's worktree, which has network and credentials; the snapshot
never does.

CI on the self-hosted runner (measured `ci.yml`): checkout without
credentials, `~/.local/bin` on PATH, term wall (refuses with no
`TERM_WALL` variable, never passes), `ruff check .` under the pinned
range, `bash ops/bin/suites.sh` (each suite with the repository root as
cwd; the conventions gate invokes every registry row, so slice 2's
`check-envelope -` row runs there with empty stdin), then `laneconf.py
closure` and `literals`: new code must read lane names through `laneconf`
and must not embed `agentscient`, `dev` or a home path (the driver's lines
carry the resolved inputs directory at run time, never a literal). The
`app` job is the Symfony gate and reads none of this lane's files.

## 5. Assumptions: measured, refused, or a finding

| # | assumption | status |
|---|---|---|
| A1 | a finding has exactly four fields and cannot grow | measured (`envelope.py` 473 to 480); D2 |
| A2 | `_text` single-spaces a claim, so a one-line grammar is safe | measured (line 295 to 298) |
| A3 | the launcher accepts counts that disagree with findings | contract (task CONTRACT.md 126 to 132: launch uses `_schema_valid`); D3 checks counts itself |
| A4 | the driver retries a stopped stage on resume until attempt 2 | measured (1199 to 1211); D3 |
| A5 | `--retry STAGE --because TEXT` exists and is spent once | measured (131 to 166, 1234 to 1250) |
| A6 | `make_input` follows symlinks | measured (642 to 646: `write_text`); D6 |
| A7 | the last input is the recorded one | measured (762 to 767); D5 |
| A8 | the exit-2 seam in the launcher is `CORRECTION.Refused` | measured (2583 to 2585); D7 |
| A9 | the conventions gate runs rows with empty stdin in a temp cwd | measured (244 to 264); D4 |
| A10 | `ladder.py.json` may gain a row | measured (seed pins 55 to 94 exclude it) |
| A11 | the registry admits only `ops/conductor/tools/` | measured (line 200); F2 |
| A12 | `findings.py import` copies `claim` verbatim and accepts check-tests | measured (42 to 44, 225 to 243); item 6 |
| A13 | the stub gives check-tests no findings on a `changes` verdict | measured (398 to 419); D10 |
| A14 | `plan` and `adjudicate` prompts carry a positive write instruction | measured (`jobs.json` 60, 95); D8, F1 |
| A15 | the scope fits the cap | measured 779 bytes |
| A16 | codex read roles get `workspace-write` with `out/` writable | contract (924 to 937); record 344d3f argv measured |
| A17 | no network in a job | could not look; contract (947 to 948) and brief |
| A18 | isolated homes per harness | could not look; contract (918 to 922) |
| A19 | the snapshot git directory is read-only to a codex worker | record 307788 marker line 12; measured here `test -w .git` is writable under a claude read job, so this is per harness, not universal |
| A20 | `{out}` stays supplied by the launcher after D1 drops it | measured (1529 to 1531: the value is set regardless); a template naming nothing missing renders |
| A21 | the ladder never dispatches `plan` or `adjudicate` | measured (`DISPATCH_STAGES` 28 to 38) |
| A22 | slice 2's implement run fits ten minutes | not measured; F8 |
| A23 | `write_instruction` on D1's prompt returns None | refusal: the tests plant D1's prompt and the ref's prompt both ways |

## 6. Tests, by file, and why each is red at the ref

All new files sit under existing `tests/` directories so the driver
derives their command; the tests stage lists every file in `artifacts`
and proves each red on its own assertion.

Slice 1
- `ops/devlane/task/tests/test_check_tests_contract_row.py`: pins the
  CONTRACT.md `check-tests` row ("the JSON envelope on stdout", "quotation
  pair", "`artifacts` empty", "no file written") and the grammar
  subsection. Red: line 178 says "a skeptic's report at `out/SKEPTIC.md`"
  (measured); no grammar subsection.
- `ops/conductor/tests/test_ladder_lever_skeptic_contract.py`: pins in
  ladder-lever.md the `tests-fix` row naming `skeptic-findings.md` and no
  `SKEPTIC.md`, the stops rows `envelope` and `custody`, "never retried",
  the verb `check-envelope`, the record's `envelope` field. Red: `grep -c
  SKEPTIC.md ops/conductor/ladder-lever.md` → 1; no such rows (measured
  stops table 104 to 110).
- `ops/devlane/dispatch/tests/test_launch_role_contract.py`: pins the
  §Refusals row `role` with "exit 2, founding wire", the job and the
  sentence in the found text. Red: no `role` row (measured 989 to 1014).

Slice 2
- `ops/devlane/task/tests/test_check_tests_job.py`: `check-tests` keeps
  role `read`, snapshot `whole`, caps 1800; the prompt has no `{out}`,
  keeps `{ref}`, `{inputs}`, `{scope}`, carries the D2 grammar, "Write no
  file", "artifacts is an empty object", the spend and envelope clauses;
  the deliverable names the envelope on stdout; the other eight entries
  equal a copy taken at the ref. Red: the prompt says "Write the report to
  {out}/SKEPTIC.md" (measured).
- `ops/conductor/tests/test_ladder_skeptic_envelope.py` (on
  `_LadderFixture`, with D10's stub): a well-formed `changes` envelope
  advances to `tests-fix`; each malformed field (artifacts non-empty,
  findings not a list, a finding with a fifth field, bad severity,
  whitespace in `where`, prose claim, missing `; misses: `, null
  reproduce, counts off by one, `approve` with a finding, `changes` with
  none) stops with exit 3, the last two lines `envelope: expected …`
  naming the field and `stopped stage=check-tests record=<id>
  reason=envelope`, no `tests-fix` dispatch, no `import` in the findings
  argv log for that stage, `reason` and `envelope.field` on the row; a
  plain `resume` does not relaunch (dispatch count for `check-tests` stays
  1) and stops with the same line; `resume --retry check-tests --because
  x` relaunches once. Red: `finish` advances on any status-`ok` envelope
  (measured 1106 to 1121) and resume relaunches (1199 to 1213).
- `ops/conductor/tests/test_ladder_skeptic_custody.py`: `tests-fix`
  argv carries `--input <worktree>/.dev/records/ladders/<id>/skeptic-findings.md`
  and no path named `SKEPTIC.md` even when the plant writes one; the file
  is a regular file whose first line names the check-tests record and
  whose body is the validated envelope; the row's `input.path` and
  `input.sha256` equal the file and its digest; the file is in the record
  commit; a planted symlink at that name, and a planted symlinked inputs
  directory, each stop with `custody: expected …` and `reason=custody`,
  the symlink target untouched and the symlink still in place. Red: the
  driver passes the `SKEPTIC.md` artifact (1145 to 1150) and `make_input`
  writes through a symlink (642 to 646).
- `ops/conductor/tests/test_ladder_check_envelope_verb.py`: the staged
  tool with `check-envelope -` and empty stdin → exit 2, one stderr line
  starting `envelope:`, empty stdout; a valid record on stdin → exit 0
  silent; a record with a prose claim → exit 2 naming
  `findings[1].claim`; a path argument works the same; the registry file
  carries the D4 row (parsed with `test_instrument_conventions.read_registry`).
  Red: the verb is an `arguments` refusal today (measured 1864 to 1870);
  the registry has one row.
- `ops/conductor/tests/test_ladder_lever.py`: D10's stub extension, and
  `test_tests_fix_is_given_skeptic_md` rewritten to assert the custody
  file (its present assertion contradicts item 4). Red after rewrite:
  the same reason as the custody file above.

Slice 3
- `ops/devlane/task/tests/test_write_path.py`: `write_instruction`
  planted both ways: the ref's check-tests sentence (quoted in the test) →
  that sentence; D1's prompt → None; "Do not write to {out}/X.md" → None;
  "Write no file" → None; a path with no verb, and a verb with no path →
  None; a write verb after "and" with a path → the sentence; the CLI on a
  planted `jobs.json` copy with the ref's entry → exit 2, `role:` line
  naming the job and the sentence, empty stdout; on a copy with D1's entry
  → exit 0; an unknown job → `job:`; a write-role job with a write sentence
  → exit 0; each run under a temporary `HOME`. Red: the module is absent
  (measured).
- `ops/devlane/dispatch/tests/test_launch_role_guard.py` (on
  `launch_support._TempLaunch`, planting a read-role job entry carrying a
  write sentence, and a renamed twin of `check-tests` with D1's prompt):
  the planted job → exit 2, one bare `role:` stderr line, empty stdout, no
  job directory, no record file, the fake CLI's start witness absent; the
  renamed twin launches; a write-role job with a write sentence launches;
  `--override role:x` is refused `override`. Red: the launcher renders
  the sentence and mints today (measured 1529 to 1532).

## 7. Findings against this plan and the tree

- F1 (contract, D8): item 5 as written refuses `plan` and `adjudicate` at
  render once slice 3 lands (measured A14). Their conversion to the wire
  is outside items 1 to 8. The owner decides before slice 3 is dispatched:
  accept the outage until a follow-up work order (the `plan` job's inline
  exception already exists), or amend item 5 to the jobs whose deliverable
  is on the wire. Slices 1 and 2 do not depend on the answer.
- F2 (tree): the conformance registry admits only `ops/conductor/tools/`
  (A11), so `write_path.py` and `launch.py` cannot carry a registry row for
  `role`. Item 7's row for the driver is D4; for the guard the wire is
  asserted by `test_write_path.py` and `test_launch_role_guard.py` under a
  temporary `HOME`, and the missing devlane registry is recorded here, not
  built (a new gate would widen the work order).
- F3 (tree, observation): the role card `test-skeptic.md` still says
  "Report in the repo's wire format (CONTRIB.md §Review protocol)"; the
  prompt already overrides it with the envelope clause today. Not in this
  work order's files; a hypocrisy concern would quote the pair.
- F4 (tree, observation): `ops/conductor/lane-policy.md` (1 mention) and
  `ops/conductor/lessons/conducting.md` (2) name `SKEPTIC.md`; the first
  is contract prose about output declarations, the second a record. Left
  as they stand (boundary: render-slot prose; records keep provenance).
- F5 (plan): A17 and A18 are not measured in this job; they rest on the
  dispatch contract and the brief, as stated. A19 is measured from a
  record, not this job.
- F6 (plan): slice 2's tests stage edits the shared stub in
  `test_ladder_lever.py` (D10). It is test support, outside every bucket,
  and the seven `changes`-without-findings plants would otherwise go red
  under the new driver for a reason no contract names.
- F7 (plan): item 7 says every new refusal is exit 2; the mid-ladder
  `envelope` and `custody` outcomes are stops at exit 3 with the wire line
  as the last reading (D3, D6), because the ladder contract owns that
  classification; the exit-2 refusal proper is reached through the verb of
  D4. The reading is declared here so an audit measures it against the
  contract rather than finding it.
- F8 (plan): slice 2's implement run (validation, guarded writer, verb,
  resume rule, about 150 lines in the driver, plus the job entry) may pass
  ten minutes; implement runs measured 6.7 to 16 minutes in
  `.dev/wip/calibration-buckets.md.txt`. By the owner's rule the row may
  measure M by minutes while S by files; the calibration rows decide.
- F9 (tree): a tests stage lands whatever it commits; the bucket check
  (`land_result`, 1037 to 1064) runs only for `code` stages. A tests
  worker that edits a bucket file lands it; the skeptic and the audits are
  the guard. Recorded; no fix here.
- F10 (tree): the launcher's other refusals stay at exit 3 with a prefix
  (measured 2586 to 2588); this plan adds one exit-2 refusal through the
  existing seam and leaves the reconciliation where the dispatch contract
  leaves it (982 to 985).

## 8. Calibration rows (declared; the driver writes the measured ones)

| slice | plan said | stage | minutes | files / tests |
|:--|:--|:--|--:|:--|
| skeptic-contracts | S | tests | 10 | 3 test files |
| skeptic-contracts | S | skeptic | 6 | |
| skeptic-contracts | S | tests-fix | 8 | |
| skeptic-contracts | S | implement | 8 | 3 files |
| skeptic-contracts | S | security | 7 | |
| skeptic-contracts | S | adversarial | 8 | |
| skeptic-contracts | S | fix-tests | 8 | |
| skeptic-contracts | S | fix-code | 6 | |
| skeptic-contracts | S | security-re | 6 | |
| skeptic-driver | S | tests | 23 | 4 test files, 1 support edit |
| skeptic-driver | S | skeptic | 11 | |
| skeptic-driver | S | tests-fix | 20 | |
| skeptic-driver | S | implement | 12 | 3 files |
| skeptic-driver | S | security | 8 | |
| skeptic-driver | S | adversarial | 10 | |
| skeptic-driver | S | fix-tests | 18 | |
| skeptic-driver | S | fix-code | 12 | |
| skeptic-driver | S | security-re | 8 | |
| read-role-guard | S | tests | 18 | 2 test files |
| read-role-guard | S | skeptic | 9 | |
| read-role-guard | S | tests-fix | 15 | |
| read-role-guard | S | implement | 9 | 2 files |
| read-role-guard | S | security | 8 | |
| read-role-guard | S | adversarial | 9 | |
| read-role-guard | S | fix-tests | 15 | |
| read-role-guard | S | fix-code | 9 | |
| read-role-guard | S | security-re | 7 | |

Reading: the scope declared one S in two buckets over seven files; this
plan declares three S slices over eight files (D11), and the declared row
is what they are measured against. Minutes come from the measured rows in
`.dev/wip/calibration-buckets.md.txt` (tests 13 to 23, skeptic 6 to 11,
fix rounds 18 to 26, implement 7 to 16, audits 7 to 10) and the ladder
307788 rows (tests 14.8, skeptic 5.3, tests-fix 17.0, code 6.7, security
6.4).

## 9. Machine lines

One slice's two lines per ladder run, copied to
`.dev/ladder-inputs/plan-<name>.md`. Bucket files are the only paths a
landed implementation may touch; tests are outside every bucket on purpose.

slice	skeptic-driver	S
bucket	skeptic-driver	S	ops/devlane/task/jobs.json ops/conductor/tools/ladder.py ops/conductor/registry/ladder.py.json
