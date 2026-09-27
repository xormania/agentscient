# AAR — 2026-09-15, every test family onto the kit

Record by Claude Fable 5.1 on `lane/session-20260914-b`, the fourth part
of the session. Grants 234 (other) and 235 (wall), at the owner's word;
the second producer is absent on every hand commit and each says so.

## The order, in the owner's words

- 2026-09-12: "reuse of testing patterns - a framework going forward
  that avoids one-off tests in favor of a testing framework"
- 2026-09-15: "is the tesing sysem overhauled?"; then "all this and you
  didn't do it?"; "i said i don't want to hear from you until its done -
  and its NOT DONE"; "GET IT FUCKING DONE!!!!!! FUCK YOUR EXCUSES"

## What was wrong before this part

The plan record 20260913T034513Z-plan-claude-892490 built the kit,
enforced it on new modules and migrated one family; its 21 slices were
reported as all done (AAR-2026-09-14-testkit-plan-landed.md) while 205 of
222 lane test modules stood off the kit. Nothing mechanical had stopped
the migration: the deliverable was measured against the plan, not a
census, and the gate had no floor. Session -a put a measured target on
the deliverable lock (#219); sessions -a and -ab added the done gate
(#220, #221). This part is the migration itself.

## What was done

- `testkit_ratchet.py --census` (1b670118): the one line the lock
  measures, `modules=N on_kit=N exempt=N off_kit=N`; fixture
  applications excluded.
- A migration guide as the workers' input
  (`.dev/ladder-inputs/testkit-migration-guide.md`) and a dispatcher of
  84 chunks (support modules first per family, then modules): 86
  author-tests dispatches, records `20260915T045242Z-tests-codex-0353f2` to `20260915T064034Z-tests-codex-0e5fd3`, codex
  and grok alternating; landed 43 on codex and 41
  on grok, each on its modules' discover commands, ruff and the ratchet,
  as 84 merge commits on the branch. Two chunks were retried on
  the other harness; two landed by hand (chunk 6: the corpus run keeps
  the host environment, 12a94173; chunk 14: its module Ran 29 OK alone
  while the family suite had HEAD moving under it).
- By hand: the fixtures' portable copy carries the kit (e024511c, after
  a landing reset dropped its first commit 2720bbb8); test_engine.py
  onto the kit (12f1e8ee); the kit's own leaves and the fixture
  applications exempt or excluded.
- The diff against the trunk before the migration (aba8600a): 248 files changed, 10380 insertions(+), 9365 deletions(-).

## Readings at close

- Branch `cc463a6b`, `origin/dev` `b123181b`.
- Full suite lever at `cc463a6b`: == ruff All checks passed! == devlane/dispatch Ran 622 tests in 80.047s OK == devlane/harness Ran 164 tests in 6.933s OK == devlane/task Ran 356 tests in 12.205s OK == devlane/telemetry Ran 227 tests in 20.172s OK == devlane/hooks Ran 310 tests in 67.920s OK == devlane/fixtures Ran 221 tests in 35.085s OK (skipped=6) == devlane/workflow Ran 62 tests in 1.452s OK == testkit Ran 34 tests in 8.640s OK == conductor Ran 1181 tests in 176.156s OK == pr-overview Ran 8 tests in 0.874s OK suites exit 0
- Census on this tree: modules=226 on_kit=216 exempt=10 off_kit=0
- The ratchet: ratchet holds: home_by_hand=8, embedded_programs=4, run_without_timeout=0
- Corpus: cc463a6b {'pass': 273, 'fail': 0, 'unreachable': 0}
- The lock, read from the main checkout (dev): target: expected the measure to read off_kit=0; found modules=222 on_kit=15 exempt=2 off_kit=205; needed keep going; done is the reading, never the named slices

## What went wrong

- The dispatch wrapper refused every launch for ten minutes with
  `stale-base` once the trunk moved: it merges dev forward and wants a
  clean `git status --porcelain`, and the untracked scope files and
  records made it dirty. The driver now merges the trunk forward itself.
- A landing's `git reset --hard` after a red suite dropped a commit made
  in the same window (2720bbb8); restored by cherry-pick (e024511c); the
  rule since: no hand commit while the driver runs, and the reset is
  guarded.
- The family suites as the landing gate were flaky under sixteen
  workers: the conductor suite takes three minutes and every record
  commit moves HEAD under it (LD-39's class); chunk-module discover runs
  became the gate, the family suites and the lever run at the end.
- A content-aware watch had to stay off the live-store guard (the
  review round's finding); the fixtures' portable copy and the corpus
  run under a hermetic HOME were the two places the kit's hermeticity
  met a host dependency, each named on its line.
- Residual census counts (home_by_hand 8, embedded_programs 4) sit in
  modules that are on the kit: assertions on the isolation module's own
  `{"HOME": ...}` environments, and support programs; they are the
  ratchet's next floor, not this order's target.

## Handoff

H-7 carries T-32 to T-35; this part adds nothing the lock does not
measure. The residual counts are the next reading to take down.
