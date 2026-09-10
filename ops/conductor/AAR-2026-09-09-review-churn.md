# Review churn during finding-admission work

Standing: measured report and work-order guidance, not a new acceptance gate.
Recorded 2026-09-10T01:02:04.859611+00:00 against `46a2805d1f7075a5491a451ab4346e8f3d26192c`. The implementation remains in progress.

## What happened

Independent test reviews accepted fixtures whose assumptions did not match
existing interfaces. The monitor helper changed an explicitly empty branch
list into valid defaults, and event assertions guessed how the existing
consumer formatted metrics. Admission fixtures omitted declared dependencies
and provenance, used keys outside their mocked batch, and inherited a raw
report input that the new contract expressly replaces.

The initial red runs often stopped at the absent API. Those failures proved
that the feature was absent; they did not exercise the later assertions.
Corrections were dispatched as problems appeared, producing serial cycles.
The conductor also prohibited inspection of established implementation too
broadly while trying to keep new implementation hidden from test authors.
That decision contributed to the guessed interface assumptions.

These were concrete test defects, so fixing them was justified. Repeated
serial review rounds were the avoidable part. Suggestions never gain correction
authority merely because a reviewer supplied them.

## Measured evidence

- Monitor fixture corrections and their closure are retained in dispatches
  `20260910T003157Z-tests-grok-298598`,
  `20260910T003832Z-tests-grok-53065e`, and
  `20260910T004501Z-check-tests-claude-8051ef`.
  [The monitor receipt](handoff/evidence-2026-09-09-git-refs/tdd.json) lives on
  `lane/dev-freshness-20260909`; it records identical red/green test hashes,
  19 focused passes and 2,233 full-suite tests with six skipped.
- Admission fixture corrections are retained in
  `20260910T003757Z-tests-grok-49b66c`; independent closure
  `20260910T005000Z-check-tests-claude-f02a37` approved them at
  `d9b0cb6825a06b2f2ca17ddd74358f36ff4ec64b`. The four unchanged commands ran 102 tests against old
  source, with 34 assertion failures and no errors.
- The same test bytes against preserved implementation
  `d391c00927d69399a4a1bf682ee6d642b57ca4ba` exposed five failures: independent PARTIAL admission,
  empty correction bookkeeping, two withheld-implementation leak refusals,
  and the prior code record's custody reference. These are the bounded
  correction batch in `20260910T005819Z-code-codex-5b0115`.

## Work-order guidance from this run

1. Verify fixture preconditions before accepting red. Prove the actual
   planted input and consult the established public interface. Keep the new
   implementation hidden from test authors; do not hide an existing API they
   must consume. Label absent-API red accurately instead of treating it as
   proof that downstream assertions have been exercised.
2. Collect known interface contradictions into one batch before a correction
   dispatch. Verify the named corrections together. Do not restart a general
   test review after each small fix.
3. Apply the same admission test to every new demand: existing requirement,
   reachable trigger, actual failure and reproduction or evidenced path.
   Follow-up review covers named fixes and affected behavior; additional
   demands must independently earn action. Keep expansion and unproven claims
   visible without making them conditions.
4. Put the finish line in the work order: frozen acceptance commands, the
   existing required final checks, then the draft PR into `dev`. An optional
   improvement does not silently add another stage.

For this run, tests remain frozen and the active implementation order is the
five reproduced failures above. After correction, reproduce green, run the
full lane suite, complete the existing independent acceptance batch and open
the draft PR. The monitor implementation stays unchanged. This report adds
no feature, new review count, automated gate or condition to either PR.
