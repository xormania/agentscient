# Slice dispatch-agent (S)

Measured 2026-09-04: `run-reaudit.sh` exported `WF_AGENT='Grok 4.6 <noreply@x.ai>'` and the launch record stamped Fable (`WF_AGENT_DEFAULT`). `dispatch.sh` sets `agent=$WF_AGENT_DEFAULT` and only `--agent` overrides.

## Contract

Identity for the launched argv: `--agent` if passed; else `WF_AGENT` when it matches `Name <address>`; else `WF_AGENT_DEFAULT`. Do not let a local conf `WF_AGENT_DEFAULT` be required for Grok-led sessions.

Files: `ops/conductor/tools/dispatch.sh`. Tests: `ops/conductor/tests/test_dispatch_wrapper.py`.

slice	dispatch-agent	S
bucket	dispatch-agent	S	ops/conductor/tools/dispatch.sh
