# S2 — ledger-id-reservation

Class 1a of the 2026-09-16 issues: state kept as a flat file, or a git row, with no transaction and no history. Planner record 20260916T085626Z-review-claude-30f3eb, Part 1 C1, Part 2 slice 5. Issue 5: `LD-68.md` filed independently on lane/session-20260916-d and lane/session-20260916-f for two unrelated defects; T-65: pitfall 40 minted on two branches. Measured 2026-09-16 at dev 46639344: `python3 ops/conductor/tools/defects.py next` on the main checkout prints `LD-68` while two branches already carry `LD-68.md`; a third is one command away.

## The mechanism

`ops/conductor/tools/ledger.py` mints `highest(root, spec) + 1` (`highest`, the tree and `origin/<trunk>`; `do_add`), stateless: two sessions on one host read one highest and mint one id. The fix is a host-local reservation taken in one transaction, so two owners cannot hold one number.

- A table `ledger_reservations(ledger TEXT NOT NULL, number INTEGER NOT NULL, owner TEXT NOT NULL, agent TEXT NOT NULL, reserved_at TEXT NOT NULL, filed_at TEXT, path TEXT, UNIQUE(ledger, number))` in the state engine's store, `state.db` under the lane's state directory (`machine.connect(create=True)` for writes, `create=False` for reads; a plain register with no places, the state skill's "State with no places (a plain register) is a table in the same store").
- `reserve(conn, root, spec, owner, agent)`: `BEGIN IMMEDIATE`; `top = max(highest(root, spec), max(number) reserved for this ledger)`; insert `top + 1`; commit; return the number. The UNIQUE constraint is the second wall; a race is a refusal (`sqlite3.IntegrityError` re-read as the winner's number, then one retry), never a lost update.
- `owner` is `instrument.session()` when it is not `unknown` (Claude Code sets CLAUDE_CODE_SESSION_ID; measured in session a6b096a2 on 2026-09-16), else the repository root path from `repo_root()`; one worktree per session makes the path unique.
- `next LEDGER` prints this owner's unfiled reservation when one exists, else reserves and prints it. Two owners calling `next` print two ids.
- `add LEDGER ...` consumes this owner's unfiled reservation, else reserves; writes the row file; stamps `filed_at` and `path`. `add` never mints outside the table.
- `check LEDGER` reports reserved-and-unfiled numbers with owner and age beside shared numbers; findings, exit 1.
- `ops/conductor/placement/ledger.py.json` flips to `{"placement": "migrated", "state": {"engine": "sqlite", "files": "one file per ledger row under ops/conductor/handoff/, the git record plane, written from a reservation in state.db"}}`; `FILE_BACKED` in `ops/conductor/tests/test_state_placement.py` shrinks by `ledger.py` in the same commit as the flip (the gate's own rule: "shrink FILE_BACKED").
- `defects.py`, and every shim over `ledger.py`, keeps its spelling; the ideas register (handwritten) reserves through `next` the same way.
- `highest()` keeps its bounded fetch of `origin/<trunk>`: the reservation adds same-host atomicity, the fetch keeps cross-host awareness.

## Planted faults and the clean neighbour

Faults file `ops/conductor/tests/ledger_faults.py`, the shape of `ladder_faults.py` (`Mutant` from the kit; `cases.py calibrate`):
- M-no-reserve: the insert removed; `next-reserves` goes red.
- M-owner-blind: `owner` ignored when `next` looks for an unfiled reservation; `add-uses-own-reservation` and `add-after-other-next` go red.
- M-add-mints: `add` mints from `highest()` and skips the table; `add-after-other-next` goes red.
Clean neighbour: the unmodified lever passes every row.

## Rows (a case table by id in ops/conductor/tests/test_ledger.py; each executes the lever and asserts what it did)

- next-reserves: two `next defects` calls from two scratch repositories under one XDG_STATE_HOME (two owners, two CLAUDE_CODE_SESSION_ID values) print two distinct ids, both present in `ledger_reservations` unfiled.
- add-after-other-next: owner A `next` prints LD-N; owner B `add` writes `LD-(N+1).md`, never `LD-N.md`.
- add-uses-own-reservation: owner A `next` prints LD-N; owner A `add` writes `LD-N.md`; the reservation reads filed with that path.
- check-reports-unfiled: after next-reserves, `check defects` exits 1 and names the unfiled numbers with their owners.
- highest-still-reads-origin: a scratch repository whose path-local `origin` trunk carries `LD-90.md`; `next` prints LD-91 (no network in a World; the origin is a directory).
- race-never-shares: two `add` calls started together (two `run` children) write two files with distinct numbers; `check` reads no shared number.
- read-never-creates: `list` and `show` on a host with no `state.db` leave none behind.
Fixture: `World`, one scratch repository per owner with a path-local origin, `LANE_CONF` planted with `LANE_NAME` and `TRUNK_BRANCH`, `WF_AGENT` on writes only, every subprocess through `run` with a timeout. Origin rows: issue 5 of the 2026-09-16 issues report, T-65.

## Not covered

Two hosts (the store is host-local, machine-lever.md §The store). The two LD-68s already filed, reconciled by hand before either PR merges (the Lead's call). The measure for the lock: `sh -c "git -C /home/scientdb/projects/uscient/agentscient fetch -q origin; git -C /home/scientdb/projects/uscient/agentscient show origin/dev:ops/conductor/tests/test_ledger.py | grep -q next-reserves && echo s2=on-dev || echo s2=short"`, until `s2=on-dev`.

## Scope

author-tests for S2 ledger-id-reservation. Subject: ops/conductor/tools/ledger.py, its `next`, `add`, `check` verbs. Write ops/conductor/tests/test_ledger.py rows by id: next-reserves, add-after-other-next, add-uses-own-reservation, check-reports-unfiled, highest-still-reads-origin, race-never-shares, read-never-creates; and ops/conductor/tests/ledger_faults.py with mutants M-no-reserve, M-owner-blind, M-add-mints. Behaviour: ids are reserved in a ledger_reservations table in state.db in one BEGIN IMMEDIATE, owner = the harness session id else the repository root; next and add share the owner's unfiled reservation; check reports unfiled reservations. Import the kit from the repository root; every subprocess through run with a timeout; each case executes the lever and asserts what it did; prove red at the ref. The brief in --input carries the rest.

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
