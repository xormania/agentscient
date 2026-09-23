# One dev-lane verification gate

Owner direction, 2026-09-23: consolidate CI into shared check definitions,
bounded execution and a verdict that cannot pass missing work. This replaces
the old workflow step-order and absent-suite behavior. It does not change the
application job or the release evidence attached to a push on dev.

`bash ops/bin/suites.sh` is the full gate locally and in GitHub. Its adapter,
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

The GitHub workflow only prepares checkout, PATH and record refs, supplies
TERM_WALL, and invokes the full gate. Its lane and app jobs, triggers,
concurrency, timeouts and pinned checkout remain. The workflow uses JSON
syntax within its .yml file, a YAML subset read by the standard JSON parser;
the former handwritten YAML parser is retired. The configuration closure
check reads that same format. Contract tests inspect executable argv and
conditions, not step names, and prove that disabling the gate is detected.

The adapter and kit are wall machinery and join the existing wall path
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
