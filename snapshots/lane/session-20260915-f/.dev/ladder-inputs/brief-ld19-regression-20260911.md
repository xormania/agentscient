# Brief: regression tests for LD-19 from another harness

LD-19 (row in `ops/conductor/handoff/lane-defects.md`; the lever
sentences in `ops/conductor/ladder-lever.md`: "each test module
(`test*.py`, unittest's default pattern) under a `tests/` directory
becomes a `python3 -m unittest discover` invocation ... another `.py`
there is a support module, carried as an artifact and never run" and
"`resume LADDER_ID --retry STAGE --because TEXT` grants that stage one
further attempt ... written on the stage row (`retry`: because, at, by,
from_attempt) and is spent once") landed by hand in PR 122 with the
repairer's own tests `test_ladder_support_modules.py` and
`test_ladder_retry.py`. The lane rule asks a second producer for the
regression test. Write
`ops/conductor/tests/test_ladder_ld19_second_producer.py` from the lever
sentences only; do not read or copy the repairer's two tests, and do not
edit the driver.

Subjects in `ops/conductor/tools/ladder.py` (load with `importlib`,
register in `sys.modules` before executing): `Driver.derive_command`
on a stub with `conf={"SCOPE_CAP": "4096"}` and a `make_input(name,
body)` that records the body; `Driver.retry_granted(name)` on a stub
with `retry`, `agent` and `row(name)`; the module function
`resume_options(args)` which returns `(rescope, retry)` or raises
`Refused`. Cover:
- a `tests/helper.py` beside a `tests/test_x.py` yields one discover
  invocation, for the test module only; a helper alone is an
  `artifacts` stop;
- a file named `test_x.py` outside any `tests/` directory is ignored;
- `retry_granted` is False with no retry, False for another stage,
  True once for the named stage, writing `because`, `at`, `by`,
  `from_attempt`, and False on the second call;
- `resume_options`: plain, `--rescope`, `--retry code --because TEXT`,
  and refusals for a retry without a reason, a reason without a stage,
  an unknown stage, an empty reason, and an unknown flag.
Prove each case red against a planted copy of the driver whose
`derive_command` still accepts every `.py` under `tests/` and whose
`retry_granted` always returns False, then green; say in `note` how.
Frozen command:
`python3 -m unittest discover -s ops/conductor/tests -p test_ladder_ld19_second_producer.py`

## First-run walkthrough
- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the conductor suites.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
