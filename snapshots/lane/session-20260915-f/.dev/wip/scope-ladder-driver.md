# Scope — the ladder driver: a scope runs the loop end to end without a session at each boundary

Formed in chat with the owner, 2026-09-04. The owner's words are verbatim.
Measured on dev at `e566c33` (lane fix batch 1 merged). Nothing here says how.

## What the owner said

> keep it all going

> I feel more inclined for contractual guarentees

> start with the stale tests now and cut the driver's scope while that runs
> - but now php/symfony until i'm comfortable with the dev machinery

## What was measured

Batch 1 ran 12 dispatches through 12 stage boundaries; at every boundary
the session read the record, landed the result (the lever from batch 1
on, by hand before it), re-authored where a harness wrote its own name,
built the next input file and scope sentence, launched the next stage
through `dispatch.sh`, and armed a monitor. Session latency per boundary
was three to five minutes; about forty-five minutes of a four-hour batch
was that latency, and every hand step was a chance for the errors the
session made (an effort bypass, a launch under a ten-minute tool cap, a
loop that stopped on its own filter). The stages themselves ran
unattended. The levers the driver needs exist since batch 1: the
dispatcher returns at mint with the record id (`--detach`), the launcher
`wait`s on a record, `collect` recovers a tripped tree, `land.py` lands
an accepted result, and the dispatcher runs the branch's own launcher.

## What the owner wants

- One lever, `ops/bin/ladder.sh` (or the Python beside it), that takes a
  scope file and a branch (in a worktree) and runs the loop the process
  document names, in order: author-tests (Grok), check-tests (Codex
  skeptic), a Grok fix round when the skeptic's verdict is changes,
  implement (Codex Sol) with the named command, the security audit
  (Codex, the security model) and the adversarial audit (Grok), one fix
  round (Grok tests, Sol code) when either audit's verdict is changes,
  the security re-audit only, then the draft PR into dev with a body
  built from the records. Each stage's result lands through the land
  lever; each launch goes through `dispatch.sh` so the conf's models and
  efforts apply; every commit a harness made is authored by the owner
  with the model in `Co-Authored-By` before it lands.
- The shape per slice is the owner's ruling D-LADDER-1 (2026-09-04:
  "Split the implimentation into 2 runs - and audit once per batch and
  no skeptic on fixed tests. This is what i meant about optimizing
  planning"), and the driver enforces it rather than remembering it: the
  skeptic runs once, on the first tests, and the fix round's output goes
  to implement without a second skeptic; implement runs per S bucket of
  files, so an M slice is two implement runs the plan names, each
  landed and green before the next; the two audits, their one fix round
  and the security re-audit run once per batch on the merged tree,
  after the batch's last slice lands, never per slice; and when a slice
  closes the driver writes the plan's declared bucket beside the
  measured one (files, tests, lines, minutes per stage, findings per
  stage) into the record, which is the planner's calibration table.
- The driver stops, on the wire, at the first refusal, trip, crash or
  verdict it cannot resolve by the rules above, printing the record id
  and the stage; it never lands by hand, never edits tests or code, never
  retries a stage more than once, and never runs a second fix round
  (owner: no eighteen-hour loops). A stopped run resumes from the stage
  it stopped at, by record.
- Inputs per stage are cut for that stage: the scope, the plan section
  for its unit, and the previous stage's envelope, never the history
  (owner, 2026-09-04: "every level reads context - yes, but we cherry
  pick it - its about the right context at the right place at the right
  time"); a read job gets a fileset, never the tree (the meter's unit
  C); the withholding the ruling D-FIREWALL-1 demands is proved both
  ways. Batch 1's multi-input fix is proven live, so inputs stay
  separate files.
- The lane's names the driver would otherwise carry (trunk branch,
  worktree root, check name, models, efforts, the security model, walls
  per stage) come from one lane conf (`.dev/wip/scope-lane-conf.md`):
  the conf is this scope's first unit, the driver its second.
- Everything the driver does is a record: which stage, which record,
  what it landed, why it stopped; the findings ledger is fed at every
  review stage with `findings.py import`.
- Bucket: M for the driver, S for the conf. Guarantees the driver must
  declare and keep (docs/verified-couplings.md): a stage's input never
  contains the withheld artifact; a landed commit is a descendant of the
  stage's base; a stage runs the model and effort the conf names; the
  driver's own exit classes are the wire's four.

## Boundaries the owner set

- No PHP or Symfony work until the owner is comfortable with the
  machinery; the driver's first real run is a lane slice, and its
  proving ground after that is the fixture repository (a Symfony app in
  its own repository with the lane installed), not this project's code.
- The lane is bounded: this is one lever over existing levers; no new
  kernel responsibility; the process document stays the law of the
  order.
- Tests and skeptic never see the implementation (D-FIREWALL-1).

## Acceptance, measurable

- `ladder.sh <scope> <branch>` on a lane S slice runs from tests to draft
  PR with no session action between stages; the records show every
  stage launched through the dispatcher with the conf's model and
  effort, and every landed commit authored by the owner.
- A planted refusal at any stage stops the driver on the wire naming the
  stage and the record; `ladder.sh resume <record>` continues from there.
- A planted second "changes" verdict after the fix round stops the driver
  with the findings in the ledger and no further dispatch.
- Every name the driver uses is read from the lane conf; `grep` for the
  trunk name, the worktree root, the check name and any model id over the
  driver finds none.
- Every lane suite green; `ruff check .` clean.
