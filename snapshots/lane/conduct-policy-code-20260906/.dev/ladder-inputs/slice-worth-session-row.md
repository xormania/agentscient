# Slice worth-session-row (S)

Plan 2c8a8f slice 4. Ledger 48 / R6. Own PR. Do not add SESSION_* ceiling keys here.

## Contract

1. `--claude-dir` has no argparse default. Resolution: flag, else `laneconf.get("CLAUDE_DIR")`; missing key: exit 2, class `conf-key`. Relative CLAUDE_DIR is against `Path.home()`. Tracked `CLAUDE_DIR='.claude/projects'`.
2. Waste session row for each ranked Claude session: `turns`, `avg_context`, `refusals` with the same definitions as session-budget (assistant usage rows; mean of input+cache_creation+cache_read; tool-result deny markers). Unreadable transcript: those three print `unrecorded`, never 0.
3. Keep dispatch rows, windowing, cache-churn 20x, JSON/plain parity.

Files: `ops/lane.conf` `ops/devlane/telemetry/worth.py` `ops/process/worth.md`. Tests: `ops/devlane/telemetry/tests/test_worth.py` and bdd worth as named in 2c8a8f.

slice	worth-session-row	S
bucket	worth-session-row	S	ops/lane.conf ops/devlane/telemetry/worth.py ops/process/worth.md
