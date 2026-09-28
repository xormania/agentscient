# Plan — fixture apps: the lever, the manifest, and four apps in five S slices

Planned against the tree at `c52bc60f348b021123d6d5c25c8b071a3617a46a`
(2026-09-04). Scope: `in/scope-fixture-apps.md` (owner, 2026-09-04),
read whole. This plan says how; it moves none of the scope's
boundaries. Every fact below about the tree was produced by a command
against that ref during planning; where the plan could not measure, it
says so.

## What the tree holds today, measured

| claim | how measured, at c52bc60 |
|---|---|
| no `ops/bin/fixture.sh`, no `ops/devlane/fixtures/apps/`, no `FAULTS.json`, no `FAULT-KINDS.md` | `ls ops/bin`; `find ops/devlane/fixtures`; `grep -rIl "FAULTS.json\|FAULT-KINDS" .` returns nothing |
| no lane conf file and no toolchain profile in the tree; the lane conf is named only in two idea records | `grep -rIl -e "lane-conf" -e "lane conf" .` → `I-012`, `I-014`, and one row of `findings.jsonl`; `grep -rIl -i "toolchain profile" .` → nothing |
| the probes lever `ops/conductor/tools/probes.py` is a contract without an instrument | `ls ops/conductor/tools/probes.py` → no such file; contract at `ops/conductor/probes-lever.md` |
| `findings.py` has no test suite of its own; it is in the conformance registry with one row (`disposition … NOSUCH#1` → class `key`) | `ls ops/conductor/tests \| grep -c findings` → 0; `test_instrument_conventions.py` REGISTRY |
| the findings ledger imports only from `.dev/records/dispatches/*.json` of jobs `check-tests`, `security-audit`, `adversarial-review`, keyed `<record>#<n>`, columns fixed | `findings.py` lines 33–45, 78–96 |
| a reviewer's `where` carries one or several `path:start-end` spans, joined by `;`, `,` or `↔` | `grep -o '"where": …'` over the two security-audit records of 2026-09-03/04 |
| the envelope's finding fields are `severity, where, claim, reproduce`; severities `p1 p2 p3` | `ops/devlane/task/envelope.py` FINDING_FIELDS, SEVERITIES |
| `suites.sh` discovers `ops/devlane/{dispatch,harness,task,telemetry,hooks,fixtures,workflow}/tests`, `ops/conductor/tests`, `.claude/skills/pr-overview/tests`; a new file under `ops/devlane/fixtures/tests/` runs in CI with no wiring | `ops/bin/suites.sh` line 17 |
| root CI runs `ruff check .` over the whole tree with the `S` family selected, and the term wall over every tracked file; PHPUnit reads `tests` and `packages/*/tests` only; `php -l` reads `src packages` only | `.github/workflows/ci.yml`; `ruff.toml`; `phpunit.dist.xml` lines 22–35 |
| the CI runner's declared toolchain is php, composer, python3, cue, jq, ruff; no cargo | `ci.yml` step "the host toolchain the self-hosted runner relies on" |
| `dispatch.sh --dry-run` needs a sourceable `dispatch.conf`, a `launch.py` at `ops/devlane/dispatch/launch.py` relative to the script, and either `--branch` in a worktree or `--worktree DIR`; it prints one JSON line with `argv`, `env`, `launcher` | `ops/conductor/tools/dispatch.sh` lines 10–68, 184–202 |
| `dispatch.sh` refuses with exit 3 and a `dispatch: refusal:` prefix, not the exit-2 one-line wire | `dispatch.sh` lines 4–7; a standing divergence, not this batch's to fix |
| the conformance registry invokes `sys.executable <tool>`; a bash lever cannot join it as written | `test_instrument_conventions.py` lines 54–55 |
| the vocabulary wall is not a CI step at this ref; the term wall is | `ci.yml` steps; `vocabulary_wall.py` allowed prefixes do not include `ops/` |
| the hooks armed by `.claude/settings.json` include `test-guard-hook.sh` (advisory: a planted fault without its proof) | `.claude/settings.json` PostToolUse |

Consequences the design takes from these: the lane conf is a parallel
unit, so this batch reads it through one declared seam and lands
without it; grading reads the envelope's `where` spans, which is the
only mechanical handle a finding carries; the apps must be excluded
from the root `ruff check .` or their planted faults die in CI; a bash
lever proves its wire in its own suite, not the registry.

