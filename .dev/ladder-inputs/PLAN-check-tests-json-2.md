# Item 31 batch, slice 2 — security re-audit findings

Tree: `188394d0fc87904079adbf72f3e6143f91982fca` (`lane/check-tests-json`).
Record: `20260904T140242Z-review-codex-69d0fb`, verdict `changes`, counts `p1=2 p2=2 p3=1`.
D-LADDER-1 (ratified): no second fix round on the first ladder; this slice runs the whole ladder on this branch: tests (Grok) → skeptic once → one implement run per S bucket → audits once → one fix round → security re-audit → draft PR.

This file is the plan only. No code, no tests.

## Slice shape

One slice, size **S**, one named S bucket, three files, one implement run.

M was considered and rejected: at this ref the driver derives one test command from the first tests envelope (`ladder.py` `derive_command`, `stage_scope` passes `test-command.md` as `--scope-file` for every `code` / `code-N` stage). Two S buckets would therefore receive the same command. The first run could not go green without editing the second bucket's files, and the second run would have nothing left to do. That is not "each landed and green alone". L (two slices) is not required: three files is inside the S bound (1–3 files, under 10 minutes).

This slice is the batch's second slice and deserves its own draft PR (the ladder `pr` stage). It does not share a PR with slice 1. There is no second slice in this plan.

Value order inside the one implement run: finding 1, then finding 2, then finding 4's pin, then finding 3, then finding 5. p1 first.

## Findings in scope (verbatim claims, this ref)

Measured at `188394d0` this session. Each still holds.

1. **p1** — `ops/devlane/task/jobs.json:72`; `ops/conductor/tools/ladder.py:799-805,1419-1423`. Declared: jobs.json says “verdict is changes when any finding exists and approve otherwise.” Practiced: validation rejects only `verdict == "approve" and bool(findings)`. A schema-valid `changes` envelope with no findings is accepted and dispatches tests-fix with an empty specification.
2. **p1** — `ops/conductor/ladder-lever.md:99-111`; `ops/conductor/tools/ladder.py:997-1007`. Declared: the ladder record names a “driver-written check-tests findings file.” Practiced: `findings_payload.write_text(...)` follows a pre-existing symlink, after which `findings_file.symlink_to(...)` creates another symlink. A write-stage worker can plant the predictable payload symlink and redirect the driver's later write outside the worktree.
3. **p2** — `ops/devlane/task/tests/test_check_tests_json.py:44-68,121-226`; `ops/devlane/task/tests/test_jobs.py:41-63,269-332`. Declared: the tests say the read-role prompt “rejects any write path, not a blacklist.” Practiced: the regex still lists selected write verbs and requires a slash, extension, or `{out}`. `Create REVIEW in the repository` passes all 13 relevant tests.
4. **p2** — `ops/conductor/tests/test_ladder_lever.py:3367-3400`. Declared: malformed check-tests envelopes must be validated before routing. Practiced: `test_findings_none_does_not_move_to_tests_fix` asserts only that later stages and payload files are absent; it never requires a nonzero result or the `envelope` refusal. A driver that silently returns success passes this test.
5. **p3** — `ops/devlane/task/CONTRACT.md:131-138`; `ops/devlane/task/jobs.json:55-72,90-95`. Declared: CONTRACT.md still says “all three read jobs name `{inputs}`.” Practiced: plan's prompt names only `{ref}`, `{out}`, and `{scope}`; only check-tests and adjudicate name `{inputs}`.

The Symfony vendor-tree rule in the input does not apply here. Stubs, bypasses, walkthroughs, and “pin the refusal, not the absence” do.

## Bucket `reaudit-findings` (S)

### Files (implement)

