# Plan: fixture batch, second slice

Tree this plan is for: `f8f16e28a3d61bab2a90c955919d0a6ffb824fa7` (detached `HEAD` of this snapshot). Parent of that commit is `c4a70106179c8bee35b7f100efc86324d2df917f` (`lane/fixture-fix`). The only path that differs between those two commits is the security re-audit record `.dev/records/dispatches/20260904T125539Z-review-codex-113849.json`. The seven findings were taken against `c4a7010`; every reproduce in the input that reads the tree still holds at `f8f16e28` (measured, this write).

Unit: `lane/fixture-fix-2`. Output: this plan only. No code, no tests in this dispatch.

## Scope, in the owner's words

The fixture batch (four fixture apps, `ops/bin/fixture.sh`, the findings lever) had its one fix round (two implement runs) and its security re-audit returned changes again. By D-LADDER-1 the batch gets no second fix round; the unresolved findings are this slice's scope and it runs the whole ladder: tests (Grok) → skeptic → implement (Codex) per S bucket → audits once → one fix round → security re-audit → draft PR.

D-LADDER-1 (register, standing ratified, `ops/conductor/decisions.seed.json`, decided_by owner 2026-09-04): an implement run covers at most one S bucket and an M slice is implemented in two runs the plan names; the security and adversarial audits run once per batch on the merged tree, never per slice, with one fix round and the security re-audit only; the skeptic runs once on the first tests and never on the fixed tests.

Bucket sizes (owner, 2026-09-04): S = 1–3 files, one implement run under 10 minutes; M = two named S buckets (run A, run B), each landed and green alone; L = split.

## What this slice is not

- Not a second fix round on `lane/fixture-fix`. New lineage, new tests, new implement runs.
- Not the toolchain batch. Installing Symfony `vendor/` from the host composer cache is a separate, already-planned slice. This slice refuses when the trial has no vendor. It does not copy ignored files and it does not install.
- Not a rewrite of `docs/probes.md`. That file is the law for the probe boundary. This slice makes `fixture.sh` keep it.
- Not python-tooling's check line (still `&& ruff check .` at this ref). Finding 5 names python-service only.
- Not `suites.sh` and not the whole suite as an implement command.

## Findings, verbatim

Source: input file, record `20260904T125539Z-review-codex-113849`, tree `c4a7010` (`lane/fixture-fix`). Verdict: changes. Counts: `{"p1": 4, "p2": 2, "p3": 1, "opinions": 0}`.

### 1. p1

```json
{
 "severity": "p1",
 "where": "docs/probes.md:23-24 \u2194 ops/bin/fixture.sh:294-307 \u2194 ops/bin/fixture.sh:370-373",
 "claim": "NOT FIXED. Declared: \u201cRow commands are restricted to an allowlisted read set\u201d and \u201cread-only is enforced.\u201d Practiced: probe retains HOME and passes each manifest `probe` string to `/bin/sh` with `shell=True`. The fix removed most ambient environment keys, but an ordinary trusted fixture probe can still read credential files under HOME or write outside the fixture, so the declared security boundary is still absent.",
 "reproduce": "python3 -c 'from pathlib import Path; s=Path(\"ops/bin/fixture.sh\").read_text(); b=s[s.index(\"def probe(\"):s.index(\"def prove(\")]; p=s[s.index(\"def prove(\"):s.index(\"def spans(\")]; assert \"for key in (\\\"PATH\\\", \\\"HOME\\\")\" in b and \"shell=True\" in b and \"probe(fault[\\\"probe\\\"], directory, timeout)\" in p'"
}
```

Re-ran at `f8f16e28`: all three asserts hold.

### 2. p1

```json
{
 "severity": "p1",
 "where": "ops/devlane/task/envelope.py:14-18 \u2194 ops/bin/fixture.sh:443-475 \u2194 .dev/records/dispatches/20260904T122257Z-code-codex-c7f52a.json:382",
 "claim": "REGRESSED. Declared: parsed envelopes are revalidated and counts must match the exact finding shape. Practiced: the second implement run explicitly treats any envelope whose only key is `findings` as `legacy_fixture`, skips `envelope.validate()` and the status check, and also never calls the available dispatch-record validator or checks the outer record status. The run record calls this an intentional compatibility assumption. A fabricated findings-only or outer-tripped record can therefore still overwrite calibration rows.",
 "reproduce": "git diff 1b820912c0cb22daa223e6135991ebf232f51b5d 7abf3f152054c3cbea14d9b1243128595bd66c71 -- ops/bin/fixture.sh | rg 'legacy_fixture|not legacy_fixture' && python3 -c 'from pathlib import Path; s=Path(\"ops/bin/fixture.sh\").read_text(); r=s[s.index(\"def review_envelope(\"):s.index(\"def grade(\")]; g=s[s.index(\"def grade(\"):s.index(\"if not ARGS:\")]; assert \"set(envelope) == {\\\"findings\\\"}\" in r and \"not legacy_fixture\" in r and \"record.validate\" not in g and \"payload.get(\\\"status\\\")\" not in g'"
}
```

Re-ran the Python half at `f8f16e28`: all four asserts hold. The named record's envelope note still says the findings-only envelopes were treated as an intentional compatibility assumption.

### 3. p1

