# Runtime consolidation: owner-selected item 4

Measured 2026-09-23T21:18:42.453517+00:00 against dev `a91284eccdc532e63ef8c9de84ee19776e64bf51`. This is an independent PR from the same dev base as #293; their code paths do not overlap. Owner explicitly requested two PRs. Hand grant 2; one producer (Codex), independent test author and external reviewer absent. Exact model identifier is not exposed in this session.

## Change

- One `mcp_transport.py` owns framing, draining, decode errors, envelope validation, notifications, metadata, negotiation and ping. Both MCP entrypoints call it. Server identity and strict/permissive initialize policy are explicit adapter inputs; capability checks, domain routing, error shapes and coordination response limits remain adapter-owned.
- One `DispatchRecord` interpretation is used by monitor, watchdog and lane reads. It owns normalized result/envelope/changed-path fields, phase, recorded outcome and metrics. Existing acquisition limits, symlink/FIFO defenses, cache behavior, process identity policies and alert state remain intact.
- Discovery implementation identity includes both extracted dependencies. The new regression fails when either file is omitted from the manifest and passes after inclusion. The fixed-path declarations are updated. No claim is made that the separately specified trusted boot-loader mechanism is implemented by this change.
- Staged tools include their new dependencies. The modules declare no durable state and no domain authority. The owning contract is `ops/conductor/runtime-observation-contract.md`.

## Measured tests

| Suite | Before | After | Result |
|---|---:|---:|---|
| MCP (`test_*mcp*.py`) | 93 | 91 | pass |
| Monitor (`test_monitor*.py`) | 73 | 73 | pass |
| Watchdog (`test_watchdog*.py`) | 99 | 99 | pass |
| Instrument | 57 | 57 | pass |
| State placement | 15 | 15 | pass |

MCP count includes six shared transport tests and one new dependency-fingerprint regression. Nine redundant endpoint tests are retired; no lifecycle integration test is removed. The remaining lane handshake runs once instead of repeating the catalogue assertions for every protocol version. Protocol negotiation now runs at the shared boundary. This PR reduces the required-suite count by two (3,729 → expected 3,727); together with #293 the reduction is 170 (expected 3,559). The runtime extraction is intentionally narrower than a broad lifecycle redesign.

Commands: `python3 -m unittest discover -s ops/conductor/tests -p PATTERN` for each table row; `python3 -m ruff check .`; `python3 ops/devlane/workflow/checks/testkit_ratchet.py`; `python3 ops/conductor/tools/laneconf.py literals`; `git diff --check`. The local toolchain lacks Rust/PHP/CUE/tmux; full CI is required before ready.

Initial monitor verification caught two staged copies missing the new dependency. After updating their sibling list, both cases and the full 73-test monitor suite pass.

## Planted faults

Each named replacement was applied to the shared implementation, tested with the listed acceptance module/case, and restored. All ten faults are detected; healthy runs pass. The discovery fingerprint regression was separately measured red for both omitted dependency files, then green with the five-file manifest.

| Fault | Detector | Result |
|---|---|---|
| accept nonfinite JSON | `test_mcp_transport` | detected |
| do not drain oversized frame | `test_mcp_transport` | detected |
| dispatch notifications | `test_mcp_transport` | detected |
| leak metadata into domain | `test_mcp_transport` | detected |
| ignore strict initialize policy | `test_mcp_transport` | detected |
| ignore tripped envelope | `test_monitor.DispatchLifecycle.test_noop_versus_completion_and_invalid_envelope` | detected |
| misclassify write no-op | `test_monitor.DispatchLifecycle.test_noop_versus_completion_and_invalid_envelope` | detected |
| forget terminal died status | `test_watchdog.ClosedRecords.test_died_is_closed_and_reported_with_report_existing` | detected |
| ignore exit marker | `test_watchdog.Settling` | detected |
| wrong changed-path count | `test_watchdog.ClosedRecords.test_closed_ok_empty_changed_with_report_existing` | detected |

## Retired endpoint cases

Protocol mechanics move to `test_mcp_transport.McpTransport`; exact endpoint identity, catalogues, hints, routing, refusals, metadata integration, capability checks, response bounds and read-only evidence remain in the endpoint suites. Presence-only assertions are superseded by real CLI/MCP execution and placement closure. Unknown-method tests remain on both adapters because routing owns that outcome.

- `test_lane_mcp.py:TestLaneMcpPresence.test_the_tool_file_is_present`
- `test_coordination_mcp.py:CoordinationMcpPresence.test_the_tool_file_is_present`
- `test_coordination_mcp.py:CoordinationMcpTransport.test_a_clean_initialize_still_negotiates`
- `test_coordination_mcp.py:CoordinationMcpTransport.test_a_notification_is_answered_with_silence`
- `test_coordination_mcp.py:CoordinationMcpTransport.test_a_protocol_version_that_is_not_a_string_is_invalid_params`
- `test_coordination_mcp.py:CoordinationMcpTransport.test_an_oversized_line_is_drained_and_the_next_line_still_answers`
- `test_coordination_mcp.py:CoordinationMcpTransport.test_an_unsupported_protocol_falls_back_to_the_newest_supported`
- `test_coordination_mcp.py:CoordinationMcpTransport.test_every_declared_protocol_is_accepted`
- `test_coordination_mcp.py:CoordinationMcpTransport.test_ping_carrying_extra_members_still_answers`
