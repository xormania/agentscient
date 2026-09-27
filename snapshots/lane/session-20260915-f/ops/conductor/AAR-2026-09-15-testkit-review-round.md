# AAR — 2026-09-15, the test kit review round: Grok 4.6 reviewed, Astra ruled, seven corrections by hand

Record by Claude Fable 5.1 on `lane/session-20260914-b`, the third part
of the session (the first two: `AAR-2026-09-14-testkit-reading.md`,
`AAR-2026-09-14-testkit-plan-landed.md`). Grants 231 (other) and 232
(wall), both at the owner's word; the second producer is absent on
every commit and every commit says so.

## The request, in the owner's words

- "have grok 4.6 review - then have astra decide what is important and
  report back to you - then you correct it"
- on the launcher's refusal of the review: "this is bullshit - i'm
  signing in every day to grok - find out wtf is going on", then "fix
  the launcher so the renewals carry back - do it now"

## What was found first: the credential (LD-41, #217 at f08d56c7)

The launcher refused the review at 39.1 h since the last login. The
grok CLI renews its token by renaming a new file over the credential,
which turns the symlink `build_home` plants into a regular file inside
the job home; 48 job homes held a renewal, 222 the link, and the host
copy carried the 2026-09-13 login. The CLI's own log showed only two
logins on this host (the 11th and the 13th), each after a
`RefreshTokenRejected`. `isolation.carry_back` now copies a renewed
file back after every attempt and records the reading; the review's
attempt read `[{'file': 'auth.json', 'outcome': 'linked'}]` (a minute after the login, no renewal yet;
T-33 waits for the first `carried`).

## The review and the ruling

- Grok 4.6, record `20260915T023743Z-review-grok-7da077`: verdict
  changes, counts {'p1': 0, 'p2': 5, 'p3': 0, 'opinions': 0}; all five
  reproduced on the tree by the session before the ruling.
- Astra (`gpt-6-astra` on codex), record
  `20260915T025600Z-adjudicate-codex-68d3d9`, dispatched as
  `adversarial-review` at stage `adjudicate` with the ruling brief as
  the scope (LD-42: the `adjudicate` job cannot pass the wrapper):
  verdict changes, counts {'p1': 0, 'p2': 7, 'p3': 0, 'opinions': 0}. F1 and F2
  UPHELD, F4 and F5 PARTIAL, F3 REJECTED (the row's origin brief names
  the class), and three defects Grok missed: the wire assertion
  certifying malformed refusals, the unbounded timeout cleanup, and
  `enter` losing named ambient values.

## The corrections

- `e4df7c5e` (ranks 1 to 4, the kit): contents in a watch, with
  `contents=False` for the live-store guard after the ladder suite
  stalled ten minutes hashing the dispatch store; the strict wire; a
  session per child and a bounded cleanup; `enter` reading before
  clearing.
- `598e0f98` (ranks 5 to 7): the same-directory row and the retained
  end-to-end assertion, `M-derive-first-per-directory`; the kit-import
  row at any depth, by ast, with a reasoned exemption and untracked
  files as new; the ratchet below `tests/`, baseline 179 -> 185.
- The calibrate record `calibrate-ladder-tables-20260915.json` at
  `598e0f98`: clean green, mutants {'M-derive-abs': 'caught', 'M-derive-dotdot': 'caught', 'M-derive-first-per-directory': 'caught', 'M-derive-support': 'caught', 'M-resume-options': 'caught', 'M-retry-unspent': 'caught', 'M-wall-default': 'caught'},
  quiet [].

## Readings at close

- Branch `598e0f98`, `origin/dev` `f08d56c7`.
- Full suite at `598e0f98`: == ruff All checks passed! == devlane/dispatch Ran 622 tests in 74.124s OK == devlane/harness Ran 164 tests in 6.434s OK == devlane/task Ran 356 tests in 11.969s OK == devlane/telemetry Ran 227 tests in 45.714s OK == devlane/hooks Ran 304 tests in 62.009s OK == devlane/fixtures Ran 221 tests in 35.878s OK (skipped=6) == devlane/workflow Ran 61 tests in 1.355s OK == testkit Ran 34 tests in 8.481s OK == conductor Ran 1166 tests in 147.996s OK == pr-overview Ran 8 tests in 0.860s OK suites exit 0
- Corpus: 598e0f98 {'pass': 251, 'fail': 0, 'unreachable': 0}
- The ratchet: ratchet holds: home_by_hand=57, embedded_programs=30, run_without_timeout=185
- Findings: 20260915T023743Z-review-grok-7da077|fixed|4; 20260915T023743Z-review-grok-7da077|ruled|1; 20260915T025600Z-adjudicate-codex-68d3d9|fixed|7
- Grants: 231 other the test kit review round: the scope files for a Grok 4.6 adversarial review and an Astra adjudication, dispatched through dispatch.sh; then the corrections the ruling upholds, by hand age=5582s ttl=28800s within ttl; 232 wall the corrections Astra ruled on the test kit review (record 20260915T025600Z-adjudicate-codex-68d3d9): ops/testkit/ world.py and command.py and their tests, the kit-import row in ops/devlane/hooks/claude/engine.py and its test age=1650s ttl=28800s within ttl
- H-7: T-32 open [H-7] LD-42: the adjudicate and verify jobs cannot be dispatched through dispatch.sh (scope-cap refuses any scope; the wrapper always passes one) — to a later session — opened by Claude Fable 5.1 <noreply@anthropic.com> 1m ago; T-33 open [H-7] the credential carry-back (LD-41, #217 at f08d56c7): its first live `carried` reading — to next session — opened by Claude Fable 5.1 <noreply@anthropic.com> 1m ago; T-34 open [H-7] a second producer reads the kit corrections (docs/tests.md rule 8) — to a later session — opened by Claude Fable 5.1 <noreply@anthropic.com> 1m ago; T-35 open [H-7] the ratchet's exposed debt: run_without_timeout 179 -> 185 under tests/fakes/ — to a later session — opened by Claude Fable 5.1 <noreply@anthropic.com> 1m ago

## What went wrong

- `dispatch.sh --job adjudicate` refused on scope-cap and, without a
  scope file, on the wrapper's own check: LD-42.
- The first content-aware watch hashed the whole live dispatch store
  through the ladder fixture's guard; the runner was killed at ten
  minutes and the guard declared shallow.
- The exemption pattern's `\s+` matched a newline, so `# testkit:
  exempt` alone passed once more; caught by the engine test's red.
- The `calibrate` verb reads the committed tree: the first record after
  the row was written still read quiet, and the record was regenerated
  after the commit.
- Twelve hook refusals this part: clipped-sweep 5, graft-first 3,
  hand-write 2, trunk-commit 0, claim-unmeasured 0.

## Handoff

H-7 in the store: T-32 (LD-42), T-33 (the first `carried` reading),
T-34 (a second producer over the kit corrections, rule 8), T-35 (the
ratchet's exposed debt). Records ride this PR (session -a, 2026-09-15:
no records-only PR).
