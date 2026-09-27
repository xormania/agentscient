# Brief: regression tests for LD-15 from another harness

LD-15 (row in `ops/conductor/handoff/lane-defects.md`; the sentence "The
command names the tree" in `ops/conductor/ladder-lever.md`) landed by hand
in PR 109 with the repairer's own test
`ops/conductor/tests/test_ladder_derive_command.py`. The lane rule asks a
second producer for the regression test. Write
`ops/conductor/tests/test_ladder_command_names_the_tree.py` from the
lever sentence only; do not read or copy the repairer's test, and do not
edit the driver.

The subject is `Driver.derive_command(tests_envelope)` in
`ops/conductor/tools/ladder.py`, callable on a stub carrying
`conf={"SCOPE_CAP": "4096"}` and a `make_input(name, body)` that records
the body (load the module with `importlib` and register it in
`sys.modules` before executing, as its dataclasses need). Cover:
- a relative artifact under a `tests/` directory yields
  `python3 -m unittest discover -s <dir> -p <file>`;
- an absolute artifact under any `.../snapshot/` prefix yields the same
  command with the part after `snapshot/`, never the absolute directory;
- an absolute artifact with no `snapshot` component stops the ladder
  with reason `artifacts` and the path in the detail;
- a `..` component stops the ladder with reason `artifacts`;
- two artifacts join with ` && ` in order; a non-`.py` artifact and a
  path outside `tests/` are ignored; no artifact at all is an
  `artifacts` stop.
Prove each case red against a planted copy of the driver whose
`derive_command` still uses the path verbatim, then green against the
real one; say in `note` how. Frozen command:
`python3 -m unittest discover -s ops/conductor/tests -p test_ladder_command_names_the_tree.py`

## First-run walkthrough
- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the conductor suites.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