## The batch in one view

| slice | lands | bucket | depends on | unblocks |
|---|---|---|---|---|
| 1 | `ops/bin/fixture.sh` (make, prove, grade), `FAULT-KINDS.md`, the manifest shape, a synthetic test app under the lane's tests, the ledger's `calibrate` verb, the ruff exclusion | S | nothing in flight; a stub conf in tests | every app slice; the concerns contract's calibration clause gains an instrument |
| 2 | `apps/python-tooling`: skeleton, 6–8 faults, probes, neighbours, fixes | S | slice 1 | the two-minute proof (`make` then the suites); the first measured catch rates; the copy list's first measured value |
| 3 | `apps/python-service` (sketch; own run) | S | slice 1; a host with a venv from the lock | the production-dialect profile's specification by example |
| 4 | `apps/symfony-app` (sketch; own run) | S | slice 1; composer cache on the host | PHP through the loop for the first time, outside the product |
| 5 | `apps/rust-crate` (sketch; own run) | S | slice 1; cargo on a host | the end-use profile's specification by example |

Order: 1, then 2, then 3 to 5 in the order the scope lists them,
each its own run. Slices 3 to 5 are sketched here to the same shape as
slice 2 and are not planned to test-file detail; their planning runs
read slice 2 as landed.

"Bucket" here is the size class of scope-lane-fixes item 25, which is
not in this tree (measured above); S is used as the scope names it,
with the proxy the idea record gives (files and minutes): each slice
is one lever or one app of a few hundred lines besides dependencies,
one PR, one pipeline pass.

## The lane conf: what this batch reads, what it does not need

The lane conf's path, format and key names are not in the tree. This
batch reads it through one seam and nothing else:

- **Read: the copy list.** The paths the lane copies into a target
  ("the same files the lane conf's copy rule names"). `fixture.sh make`
  takes it from the conf at `$LANE_CONF` when that variable is set,
  and refuses class `conf` (expected a lane conf naming the copy list;
  found unset or no file; needed set `LANE_CONF`) when it is not. The
  batch's tests write a stub conf holding only the copy list. The
  slice 1 acceptance run is made with a hand-written conf whose
  contents are quoted in the PR body, and the list that makes the
  scratch suites green is the copy rule's first measured value, handed
  to the lane-conf unit as a finding, not a guess.
- **Not needed: toolchain profiles.** No verb of the lever reads a
  profile. `prove` runs the probe commands the manifest names; `grade`
  reads a record and a manifest. Each app's README and manifest carry
  the app's one "is it green" command, so a profile row can cite the
  app as its specification by example; declaring that edge is the
  lane-conf unit's work.
- **Not needed:** models, efforts, the launcher pin, retention, CI
  thresholds, tick rates, bucket sizes, the term-wall pattern. The
  scratch repository's `dispatch.sh --dry-run` resolves its models and
  efforts from the copied `dispatch.conf`, because that file is on the
  copy list; when the lane conf absorbs `dispatch.conf`, the copy list
  changes and the lever does not.

Key names in the conf are the lane-conf unit's to fix; this batch
declares only the fact it needs (a list of tree paths) and the seam
(`LANE_CONF`), and its tests pin the seam, not the names.

## Shared data, declared in slice 1

### `ops/devlane/fixtures/apps/FAULT-KINDS.md`

One table, one row per kind, nine rows from the scope's taxonomy. The
ids are stable and every manifest cites one:

| id | kind | the declared-versus-practiced shape |
|---|---|---|
| K1 | untrusted string reaching a shell or argv | declaration: input is passed as arguments; practice: string interpolation into a shell line |
| K2 | a path escaping its root | declaration: paths stay under the root; practice: join without normalising or checking the prefix |
| K3 | a loose comparison (false as zero) | declaration: absent and zero are distinct; practice: a truthiness or `==` test that conflates them |
| K4 | a secret in the environment or a log | declaration: credentials never leave the process; practice: a token in a log line or an inherited environment |
| K5 | an error swallowed | declaration: failures are reported; practice: a bare catch that returns a default |
| K6 | a boundary off by one (half-open intervals) | declaration: the range is half-open; practice: an inclusive end |
| K7 | a test proving against a stub | declaration: the test covers the boundary; practice: the boundary is replaced by a stub that cannot fail |
| K8 | an oracle taken from the code under test | declaration: expected values are independent; practice: the expected value is computed by the function being tested |
| K9 | an unpinned or drifted dependency | declaration: pinned and locked; practice: a range, or a lock that disagrees with the manifest |

