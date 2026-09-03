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

## Standing rulings

- **Symfony is the framework, whole** (owner, 2026-09-03: "we use
  Symfony/ai — we use everything Symfony has to offer"). Every
  capability is built on what Symfony and its ecosystem already ship,
  symfony/ai included. The functionality carried over from the House
  lane is proven; what it needs is organization and abstraction, not
  reinvention. Before any contract is written, the first question is
  which package already covers it; `docs/mapping.md` is the measured
  answer and is re-measured before it is relied on. This supersedes
  the migration doctrine's "harness CLIs stay dispatched subprocesses,
  never language SDKs": model access goes through the symfony/ai
  Platform, whose Claude Code and Codex bridges spawn those same CLIs
  as subprocesses, so the wire and the subprocess hold while the
  abstraction changes. Unchanged: no vendor becomes load-bearing
  (pre-1.0 packages are pinned exactly, probed, and mocked), and the
  model is named at dispatch, never in a table.
- **Four projections of one service** (owner, 2026-09-03: "this is
  about providing cli, mcp and api resources", "and probably a TUI").
  Every capability is exposed as a Console command, a TUI view, an
  MCP resource, and an API resource, each a projection of the same
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
  deferred, not dropped: its pins are kept (Symfony 8.1.*, PHP 8.4) so
  the later move is free, and graduation to sibling repositories and
  the recipes endpoint is a later act, per package, when its boundary
  is proven. This answers the question the estates ruling left open:
  packages gestate here.

## The lane

The operating apparatus lives under `ops/`. `ops/devlane/` is the dev
lane — dispatch, harness, task, telemetry, hooks, guards — carried over
from the House lane as the bounded Python incumbent: every instrument
there is the functional specification for a Symfony Console twin, and
retires only when its twin passes the same conformance row.
`ops/process/` holds the pipeline law; `ops/bin/` the levers.
Delegation runs through `ops/bin/dispatch.sh` (or `go.sh`) and nothing
else — in-session sub-agents are refused by hook. `ops/bin/suites.sh`
is the one answer to "is it green?", here and in CI. Read
`ops/README.md` before dispatching or touching the lane.

## Coordination

The conductor lane for this project runs from the sibling working
repository under the same organization; sessions coordinate by
message and by record, never by memory. When in doubt, the record
outranks recall.
