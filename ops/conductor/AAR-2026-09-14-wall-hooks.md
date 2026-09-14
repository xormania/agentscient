# AAR — 2026-09-14, the wall hooks: T-5, T-11 and T-13

Session `lane/session-20260914-a`, Claude Fable 5.1, by hand under wall
grant 223 (the hook tests, engine, registry, matrix docstring, ci.yml)
and grant 224 (the SessionStart script, settings.json, the records).
Written at `95c83ef8`, the code head; every reading names its sha. The
handoff is rows in the state engine's store, not a file.

## The request, in the owner's words

After the board at onboard, the owner: "blanket hand grant ok'd - get
T5,11, and 13 don" (2026-09-14). The three threads were taken from the
store on this branch (`handoff.py take T-5`, `T-11`, `T-13`, each
`taken ... on lane/session-20260914-a`).

## What was done

| commit | grant | what |
|---|---|---|
| `5b015438` | 223 | the red: two engine tests and `test_trunk_forward.py` |
| `c197667d` | 223 | `engine.py`: a merge of `<remote>/<trunk>` that git reports as a fast-forward is not a trunk commit; the `file_state_store` predicate; the `file-state` row in the registry; the matrix docstring line |
| `3e030317` | 224 | `trunk-forward.py`, a SessionStart hook bound before the engine in `.claude/settings.json` |
| `95c83ef8` | 223 | `ci.yml`: actions/checkout 4.4.0 to 7.0.1, the two lines of #200 (`20729e00`), dependabot credited |
| `264745c0` | 224 | `trunk-forward.py`'s docstring reworded: the literals verb forbids the lane literal for the trunk |
| the records commit | 224 | this page; the `refused` and `state` skill pages; the README hooks line; LD-38's repair; seven corpus rows `P-WALLHOOKS-20260914-*` |

## Readings

- Red at `6e3de429` (the base): `python3 -m unittest discover -s
  ops/devlane/hooks/tests -p 'test_engine.py'`: Ran 18 tests, FAILED
  (failures=2), the trunk row refusing `git merge --ff-only origin/dev`
  and hook-error on the unknown predicate; `-p 'test_trunk_forward.py'`:
  Ran 10 tests, FAILED (failures=10), the script absent.
- Green with the same commands at `3e030317`: Ran 18 tests, OK; Ran 10
  tests, OK. `test_boundaries.py`: Ran 6 tests, OK. The whole hooks
  suite: Ran 303 tests, OK. `engine.py lint`: 6 engine rows, 11
  predicates, no unknown predicate or event. `ruff check` on the five
  Python files: clean.
- The wire by hand at `c197667d`, the branch's engine against the main
  checkout at `cccc810b`: a redirect to
  `~/.local/state/agentscient/claims.json` answered deny with
  `[engine:file-state]`; `git -C <main> merge --ff-only origin/dev`
  answered nothing (let through); `git -C <main> merge --no-ff
  origin/dev` answered deny with `[engine:trunk-commit]`.
- `trunk-forward.py` by hand at `3e030317` against this worktree:
  `trunk-forward: ... is on lane/session-20260914-a, not dev; not
  moved`, exit 0. Its first live run at a session start waits on the
  merge; not measured here.
- `ops/bin/suites.sh` at `95c83ef8`: dispatch 618, harness 155, task 351, telemetry 227, hooks 303,
  fixtures 221, workflow 51, pr-overview 8, all OK; conductor Ran 1180,
  FAILED (failures=2): `laneconf.py literals` on `trunk-forward.py`'s
  docstring naming the remote trunk by its lane literal, reworded in
  `264745c0`; and the tracked corpus's three count rows, re-pinned in
  the records commit. Exit 1. The re-run on the head is in the PR's
  ready note.
- Corpus: `probes.py run` at `95c83ef8`, before this session's rows:
  pass 194, fail 3, unreachable 0. The three fails are count rows this
  change moved on purpose, `P-BND-20260912-registry` (20 to 21 rows),
  `P-TRUNK-20260912-prose` (5 to 6 engine rows) and
  `P-ENG-20260912-vocab` (10 to 11 predicates), re-pinned in the
  records commit. The seven rows of this session and the re-run are
  read in the PR's ready note.

## Decisions

- **The exception is one ref.** Only a merge whose single operand is
  `<remote>/<trunk>` passes; a local branch that would fast-forward
  still refuses, because the row's point is that the trunk moves only
  by what landed on the remote (LD-38's own words).
- **`--ff-only` on a diverged trunk is let through.** Git refuses it
  itself and no commit can result; the row refuses what would create a
  commit, not what git will refuse anyway.
- **`file-state` escapes nothing.** The remedy is the engine, the
  agent's own; the placement pin `FILE_BACKED` with the owner's word is
  the only other way, and the row's needed half says so. `.log` is not
  a store suffix: the matrix itself writes `graft-first.log` under the
  state directory.
- **The SessionStart script is Python beside `engine.py`**, one line
  always, exit 0 always: a session start is never blocked, and a fetch
  that fails is said as could-not-look.
- **T-13 by hand, not a cherry-pick.** `cherry-pick --no-commit` reads
  as a write to `.`, which a wall grant may not cover, and an amend is
  denied; the two lines were applied by a script that spells the path,
  with dependabot in `Source:` and `Co-Authored-By:`. #200 stays open
  for the owner; whether Dependabot closes it once dev carries the
  version is not measured.

## What went wrong

- The first onboard brief measured the main checkout at `cccc810b`,
  14 commits behind `origin/dev` at `6e3de429`: T-11's cost, paid once
  more. The brief was re-taken from a detached worktree
  `../wt/ag-onboard-20260914` at `6e3de429`, which served the
  `== handoffs` section the stale tree could not.
- `claim-unmeasured` refused two commit messages: a body paragraph with
  "passes" and no reading, then a subject line with "passes". The hook
  denies the whole Bash call, so a chained `git add && git commit`
  staged nothing; both retries were scanned with
  `matrix.unmeasured_claim` first (pitfall 36).
- Five `clipped-sweep` refusals on alternation greps piped to `head`,
  one `stale-check-rollup` on `statusCheckRollup`; none wrong, one
  pattern per call after.
- `coverage-zones.md` names `test_ci_shape` for the CI shape zone;
  `find ops -name 'test_ci_shape*'` at `95c83ef8` found nothing. Not
  measured whether it lives elsewhere; #200's own checks ran to pass on
  the same two lines (run 34783304650).

## Calibration

- Tokens: not measured this session.
- Hook refusals: 8 (`clipped-sweep` 5, `claim-unmeasured` 2,
  `stale-check-rollup` 1), 0 wrong.
- Corpus at `95c83ef8`, before this session's rows: pass 194, fail 3
  (the three count rows above), unreachable 0.
