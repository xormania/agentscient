# Ratification — U0 plan gate (child plan 1a1afa), by the conductor, 2026-08-29

Parent: `agentscient-framework-plan.md` row U0. This file is the complete
ratification available in this tree; it does not claim the presence of a
separate framework-ratification file. All six are design decisions.

| decision | ruling | reason | premise |
|---|---|---|---|
| D-U0-bootstrap-binding | standing | the first vetter cannot be vetted by itself until it exists; binding to the parent's prose digest and rebinding in U0's last commit is honest bootstrapping, and `plan.bound-prose` makes the temporary state expire | `measured`: no sidecar exists at this ref |
| D-U0-economics | standing | declared where a human knows it (gate `cost`, `economics.write`), derived where a tool can compute it (carry, change), refused when hand-written — the single-source principle applied to numbers | owner: "these contracts and their economics are important" |
| D-U0-standing-rule | standing, with one addition | `new`/`ratified_by`/`status` on every decision and code blocked while `pending`/`revisit` is the governance mechanism this whole lane needed; addition: `ratified_by` names the conductor for design decisions and the owner for policy ones (owner: "not me - you have to know how to design a framework") | `read`: parent §3.2 |
| D-U0-extract-form | standing | fixed-header tables plus fenced `json plan:<field>` blocks make extraction deterministic; byte-drift refusal keeps prose and sidecar one artifact | `assumed` by the planner; the fault corpus tests it |
| D-U0-vet-shape | standing | raw-presence → `cue vet -c` → relational rules, first failure wins, `--definition` parameterised so `#Workflow` reuses it — the 5d87918 lesson made a pipeline | `read`: after-action 5d87918 |
| D-U0-layout | standing | `ops/capabilities/` beside the old apps, plans under `plans/`, contracts with `examples/` and `faults/` — the anatomy the parent prescribes, applied to the framework itself | `read`: parent §2.1 |

Code stage may proceed once tests and the skeptic are done.

## Closure 2026-08-30 (conductor)
U0 is done at `3a61777` (+ the review record): two Codex fix cycles on two review rounds and a final executing review (`80dca4`): five §7 gates exit 0, 69/69 with cue, 45 skipped / 0 failed without cue, ruff clean; 2 P1 + 3 P2 closed, 1 P2 covered by D-U0-standing-rule. One residual, deferred by ruling: the derived-economics formula (`--economics` prints unmultiplied bytes and summed direct-child minutes) — the owner has the yield math ("i have the semantic yield math"); the formula lands with the Meters `yield` unit, not here. Unit branch stays on GitHub until the group PR (assumed policy).
