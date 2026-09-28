# I-029 — the test kit's leverage, and what a package would have to supply

Standing: recorded 2026-09-14 by Claude Fable 5.1 on lane/session-20260914-b,
slice 21 of the test kit plan (record 20260913T034513Z-plan-claude-892490).
The measurement is `ops/conductor/handoff/testkit/leverage.md`, taken at
1e577966 with its commands.

## The rule

docs/tests.md rule 7: no test package until two families share the
primitives and the leverage is measured and recorded; the owner decides
on that record. Two families share them now (the ladder family, the
hooks family). This idea is where a package is proposed, if ever: it
must name a capability the kit cannot supply within the stdlib, and
carry the leverage table beside it.

## What the kit supplies today

- A hermetic world (HOME, the XDG roots, TMPDIR, cwd, a bin, a frozen
  git identity and clock), ambient by name only.
- One command runner with one result shape and one timeout policy that
  kills and reaps; the wire parsed from a result.
- Fakes driven by data with an append-only call log; wrapped real tools.
- Case tables by id with an origin; planted faults as data with an
  anchor guard; calibrate and sidebyside over an archive copy that is a
  repository of its own.

## What a package would have to add, to be worth its verification bill

- pytest: fixtures by injection and parametrize. The tables give
  parametrize by data already; injection buys nothing the World does
  not, and the suite lever and CI are stdlib-only by design (no pip
  step). Not proposed.
- Hypothesis: property-based inputs. No table today has a property a
  generator would reach that its rows do not; when one does, it is
  named here with the row it would replace. Not proposed.
- mutmut or another mutation tool: automatic mutants. The kit's faults
  are hand-planted and named for the defect they replay (LD-15, LD-17,
  LD-19, LD-23); a generated mutant set is a different question, cheap
  to try against `cases.py calibrate` when a table's fault set is
  suspected thin. Not proposed until a table's calibrate reads quiet on
  a fault a generator found.

## Open

- The ladder family's bytes did not fall (254,957 at 73024e7,
  256472 at 1e577966): the duplicates slice 15 keeps and names are
  the next retirement, each on its side-by-side record.
- 40 modules in the other families still set HOME by hand
  (58 tree-wide by finding 1's command); the ratchet holds the
  ceiling and each family migrates under the same evidence rule.
