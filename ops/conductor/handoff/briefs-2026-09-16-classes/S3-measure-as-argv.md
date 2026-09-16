# S3 — measure-as-argv, readings on demand

Class 4 of the 2026-09-16 issues: a command stored as one string and re-tokenized by a tokenizer other than the shell that would run it. Planner record 20260916T085626Z-review-claude-30f3eb, Part 1 C4, Part 2 slice 3. Issue 3: `deliverable.py` runs `shlex.split(target["measure"])` with no shell (`reading()`), so a measure written for `sh -c "..."` with quotes inside its quotes tokenizes into an argv the author never wrote; lane/session-20260915-g's measure read `unreachable (exit 1)` and `met` on different `show` calls. Measured 2026-09-16 in session a6b096a2 at dev 46639344: the onboard brief's lock read timed out at 5 s and again at 20 s (`lock: UNREACHABLE`), and `deliverable.py show` timed out at 30 s, because bare `show` runs every session's measure in series (fourteen branches in the lock; one measure runs the whole testkit suite from a git archive).

## The mechanism

- `--measure` takes a JSON list, the argv (`["python3", "-c", "..."]`, `["sh", "-c", "..."]`): stored as a list, run as a list through `instrument.run` with no tokenizer between. A bare string on `add` or `set` refuses class `arguments` naming the list shape. A target already stored as a string (every live target today) is read as legacy: run through `shlex.split` as now, and its target line says `legacy-string` so the reading is never mistaken for an argv reading; sessions re-add their targets as lists when they choose.
- Bare `show` prints the lock and one line per target without running any measure: `target <branch>: until <text>; reading not run; show <branch> reads it`. `show <branch>` runs that one measure and prints the line the done-gate row accepts (`target <branch>: until ...; reading ...; met|short`). `done <branch>` runs its one measure as now. `remove` runs only the measures of the branches it lifts, as now.
- `onboard.py`'s `lock_lines` keeps calling `show` (now cheap) and its `bounded_read` timeouts stand; the reading it prints per target is `not run` and the session's own branch is read by the session (`deliverable.py show <branch>`), which the deliverable skill says.
- The deliverable skill and the refused skill (`done-gate` row) say the two shapes: the list form of `--measure`, and `show <branch>` for the reading.

## Planted faults and the clean neighbour

Faults file `ops/conductor/tests/deliverable_faults.py`: M-string-tokenizer (a list measure joined and re-split before running; `measure-is-argv` goes red on a measure carrying a quoted `"$X"`), M-show-runs-all (bare `show` runs every measure; `show-runs-nothing` goes red on a sleeping measure), M-string-accepted (a string measure accepted on `add`; `string-refuses` goes red). Clean neighbour: the unmodified lever passes every row.

## Rows (ops/conductor/tests/test_deliverable.py, a case table by id; each executes the lever and asserts what it did)

- measure-is-argv: `add lane/x --measure '["sh","-c","printf \"%s\" \"$X\""]' --until ...` with `X` planted in the env; `show lane/x` twice prints the same reading, the literal the shell produced.
- string-refuses: `add lane/x --measure 'sh -c "echo hi"' --until hi` exits 2 with one stderr line, class `arguments`, naming the JSON list shape; stdout empty.
- legacy-string-reads: a lock file planted with a string measure (today's shape); `show lane/x` prints its reading with `legacy-string` on the line; `done lane/x` still reads it.
- show-runs-nothing: a target whose measure sleeps 20 s; bare `show` returns under 2 s and prints `reading not run` for it.
- show-branch-reads: the same lock; `show lane/x` runs the measure and prints `met` or `short`.
- done-runs-one: two targets, one sleeping; `done lane/y` returns under 2 s with its own reading.
- onboard-prints-lock: `onboard.py` on a lock with a sleeping measure prints `lock:` with the branches, no `UNREACHABLE`, under its 5 s read.
Fixture: `World`, `LANE_CONF` planted, `WF_AGENT` on writes only, `run` with timeouts; a scratch git repository only where onboard needs one. Origin rows: issue 3 of the 2026-09-16 issues report; onboard's LD-48 retry.

## Not covered

The reason one legacy string read differently on two calls is not measured (the shape is removed rather than explained); onboard's own timeouts stay at 5 s and 20 s. The measure for the lock: `sh -c "git -C /home/scientdb/projects/uscient/agentscient fetch -q origin; git -C /home/scientdb/projects/uscient/agentscient show origin/dev:ops/conductor/tests/test_deliverable.py | grep -q measure-is-argv && echo s3=on-dev || echo s3=short"`, until `s3=on-dev`.

## Scope

author-tests for S3 measure-as-argv. Subject: ops/conductor/tools/deliverable.py (add, set, show, done) and ops/conductor/tools/onboard.py's lock_lines. Write rows by id in ops/conductor/tests/test_deliverable.py: measure-is-argv, string-refuses, legacy-string-reads, show-runs-nothing, show-branch-reads, done-runs-one; in ops/conductor/tests/test_onboard_lever.py: onboard-prints-lock; and ops/conductor/tests/deliverable_faults.py with mutants M-string-tokenizer, M-show-runs-all, M-string-accepted. Behaviour: --measure is a JSON list run as argv with no tokenizer; a string refuses `arguments` on add/set; a stored string reads as legacy-string; bare show runs no measure; show BRANCH and done BRANCH run one. Kit from the repository root; run with timeouts; each case executes the lever and asserts what it did; prove red at the ref. The brief in --input carries the rest.

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
