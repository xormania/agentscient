# Scope: re-check-tests, sessions slice 1 (A-484)

Contract: ops/conductor/sessions-lever.md. Candidate: the revised
ops/conductor/tests/test_sessions.py, test_session_adapters.py,
fakes/session_harness.py and fakes/session_tmux.py (A-483). Judge only
whether each of the 26 findings in
.dev/records/dispatches/20260922T215604Z-review-codex-f6777b.json was
fixed, or answered with a contract line that holds. Re-run the three
p1s (test_sessions.py:61, :394, :572 in the old numbering) from their
reproduce commands; never take the revision's note on trust. A finding
still standing is one finding again, with its old number in the claim.
A new defect the revision introduced is one finding. The calibration
gap is declared until the implementation exists; it is not a finding.
