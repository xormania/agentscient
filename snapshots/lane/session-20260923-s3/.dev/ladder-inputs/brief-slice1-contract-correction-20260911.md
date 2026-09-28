# Brief: two corrections to slice 1's landed contract text

Fresh security audit 20260911T003235Z-review-codex-06b790 on this branch,
after the ladder's one fix round, found two things the landed contract
documents do not yet say. Both cite a numbered item of the work order
`.dev/ladder-inputs/scope-gate-20260910.md`; both are disposed fix-round
in the ledger. A third finding is resolved by ruling R8 in the plan and
needs one sentence in the contract.

Change only these documents: `ops/devlane/dispatch/CONTRACT.md`,
`ops/conductor/ladder-lever.md` if a sentence there must agree, and
nothing else. Do not edit tests. The pin suites must still pass; if a pin
contradicts a correction below, stop and report which pin, do not change
the pin.

1. Contract item 3, finding #1 (p1). The `correction` refusal row in
   `ops/devlane/dispatch/CONTRACT.md` gives one remedy for every arm. Each
   of the five arms (no key, absent, open, uncited, late) gets the needed
   text plan decision D5 prescribes: for the no-key arm, `pass --answers
   <record>#<n> for each finding answered, each disposed by python3
   ops/conductor/tools/findings.py disposition <record>#<n> <disposition>
   'contract item N of <scope path>: <why>'`; for the absent arm, `python3
   ops/conductor/tools/findings.py import, then` followed by the
   disposition command with the real key; for open, uncited and late, the
   disposition command with the real key. Rulings R1, R2 and R7 in the
   plan's section 10 apply: the key is shell-quoted in the printed
   remedy, the citation grammar stops before a colon, and the late arm's
   remedy is `wait one second and retry`.

2. Contract item 1, finding #2 (p2). The dispatch contract must state,
   mechanically, what a correction is: a write-role job (`implement`,
   `author-tests`) whose `--follows` names a record whose job is one of
   `check-tests`, `security-audit`, `adversarial-review`, `adjudicate`,
   `sweep`, or whose `--input` paths include a file under such a
   record's `out/`; read from the dispatch arguments and the followed
   record, never from prose. Put it where the `correction` and `follows`
   rows can cite it. Rulings R5 and R6 apply: the followed id must match
   the record-id shape and resolve under the records directory, and the
   record's own id must equal the requested id.

3. Contract item 7, finding #3 (p3), ruling R8. One sentence beside the
   `arguments` row or the `correction` row: a write job that follows a
   plan, tests or implement record, or nothing, is not inspected by the
   gate; `--answers` given on such a job is refused `arguments` at
   argument parsing, before the gate runs, because a claim no gate would
   verify must not enter a record.

Named command, which must pass:
`python3 -m unittest discover -s ops/devlane/dispatch/tests -p test_launch_correction_contract.py && python3 -m unittest discover -s ops/conductor/tests -p test_ladder_lever_correction_contract.py`

Commit with trailers per AGENTS.md.

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network and an isolated home — measured by the launcher's contract; the
  pin suites read documents only.
- assumption: the two pin suites pass at this ref — measured by the
  ladder's fix-code stage 20260911T002036Z-code-codex-4de570.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