```json
{
 "severity": "p1",
 "where": "../in/input-fixture-reaudit.md:6 \u2194 ops/devlane/fixtures/apps/symfony-app/.gitignore:1 \u2194 ops/bin/fixture.sh:351-365 \u2194 ops/devlane/fixtures/apps/symfony-app/probes/sa01.sh:2",
 "claim": "NEW. Declared: the fixture comes from the tracked tree \u201cso an untracked or ignored file never rides.\u201d Practiced: fixed proof now detects an ignored `vendor/bin/phpunit`, copies the entire ignored vendor tree into the trial, and the shipped probes execute that copied binary. A stale or replaced untracked vendor executable can control calibration results with the lane user's authority.",
 "reproduce": "python3 -c 'from pathlib import Path; s=Path(\"ops/bin/fixture.sh\").read_text(); p=s[s.index(\"def prove(\"):s.index(\"def spans(\")]; i=Path(\"ops/devlane/fixtures/apps/symfony-app/.gitignore\").read_text(); q=Path(\"ops/devlane/fixtures/apps/symfony-app/probes/sa01.sh\").read_text(); assert \"/vendor/\" in i and \"shutil.copytree(vendor, trial / \\\"vendor\\\", symlinks=True)\" in p and \"exec vendor/bin/phpunit\" in q'"
}
```

Re-ran at `f8f16e28`: all three asserts hold.

### 4. p1

```json
{
 "severity": "p1",
 "where": "ops/devlane/dispatch/CONTRACT.md:38-41 \u2194 ops/devlane/dispatch/CONTRACT.md:111-130 \u2194 .dev/records/dispatches/20260904T120858Z-code-codex-075cb1.json:309-343",
 "claim": "NEW. Declared: \u201cthe job directory is where one dispatch's snapshot and artifacts live.\u201d Practiced: the first implement run copied the repository index and wrote Git objects to fixed names under global `/tmp`; those paths remain after closure, outside the job, with modes 0644 and 0755. This both escapes the recorded job boundary and leaves world-readable private-tree residue at predictable names.",
 "reproduce": "python3 -c 'from pathlib import Path; from stat import S_IMODE; r=Path(\".dev/records/dispatches/20260904T120858Z-code-codex-075cb1.json\").read_text(); i=Path(\"/tmp/agentscient-d037e5f.index\"); o=Path(\"/tmp/agentscient-d037e5f-objects\"); assert \"cp .git/index /tmp/agentscient-d037e5f.index\" in r and \"mkdir -p /tmp/agentscient-d037e5f-objects\" in r and i.is_file() and o.is_dir() and S_IMODE(i.stat().st_mode)==0o644 and S_IMODE(o.stat().st_mode)==0o755'"
}
```

Looked in the snapshot: the record contains those two commands (lines 313 and 331 of the record file). Did not look at live `/tmp` (outside this snapshot); the file/dir half of the reproduce is therefore not re-checked here. `ops/devlane/dispatch/launch.py` has no `TMPDIR` assignment (measured). Codex write argv sets `sandbox_workspace_write.writable_roots` to `out/` only; the comment at `launch.py:419` still says nothing else outside cwd and `/tmp` is writable.

Replacement location this plan names: `<job>/scratch/git/index` and `<job>/scratch/git/objects`. Child `TMPDIR`/`TMP`/`TEMP` = `<job>/tmp`. Both directories are created by the launcher and listed in `CONTRACT.md` §The job directory. They are added to Codex `writable_roots` together with `out/`. `/tmp` is not a named writable root.

### 5. p2

```json
{
 "severity": "p2",
 "where": "ops/devlane/fixtures/apps/python-service/README.md:5-11 \u2194 ops/devlane/fixtures/apps/python-service/requirements.lock:14-15 \u2194 ops/devlane/fixtures/apps/python-service/FAULTS.json:3-6",
 "claim": "NOT FIXED. Declared: install and run a \u201cpinned toolchain.\u201d Practiced: the lock now hashes and pins Ruff, but the sole green check still invokes bare `ruff` from PATH instead of `.venv/bin/ruff`. The bytes installed into the fixture are therefore not necessarily the executable that decides the check.",
 "reproduce": "python3 -c 'import json; from pathlib import Path; d=json.loads(Path(\"ops/devlane/fixtures/apps/python-service/FAULTS.json\").read_text()); lock=Path(\"ops/devlane/fixtures/apps/python-service/requirements.lock\").read_text(); assert \"--require-hashes\" in d[\"toolchain\"][\"install\"] and \"ruff==0.16.5\" in lock and \"&& ruff check .\" in d[\"check\"] and \".venv/bin/ruff\" not in d[\"check\"]'"
}
```

Re-ran at `f8f16e28`: all four asserts hold. README.md:11 is the same bare `ruff check .`. Host `ruff` is on PATH at `/home/scientdb/.local/bin/ruff` (measured this job). The app tree has no `.venv/bin/ruff` (ignored, not in the snapshot).

### 6. p2

```json
{
 "severity": "p2",
 "where": "ops/devlane/fixtures/apps/rust-crate/FAULTS.json:5-7 \u2194 ops/devlane/fixtures/apps/rust-crate/FAULTS.json:38-41 \u2194 ops/devlane/fixtures/tests/test_rust_crate_app.py:1758-1764",
 "claim": "NEW. Declared/practiced as a toolchain readiness and per-probe needs check, the new command is `cargo metadata --offline` without `--locked`. Cargo's own help distinguishes `--offline` from `--locked` (\u201cAssert that Cargo.lock will remain unchanged\u201d); on a stale manifest/lock, this nominal read may rewrite Cargo.lock and resolve a different cached graph before calibration.",
 "reproduce": "python3 -c 'import json; from pathlib import Path; d=json.loads(Path(\"ops/devlane/fixtures/apps/rust-crate/FAULTS.json\").read_text()); cmds=[d[\"toolchain\"][\"ready\"],*[n for f in d[\"faults\"] for n in f.get(\"needs\", [])]]; assert cmds and all(\"cargo metadata --offline\" in c and \"--locked\" not in c for c in cmds)' && cargo metadata --help | rg -- '--locked +Assert that `Cargo.lock` will remain unchanged'"
}
```

