# Scope: revise-tests, sessions slice 1 (A-483)

Revise ops/conductor/tests/test_sessions.py,
ops/conductor/tests/test_session_adapters.py and
ops/conductor/tests/fakes/session_harness.py, session_tmux.py against
the 26 findings in
.dev/records/dispatches/20260922T215604Z-review-codex-f6777b.json
(result.envelope.findings). Contract: ops/conductor/sessions-lever.md.
No implementation exists; every row stays red on its own assertion.
The three p1s are fixed, never answered away. Read the input's
First-run walkthrough first: the socket-length limit, the hermetic
home, the calibration gap and the subprocess rule are measured there.
Note: each finding number with fixed or answered <why>, and the reading
of python3 -m unittest discover -s ops/conductor/tests -p
'test_session*.py'.
