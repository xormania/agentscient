# The workflow genus

A workflow is a declared graph of states and typed transitions,
where every transition names four things:

- its **actor class** — who may move it,
- its **evidence duty** — what record the move must produce,
- its **failure class** — how the move goes wrong, on the wire,
- its **gate** — what must hold before the move is allowed.

Everything else is parameterization. Workflows are declared as data
in a registry and executed by a generic engine; they are never
hand-coded step chains. Any custom create-or-load sequence that
recurs is a workflow waiting to be declared.

## Instances, not inventions

The genus covers, as instances differing only in their type
parameters: artifact lifecycles (draft, review, fix, ratify), job
pipelines, audit ladders, work-item lifecycles, readiness flips, and
standing machines (proposed, ratified, superseded). Owner-class
ratification is a transition class of its own — a Denial that only
one actor may lift — never a stage an engine can traverse.

## Markings

The following terminology is shared. The prod application uses Symfony
Workflow under its application rules; the dev lane implements the genus
independently under [the lane boundary](../AGENTS.md#lane-boundary-and-precedence).
This contract requires neither a Symfony app dependency nor replacement
of dev-lane workflow machinery by an application implementation.

Following the Symfony Workflow model: a **state machine** holds one
place at a time (a sequential ladder); a **workflow proper** may
hold multiple places simultaneously (a parallel fan-out). Both are
one genus with different markings. The marking lives on the subject
and is append-only evidence: where a thing stands is a fact it
carries, with the transition history as its chain.

## The audit ladder pattern

A review workflow worth naming: sequential audits by independent
reviewers, findings fixed and the full floor re-run between stages,
so each later auditor sees a tree stripped of what any reviewer
could find; scarce, expensive review fires only after the ladder.
Each stage's findings-after-filtration is recorded — the marginal
detection series of each reviewer, produced as a byproduct. The
sequence of reviewers is supplied by the operator as declared data
with a per-run override; it is never inferred by the system.
