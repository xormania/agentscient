# One dev-lane verification gate

Owner direction, 2026-09-23: consolidate CI into shared check definitions,
bounded execution and a verdict that cannot pass missing work. This replaces
the old workflow step-order and absent-suite behavior. It does not change the
application job or the release evidence attached to a push on dev.

`bash ops/bin/suites.sh` is the full local lane gate. Its adapter,
`lane.py`, declares the required checks and suite families once. The generic
check and discovery primitives live in `ops/testkit`; subprocess ownership,
timeouts and result data remain owned by `ops.testkit.run`.

- A check has a unique name, an argv, required paths and a finite positive
  timeout. Empty plans, duplicate names and missing inputs refuse before any
  check starts: exit 2, one expected/found/needed line on stderr, empty stdout.
- Every required suite directory must contain matching test files. Shard
  patterns must cover each discovered file exactly once. Each child discovers
  and runs real unittest cases; zero collected cases is a rejection, on every
  supported Python version. Import errors, failures and errors remain red.
- Each check executes once in the requested plan. The existing command runner
  supplies the same cwd, explicit environment, timeout cleanup and Result.
  Spawn failures and timeouts are unsuccessful results. A run is green only
  when all required results exist and exit zero. Completed checks print their
  names, output and durations immediately; parallel execution remains the
  default and `SUITES_SERIAL=1` uses the same plan serially.
- The full plan includes lint, the term wall, the test-kit ratchet, both
  configuration guards, every suite and the probe corpus. The real corpus runs
  once as a named check; the probe runner retains its synthetic behavioral
  tests. Missing TERM_WALL configuration remains a refusal by its owner.
- `--suite DIR` is an explicit partial check for portability fixtures and
  focused local work. It runs lint plus the named suite(s), rejects absent or
  empty selections and labels its output PARTIAL. It is never the CI command
  or evidence that the full lane is green.

The GitHub workflow prepares checkout and record refs, supplies TERM_WALL,
and invokes the CI adapter described below with the same lane plan.
Its lane and app jobs, triggers,
concurrency, timeouts and pinned checkout remain. The workflow uses JSON
syntax within its .yml file, a YAML subset read by the standard JSON parser;
the former test-only handwritten YAML parser is retired. The configuration
closure and PR-readiness readers consume that same format. PR readiness also
retains YAML reads for older refs. Contract tests inspect executable argv and
conditions, not step names, and prove that disabling the gate is detected.

The CI checks and kit are wall machinery and join the existing wall path
classification. This is an isolated wall change under the owner's instruction
to make this PR. One producer implements and verifies it; an independent
producer is absent, as permitted for owner-directed dev-lane work.

## Retired coverage and its replacement

| Previous owner | Retained invariant |
|---|---|
| `test_suites_ruff.py` | Shared execution failure/spawn cases and the adapter's lint-failure row |
| `test_suites_shards.py` | Generic discovery table: exact partition, gap, overlap, missing family and new matching file |
| YAML parser cases in `test_ci_two_jobs.py` | Standard JSON parsing; workflow contract and planted execution/filter faults |
| `TheTrackedCorpusRunsGreen` in `test_probes.py` | One mandatory full-plan corpus check, with a failing-corpus adapter case |
| Implicit omissions in portability fixtures | Explicit partial invocation, using the same runner and discovery primitive |

Reuse: testkit.world, testkit.run, testkit.fakes, testkit.refusal-wire.

## PR02: bounded work, isolated state, and reusable execution evidence

Owner direction, 2026-09-24: repair the eight-minute CI regression and avoid
repeating successful verification. Use GitHub-hosted runners until the included
3,000 minutes are exhausted, then switch to local capacity. The concern about
eight-minute hosted burns was not a request to abandon this plan. PR297's
self-hosted optimization was the first part of PR02, not its completion.

- Run inexpensive guards before suites. A failed guard ends the gate red
  without launching expensive work. Preflight still validates the whole plan.
- Discover conductor modules independently, including newly added modules,
  and schedule with a bounded worker pool. Keep all existing cases and their
  failure semantics. Record module durations; target the previous roughly
  three-minute native gate, and report actual timing before claiming success.
  The measured long dispatch and sessions-trial groups each use four disjoint
  partitions of sorted, actually discovered test cases. New cases join the
  partition automatically; import errors and empty partitions remain red.
  CI explicitly uses eight workers for these process-heavy suites, including
  on standard two-CPU hosted machines; the direct local gate retains its
  CPU-aware default. Receipts record the actual CPU count and worker limit.
- CI uses private HOME, XDG and temporary roots through the existing testkit.
  Resolve declared tools before isolation, require them explicitly, and keep
  runner/API credentials out of child test environments. Preserve world
  watches and owned-process cleanup. A shared Composer cache contains only
  dependency downloads; operator configuration and stores are not imported.
