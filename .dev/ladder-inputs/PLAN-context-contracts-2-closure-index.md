# Plan — context contracts (re-plan of item 45)

Stamp: tree `28608ca4f3f3ef982902cb7c9bbcbe1f96aadf4b` (`git rev-parse HEAD`), measured 2026-09-04T15:34:38Z. Host: `cue version v0.17.1` at `/home/scientdb/.local/bin/cue`, `python3` 3.12.3. Tracked files: 728 (`git ls-files | wc -l`). This plan writes no code. It revises record `20260904T121217Z-plan-claude-01b3dc` (seven buckets, tree `0cea17a`); it does not start from nothing.

The owner's freeze item 1, in the owner's words: "contracts - you need to have guaranteed format and its that simple." Every stage boundary gets a closed CUE definition per job kind for the input manifest, the plan, the test command, and the envelope. `cue vet` runs in the dispatcher before launch and in the consumer at land. A failed vet is class `context` on the wire. First, the closure gate the copy left out: every `.cue` file and every `ops/conductor/*-lever.md` names its consumer and a firing fixture, or the gate refuses.

## 0. What the previous plan got wrong, and what this one keeps

The previous plan is the design to revise. It already measured that `context.cue` exists and nothing on the launch path runs it. It is missing the closure gate, the three other boundary documents (plan, command, envelope), vet at land, vet in the dispatcher, and the owner's bucket rule S = 1–3 files.

Kept from that plan, still the decisions unless the owner overrules:

