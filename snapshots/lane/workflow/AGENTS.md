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
- **Four projections of one capability** (owner, 2026-09-03: "this is
  about providing cli, mcp and api resources", "and probably a TUI").
  Every capability is exposed as a Console command, a TUI view, an
  MCP resource, and an API resource, each a projection of the same
  capability, generated from the same contract. The wire holds on all
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

## The vocabulary boundary

This file is dev-lane surface. Its vocabulary (work order, gate, stage,
receipt, red/green, chain, claim, marker) stays on dev-lane surfaces: this
file and the other root dev-lane files (`CONTRIB.md`, `README.md`,
`ruff.toml` — a lint contract cannot name the paths it configures
without the vocabulary), everything under `ops/`, `.dev/` and `.git/`, the
root tool-configuration dot-directories (`.github/`, `.claude/`,
`.serena/` — they describe how the repo is worked on, not what the
product is), and dev-lane commit messages. The vocabulary-wall check
enforces this boundary; its allowlist and this sentence must name the
same surfaces. In this project the reserved words are also the product's
own, so the wall stands as mechanism until the lexicon is ruled (I-007).

## The development process

The canonical process documents live in `ops/process/`, shared by every
harness that works this repo — Claude, Codex, Grok. Roles are
interchangeable: any harness may lead a change. The process names roles;
the owner names the model that fills each. The instructional entry point
for the lane and each of its apps is `ops/guide/README.md`.

| document | what it governs |
|:--|:--|
| `ops/process/pipeline.md` | **the sequence**: who produces scope, plan, tests and code, in what order, and what each is denied |
| `ops/process/tdd.md` | the wf-governed red→green loop: honest reds, sealed frozen sets |
| `ops/process/bdd.md` | Given/When/Then scenarios before tests or code, traceable to tests |
| `ops/process/cross-review.md` | who may review what, the detached-snapshot rule that enforces it, and who rules on a CHANGES verdict |
| `ops/process/roles/test-author.md` | writes failing tests from the contract, never from the code |
| `ops/process/roles/test-skeptic.md` | refutes the claim "these tests would catch the code being wrong" |
| `ops/process/token-thrift.md` | where tokens go, and the checklist for spending fewer |
| `ops/process/worth.md` | what a window of work cost, joined to what it produced |
| `ops/process/agentic-management.md` | the conductor operating framework: delegation, controls, exceptions, and verification span |

The rule underneath all of them: **no producer owns two consecutive
artifacts** — the harness that writes the implementation does not author
or approve its own tests when a second harness is available.

## The lane

The operating apparatus lives under `ops/`. `ops/devlane/` is the dev
lane — dispatch, harness, task, telemetry, hooks, guards — carried over
from the House lane as the bounded Python incumbent: every instrument
there is the functional specification for a Symfony Console twin, and
retires only when its twin passes the same conformance row.
`ops/conductor/` is the conductor lane — the instruments, their
contracts, the ideas and hand-off records, the register — with its own
state under `~/.local/state/agentscient/`. `ops/devlane/workflow/` is the engine (§The engine's surfaces);
`ops/capabilities/` the framework seed; `ops/docs/` the shelf;
`ops/process/` holds the pipeline law; `ops/bin/` the levers;
`CONTRIB.md` the naming and the templates.
Delegation runs through `ops/bin/dispatch.sh` (or `go.sh`) and nothing
else — in-session sub-agents are refused by hook. `ops/bin/suites.sh`
is the one answer to "is it green?", here and in CI. Read
`ops/README.md` before dispatching or touching the lane.

## The engine's surfaces

The workflow engine is `python3 ops/devlane/workflow/wf.py` — the
ledger of work orders, stages, gates and receipts, with `wf --help`
listing the verbs — and it is served read-only over MCP as the `wf`
server registered in `.mcp.json`:

| tool | answers |
|:--|:--|
| `wf_next` | what stage a work order is in, what evidence is missing, and the exact argv that records it |
| `wf_status` | every work order at a glance, or one in full with its events |
| `wf_log` | the chain, filterable by event type, recording agent and time |
| `wf_agents` | who has recorded what, and who holds a claim right now |
| `wf_checks` | the registered checks and which of them CI runs |

Every tool is a read; there is no writing tool and there will not be
one — the server cannot append to a chain, and that is enforced rather
than intended. Recording evidence is the CLI's job, and the CLI is the
fallback if the server is unavailable. An empty answer is usually
correct: until a work order is opened, `wf_status` returns an empty
list. `wf.db` is a gitignored cache; the tracked export under
`ops/devlane/workflow/chains/` is the evidence, and a tool that says
the database is missing is telling you to run `wf init --rebuild`,
which the registered server does on start.

## Coordination

The conductor lane for this project runs from the sibling working
repository under the same organization; sessions coordinate by
message and by record, never by memory. When in doubt, the record
outranks recall.
