# AGENTS.md — Agentscient operating seed

You are working on Agentscient: the trust layer for agent systems,
built as a Symfony project. This repository is that project: the
application shell, the packages it gestates under `packages/`, the
founding contracts under `docs/`, and the lane under `ops/`. A package
graduates to its own repository with a Flex recipe when its boundary
is proven; until then it lives here, package-shaped.

Read `docs/` before working: the wire, the workflow genus, probes,
concerns, and verified couplings are the law every change is built
against. The founding rule: contracts first — no code lands whose
boundary is not a declared, verifiable coupling.

## Ground rules

- **dev is the trunk; master is the release.** Branch from `dev`,
  open PRs into `dev`, draft-first: a PR opens as a draft and is
  marked ready only when its lineage is stationary and its checks are
  green. `master` is the default and release branch: a release is a
  draft PR from `dev` into `master`, opened by a session for a group
  of landed work and merged by the owner alone. No squash merges,
  never a deleted branch.
- **Every commit carries its trailers**: `Source:` (original, a
  `repo@sha` pointer for adapted content, or `owner <date>`), and
  `Co-Authored-By:` naming the specific model — the credited agent,
  vendor noreply address. Work you did not do gets no trailer with
  your name.
- **Every factual claim is produced by a command at the moment of
  writing**, stamped with what it was measured against. Absence is
  declared, never inferred from silence: distinguish "looked and
  found nothing" from "could not look."
- **No producer owns two consecutive artifacts.** Whoever writes an
  implementation neither writes nor approves its tests. This binds
  every producer, the founder included.
- **Refusals are the interface.** Components refuse rather than
  guess, on the wire, with expected–found–needed stated.
- **No vendor becomes load-bearing.** Every external capability is
  consumed through a contract, a probe, and a verified mock, and is
  removable for the cost of a configuration line.

## Lane boundary and precedence

Owner, 2026-09-05: "Symfony - no, this is dev-lane right now - we're
not using symfony app"; "previous models seemed to think that we'll
be using the prod-lane to replace the dev-lane as we go - no, this is
NOT the case."

Dev tooling under `ops/` and the prod application are independent.
The dev lane must operate without the Symfony application, its kernel,
container, services or `vendor/`. It evolves independently; no automatic
twin, strangler, retirement or graduation into application machinery is
required or implied. The prod lane develops the Symfony application and
its packages under the application rulings below.

Work profile describes the work's boundary; it is independent of harness,
model and conductor/worker role. Using dev tooling to work on the prod
application does not make the tooling part of that application. Both
lanes may read shared contracts and describe or inspect the application;
that permission does not authorize a runtime dependency on it. Shared
wire, provenance, custody and independent-producer obligations still hold.

This owner correction governs wherever older repository language would
force Symfony into dev tooling or make the application its replacement.
Apply it when reading seeds, scoped instructions, briefs and contracts.
Historical migration doctrine, stack/census records, ideas, AARs,
handoffs and captured plans retain provenance, but conflicting passages
have no current operational authority. A stale brief or resumed job does
not restore that authority. The withdrawn shared-Symfony recommendation
for lane MCP and launcher work cannot support acceptance of those designs.
Unknown or conflicting scope must refuse with expected–found–needed,
not silently reclassify the work or seek approval for a forbidden action.

This is the owning instruction boundary. `ops/README.md` carries its
operating references; `docs/verified-couplings.md` carries its dependency
obligation. Mechanical enforcement design belongs to the separate planner;
this documentation correction does not establish a live guard.

## Standing rulings

These framework, projection and package rulings govern the prod application.

