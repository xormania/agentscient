# Slice false-positive-rows (S)

Plan 20260904T172250Z-plan-grok-2c8a8f slice 2. Ledger 49 / R4. Own PR.

## Contract

1. **hand-write.** A code-root path is a write only when the statement's verb writes that path. A lane path as data written elsewhere, or as a read argument, is not a write. `python3 -c "open('AGENTS.md','w').write('x')"` stays refused.
2. **direct-launch.** Refuse when the command word is `launch.py`. Do not refuse `pgrep -fc launch.py`, `pgrep -f launch.py`, `pgrep -fc ops/devlane/dispatch/launch.py`.
3. **clipped-sweep.** Keep `| head`. Skip `| tail`. Corpus BLOCK row with `| tail -10` becomes PASS.

Files: `ops/devlane/hooks/claude/matrix.py` `ops/devlane/hooks/claude/unsafe-command.py`. Tests in `ops/devlane/hooks/tests/test_matrix.py` and `test_unsafe_command.py` / `corpus.py` as named in plan 2c8a8f.

Measured demand: Fable session ~70 hook refusals, clipped-sweep 25 of them, each a full-context turn plus retry.

slice	false-positive-rows	S
bucket	false-positive-rows	S	ops/devlane/hooks/claude/matrix.py ops/devlane/hooks/claude/unsafe-command.py
