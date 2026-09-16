# S4 — lock-on-the-engine

Class 1b of the 2026-09-16 issues: state kept as a flat file with no transaction and no history. Planner record 20260916T085626Z-review-claude-30f3eb, Part 1 C1, Part 2 slice 7; threads T-6, T-39 (the wall half), T-65, T-71. Issue 2: the lock's per-target `by` and `at` hold the latest claimant only, so "three sessions claimed dev" cannot be read from the store. Measured 2026-09-13 (dispatch 20260913T105222Z-review-grok-00b782, finding 2): a concurrent `remove` and `add` lost a branch in 3 of 60 trials before the flock. Depends on S3 (the measure as a list) landing first.

## The mechanism

`deliverable.py` becomes an instrument on the state engine (`machine.py`, machine-lever.md; the handoff manager is the worked example):
- Machine `deliverable`, one subject per branch: places `named`, `lifted`; transitions `name` (create), `target` (actor `holder`, hold `keep`: only the session that named the branch sets its target, T-71), `lift` (`named -> lifted`, actor `holder-or-lapsed`, ttl the grant's day), `clear` (`any`, the owner's one-host verb). The instrument's own table `deliverable_targets(subject INTEGER, measure TEXT (JSON list), until TEXT, by TEXT, at TEXT)` keyed by the engine's subject id; `why` on the subject's holder note.
- History is the marking: `show --history [branch]` prints every move oldest first (`machine.py history deliverable <id>`), so every claimant is on record.
- `deliverable.json` becomes an export the lever writes after every move (atomic replace, the same shape as today: branches, why, by, at, targets), for the two readers that stay on the file: `matrix.py deliverable_lock()` (wall, T-39, moved by a wall session later) and `watchdog.py deliverable_lock()`. The placement file declares it: `{"placement": "migrated", "state": {"engine": "sqlite", "files": "deliverable.json, an export written after every move for the hook matrix (wall, T-39) and the watchdog; state is the deliverable machine in state.db"}}`; `FILE_BACKED` in `test_state_placement.py` shrinks by `deliverable.py` in the same commit.
- `onboard.py` reads `show` as before (S3's cheap show). A registry row `ops/conductor/registry/deliverable.py.json` joins the wire's conformance gate (docs/wire.md §Conformance: one hermetic refusal-provoking invocation).
- Reads (`show`, `done`) connect with `create=False`; a read never creates the store.

## Planted faults and the clean neighbour

Faults file `ops/conductor/tests/deliverable_faults.py` (S3's file, extended): M-no-history (a move written without its marking row; `claim-history` goes red), M-any-retargets (`target` actor `any`; `set-retargets-own-only` goes red), M-export-stale (the export not rewritten after `lift`; `export-matches-rows` goes red). Clean neighbour: the unmodified lever passes every row.

## Rows (ops/conductor/tests/test_deliverable.py; each executes the lever and asserts what it did)

- claim-history: `add lane/x` by session A, `set lane/x --measure ... --until ...` by A; `show --history lane/x` prints both moves with their agents and stamps, oldest first.
- concurrent-add-keeps-both: two `add` calls of two branches started together; `show` names both; `history` carries both creates (the 3-of-60 loss).
- set-retargets-own-only: A names lane/a with a target, B names lane/b; B `set lane/a --measure ...` refuses class `holder` naming A; A's target is unchanged.
- lift-by-holder: A `remove lane/a` moves it to lifted; `show` no longer names it; the export no longer names it.
- export-matches-rows: after every verb in the table, `deliverable.json` equals the projection of the rows (branches, targets by branch).
- read-never-creates: `show` on a host with no store prints `no lock` and creates none.
- wire-row: the registry row's invocation refuses on the wire (exit 2, one stderr line, class token, expected–found–needed, stdout empty).
Fixture: `World`, `LANE_CONF`, two `WF_AGENT` identities and two CLAUDE_CODE_SESSION_ID values, `run` with timeouts. Origin rows: issue 2; T-71; dispatch 20260913T105222Z-review-grok-00b782 finding 2.

## Not covered

`matrix.py`'s reader stays on the export until a wall session moves it (T-39; the Lead's wall queue); `watchdog.py`'s reader likewise until its own slice. Two hosts. The measure for the lock: `sh -c "git -C /home/scientdb/projects/uscient/agentscient fetch -q origin; git -C /home/scientdb/projects/uscient/agentscient show origin/dev:ops/conductor/tests/test_deliverable.py | grep -q claim-history && echo s4=on-dev || echo s4=short"`, until `s4=on-dev`.

## Scope

author-tests for S4 lock-on-the-engine. Subject: ops/conductor/tools/deliverable.py as a machine on ops/conductor/tools/machine.py (state.db), with deliverable.json kept as an export. Write rows by id in ops/conductor/tests/test_deliverable.py: claim-history, concurrent-add-keeps-both, set-retargets-own-only, lift-by-holder, export-matches-rows, read-never-creates, wire-row; extend ops/conductor/tests/deliverable_faults.py with M-no-history, M-any-retargets, M-export-stale. Behaviour: one subject per branch, places named/lifted, target set only by the holder, history from the marking via show --history, the export rewritten after every move. Kit from the repository root; run with timeouts; each case executes the lever and asserts what it did; prove red at the ref. The brief in --input carries the rest.

## The rules every build follows

- No producer owns two consecutive artifacts: the tests come from a dispatched Grok `author-tests` job, Codex `check-tests` reads them, the builder codes against the sealed tests, Grok `adversarial-review` and Codex `security-audit` read the pushed head. The builder never edits a test to reach green; a test that must change is a new tests commit by the test author, reviewed again.
- Every test case executes the subject and asserts what it did (the rule the wall session adds to docs/tests.md on 2026-09-16); a row that pins a count the contract does not own is a finding.
- Reviews and audits are dispatched against the pushed head, never an unpushed worktree commit.
- Every subprocess in a test goes through `ops.testkit.run` with a timeout; the world is hermetic and ambient is named; a fake is planted through the registry.
- The red is pasted, never inferred: `FAIL:` with an `AssertionError` at the base sha, `Ran N tests ... OK` at the head, the same discover command, both in the code commit's body with the base sha (the tdd skill).
- Every commit carries `Source:` and `Co-Authored-By:`; every paragraph that claims carries its reading (the claim skill); the second producer's absence is said where the owner's hand grant stands in.
- Draft PR into dev, body per CONTRIB.md, `## Proof` naming corpus rows under `ops/conductor/handoff/probes/`; the ready flip waits for a closed `security-audit` record on codex `gpt-daybreak-blue-latest` at the head sha with every finding disposed (CONTRIB.md ready table, owner's rule of 2026-09-16); a push after the audit voids it.
- A CHANGES verdict is a stop, ruled on by agentscient-0d (the planner), never by the builder; report each PR to agentscient-11 by message with its number, head, readings and what was not measured.

## The pipeline, as commands

1. `python3 ops/conductor/tools/deliverable.py add lane/session-20260916-<x> --why '<the owner's words, dated>' --measure '<see the brief>' --until '<see the brief>'`, then `git worktree add ../wt/ag-session-20260916-<x> -b lane/session-20260916-<x> origin/dev`; `hand.py declare` at the owner's relayed word, `HAND_GRANT=<id>` leading every write.
2. Write the `## Scope` text below to a file under 1024 bytes (SCOPE_CAP in ops/lane.conf) and pass this brief whole as `--input`: from the worktree, `ops/bin/dispatch.sh --job author-tests --harness grok --scope-file <scope> --input <brief> --branch lane/session-20260916-<x>` (dispatch-by-hand: an unscoped open grant, from the branch's own worktree, no --model or --effort, every path spelled out). `record-target` refuses from the main checkout (issue 7); dispatch from the worktree.
3. Land the closed record: `python3 ops/conductor/tools/land.py <record id>`; push the branch.
4. `ops/bin/dispatch.sh --job check-tests --harness codex ...` at the pushed head; import its findings (`findings.py import`) and dispose each with a citation before coding.
5. Code by hand under the grant with the tests sealed; `ruff check` the changed files; commit with the red and green lines; push.
6. `--job adversarial-review --harness grok` and `--job security-audit --harness codex` at the pushed head; dispose every finding; correction rounds through `correction.py`.
7. `gh pr create --draft --base dev` with the body per CONTRIB.md; corpus rows for the change under `ops/conductor/handoff/probes/probes-2026-09-16-<slice>.jsonl`, named under `## Proof`.