Each row also states which of the three idioms (Python, PHP, Rust)
carries it naturally and the probe shape that proves it (a failing
test, a static grep, or a runtime check), so the four manifests plant
the same kinds and a reviewer's rates compare across languages.

### `FAULTS.json`, one per app

A JSON object with the app's name, its one `check` command (the "is it
green" command, run from the app root), and a `faults` list. One row
per fault, every key required, absence refused by the manifest sweep:

| field | holds |
|---|---|
| `id` | `<APP>-<nn>`, unique in the app, cited by the ledger |
| `kind` | a `K` id from `FAULT-KINDS.md` |
| `severity` | `p1`, `p2` or `p3`, the envelope's vocabulary |
| `location` | `path` (app-relative) and `lines` (a closed span) where the fault is practiced |
| `declared` | the declared words verbatim, with `path` and `lines` (the app's README or a docstring carries the declaration) |
| `practiced` | the practiced evidence verbatim, with `path` and `lines` |
| `finding` | one sentence: the finding a reviewer should make |
| `neighbour` | `path`, `lines`, and `why_clean`: a similar-looking place with no fault, which must not be flagged |
| `probe` | a command, run from the app root, that exits non-zero while the fault is planted and zero once fixed |
| `fix` | the path of a patch under `fixes/` that removes the fault and nothing else |
| `visible_to` | `test` (the probe is a failing test), `audit` (only review sees it), or both |

The quotation pair is the concerns contract's finding shape
(`docs/concerns.md`): a manifest row without both quotes is refused by
the sweep, the same as a finding without both quotes is not a finding.
Probes live under the app's `probes/`, outside the app's own test
discovery, so the app's `check` is green as shipped while every probe
is red; fixes live under `fixes/` as patches `git apply` can check.
Probes and fixes are apparatus and are named as such in the app's
README. The manifest is data: a new fault is a new row, a new probe,
a new patch.

### The lever, `ops/bin/fixture.sh`

Bash, like its siblings under `ops/bin/`, speaking the wire of
`docs/wire.md`: exit 0, 1 for findings, 2 with one stderr line
`class: expected …; found …; needed …` and empty stdout, 3 on abort.
Reads need no identity; writes refuse class `identity` without
`WF_AGENT` in the `Name <address>` form.

- `make <app> [DIR]` (write): refuses `app` when
  `ops/devlane/fixtures/apps/<app>/FAULTS.json` is absent; refuses
  `conf` without a copy list; refuses `target` when DIR is inside any
  worktree of the invoking repository (the launcher's `live-target`
  rule, kept); default DIR is a fresh directory under
  `${XDG_STATE_HOME:-$HOME/.local/state}/agentscient/fixtures/`.
  Copies the app's tree to the root of DIR, then the copy list from
  the invoking repository's tracked tree (`git ls-files` resolution,
  so an untracked or ignored file never rides), proves the copy in
  both directions the way `stage.prove` does (every listed path
  present, nothing outside the list present) before it runs `git
  init`, sets the fixture identity from `WF_AGENT`, commits once with
  `Source:` and `Co-Authored-By:` trailers, and prints DIR on one
  stdout line. A `make` that cannot prove its copy leaves no
  directory behind.
- `prove [--fixed] DIR` (read): refuses `manifest` when DIR carries no
  `FAULTS.json`; refuses `fix` when `--fixed` and any patch fails `git
  apply --check`. With `--fixed`, applies every patch first. Runs every
  probe from the app root with a bounded timeout, identity stripped,
  time and locale pinned, and reports one line per fault: `RED`,
  `GREEN`, or `UNREACHABLE` (spawn failure or timeout, never a colour),
  then counts. Exit 0 when every probe has the expected colour (RED
  fresh, GREEN fixed) and none is UNREACHABLE; exit 1 otherwise. The
  runner semantics are `docs/probes.md`: UNREACHABLE is neither a pass
  nor a fail, and it is counted separately.
