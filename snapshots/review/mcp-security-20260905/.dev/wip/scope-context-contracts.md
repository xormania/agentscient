# Scope — context is a contract, and the contract runs

Formed in chat with the owner on 2026-09-04. The owner's words are
verbatim. Every fact was measured by the session, on the day, in this
repository. Nothing here says how.

## What the owner said

> every level reads context - yes, but we cherry pick it - its about
> the right context at the right place at the right time

> in the previous house system - we defined context as cue contracts -
> so that context was guardable - thoughts?

> great - so i take the time to figure a good idea - and it never gets
> enforced!? wtf

## What was measured

- `ops/devlane/harness/context.cue` defines `#Context`, the closed
  shape of an observed dispatch (harness, isolation applied and
  observed, what the snapshot holds, the instruction files in force,
  with absence spelled as `declared_absent`), and `#Dispatchable`, the
  law: the subset of shapes that may launch. `evidence.cue` sits beside
  it. Both came over from the previous repository. The file's header
  records why: on 2026-08-23 an isolation step evaluated an absent
  module's empty output, succeeded, and a worker left carrying the
  operator's whole configuration. "The guard was fine. The absence of
  the guard was invisible."
- Nothing runs it. `grep` over `ops/conductor/tools/dispatch.sh` and
  `ops/devlane/dispatch/launch.py` finds no `cue vet`; only documents
  under `ops/docs/` and `ops/conductor/` mention it. `cue` v0.17.1 is
  on the host and CI prints its version on every run.
- The launcher's only context guards are caps: `scope-cap` (1024
  bytes) and `cap-out` from `wires.py`. Withholding is proved by
  pattern lists per job, both directions, and nothing records what a
  job was given as a manifest.
- The session's hand-built inputs grew by accretion: 528 lines for
  the conf unit, 1,033 for the driver's run C, 1,413 for the ladder
  fix round, 1,472 for the fixture fix round, each carrying the prior
  contract, findings and rulings. The driver's own contract says a
  stage receives the scope, the plan section for its unit and the
  previous stage's envelope, never the history. Nothing enforced that
  on the session.

## What the owner wants

- First, the gate the copy lacked: every contract in the tree (a
  `.cue` definition, a lever contract under `ops/conductor/`) names its
  consumer, the instrument or gate that runs it, and a fixture that
  proves it fires; a contract with no consumer is a finding of a
  closure check that runs in the suites and in CI, the couplings
  contract's first obligation applied to contracts themselves. Owner,
  2026-09-04, on learning the copy carried the definition without its
  gate: "why leave out the important part?" The copy was judged by
  files present and suites green; nothing asked who runs the file.
- Every dispatched job carries a context manifest: one entry per
  section of its input (the scope, the plan section, the previous
  envelope, findings, the named command), each with its source (a
  record id or a tracked path), its digest and its size; the given and
  withheld pattern lists with their proof; the harness and isolation
  facts `#Context` already names. Absence is spelled, never omitted.
- The manifest is vetted before launch against the job kind's
  definition in CUE: the definitions extend `context.cue` with one
  closed shape per job kind (author-tests, check-tests, implement, the
  audits, plan, adjudicate) naming which sections may appear, the size
  cap of each, and that no history section exists. Extra context does
  not evaluate; missing context does not evaluate. A failed vet is a
  refusal of class `context` on the wire, before the harness starts,
  naming the field.
- The launcher writes the manifest into the record and the job
  directory, so every run is a row saying exactly what its worker saw,
  and the meter can report context size per stage beside minutes and
  tokens (the calibration table gains a column).
- The dispatcher builds the manifest for a hand-launched job from its
  arguments; the driver builds it per stage by construction, so the
  driver cannot feed a stage the history even if a session would.
- The definitions are tracked artifacts under the concerns rule:
  identical run to run until deliberately changed, every change a
  reviewable diff, with planted fixtures (a manifest with an extra
  section, one with a missing digest, one over cap) the gate must
  refuse and a clean one it must pass, in the suites and in CI.

## Boundaries the owner set

- Enforced, not documented: a definition nothing runs is the finding
  this scope exists to close.
- The wire holds: class, expected, found, needed on every refusal.
- No vendor becomes load-bearing: `cue` is consumed through the lever
  and a probe of its version; a host without it is a declared absence,
  not a silent pass.
- The full ladder, never a hand patch.

## Acceptance, measurable

- A planted job input with a section the job kind does not allow, one
  over its cap, one whose digest does not match its source, and one
  carrying a `history` section each stop the dispatcher with a
  `context` refusal naming the field; a clean manifest launches.
- Every record minted after this carries `context.manifest`; the
  meter's report shows context bytes per stage.
- The driver's stages produce manifests that vet clean for a planted
  ladder in `test_ladder_lever.py`.
- `bash ops/bin/suites.sh` green; `ruff check .` clean; the conf's
  closure and literals checks clean; CI runs the vet fixtures.
