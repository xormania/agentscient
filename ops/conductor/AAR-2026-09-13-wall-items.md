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
