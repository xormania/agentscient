# S5 — wrapper-hermetic-store

Class 5 of the 2026-09-16 issues: a test guards a live host path instead of owning a hermetic world. Planner record 20260916T085626Z-review-claude-30f3eb, Part 1 C5, Part 2 slice 1. Issue 6, LD-69 on lane/session-20260916-d: `ops/conductor/tests/test_dispatch_wrapper.py` (`_WrapperFixture.setUp`) watches every root `_jobs_roots_to_guard()` returns, the host's `~/.local/state/agentscient/dispatch` among them, and `tearDown` asserts them unchanged with one tolerated shape (`^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$`, LD-16); the launcher's own `.launcher.XXXXXX` entries, minted by other sessions' dispatches, are not tolerated, so the suite reads failures=2/3/0 on identical trees while any session dispatches. `ops/conductor/tests/test_dispatch_wrapper_ld16.py` inherits the fixture and exercises the tolerance. Measured 2026-09-16 at dev 46639344: `grep -rl _jobs_roots_to_guard ops` lists exactly these two files.

## The mechanism

docs/tests.md rule 4: a world is hermetic by default; ambient is explicit and named. The host store is not the subject's to reach: the fixture already hands the wrapper `DISPATCH_JOBS=<world>/jobs` (`_WrapperFixture`, the env it builds), HOME and the XDG roots are the world's, and the launcher admits `DISPATCH_JOBS` (its live-target refusal). So:
- `_jobs_roots_to_guard()` and the host watch go; the fixture watches its own `jobs_root` under the world and asserts after each run that only the run's own record directory appeared there (the record id the wrapper printed), nothing else.
- Hermeticity is proved positively, once per suite: a row runs the wrapper with `DISPATCH_JOBS` unset and `HOME` the world's; the wrapper's jobs root resolves under the world's `XDG_STATE_HOME`, never under the host's home (the path printed by `--dry-run`, or the record's root). The host path is not in the environment, so it cannot be written; no watch of it is needed.
- `test_dispatch_wrapper_ld16.py` loses its purpose (the tolerance it exercised is gone): its rows move into the table as the two above, its origin (LD-16) kept on the rows; the file is retired only when the side-by-side record (`cases.py sidebyside`) shows the new rows catch every fault the old file caught.
- `live_store_guard.py` stays for the suites that still use it; a count of its remaining callers goes in the PR body as measured.

## Planted fault and the clean neighbour

The fault is planted in a copy of the wrapper (`ops/conductor/tools/dispatch.sh` is bash; the kit's `Mutant` edits a copy by anchor): M-ignore-jobs-env, the line that honours `DISPATCH_JOBS` removed, so the record lands under the world's `XDG_STATE_HOME` default instead of `jobs_root`; the row `record-lands-in-world-jobs` goes red. M-host-home, the wrapper reading `~` instead of `HOME`; `jobs-root-under-world-state` goes red (the row reads the dry-run path). Clean neighbour: the unmodified wrapper passes both. Calibration: with a second world minting `.launcher.XXXXXX` and a record-shaped directory under the world's jobs root during a run, the table stays green (the concurrent-dispatch case that failed on the host).

## Rows (ops/conductor/tests/test_dispatch_wrapper.py; each executes the wrapper and asserts what it did)

- record-lands-in-world-jobs: a wrapper run (existing fixture, `--dry-run` or a planted launcher) leaves exactly one new entry under `<world>/jobs`, the record id printed.
- jobs-root-under-world-state: with `DISPATCH_JOBS` unset, the jobs root the wrapper resolves is under the world's `XDG_STATE_HOME`; the host home path does not appear in the resolved argv or the record.
- concurrent-entry-not-ours: a `.launcher.abcdef` directory and a record-shaped directory planted under `<world>/jobs` by the test mid-run are reported by the fixture as not this run's, and the run's own assertion still passes (the LD-16 and LD-69 case, now inside the world).
- host-store-untouched-by-construction is not a row but the fixture's invariant, asserted in `setUp` on the environment the world hands the wrapper (no path under the host's home). The executing fault for the class rides `jobs-root-under-world-state`: M-host-home resolves the jobs root through `Path.home()`; the row runs the wrapper with `DISPATCH_JOBS` unset and `HOME` planted inside the world at a directory the test reads afterwards, and goes red when the record lands there (grok 20260916T094152Z-review-grok-e72972#6, partial by codex 20260916T095708Z-adjudicate-codex-c5aefc; today's executing neighbour at test_dispatch_wrapper.py:1206-1250 stays).
Every existing row of the table keeps its id; the fixture change is the only edit to them. Origin rows: LD-16, LD-69, issue 6.

## Not covered

Whether the other copier suites watch the host store (the planner did not measure it; the builder measures `grep -rl live_store_guard ops` and records the count). The measure for the lock: `sh -c "git fetch -q origin; git show origin/dev:ops/conductor/tests/test_dispatch_wrapper.py | rg -q _jobs_roots_to_guard && echo s5=short || echo s5=on-dev"`, until `s5=on-dev`. The lock runs a measure with its cwd at the repository root; a measure never names another checkout with `-C` (codex 20260916T094142Z-review-codex-995043#1, upheld by grok 20260916T095437Z-adjudicate-grok-8c207d); once S3 lands, the same command as a JSON list.

## Scope

author-tests for S5 wrapper-hermetic-store. Subject: the fixture of ops/conductor/tests/test_dispatch_wrapper.py and ops/conductor/tests/test_dispatch_wrapper_ld16.py against ops/conductor/tools/dispatch.sh. Write rows by id: record-lands-in-world-jobs, jobs-root-under-world-state, concurrent-entry-not-ours; the fixture asserts host-store-untouched-by-construction in setUp and watches only the world's jobs root, never a host path; a faults file dispatch_wrapper_faults.py with M-ignore-jobs-env and M-host-home on a copy of the wrapper. Keep every existing row id. Kit from the repository root; run with timeouts; each case executes the wrapper and asserts what it did; prove red at the ref on the fixture's host watch. The brief in --input carries the rest.

## The rules every build follows

- No producer owns two consecutive artifacts: the tests come from a dispatched Grok `author-tests` job, Codex `check-tests` reads them, the builder codes against the sealed tests, Grok `adversarial-review` and Codex `security-audit` read the pushed head. The builder never edits a test to reach green; a test that must change is a new tests commit by the test author, reviewed again.
- Every test case executes the subject and asserts what it did (pending in docs/tests.md: agentscient-e0's World PR from lane/session-20260916-g adds it, in these words relayed by agentscient-11 at 09:59Z on 2026-09-16: "A case executes the subject's behaviour and asserts what it did. A case that pins a schema word, a mock's shape, a name, or an assertion that cannot fail is a declared gap wearing a pass; it is rewritten to run the subject against a planted fault, or dropped."; until it lands, the Lead's rule for these briefs; grok 20260916T094152Z-review-grok-e72972#9, partial); a row that pins a count the contract does not own is a finding.
- Reviews and audits are dispatched against the pushed head, never an unpushed worktree commit.
- Every subprocess in a test goes through `ops.testkit.run` with a timeout; the world is hermetic and ambient is named; a fake is planted through the registry.
- The red is pasted, never inferred: `FAIL:` with an `AssertionError` at the base sha, `Ran N tests ... OK` at the head, the same discover command, both in the code commit's body with the base sha (the tdd skill).
- Every commit carries `Source:` and `Co-Authored-By:`; every paragraph that claims carries its reading (the claim skill); the second producer's absence is said where the owner's hand grant stands in.
- Draft PR into dev, body per CONTRIB.md, `## Proof` naming corpus rows under `ops/conductor/handoff/probes/`; the ready flip waits for a closed `security-audit` record on codex `gpt-daybreak-blue-latest` at the head sha with every finding disposed (CONTRIB.md ready table, owner's rule of 2026-09-16); a commit after the audit touching any path outside `.dev/records/` voids it; a record landing does not (agentscient-11's ruling, 2026-09-16 09:55Z).
- A CHANGES verdict is a stop, ruled on by agentscient-0d (the planner), never by the builder; report each PR to agentscient-11 by message with its number, head, readings and what was not measured.

## The pipeline, as commands

1. `python3 ops/conductor/tools/deliverable.py add lane/session-20260916-<x> --why '<the owner's words, dated>' --measure '<see the brief>' --until '<see the brief>'`, then `git worktree add ../wt/ag-session-20260916-<x> -b lane/session-20260916-<x> origin/dev`; `hand.py declare` at the owner's relayed word, `HAND_GRANT=<id>` leading every write.
2. Write the `## Scope` text below to a file under 1024 bytes (SCOPE_CAP in ops/lane.conf) and pass this brief whole as `--input`: from the worktree, `ops/bin/dispatch.sh --job author-tests --harness grok --scope-file <scope> --input <brief> --branch lane/session-20260916-<x>` (dispatch-by-hand: an unscoped open grant, from the branch's own worktree, no --model or --effort, every path spelled out). `record-target` refuses from the main checkout (issue 7); dispatch from the worktree.
3. Land the closed record: `python3 ops/conductor/tools/land.py <record id>`; push the branch.
4. `ops/bin/dispatch.sh --job check-tests --harness codex ...` at the pushed head; import its findings (`findings.py import`) and dispose each with a citation before coding.
5. Code by hand under the grant with the tests sealed; `ruff check` the changed files; commit with the red and green lines; push.
6. `--job adversarial-review --harness grok` and `--job security-audit --harness codex` at the pushed head; dispose every finding; correction rounds through `correction.py`.
7. `gh pr create --draft --base dev` with the body per CONTRIB.md; corpus rows for the change under `ops/conductor/handoff/probes/probes-2026-09-16-<slice>.jsonl`, named under `## Proof`.
