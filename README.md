# Agentscient

**The trust layer for agent systems** — built as Symfony packages,
composed package-first, headed for a snapshot-per-request runtime.

Agent frameworks ship orchestration: queues, workers, tool calls.
What none of them ship is trust — the machinery that makes a system
of stochastic, vendor-supplied, mutually reviewing agents *safe to
believe*. Agentscient is that layer:

- **Contracts first.** Every component boundary is a declared,
  verified coupling. Disjointed code composes because composition is
  checked at the edges, never assumed in the middle.
- **Evidence, not logs.** Every state transition carries an evidence
  duty; every claim is produced by a command at the moment of
  writing; absence is declared, never inferred from silence.
- **Refusal as interface.** Components refuse rather than guess, on
  a one-line wire with typed failure classes.
- **Adversarial by construction.** Producers are firewalled from
  reviewing their own work; stochastic checkers are calibrated on
  planted faults and clean neighbors; a hypocrisy sweep diffs what
  is declared against what is practiced — for every actor, owner
  included.
- **Custody.** Who may see what, who may produce what, and how any
  piece of context earned its place are queryable properties, not
  conventions.

## Status

Genesis. This repository currently contains founding contracts only
— no code. The documents under `docs/` are the law the first
packages will be built against, extracted and de-instanced from a
working conductor lane that ran these disciplines by hand first.

## The founding documents

| document | governs |
|:--|:--|
| `docs/wire.md` | the refusal wire and the four outcome classes |
| `docs/workflow.md` | the workflow genus: declared graphs with actor, evidence, failure, and gate per transition |
| `docs/probes.md` | deterministic hand-over: probe corpora, runners, and session-close manifests |
| `docs/concerns.md` | single-concern reviewers as fixed, calibrated artifacts |
| `docs/verified-couplings.md` | the six verification obligations of every edge in the code graph |
| `docs/mapping.md` | what we have, what Symfony has, what is left — measured against Packagist |

Architecture doctrine: package-first composition per
[MinSpec](https://github.com/minspec). Runtime road: plain
supervised processes today; snapshot-per-request isolation as the
runtime matures.
