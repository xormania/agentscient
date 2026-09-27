# Brief: the matrix guard admits the launcher's read verbs (LD-1)

Lane defect LD-1 (`ops/conductor/handoff/lane-defects.md`): `ops/README.md`
documents the launcher verb `wait ID` as the way to wait for a dispatch
to close, and the matrix guard `ops/devlane/hooks/claude/matrix.py`
refuses every direct launcher call as `direct-launch`. A documented verb
is unusable by a session. The `direct-launch` row exists so the lane conf
applies at the mint; a read of an already-minted record launches nothing.

## The change, exactly

In `ops/devlane/hooks/claude/matrix.py` only:

1. After the line `DRIVER = "ladder.sh"` add a module constant with a
   comment:

       # Launcher verbs that launch nothing: they read a record the dispatcher
       # already minted. ops/README.md documents the wait verb; the lane conf
       # the direct-launch row protects is applied at the mint, not at a read.
       LAUNCHER_READ_VERBS = ("status", "wait", "brief")

2. In `dispatch_args(tokens)`, after `flags = {"input": [], "command": name}`,
   record the launcher verb when the token right after the launcher
   program is not a flag:

       if kind == "launcher" and program + 1 < len(tokens) and not tokens[program + 1].startswith("-"):
           flags["verb"] = tokens[program + 1]

3. In `check_dispatch`, at the top of the `if kind == "launcher":` branch,
   before the grant check, allow those verbs:

       if flags.get("verb") in LAUNCHER_READ_VERBS:
           return None

Nothing else changes. The three existing direct-launch tests in
`ops/devlane/hooks/tests/test_matrix.py` must still pass: a bare launcher
call, an absolute path to it, `--job verify` after it, and a leading
environment assignment are all still refused, because none of them
carries a read verb as the first token after the program.

## Verification, required

- `python3 -m unittest discover -s ops/devlane/hooks/tests -p test_matrix.py`
  passes.
- `ruff check ops/devlane/hooks/claude/matrix.py` is clean.
- Report in `note` the exact hook decision for these two inputs, using the
  suite's own `run_bash` helper or an equivalent direct invocation of the
  hook with a Bash tool payload: `ops/devlane/dispatch/launch.py wait
  20260101T000000Z-x-y-000000` is allowed; `ops/devlane/dispatch/launch.py
  --job verify` is refused `direct-launch`.

Commit with trailers per AGENTS.md. Do not edit tests; a separate test
author adds the regression cases.

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the launcher's contract;
  the hook suite needs neither.
- assumption: at this ref the hook refuses `launch.py wait ID` —
  measured 2026-09-10 in the conductor session: `direct-launch: expected
  every stage launched through ops/bin/dispatch.sh …; found launch.py run
  directly`.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
