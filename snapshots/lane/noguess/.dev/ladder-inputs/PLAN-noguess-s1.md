# Slice 1 — defaults-verb (S)

See `PLAN.md` census and guard design. Own PR. First.

Files: `ops/conductor/tools/laneconf.py` `ops/conductor/tools/defaults-exceptions.json`

Unblocks: every later slice. Risk: a contract (exception table). Edges: `defaults` → `ops/lane.conf`; `defaults` → `defaults-exceptions.json` (closure both ways). Depends on: nothing. Lands green alone: yes. Own PR: yes.

Tests: `ops/conductor/tests/test_laneconf_defaults.py`. Why red at `90b8c2721a8f3da06fd98f334026c20aba640ede`: `python3 ops/conductor/tools/laneconf.py defaults` exits 2 class `arguments` (measured). Named command: `python3 -m unittest discover -s ops/conductor/tests -p test_laneconf_defaults.py`

Walkthrough of the first run: `PLAN.md` §Slice 1.

## Machine lines, slice 1

slice	defaults-verb	S
bucket	defaults-verb	S	ops/conductor/tools/laneconf.py ops/conductor/tools/defaults-exceptions.json
calibration	defaults-verb	S	files=2	tests=1	lines=220	author-tests=21	check-tests=10	implement=8