- **Symfony is the framework, whole** (owner, 2026-09-03: "we use
  Symfony/ai — we use everything Symfony has to offer"). Every application
  capability is built on what Symfony and its ecosystem already ship,
  symfony/ai included. The functionality carried over from the House
  lane can inform application contracts without replacing that lane.
  Before any application contract is written, the first question is
  which package already covers it; `docs/mapping.md` is the measured
  answer and is re-measured before it is relied on. For application model
  access this supersedes the migration doctrine's "harness CLIs stay
  dispatched subprocesses, never language SDKs": access goes through the symfony/ai
  Platform, whose Claude Code and Codex bridges spawn those same CLIs
  as subprocesses, so the wire and the subprocess hold while the
  abstraction changes. Unchanged: no vendor becomes load-bearing
  (pre-1.0 packages are pinned exactly, probed, and mocked), and the
  model is named at dispatch, never in a table.
- **Four projections of one service** (owner, 2026-09-03: "this is
  about providing cli, mcp and api resources", "and probably a TUI").
  Every application capability is exposed as a Console command, a TUI
  view, an MCP resource, and an API resource, each a projection of the same
  service generated from the same contract. The wire holds on all
  four: exit classes on the CLI, problem details on the API, error
  results on MCP, the refusal line wherever text is shown. MCP stays
  the context-and-diagnostics plane, read-only by construction; the
  CLI and the API act.
- **This is a Symfony project, not a constitutional repository**
  (owner, 2026-09-03: "i don't know where the constitutional came from
  - probably bad assumptions from the other model. This is a Symfony
  project"; and "we'll skip MinSpec for now - we can organize what we
  write here into a package/flex recipe later"). The genesis framing
  of this repository as law-only is withdrawn. Code lives here: each
  package under `packages/<name>/` with its own `composer.json` of
  type `symfony-bundle`, its own tests and README, reaching its
  siblings only through Composer path repositories, never by relative
  import, so that graduation is a subtree split plus a recipe and
  never a refactor. The application shell composes them. MinSpec is
  not used (owner, 2026-09-03: "we're not using MinSpec - i said
  that"); the Symfony pins (8.1.*, PHP >=8.4) stand on their own, and a
  package graduates to its own repository under this organisation with
  its own Flex recipe when its boundary is proven. This answers the
  question the estates ruling left open: packages gestate here.

## The lane

The operating apparatus lives under `ops/`. `ops/devlane/` is the dev
lane — dispatch, harness, task, telemetry, hooks, guards — carried over
from the House lane and maintained independently under the lane boundary
above. Its contracts and conformance obligations hold as it evolves.
`ops/conductor/` is the conductor lane — the instruments, their
contracts, the ideas and hand-off records, the register — with its own
state under `~/.local/state/agentscient/`. `ops/process/` holds the
pipeline law; `ops/bin/` the levers; `CONTRIB.md` the naming and the
templates.
Delegation runs through `ops/bin/dispatch.sh` (or `go.sh`) and nothing
else — in-session sub-agents are refused by hook. `ops/bin/suites.sh`
is the one answer to "is it green?", here and in CI. Read
`ops/README.md` before dispatching or touching the lane.

## Coordination

The conductor lane for this project runs from the sibling working
repository under the same organization; sessions coordinate by
message and by record, never by memory. When in doubt, the record
outranks recall.

The following diagnostic instructions apply to prod application work.
Mate is not a prerequisite for operating or developing the dev lane.

<!-- BEGIN AI_MATE_INSTRUCTIONS -->
AI Mate: project diagnostic tools, exposed through the `vendor/bin/mate` CLI.

- Provenance: this block is generated by `vendor/bin/mate discover`. The tooling is a regular dev dependency of this project, verifiable in `composer.json` (`symfony/ai-mate`); the binary lives at `vendor/bin/mate`.
- Invocation: always run Mate as `vendor/bin/mate`; another interpreter reports on a runtime that is not this application's, and Mate refuses to start under one.
- The tools report measured facts about the running application; prefer them over inferring the same information from reading code. They are described in `mate/AGENT_INSTRUCTIONS.md`.
- Discover the tool surface with `vendor/bin/mate tools:list`, inspect parameters with `tools:inspect <tool>`, and run a tool with `tools:call <tool> --<param>=<value>` (add `--format=json` for machine-readable output).
- Installed extensions: symfony/ai-mate, symfony/ai-symfony-mate-extension.
<!-- END AI_MATE_INSTRUCTIONS -->
