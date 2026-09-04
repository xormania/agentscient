# Slice onboard-running (S)

Measured 2026-09-04 onboard `running=` named `7f3024` and `31155a` (no record.json) and `248a65`, `46a1db`, `9e58d9` (died, invalid) as if live. Only `launched` with a live pid, or an equivalent live launcher state, is running.

## Contract

`dispatches: running=` lists ids only when the record status is `launched`, `state.json` names a positive integer pid for which signal zero succeeds, and the `exit` file is absent. Boolean and non-integer pids are malformed, not live. This observes PID existence, not worker identity or progress; unreaped zombies and PID reuse remain limitations of this observation. A `died` or `closed` record is not running. A job directory without `record.json` is not running; it may be named elsewhere as unrecorded, never in `running=`. Absence of a pid file plus status launched is not inferred live.

Files: `ops/conductor/tools/onboard.py` (and any helper it uses for the dispatches line). Tests: `ops/conductor/tests/test_onboard_lever.py`.

slice	onboard-running	S
bucket	onboard-running	S	ops/conductor/tools/onboard.py
