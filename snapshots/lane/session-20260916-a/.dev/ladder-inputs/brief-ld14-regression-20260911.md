# Brief: regression tests for LD-14 from another harness

LD-14 (row in `ops/conductor/handoff/lane-defects.md`; contract paragraph
"Measured Codex read-role containment" in `ops/devlane/dispatch/CONTRACT.md`)
landed by hand in PR 107 with the repairer's own test
`ops/devlane/dispatch/tests/test_launch_read_role_tmp.py`. The lane rule
asks a second producer for the regression test. Write
`ops/devlane/dispatch/tests/test_launch_codex_read_containment.py` from
the contract paragraph only; do not read or copy the repairer's test, and
do not edit the launcher.

Cover, using `launch_support._TempLaunch` as the existing suites do (plant
a `dev` branch at the fixture's middle commit so a review job's diff is
non-empty; one job per test case, since the fixture holds one record):
- for each Codex read-role job in `ops/devlane/task/jobs.json` (plan,
  check-tests, security-audit, adversarial-review, adjudicate, sweep):
  argv carries `--sandbox workspace-write` and exactly one
  `sandbox_workspace_write.writable_roots` naming the job `out/`; the
  record's `harness.sandbox` says `workspace-write`;
- the child's `TMPDIR` is a real, non-symlinked `out/tmp` under the job;
- every regular file under the snapshot has no write bit after launch;
- a Codex write-role job (implement) is unchanged: `workspace-write` with
  the same single root, and no snapshot mode stripping is required of it.
Prove each case red by pointing it at a stub launcher that emits the old
`--sandbox read-only` argv, then green against the real one; say in
`note` how. Frozen command:
`python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_launch_codex_read_containment.py`

## First-run walkthrough
- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home; the dispatch suites build their own git
  fixtures — measured: `launch_support.py` does so.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
