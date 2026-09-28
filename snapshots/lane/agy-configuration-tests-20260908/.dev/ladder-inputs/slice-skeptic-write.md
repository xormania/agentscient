# Slice skeptic-write (S)

Ledger 51. Unblocks every check-tests stage (session-budget, five parked ladders). Own PR. Do not feed PLAN.md to the driver; this file is `[PLAN]`.

## First-run walkthrough

- historical evidence, before the current source: Codex check-tests ran `--sandbox read-only`; `writable_roots` was then added only for `workspace-write`. Records `bb30da` and `bb8ddb` note apply_patch refused, and 63 tests errored in `setUp` with no writable tempdir.
- measured current behavior: check-tests remains a read-role job, but fresh Codex check-tests is the scoped exception that selects `workspace-write`, adds the job `out/` as a writable root, strips snapshot Unix write bits before the attempt, and sets `TMPDIR` to a real, non-symlinked `out/tmp` (`launch.py` `_launch`, `_argv`, and `_run_attempt`). The mode-bit hardening is not claimed as a hostile-process security boundary; read-role settlement still requires `HEAD == ref_sha` and no residual snapshot paths.
- absence: live vendor containment proof of this current path has not run.
- assumption: `launch.py wait` prints `poll … running` on stderr every interval, then on close prints stdout `… closed … envelope=invalid` and exits 1 — measured `launch.py` `_wait` 1594–1612.
- assumption: the driver classifies wait exit nonzero as `wall` when "running" appears in combined stdout/stderr — measured `ladder.py` `await_result` 806–811. Poll lines contain "running", so a closed invalid envelope is labelled wall. Job cap was 1800s; stop at ~340s was the job finishing, not the wall.
- assumption: pytest absent; frozen command is unittest discover.

## Contract

1. **Codex check-tests exception (proposed for owner review).** Keep the job role `read`, but select the `workspace-write` sandbox label only for Codex check-tests, pass its job `out/` in `sandbox_workspace_write.writable_roots`, and create a real, non-symlinked `out/tmp` as `TMPDIR` before exec. Strip snapshot Unix write bits as hardening, without treating those bits alone as a hostile-process security boundary, and retain the post-attempt read-role checks that require the snapshot HEAD and worktree to be unchanged. Other Codex read jobs remain `read-only`; this does not promise generic file-output support for plan or adjudicate. Live vendor containment proof remains unrun.

2. **Wait reason.** If `launch.py wait` stdout contains a closed/died line with `envelope=`, the driver stop reason is `envelope` (or `died`/`tripped` from that line), never `wall`, even if stderr poll lines contain `running`. `wall` is only when wait exits because elapsed >= timeout while the record is still not closed. Pin: a fixture of poll-running stderr plus stdout `closed … envelope=invalid` is reason envelope, not wall.

3. **No third skeptic of this slice.** This slice repairs check-tests itself. Tests and implement only; audits after land. Do not require a green check-tests stage to land this slice.

Unblocks: parked ladders and session-budget resume. Risk: launcher argv and ladder wait (touches dispatcher-adjacent launch.py and the driver). Files: `ops/devlane/dispatch/launch.py` `ops/conductor/tools/ladder.py`. Proposed for owner review; this description does not ratify the mechanism or approve its tests.

## Tests

- `ops/devlane/dispatch/tests/` (or existing launch tests): Codex check-tests remains role `read`, uses the `workspace-write` sandbox label with only the job `out/` added as a writable root, uses a real non-symlinked `out/tmp` as `TMPDIR`, hardens snapshot modes, and is invalidated after the attempt if HEAD or the snapshot worktree changed. Other Codex read jobs remain `read-only`. This is the proposed coverage description, not a claim that the tests are approved or that live vendor containment passed.
- `ops/conductor/tests/test_ladder_lever.py`: wait combined output with poll `running` lines and a closed `envelope=invalid` stdout line stops as `envelope`, not `wall`.

Frozen command: `python3 -m unittest discover -s ops/devlane/dispatch/tests -p 'test_*.py' && python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever.py`

## Calibration

| slice | declared | tests | check-tests | code | security | adversarial |
|---|---|---|---|---|---|---|
| skeptic-write | S | 9 | skip | 4 | 8 | 8 |

slice	skeptic-write	S
bucket	skeptic-write	S	ops/devlane/dispatch/launch.py ops/conductor/tools/ladder.py
