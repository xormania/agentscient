# Brief: the wall session for job timeouts

Written by the XO (PT-21, Claude Opus 5.5) on 2026-09-22, at the Lead's
order (agentscient-d8, PT-20). Readings taken at origin/dev e20dac19.

Owner, 2026-09-22, relayed by the Lead: "raise them to 60 mins - we're
shooting ourselves in the foot".

## Start

- Cut `lane/session-<date>-<id>` from `dev` in your own worktree. Add
  your lock with `deliverable.py add`. The measure must read both items
  on origin/dev, and it runs under `sh -c` because deliverable.py runs
  its measure with no shell.
- Grants come from the owner's words typed in your own terminal. A
  relayed grant is refused; the builder of this slice refused one
  correctly. Two classes are needed:
  - `wall` for `ops/devlane/task/jobs.json` and
    `ops/devlane/dispatch/launch.py`. Both are in matrix.py WALL_PATHS.
  - `other` for `ops/devlane/dispatch/tests/test_launch_job_caps.py`
    and `ops/devlane/dispatch/CONTRACT.md`. Neither is a wall path.
    Tests stay with the code they test.
- Do not touch any other worktree. Dispatches are running from
  lane/session-20260922-69.

## Readings

- jobs.json caps.timeout: verify 900, adversarial-review 1800,
  security-audit 1200, author-tests 1800, sweep 900, plan 900,
  check-tests 1800, implement 3600, adjudicate 900.
- launch.py:1934-1942 resolves `DISPATCH_TIMEOUT` from the environment,
  else the job cap, else WALL_DEFAULT. It records `timeout_source` and
  never clamps.
- CONTRACT.md:1178-1188 declares that order and a closed source enum:
  `DISPATCH_TIMEOUT`, `job`, `default`.
- test_launch_job_caps.py:103-114 pins today's behaviour. It sets
  ENV_TIMEOUT 123.5 over JOB_TIMEOUT 42 and asserts the environment
  value wins.
- The 1800s author-tests cap was measured killing live work today:
  - A-483 timed out and kept only d2a24d8c.
  - Record 20260922T231526Z-code-grok-312c63 was still committing red
    rows when its limit came near.

## Item 1: every job cap to 3600

1. Contract first: CONTRACT.md says a job's caps.timeout is 3600, so a
   row that checks the value is backed by the contract (docs/tests.md
   rule 3).
2. Red row: launch each job in the real catalogue with no
   `DISPATCH_TIMEOUT` set. Assert that the recorded caps.timeout is 3600
   and the source is `job`. This runs the subject, per rule 9. Prove it
   red at e20dac19.
3. Green: set the eight caps below 3600 to 3600.
4. The planted fixtures in test_ladder_tables.py:155-161 and
   fakes/ladder_dispatch.py:277 are not reads of jobs.json. Leave them.

## Item 2: DISPATCH_TIMEOUT bounded by the job cap

1. Contract first: amend CONTRACT.md:1178. Say what happens when the
   environment asks for more than the cap, and record the requested
   value beside the one applied.
2. Red rows: rewrite 103-114 into two rows:
   - above the cap: not admitted as given;
   - below the cap: admitted, with source `DISPATCH_TIMEOUT`.
   Prove both red at e20dac19.
3. Green in launch.py:1934-1942.
4. Not yours to fix: pipelines.md:128 tells launch scripts to set
   `DISPATCH_TIMEOUT`, and after this change that can only lower a cap.
   Note it in the PR as a follow-up.

## Proof and close

- Red then green, each proven with the same command:
  `python3 -m unittest discover -s ops/devlane/dispatch/tests -p 'test_launch_job_caps.py'`.
  Then `ops/bin/suites.sh` exit 0.
- This is one producer under a hand grant. Say in each commit that the
  second producer is absent.
- Open one draft PR into dev. It carries probe rows, a `## Proof`
  section, green CI on the head, and a codex security audit with every
  finding disposed. The Lead flips and merges on the XO's line.
- Settle each grant with a bare sha. Write a handoff for anything left
  open.
