# Scope: check-tests, sessions slice 1 (A-478)

Contract: ops/conductor/sessions-lever.md (at 13664232, in the tree).
Candidate, by Grok (record 20260922T213030Z-code-grok-1693c9, commits
d078b68b, ea39ec55): ops/conductor/tests/test_sessions.py,
ops/conductor/tests/test_session_adapters.py,
ops/conductor/tests/fakes/session_harness.py,
ops/conductor/tests/fakes/session_tmux.py.
No implementation exists; every row is red by design. Judge each row by
the broken sessions.py it would still pass.
Also judge against docs/tests.md: rule 6 (are the fakes planted through
the registry, or programs embedded in the suite), rule 9, rule 3, rule 5
(every subprocess through run with a timeout), rule 4 (no read of the
operator's home or store). A fixture in the contract's Tests section or
a refusal class in its table with no row is one finding.
