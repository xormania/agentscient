# Scope: author the tests for the managed-sessions slice 1

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, PT-20, writes no test). Checked afterwards by Codex (check-tests),
implemented by Claude, reviewed by Grok and Codex.

Contract: `ops/conductor/sessions-lever.md` at the ref given. Read it
whole, then `docs/tests.md`, `ops/testkit/` (world, command, fakes,
cases), `ops/conductor/instrument-conventions.md`,
`ops/conductor/machine-lever.md`, and `ops/conductor/tests/test_handoff.py`
as the worked example of a suite over a machine on the engine. Do not
read any implementation: none exists.

Write:

1. `ops/conductor/tests/test_sessions.py`: a case table addressed by
   id, one row per fixture named in the contract's Tests section, each
   row with `origin: sessions-lever.md`, executing
   `python3 ops/conductor/tools/sessions.py <verb>` through
   `ops.testkit.run` with a timeout, asserting the printed lines, the
   exit class and, for refusals, the wire through `refusal_wire`.
   Cover every verb and every refusal class in the table. The cold
   start and populated-store rows read the coordination store after
   `start` and assert the participant's roles. The `stop --terminate`
   stale-pid row asserts the reused pid was not signalled (the world
   owns the child that holds the pid).
2. `ops/conductor/tests/test_session_adapters.py`: the framing faults
   through the real parser, and the adapter interface (the five
   methods, the `claude` adapter's `argv` carrying the launch id, its
   `probe` reading `unmeasured slice 2` for the channel).
3. The fake harness: planted through the registry (`Tools.plant(...,
   script=...)`), driven by a spec that says which session id to bind;
   it runs the profile's `guard.sh SessionStart` and then blocks on
   stdin. No program embedded in the test module.
4. tmux rows on a private socket in the world; skip with the reason
   when tmux is absent, and say in the note how many rows skipped.

Rules that bind: every subprocess through `run` with a timeout; the
world hermetic, ambient named; no test package; a pin on a count the
contract does not own is a finding. Report `reused:` names from
`docs/tests.md` in the job note.
