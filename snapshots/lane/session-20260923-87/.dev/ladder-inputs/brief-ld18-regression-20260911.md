# Brief: regression tests for LD-18 from another harness

LD-18 (row in `ops/conductor/handoff/lane-defects.md`) landed by hand in
PR 120 with the repairer's own tests `test_isolation_credential_age.py`
and `test_launch_credential_age.py`. The lane rule asks a second producer
for the regression test. Write
`ops/devlane/harness/tests/test_credential_age_second_producer.py` from
the isolation entry and the launcher's refusal wire only; do not read or
copy the repairer's two tests, and do not edit the module or the launcher.

The subject is `check_credential_age(harness, spec, name, src)` in
`ops/devlane/harness/isolation.py` (load it with `importlib`), driven by
`HARNESSES["grok"]["credential_age"]`: `file`, `field` (`create_time`),
`max_hours`, `remedy`, `measured`. Cover:
- a grok `auth.json` whose newest entry's `create_time` is older than
  `max_hours` raises `NotIsolated` naming the remedy and the field;
- one younger than `max_hours` passes silently;
- a file with several entries is judged by the newest stamp;
- a file with no `create_time`, an empty object, or unparseable bytes is
  not aged (no exception);
- a nanosecond stamp with a trailing Z (`2026-09-11T05:41:45.673826295Z`)
  parses; a malformed stamp is ignored;
- `build_home("grok", root, env={"HOME": ...})` raises `NotIsolated` for
  the aged file and leaves no `auth.json` link in `root`;
- the codex entry carries no `credential_age` and an aged codex file
  builds a home.
Prove each case red against a planted copy of the module whose
`check_credential_age` returns without looking, then green against the
real one; say in `note` how. Frozen command:
`python3 -m unittest discover -s ops/devlane/harness/tests -p test_credential_age_second_producer.py`

## First-run walkthrough
- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home; tests build their own homes under a
  temp dir — measured: the harness suite already does so.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
