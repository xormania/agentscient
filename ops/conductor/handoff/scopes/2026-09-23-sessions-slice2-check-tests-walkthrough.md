# Input: check the tests for managed sessions, slice 2 (A-503 to A-506)

Readings taken 2026-09-23 by the contract session (agentscient-87,
Claude Fable 5.1) against lane/session-20260923-87 at 5e41f41c and
this host. One pass, fixed once, no re-check (owner, 2026-09-23:
"practical issues, not theoretical").

## First-run walkthrough

- order (the Lead, 2026-09-23): do not run test_session* until the
  tmux-leak fix (agentscient-5c, sha to follow) is on the tree; each
  run leaks about 40 tmux servers. Measured by the XO: the slice 1 test
  world leaks its private tmux server, and 1,211 servers held about
  43 GB at 01:35Z. A check that needs a reading of the suite reads the
  last landed record instead, and says so in the note.
- assumption: the contract is in the tree. Measured: the section
  "Slice 2 — persistent native conversation" is
  `ops/conductor/sessions-lever.md` lines 256–509 at b9bc1444, with
  slice 1's sections above it.
- assumption: no slice 2 implementation exists. Measured at 5e41f41c:
  `ops/conductor/tools/sessions.py` and `courier.py` are slice 1's;
  `sessions.py` has no `bridge` and still lists `join` and `recover`
  under `LATER` as "slice 2"; `session_adapters/codex.py`,
  `session_adapters/grok.py`, `tests/fakes/session_codex.py` are absent;
  `coordination.py` has no `--key` and no `delivery_routes`. Every row
  stays red on its own assertion, never on import or setup.
- assumption: the kit binds. Measured (docs/tests.md): `from
  ops.testkit import World, run, refusal_wire`; a fake planted through
  `Tools`; every subprocess through `run` with a timeout; a program
  embedded in a test module is a finding (rule 6, A-481 #7), and the
  wall refuses it at CI, so it is rated practical.
- assumption: a tmux socket under the world root fits. Refusal: the host
  refuses a unix socket path of 108 bytes or more (slice 1, A-481 #2);
  the socket goes in a short directory the world owns.
- assumption: grok can claim the assignment through the store. Refusal:
  the launcher wires the acting coordination MCP for codex only
  (`launch.py:640 COORD_MCP_HARNESSES = ("codex",)` at 5e41f41c); the
  note says the claim was not possible and the XO settles the store.
- assumption: findings are requirements. Refusal: a finding is practical
  when a row cannot fail, does not execute the subject, pins a count the
  contract does not own, embeds a program, or reaches outside the world;
  a finding on style or on a theoretical fault is recorded and declined.
