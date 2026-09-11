# Brief: fix round for slice 4 (launcher gate), tests half

Both audits of ladder 20260911T040533Z-ladder-fd103b found one defect
and cited contract item 1 of `.dev/ladder-inputs/scope-gate-20260910.md`
(the adversarial audit also items 2 and 3): the correction shape is read
from the `--input` argument's *resolved* path (`Path.resolve()` in
`ops/conductor/tools/correction.py` `_input_record_id`), so a symlink
that sits under a review job's `out/` but points elsewhere is not
classified as a correction, mints with `answers []`, and the launcher
then copies the symlink's target. Findings: security 314c2d#1,
adversarial 79cad6#1, both disposed `fix-round` with the citation.

Item 1 says the shape is read from the dispatch arguments. So: the
given path decides. A write job whose `--input` argument lies under a
review job's `out/` is a correction whether or not the entry is a
symlink; and a review artifact that is a symlink is never followed.

## The change (tests only)

In `ops/devlane/dispatch/tests/test_launch_correction_gate.py`, extend
the existing `CorrectionShape` cases (no new class, no other file):
- a `--input` that is a symlink under a review job's `out/` pointing at
  a regular file elsewhere, with no `--answers`: refused `correction`
  on the wire, no record minted, no child started, and the symlink's
  target is not copied anywhere under the jobs root;
- the same symlink with satisfying `--answers`: still refused before the
  mint (a review artifact that is a symlink is not a readable input),
  class `input`, found-text naming the symlink; no mint.
Prove both red on this tree (they fail today: the first mints, the
second launches), then leave them red: the code half is a separate
dispatch. Do not touch `launch.py`, `correction.py` or `record.py`.
Frozen command stays:
`python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_record_answers.py && python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_launch_correction_gate.py`
Report in `note` the two failing case names and their failure lines.

## First-run walkthrough
- assumption: whole tree at the branch ref, no network, isolated home;
  the tests build their own jobs root under a temp dir — measured.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
