# Agentscient

**The trust layer for agent systems.**

Agentscient develops the contracts, evidence, independent review, and context
custody needed to judge agent-produced work. Its central question is how to
establish what an agent was allowed to do, what it actually did, and what
evidence supports accepting the result.

This repository contains a Symfony application shell and a working development
lane built in Python and Bash. The lane dispatches harness workers, records
their results, supports independent testing and review, and serves operational
observations. The product architecture brings these capabilities into Symfony
packages, preserving their contracts as each implementation moves.

## Current status

The implementation inventory below was checked on **2026-09-05** against
`dev` at `fbdbacfe0ed956fc7f8e65b222d0a7df41886f8f`. It describes that tree;
it does not assert the health of a running service or a current CI result.
The [verification notes](#verification-notes) name the commands and sources.

| Area | Available in this tree |
| --- | --- |
| Symfony application | A bootable FrameworkBundle application, Console and HTTP entry points, environment configuration, and Composer lockfile. Application code under `src/` consists of `Kernel.php`. |
| Product packages | No package manifests under `packages/` yet. The refusal wire is the proposed first bundle. |
| Development lane | Harness dispatch, snapshot preparation, job envelopes and records, usage and budget tooling, hooks, guards, and synthetic fixtures under `ops/devlane/`. |
| Conductor instruments | Onboarding, decisions and handwork records, PR checks, branch census, landing and ladder tools, watchdog, and configurable condition monitor under `ops/conductor/`. |
| Lane MCP | A Python stdio server with four read-only tools and matching resources, backed by explicitly selected local sources. It also exposes the same queries through a CLI. |
| Application diagnostics | Symfony AI Mate and its Symfony extension, installed as development dependencies and invoked through `vendor/bin/mate`. |
| Tests and CI | Python lane suites and a two-job GitHub Actions workflow (`lane` and `app`). PHPUnit is configured for the application and future packages; the current tree has no PHP test cases. |

Product API resources, a TUI, the Symfony workflow engine, and Symfony-based
dispatch are planned. The existing lane MCP server is a separate implementation
from those future projections. There is no product UI or product API to try in
the application shell yet.

## The contracts

Read [AGENTS.md](AGENTS.md) and [docs/](docs/) before changing behavior.
They establish the boundaries against which implementations are evaluated.

| Contract | What it specifies |
| --- | --- |
| [Wire](docs/wire.md) | Typed outcomes and refusals that state what was expected, what was found, and what is needed. |
| [Workflow](docs/workflow.md) | Declared state graphs whose transitions name an actor class, evidence duty, failure class, and gate. |
| [Probes](docs/probes.md) | Deterministic handover checks, including an explicit distinction between absence and an unreachable source. |
| [Concerns](docs/concerns.md) | Reviewers with one defined charge, findings grounded in quotation pairs, and calibration against planted faults and clean examples. |
| [Verified couplings](docs/verified-couplings.md) | Declared dependencies checked for closure, shape, behavior, freshness, permission, and blast radius. |
| [Symfony mapping](docs/mapping.md) | The package reuse plan and the remaining project-specific work. Its version measurements are dated; remeasure them before relying on them. |

The wire defines these outcomes for components that implement it:

| Exit | Outcome | Meaning |
| --- | --- | --- |
| `0` | Success | The requested action completed. |
| `1` | Finding | The action completed and produced findings. |
| `2` | Rejection | The component refused before acting. |
| `3` | Abort | The action stopped partway through, preserving durable partial results. |

A conforming CLI refusal is one line on stderr, with stdout empty:

```text
class: expected <what>; found <what>; needed <remedy>
```

The [instrument conventions](ops/conductor/instrument-conventions.md) apply
this contract to participating lane tools. Consult each entry point's contract:
older wrappers retain different exit conventions, so the table is not a claim
that every script in the repository already conforms.

## Architecture and repository layout

Symfony is the target framework for the product. The standing design uses
Symfony's existing components, including Workflow and the Symfony AI Platform,
before introducing custom machinery. Each capability is intended to expose
Console, TUI, MCP, and API projections of the same service and contract. MCP
serves context and diagnostics; the CLI and API perform actions.

Packages begin under `packages/<name>/` with their own `composer.json` of type
`symfony-bundle`, README, and tests. The root Composer manifest declares a
`packages/*` path repository. Sibling packages must depend on one another through
Composer. A package graduates to its own repository and Flex recipe when its
boundary is proven. See [the package conventions](packages/README.md).

The Python lane is the existing functional reference for these future Symfony
implementations. A replacement must pass the inherited conformance requirements
before the incumbent is retired. External capabilities are intended to remain
replaceable through a declared contract, a live probe, and a verified mock.

| Path | Purpose |
| --- | --- |
| `src/`, `config/`, `public/`, `bin/` | Symfony application code, configuration, HTTP entry point, and Console entry point. |
| `packages/` | Future product bundles, composed through Composer path repositories. |
| `tests/`, `phpunit.dist.xml` | Application test bootstrap and PHPUnit discovery configuration. |
| `docs/` | Founding contracts and the Symfony capability mapping. |
| `mate/` | Mate configuration, extension registry, and diagnostic instructions. |
| `ops/bin/` | Operator entry points for dispatch, ladders, board, fixtures, and suites. |
| `ops/devlane/` | Dispatch, harness, task, telemetry, hooks, guards, fixtures, and infrastructure files. |
| `ops/conductor/` | Instruments, contracts, tests, ideas, handoffs, and after-action reports. |
| `ops/process/` | Contract, test, implementation, review, and evidence-production disciplines. |
| `.github/workflows/ci.yml` | The repository's `lane` and `app` CI jobs. |
| `ops/archive/`, `.dev/wip/`, `.dev/records/dispatches/` | Historical material and retained captures. Read records with their provenance; preserve captured bytes. |

Some carried documents describe earlier implementations or proposed work.
In particular, the workflow specifications and process examples do not establish
that their `wf.py` commands are available: that executable is absent from this
tree. Use the standing rulings and the checked implementation inventory when
interpreting those records.

## Getting started

### Requirements

- **Application development:** Composer 2 and PHP 8.4.1 or later within the 8.4
  series. The root manifest declares PHP `>=8.4`, while locked Symfony and
  PHPUnit packages require `>=8.4.1`. [Mate's configuration](mate/config.php)
  currently requires the 8.4 major/minor runtime. Use Composer's platform check
  below to verify the required extensions.
- **Lane development:** Python 3, Bash, Git, and Unix command-line utilities.
  [Ruff configuration](ruff.toml) targets Python 3.12 and requires Ruff
  `>=0.16,<0.17`. Live process checks use Linux `/proc`; detached dispatch uses
  `setsid` and `nohup`.
- **GitHub observations and PR operations:** an installed, authenticated `gh`
  CLI with access to the repository. Onboarding reports unavailable sources
  explicitly when GitHub or local stores cannot be read.
- **Harness dispatch:** an installed and authenticated supported harness
  (`grok`, `codex`, or `claude`), with an operator-selected model and identity.
  The local MCP and monitor configuration examples do not require a harness.
- **The CI toolchain:** PHP, Composer, Python, CUE, `jq`, and Ruff are checked by
  the workflow on self-hosted runners. Individual tools can require a subset.

### Create an owned worktree

Development targets `dev`; `master` is the release branch. The main checkout is
a reference tree. Create a separate worktree for each line of work:

```sh
git clone --branch dev https://github.com/uscient/agentscient.git
cd agentscient
git worktree add -b repo/my-change ../wt/ag-my-change origin/dev
cd ../wt/ag-my-change
```

For an existing clone, fetch `origin` before creating the worktree. Do not switch
or modify another session's checkout. The commands below run from the root of
your owned worktree.

### Boot and inspect the application

```sh
composer validate --strict
composer check-platform-reqs --lock
composer install --prefer-dist --no-progress --no-interaction
php bin/console about
vendor/bin/mate tools:list
vendor/bin/mate tools:call symfony-services --query=router --limit=10 --format=json
```

Composer installs from [composer.lock](composer.lock) and runs the configured
cache-clear and asset-install scripts. The application pins Symfony to `8.1.*`;
the Mate dependencies are pinned exactly to `0.13.0`.

Local application overrides belong in `.env.local`, which is ignored by Git.
The tracked `.env` defaults to `APP_ENV=dev` and contains an empty `APP_SECRET`.
Supply environment-specific secrets through local configuration when needed.

Always invoke Mate as `vendor/bin/mate`. Discover parameter names with
`vendor/bin/mate tools:inspect TOOL`; see
[Mate's agent instructions](mate/AGENT_INSTRUCTIONS.md) for the diagnostic
surface. Application data returned by diagnostics is evidence to inspect,
including any `untrusted_data` payload.

## Using the development lane

Read [ops/README.md](ops/README.md) before operating the lane and
[the dispatch trust boundary](ops/devlane/AGENTS.md) before launching work.
Workers run with host authority in prepared snapshots. Snapshot and configuration
isolation do not provide OS containment; this lane is for trusted,
maintainer-directed work. An isolated environment for untrusted contributors
has not been implemented.

### Onboarding and observation

```sh
python3 ops/conductor/tools/onboard.py
```

The brief reports the reading list, decisions register, handwork ledger, open
PRs, dispatch observations, current branch, and latest available AAR calibration
section. It is a read and needs no identity. Exit `1` means the brief includes
absences or sources that could not be measured; read those lines before relying
on the result. A fresh clone does not contain the operator's state databases.

Useful entry points and their detailed contracts:

| Need | Entry point | Contract |
| --- | --- | --- |
| Session brief | `python3 ops/conductor/tools/onboard.py` | [Onboard](ops/conductor/onboard-lever.md) |
| Decisions register | `python3 ops/conductor/tools/decisions.py report` | [Decisions](ops/conductor/decisions-register.md) |
| Branch census | `python3 ops/conductor/tools/branches.py census` | [Branch census](ops/conductor/branch-census.md) |
| PR check observation | `ops/conductor/tools/watch.py` | [Watch](ops/conductor/watch-lever.md) |
| Dispatch and forge watchdog | `ops/conductor/tools/watchdog.py` | [Watchdog](ops/conductor/watchdog-lever.md) |
| Scheduled conditions and queued events | `ops/conductor/tools/monitor.py` | [Monitor](ops/conductor/monitor-lever.md) |
| Recorded lane context | `ops/conductor/tools/lane_mcp.py` | [Lane MCP](ops/conductor/lane-mcp-lever.md) |
| Artifact landing and audit ladders | `ops/conductor/tools/land.py`, `ops/bin/ladder.sh` | [Land](ops/conductor/land-lever.md), [ladder](ops/conductor/ladder-lever.md) |

### Configuration and dispatch

[ops/lane.conf](ops/lane.conf) holds the shared lane configuration.
Machine-specific overrides belong in the ignored `ops/lane.local.conf`.
The reader resolves environment overrides before local and tracked values;
lane identity keys cannot be changed in the local file. These files use
literal `KEY='value'` assignments. Use `LANE_CONF` to select a different base
configuration, and consult [the reader](ops/conductor/tools/laneconf.py) for
the accepted keys and validation.

Delegation goes through `ops/bin/dispatch.sh` or its short front end,
`ops/bin/go.sh`. The [job registry](ops/devlane/task/jobs.json) defines jobs
such as `plan`, `author-tests`, `check-tests`, `implement`, `adversarial-review`,
and `security-audit`. The `go.sh review` intent launches the two review jobs.
Models and effort are resolved at dispatch from explicit flags or lane
configuration; the job registry does not choose a model.

For a preview, set `WF_AGENT` to the actual producer's full `Name <address>`
identity, and set `MODEL` to the intended model identifier. Write the task to
a scope file, then inspect the resolved invocation:

```sh
printf '%s\n' 'Plan the change described in the supplied contract.' > /tmp/agentscient-scope.md
bash ops/bin/dispatch.sh \
  --worktree . \
  --job plan \
  --harness codex \
  --model "${MODEL:?set the intended model identifier}" \
  --agent "${WF_AGENT:?set the actual producer identity}" \
  --stage plan \
  --scope-file /tmp/agentscient-scope.md \
  --dry-run
```

`--dry-run` prints the resolved launcher arguments and environment. Removing it
launches the job and can incur model usage. The scope is bounded to 1024 bytes
by the tracked configuration. Use `--input FILE` for supporting artifacts and
`--follows ID` to identify predecessor records. `--detach` returns a durable job
identifier; retain it before scheduling further work. See
[the dispatch contract](ops/devlane/dispatch/CONTRACT.md) for status, wait,
collection, and resume semantics.

Runtime state normally lives beneath
`${XDG_STATE_HOME:-$HOME/.local/state}/agentscient/`, outside the source tree.
Dispatch also accepts `DISPATCH_JOBS`; MCP and monitor source paths are explicit
configuration. Some older instruments retain their own location rules, such as
the handwork ledger's home-relative store. Check the relevant contract before
moving or resetting state.

### Monitor and MCP

The monitor evaluates configured schedules and conditions and queues bounded
observations. Its adapters cover selected dispatch records, one selected Codex
usage rollout, and GitHub rate-limit readings. There is no model call per tick
and no automatic agent wakeup. Validate the supplied example with:

```sh
python3 ops/conductor/tools/monitor.py \
  --config ops/conductor/monitor.example.json check
```

All source monitors in that example are disabled. To operate it, prepare an
owned configuration with explicit sources, validate it, and use the documented
`run` and `digest` verbs. Running persists observations and requires identity;
digest reads acknowledge events only when `--ack` is supplied. A running loop
reloads its configuration. Boot-time service management is not supplied.

The lane MCP server exposes:

| Tool | Resource | Reading |
| --- | --- | --- |
| `lane_brief` | `lane://brief` | Selected record summaries and one alert page. |
| `lane_record` | `lane://record/ID` | One explicitly configured dispatch record summary. |
| `lane_alerts` | `lane://alerts` | A bounded alert page for the configured consumer. |
| `lane_usage` | `lane://usage` | Aggregate token and context measurements from the selected rollout tail. |

Try the same read service without registering an MCP client:

```sh
python3 -B ops/conductor/tools/lane_mcp.py \
  --config ops/conductor/lane-mcp.example.json check
python3 -B ops/conductor/tools/lane_mcp.py \
  --config ops/conductor/lane-mcp.example.json query lane_brief
```

The example selects no jobs and disables all source paths. Its brief therefore
contains no records and reports the monitor database as unarmed. Successful
query execution does not imply that a live source was available.

For a stdio MCP client, use the same program with `--config FILE serve`, with
explicit paths to the program and an owned configuration. Source paths resolve
relative to that configuration file. Restart the server after changing it.
Use the brief first, individual records when needed, and usage on demand.
MCP reads do not acknowledge queued events, execute jobs, or determine PR
readiness; the server has no HTTP listener.

The [MCP contract](ops/conductor/lane-mcp-lever.md#explicitly-deferred-malformed-input-limits)
records known numeric-input and cursor-overflow limits. Its current scope is
operator-selected local data; it does not establish safety for arbitrary
untrusted sources or remote exposure.

## Verification and CI

The shared lane suite entry point is:

```sh
bash ops/bin/suites.sh
```

It runs the registered suite directories concurrently and prints their results
in a fixed order. Set `SUITES_SERIAL=1` for serial execution. This is the same
entry point CI uses; it does not replace the additional checks in
[the workflow](.github/workflows/ci.yml).

The `lane` job also runs:

```sh
python3 ops/devlane/workflow/checks/term_wall.py --root .
ruff check .
python3 ops/conductor/tools/laneconf.py closure
python3 ops/conductor/tools/laneconf.py literals
```

The term wall requires the operator's pattern through `TERM_WALL` or the
ignored `ops/bin/term-wall.conf`. The tracked
[example](ops/bin/term-wall.conf.example) is a placeholder. An absent pattern
is a refusal. The wall checks authored content and every tracked path; captured
content has the specific exceptions documented in [ops/README.md](ops/README.md#the-wall-here).

The `app` job validates and installs Composer dependencies, lints PHP, boots
the kernel, invokes PHPUnit, and checks Mate container inspection. Run PHP tests
with:

```sh
vendor/bin/phpunit
```

At the inventory revision, this prints **“No tests executed!”** Application and
package discovery are configured, but a successful command exit is not evidence
of product test coverage.

The workflow runs on pushes to `dev`, PRs targeting `dev`, and merge groups
for `dev`, using self-hosted runners. PR evidence must describe the tested tree
and the applicable [coverage zone](ops/conductor/coverage-zones.md), including
verification against its merge with `origin/dev`.

## Contributing

[AGENTS.md](AGENTS.md) and [CONTRIB.md](CONTRIB.md) define the operating rules.
The core contribution sequence is:

1. Read the relevant contract and remeasure any package mapping the change
   depends on. Declare a new boundary before implementing it.
2. Work in your own worktree, branched from `dev`, with one line of work per
   checkout. Preserve captured evidence and retained branches.
3. Keep implementation and test producers independent. No producer owns two
   consecutive artifacts; the implementer neither writes nor approves its
   tests. Dispatch delegated work through the lane.
4. Run the applicable checks and record the commands, results, and source SHA.
   Distinguish a clean result from a source that could not be inspected.
5. Include `Source:` and `Co-Authored-By:` trailers on every commit, naming the
   specific model that did the work. Follow the review and attribution rules
   in `CONTRIB.md`.
6. Open a **draft PR into `dev`** with What, Sources, Evidence, and For reviewers
   sections. Mark it ready only when the lineage is stationary and all required
   checks are present and green. Review evidence is tied to a commit and expires
   when that commit changes.

Use merge commits; do not squash or delete branches. Releases are draft PRs
from `dev` into `master`, and only the owner merges them.

### Verification notes

This README's implementation claims were checked against the revision named
under [Current status](#current-status) using the tracked manifests,
configuration, contracts, and entry points. The inventory was inspected with:

```sh
git rev-parse HEAD
git ls-files src config packages tests mate ops .github/workflows
```

During that inspection, `composer validate --strict`,
`composer check-platform-reqs --lock`, the installation and application
diagnostic commands above, both example configuration checks, and the example
MCP brief were run. PHPUnit was also run and reported no tests. These are
dated setup measurements; rerun checks for the tree and environment you use.

## License

[composer.json](composer.json) declares the project license as `proprietary`.
No standalone license file is present at the inventory revision.
