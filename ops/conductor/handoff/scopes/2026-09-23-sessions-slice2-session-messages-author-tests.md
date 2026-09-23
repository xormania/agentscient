# Scope: author `test_session_messages.py` for sessions slice 2

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, agentscient-87, writes no test). Checked once by Codex
(check-tests), implemented by the S2 builder, reviewed by Grok and Codex.
Withheld: implementation. None exists; read none.

Contract: `ops/conductor/sessions-lever.md` at the ref given, the
section "Slice 2 — persistent native conversation" (lines 256–509 at
b9bc1444), against slice 1's sections above it. Read `docs/tests.md`,
`ops/testkit/` and `ops/conductor/tests/test_sessions.py` as the worked
example of a suite over `sessions.py`; the slice 1 fakes under
`ops/conductor/tests/fakes/session_*.py` are yours to extend.

Write `ops/conductor/tests/test_session_messages.py` on the kit:
`World` hermetic with the source lane's name (profiles.py pins
`LANE_CONF`), every subprocess through `run` with a timeout, harnesses
planted through `Tools` from `fakes/session_codex.py` and
`fakes/session_grok.py` (new, spec-driven: native id to answer, a
method to answer -32601, a request to die after; one JSON line per
request), rows by id with `origin: sessions-lever.md#slice-2 <n>`
naming the fixture number, `refusal_wire` on every refusal row. No
program embedded in the test module (rule 6, A-481 #7).

Rows, from the fixture set at lines 449–509 and the verbs at 407–423:
fixtures 1 (the cross-harness exchange through the bridge), 2 (two
codex members, second fake's log only), 6 (-32601: `unsupported`,
ingress `refused channel`, bridge alive), 7 (`recover` alive vs reaped
pid reused by a world-owned child, then `start` mints generation 2),
8 (`stop` on a stopped run: exit 2, marking row count unchanged),
9 (`--tmux-socket` at 108 bytes refuses `socket` with the tmux log
empty), 10 (`join` then `stop --terminate`: `unresolved unmanaged`,
nothing signalled), 11 (readiness probe acked vs never acked); the
`transport` refusals of `bridge` and `input` on a claude member; the
clean neighbours: all eight `ok` for a codex and a grok member, `input`
text in the fake's log. tmux rows on a private socket under 108 bytes;
skip with the reason when tmux is absent and count the skips in the
note. A pin on a count the contract does not own is a finding. Report
`reused:` names from `docs/tests.md` in the job note.