- `ops/conductor/tools/ladder.py` — findings 1 and 2 (finding 4's production gate is the same `validate_check_tests` path).
- `ops/devlane/task/write_path.py` — finding 3. Absent at this ref. The write-path detector lives in the two test files today; the implementer is forbidden from editing those files (`jobs.json` implement constraints). Tests-stage points both files at this module through `support.load("write_path")` with no local regex fallback. Implement creates the module.
- `ops/devlane/task/CONTRACT.md` — finding 5. Align the slots sentence with practiced prompts. Do not add `{inputs}` to plan's prompt. Do not edit the job table (see edges).

Not in the bucket: `jobs.json` (check-tests already states the verdict rule; other jobs are hash-frozen), `ladder-lever.md` (already names the driver-written findings file), `envelope.py`, `launch.py` `_schema_valid` (both accept empty `changes`; that is the general envelope, not the check-tests gate).

### Tests, by file, and why each is red at this ref

Tests-stage writes and proves these red. Implement does not edit them.

`ops/conductor/tests/test_ladder_lever.py` (extend `CheckTestsEnvelopeValidatedBeforeFindingsFile` and add a write-time findings-file class beside `FindingsFilePathStaysInsideLadderInputs`):

- **changes with no findings is an `envelope` stop.** Plant `verdict=changes`, `findings=[]`, counts all zero. Require `assert_stopped(..., stage="check-tests", reason="envelope")` (exit 3), `tests-fix` not dispatched, no findings payload written. Why red: `Driver.validate_check_tests` accepted that envelope this session (`schema_valid True`; validate printed `accepted changes with no findings`). `envelope.validate` accepted it too. Routing at `ladder.py:1419-1423` would then run tests-fix.
- **payload symlink is not followed.** Plant `check-tests-findings.payload.json` as a symlink to a host file whose body is `HOST`, then take the driver's findings write. Require: the host file still reads `HOST`; the write does not land outside the worktree; tests-fix is not given a path outside ladder inputs. Why red: the finding 2 reproduce this session wrote the findings JSON through the symlink (`outside_changed True`, payload remained a symlink). This is the bypass; a test that only checks a different filename while `write_text` still follows a symlink is not the pin.
- **`test_findings_none_does_not_move_to_tests_fix` requires the refusal.** Use `assert_stopped(..., reason="envelope")` (exit 3), not only “tests-fix absent and no payload”. Why red at this ref against a silent-success double: the finding 4 reproduce passed this session (`absence-only test accepted a result with no returncode or refusal`). Against the live driver, `findings is None` already raises `Stopped` reason `envelope` (measured this session). The rewrite pins that refusal so a silent success cannot pass. Do not leave the method as an absence-only test.

`ops/devlane/task/tests/test_check_tests_json.py` and `ops/devlane/task/tests/test_jobs.py`:

- **`write_path_ask` comes from `ops/devlane/task/write_path.py`**, loaded the way `support.load` already loads sibling modules (`ops/devlane/task/tests/support.py:29-37`). No in-file regex, no fallback that restores the current pattern. Why red: `ops/devlane/task/write_path.py` is absent (`ls`: no such file). `support.load("write_path")` cannot exec it.
- **`Create REVIEW in the repository` is a write path** (extensionless relative name, no slash, no `{out}`). Why red: this session `write_path_ask("Create REVIEW in the repository")` returned `None`; the 13-test plant of that string as the live check-tests prompt ran `OK` (`wrong extensionless write prompt accepted True`). After the detector exists, that plant must not be a clean suite.
- The live check-tests prompt at this ref must still not be a write path, and must still contain `Return the JSON envelope on stdout and leave artifacts empty.`

`ops/devlane/task/tests/test_jobs.py` (or the check-tests tests file, one place is enough if both files load the same detector):

- **CONTRACT.md does not claim that all three read jobs name `{inputs}`.** Practiced slots at this ref: plan `{ref, out, scope}`; check-tests `{ref, inputs, scope}`; adjudicate `{inputs, ref, out}`. Why red: `CONTRACT.md:133-135` still contains `all three read\njobs name `{inputs}`` (measured this session).

Pin refusals, not silence. Finding 4 is the named instance of that class. Finding 2's test must fail if the host file changes. Finding 3's tests must fail if the detector is missing or still requires a slash, an extension, or `{out}`.

### Named implement command

Never `suites.sh`, never the whole suite. Discover, because a module import of the task tests fails (`No module named 'support'`, measured this session).

```
python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever.py && python3 -m unittest discover -s ops/devlane/task/tests -p test_check_tests_json.py && python3 -m unittest discover -s ops/devlane/task/tests -p test_jobs.py
```

235 bytes. `SCOPE_CAP` is 1024 (`ops/lane.conf:26`). `CheckTestsEnvelopeValidatedBeforeFindingsFile` plus `FindingsFilePathStaysInsideLadderInputs` ran in 3.5s this session; the task tests are sub-second once discover puts `ops/devlane/task/tests` on `sys.path`.

### Edges and guarantees (`docs/verified-couplings.md`)

Edge: check-tests envelope → `validate_check_tests` → tests-fix routing.

- Closure: jobs.json:72 declares changes iff any finding exists; the driver is the live counterparty. Schema-valid is not sufficient.
- Shape: a check-tests envelope still has the wire fields; `verdict=changes` with an empty findings list is invalid for this job.
- Behaviour: empty `changes` stops as `envelope` (exit 3) before a findings file is written and before tests-fix is minted. Valid `changes` with a quotation-pair list still moves to tests-fix (`test_validated_changes_still_moves_to_tests_fix` stays green).
- Permission: the driver may write the findings payload only as a regular file inside `inputs_dir` (`.dev/records/ladders/<id>/` in the worktree). The job directory rule in `ops/devlane/dispatch/CONTRACT.md` is the dispatch side of the same law: a dispatch writes under its job directory; the ladder writes under that inputs dir, not through a symlink to the host.
- Blast radius: `validate_check_tests` and `ledger_result` in `ladder.py`. Not `envelope.py`.

Edge: findings payload write → host filesystem.

- Closure: `check-tests-findings.payload.json` must be a regular file inside `inputs_dir`. A pre-existing symlink is a planted fault, not a destination.
- Behaviour: host target unchanged; no follow. Replacing the symlink with a regular file inside inputs, or stopping before the write, are both refusals of the bypass. Writing through the symlink is the bypass.
- Blast radius: `ladder.py:997-1007` only. Consume-time `Path.resolve` checks at `1045-1057` already exist and are not this finding.

Edge: read-role prompt tests → write-path detector → live `jobs.json` check-tests prompt.

- Shape: a write verb plus a path-shaped token. Path-shaped includes an extensionless relative name (`REVIEW`), not only slash, extension, or `{out}`.
- Behaviour: `Create REVIEW in the repository` is a write path; the live check-tests prompt is not.
- Blast radius: `write_path.py`. Both test files load it. `jobs.json` is not edited.

Edge: `CONTRACT.md` slots sentence → practiced `jobs.json` prompts.

- Freshness: the sentence is true of this ref's prompts or it is wrong.
- Behaviour: plan does not name `{inputs}`; check-tests and adjudicate do.
- Blast radius: the slots paragraph only. `TheDocAndTheRegistryAgree` in `test_run.py:1452-1491` compares the job table to `jobs.json`; do not retitle or drop table rows.

### Calibration (declared)

| files | tests (new or changed methods) | lines | minutes |
|---|---|---|---|
| 3 | 8 | 220 | 8 |

Under the 10-minute S bound. Implement wall in `jobs.json` is 3600s; do not use that as the bucket size.

## First-run walkthrough

First run of this bucket = the implement job (Codex, write, whole snapshot) with the command above as `{scope}`.

- assumption: the worker's Codex home is `<job>/home/codex` holding `auth.json` only — measured: `ops/devlane/harness/isolation.py:102-106`; `ops/devlane/dispatch/CONTRACT.md:126,171`.
- assumption: `CODEX_HOME` is that directory; Codex does not also relocate `HOME` — measured: `isolation.py:105` `home_env` is `CODEX_HOME`; grok is the harness with `also_env: ["HOME"]` (`isolation.py:118-127`).
- assumption: the child cwd is the snapshot — measured: `ops/devlane/dispatch/CONTRACT.md:158`.
- assumption: no network — measured: implement constraints `jobs.json:86-88`; Codex containment is `os` (`launch.py:262`); sandbox is `workspace-write` for write roles (`launch.py:259`).
- assumption: writable roots are the snapshot cwd, `/tmp`, and the job `out/` — measured: `launch.py:418-422`.
- assumption: `.git` is read-only for Codex; a denied `git commit` is not a failed job — measured: `launch.py:1113-1126`; implement prompt `jobs.json:84` (write `out/COMMIT_MSG` or a commit object; the launcher commits).
- assumption: `{scope}` is the derived test command, not the slice prose — measured: `ladder.py:587-591` `stage_scope` returns `test-command.md` for code stages; `jobs.json:84` “implement whatever makes this command exit 0: {scope}”.
- assumption: the command is `unittest discover`, not a package import — measured: `python3 -m unittest ops.devlane.task.tests.test_jobs` raised `No module named 'support'`; `ladder-lever.md:50-53` is discover `-s` `-p`.
- assumption: `python3` and unittest are present — measured: Python 3.12.3 this session; `.github/workflows/ci.yml:54-55` runs `python3 --version` on `self-hosted`.
- assumption: finding 2's test may use `tempfile` — measured: `tempfile.TemporaryDirectory()` created `/tmp/tmppaao66vz` this session; Codex may write `/tmp` (`launch.py:419`).
- assumption: the self-hosted runner workspace for CI is a checkout on `runs-on: self-hosted` — measured: `.github/workflows/ci.yml:25-29`. The implement worker is not that job. Its workspace is the dispatch snapshot under the jobs root `${XDG_STATE_HOME:-$HOME/.local/state}/agentscient/dispatch/<id>/snapshot` — measured: `CONTRACT.md:77-79,113-128`. The ladder driver itself runs in the branch worktree (`WORKTREE_ROOT='../wt'`, `ops/lane.conf:13`); the worker does not.
- assumption: the named command does not need the network or Composer — measured: local unittest only; Symfony vendor install is out of scope (input).
- assumption: editing `jobs.json` makes the run red — measured: `OTHER_JOBS_SHA256` / `OTHER_JOB_WIRES` freeze every job except check-tests. That is a refusal the tests will hit, not a way to go green.
- assumption: `write_path.py` is missing until this run — measured: absent at this ref. A local regex left in the test files would green finding 3 without an implement file and would be the bypass remaining; tests-stage must not leave one.
- assumption: implement must not edit the test files — measured: `jobs.json:86-87`. Finding 3's detector therefore cannot stay only in those files.
- assumption: command length fits `SCOPE_CAP` — measured: 235 bytes; cap 1024.
- assumption: the live check-tests prompt is not itself a write path — measured: it contains the stdout / empty-artifacts clause and no create-path instruction; existing live-prompt tests are green at this ref.

## Out of scope

- A second fix round on the first ladder (D-LADDER-1).
- Installing a vendor tree, copying ignored files, or a `toolchain` refusal (input: the Symfony rule does not apply).
- Changing `jobs.json` prompts or adding `{inputs}` to plan.
- Coupling `verdict` to findings emptiness in `envelope.py` or `launch._schema_valid` (general envelope; the check-tests driver is the named gate).
- Probe allowlists (`docs/probes.md`) — not these five findings.
- Dispatch objects under `/tmp` — not these five findings. Finding 2 is the ladder payload symlink, pinned as “host file unchanged”, not as a `/tmp` index copy.

## Machine lines

slice	check-tests-json-reaudit	S
bucket	reaudit-findings	S	ops/conductor/tools/ladder.py ops/devlane/task/write_path.py ops/devlane/task/CONTRACT.md
