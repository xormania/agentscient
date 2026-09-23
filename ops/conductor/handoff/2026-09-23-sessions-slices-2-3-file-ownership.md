# Slices 2 and 3: file ownership and dispatch shapes

Prepared by the XO (PT-21, Claude Opus 5.5) on 2026-09-23 at the Lead's order. Source: plan §7, §8, §9 and §11 (`.xor/in/multi-agents/agentscient-dev-lane-multi-harness-integration-plan-2026-09-22.md`), and slice 1's records. Contracts for both slices come first, written by the Fable 5.1 contract session with `ops/conductor/sessions-lever.md` as the template.

## The rule

Every file has exactly one owner. A builder never edits a file outside its column. When one slice needs a change in the other's file, the need is written into its contract as a requirement on the other owner's interface, and the change lands at integration. Tests stay with the code they test, but each slice writes its own test modules and fakes; no shared fake is edited by both.

## Owners

| Path | Owner | Why |
|---|---|---|
| `ops/conductor/tools/courier.py` | S2 | native delivery route (§7) |
| `ops/conductor/tools/session_adapters/codex.py`, `grok.py` (new) | S2 | the codex and grok adapters |
| `ops/conductor/tools/session_adapters/framing.py`, `claude.py`, `__init__.py` | S2 | submit, observe and ack on the existing adapters |
| `ops/conductor/tools/sessions.py` | S2 | owner input, status, attach, basic recover and stop, multiple same-harness members |
| `ops/conductor/tools/coordination.py` | S2 | additive tables: delivery attempts and send-request identity (§7) |
| `ops/conductor/tools/coordination_mcp.py` | S2 | coord_send idempotency and ack projections |
| `ops/conductor/tools/dispatch_actions.py` (new) | S3 | coord_launch, coord_status, coord_wait, coord_collect; launch intents; reconciliation (§8) |
| `ops/conductor/tools/dispatch_intents.py` (new) | S3 | the dispatch-intent table, created through the core's writer as c1a69a78 did for sessions; it does not edit coordination.py |
| `ops/conductor/tools/dispatch_mcp.py` (new) | S3 | the dispatch projection as its own module. The single registration line in coordination_mcp.py lands at integration and is written by S2's owner from S3's contract. |
| monitor and watchdog event routing (new module beside them) | S3 | event-driven follow-through (§8) |
| `ops/devlane/dispatch/launch.py`, `ops/devlane/hooks/profiles.py`, native and enforcement helpers | W | wall paths in matrix.py WALL_PATHS: correlation propagation, acting-MCP for claude and grok, owned cancellation, same-harness profile composition. One wall session in isolation serves both slices from a brief written from both contracts. |
| `ops/conductor/tools/dispatch.sh` | S3, unless it is in WALL_PATHS | check matrix.py before the start; if it is wall, it moves to W |
| `ops/conductor/tools/onboard.py`, role guidance, skills | S4 | not in slices 2 or 3 |
| test modules and fakes | | |
| `ops/conductor/tests/test_session_messages.py`, `test_courier_native.py`, `test_session_adapters_codex.py`, `test_session_adapters_grok.py` | S2 tests | |
| `ops/conductor/tests/fakes/session_*` (existing) | S2 tests | S3 must not touch them |
| `ops/conductor/tests/test_dispatch_actions.py`, `test_dispatch_mcp.py`, `fakes/dispatch_*` (new) | S3 tests | |
| `ops/devlane/dispatch/tests/test_launch_correlation.py` | W | tests stay with the wall code |

## The known coupling points, stated in advance

1. **The schema.** S2's tables go in coordination.py. S3's intent table is created by dispatch_intents.py through the core's writer. If the contract session judges that the intent table must live in coordination.py, S2 owns that edit too and S3 codes against the contract's table definition.
2. **The MCP registration line.** S3 builds dispatch_mcp.py standalone and tests it through its own entry. The single line that mounts it in coordination_mcp.py is an integration commit.
3. **The wall.** Both slices need wall changes. W starts when both contracts exist, from one brief, and lands first. Until W lands, each slice tests against a contract-verified fake of the launch or profile surface.
4. **The same-harness routing in slice 2** touches profiles.py (W) and sessions.py (S2). Split it in the contract so profiles.py composes and sessions.py selects.

## Order of work, per slice, in parallel from the contract commit

Tonight's serial wait of implementation on tests cost 118 minutes (contract 21:14:55, builder start 23:13:21). Next time:

1. Contract commit (Fable session). XO reads it against the code the same hour.
2. At that commit, in parallel:
   - author-tests job(s), one per test module, grok, each sized to finish well inside 3600 s;
   - the builder (Opus 5.5, by hand under a grant) starts implementation from the contract, not from the tests;
   - W starts on the wall brief.
3. check-tests (codex) at the author-tests head.
4. Integration on the slice branch: tests, code and W merged, then measured. Test-side causes go to a test fixer who is not the builder; code-side causes go to the builder.
5. Reviews grok and codex in parallel at the integrated head. One fix pass. The one audit at the fix-round head. Flip.

## Dispatch shapes

Every launch goes through the Dispatcher seat, with `--for A-n` (LD-116 and LD-120) and DISPATCH_TIMEOUT=3600. dev's jobs.json cap is 3600 since #270.

| Job | Harness | Role | Ref | Scope must name | Split |
|---|---|---|---|---|---|
| author-tests | grok (grok-4.7) | write | the slice branch at the contract commit | the contract path and its clauses by line, one test module, the fakes it may create, testkit rules 1–9, "withheld: implementation" | one job per module; tonight a single job at 30 minutes lost its work |
| check-tests | codex | read | the author-tests head | the contract, the test modules, the fixture-set rule | one per slice |
| adversarial-review | grok and codex | read | the integrated head | the contract, the full diff against origin/dev | two in parallel |
| security-audit | codex (MODEL_CODEX_SECURITY_AUDIT) | read | the fix-round head | the full diff | one per PR (CONTRIB.md:92) |

The grok envelope reads invalid (LD-122), and grok workers cannot claim in the store. Read grok findings from the record, and settle the assignment from the record.

## Assignments to draft when the contracts land

S2: author-tests per module (about 3), check-tests, implement (by hand), reviews ×2, audit.
S3: author-tests per module (about 2), check-tests, implement (by hand), reviews ×2, audit.
W: one wall brief, one audit.
