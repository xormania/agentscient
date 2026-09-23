# Input: author-tests for managed sessions, slice 1

Contract: `ops/conductor/sessions-lever.md` at 13664232
(lane/session-20260922-af333fa2; F3 and F4 ruled there), merged into lane/session-20260922-69.
Readings taken 2026-09-22 by the XO (Claude Opus 5.5) against 985e28af
and this host.

## First-run walkthrough

- assumption: no implementation exists to read, so the tests are written
  from the contract alone. Measured: `git cat-file -e` at 985e28af finds
  `ops/conductor/tools/sessions.py`, `ops/conductor/tools/session_adapters`,
  `ops/bin/conduct.sh` and `ops/conductor/team.default.json` all absent.
  Every row is red until the implement stage.
- assumption: the inputs the scope names are in the snapshot. Measured
  present at 985e28af: `ops/conductor/tests/test_handoff.py`,
  `ops/conductor/machine-lever.md`,
  `ops/conductor/instrument-conventions.md`, `ops/testkit/fakes.py`,
  `ops/devlane/hooks/profiles.py`, `ops/conductor/placement/`.
- assumption: the fake harness is planted with a script through the kit.
  Measured: `ops/testkit/fakes.py:48` has `plant(self, name, *, ...,
  script: str | None = None)`.
- assumption: the profile path the contract names exists. Measured:
  `ops/devlane/hooks/profiles.py:530` accepts `prepare-interactive`,
  `run-interactive` and `check`; the profile mints its own
  `coordination_capability` (`profiles.py:158`) and projects it as
  `COORDINATION_CAPABILITY` (`profiles.py:354`), so the fake harness binds
  with the profile's credential and never with the operator's.
- assumption: `guard.sh` is written into the profile, not tracked.
  Measured: `git ls-files` lists no `guard.sh`; `profiles.py` names it
  once. Tests read it from the prepared profile directory.
- assumption: the first bind on an empty store takes lead (the cold-start
  row). Measured: `coordination.py` `core_bind` computes `bootstrap` from
  `COUNT(*) FROM participants == 0`. A bind also refuses `session`
  without a session id in the environment, so the fake sets one.
- assumption: the isolated home is the world's. Refusal: a test that
  reads the operator's `~/.local/state/agentscient`, `~/.claude` or live
  coordination store is a finding. The world owns HOME, the XDG roots and
  the state root (`docs/tests.md`, World).
- assumption: there is no network. Measured by the contract ("No live
  harness runs in the suite"). A row that needs `claude`, `codex` or
  `grok` for real is out of scope and is written as a declared gap.
- assumption: tmux may be absent in the runner's sandbox. The host has
  tmux 3.4 and bwrap at `/usr/bin`, measured; the sandbox is not
  measured. Refusal: tmux rows skip with the reason when
  `command -v tmux` fails in the world, and the job note says how many
  rows skipped.
- assumption: the .git is read-only and the worker cannot push.
  Refusal: tests build any repository or worktree they need under the
  world's temp root, never in the snapshot's `.git`; the worker commits
  locally and the conductor lands.
- assumption: the runner workspace is the repository root, as
  `ops/bin/suites.sh` and CI use it. Measured (`docs/tests.md`, Reaching
  it): `from ops.testkit import World, run, refusal_wire`, with no
  `sys.path` insert and no `PYTHONPATH`.
- assumption: `claude` accepts a launch id. Measured: `claude --help` on
  this host lists `--session-id` (1 hit). The adapter's `argv` row
  asserts the launch id is carried; it does not run `claude`.

# Scope

The committed scope, `ops/conductor/handoff/scopes/2026-09-22-sessions-slice1-author-tests.md` at 13664232 (unchanged since 3daebdbd), carried here verbatim because the dispatched scope is cut to the 1024-byte cap:

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