- A reusable result must come from an executed check in an artifact belonging
  to this repository's designated CI workflow and completed job attempt.
  Validate source revision, workflow identity, input digest and check plan.
  Only successful individual executions qualify. Missing, failed, cancelled,
  partial, malformed, wrong-context and reuse-only records cannot mint a pass.
- Record source and tested revisions separately. For deterministic suites,
  canonicalize only the checkout commit's publication metadata: retain its
  exact tree and ordered parents. A PR test merge and the eventual merge with
  the same tree/parents therefore test the same Git object. Bind consumed
  record refs, tool identities, check definitions and relevant configuration.
  History-sensitive live probes run against the actual event checkout.
- App inputs include the application tree plus CI definitions; independent
  dev-lane source edits do not invalidate an otherwise identical app pass.
  Lane inputs conservatively include the full tracked tree. Unknown inputs
  or unavailable prior evidence cause real verification, never a cached green.
- Each result says executed or reused and links its original run/job.
  A reused marker is not an original execution. Preserve both required job
  names and candidate associations across PR, push and retry events.
- The workflow publishes bounded JSON evidence and readable job summaries.
  No extra database, dispatcher, model call or operator-session prerequisite
  participates in the CI gate.

## Runner selection and same-candidate recovery

`CI_RUNNER_MODE` is one repository Actions configuration variable. Empty or
`hosted` selects standard `ubuntu-24.04`; `local` selects the existing
GitHub-registered `self-hosted` runners. Any other value fails workflow
expression evaluation with `INVALID_CI_RUNNER_MODE_expected_hosted_or_local`,
before a job starts. Both required jobs use the same selector directly;
there is no hosted helper job that could block local recovery at quota.
A Gitea act_runner registration alone does not accept GitHub jobs.

Hosted preparation uses commit-pinned setup actions: Python 3.12, CUE 0.17.1,
Ruff 0.16.8, PHP 8.4 without coverage instrumentation, and Composer 2.
The Ubuntu image supplies Git and Bash; missing jq, ripgrep, tmux and
Bubblewrap are installed explicitly. Preflight proves Bubblewrap can create
the namespace and bind mounts required by the existing isolation tests before
any suite starts. Local mode does not install tools or
alter operator configuration. The CI adapter requires the actual declared
tools; the same lint, configuration, suite and app checks enforce compatibility.
Every receipt binds resolved tool versions/binary hashes and the actual runner
environment. Hosted image identity is also an input. Switching environment or
changing an image/tool forces fresh checks; changing only a runner name does
not. Unknown hosted image identity refuses rather than reusing old proof.
Private test worlds disable automatic Git packing/maintenance so object files
cannot disappear while calibration copies a fixture. Operator Git configuration
is unchanged; the setting belongs to the world's command environment.

The existing stop on hosted usage remains. This initial switch is manual;
there is no billing API prerequisite, paid-overage change or quota polling.
From an authenticated checkout with `gh` repository-variable permission:

```sh
python3 -m ops.devlane.workflow.checks.ci_runners set-mode --repo OWNER/REPO --mode local
```

This changes routing for new jobs, not already queued work. For an exhausted
or otherwise blocked hosted run, cancel it if still active and wait until
GitHub marks it completed. Recover that original run without a source edit:

```sh
python3 -m ops.devlane.workflow.checks.ci_runners recover --repo OWNER/REPO --mode local --run RUN_ID
gh run watch RUN_ID --repo OWNER/REPO --exit-status
python3 -m ops.devlane.workflow.checks.ci_runners inspect --repo OWNER/REPO --mode local --run RUN_ID --expect-sha ORIGINAL_HEAD_SHA
```

`recover` validates the workflow, repository, trusted head repository and
candidate, writes and reads back the variable, then requests a rerun of the
original run. Its `requested` result is not a pass. `inspect` checks the
original candidate SHA, latest attempt, both required completed successful jobs
and their actual runner labels/names. Missing, duplicate, failed, cancelled,
queued/offline or wrong-environment jobs remain `not-verified` (exit 1).
Read/mutation errors refuse (exit 2); there is no automatic retry loop.
The native rerun must demonstrate that routing was re-evaluated; queued jobs
are never claimed to have moved merely because the variable changed.

To return to the included hosted allowance after reset:

```sh
python3 -m ops.devlane.workflow.checks.ci_runners set-mode --repo OWNER/REPO --mode hosted
```

The same operations are available in repository Settings → Secrets and
variables → Actions → Variables, followed by Actions → original run → Re-run
all jobs. Check the resulting runner identities and candidate before merging.
No dummy commit, dispatcher, grant command, model call or new token belongs
in the recovery path. The operator's existing GitHub authentication belongs
only to the control command, never to child verification checks.

Quota exhaustion is represented by a never-started fixture in tests; native
mode switching and candidate/status preservation must be measured separately.
Report actual job durations and runner identities. Hosted minute estimates
round each executed Ubuntu job up separately, including short reused jobs;
local elapsed minutes do not consume the hosted allowance. Use the existing
`ci_minutes.py` report for repository estimates; it is not organization billing.
