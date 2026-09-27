# Slice session-budget (S)

Ledger 49(a). The session is stopped by the machinery. One S bucket, own PR. Ladder `[PLAN]` is this file, not `PLAN.md`.

## First-run walkthrough

- assumption: this job's isolated grok home has no `.claude` and no lane state — measured in the parent plan at 2026-09-04T17:23Z (`ls "$HOME/.claude"` empty).
- assumption: no network — refusal: the author-tests and implement prompts forbid it; plant transcripts in the test tempdir, do not fetch a hook schema.
- assumption: Codex implement meets a read-only `.git` — measured: `launch.py` `_commit_for_harness`; this grok snapshot's index is writable, which is not the implement sandbox.
- assumption: `pytest` is not on PATH — measured `command -v pytest` missing; use `python3 -m unittest discover -s ops/devlane/hooks/tests -p test_matrix.py`.
- assumption: PreToolUse may omit `transcript_path` — refusal: the row denies could not look; tests plant both missing and present paths.
- assumption: ceiling integers are not in `ops/lane.conf` at the ref — measured `laneconf.py get SESSION_TURNS_CEILING` exit 2. Tracked values 100 / 200000 / 10 come from the churn analysis "The test"; missing keys refuse, no defaults.

Trace: grok author-tests writes `test_matrix.py` methods from this contract without reading `matrix.py`. Isolated home cannot open operator transcripts. Prove red: empty stdout on each `session-budget` assertion against `1ac20fded9fd8335176bf025bba4808b2d0347b9`. Codex check-tests is read-only. Codex implement edits only `ops/lane.conf` and `ops/devlane/hooks/claude/matrix.py`. If implement defaults a ceiling in Python: refuse. If it reads `~/.claude` instead of `payload["transcript_path"]`: refuse. If it grant-escapes this row: refuse. CI then runs `suites.sh` and `laneconf.py closure` on a self-hosted runner whose HOME is not this grok home.

## Contract

On every parsed PreToolUse payload, first: read `transcript_path`; read `SESSION_TURNS_CEILING`, `SESSION_AVG_CONTEXT_CEILING`, `SESSION_REFUSALS_CEILING` from `ops/lane.conf` with no defaults; compute turns, average context, refusals this session from that JSONL (assistant `usage` rows; mean of input+cache_creation+cache_read; tool-result deny markers `[matrix:`, `[clipped-sweep]`, `[clipped-runner]`, `[unguarded-replace]`, `permissionDecision": "deny"`). Past a ceiling, deny class `session-budget` on that call and every later tool, including Write: expected the session under the named ceiling; found the measured figure; needed close the session with the hand-off. Missing or unreadable transcript: could not look. Missing key: conf-key. No grant escape. Runs before dispatch rows; `dispatch-by-hand` stays last among dispatch rows.

Unblocks: a runaway conductor cannot keep calling tools. Risk: a contract (matrix hook): its own slice. Edges: hook → transcript JSONL; hook → the three conf keys. Depends on: nothing in this batch. Lands green alone: tests plant conf and transcript. Own PR.

Implement files: `ops/lane.conf` `ops/devlane/hooks/claude/matrix.py`

## Tests

`ops/devlane/hooks/tests/test_matrix.py` — new `test_session_budget_*` methods named in `PLAN.md`. Red at the ref because `decide()` never reads `transcript_path`. Helper attaches an under-ceiling transcript to existing payloads so later implement does not break allow methods.

## Calibration

| slice | declared | tests | check-tests | code | security | adversarial |
|---|---|---|---|---|---|---|
| session-budget | S | 9 | 8 | 4 | 8 | 8 |

slice	session-budget	S
bucket	session-budget	S	ops/lane.conf ops/devlane/hooks/claude/matrix.py
