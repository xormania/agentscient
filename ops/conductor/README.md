# ops/conductor — the conductor lane

The conductor's own apparatus, carried over whole from the House lane at
the owner's word (copy first, 2026-09-03) with a clean slate: its own
state directory, its own records, its own register. Nothing here shares
a file or a store with the House; the contracts and the instruments
crossed, the House's records did not.

## What lives here

| path | holds |
|---|---|
| `tools/` | the instruments: `onboard` (the brief), `decisions` (the register), `hand` (the handwork ledger), `watch` (PR checks), `land` (the landing lever), `ladder` (the audit-ladder driver), `ci` (the CI store), `branches` (the census), `skills` (the skills registry), `co_doc` (the doctor), `dispatch.sh` (the wrapper; `ops/bin/dispatch.sh` is its shim), `gate.sh` (the gate runner) |
| `tests/` | thirteen suites, the conformance gate among them; `ops/bin/suites.sh` runs them |
| `contracts/` | the board contract estate: `board.cue`, its example, its fault corpus |
| `*.md` | the instrument contracts and the lane's doctrine — `instrument-conventions.md` first, every instrument inherits it |
| `ideas/` | the idea records, `I-NNN-<slug>.md` — see `ideas/README.md` |
| `handoff/` | hand-over records and the probes corpus — see `handoff/README.md` |
| `AAR-*.md` | after-action reports; the newest one's calibration clause is what `onboard` serves as the thread |
| `lessons/`, `concerns/` | lessons carried from the House, and the fixed concerns (the hypocrisy concern first) |
| `stack.md`, `mcp-tools.md`, `census-package-map.md` | records the House wrote about this project before it existed; kept as origin, partly superseded by `docs/mapping.md` and the rulings in `AGENTS.md` |

## State

`~/.local/state/agentscient/` — `decisions.db`, `handwork.db`,
`dispatch/`, the skills and CI stores; created on first write, never in
a tree. The House's stores live under its own name and are never
touched from here.

## The loop

An idea is recorded → a ruling enters the register → a plan is
dispatched through the launcher → the record lands → `onboard` serves
the next session its brief → the AAR closes the session and writes its
probe rows. Half of that loop done by hand is what the copy exists to
end.

## Declared absences

- `probes.py`, the probes lever: contract only (`probes-lever.md`,
  `docs/probes.md`), as in the House — the runner has not been built
  anywhere yet.
- `board.py`: the board contract exists (`CONTRACT.md`, `contracts/`);
  the instrument was never built.
- the base-led branch form in `routing.md`: carried, not adopted;
  `AGENTS.md`'s `<area>/<slug>` stands.
- the skill suites under `.claude/skills/*/tests/` reference the
  workflow engine (`wf.py`, the next freight) and are not in the suite
  runner until it lands.
- `lessons/conducting.md` is the House's conducting record carried as
  lessons; its incident references are House history, read as such.