- `grade <record> <app>` (write): reads a dispatch record (a path, or
  an id resolved under `.dev/records/dispatches/` of the repository
  named by `--repo`, default the invoking one), refuses `record` when
  the file is absent or its job is not a review job, refuses `app`
  when the manifest is absent. For each finding in the record's
  envelope it extracts every `path:start-end` span from `where`
  (measured shape above; a `where` with no span is `unlocated`).
  Classification, per finding: `caught` when any span overlaps a
  fault's `location`; `false-positive` when any span overlaps a
  fault's `neighbour` and none overlaps a fault; `unmatched` otherwise.
  Per fault: `missed` when no finding caught it. Prints per reviewer
  (the record's harness and model as the record carries them) the
  counts caught, missed, false-positive, unmatched, unlocated, and the
  two rates: caught over faults, false-positive over neighbours. Then
  writes the rows to the findings ledger through `findings.py
  calibrate` (below) and prints nothing else. The stated limit, as the
  probes lever states its own: mechanical grading proves span overlap,
  nothing more. An `unmatched` finding may be a real unplanted defect
  or a false positive; that is a reviewer's question and the row
  carries the claim verbatim so the reviewer can answer it. Exit 0
  after writing; the rates are data, never a verdict.

### The ledger's `calibrate` verb, in `findings.py`

The scope asks that grades be written to the findings ledger with the
app and fault ids. The ledger's columns are fixed and its keys are
`<record>#<n>`; a missed fault has no finding row to hang on. So the
store gains one table, `calibration`, beside `findings`, and
`findings.py` gains one writing verb, `calibrate`, which reads the
grader's rows as JSON on stdin (one object per row: record, app,
fault id or null, finding key or null, class, reviewer harness and
model, the claim verbatim) and upserts them keyed on record, app,
fault id and finding key. The tracked export gains a second file,
`ops/conductor/findings/calibration.jsonl`, written by `findings.py
export --calibration`; the existing `export` output is byte-identical
to today. Refusal class `calibration` for malformed stdin, one line,
exit 2. Identity required. This is the batch's one instrument edit;
it adds a table and a verb to a conductor instrument, not a kernel
responsibility, and it joins the conformance registry with a second
row for `findings.py` (`calibrate` on empty stdin → class
`calibration`).

Alternative considered and set aside: the lever writing SQLite itself.
That duplicates the store's schema in a second place, which is the
drift the instrument conventions forbid.

### Root changes the batch must make, and why

- `ruff.toml`: `extend-exclude` gains `ops/devlane/fixtures/apps`,
  with the reason in a comment: the apps are lint-checked by their own
  toolchain through `prove` and their `check` command, and a planted
  fault must survive the root `ruff check .`, whose `S` family would
  otherwise kill K1 and K4 at the gate. The lane's own tests under
  `ops/devlane/fixtures/tests/` stay linted.
- `ops/README.md` layout table: one row for `ops/devlane/fixtures/apps/`
  and one lever row for `fixture.sh`.
- No CI step changes. The term wall covers the apps by construction
  (every tracked file); PHPUnit, `php -l`, `composer validate` and the
  mate step do not reach `ops/`, measured above.

## Slice 1 — the lever, the kinds, the manifest shape

**Unblocks.** Every app slice; the calibration clause of
`docs/concerns.md`, which today is a declared gap; the concerns
contract's "verdicts beside rates".

**Bucket.** S: one bash lever, one markdown table, one JSON shape, one
verb in one instrument, one ruff row, four test files.

**Edges it touches, and the guarantees.**

