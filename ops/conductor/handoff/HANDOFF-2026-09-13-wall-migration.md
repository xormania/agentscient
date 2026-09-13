# Handoff — 2026-09-13, after the wall migration of laneconf.py and probes.py

Record by Claude Fable 5.1 on `lane/session-20260913-i`, written at
`2e7dec62`. The board, PRs and grants are re-measured by
`onboard.py`, not taken from here. The
[AAR](../AAR-2026-09-13-wall-migration.md) carries the readings.

## Where things stand

- Commits on the branch over dev `c7245c6c` (#190): `dee2b4c9`, the two
  wall files onto `instrument.py` (grant 201, class wall); `15bea6a3`,
  their placement files to `migrated` (grant 202); `a9b79257`, the four
  fixture copy lists naming `instrument.py` beside `laneconf.py`;
  `2e7dec62`, the merge of `origin/dev` at `3014cb22` (#191); then the
  records commit carrying this file, the AAR and six corpus rows.
- PR: opened as a draft from this branch after the records commit; its
  number, head and checks are in the ready note and in `gh pr list`,
  not here. Ready waits on the full check set green on the final head,
  merge state clean, and `## Proof` naming the `P-WALL-20260913-*` rows.
- The consolidation gate at `15bea6a3`: 19 migrated, 1 no-wire
  (`lane_refs.py`), 3 pending (`skills.py`, `co_doc.py`, `control.py`).
  Nothing pending is a copy removal.
- Grants 201 and 202: settled after `cabb9d25`, but as "claimed;
  unverified": the evidence was prose with the sha inside it, and the
  lever verifies a bare object id only; a settled grant cannot be
  settled again. Pitfall 32. Grant 204 (this row and this line) is
  settled with a bare sha.
- The lock names `lane/session-20260913-i`; removed with
  `deliverable.py remove` once the PR has landed on dev, per the
  deliverable skill.
- Worktree `../wt/ag-session-20260913-i`.
- Dispatches: none run. Ladders: none. Findings: none produced.

## Corrections to retain

- **A wall grant writes wall paths only.** The placement files and the
  records went under a second grant of class `other`, declared at the
  same word; the code and its placement flip are two commits so the
  gate is never red between them.
- **`ConfigError` is a `Refusal`.** A consumer may catch either name;
  `line(kind)` still projects under a caller's token. New consumers
  should catch `instrument.Refusal` through `conf()` and not import
  `laneconf` for its class.
- **A copied `laneconf.py` needs `instrument.py` beside it.** The
  fixture copy lists in the four app tests are copiers too; a change to
  a tool's siblings reads every list that names the tool, not only the
  suites that stage it (`suites.sh` at `15bea6a3`, four reds).
- **The handoff directory.** Records named `HANDOFF-*` live under
  `ops/conductor/handoff/`; AARs beside `ops/conductor/`.

## Next thread

The consolidation's copy removals are complete. What remains is the
owner's ruling on the three older tools, summarized for the owner this
session:

- `skills.py`, the skills registry and its telemetry: on a bad call it
  prints a usage sentence and exits 1, the Finding class (measured:
  `skills.py nonsense`), where the wire says exit 2 with
  `class: expected; found; needed`. Adopting the wire changes what
  every caller of a bad verb sees.
- `co_doc.py`, the read-only permission doctor: on a bad argument it
  prints a usage line and exits 2 without the wire line (measured:
  `co_doc.py --bad`); otherwise it collects probe lines into a report
  object and exits 0, 1 or 2 from the report's state, and its
  `[Abort] probe: expected / found, remedy` lines are a wire of their
  own, older than the shared one.
- `control.py`, the finite conductor controller: it has its own
  `Refusal` class and a `need()` helper whose defaults fill in expected
  and needed; its lines are on the wire already (measured: no
  arguments exits 2 with a `control:` line), but the class is a private
  copy the gate names, and its defaults would go.

Each is a shape change with callers to read first, not a copy removal;
a session takes one at the owner's word. Two wall items from session
-h's handoff stay open, unassigned, for a wall session: the
corpus-shape rule refusing an `expect` that spans lines (`probes.py`),
and the hook's deliverable remedy that still says `clear` (`matrix.py`,
one line).