- One builder, `ops/devlane/harness/manifest.py`. Launcher loads it in-process (`dispatch → harness`, already declared). Driver and dispatcher invoke it as a subprocess. Bash builds nothing.
- `--input KIND=PATH` replaces bare `--input PATH`. Kind is never inferred from a file name.
- Shape versus law: each job kind is a closed definition; `#Launchable` requires concrete `brief` and `diff` and empty custody-failure lists. Driver vets `-d '#<Kind>'`. Launcher vets `-d '#<Kind>' -d '#Launchable'`.
- A `context` refusal mints nothing (launcher contract: before anything is minted).
- Launcher wire stays exit 3. Land stays exit 2. Driver `Stopped` for a failed vet is exit 3, `reason=context`. The exit-3-versus-2 split predates this batch.
- `#CueVersion: "v0.17.1"` lives in the law file the builder reads. No new `lane.conf` key.
- Observed isolation may be `#Unresolved`. Live records on this tree carry `observed: {"unresolved": "behavioural probe has not run"}` (read from this job's `record.json`).
- Caps are declared numbers in `manifest.cue`, re-measured after the first ten manifests.
- Pre-manifest records stay closable by writing `context.manifest.declared_absent`.
- The meter prints `context=unrecorded` when the field is absent or declared absent, never `0`.

Dropped from that plan:

- Generated `controls/manifests/**` files on the bucket line. S is 1–3 files (`land_result` set-difference, `ladder.py:884–911`). Tests plant JSON in a temp directory and call `cue vet`. `build.py --check` keeps the existing 42 controls and is not extended with a generated tree this batch would have to land.
- Seven one-bucket ladders as the only way to avoid a joined test command. The command is now a boundary document; per-bucket discover form is in scope. Until that lands, every slice below is S (one bucket, one test file), so today's `derive_command` (`ladder.py:1081–1109`, one `&&` join of every tests-envelope artifact, handed to every implement) does not judge the first implement on a second bucket's tests.
- Naming the plan-job kind `#Plan`. `ops/capabilities/contracts/plan.cue` already defines `#Plan`. The driver document is `#Plan` in package `harness` (`ops/devlane/harness/plan.cue`). The plan job's input manifest is `#PlanJob`.

## 1. What was measured on this tree

Each claim names the command, run on `28608ca4f3f3ef982902cb7c9bbcbe1f96aadf4b`.

- **19 `.cue` files** (`git ls-files '*.cue'`). **6 lever contracts** (`git ls-files 'ops/conductor/*-lever.md'`). Consumers, by `git grep -l` of each basename over `*.py`, `*.sh`, `*.yml`, excluding `ops/archive`:

  | path | consumer found | firing fixture found |
  |---|---|---|
  | `ops/devlane/harness/context.cue` | `vet_context.py`, `controls/build.py` | `controls/rejects/*.json` (24 controls, `vet_context.py` prints `24 control(s), 0 problem(s)`) |
  | `ops/devlane/harness/evidence.cue` | `vet_context.py` | `controls/evidence-receipt.json`, rejects under `controls/rejects/` |
  | `ops/conductor/contracts/board.cue` | `ops/conductor/tests/test_board_contract.py` | `ops/conductor/contracts/faults/*.json` (4 files) |
  | `ops/devlane/workflow/contracts/cue/commitmsg.cue` | `ops/devlane/workflow/checks/commit_trailers.py` (filename hit) | not verified here that the check calls `cue vet` |
  | `ops/capabilities/contracts/{capabilities,capability,outcome,plan}.cue` | none | none |
  | `ops/devlane/workflow/contracts/cue/{canonical,cli,db,events,exitcodes,gatekinds,layout,mcp,meta,schema,vocab}.cue` | `schema.cue` hits `harness/stage.py` (word `schema`, not a vet); the rest none | none |
  | `ops/conductor/ladder-lever.md` | `ladder.py`, `test_ladder_lever.py` | planted refusals in that suite |
  | `ops/conductor/land-lever.md` | `land.py`, `test_land_lever.py` | same |
  | `ops/conductor/onboard-lever.md` | `onboard.py`, `test_onboard_lever.py` | same |
  | `ops/conductor/watch-lever.md` | `watch.py`, `test_watch_lever.py` | same |
  | `ops/conductor/watchdog-lever.md` | `watchdog.py`, `test_watchdog.py` | same |
  | `ops/conductor/probes-lever.md` | **`ops/conductor/tools/probes.py` is absent** (`ls` of that path) | none |

  That last row is the copy's failure, applied to a lever: a contract with no instrument. The closure gate exists so this is a refusal, not a green suite.

- **Nothing on the launch path vets.** `git grep -n -E 'cue vet|vet_context'` over `ops/conductor/tools/dispatch.sh`, `ladder.py`, `land.py`, `ops/devlane/dispatch/launch.py` hits only the Claude tool-rule string `Bash(cue vet *)` at `launch.py:311`. `cue vet ./ops/devlane/harness/` exits 0 as a package. `cue vet ./ops/devlane/harness/evidence.cue` prints `#NonEmpty` / `#Digest` not found. The check is the package vet, never a per-file vet.

- **The session hook named in the input is not on this tree.** `git ls-files | rg -i matrix` returns `ops/devlane/workflow/checks/ci_matrix.py` only. `ops/devlane/hooks/claude/matrix.py` is absent. Looked; found nothing. The vet belongs in the dispatcher regardless.

- **Launcher inputs and records.** `launch.py _launch` (`838–1041`): scope capped by `SCOPE_CAP` (`lane.conf` `SCOPE_CAP='1024'`), `--input` copied to `in/` with `{path, sha256}` into `brief.inputs`, diff at `context/diff.patch`. `record.py FIELDS` has 20 names, no `context`. 81 tracked dispatch records (`git ls-files .dev/records/dispatches/*.json | wc -l`); `brief.bytes` 848–4157; record files 2969–30028 bytes; inputs per dispatch 0–2; **0 records carry a `context` key**.

- **Envelope parser accepts a partial object.** `_schema_valid` (`launch.py:531–567`) checks JSON Schema. `_most_envelope_shaped` (`571–577`) scores by key presence. After a harness-specific parse fails, `launch.py:670–673` falls back to that scorer ("Compatibility for pre-U10 raw.out"). `envelope.validate` (`task/envelope.py:253–310`) is not that path. A `changes` verdict with empty `findings` satisfies `ENVELOPE_SCHEMA` (`task/envelope.py:52–112`): `findings` is an array with no minItems. Land (`land.py:220–224`) checks `result.envelope.status == ok` and does not cue-vet.

- **Plan grammar is TSV in prose, not a contract.** `parse_plan` (`ladder.py:324–356`) splits `slice` / `bucket` lines. An M slice requires `len(buckets) == 2` **in the whole file**, so a three-slice plan is refused with found clause `N buckets in {plan}` (the wrong found: it counted every bucket, not the slice's). Files are `fields[3].split()` (whitespace, not comma). `DEFAULT_PLAN` in `test_ladder_lever.py:140` has no machine lines.

- **Test command.** `derive_command` (`ladder.py:1081–1109`) already emits `python3 -m unittest discover -s DIR -p FILE` per tests-envelope artifact whose path has `tests` in a parent and suffix `.py`, then joins with ` && `. One command file is handed to every implement (`1365–1369`). A form that cannot import is not refused; a worker can add a root shim.

- **Read jobs that name `{out}`.** `jobs.json`: `plan`, `check-tests`, `adjudicate` are `role: read` and contain `{out}`. `check-tests` names `{out}/SKEPTIC.md`. Codex read sandbox is `read-only` (`dispatch/CONTRACT.md` isolation table). Claude already passes `--add-dir` for `out/`. Codex `workspace-write` is the write role; the read role does not get `writable_roots`.

- **Residual index under `/tmp`.** `_write_residual_patch` (`launch.py:1275–1294`) uses `tempfile.NamedTemporaryFile(prefix="residual-index-", delete=False)` as `GIT_INDEX_FILE`. The job directory is the only place a dispatch may write (`dispatch/CONTRACT.md` §The job directory).

- **CI.** `.github/workflows/ci.yml` `lane` job (lines 24–45) runs term wall, ruff, `suites.sh`, `laneconf.py closure`, `laneconf.py literals`. It does not print `cue version` and does not run `vet_context.py`. The `app` job prints `cue version` at line 55. `ops/bin/suites.sh` is unittest discover over nine directories; it does not call `vet_context.py` or `cue`.

- **Probes allowlist is prose, not data.** `ops/conductor/probes-lever.md:30–38` names allowed `git` / `gh` / sibling-instrument forms. `ops/conductor/tools/probes.py` is absent. `docs/probes.md` is the law: allowlisted read set, identity stripped, read-only enforced.

- **Symfony fixture vendor is gitignored.** `ops/devlane/fixtures/apps/symfony-app/.gitignore` lists `/vendor/`. This batch's named commands are Python unittest. They do not copy that tree and they do not install.

- **Ladder scratch copies stub launchers**, not the real ones (`test_ladder_lever.py:1073–1084`). That is pre-existing test apparatus. This batch does not add a stub of a dependency to get green. Cue is probed (absent / wrong version). Composer vendor is refused, not copied.

- **CUE lessons that the definitions must respect** (`ops/docs/cue-aar-equality.md`, re-checked: `cue vet -d '#Dispatchable' …/rejects/role-mismatch.json` names `role:`). No equality-as-default in CUE (lesson 4: Python checks digests). No comprehension inside `close()` (lesson 3). `-d` may be repeated. Package vet, not per-file.

Today's measured cases are the fixtures the new contracts must refuse. Cite them by record id in the tests, do not invent replacements.

| record | missing format |
|---|---|
| `20260904T101518Z-code-codex-31ed0a` | implement input with no toolchain profile; worker stubbed dependencies |
| `20260904T063409Z-review-codex-28e041` and nine more check-tests | read-role prompt named `{out}/SKEPTIC.md`; ten envelopes tripped |
| `20260904T130010Z-code-codex-f2506c` | command not in discover form; worker added a root shim |
| `20260904T150457Z-code-codex-a3279b` | tests envelope `changes` without findings |
| `20260904T144439Z-check-tests-codex-ffaf2b` accepted; re-audit `20260904T140242Z-review-codex-69d0fb` finding 1 | `changes` with no findings accepted by the driver |
| ladder `20260904T132749Z-ladder-f5d171`, `20260904T132831Z-ladder-50b74b` | plan grammar undocumented; three-slice plan refused with the wrong found clause; comma-joined bucket files |
| `20260904T122257Z-code-codex-c7f52a` re-audit finding 2 | partial / `legacy_fixture` envelope shape bypasses validation (`_most_envelope_shaped`) |

Finding 2 of that class (stub / bypass to get green) is in scope. A test must pin the bypass is gone: implement without a toolchain profile is a `context` refusal before the worker starts, and a schema-invalid envelope is not accepted as `ok`.

## 2. Decisions the scope leaves open, taken here

The owner overrules any of these before tests are written.

1. **Closure index is data, complete versus `git ls-files`.** `ops/devlane/harness/closure.json` lists every tracked `*.cue` and every `ops/conductor/*-lever.md`. Each row is `{path, consumer, fixture}` or `{path, consumer: {declared_absent: reason}, fixture: {declared_absent: reason}}`. `closure.py check` refuses class `closure` (exit 2) when a tracked contract is missing from the index, when a named consumer or fixture path does not exist, or when a planted extra `.cue` is unindexed. Rows with `declared_absent` are findings (exit 1) and the live-tree unittest pins the set to the unclosed rows measured in §1, so closing one is a reviewable diff. New contracts this batch lands (`manifest.cue`, `plan.cue`, `command.cue`, `envelope.cue`, `closure.cue`) must be fully closed (live consumer and firing fixture), never `declared_absent`.

2. **Four closed documents, four files, package `harness`.** `manifest.cue` (job-kind input manifests), `plan.cue` (`#Plan` for the driver document), `command.cue` (`#Command` discover form), `envelope.cue` (`#Envelope` and per-kind closed envelopes). They import helpers from `context.cue` by sitting in the same package, not by a CUE import of another module. Vet is always `cue vet -d '#Name' context.cue evidence.cue <file> <document>` (all three law files, because vetting one file alone once reported a tidy count of failures that were really "the schema did not load", `vet_context.py:43–47`).

3. **A section is one input file, slotted by kind.** Manifest keys are `scope`, `brief`, `diff`, `plan`, `previous`, `findings`, `report`, `document`, `markers`, `command`, `toolchain`. No `history`. Implement requires `toolchain`. Caps stay the previous plan's declared numbers, re-measured on this tree where the records exist: `scope` 1024, `brief` 8192 (max 4157), `plan` 32768, `previous` 65536 (max record 30028), `findings` 65536 and at most two, `report` 32768, `document` 16384 and at most two, `markers` 4096, `diff` 1048576, `command` 1024 (SCOPE_CAP), `toolchain` 4096. `total_bytes` is Python-checked against the sum.

4. **Dispatcher vets by subprocess, writes nothing.** `dispatch.sh` runs `manifest.py vet-args --kind K --section KIND=PATH …` which builds the document in memory from the source paths (job-dir-relative paths are computed, not written), package-vets it, prints one JSON object on stdout on success. Failure: one stderr line `context: expected …; found …; needed …`, and the wrapper exits 3. No file under `/tmp`. Launcher still vets before mint so a direct `launch.py` call cannot skip the guard.

5. **Land is the write consumer; the driver is the review consumer.** `land.py` cue-vets `result.envelope` against `#Envelope` and the job kind before the first cherry-pick; failure is class `context`, exit 2, nothing landed. `ladder.py load_envelope` cue-vets the same object for review stages and stops `reason=context`. `_most_envelope_shaped` as an accepting fallback is removed in the launcher slice; a partial object becomes `status: invalid` with note `schema-invalid`. `changes` with zero findings does not evaluate under `#Envelope`.

6. **`#Plan` is one slice per plan file.** Closed JSON the driver builds from TSV: `{slice: {name, size: "S"|"M"}, buckets: [{name, size: "S", files: [1–3 paths]}]}`. S: one bucket. M: exactly two buckets. Each file token `=~"^[^,]+$"` (comma-joined is `field not allowed` / out of bound, not a silent one-token file). `parse_plan` vets that object with `cue vet -d '#Plan'` **before** the first dispatch. The found clause names the slice, not the file's total bucket count. Machine lines stay the four-field grammar the owner named: `slice<TAB>name<TAB>S|M` and `bucket<TAB>name<TAB>S<TAB>files`. Tests are named in the bucket prose and as the implement command, not on the bucket line (a fifth field would enter `land_result`'s allow-set).

7. **`#Command` is one discover invocation per test file of this bucket.** `argv` is exactly `["python3", "-m", "unittest", "discover", "-s", <dir>, "-p", <file>]` with `tests` in a parent of the file and suffix `.py`. No `&&` in a single argv. No root shim. The driver, once slice 9 has landed, selects from the tests envelope the artifacts whose basename equals the test file that bucket's prose named. Until then every slice is S with one test file, so today's join of one artifact is already the discover form.

8. **Read jobs may name `{out}`; they may not name a snapshot write.** Job-kind CUE: `writes: "out" | "snapshot" | "none"`. `role: "read"` unifies only with `"out"` or `"none"`. A planted prompt containing `{into}` or a `snapshot/` write path is `context` naming `prompt`. For `writes: "out"`, the launcher grants the job's `out/` as writable without making the snapshot writable (Codex: `writable_roots` includes `out/` even on the read role; Grok already `auto`; Claude already `--add-dir out`). That is the ten-trip fixture. `jobs.json` prompts stay; the contradiction was sandbox, not the deliverable path.

9. **Probe allowlist is CUE data in `manifest.cue`.** `#ReadProbe` lists the forms `probes-lever.md` already names (`git` limited to `grep|log|show|rev-parse|rev-list|merge-base|for-each-ref|ls-files`; `gh` limited to `pr list|pr view|pr checks`; `python3 ops/conductor/tools/<name>.py`). A manifest section whose source is a probe command outside that list refuses `context` naming `sections.<k>.source`. `probes.py` is not in this batch; when it lands it consumes the same definition. Identity stripped remains the probes runner's job.

10. **Residual index lives at `<job>/context/residual-index`.** Objects of the whole snapshot stay under `<job>/snapshot/.git`. A test after a residual-writing close lists `tempfile.gettempdir()` and finds no `residual-index-*`.

11. **Toolchain is a required implement section, a refusal not a stub.** `#Implement` requires `sections.toolchain`. Absence is `context` naming `sections.toolchain`, before mint. The worker never starts, so it cannot stub dependencies (`20260904T101518Z`). A trial that needs `vendor/` and does not have it is class `toolchain` (expected vendor at the fixture path, found absent, needed the toolchain batch). This batch's named commands do not start that trial. Do not copy ignored `vendor/`. Do not `composer install`.

## 3. The design, short

### 3.1 Closure — `closure.cue`, `closure.py`, `closure.json`

`#ClosureIndex: close({contracts: [...#Row, ...]})`. `#Row: close({path: #NonEmpty, consumer: #NonEmpty | #DeclaredAbsent, fixture: #NonEmpty | #DeclaredAbsent})`. `closure.py check` walks `git ls-files '*.cue' 'ops/conductor/*-lever.md'`, diffs against the index, vets the index as `#ClosureIndex`, and for every closed row subprocess-checks that the fixture path exists. Cue missing: class `cue-missing`, exit 2. Cue version other than `#CueVersion`: `cue-version`. CLI stdlib only.

### 3.2 Job-kind manifests — `manifest.cue`

Reuse `#NonEmpty`, `#Digest`, `#DeclaredAbsent`, `#HarnessName`, `#IsolationObserved` from `context.cue`. New: `#CueVersion`, `#Section`, `#HarnessFacts`, `#Custody`, `#Manifest`, `#Launchable`, `#ReadProbe`, one closed definition per kind.

| kind | required slots | optional (max) | writes |
|---|---|---|---|
| `author-tests` | scope, brief, diff | plan (1), previous (1), report (1), findings (2) | snapshot |
| `check-tests` | scope, brief, diff, previous | plan (1) | out |
| `implement` | scope (the command), brief, diff, toolchain | plan (1), document (1), findings (2), markers (1), command (1) | snapshot |
| `security-audit` | scope, brief, diff | plan (1), previous (1) | none |
| `adversarial-review` | scope, brief, diff | plan (1), previous (1) | none |
| `plan` (`#PlanJob`) | scope, brief, diff | document (2) | out |
| `adjudicate` | brief, diff, findings (1–2) | none | out |
| `sweep` | scope, brief, diff | document (2) | none |

No kind has `history`. Extra key: `field not allowed`.

### 3.3 Plan, command, envelope

`#Plan` (driver document): one slice, S or M, buckets as above, files 1–3, no commas.

`#Command`: `{bucket: #NonEmpty, invocations: [...#Discover, ...]}`. `#Discover` closed argv as in decision 7.

`#Envelope`: the nine keys, closed, `additionalProperties` impossible under `close`. `#Envelope & {verdict: "changes", findings: [{...}, ...]}` so `changes` requires at least one finding. Per-kind envelopes add artifact keys where the job promises a document (`plan` requires `artifacts.plan`, `check-tests` requires a handle whose basename is `SKEPTIC.md`). Counts-versus-list remains Python (`envelope.validate`).

### 3.4 Builder — `manifest.py`

`build`, `prove`, `vet` (package `cue vet`), `vet_args` (no write), `verify` (re-digest), `cue_probe`. CLI verbs `build`, `vet`, `vet-args`. Exit 0, or one stderr line at exit 2. `DEFINITIONS` and `LAW_FILES` are module-level so launch tests can patch them.

### 3.5 Launcher, dispatcher, land, driver, meter

Order in `_launch` after `empty-comparison`: compute id, paths, prompt text (no `mkdir`); `cue_probe`; `build` + `prove` + `vet` with law; optional `--manifest` compare; only then `_preflight_isolation`, `mkdir`, snapshot, copy, render, re-digest `in/`. Write `context/manifest.json`. Record field `context` between `brief` and `caps`. Residual index under `context/`. Read-role `writes: out` gets `out/` writable. `_most_envelope_shaped` is not an accepting path.

`dispatch.sh` parses `KIND=PATH` (PATH must be a file), forwards `--given`, `--withheld`, `--manifest`, `--scope-source <scope-file as given>`, runs `vet-args` before exec.

`land.py` vets the envelope; `ladder.py` vets `#Plan` at start, builds a per-stage manifest, vets it, passes `--input KIND=PATH` / `--manifest`, and vets the recorded envelope on consume. `worth.py dispatch_rows` reads `context.manifest.total_bytes`.

## 4. The buckets

S = 1–3 files, one implement under 10 minutes. Test files belong to the tests stage. The named implement command is those test files, never `suites.sh`. Risk: **law**, **launch-path**, **instrument**, **wiring**.

Every bucket names edges from `docs/verified-couplings.md` (closure both directions, shape, behavior, freshness, permission, blast radius) and a calibration row (declared files, tests, lines, minutes).

### Slice 1 — `closure-index` (S) — FIRST. Own PR.

Files: `ops/devlane/harness/closure.cue` `ops/devlane/harness/closure.py` `ops/devlane/harness/closure.json`

- Unblocks: every later contract must be a closed row; 2 runs the same binary in CI.
- Risk: law.
- Edges: `closure.py → closure.cue` (package `harness`, helpers from `context.cue`); `closure.py → git ls-files` (the inventory is the tree, not a remembered list); `closure.py → cue` (probe `cue_probe`, contract `#CueVersion`). Guarantees: a tracked `.cue` or `*-lever.md` absent from the index refuses `closure` naming `path`; a named consumer path that does not exist refuses naming `consumer`; this batch's new law files are not `declared_absent`.
- Depends on: nothing.
- Lands green alone: yes. New files. No suite reads them until slice 2 and the new test file.
- Tests, `ops/devlane/harness/tests/test_closure_gate.py`. Why red at this ref: the three files are absent, so the subprocess `python3 ops/devlane/harness/closure.py check` exits nonzero (file not found) and the assertions on stdout never run. Cases: live tree, index complete versus `git ls-files '*.cue' 'ops/conductor/*-lever.md'` (19+6); planted extra `.cue` in a temp clone refuses `closure` naming that path; planted row with missing consumer path refuses; `PATH` without `cue` exits 2 class `cue-missing`; fake `cue` printing `v0.14.1` exits 2 class `cue-version`; unclosed set equals §1's rows with no consumer (capabilities four, workflow cue except the commitmsg hit, `probes-lever.md`). A host without cue makes this file red, never skipped.
- Named command: `python3 -m unittest discover -s ops/devlane/harness/tests -p test_closure_gate.py`
- Calibration: files 3, tests 1, lines ~250, minutes 8.

#### First-run walkthrough

- assumption: implement runs under the worker's isolated HOME (`GROK_HOME`/`CODEX_HOME` at `<job>/home/<harness>`, `auth.json` only) — measured: `dispatch/CONTRACT.md` isolation table; this command is stdlib + `cue` on the host PATH, which the child's environment still has as `/home/scientdb/.local/bin` on the self-hosted runner (`ci.yml:30–31`).
- assumption: no network — measured: the named command does not fetch; `cue vet` is local. Refusal if a test shells out to `gh`: not in this file.
- assumption: Codex snapshot `.git` is writable for implement — measured: implement is `role: write`, Codex `workspace-write`. This slice's files are new; no need to rewrite `.git`.
- assumption: the job prompt is `jobs.json` `implement` at this ref, scope = the named command — measured: `jobs.json:78–85`.
- assumption: self-hosted runner has `cue` v0.17.1 — measured: `cue version` on this host; `ci.yml:55` already prints it on the `app` job. Refusal: `cue-missing` if PATH has none.
- assumption: tests do not copy `symfony-app/vendor` — measured: this bucket's files and the named test live under `ops/devlane/harness/`. If a trial has no vendor, this command never starts phpunit against it.

### Slice 2 — `closure-ci` (S). Same PR as slice 1.

Files: `ops/bin/suites.sh` `.github/workflows/ci.yml`

- Unblocks: "CI runs the vet fixtures"; a runner without cue is a red step, not a skipped unittest.
- Risk: wiring.
- Edges: `suites.sh → closure.py` and `vet_context.py` (named steps, not only unittest collection); `ci.yml lane → cue version` and those same two binaries. `laneconf.py closure` reads job names, not steps, so `CHECK_NAMES` is untouched. Guarantee: `vet_context.py` without cue already exits 2 (`vet_context.py:249–252`); the new step must not wrap that in `|| true`.
- Depends on: 1.
- Lands green alone: yes on this runner (`vet_context.py` already exits 0 here).
- Tests, `ops/devlane/harness/tests/test_vet_gate.py`. Why red at this ref: `ci.yml` `lane` job has no `cue version` and no `vet_context.py` / `closure.py` (`sed -n '24,45p' .github/workflows/ci.yml`); `suites.sh` is unittest only (44 lines). Assertions: `suites.sh` contains the two python3 invocations; `ci.yml` `lane` has a step whose `run` names `closure.py check` and one that names `vet_context.py` and a `cue version` line in that job; running `vet_context.py` still prints `24 control(s)` (silent neighbour, kept).
- Named command: `python3 -m unittest discover -s ops/devlane/harness/tests -p test_vet_gate.py`
- Calibration: files 2, tests 1, lines ~40, minutes 5.

#### First-run walkthrough

- assumption: editing `suites.sh` does not require network or vendor — measured: the file is bash, 44 lines.
- assumption: CI `lane` job PATH includes `~/.local/bin` — measured: `ci.yml:30–31`.
- assumption: adding steps does not add a `ci.yml` job name, so `laneconf.py closure` stays green — measured: that tool reads job names (`CHECK_NAMES='lane app'`). Refusal if a new job is added: `conf-key` / literals elsewhere; this slice must not add a job.

### Slice 3 — `context-manifests` (S). Own PR (the law files).

Files: `ops/devlane/harness/manifest.cue`

- Unblocks: 4, 5, 6.
- Risk: law. A definition too loose passes every negative test (AAR: failures land on the side of agreement). Each refuse case is one path away from a positive planted in the test.
- Edges: `manifest.cue → context.cue` (same package; every helper named exists). Guarantee: every kind closed; no `history`; `#Implement` requires `toolchain`; `#CueVersion` is `v0.17.1`; `#ReadProbe` lists the probes-lever forms.
- Depends on: nothing (CUE only). Lands green alone: yes.
- Tests, `ops/devlane/harness/tests/test_manifest_law.py`. Why red at this ref: `manifest.cue` absent; `cue vet -d '#Implement' … manifest.cue` exits 1 on a missing file. Cases (JSON planted in temp, package vet): eight kinds validate as themselves and as `#Launchable`; `sections.history` and `sections.notes` are `field not allowed` under every kind; dropped `sha256` incomplete; `plan.bytes` 32769 out of bound; pending `brief` accepted by the kind, refused by `#Launchable`; implement without `toolchain` refused naming `sections.toolchain` (fixture `20260904T101518Z`); probe source not in `#ReadProbe` refused; `cue export -e '#CueVersion'` prints `"v0.17.1"`.
- Named command: `python3 -m unittest discover -s ops/devlane/harness/tests -p test_manifest_law.py`
- Calibration: files 1, tests 1, lines ~200, minutes 8.

#### First-run walkthrough

- assumption: `cue vet` of a temp JSON against the new file needs the package (context.cue + evidence.cue + manifest.cue) — measured: per-file `evidence.cue` fails `#NonEmpty`; package vet of `./ops/devlane/harness/` exits 0. Tests pass all three paths. Refusal: a test that vets `manifest.cue` alone will fail on helpers; that is a test bug, not an implement workaround.

### Slice 4 — `stage-documents` (S). Same PR as slice 3.

Files: `ops/devlane/harness/plan.cue` `ops/devlane/harness/command.cue` `ops/devlane/harness/envelope.cue`

- Unblocks: 5 (builder vets them), 8–9 (driver and land consume them).
- Risk: law.
- Edges: each file → `context.cue` (`#NonEmpty`). `#Plan` does not collide with `ops/capabilities/contracts/plan.cue` because vet always names this file. Guarantee: M with 1 or 3 buckets does not evaluate; a comma inside a file token does not evaluate; `#Command` argv is the discover five-tuple plus `-s`/`-p` values; `#Envelope` `verdict: "changes"` requires a non-empty findings list (fixtures `20260904T150457Z`, `20260904T144439Z`); a partial object with a subset of keys does not evaluate (fixture `20260904T122257Z`).
- Depends on: nothing. Lands green alone: yes.
- Tests, `ops/devlane/harness/tests/test_stage_docs_law.py`. Why red at this ref: the three files are absent. Cases: a one-slice S plan with one bucket of two files vets; a three-slice document does not; comma-joined files do not; discover argv vets; `python3 tests/foo.py` does not (fixture `20260904T130010Z`); `changes` + `findings: []` does not; a seven-key object does not.
- Named command: `python3 -m unittest discover -s ops/devlane/harness/tests -p test_stage_docs_law.py`
- Calibration: files 3, tests 1, lines ~180, minutes 8.

#### First-run walkthrough

- assumption: same cue package discipline as slice 3 — measured: same.
- assumption: capabilities `#Plan` is not loaded — measured: tests pass `plan.cue` as the schema file, not `ops/capabilities/contracts/plan.cue`.

### Slice 5 — `context-builder` (S)

Files: `ops/devlane/harness/manifest.py`

- Unblocks: 6, 7, 8, 9.
- Risk: instrument.
- Edges: `manifest.py →` the four law files + `context.cue` + `evidence.cue` (`LAW_FILES`); `manifest.py → isolation.py` (harness facts); `manifest.py → cue` (probe + mock by PATH). Guarantees: section digests equal `sha256sum`; `total_bytes` equals the sum; `--section history=PATH` refuses `context` naming `sections.history`, writes nothing; unknown kind refuses `context`, never a fallback.
- Depends on: 3, 4.
- Lands green alone: yes; new module, own suite.
- Tests, `ops/devlane/harness/tests/test_manifest_builder.py`. Why red at this ref: `manifest.py` absent; load-by-path fails the assertion, not collection (same `require_module` idea as `launch_support.py:6–10`). Cases: `build` on planted files vets as `#PlanJob`; `vet-args` prints JSON, writes no path under `tempfile.gettempdir()`; digest edit makes `verify` name the path; `prove` fills `withheld_present` / `given_unmet`; PATH without cue → `cue-missing`; fake cue v0.14.1 → `cue-version`.
- Named command: `python3 -m unittest discover -s ops/devlane/harness/tests -p test_manifest_builder.py`
- Calibration: files 1, tests 1, lines ~350, minutes 9.

#### First-run walkthrough

- assumption: `vet-args` can refuse without minting a job directory — measured: this module does not call `launch.py`. Finding 4: it must not write `/tmp`. The test lists `gettempdir()` before and after.
- assumption: no vendor install — measured: stdlib + cue.

### Slice 6 — `context-launcher` (S). Launch-path PR with 7.

Files: `ops/devlane/dispatch/launch.py` `ops/devlane/dispatch/record.py` `ops/devlane/dispatch/CONTRACT.md`

- Unblocks: every record minted after this carries `context.manifest`; the four planted-input refusals; residual index move; read-role `out/` writable; envelope fallback gone.
- Risk: launch-path. Fake-CLI suite and `test_launch_refusals.py` (722 lines) are the floor; run the named file, not `suites.sh`.
- Edges: `launch.py → manifest.py` in-process (`launch.MANIFEST` patchable); `record.py FIELDS` order; argv from `dispatch.sh` (slice 7). Guarantees kept: refusal mints nothing; `_portable_paths` holds. Guarantees added: `context` between `brief` and `caps`; `context.sha256` equals `context/manifest.json`; implement without `--input toolchain=PATH` refuses `context` naming `sections.toolchain` (no worker, so no stub); `GIT_INDEX_FILE` is `<job>/context/residual-index`; Codex read + `writes: out` includes `out/` in `writable_roots` (fixture `20260904T063409Z`); `_most_envelope_shaped` is not used to accept a schema-invalid object (fixture `20260904T122257Z`); `changes` + empty findings is schema-invalid.
- Depends on: 3, 5.
- Lands green alone: yes, provided the tests stage updates `launch_support.py` `RECORD_FIELDS` (tests-owned). No conf key, so `test_launch_lane_conf.py` stays.
- Tests, `ops/devlane/dispatch/tests/test_launch_context.py`. Why red at this ref: no `context` in `FIELDS`; `--input document=PATH` is copied as a file named `document=PATH` or fails; `--given` / `--manifest` are unknown to argparse (exit 2, not a `context` line). Cases: `plan` launch with `--input document=PATH` closes with `context.manifest` vetting as `#PlanJob` and `#Launchable`; four planted inputs refuse `context` exit 3 naming `sections.history`, `sections.plan.bytes`, digest mismatch via `--manifest`, `sections.notes`, no job dir; bare `--input PATH` refuses `context` naming the kind; implement without toolchain refuses; PATH without cue refuses `cue-missing` and mints nothing; close/resume of a planted pre-manifest record writes `declared_absent`; after residual close, `gettempdir()` has no `residual-index-*` and `<job>/context/residual-index` was used; a grok/codex raw.out that is a seven-key object is recorded `invalid`, not `ok`; Codex read argv for `check-tests` contains `writable_roots` with `out/`. `CONTRACT.md` names the new refusal classes and the `context` field (red: absent).
- Named command: `python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_launch_context.py`
- Calibration: files 3, tests 1, lines ~400 of new test plus edits to 1757+111+contract, minutes 10.

#### First-run walkthrough

- assumption: tests use the fake CLI in `launch_support.py`, not a live harness — measured: that module's `_FAKE_CLI`; no network.
- assumption: host `cue` is on PATH inside the fake launch — measured: this environment. Refusal: `cue-missing` is itself a test case.
- assumption: isolated HOME of a real worker is not this suite's HOME — measured: launch tests plant `DISPATCH_JOBS` and a fake executable. They must not write the operator's `/tmp` residual index; the assertion is on `gettempdir()` of the test process.

### Slice 7 — `context-dispatcher` (S). Same PR as 6.

Files: `ops/conductor/tools/dispatch.sh`

- Unblocks: hand launches and the driver reach `vet-args` before `launch.py`.
- Risk: instrument. Dry-run JSON is what the driver parses; new flags must survive `print_launch` in order.
- Edges: `dispatch.sh → manifest.py vet-args` (before exec); `dispatch.sh → launch.py` argv. Guarantee: `KIND=PATH` reaches argv verbatim; a missing PATH half refuses before launch; `--dry-run` still creates nothing; `vet-args` failure is class `context` on stderr, wrapper exit 3, launcher not exec'd (print_launch may still show argv on dry-run; live run must not exec on vet failure).
- Depends on: 6 (launcher must accept the flags). A foreground launch with them at this ref is argparse exit 2.
- Lands green alone: yes against stub launchers in `test_dispatch_wrapper.py`.
- Tests, appended rows in `ops/conductor/tests/test_dispatch_wrapper.py` (the tests stage appends; implement only edits `dispatch.sh`). Why red at this ref: `[[ -f $input ]]` on the whole `KIND=PATH` token fails (`dispatch.sh:174–177`); `--given` / `--manifest` hit unknown-flag refusal (`153`); no `--scope-source`; no `vet-args`. Cases: `--input plan=PATH` reaches argv; missing PATH refuses naming the path; `--given`, `--withheld`, `--manifest` reach argv in order, repeatable; every dry-run argv carries `--scope-source` then the scope file as given; a failing `vet-args` stub prevents exec; a bare `--input PATH` still forwards (silent neighbour).
- Named command: `python3 -m unittest discover -s ops/conductor/tests -p test_dispatch_wrapper.py`
- Calibration: files 1, tests 1 (file already 1518 lines; new cases only), minutes 8.

#### First-run walkthrough

- assumption: dispatcher runs on the conductor host, not in the worker HOME — measured: `dispatch.sh` is the parent of `launch.py`. `cue` / `python3` are host PATH. Isolated worker HOME applies to the child after exec.
- assumption: `vet-args` writes nothing — measured: slice 5's contract; this wrapper must not add a `mktemp` under `/tmp` for the manifest. Detach already uses `mktemp -p "$jobs_root"` (`dispatch.sh:261`), which is the jobs root, not `/tmp`. Do not add another.

### Slice 8 — `context-land` (S)

Files: `ops/conductor/tools/land.py` `ops/conductor/land-lever.md`

- Unblocks: consumer-at-land acceptance; `changes` with no findings cannot land (fixture `20260904T144439Z`).
- Risk: instrument.
- Edges: `land.py → manifest.py vet` (envelope document, `-d '#Envelope'` and the job kind); `land.py → cue` through that only. Guarantee: cue-vet runs after `envelope-status` and before the first pick; failure class `context`, exit 2, `n=0` landed; cue-missing is `cue-missing`, exit 2, not a skip.
- Depends on: 4, 5. Envelope CUE and builder must exist. Does not depend on 6 to land green: tests plant a record directory.
- Lands green alone: yes.
- Tests, appended in `ops/conductor/tests/test_land_lever.py`. Why red at this ref: `land.py` has no `cue` / `manifest.py` call (`grep cue` over the file is empty). Cases: planted `ok` envelope that vets as `#Envelope` lands; planted `changes` with empty findings refuses `context` naming `findings`; planted seven-key object refuses `context`; PATH without cue refuses `cue-missing` and does not pick.
- Named command: `python3 -m unittest discover -s ops/conductor/tests -p test_land_lever.py`
- Calibration: files 2, tests 1, minutes 8.

#### First-run walkthrough

- assumption: land tests plant `XDG_STATE_HOME` / `HOME` — measured: `instrument-conventions.md:47–48`. Isolated HOME of the test is a temp dir, not the operator's.
- assumption: no network — measured: land shells only to `git`.

### Slice 9 — `context-plan` (S). Driver PR with 10.

Files: `ops/conductor/tools/ladder.py`

- Unblocks: `#Plan` before the first dispatch (fixtures `20260904T132749Z`, `20260904T132831Z`); per-bucket `#Command` so a later M slice is possible; discover form vetted (fixture `20260904T130010Z`).
- Risk: instrument.
- Edges: `ladder.py → manifest.py` subprocess (`vet` of the synthesized `#Plan` JSON and of `#Command`); `parse_plan` found clause names the slice. Guarantee: a three-slice plan file refuses `plan` (or `context`) with found `3 slices`, not `N buckets`; comma-joined files refuse; `derive_command` emits `#Command` JSON, vets it, and writes the discover argv for **this bucket's** named test file only. Until other slices use M, the selection of one artifact matches today's join of one.
- Depends on: 4, 5, 7 (flags). Scratch `seed_repo` must copy `manifest.py`, `isolation.py`, `context.cue`, `evidence.cue`, `manifest.cue`, `plan.cue`, `command.cue`, `envelope.cue` (copy-tool-bytes, already the rule at `test_ladder_lever.py:19`). That copy is tests-stage work on `test_ladder_lever.py`.
- Lands green alone: yes against the stub dispatcher, once the tests stage extends the scratch copy.
- Tests, appended in `ops/conductor/tests/test_ladder_lever.py` class `PlanGrammar`. Why red at this ref: `parse_plan:340–353` counts all buckets; `derive_command` does not vet and joins every artifact. Cases: three `slice` lines refuse with found containing `3 slice`; comma-joined files refuse; M with two S buckets still launches two implements (`test_m_slice_of_two_s_buckets_implements_twice_then_audits_once` stays green); two test artifacts yield a first implement argv whose scope is only the first bucket's test file (after this slice; at this ref the join includes both, which is the red for the new assertion).
- Named command: `python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever.py`
- Calibration: files 1, tests 1, minutes 10.

#### First-run walkthrough

- assumption: ladder tests stub `dispatch.sh`, `launch.py`, `land.py`, `findings.py` — measured: `seed_repo` writes those stubs. This slice must not stub `manifest.py`: it copies the real bytes. Cue on PATH in the scratch environment is the host cue unless the test deletes it (`cue-missing` case in slice 10).
- assumption: the named command runs the whole `test_ladder_lever.py` (2962 lines) — measured: discover `-p` that file. Minutes cap is 10 for implement, not for this suite; the suite already runs in CI. Implement is done when that file is green on the new assertions.

### Slice 10 — `context-driver` (S). Same PR as 9.

Files: `ops/conductor/tools/ladder.py` `ops/conductor/ladder-lever.md`

- Unblocks: driver-built manifests that vet; no `history` by construction; `load_envelope` vets at consume; calibration `measured.context`; `cue-missing` after `gh-missing`.
- Risk: instrument.
- Edges: `ladder.py → dispatch.sh` argv (`KIND=PATH`, custody, `--manifest`); `ladder.py →` dispatch record `context.manifest` by digest. Guarantee 5 **Context** joins `ladder-lever.md`: every stage vets as its kind before dispatch; recorded manifest equals the expectation on supplied sections; stage table has no `history` kind; failure stops `reason=context`.
- Depends on: 6, 7, 9.
- Lands green alone: yes with the same scratch-copy extension (tests stage).
- Tests, further rows in `test_ladder_lever.py`. Why red at this ref: `inputs_for` (`970–1015`) returns bare paths, no kinds; no `--manifest`; `load_envelope` does not cue-vet; `validate_preconditions` has `gh-missing` only; `calibrate` (`1193–1237`) has files/tests/lines/minutes/findings, no `context`. Cases: every stage argv has `--input KIND=PATH` from the §3.2 table, `--manifest` naming a file that vets as that kind; stage row `context: {path, sha256, bytes}`; `measured.context` per stage; stub record with differing digest stops `reason=context` exit 3; PATH without cue but with `gh` refuses `cue-missing`; `gh-missing` still wins when both are absent; no stage manifest has a `history` key.
- Named command: `python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever.py`
- Calibration: files 2, tests 1, minutes 10.

#### First-run walkthrough

- assumption: same scratch as slice 9, plus a stub dispatcher that echoes `--manifest` into `context.manifest` (plant knob for a differing digest) — that stub is tests-stage, extending the existing stub dispatcher, not a new substitute of cue or vendor.
- assumption: `ladder-lever.md` is documentation of argv and guarantee 5; the tests pin the strings that must appear.

### Slice 11 — `context-meter` (S). May ride the driver PR.

Files: `ops/devlane/telemetry/worth.py` `ops/process/worth.md`

- Unblocks: the meter shows context bytes per stage.
- Risk: instrument; read-only over records.
- Edges: `worth.py → record.context.manifest.total_bytes`. Absent or `declared_absent` is `unrecorded`, never 0 (`worth.md` §3 as amended).
- Depends on: the field name from 6, not its landing. Tests plant records.
- Lands green alone: yes.
- Tests, `ops/devlane/telemetry/tests/test_worth_context.py`. Why red at this ref: `dispatch_rows` (`worth.py:488–537`) never reads `context`. Cases: planted job with `total_bytes` prints `context=<n>` on the report row and in JSON; planted job without the field prints `unrecorded`; `declared_absent` prints `unrecorded`; `waste` entries carry the same.
- Named command: `python3 -m unittest discover -s ops/devlane/telemetry/tests -p test_worth_context.py`
- Calibration: files 2, tests 1, minutes 5.

#### First-run walkthrough

- assumption: worth tests plant records under a temp repo — measured: existing `test_worth_dispatches.py`. No network, no cue, no vendor.

## 5. Order, PRs, value

Dependencies: 1 → 2; 3 → 5 → 6 → 7; 4 → 5, 8, 9; 6+7+9 → 10; 6's field name → 11.

Run as eleven S ladders in that number order. Parallel-safe after 1: 3 with 2; 4 with 3; 11 with anything after 6; 8 with 6.

Value order: the gate that makes an unrun contract a refusal; the four shapes; the builder; the dispatcher/launcher (before a worker); land (the consumer); the driver (cannot feed history); the meter.

Own PRs: slices 1–2 (closure); slices 3–4 (law files); slices 5–7 (launch path); slices 8–10 (land + driver); slice 11 may ride 8–10.

Audits once per batch: a hand decision on each run, recorded on the ladder record, requesting the full pair on the last PR. The driver still audits every run; skipping is not a flag it offers.

## 6. Acceptance, mapped to proof

| acceptance (scope) | proved by |
|---|---|
| planted extra section, over-cap, digest mismatch, `history` each stop the dispatcher with `context` naming the field; a clean manifest launches | 6 `test_launch_context.py`; 7 forwards; 5 mutants |
| every record minted after this carries `context.manifest` | 6 field/order tests; `record.validate`; pre-manifest `declared_absent` |
| meter shows context bytes per stage | 11 `test_worth_context.py`; 10 `measured.context` |
| driver's stages produce manifests that vet clean for a planted ladder | 10 ladder rows calling `cue vet -d '#<Kind>'` |
| closure: every `.cue` and conductor lever names consumer and fixture, or the gate refuses | 1 live-tree index + planted extra file; 2 CI step |
| `changes` without findings does not land / is not accepted | 4 envelope CUE; 6 parser; 8 land; 10 `load_envelope` |
| `#Plan` vetted before the driver starts | 9 `parse_plan` + cue |
| discover-form command, no shim | 4 `#Command`; 9 `derive_command` |
| toolchain declared or implement does not start | 3 `#Implement`; 6 refusal (fixture `20260904T101518Z`) |
| read job can write `out/` without writing the snapshot | 6 Codex `writable_roots` (fixture `20260904T063409Z`) |
| no `/tmp` index | 5 `vet-args`; 6 residual path |
| `bash ops/bin/suites.sh` green; `ruff check .` clean; conf closure and literals clean; CI runs the vet fixtures | each bucket's named command; `ruff.toml` already grants S603/S607 on `ops/devlane/harness/*.py`; no conf key; slice 2 |

## 7. Residue, named

- **The section is still the file.** The driver still hands a stage the whole plan and whole dispatch records. Caps bound them; the kind slot refuses `history`. Cutting the plan per unit and passing `result.envelope` alone is a later bucket on `ladder.py`.
- **The tree is not in the manifest.** Jobs are `snapshot: whole`. Fileset staging is plan `20260904T000335Z-plan-claude-28b1a2` unit C and I-009, not this batch.
- **Observed isolation stays unresolved** on live records; `#Dispatchable.operator_config_present: false` is not applied to live dispatches.
- **Doctrine chain** (`#Doctrine`) is not in the manifest.
- **Caps for `plan`, `diff`, `report`, `document`, `markers` are declared**, not measured from the four hand-built inputs the scope named (those files are not in the tree). The first ten manifests are the measurement.
- **Two wires.** Launcher and dispatcher refuse at exit 3; land and the instruments at exit 2. Unchanged.
- **M slices** wait on slice 9. This plan's machine lines are all S so today's joined command cannot fail the first implement on a second bucket.
- **`go.sh` / hand launches must say the kind** (`--input KIND=PATH`). Forgetting is a `context` refusal before mint.
- **`jobs.json` prompts are unchanged.** The ten trips are fixed by sandbox, not by deleting `{out}`.
- **`probes.py` is still absent.** The allowlist is data in `manifest.cue`; the instrument is not this batch.
- **Symfony `vendor/`** stays gitignored. Installing from the host composer cache is the toolchain batch.
- **`matrix.py` is absent at this SHA.** The dispatcher carries the vet.
- **Not measured here:** cue's exact error text for a required field omitted from a list-typed slot (tests stage measures it and pins the path).

## Machine lines

slice	closure-index	S
bucket	closure-index	S	ops/devlane/harness/closure.cue ops/devlane/harness/closure.py ops/devlane/harness/closure.json
