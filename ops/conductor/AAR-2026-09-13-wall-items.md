# AAR — 2026-09-13, the two wall items: one-line expects, the remedy that said clear

Session record by Claude Fable 5.1 on `lane/session-20260913-k`, cut from
dev `eaf73b98` (#192). Written at `2f21512f`, the wall commit; the records
commit carrying this file follows. The
[handoff](handoff/HANDOFF-2026-09-13-wall-items.md) carries the board at
close. Grants 206 (wall) and 207 (records).

## Request and outcome

The owner, in order: "on board from the last session - co-ordinate with
other session after yu onboard to deconflict work"; then "192 merged -
hand grant ok'd for `The two wall items left`".

Onboarded from `onboard.py` at dev `3014cb22` (brief complete, exit 0,
seven law files present). Messaged session agentscient-5e (`-i`) before
naming a deliverable; it replied with its file set (laneconf.py,
probes.py, their placement files, four fixture copy lists, its records),
PR #192 at `cabb9d25`, and that it took neither wall item. No overlap.

One commit of code, `2f21512f`, both items:

- `probes.py` refuses class `corpus` for a serve or nearmiss `expect`
  containing a newline; the contract's serve row and refusal table say
  so. Pitfall 30 is the practice this makes mechanical: a row pins
  membership, one line, because a sorted list gains neighbours from
  every parallel session.
- `matrix.py`'s deliverable refusal no longer tells a session to run
  `deliverable.py clear`, which wipes every session's entry; it names
  `add <branch>` for a new session and `remove` when the work lands.

## What was decided and why

- **Both items in one wall commit, one PR.** Each is a few lines; two
  PRs would cost two CI rounds for the same wall grant.
- **The contract page changed with the code.** The corpus rule is the
  contract's to declare; a runner refusing what its contract does not
  name is drift.
- **`deliverable.py`'s usage line still lists `clear`.** The verb exists
  and the usage line describes it; only the hook's remedy pointed a
  parallel session at it. Not changed, not a wall file.
- **No new pitfall.** The one refusal met, the deliverable hook judging
  `deliverable.py add && git worktree add` before the add ran, is
  pitfall 27's shape (the hook judges the whole command first; two
  calls).

## What went wrong

- Two `clipped-sweep` refusals on multi-alternation greps with `head`;
  re-run without the clip.
- One `hand-write` refusal on a heredoc script with `cd` ahead of
  `HAND_GRANT`; the grant id must lead the whole command, so the
  script moved to the scratchpad and was run as
  `HAND_GRANT=206 python3 <abs path>`.
- The first `unittest` invocation of the matrix test by dotted module
  name errored on import; the suite's own `discover -s` form is the one
  to use, and the red reading was taken with it.

## Calibration

- Red then green, same commands, at `eaf73b98` then `2f21512f`:
  `python3 -m unittest ops.conductor.tests.test_probes.CorpusRefusals.test_an_expect_that_spans_lines_refuses`
  failures=2 then OK; `python3 -m unittest discover -s
  ops/devlane/hooks/tests -p test_matrix.py -k
  a_new_worktree_or_branch_outside_the_lock` failures=4 then OK.
- `test_probes.py` Ran 23 OK; `test_matrix.py` Ran 70 OK; `ruff check`
  clean on the four files, at `2f21512f`.
- `probes.py run`: pass 146 at `eaf73b98` with the rule in place (no
  tracked row spans lines, also read by a JSON walk over 146 rows);
  pass 150, fail 0, unreachable 0 at `2f21512f` with the four
  `P-WALLITEMS-20260913-*` rows in the worktree.
- `suites.sh` at the records commit: in the ready note.
- One producer wrote tests and code by hand under grant 206; no second
  producer.

## Second thread: the four rulings, one PR

Owner, 2026-09-13, after the explain of five rulings: "#1- #4 hand grant
ok'd get them done in one PR". Grants 210 (other) and 211 (wall). The
same branch, fast-forwarded to dev `25b48ed5` (#193), then dev merged
forward at `268065a3` (#194, the other session's skill-use hook) before
the commits.

Two commits: `9950d14d`, the three tools on the wire and instrument.py
(grant 210); `2bd810e2`, suites.sh running ruff and the two hook tests
that copy skills.py staging the shared module beside it (grant 211).

### What was decided and why

- **The class token names what refused, not the tool.** control.py's
  one token for every refusal became eight; the registry row for it
  reads `state`. No caller matched the old token: the conductor-control
  hook allows argument shapes and reads no stderr; no test named it.
- **The report is not a refusal.** co_doc.py's exit 2 with a report on
  stdout for an invalid probe is its outcome contract
  (permission-surface.md) and is untouched; only the unknown-argument
  path moved to the wire.
- **skills.py's wire tests were written before its shape changed**
  (`test_skills.py`), red at the base on the exit code and on the
  store's location, which now honours XDG_STATE_HOME through
  `state_dir()`. The explain and the commit `9950d14d` said skills.py
  had no test file; it had one, `test_skills_registry.py` (23 tests),
  which a search for the name `test_skills.py` alone did not find. A
  recollection wearing a reading; corrected here, not in the commit.
- **Two lint contracts in one scratch tree.** The fixture app tests copy
  the lane into a scratch app and run `suites.sh` there; with ruff in
  it, the lane copies read red under the app's own rules, and a lane
  `ruff.toml` at the scratch root shadowed the app's config and its
  planted faults. The lane contract rides as a nested `ops/ruff.toml`
  in the scratch, keys re-rooted, which ruff applies to the copies
  alone; the copy lists are unchanged.
- **One PR carries a wall commit and a non-wall commit**, each under its
  own grant and said in each message, at the owner's word; the wall
  grant also wrote the two hook tests (wall paths) that stage the
  module beside the copied lever.
- **A lint the host cannot run is not a green lint**: suites.sh reads
  ABSENT and not OK without ruff, rather than skipping.

### What went wrong

- The first migration dropped `import re` from skills.py while
  `frontmatter()` still used it; ruff named it and `sync` failed; one
  fix before any commit.
- The co_doc read-only test read the interpreter's bytecode cache for
  the imported module as the doctor writing a file; the test's
  environment now sets PYTHONDONTWRITEBYTECODE, the conformance gate's
  precedent.
- Two hook tests copy skills.py alone into a fake repository and read
  the `tooling` refusal once it imported instrument.py; the shape
  probes.py and monitor.py already handled in their own tests.

- `suites.sh` at `a20ffde9` read fixtures 2 red and conductor 21 red:
  `test_skills_registry.py` copies skills.py alone into a throwaway
  tree, and the four fixture scratch trees linted under the app's
  rules. Both fixed in the commit after the records, under grant 213.

### Calibration

- Red then green with the same commands, at `25b48ed5` then `9950d14d`
  or `2bd810e2`: test_skills 17 failures of 9 then OK; test_co_doc -k
  unknown_argument 9 failures then Ran 21 OK; test_control -k
  refusal_classes 1 failure then Ran 8 OK; test_instrument 3 failures
  then Ran 34 OK; test_instrument_conventions 3 failures then Ran 18 OK;
  test_suites_ruff 3 failures then OK; test_miss_log 9 failures at
  `9950d14d` then Ran 9 OK; test_skill_use Ran 8 OK; test_conductor_enforce
  Ran 11 OK.
- `ruff check .` clean at `2bd810e2`. `probes.py run` at `2bd810e2` with
  the seven `P-WIRE-20260913-*` rows: pass 163, fail 0, unreachable 0.
- `suites.sh` at the records commit: in the ready note.
- One producer wrote tests and code by hand; no second producer.