Re-ran the Python half at `f8f16e28`: seven commands, all `cargo metadata --offline --format-version 1 >/dev/null`, none carry `--locked`. `EXPECTED_READY` in `test_rust_crate_app.py:211` is that same string. The cargo-help half was not confirmed in this environment (`cargo metadata --help` piped to `rg` returned no lines here); the tests for this finding pin the manifest flags, not cargo's help text.

### 7. p3

```json
{
 "severity": "p3",
 "where": "../in/input-fixture-reaudit.md:12 \u2194 ops/bin/fixture.sh:269-291",
 "claim": "NEW. Declared: nothing outside the copy list enters fixed proof. Practiced: a manifest fix path is checked only lexically, then `Path.is_file()` and `git apply` follow it without resolving and proving containment. A hostile tracked `fixes/*.patch` symlink can therefore make fixed proof read an external file; under the ruled private-branch trust model this requires a hostile branch and is P3.",
 "reproduce": "python3 -c 'from pathlib import Path; s=Path(\"ops/bin/fixture.sh\").read_text(); b=s[s.index(\"def patch_fixture(\"):s.index(\"def probe(\")]; assert \"safe_relative(rel)\" in b and \"patch = directory / rel\" in b and \"patch.is_file()\" in b and \"[\\\"git\\\", \\\"apply\\\"\" in b and \"patch.resolve()\" not in b and \"relative_to(directory)\" not in b'"
}
```

Re-ran at `f8f16e28`: all six asserts hold. `inside()` already exists in `fixture.sh` and is not used on the patch path.

## Value order

1. `dispatch-job-scratch` (finding 4, P1). Lands first so later Codex implement runs on this lineage inherit a job-scoped `TMPDIR` and scratch. Blast radius is every write dispatch.
2. `probe-allowlist-and-patch` (findings 1 and 7, P1 then P3). Every calibration probe currently runs under `shell=True` with `HOME`.
3. `envelope-and-vendor` (findings 2 and 3, both P1). Calibration rows must not accept a fabricated envelope; ignored `vendor/` must not ride.
4. `python-service-ruff` (finding 5, P2).
5. `rust-crate-locked` (finding 6, P2).

## Which slice deserves its own PR

`dispatch-job-scratch` deserves its own PR. It is the dispatch app (`ops/devlane/dispatch/`), not the fixture lever. Its test directory is `ops/devlane/dispatch/tests/`. Its blast radius is every write dispatch, not fixture calibration. Mixing it with fixture-lever changes makes the review frontier the union of two apps.

The other four S buckets are one fixture PR on `lane/fixture-fix-2`: one M (`fixture-lever-reaudit`) then one M (`fixture-manifest-pins`), landed in that order, one ladder, audits once on the merged fixture tree.

Two PRs, two ladders, two audit pairs. D-LADDER-1's "audit once per batch" is once per PR, not once for both apps.

## Edges, from `docs/verified-couplings.md`

The six obligations of every edge: closure both ways, shape, behavior, freshness, permission, blast radius. Per bucket:

| bucket | edge | contract | gate (behavior) | blast |
|---|---|---|---|---|
| dispatch-job-scratch | launcher child → job directory | `CONTRACT.md` §The job directory, §The child's environment, §Isolation | tests below: `TMPDIR` under the job; writable roots are job paths; tempfile lands under `tmp/` | every write dispatch |
| probe-allowlist-and-patch | `docs/probes.md` ↔ `fixture.sh` `probe()` / `patch_fixture()` | allowlisted read set; identity stripped; read-only enforced; fix paths contained | tests below: allowlist as data; off-list probe refuses; no `HOME`; no shell; symlink patch refuses | every `prove` |
| envelope-and-vendor | `envelope.py` `validate` and `record.py` `validate` ↔ `fixture.sh` `grade`; tracked tree ↔ `prove --fixed` | parsed envelopes revalidated; ignored files never ride | tests below: findings-only refuses; outer non-closed refuses; `record.validate` failure refuses; no vendor copytree; missing vendor while a probe needs it refuses `toolchain` | calibration rows; Symfony `--fixed` |
| python-service-ruff | `FAULTS.json` `check` ↔ `requirements.lock` ruff pin | pinned toolchain is the executable that decides the check | tests below: check names `.venv/bin/ruff`; bare `ruff` token absent | python-service calibration only |
| rust-crate-locked | `FAULTS.json` `ready`/`needs` ↔ `Cargo.lock` | `--offline` does not rewrite the lock | tests below: every ready/needs metadata command carries `--locked` | rust-crate calibration only |

Freshness: each edge is true of `f8f16e28` until the landing commit of its bucket; the next bucket re-verifies only its own frontier.

## Tests stage (once, before any implement)

Job `author-tests`, harness Grok, prompt as `ops/devlane/task/jobs.json` `author-tests` at this ref. Snapshot mode `whole`. Constraints: do not edit the implementation; no network. The prompt says prove each test red for its own assertion and commit each test file as soon as its red is proven.

The tests author writes from this plan and from `docs/probes.md`, `ops/devlane/dispatch/CONTRACT.md`, `ops/devlane/task/envelope.py`'s contract comments, and `docs/wire.md`. They do not open `ops/bin/fixture.sh` or `ops/devlane/dispatch/launch.py`.

Ladder custody cannot withhold those files: `ops/conductor/ladder-lever.md` lines 136–139 declare whole-tree snapshots as residue. The firewall is policy (`Do not read the implementation`), not OS.

Existing tests that currently pin the broken practice must be turned to pin the contract, in the same files, so they are red at this ref:

- `test_fixture_lever.py` `test_prove_scrubs_ambient_secrets_from_the_probe_environment` currently asserts `HOME=` plus the scratch home. After this slice it asserts `HOME` is absent from the probe environment, still asserts host secrets and `CARGO_HOME` are absent, still asserts `PATH` is present.
- `test_python_service_app.py` `CHECK_CMD` is `.venv/bin/python -m pytest -q tests && ruff check .`. After this slice it is `.venv/bin/python -m pytest -q tests && .venv/bin/ruff check .`. `test_check_command_names_pytest_and_ruff` and `test_app_check_green_when_ready_else_skip` compare against that constant. `test_ruff_check_green_on_a_fresh_make` currently calls `shutil.which("ruff")` (host PATH). After this slice it must not: either drop it, or run the venv binary after install. Leaving `which("ruff")` in place would keep blessing finding 5.
- `test_rust_crate_app.py` `EXPECTED_READY` is `cargo metadata --offline --format-version 1 >/dev/null`. After this slice it is `cargo metadata --offline --locked --format-version 1 >/dev/null`. The same string is used for every `needs` entry that is a metadata command.
- `test_fixture_grade.py` plants incomplete dispatch records. Finding 2 requires `record.validate`. The tests author adds a complete-record helper so existing classification tests keep extra fields the current lever ignores (those tests stay green at this ref) and adds new tests that are red: findings-only envelope refused; outer `status` not `closed` refused; a record that fails `record.validate` refused. Do not leave the synthetic records unable to pass `record.validate` once the lever starts calling it — the implementer cannot edit tests.
- `test_symfony_app_app.py` `prove --fixed` cases that today go green by copying ignored vendor become refusals of class `toolchain`. The tests author changes those assertions before implement. New refusal tests may live in `test_fixture_lever.py` (synthetic app whose probe/needs names `vendor/`); the Symfony file still has to stop expecting green `--fixed` without a vendor.

`test_fixture_lever.py` staging today copies only `fixture.sh`. After bucket `probe-allowlist-and-patch` the lever reads `ops/devlane/fixtures/probe-allowlist.json` from the scratch repo root. The tests author plants that file next to the copied lever, bytes matching the allowlist this plan declares. At this ref the lever ignores the extra file (green). After implement it is required.

Never stub a dependency to get green. The existing `CALIBRATE_STUB` in `test_fixture_grade.py` is pre-existing apparatus that captures `findings.py calibrate` stdin; it is not a validation bypass and this slice does not extend it. Finding 2's `legacy_fixture` path is the bypass that is removed; a test must pin it is gone.

### Tests-stage first-run walkthrough

- assumption: the worker's HOME is the job grok home, not the operator home — measured: this plan job has `HOME` and `GROK_HOME` equal to `…/dispatch/20260904T130753Z-plan-grok-d7fac2/home/grok`; `auth.json` there is a symlink; `CONTRACT.md` isolation table says grok sets both.
- assumption: Grok can write `.git` and commit — measured: this plan job's `.git/index` is a regular writable file; `jobs.json` author-tests is a write role; grok sandbox is `always-approve` with containment `policy`. Codex's read-only `.git` is not this run.
- assumption: no network — measured: `jobs.json` author-tests constraints include `no network`; grok argv carries `--disable-web-search` (`launch.py:_grok_permission`). A test that `pip install`s or `cargo fetch`es hits skip/`UNREACHABLE` paths already in the app tests, or a failed command, not a silent network use the brief allows.
- assumption: the job prompt is the `author-tests` template at this ref — measured: `ops/devlane/task/jobs.json` `author-tests.prompt` (write tests from the contract, do not read the implementation, prove red, commit each file). `{scope}` is this plan.
- assumption: the self-hosted runner workspace is the snapshot cwd — measured for this dispatch: cwd is the snapshot root, `git remote` is empty, `DISPATCH_JOB=20260904T130753Z-plan-grok-d7fac2`, `WF_LANE=dev`. Could not look at a live `agentscient-wsl` runner (not in the snapshot). `ci.yml` says `runs-on: self-hosted` and checks out the repo; `lane.conf` has `WORKTREE_ROOT='../wt'`. A test that hard-codes `/home/runner/work/` or a host `/tmp/agentscient-*` path is wrong.
- assumption: `TMPDIR` is unset, so `tempfile` in tests lands under host `/tmp` — measured: `TMPDIR` is unset in this job. That is finding 4's world; the tests stage does not fix it. Tests must not require a job-scoped `TMPDIR`.

## Slice `dispatch-job-scratch` (S) — own PR

Finding 4. Implement files (2): `ops/devlane/dispatch/launch.py`, `ops/devlane/dispatch/CONTRACT.md`.

### Behavior

Launcher, before spawn of every harness child:

1. Creates `<job>/tmp/` and `<job>/scratch/` (and `<job>/scratch/git/` so the named index/object paths have a parent).
2. Sets child `TMPDIR`, `TMP`, and `TEMP` to `<job>/tmp`.
3. For Codex `workspace-write`, `sandbox_workspace_write.writable_roots` is the JSON list of `out/`, `tmp/`, and `scratch/`, each the absolute job path. `/tmp` is not in that list. The comment that currently says nothing else outside cwd and `/tmp` is writable is updated to name the job directory.

`CONTRACT.md` §The job directory listing gains:

```text
tmp/           child TMPDIR; mktemp and tempfile land here
scratch/       worker git index and objects when .git is read-only; not a deliverable
```

Named destinations: `<job>/scratch/git/index` and `<job>/scratch/git/objects`. Workers that still need a writable index (Codex `.git` is read-only) use those paths, or write `out/COMMIT_MSG` as `jobs.json` implement already says. They do not write under `/tmp`.

The launcher still commits residual for Codex (`_commit_for_harness`). That path stays. This bucket does not teach the worker to copy the index; it makes the only writable places the job directory.

### Tests, and why they are red at this ref

File: `ops/devlane/dispatch/tests/test_launch_isolation.py` (extend; 22 tests, 664 lines today).

1. A Codex write launch (`job=implement`, `stage=code`) has child env `TMPDIR`, `TMP`, `TEMP` equal to `job_dir/tmp`. Red: `_child_env` does not set them (`TMPDIR` does not occur in `launch.py`).
2. That job directory has `tmp/` and `scratch/` as directories before spawn. Red: launcher does not create them; `CONTRACT.md` listing does not name them.
3. Codex write argv `writable_roots` JSON list is exactly those two plus `out/`, all under the job directory, and does not contain `/tmp`. Red: argv is `writable_roots=["<out>"]` only (`launch.py:422`).
4. `tempfile.TemporaryDirectory` (or `mktemp -d`) under a copy of that child env creates a path whose `resolve()` is `relative_to(job_dir/tmp)`. Red: with `TMPDIR` unset, tempfile lands under host `/tmp`.

Do not scan the host `/tmp` for leftover `agentscient-*` names. That is not hermetic and is outside the snapshot.

Implement command (those test files, never `suites.sh`):

```text
python3 -m unittest discover -s ops/devlane/dispatch/tests -p 'test_launch_isolation.py'
```

### Calibration (declared)

files 2; tests 1 file / 4 new tests / ~80 lines; minutes 8 (assumed; this file was not timed at this ref).

### First-run walkthrough

- assumption: Codex HOME is `CODEX_HOME=<job>/home/codex` with `auth.json` only, and process `HOME` is not that directory — measured: `isolation.py` HARNESSES `codex` sets `home_env` `CODEX_HOME` only; `test_launch_isolation.py` asserts `HOME != CODEX_HOME`.
- assumption: no network — measured: `jobs.json` implement constraints include `no network`; Codex argv is `--sandbox workspace-write` with no `network_access` flag in `launch.py`. If a future Codex default grants network, the constraint is policy only — refusal: the brief still says no network; this bucket does not need the network.
- assumption: Codex `.git` is read-only, so `git commit` in the snapshot fails — measured: `launch.py:1113` `_commit_for_harness` docstring; record `20260904T120858Z-code-codex-075cb1` commands 25–34 (`Unable` path via copied index); record `20260904T122257Z-code-codex-c7f52a` note: sandbox made `.git/index.lock` read-only, fallback `out/COMMIT_MSG`.
- assumption: the only extra writable root today is `out/`, so a worker who cannot write `.git` writes `/tmp` or `out/` — measured: `launch.py:419-422`; the named record wrote `/tmp/agentscient-d037e5f.index` and `/tmp/agentscient-d037e5f-objects`. Refusal this run will hit if it writes `<job>/scratch/` before the code change: that path is not in `writable_roots` yet. Use `out/COMMIT_MSG` (already writable) for this run's own commit message. Do not copy the index to `/tmp`.
- assumption: the job prompt is `jobs.json` implement at this ref — measured: implement whatever makes `{scope}` (the command above) exit 0; do not edit the files the tests live in; no network; if the sandbox refuses `git commit`, status stays ok and the message goes to `out/COMMIT_MSG`.
- assumption: the self-hosted runner workspace is the snapshot — measured as in the tests-stage walkthrough. `DISPATCH_JOB` is in the child env (`_child_env`). Job directory is `snapshot.parent`.

## Slice `fixture-lever-reaudit` (M) — fixture PR, run A then run B

### Bucket `probe-allowlist-and-patch` (S) — findings 1 and 7

Implement files (2): `ops/bin/fixture.sh`, `ops/devlane/fixtures/probe-allowlist.json` (new).

#### Allowlist, as data

New file `ops/devlane/fixtures/probe-allowlist.json`, sibling of `copy-list`, not an entry on `copy-list` (it is lever data, not a file to copy into a made fixture).

```json
{
  "forms": [
    {
      "id": "python-probe-script",
      "env": { "PYTHONPATH": "." },
      "argv": ["python3", "probes/*.py"]
    },
    {
      "id": "sh-probe-script",
      "env": {},
      "argv": ["sh", "probes/*.sh"]
    }
  ]
}
```

Those two forms are the only probe strings in the four apps at this ref (measured: python-service and python-tooling are `PYTHONPATH=. python3 probes/<id>.py`; rust-crate and symfony-app are `sh probes/<id>.sh`). This bucket does not rewrite `FAULTS.json` probe strings.

`probe()` loads that file as data from `ROOT/ops/devlane/fixtures/probe-allowlist.json`. Missing or malformed file: refuse class `probe`, expected the allowlist file, found absent/invalid, needed restore it.

A manifest `probe` string is parsed as optional `KEY=VALUE` assignments plus argv, without `shell=True`. It matches a form when:

- every env key is in that form's `env` and the value equals the form's value (`PYTHONPATH` is `.` only);
- argv[0] equals the form's interpreter;
- argv[1] matches `probes/<file>.py` or `probes/<file>.sh` with no extra tokens (`-c`, extra flags, extra words);
- argv[1] resolved (`Path.resolve()`) is a regular file inside `directory/probes/` (`inside()` / `relative_to`). A symlink that escapes refuses.

A string that does not match: refuse class `probe`, expected an allowlisted read form, found the string, needed repair the manifest probe. Adding a form is out of this slice.

Environment actually passed to the process: `PATH` (from the parent, so `python3` and `sh` resolve), `LC_ALL=C`, `LANG=C`, `TZ=UTC`, plus the form's env. Not `HOME`. Not `WF_AGENT`. Not host secrets. `subprocess.Popen(argv, shell=False, cwd=directory, env=that)`.

Read-only is enforced at the string: without a shell, `cmd > /tmp/x` is not a redirect, and an argv path outside `probes/` refuses. Tracked probe scripts may still write inside the fixture cwd (the existing SYN-01 `printenv` dump is inside `probes/`). That is inside the fixture, not outside it.

`docs/probes.md` is not edited.

#### Patch containment (finding 7)

After `safe_relative` succeeds and `directory/rel` is a file, resolve it and prove `inside(resolved, directory.resolve())`. If not, refuse class `fix`, expected a patch contained in the fixture directory, found the resolved path, needed a real file under the fixture, not a symlink out. Then `git apply` the resolved path. `inside()` already exists in `fixture.sh`.

#### Tests, and why they are red at this ref

File: `ops/devlane/fixtures/tests/test_fixture_lever.py` (40 tests, 1341 lines today).

1. `test_the_allowlist_file_is_present_and_readable` — the file exists at the path above and parses as the two forms. Red: file is absent (measured).
2. Flip of `test_prove_scrubs_ambient_secrets_from_the_probe_environment`: `HOME` is not in the probe `printenv` dump; host secrets still absent; `PATH` still present. Red: current lever passes `HOME`.
3. A planted probe `true; echo PWNED > ../outside.txt` (or `python3 -c 'open("/tmp/x","w")'`) refuses class `probe` and does not create the outside file. Red: `shell=True` runs it.
4. A planted probe `sh probes/syn-01.sh` still colours. Stays green if the tests author plants the allowlist in the scratch repo; the new assertion is that an off-list string refuses.
5. A planted `probes/escape.sh` symlink whose target is outside the fixture, used as the probe path, refuses class `probe`. Red: no resolve check.
6. A planted `fixes/syn-01.patch` symlink whose target is an outside file: `prove --fixed` refuses class `fix` and does not apply the outside bytes. Red: `patch.resolve()` is absent; `is_file()` follows the symlink and `git apply` reads it.

Staging helper plants the allowlist file beside the copied lever.

Implement command:

```text
python3 -m unittest discover -s ops/devlane/fixtures/tests -p 'test_fixture_lever.py'
```

Do not put the four app test modules on this command. The two allowlisted forms are the forms those modules already ship; they stay green if the parser accepts them. If the tests author finds they must change an app module to keep a prove test honest, that file joins this command and the bucket is then L (split) — do not silently grow past 3 implement files.

#### Calibration (declared)

files 2; tests 1 file / 6 tests / ~150 lines; minutes 9 (assumed).

#### First-run walkthrough

- assumption: Codex isolated home is `CODEX_HOME` only — measured: as in `dispatch-job-scratch`.
- assumption: no network — measured: implement constraints. This bucket does not install anything.
- assumption: Codex `.git` is read-only — measured: as above. Write `out/COMMIT_MSG`. If `dispatch-job-scratch` has already landed on the lineage this run is dispatched from, `TMPDIR` is `<job>/tmp` and scratch is writable; if it has not, `/tmp` is still writable — do not use it. Refusal: none today for `/tmp` writes (that is the finding). The brief for this bucket forbids them.
- assumption: the job prompt is `jobs.json` implement with `{scope}` the command above — measured: that template at this ref.
- assumption: self-hosted workspace is the snapshot — measured: as above.
- assumption: the four apps' probe strings match the two forms without `FAULTS.json` edits — measured: all 28 `probe` values listed in the four `FAULTS.json` files are one of those two shapes.
- assumption: `test_fixture_lever.py` SYN-01 probe is `sh probes/syn-01.sh` — measured: `PROBE_01` / manifest `probe` in that file.

### Bucket `envelope-and-vendor` (S) — findings 2 and 3

Implement files (1): `ops/bin/fixture.sh`.

Depends on run A having landed (same file). Run B is green alone on top of A.

#### Envelope (finding 2)

Delete `legacy_fixture`. `review_envelope` always calls `envelope.validate` when `ops/devlane/task/envelope.py` is present. Envelope `status` must be `ok` or refuse class `record`. Outer `payload.get("status")` must be `closed` or refuse class `record` (a `tripped`/`died`/`launched` record does not write calibration rows). Import `ops/devlane/dispatch/record.py` the same way the lever already imports `envelope.py`, and call `record.validate(payload)`; `RecordError` becomes refuse class `record`, expected a valid dispatch record, found the error text, needed repair or replace the record.

No findings-only envelope is accepted. No "compatibility" branch. The note in record `20260904T122257Z-code-codex-c7f52a` is the thing being removed.

#### Vendor (finding 3)

Delete `shutil.copytree(vendor, trial / "vendor", symlinks=True)` and the `vendor/bin/phpunit` existence check that gated it. Do not copy ignored files. Do not run `composer` or any install.

After the preflight copy (which already ignores `vendor`), if any fault's `probe` string or `needs` list names `vendor/` and the trial has no `vendor/bin/phpunit`, refuse class `toolchain`, expected `vendor/bin/phpunit` in the trial, found absent, needed the toolchain batch to install from the composer cache. Apps whose probes do not name `vendor/` (synth, python-service, python-tooling, rust-crate) still `prove --fixed`.

Symfony `probes/sa01.sh` stays `exec vendor/bin/phpunit …`. This slice does not make that probe green.

#### Tests, and why they are red at this ref

Files:

- `ops/devlane/fixtures/tests/test_fixture_grade.py` (22 tests, 735 lines). New: findings-only envelope (`result.envelope` keys `{"findings"}` only) refuses class `record` and does not write calibrate rows. Red: `legacy_fixture` accepts it. New: outer `status` `tripped` (envelope itself `ok`) refuses class `record`. Red: `grade()` never reads `payload["status"]`. New: a payload that fails `record.validate` (for example missing `lineage`) refuses class `record`. Red: `record.validate` is not called. Existing `test_grade_refuses_a_tripped_envelope` covers envelope status `tripped` only, which already refuses for non-legacy envelopes; keep it. Complete-record helper: extra fields current `grade()` ignores, so existing classification tests stay green at this ref and stay green after `record.validate` is called.
- `ops/devlane/fixtures/tests/test_fixture_lever.py`. New: `prove --fixed` on a tree with an ignored `vendor/bin/phpunit` marker file does not copy that marker into any trial (the supplied directory is unchanged; a refusal happens before probes if a fault names `vendor/`). New: a synthetic fault whose probe or needs names `vendor/bin/phpunit`, with no vendor in the trial, refuses class `toolchain` on `--fixed`, expected–found–needed present, and does not install. Red: current lever copies vendor when `vendor/bin/phpunit` exists and otherwise runs probes.
- `ops/devlane/fixtures/tests/test_symfony_app_app.py` (34 tests, 2430 lines). Every `prove --fixed` that today expects GREEN on a tree without a tracked vendor expects class `toolchain` instead. Red: current lever copies ignored vendor and colours. Do not add a composer install to make them green.

Implement command:

```text
python3 -m unittest discover -s ops/devlane/fixtures/tests -p 'test_fixture_grade.py' && python3 -m unittest discover -s ops/devlane/fixtures/tests -p 'test_fixture_lever.py' && python3 -m unittest discover -s ops/devlane/fixtures/tests -p 'test_symfony_app_app.py'
```

`test_symfony_app_app.py` was not timed at this ref. Several cases skip without vendor/network. If this command exceeds 10 minutes, the bucket was oversized the same way fixture-apps slice 1 was (plan said S, measured 23 and 11 minutes). Keep the Symfony assertion changes small; do not add toolchain work.

#### Calibration (declared)

files 1; tests 3 files / ~8 new or flipped tests / ~200 lines; minutes 9 (assumed; Symfony module duration not measured).

#### First-run walkthrough

- assumption: Codex isolated home, no network, read-only `.git`, implement prompt, snapshot workspace — measured: as in the previous bucket.
- assumption: `envelope.py` and `record.py` are in the snapshot for the lever to import — measured: both files present at this ref (`envelope.py` 310 lines, `record.py` 111 lines). `fixture.sh` already imports `envelope` when the file exists.
- assumption: existing grade tests plant records that are not `record.validate`-valid — measured: `test_fixture_grade.py` `record_payload` supplies `id`, `job`, `harness`, `model`, `result.envelope` only. The tests author must widen that helper before this implement run, or every existing grade test goes red and the implementer cannot edit them. Refusal this run hits if they did not: `record: expected a valid dispatch record; found …`.
- assumption: Symfony `--fixed` tests will be red until this implement, and will not need `vendor/` in the snapshot — measured: `ops/devlane/fixtures/apps/symfony-app/.gitignore` lists `/vendor/`; vendor is absent from the snapshot; `test_prove_on_fresh_make_colours_needs_unreachable_and_sa07_red` already expects UNREACHABLE without vendor for unfixed prove.
- assumption: no composer install — measured: this bucket's files do not include a toolchain installer; `ci.yml` composer install is the app job on a runner, not this implement. Refusal if the implementer runs `composer`: jobs.json no network.

## Slice `fixture-manifest-pins` (M) — same fixture PR, after the lever

### Bucket `python-service-ruff` (S) — finding 5

Implement files (2): `ops/devlane/fixtures/apps/python-service/FAULTS.json`, `ops/devlane/fixtures/apps/python-service/README.md`.

`check` becomes `.venv/bin/python -m pytest -q tests && .venv/bin/ruff check .` in both files. Lock already pins `ruff==0.16.5` with a hash. Install line already uses `--require-hashes`. Do not change the lock. Do not install in this implement.

#### Tests, and why they are red at this ref

File: `ops/devlane/fixtures/tests/test_python_service_app.py`.

- `CHECK_CMD` equals the new string; `test_check_command_names_pytest_and_ruff` and `test_app_check_green_when_ready_else_skip` compare `FAULTS.json` `check` to `CHECK_CMD`. Red: live `check` is still `&& ruff check .`.
- README contains that same check line. Red: README:11 is still bare `ruff`.
- `test_ruff_check_green_on_a_fresh_make` no longer uses `shutil.which("ruff")`. If rewritten to require `.venv/bin/ruff` after install, it is red until FAULTS.json changes only if it also reads `check`; if it still calls host ruff it stays green and fails the finding. The tests author must not leave a PATH ruff call as the green check.

Implement command:

```text
python3 -m unittest discover -s ops/devlane/fixtures/tests -p 'test_python_service_app.py'
```

#### Calibration (declared)

files 2; tests 1 file / 3 flipped tests / ~30 lines; minutes 6 (assumed).

#### First-run walkthrough

- assumption: Codex isolated home, no network, read-only `.git`, implement prompt, snapshot workspace — measured: as above.
- assumption: this command's red is the string assertions, not a venv install — measured: `test_check_command_names_pytest_and_ruff` is a JSON/README read; `test_app_check_green_when_ready_else_skip` skipTests when `toolchain.install` fails. Install is `pip install --require-hashes` and needs network or a cache. No network: skip path, not a hang, if the tests author leaves that skip in place.
- assumption: host `ruff` is on PATH and would still make a PATH-based check green — measured: `/home/scientdb/.local/bin/ruff` exists in this job. That is why the assertion must name `.venv/bin/ruff`.
- assumption: `.venv/bin/ruff` is not in the tree — measured: absent in the snapshot; `.gitignore` lists `.venv/`.

### Bucket `rust-crate-locked` (S) — finding 6

Implement files (1): `ops/devlane/fixtures/apps/rust-crate/FAULTS.json`.

`toolchain.ready` and every fault `needs` entry that is `cargo metadata --offline --format-version 1 >/dev/null` become `cargo metadata --offline --locked --format-version 1 >/dev/null`. RC-07 has no `needs` and stays that way. `check` already has `cargo test --offline --locked`. Do not run `cargo fetch`.

#### Tests, and why they are red at this ref

File: `ops/devlane/fixtures/tests/test_rust_crate_app.py`.

- `EXPECTED_READY` is the new string; `test_toolchain_install_and_ready_are_the_contracted_commands` and `manifest_toolchain` compare to it. Red: live ready is the old string.
- Every `needs` metadata command equals that string. Red: six `needs` lists lack `--locked`.

Do not scrape `cargo metadata --help` in the tests. Pin the manifest.

Implement command:

```text
python3 -m unittest discover -s ops/devlane/fixtures/tests -p 'test_rust_crate_app.py'
```

#### Calibration (declared)

files 1; tests 1 file / 2 flipped tests / ~20 lines; minutes 5 (assumed).

#### First-run walkthrough

- assumption: Codex isolated home, no network, read-only `.git`, implement prompt, snapshot workspace — measured: as above.
- assumption: this command's red is the string assertions — measured: `test_toolchain_install_and_ready_are_the_contracted_commands` reads JSON. Runtime `cargo metadata` paths already treat a non-zero as `UNREACHABLE` / skip. `--locked --offline` with tracked `Cargo.lock` does not need network. Isolated `HOME` may not have a cargo cache; those runtime tests already have an UNREACHABLE path.
- assumption: `cargo` may be on the host PATH — measured this job: `/home/scientdb/.cargo/bin/cargo`. The implementer does not need it for a JSON edit.

## Ladder for each PR

Per D-LADDER-1 and `ops/conductor/ladder-lever.md`:

1. `author-tests` (Grok) once, this plan as scope, all test files for that PR.
2. `check-tests` (Codex) once on those tests. No second skeptic after a test fix.
3. `implement` (Codex) once per S bucket, command = the named test files, never `suites.sh`. Land and green before the next bucket.
4. After the last bucket: `security-audit` (Codex) and `adversarial-review` (Grok) once, back to back.
5. One fix round (`fix-tests` then `fix-code`) if either audit says `changes`.
6. `security-re`. If it still says `changes`, stop (ladder exit 1). No second fix round.
7. Draft PR.

PR A (`dispatch-job-scratch`) has one S bucket, so one implement. PR B has four S buckets (the two M slices).

Models: `lane.conf` at this ref has `MODEL_GROK='grok-4.6'`, `MODEL_CODEX='gpt-5.6-sol'`, `MODEL_CODEX_SECURITY_AUDIT='gpt-daybreak-blue-latest'`. The dispatcher resolves them; this plan does not name a model in a table as the thing that will run.

## Denied

- Copying ignored `vendor/` into a trial.
- `composer install`, `pip install`, `cargo fetch` as the fix for findings 3, 5, or 6.
- `legacy_fixture` or any other skip of `envelope.validate` / `record.validate`.
- Writing index or objects under `/tmp`.
- Stubbing a dependency so a test goes green.
- Editing `docs/probes.md` from this plan.
- python-tooling's bare `ruff check .` (not in the seven findings).
- A second fix round, a second skeptic on fixed tests, audits per bucket.

## Machine lines

slice	fixture-lever-reaudit	M
bucket	probe-allowlist-and-patch	S	ops/bin/fixture.sh ops/devlane/fixtures/probe-allowlist.json
bucket	envelope-and-vendor	S	ops/bin/fixture.sh
