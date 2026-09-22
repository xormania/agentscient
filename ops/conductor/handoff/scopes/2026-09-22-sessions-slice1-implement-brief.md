# Brief: implement sessions slice 1 by hand (A-479)

For the Claude Opus 5.5 builder session the owner starts (Lead's order
2026-09-22, on the owner's "make sure Sonnet doesn't write code - use
Opus5.5"). Written by the XO (Claude Opus 5.5, PT-21), who does not
write the work it coordinates. Readings are stamped where taken.

## Why by hand

`ops/devlane/dispatch/launch.py` refuses every claude write dispatch
("write-role-unadmitted: expected a write row with a containment entry;
found none for claude"), measured at dev 7de37de6. Grok wrote the tests
and codex approves them, so neither may implement (AGENTS.md: whoever
writes an implementation neither writes nor approves its tests). The
builder works in its own session under its own hand grant.

## First-run walkthrough

- assumption: the tests are final. Refusal: they are being revised
  against the 26 findings of record 20260922T215604Z-review-codex-f6777b
  (A-489 part 1, A-490 part 2), then re-checked by codex (A-484). Until
  A-484 closes, build only the pieces that do not depend on the tests.
- assumption: the builder can claim A-479. Measured: a self-bind needs
  the caller's own capability (coordination-lever.md, the unprofiled CLI
  carries its own `COORDINATION_CAPABILITY`); mint a 64-hex value into a
  mode-600 file in the session's scratchpad, bind with it, and read it
  into the environment for each call. Never paste it.
- assumption: the proof is readable. Measured: the proof is at
  `/home/scientdb/projects/poc/multi-harness-proof`, HEAD a944f31, MIT,
  LICENSE "Copyright (c) 2026 xor"; all ten `mhproof/` files are stdlib.
  The withheld parts are listed in
  `ops/conductor/handoff/PT-23-proof-adaptation-inventory-2026-09-22.md`
  on lane/session-20260922-d65f.
- assumption: pieces exist already. Measured: PT-23 (Claude Sonnet 5)
  pushed team.default.json, ops/bin/conduct.sh,
  placement/sessions.py.json, session_adapters/SOURCES.md and
  session_adapters/framing.py at 495d5a19 on lane/session-20260922-d65f
  before the owner's ruling. Take or drop them; either way the builder
  answers for what lands, and a taken piece credits its author.
- assumption: the bucket command is the test. Measured at da40a17d:
  `python3 -m unittest discover -s ops/conductor/tests -p 'test_session*.py'`
  read Ran 34, FAILED (failures=46). Red first on the checked tests, then
  green with the same command, then `ops/bin/suites.sh`.

## Scope

Contract: `ops/conductor/sessions-lever.md` (13664232), whole. Plan:
`.xor/in/multi-agents/agentscient-dev-lane-multi-harness-integration-plan-2026-09-22.md`
sections 6 and 9. Examples: `ops/conductor/machine-lever.md`,
`ops/conductor/tests/test_handoff.py`,
`ops/conductor/instrument-conventions.md`.

Deliver: `ops/conductor/tools/sessions.py` (doctor, start, status,
attach, stop, export on the engine), `ops/conductor/tools/session_adapters/`
(`claude.py`, `framing.py`, `SOURCES.md` with the proof's MIT notice
verbatim and each adapted function beside its origin),
`ops/bin/conduct.sh`, `ops/conductor/team.default.json`,
`ops/conductor/placement/sessions.py.json`. Stdlib only; no Symfony,
no vendor. Never edit a test file; a test that looks wrong goes to the
XO with the row, the contract line and the reading. Adapted commits
carry `Source: /home/scientdb/projects/poc/multi-harness-proof@a944f31`.

Report to the XO at each push: branch, head, the bucket reading, CI.
