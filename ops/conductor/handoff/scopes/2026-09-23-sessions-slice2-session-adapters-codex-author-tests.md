# Scope: author `test_session_adapters_codex.py` for sessions slice 2

Job: author-tests. Producer: Grok (the contract's author, Claude Fable
5.1, agentscient-87, writes no test). Checked once by Codex
(check-tests), implemented by the S2 builder, reviewed by Grok and Codex.
Withheld: implementation. None exists; read none.

Contract: `ops/conductor/sessions-lever.md` at the ref given, "The
adapter boundary, extended" at lines 376–393 (the five methods:
`transport`, `channel`, `handshake`, `submit`, `observe`) with slice 1's
boundary at 153–177, the `channel` refusal at 425–434, and fixtures 4
and 6 at 449–509. Read `docs/tests.md`, `ops/testkit/` and
`ops/conductor/tests/test_session_adapters.py` as the worked example
over the adapter interface and the real `framing.Parser`.

Write `ops/conductor/tests/test_session_adapters_codex.py` on the kit:
`World` hermetic, the fake app-server `fakes/session_codex.py` (new,
yours: `app-server --listen stdio://` shape, answers `initialize`,
`thread/start` with the spec's thread id, `turn/start` with a turn id,
emits `turn/started`, `item/agentMessage/delta`, `turn/completed`
carrying its `threadId`; a spec method answered -32601; one JSON line
per request) planted through `Tools`, spawned through `run` with a
timeout, rows by id with `origin: sessions-lever.md#slice-2 adapters`,
`refusal_wire` on the refusal rows. No program embedded in the test
module (rule 6).

Rows: `transport()` reads `protocol`; `channel()` argv ends with
`app-server --listen stdio://`; `handshake` returns the spec's thread
id, and a fake dying after `initialize` refuses `channel` naming
`thread/start`; `submit` idle opens a turn and reads `accepted turn
<id>`, busy sends `toolOutput` into the active turn (the fake's log),
-32601 reads `unsupported turn/start`; `observe` classifies each
emitted frame (`native`, `activity`, `output`, `done`), a frame naming
another `threadId` reads `refused native`, a permission request is
answered `decline` and read `permission <title>`. A pin on a count the
contract does not own is a finding. Report `reused:` names in the note.
