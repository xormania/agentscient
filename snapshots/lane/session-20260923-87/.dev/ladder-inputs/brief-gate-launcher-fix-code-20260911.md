# Brief: fix round for slice 4 (launcher gate), code half

Both audits of ladder 20260911T040533Z-ladder-fd103b found one defect,
citing contract item 1 of `.dev/ladder-inputs/scope-gate-20260910.md`
(the adversarial audit also items 2 and 3): `_input_record_id` in
`ops/conductor/tools/correction.py` classifies the `--input` argument by
its *resolved* path, so a symlink under a review job's `out/` pointing
elsewhere is not a correction, mints with `answers []`, and the launcher
copies the symlink's target. Findings 314c2d#1 and 79cad6#1, disposed
`fix-round` with that citation. The tests half (record b18f24) added two
cases to `CorrectionShape` in `test_launch_correction_gate.py`; they are
red on this tree and are the acceptance criterion.

## The change (code only)

- `ops/conductor/tools/correction.py`: read the correction shape from
  the argument as given (lexically under `<jobs_root>/<review id>/out/`),
  never from `Path.resolve()`; keep the record lookup by that id.
- `ops/devlane/dispatch/launch.py`: before the mint, a `--input` that is
  a symlink (or whose path contains a symlinked component under the jobs
  root) is refused `input` on the wire, naming the path; the launcher
  never copies through it.
Touch nothing else; add no tests; keep the twelve refusal found-texts.
Frozen command:
`python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_record_answers.py && python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_launch_correction_gate.py`
Run it before the edit (two failures, name them in `note`) and after
(green), then `ruff check` on both files, commit.

## First-run walkthrough
- assumption: whole tree at the branch ref, no network, isolated home —
  measured by the dispatch suites.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
