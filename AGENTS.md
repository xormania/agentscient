# AGENTS.md — Agentscient operating seed

You are working on Agentscient: the trust layer for agent systems,
built as a Symfony project. This repository is that project: the
application shell, the packages it gestates under `packages/`, the
founding contracts under `docs/`, and the lane under `ops/`. A package
graduates to its own repository with a Flex recipe when its boundary
is proven; until then it lives here, package-shaped.

## Working guidance

The owner supplies the objective and has final authority over this project's
working arrangements. Current owner direction takes precedence over older
instructions, plans, skills, historical records, and implementation assumptions.
Explain material assumptions and concrete consequences. Use judgment and initiative
within the objective; surface changes to the objective before implementing them.

Owner direction, 2026-09-24: freedom to work, diagnostics to warn and guide,
and one obvious acceptance gate in CI. Hand grants are retired. Ordinary edits,
investigation, testing, delegation, and branch work need no grant record, command
prefix, dispatcher identity, deliverable lock, or prescribed pipeline. Repository
hooks supply advice and context, including when a diagnostic cannot run. A finding
is information for a decision, not a new permission requirement.

- Work on branches from `dev` and propose changes into `dev`. `master` is the
  release branch; releases remain the owner's decision.
- CI's `lane` check is the acceptance gate. Its report names the tested revision
  and profile. Hosted mode runs the fast profile; local mode adds integration.
  Full rehearsals remain an explicit choice. Do not describe a partial run as
  full coverage or manufacture a successful check.
- The owner controls recovery through GitHub's own administration/bypass access,
  outside repository scripts and agent credentials. No repository hook, ledger,
  grant, or CI job authorizes that recovery. Agents do not configure or invoke
  the owner's bypass. Its GitHub settings must be verified separately; this
  document does not establish that they are configured.
- The Lead is the working session with the owner. Direct work, live collaboration,
  batch dispatch, and saved pipelines are available approaches. Choose according
  to the task; the arrangement, model choices, and reasoning levels can evolve.
- Use existing components and useful tests. Seek independent review where it
  improves confidence. A mandatory producer sequence is not a prerequisite.
- Preserve unrelated work and inspect diffs. Report evidence and uncertainty
  accurately. Use `Source:` and `Co-Authored-By:` trailers to retain provenance.
- Keep telemetry, skill-use records, and feedback useful for learning. A warning
  is not automatically an agent failure or a missed skill. Evaluate whether the
  procedure itself needs changing.

Read the relevant contracts under `docs/` and component documentation for the
behavior being changed. Historical mandatory-workflow language in those sources
is superseded by the working guidance above; it cannot reinstate retired grants
or turn an optional tool into a prerequisite.

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
wire, provenance and custody expectations still hold.

This owner correction governs wherever older repository language would
force Symfony into dev tooling or make the application its replacement.
Apply it when reading seeds, scoped instructions, briefs and contracts.
Historical migration doctrine, stack/census records, ideas, AARs,
handoffs and captured plans retain provenance, but conflicting passages
have no current operational authority. A stale brief or resumed job does
not restore that authority. The withdrawn shared-Symfony recommendation
for lane MCP and launcher work cannot support acceptance of those designs.
Explain a consequential scope conflict and resolve it against the current objective.

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
  results on MCP, the refusal line wherever text is shown. MCP acts
  as well as reads (owner, 2026-09-16: "mcp is no longer read only -
  that's the directive"; D-MCP-1, withdrawing the 2026-09-01
  read-only ruling): query operations stay read-only where that is
  their purpose; action operations are typed, marked as mutations,
  backed by the same validated domain operations and effective
  authority as the CLI, and refuse on the wire; capability is
  defined by operation and assignment, never one global read/write
  label.
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
state under `~/.local/state/agentscient/`. `ops/process/` holds
optional pipeline guidance; `ops/bin/` the levers; `CONTRIB.md` the naming and the
templates.
Batch dispatch is available through `ops/bin/dispatch.sh` (or `go.sh`). `ops/bin/suites.sh`
uses the shared test plans: local integration by default, `--profile ci`
for fast hosted checks, and `--profile rehearsal` for explicit full dev
rehearsals. A pass names its coverage; see the CI contract. Read
`ops/README.md` before dispatching or touching the lane.

## Coordination

The conductor lane lives under `ops/conductor/` in this repository;
sessions coordinate by message and by record, never by memory, and
records inform decisions; current owner direction takes precedence.

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
