# Handoff — 2026-09-12, after proof at the boundaries

Record by Claude Fable 5.1 on dev at `4bf38d66`. See the
[AAR](../AAR-2026-09-12-proof-at-boundaries.md). Re-measure before acting.

## Where things stand

- dev `4bf38d66` carries #154 to #157 and the records; master is at
  33982a3 (release #149); the next release PR carries everything since.
- Zero open PRs; zero open grants (155 to 160 settled verified); the
  deliverable lock is cleared when this record lands.
- Worktrees this session created, all clean and pushed:
  `../wt/ag-effort-turns-20260912`, `ag-probes-runner-20260912`,
  `ag-worker-mcp-brief-20260912`, `ag-pr-proof-gate-20260912`,
  `ag-live-proof-20260912`.
- The live hook in a session comes from the main checkout: after
  #157 every ready and merge of a PR from a session is gated; the PR
  body needs a `## Proof` section naming corpus rows present at the
  head, and the head needs a green `ci` run.
- Every dispatch now writes `<job>/lane-mcp.json`, hands the worker the
  lane MCP, appends the what-exists brief and the reuse clause to the
  prompt, and records `result.proof` and (write roles) `result.reuse`.
- 11 findings open on `20260912T042714Z-review-codex-063615`: the
  conductor contract's references to `ops/conductor/tools/board.py`.

## Corrections to retain

- **Done means consumed.** A capability is recorded done only with the
  reading that shows a dispatch or a boundary consumed it; the corpus
  row is where that reading lives, and CI runs it.
- **The record keeps store paths portable**; a reader inverts them with
  `_absolute_paths` before opening the file (the proof reader learned
  this red).
- **Do not edit the tree while `suites.sh` runs**: the fixtures and the
  wrapper tests compare the tree before and after and read an edit as
  a mutation.
- **Run `ruff check .` and `probes.py run` in the branch before
  pushing**; four CI rounds today were those two commands.
- **The corpus's git rows need the records branches by local name**;
  the CI step after checkout creates them, offline.
- **The pr-proof row reads any statement whose tokens open with the
  ready or merge verb, including prose inside an executing heredoc**;
  write records with data heredocs (`cat > file <<'EOF'`).
- **Codex `-c mcp_servers.<key>.args=[...]`, Grok `$GROK_HOME/config.toml`,
  Claude `--mcp-config` plus the `mcp__<server>` tool rule**: measured
  live, all three answer.

## Open, in the ledger, not started

- The 11 dead-reference findings above (one class, one fix).
- Which predecessor test leaves the process in a deleted directory
  (LD-25 names the fixture repair only).
- The per-instrument consumption census (an instrument with no corpus
  row consuming it): named, not built.
- The first ladder under `caps.turns` and the brief: its records are
  the reading for the turn unit and for whether test authors thrash less.

## Next thread

Owner, 2026-09-12: the goal is the prod lane; the dev lane is "good
enough while being able to fix issues as I go along". The next release
PR (dev into master) is the natural next act; then the prod-lane work
the owner has been holding.

## Retrieval

```sh
git show dev:ops/conductor/AAR-2026-09-12-proof-at-boundaries.md
git show dev:ops/conductor/handoff/HANDOFF-2026-09-12-proof-at-boundaries.md
python3 ops/conductor/tools/probes.py run
```

Left behind on purpose: the session scratchpad (live probe homes and
outputs, edit scripts, CI logs).

## Addendum: the session branch shape (owner, 2026-09-12: "one brench per session - lets try it")

- Start: `git worktree add ../wt/ag-session-<date>-<id> -b lane/session-<date>-<id> origin/dev`,
  then `deliverable.py add lane/session-<date>-<id> --why '<owner's words>'`.
  The `add` verb keeps another session's branch in the lock.
- Work and records commit to that branch; nothing commits to dev from
  a session any more. One draft PR into dev at close, through the proof
  gate (a `## Proof` section, rows at the head, a green run).
- The dispatcher merges origin/dev forward before each launch. A
  `stale-base` refusal now means a real conflict; resolve the named
  files in the worktree, commit, dispatch again.
- Two sessions land separately; if both touched
  `ops/conductor/findings/findings.jsonl`, regenerate it with
  `findings.py export --write` after the merge instead of resolving by
  hand.
- First use: this branch, `lane/session-20260912`, PR into dev at close.

## Addendum, the evening (dev at d5169bc6 before this record)

- Every session: cut `lane/session-<date>-<id>` from dev, `deliverable.py add` it,
  commit everything there, one draft PR at close through the gate. A commit on
  dev from a session is a hard row.
- Hooks: `engine.py` at every event reads `ops/devlane/hooks/boundaries.json`;
  20 rows, 5 as data (trunk-commit, claim-unmeasured, prune, test-form,
  force-push), 15 still as matrix code. Adding or removing a condition is a
  row, and the registry and engine are wall paths: a grant of lever class
  `wall`, in a session that touches only the wall.
- The five hard rows answer `ask`. In a hand-driven session that is the
  owner's click. In auto mode the classifier answers it (measured d5169bc6:
  it let a dry-run commit on dev run and denied a forced push). If that is
  not wanted, the rows go back to `escape: none`; the owner has not decided.
- The owner's word is the grant: declare it unscoped the moment it is given;
  a scope is path prefixes, never a branch name (LD-26). A python write the
  row cannot resolve needs an open grant.
- Corpus rows that pin counts (`"class":` 20, ask rows 5, UNRESOLVED_WRITE 6)
  break on any removal; rewrite them as presence rows next.
- Left open: the fourteen code rows as data; a live reading of SessionStart
  and Stop; the claim row's effect on what sessions write; release PR #158
  (dev into master, #150 to #157) for the owner; #159 to #164 go in the next.
- Worktrees this session created, all clean and pushed: `ag-session-20260912`
  and `-b` to `-g`, `ag-effort-turns-20260912`, `ag-probes-runner-20260912`,
  `ag-worker-mcp-brief-20260912`, `ag-pr-proof-gate-20260912`,
  `ag-live-proof-20260912`.
