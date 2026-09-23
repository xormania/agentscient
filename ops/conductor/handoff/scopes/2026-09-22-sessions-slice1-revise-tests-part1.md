# Scope: revise-tests part 1, sessions slice 1 (A-489)

Findings: .dev/records/dispatches/20260922T215604Z-review-codex-f6777b.json
(result.envelope.findings, numbered from 1 in order). Contract:
ops/conductor/sessions-lever.md. No implementation exists; every row
stays red on its own assertion. test_session_adapters.py was revised
at d2a24d8c: do not touch it. This scope narrows the Scope section of
the walkthrough input; its First-run walkthrough still holds.
Fix findings 1, 10, 15 (the p1s, never answered away) and 18, 19, 20,
21 (every subprocess through ops.testkit.run with a timeout), in
ops/conductor/tests/test_sessions.py and
ops/conductor/tests/fakes/session_harness.py, session_tmux.py.
Commit after each finding is fixed. Note: each number with fixed.
