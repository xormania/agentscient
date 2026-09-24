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
repeating successful verification. Keep the current self-hosted runners.
This supersedes the earlier proposal to default to hosted execution.

- Run inexpensive guards before suites. A failed guard ends the gate red
  without launching expensive work. Preflight still validates the whole plan.
- Discover conductor modules independently, including newly added modules,
  and schedule with a bounded worker pool. Keep all existing cases and their
  failure semantics. Record module durations; target the previous roughly
  three-minute native gate, and report actual timing before claiming success.
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
  participates in the CI gate. Runner selection stays self-hosted until the
  owner explicitly requests a later hosted rollout.
