# Bucket calibration — declared against measured

Written 2026-09-04 by the session; minutes from each record's `at.launched` to `at.closed`. The planner's calibration table (fix scope item 25) starts here; the driver writes these rows itself once it exists.

| slice | plan said | stage | minutes | files / tests |
|:--|:--|:--|--:|:--|
| fixtures slice 1 | S | tests | 23 | 5 files, 63 tests, 2,246 lines (first round) |
| fixtures slice 1 | S | skeptic | 11 | 15 findings |
| fixtures slice 1 | S | fix round | 22 | 6 files, all 15 addressed |
| fixtures slice 1 | S | implement A | 8 | 4 files |
| fixtures slice 1 | S | implement B | 8 | 2 files; suites 1,252 OK |
| lane conf unit 1 | S | tests | 22 | 5 files (first round) |
| lane conf unit 1 | S | skeptic | 11 | 10 findings |
| lane conf unit 1 | S | fix round | 26 | 11 files, 2,159 lines, 105 red |
| lane conf unit 1 | S | implement A | 16 | 7 files |

Reading: both slices the plan called S measured M by the item 25 rule (4 to 8 files, 15 to 25 minutes a run). The tests rounds ran 22 to 23 minutes; the two-run implement kept each Sol run short with no trip. The planner's S is a first-draft guess; these rows are what it is calibrated against next time.

## Calibration row — item 31, hand-driven, measured 14:2xZ from the records

Declared: S (3–4 files, one implement run). Measured: 4 files; 10 dispatches; 2 implement runs (one not landed) + 1 fix code run; 3 review rounds (audits ×2, re-audit ×1) + 1 skeptic; 3 tests rounds; worker minutes 105.5; wasted 6.7 (the shim run); verdicts: skeptic changes, audits changes ×2, re-audit changes; batch stopped by D-LADDER-1 after the one fix round; second slice by plan.

| record | job | envelope | verdict | files | minutes | note |
|---|---|---|---|---|---|---|
| 20260904T121113Z-code-grok-7550ea | author-tests | ok | - | 2 | 13.0 |  |
| 20260904T122519Z-review-codex-beb482 | check-tests | tripped | changes | 0 | 6.4 | tripped on the report file (the defect itself); findings read by hand |
| 20260904T123335Z-code-grok-aceb6b | author-tests | ok | - | 3 | 19.4 |  |
| 20260904T130010Z-code-codex-f2506c | implement | ok | - | 5 | 6.7 | not landed (root shim outside the bucket; session command shape) |
| 20260904T130929Z-code-codex-4c8897 | implement | ok | - | 4 | 6.7 |  |
| 20260904T132037Z-review-codex-9fcb17 | security-audit | ok | changes | 0 | 6.7 |  |
| 20260904T132059Z-review-grok-2e7e4b | adversarial-review | ok | changes | 0 | 10.1 |  |
| 20260904T133139Z-code-grok-a24911 | author-tests | ok | - | 3 | 18.3 |  |
| 20260904T135018Z-code-codex-b253a4 | implement | ok | - | 1 | 10.4 |  |
| 20260904T140242Z-review-codex-69d0fb | security-audit | ok | changes | 0 | 7.8 |  |

Session touches on this lane (the baseline for the owner's theory test, 14:2xZ): 10 hand-composed dispatches (all through dispatch.sh, all vetted by the matrix from 12:5xZ on), 5 landings by the lever, 0 hand code grants, 1 command-shape error costing one run. The second slice runs under the driver: the target is 0 hand-composed dispatches for it.
