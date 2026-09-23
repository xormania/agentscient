# Scope: author `test_session_adapters_grok.py` for sessions slice 2

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, agentscient-87, writes no test). Checked once by Codex
(check-tests), implemented by the S2 builder, reviewed by Grok and Codex.
Withheld: implementation. None exists; read none.

Contract: `ops/conductor/sessions-lever.md` at the ref given, "The
adapter boundary, extended" at lines 376–393 (the five methods:
`transport`, `channel`, `handshake`, `submit`, `observe`) with slice 1's
boundary at 153–177, the `channel` refusal at 425–434, and fixture 6 at
449–509. Read `docs/tests.md`, `ops/testkit/` and
`ops/conductor/tests/test_session_adapters.py` as the worked example
over the adapter interface and the real `framing.Parser`.

Write `ops/conductor/tests/test_session_adapters_grok.py` on the kit:
`World` hermetic, the fake ACP agent `fakes/session_grok.py` (new,
yours: `agent stdio` shape, answers `initialize` with protocolVersion 1
and an `authenticate` method when the spec advertises one,
`session/new` with the spec's session id, `session/prompt` and
`_x.ai/interject`, emits `session/update`,
`_x.ai/session/prompt_complete` and, on the spec's word, a
`session/request_permission`; a spec method answered -32601; one JSON
line per request) planted through `Tools`, spawned through `run` with a
timeout, rows by id with `origin: sessions-lever.md#slice-2 adapters`,
`refusal_wire` on the refusal rows. No program embedded in the test
module (rule 6).

Rows: `transport()` reads `protocol`; `channel()` argv ends with `agent
stdio`; `handshake` returns the spec's session id, calls `authenticate`
only when advertised, and a fake dying after `initialize` refuses
`channel` naming `session/new`; `submit` idle sends `session/prompt`
and reads `written`, busy sends `_x.ai/interject` (the fake's log),
-32601 reads `unsupported session/prompt`; `observe` classifies each
emitted frame, a frame naming another `sessionId` reads `refused
native`, `session/request_permission` is answered `decline` and read
`permission <title>`. A pin on a count the contract does not own is a
finding. Report `reused:` names in the note.
