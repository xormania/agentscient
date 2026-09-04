# Slice skeptic-write (S)

Ledger 51. Unblocks every check-tests stage (session-budget, five parked ladders). Own PR. Do not feed PLAN.md to the driver; this file is `[PLAN]`.

## First-run walkthrough

- assumption: Codex check-tests runs `--sandbox read-only` — measured `launch.py` `_harness_meta` lines 259–261.
- assumption: `writable_roots` is added only when sandbox is `workspace-write` — measured `launch.py` 421–422. Read-only check-tests therefore cannot write `{out}/SKEPTIC.md`. Records `bb30da` and `bb8ddb` note apply_patch refused; 63 tests errored in setUp with no writable tempdir.
- assumption: `launch.py wait` prints `poll … running` on stderr every interval, then on close prints stdout `… closed … envelope=invalid` and exits 1 — measured `launch.py` `_wait` 1594–1612.
- assumption: the driver classifies wait exit nonzero as `wall` when "running" appears in combined stdout/stderr — measured `ladder.py` `await_result` 806–811. Poll lines contain "running", so a closed invalid envelope is labelled wall. Job cap was 1800s; stop at ~340s was the job finishing, not the wall.
- assumption: pytest absent; frozen command is unittest discover.

## Contract

1. **Writable deliverable dir.** A Codex job whose deliverable is a file under the job `out/` directory must pass `out/` in `sandbox_workspace_write.writable_roots` even when the snapshot sandbox is `read-only`. The snapshot (cwd) stays non-writable. `TMPDIR` for that process is a directory created under `out/` before exec (e.g. `out/tmp`), so unittest `setUp` temp files work. Do not switch read-role Codex to `workspace-write` on the snapshot.

2. **Wait reason.** If `launch.py wait` stdout contains a closed/died line with `envelope=`, the driver stop reason is `envelope` (or `died`/`tripped` from that line), never `wall`, even if stderr poll lines contain `running`. `wall` is only when wait exits because elapsed >= timeout while the record is still not closed. Pin: a fixture of poll-running stderr plus stdout `closed … envelope=invalid` is reason envelope, not wall.

3. **No third skeptic of this slice.** This slice repairs check-tests itself. Tests and implement only; audits after land. Do not require a green check-tests stage to land this slice.

Unblocks: parked ladders and session-budget resume. Risk: launcher argv and ladder wait (touches dispatcher-adjacent launch.py and the driver). Files: `ops/devlane/dispatch/launch.py` `ops/conductor/tools/ladder.py`. Lands green alone: tests plant argv and wait fixtures.

## Tests

- `ops/devlane/dispatch/tests/` (or existing launch tests): Codex read-role argv for check-tests includes writable_roots of the job out dir; TMPDIR points under out; snapshot sandbox remains read-only.
- `ops/conductor/tests/test_ladder_lever.py`: wait combined output with poll `running` lines and a closed `envelope=invalid` stdout line stops as `envelope`, not `wall`.

Frozen command: `python3 -m unittest discover -s ops/devlane/dispatch/tests -p 'test_*.py' && python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever.py`

## Calibration

| slice | declared | tests | check-tests | code | security | adversarial |
|---|---|---|---|---|---|---|
| skeptic-write | S | 9 | skip | 4 | 8 | 8 |

slice	skeptic-write	S
bucket	skeptic-write	S	ops/devlane/dispatch/launch.py ops/conductor/tools/ladder.py