| edge | contract | guarantee declared or kept |
|---|---|---|
| `fixture.sh` → the wire | `docs/wire.md` | declared: four classes, one-line refusal, identity on `make` and `grade`; proved by its suite, since the registry is Python-only (a declared gap, recorded in the PR) |
| `fixture.sh make` → lane conf | the `LANE_CONF` seam | declared: reads one fact, the copy list; refuses without it; the lane-conf unit owns names |
| `fixture.sh make` → the invoking tree | `git ls-files` | kept: only tracked files ride; an ignored file is never in a fixture (the launcher's snapshot rule, kept) |
| `fixture.sh make` → the scratch directory | the launcher's `live-target` refusal | kept: never inside a worktree of the invoking repository |
| `fixture.sh prove` → probe commands | `docs/probes.md` runner semantics | declared: RED, GREEN, UNREACHABLE, counted separately; identity stripped; bounded timeout |
| `fixture.sh grade` → dispatch records | `ops/devlane/dispatch/CONTRACT.md` §The record; `envelope.py` FINDING_FIELDS | kept: reads `result.envelope.findings`, `harness.name`, `model.ran`; writes nothing to the record |
| `fixture.sh grade` → `findings.py calibrate` | `ops/conductor/instrument-conventions.md` | declared: a new table and verb; existing `export` byte-identical; new registry row |
| manifests → `FAULT-KINDS.md` | the sweep test | declared: every `kind` resolves; every row carries both quotes |
| root `ruff check .` → the apps | `ruff.toml` | declared: excluded with reason; the lane's tests stay in |
| `test-guard-hook.sh` → the app trees | advisory hook | kept: planted faults are in fixture trees, not test files, so the hook's shape is not triggered; the probes are their proof |

**Depends on.** Nothing in flight. The stub conf lives in the tests.

**Lands green on its own.** Yes: with no app under `apps/`, the
manifest sweep passes over an empty directory only if it declares the
emptiness (the sweep asserts `FAULT-KINDS.md` exists and every
manifest found is valid; it does not assert an app exists, so slice 1
is green with zero apps and slice 2 adds the first). The lever's tests
build a synthetic mini-app under a temporary directory (stdlib Python,
two faults, two probes, two patches) and a stub copy list, so `make`,
`prove` and `grade` are exercised end to end in CI without any real
app, cargo, composer or a venv.

**Tests, by file, and why each is red at c52bc60.**

| file | pins | red because |
|---|---|---|
| `ops/devlane/fixtures/tests/test_fixture_lever.py` | the lever exists and is executable; every refusal (`app`, `conf`, `target`, `identity`, `manifest`, `fix`, `record`) is one stderr line, exit 2, empty stdout, expected–found–needed in order; `make` on the synthetic app prints one directory, the copy is proved both ways, the commit carries trailers, an ignored file did not ride; `prove` reports every probe RED fresh, exit 1 while any is the wrong colour, exit 0 when all match; `prove --fixed` reports GREEN; a probe that times out is UNREACHABLE and never a colour | `ops/bin/fixture.sh` is absent: the first assertion (`is_file`) fails on the file, the intended assertion, not on import |
| `ops/devlane/fixtures/tests/test_fixture_manifests.py` | the sweep: `FAULT-KINDS.md` exists with the nine ids; every `apps/*/FAULTS.json` found validates (all fields, kinds resolve, locations and neighbours name existing files and spans inside them, probes and fixes exist, ids unique, six to eight rows, six or more distinct kinds, both quotes non-empty and present verbatim at their stated spans) | `FAULT-KINDS.md` is absent |
| `ops/devlane/fixtures/tests/test_fixture_grade.py` | grading over a synthetic record (the envelope shape from `envelope.py`, `where` in the measured `path:start-end` forms including `;` and `↔` joins) and the synthetic manifest: caught, missed, false-positive, unmatched, unlocated each land where the rule says; rates are computed from the counts; a record whose job is not a review job refuses `record`; the rows handed to `calibrate` carry app and fault ids | the `grade` verb is absent (the lever is absent) |
| `ops/conductor/tests/test_findings_calibration.py` | `findings.py calibrate` upserts rows under a temp `HOME`, is idempotent, refuses `identity` and `calibration`; `export` is byte-identical before and after a calibrate; `export --calibration` is deterministic | `findings.py` refuses `calibrate` as an unknown verb (class `arguments`), so the exit-0 assertion fails on the intended verb |
| `ops/conductor/tests/test_instrument_conventions.py` (one registry row added) | `findings.py calibrate` with empty stdin → class `calibration` | the class emitted today is `arguments` |

The lane's tests never run an app's own suite except through `prove`,
and the synthetic app under test is stdlib only.

**Acceptance, mapped to proof.**

| acceptance | proof, run at the head sha and quoted in the PR |
|---|---|
| the lever speaks the wire | `test_fixture_lever.py` green; one hermetic refusal quoted verbatim |
| `make` proves its copy both ways | the test that plants an ignored file and a missing listed path, and the lever refuses or excludes as declared |
| `prove` red fresh, green fixed, on the synthetic app | `test_fixture_lever.py`; and by hand, `fixture.sh make` of the synthetic app then `prove` and `prove --fixed`, output quoted |
| `grade` counts per reviewer and writes the ledger | `test_fixture_grade.py`, `test_findings_calibration.py` |
| the product's CI steps unchanged | `git diff --stat origin/dev -- .github composer.json phpunit.dist.xml` empty; `ruff.toml` diff is the one exclusion row |
| every lane suite green, `ruff check .` clean, term wall clean | `bash ops/bin/suites.sh`, `ruff check .`, `python3 ops/devlane/workflow/checks/term_wall.py --root .`, on the merge with `origin/dev` |

## Slice 2 — `apps/python-tooling`

**Unblocks.** The two-minute proof a new session runs (`fixture.sh
make python-tooling`, then `bash ops/bin/suites.sh` in the scratch);
the first measured catch rates for a security audit and an adversarial
review; the copy list's first measured value for the lane conf; the
exemplar the implement prompt can point workers at for the dev
dialect.

**Bucket.** S: one app of a few hundred lines, stdlib only, 6–8 faults
with probes, neighbours and patches, one lane test file.

**The app.** The lane's own Python in miniature, the dev dialect:

- Layout: `README.md` (what it is, that it is apparatus, its one
  `check` command, one declaration per planted fault in plain
  sentences), `tool/` with a CLI entry (a lever speaking the refusal
  wire: one verb reads a store, one writes), a service module (a
  small ledger over a JSON-lines file, the I/O boundary), a data
  model module (a record with a half-open interval), `tests/`
  (unittest, green as shipped), `ruff.toml` selecting what a typical
  project selects (`E`, `F`, `I`, `B`; not `S`, so K1 and K4 survive
  the app's own lint and are visible only to an audit), `probes/`,
  `fixes/`, `FAULTS.json`. No packaging, no lock: K9 does not apply
  to this dialect and the manifest says so.
- `check`: the unittest discovery over `tests/` and `ruff check .`
  from the app root, green on the shipped tree.

**The first fault set, seven rows** (the eighth is left open on
purpose so the first grading run can say whether a missing kind is a
gap worth planting):

| id | kind | where planted, in one line | probe shape | visible to |
|---|---|---|---|---|
| PT-01 | K1 | the CLI builds a shell line from a user-supplied name for a helper call; the README says arguments are passed as argv | a runtime probe passes a name with a shell metacharacter and expects the helper to receive it literally | audit |
| PT-02 | K2 | the store opens `root / name` without checking the resolved path stays under `root`; the README says records never leave the store root | a probe asks for `../` and expects a refusal | audit, test |
| PT-03 | K3 | the CLI treats a count of zero as absent and prints the "no record" line; the README says zero is an answer | a failing test: a record with count 0 is served, not refused | test |
| PT-04 | K4 | the write verb logs its environment, token included, on failure; the README says credentials never leave the process | a probe runs the failing path with a planted token in the environment and greps the log; red while the token appears | audit |
| PT-05 | K5 | the service catches every exception on read and returns an empty list; the README says an unreadable store is a refusal, not an empty answer | a failing test: a corrupt store line must refuse, not serve empty | test |
| PT-06 | K6 | the interval model's `contains` uses an inclusive end; the docstring says half-open | a failing test at the boundary value | test |
| PT-07 | K8 | a shipped test computes its expected checksum by calling the function under test; the README says oracles are independent | a static probe: the test file imports the function it uses as its oracle (a grep that must find nothing once fixed) | audit |

K7 is not planted here because the app has no external boundary worth
stubbing; it is planted in `python-service` where the boundary is
real. Every row carries its clean neighbour: a second call site that
does pass argv, a second path join that does check the prefix, a
second comparison that distinguishes zero, a log line that redacts, a
narrow catch that re-raises, a second interval method that is
half-open, a test with a literal oracle.

**Edges it touches, and the guarantees.**

| edge | guarantee |
|---|---|
| the app → the manifest sweep | kept: every row validates; both quotes are present at their stated spans |
| the app → `prove` | declared: seven probes RED on a fresh `make`, GREEN after `prove --fixed`; none UNREACHABLE on a host with python3 |
| the app → the root gates | kept: excluded from root ruff (slice 1); clean under the term wall; its README uses no name the wall refuses (checked by the CI step, not by intention) |
| the app → the copy list | measured: the copy list that makes `bash ops/bin/suites.sh` green in the scratch is recorded in the PR body as the list, with the command that produced it |
| the scratch → `dispatch.sh --dry-run` | measured: `--worktree <scratch> --job sweep --harness claude --scope-file <f> --dry-run` prints the launcher, models and efforts resolved from the copied conf |
| the app → the ladder | measured: one `security-audit` and one `adversarial-review` dispatched over the scratch (a whole-snapshot read job needs a worktree of a lineage; the scratch is a repository with one branch, so the session runs the launcher from it, stated in the PR); `grade` over each record; the rates in `calibration.jsonl` |

**Depends on.** Slice 1 landed. Nothing from the lane conf beyond the
copy list, supplied by hand in this slice.

**Lands green on its own.** Yes: the app's `check` is green as
shipped; the lane suites gain one test file that runs `make` and
`prove` on this app in CI (python3 only, a few seconds); the ladder
run and the grade are the slice's acceptance, done by the session and
quoted, not a CI step.

**Tests, by file, and why red at c52bc60.**

| file | pins | red because |
|---|---|---|
| `ops/devlane/fixtures/tests/test_python_tooling_app.py` | the app exists; its manifest has six to eight rows over six or more kinds and cites K1, K2, K3, K4, K5, K6, K8; `fixture.sh make python-tooling` into a temp directory with the test's stub copy list succeeds; `prove` reports every probe RED and exit 1; `prove --fixed` reports every probe GREEN and exit 0; no probe UNREACHABLE; the app's own `check` exits 0 on a fresh make (run through the lever's `prove --check` or by the test invoking the manifest's `check` command in the scratch, which is the one place the lane runs an app's suite, as the scope allows through `prove`) | the app directory is absent: the first assertion fails on `FAULTS.json` |
| the app's own `tests/` | the app's behaviour as shipped (green) | not lane tests; green by construction; listed so the pipeline's test author knows they are the implementer's, not theirs |

**Acceptance, mapped to proof.**

| acceptance | proof |
|---|---|
| `fixture.sh make python-tooling` yields a scratch where `bash ops/bin/suites.sh` is green and `dispatch.sh --dry-run` resolves from the conf | both commands run in the scratch, output quoted with the scratch's commit sha |
| every probe red fresh, green fixed | `fixture.sh prove DIR` and `fixture.sh prove --fixed DIR2` on two fresh makes, output quoted; `test_python_tooling_app.py` green in CI |
| one security audit and one adversarial audit through the ladder; `grade` prints per-reviewer counts; the ledger holds the rows | the two record ids; `fixture.sh grade <id> python-tooling` output; `git diff --stat -- ops/conductor/findings/calibration.jsonl` |
| the product's CI steps unchanged | as slice 1 |
| lane suites, ruff, term wall green | as slice 1, on the merge with `origin/dev` |

## Slice 3 — `apps/python-service` (sketch; its own run)

The production dialect: a packaged application with a `pyproject`,
pinned dependencies and a lock, a small HTTP-shaped or CLI service
with one I/O boundary (a request parser over stdin or a socket), its
own runner (pytest or unittest, stated in its README), `ruff.toml`.
Dependencies are kept to one or two small pure-Python packages chosen
so the service runs on stdlib when they are absent; the K9 fault is
about the pin and the lock, not about importing them, so `prove` on a
host without a venv still reaches every probe.

Fault set, seven or eight rows, a target's faults: K1 an injection at
the boundary (a query string reaching a subprocess); K2 a path escape
in a file-serving verb; K4 a secret in a request log; K5 an error
swallowed at the boundary; K6 a pagination off-by-one; K7 a test
proving the boundary against a stub that cannot fail; K9 an unpinned
dependency (a range in the manifest while the lock names a version)
and, as the eighth, a lock drifted from the manifest. K3 and K8 are
covered by `python-tooling`, and the manifest says which it leaves to
its sibling.

Edges: the same as slice 2 plus the venv question. `prove` reports
UNREACHABLE for a probe that needs an installed dependency when the
venv is absent, and the README names the one install command from the
lock (no network at make time; the install is the host's, cached).
Lane test file: `test_python_service_app.py`, red because absent; it
asserts the manifest and runs `prove` only for probes the manifest
marks stdlib-reachable, and asserts the others are UNREACHABLE, never
a colour, when the venv is absent. Acceptance as slice 2, with the
venv named.

## Slice 4 — `apps/symfony-app` (sketch; its own run)

A Symfony skeleton at the product's pins (`symfony/*` 8.1.*, PHP
>= 8.4, from the root `composer.json` at this ref): one console
command (the wire on the CLI: exit classes and the refusal line on
stderr), one service, one controller, PHPUnit, a `composer.json` with
`check` and `fix` scripts as the standards draft names them, a
committed `composer.lock`. `vendor/` is not tracked; the README names
the one `composer install --prefer-dist` from the lock, served from
the host's composer cache (no network at make time is the runner's
guarantee to keep, stated).

Fault set, seven rows, the PHP idiom: K1 a `Process` built from a
string; K2 a path join in the controller; K3 a loose comparison (`==`
against `0` or an empty string, the PHP idiom the kind is named for);
K4 a secret in a Monolog line; K5 an empty catch; K6 a half-open range
in the service; K8 an oracle computed by the service in its own test.
Probes are PHPUnit tests under `probes/` (outside `phpunit.dist.xml`
discovery) and static greps; every probe is UNREACHABLE without
`vendor/`, and the README says so.

This is where PHP work first goes through the loop; nothing from it
lands in the product (`packages/`, `src/`, root config untouched, the
CI's PHP steps unchanged, measured by the diff in the PR). Lane test
file: `test_symfony_app_app.py`, red because absent; it validates the
manifest and asserts `prove` reports UNREACHABLE, never a colour,
without `vendor/`. The prove-red proof is the session's, on a host
with the cache, quoted.

## Slice 5 — `apps/rust-crate` (sketch; its own run)

A crate with a lib and a bin, `Cargo.lock` committed, `cargo test`,
`clippy`, `fmt`; end-use shaped, never a real project (owner: the
Rust one "is not a dev fixture" and "shouldn't be the only one"; the
first Rust target is unnamed, and the crate rehearses the install into
a target of that kind). Fault set, seven rows in the Rust idiom: K1 a
`Command` built via `sh -c` from an argument; K2 a path join without
`canonicalize` and a prefix check; K3 an `unwrap_or(0)` that conflates
absent and zero; K4 an env dump in a log; K5 a `let _ =` on a `Result`
or a `.ok()` that drops an error; K6 an inclusive range where the API
says half-open; K9 a wildcard version in `Cargo.toml` against a locked
one. Probes are `cargo test` invocations of tests under `probes/`
(excluded from the default target set) and static greps.

The CI runner declares no cargo (measured). The lane test file,
`test_rust_crate_app.py`, red because absent, validates the manifest
and asserts `prove` reports UNREACHABLE without cargo; the prove-red
proof is measured on a host with cargo and quoted. Whether cargo joins
the runner's toolchain step, and whether the runner's smoke matrix
gains a Rust job when CI splits, are the owner's decisions and are
named as such in the slice's PR, not assumed.

## Producer firewall for the batch

Per `ops/process/pipeline.md`: this plan is Fable's; the tests of
slice 1 and slice 2 are written by a harness that is not the
implementer, from this plan and the contracts named here, without the
lever or the app; the skeptic judges them; the implementer writes the
lever, the kinds, the app, and the app's own tests (which are part of
the fixture, not part of the judge); two reviewers review the PR. The
owner's rule that no producer owns two consecutive artifacts holds at
every step. The fixes under `fixes/` are implementation; the probes
are the fixture's proof, not tests of the lane, and the implementer
writes them with the app.

## What this plan does not decide, named

- The lane conf's key names and file format: the lane-conf unit's.
  This batch fixes only the seam (`LANE_CONF`) and the one fact read.
- Whether the bash levers under `ops/bin/` should be admitted to the
  conformance registry by giving it a second invocation shape: a
  finding for the conventions document, recorded in slice 1's PR.
- Whether `dispatch.sh`'s exit-3 prefixed refusal should move to the
  wire: a standing divergence, outside this scope.
- The eighth fault per app: left to the first grading run's evidence.
- cargo on the runner and a per-profile smoke matrix job: the owner's.
