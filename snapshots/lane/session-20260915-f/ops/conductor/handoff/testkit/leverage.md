# The test kit's leverage, measured at 1e577966

Slice 21 of the plan (record 20260913T034513Z-plan-claude-892490): the
measurement item 6 asks for before any package is weighed, taken after
slice 20 at one sha, each number with its command. The "before" column
is the plan's §1 at 73024e7 where it measured one, else the census at
cc91f00d.

| measure | before | at 1e577966 | command |
|---|---|---|---|
| ladder family bytes (tests, faults, planted programs) | 254,957 | 256472 | `git ls-files 'ops/conductor/tests/test_ladder*.py' 'ops/conductor/tests/ladder_faults*.py' 'ops/conductor/tests/fakes/ladder_*.py' \| xargs cat \| wc -c` |
| hooks support bytes (support.py + gh_stub.py) | 20,948 | 20944 | `cat ops/devlane/hooks/tests/support.py ops/devlane/hooks/tests/gh_stub.py \| wc -c` |
| kit consumers (test modules importing ops.testkit) | 0 | 18 | `git ls-files 'ops/**/tests/*.py' '.claude/skills/*/tests/*.py' \| xargs grep -l 'ops.testkit' \| wc -l` |
| ladder rows in tables (pure / refusal / stop) | 0 | 39 / 22 / 13 | the three tables' row lists, counted |
| catch parity: quiet counts in the records | — | calibrate-ladder-refusals-c7ec3afd.json 0, calibrate-ladder-stops-c7ec3afd.json 0, sidebyside-ladder-retire-rest-c7ec3afd.json 0, sidebyside-ladder-tables-44804249.json 0 | `ops/conductor/handoff/testkit/*.json`, `quiet` and `quiet_in_new` |
| ladder family run | Ran 208 tests | Ran 191 tests in 58.216s | `python3 -m unittest discover -s ops/conductor/tests -p 'test_ladder*.py'` |
| hooks suite run | Ran 303 tests (at 3b9d2a11) | Ran 304 tests in 59.696s | `python3 -m unittest discover -s ops/devlane/hooks/tests` |
| kit suite run | — | Ran 30 tests in 7.769s | `python3 -m unittest discover -s ops/testkit/tests` |
| test modules setting HOME by hand, tree (finding 1's command) | 52 | 58 | finding 1's command |
| the ratchet | baseline at 4ee85df6: 58 / 30 / 180 | home_by_hand 58 -> 57 and run_without_timeout 180 -> 179, the new floor (slice 20); the baseline takes it in this commit; ratchet holds | `python3 ops/devlane/workflow/checks/testkit_ratchet.py` |

What the numbers say: two families share the primitives (the ladder
family and the hooks family), which is the condition rule 7 of
docs/tests.md sets before a package is weighed. Bytes did not fall in
the ladder family: the tables and their fault sets landed beside the
duplicates the plan's slice 15 names and keeps (test_ladder_lever_inputs.py,
test_ladder_stage_set.py, test_ladder_skeptic_envelope.py,
test_ladder_check_envelope_verb.py) and the fixture's own scenarios;
the fall comes when those follow-up slices retire them on their
records. Every fault the retired files caught is caught by a row (the
quiet counts). The hooks support shrank by four bytes: the adapters
are the old names over the kit, not less code yet.

The rule stands: a package (pytest, Hypothesis, mutmut) is proposed
only as an idea record naming a capability the kit cannot supply within
the stdlib, with this table beside it; the owner decides. Nothing is
installed by any slice of the plan. I-029 is that record's home.
