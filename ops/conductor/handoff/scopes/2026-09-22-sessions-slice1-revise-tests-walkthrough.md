# Input: revise the tests for managed sessions, slice 1 (A-483)

Readings taken 2026-09-22 by the XO (Claude Opus 5.5) against
lane/session-20260922-69 at e6511aa4 and this host.

## First-run walkthrough

- assumption: the findings to fix are in the tree. Measured: the record
  `.dev/records/dispatches/20260922T215604Z-review-codex-f6777b.json` at
  e6511aa4 carries 26 findings in `result.envelope.findings` (p1 3, p2 22,
  p3 1), each a quotation pair with a `where`, a `claim` and a
  `reproduce`. Its `where` paths point into that job's `in/` directory;
  the same files are `ops/conductor/tests/test_sessions.py`,
  `ops/conductor/tests/test_session_adapters.py`,
  `ops/conductor/tests/fakes/session_harness.py` and
  `ops/conductor/tests/fakes/session_tmux.py`.
- assumption: no implementation exists. Measured at e6511aa4:
  `ops/conductor/tools/sessions.py`, `ops/conductor/tools/session_adapters`
  and `ops/bin/conduct.sh` are all absent. Every row stays red; a red
  must fail on its own assertion, never on collection, import or setup.
- assumption: a tmux socket under the world root fits. Refusal: the
  host refuses a unix socket path of 108 bytes or more ("AF_UNIX path too
  long", measured), and a dispatch snapshot root alone is 94 bytes
  (measured on record 20260922T215604Z-review-codex-f6777b). That is p1
  test_sessions.py:394. Put the private tmux socket in a short directory
  the world owns and assert its path is under 108 bytes before use.
- assumption: the suite may watch the operator's home for writes.
  Refusal: p1 test_sessions.py:61. The world owns HOME, the XDG roots
  and the state root; the rows assert on those, never on
  `Path.home()` of the operator (docs/tests.md rule 4).
- assumption: `calibrate` can run now. Refusal: `ops/testkit/cases.py`
  `calibrate` anchors each mutant on the subject's text
  (`check_anchors`), and the subject does not exist. Declare the gap in
  each table (the faults file follows the implementation) instead of a
  mutants file that anchors on nothing.
- assumption: the fakes may call subprocess directly. Refusal: four
  p2s (session_harness.py:98, session_tmux.py:32, test_sessions.py:623
  and :637, test_session_adapters.py:145) cite docs/tests.md rule 5.
  Every subprocess goes through `ops.testkit.run` with a timeout; a
  child the test must own is a world-owned child.
- assumption: the runner workspace is the repository root. Measured
  (docs/tests.md, Reaching it): `from ops.testkit import World, run,
  refusal_wire`. The bucket command is
  `python3 -m unittest discover -s ops/conductor/tests -p 'test_session*.py'`;
  at da40a17d it read Ran 34, FAILED (failures=46).
- assumption: grok can claim A-483 through the store. Refusal: the
  launcher wires the acting coordination MCP for codex only
  (launch.py:639 `COORD_MCP_HARNESSES = ("codex",)`, measured by PT-23).
  Say in the note that the claim was not possible; the XO settles the
  store from the record.

# Scope

Revise the four files above so that every finding in the record is
fixed, or answered in the note with the contract line that shows it is
wrong. The three p1s (test_sessions.py:61, :394, :572) are fixed; none
is answered away. For :572 the export row asserts that no
`credential_environment` value and no `coordination_capability` value
appears anywhere in the export, and that the pane capture, `launch.json`
and adapter diagnostics are present. Contract:
`ops/conductor/sessions-lever.md` in the tree. Do not read or write any
implementation. Keep every row an id with `origin: sessions-lever.md` or
the finding it answers (`origin: 20260922T215604Z-review-codex-f6777b#N`).
The note lists each finding number with `fixed` or `answered <why>`, and
the bucket reading.
