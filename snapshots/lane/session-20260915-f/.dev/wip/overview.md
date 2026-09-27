# Agentscient — working overview

Supersession notice, owner 2026-09-05:
[AGENTS.md §Lane boundary and precedence](../../AGENTS.md#lane-boundary-and-precedence)
governs current operation. This preserved 2026-09-03 body has no precedence
over `AGENTS.md` or `docs/`; its claim to newer intent does not override them.
Its dev-lane strangler, twin-replacement and verb-by-verb retirement proposal
in §6.3 is withdrawn, including the restriction to blocked-session fixes.
Dev tooling evolves independently of the prod application, without a Symfony
application dependency or required retirement. Conflicting passages below
retain historical provenance only, even when a handoff or AAR points here.

Status: WIP hand-off document, written 2026-09-03 by the conductor
session with the owner, for other AI reviewers. It records the
current specification of the whole project as settled in conversation
so far. It is not law; the law is `AGENTS.md` and `docs/`. Where the
two disagree, this document is the newer intent and the law has not
yet been updated to match.

Every statement carries one of four labels:

- **RULED** — recorded in `AGENTS.md`, `docs/`, or the register.
- **AGREED** — said by the owner in session, not yet recorded.
- **PROPOSED** — the session's recommendation, not yet ruled on.
- **OPEN** — a question nobody has answered.

Measured facts carry the date they were measured. Package versions
are collected in §12 and were measured against Packagist on
2026-09-03.

For reviewers: §11 lists the questions where a second opinion is most
useful. Opinions on anything are welcome, but PROPOSED and OPEN items
are where they change what gets built.

---

## 1. What Agentscient is

**AGREED.** Agentscient is a tool you install once on a machine and
initialize into a project, that runs that project's development with
AI agents under a trust discipline: agents dispatched with a producer
firewall, mechanical gates and single-concern reviewers standing in
for a human reading the code, records and a brief so sessions never
start from memory, and an MCP plane so the harness working in that
project sees measured truth instead of guessing from source.

The owner plans and manages. Agents produce. Nobody reads all the
code; the tests written by one producer, the gates, and the reviewers
do that job.

**AGREED.** The projects it develops are mainly Rust. The first is
`xormania/raddy` (§10.1). Agentscient itself is PHP 8.4 on Symfony
8.1, end to end. No Rust toolchain lives in this repository; a
target's toolchain is configuration the tool executes in the target's
worktree.

**AGREED.** It starts as one Symfony application with Messenger
messages and workers, running locally in one container, because raddy
needs it soon. It is going to be much more (§2.4, §2.5), and the
design must not paint itself into a corner, but the first version is
small.

**RULED, 2026-09-03 in `AGENTS.md`:** Symfony is the framework, whole,
symfony/ai included; every capability is exposed as four projections
of one service (CLI, TUI, MCP, API); this is a Symfony project, not a
constitutional repository; MinSpec is not used.

**AGREED, supersedes part of the ruling above:** packages do not
graduate to their own repositories with Flex recipes. Nobody outside
this repository consumes Agentscient as PHP packages. The product is
the application. See §3.1.

---

## 2. The shape

### 2.1 Install once, initialize per project — AGREED

Installing the tool on a machine gives the `agentscient` command.
Three forms, in the order they become available (§2.5): a link to
this checkout's front script, a PHAR, a static binary. After install
the tool owns two user directories and writes nowhere else:
`~/.config/agentscient/` (identity, default models, harness names)
and `~/.local/state/agentscient/` (every store). No root. Nothing
system-wide. `agentscient doctor` reports which external binaries it
can and cannot find.

Initializing a project: `agentscient init` in the repository detects
the project's shape (a `Cargo.toml` and a justfile for raddy) and
writes a tracked `.agentscient/` directory:

| tracked in `.agentscient/` | purpose |
|:--|:--|
| the config file | gate profile (`just check`, `just bdd`, `cargo audit` for raddy), allowed harnesses and models, the control plane (`local` now) |
| `contracts/`, `workflows/`, `concerns/`, `probes/` | project overrides of the tool's defaults; empty until the project puts something there |

It also writes one line into the harness config: an MCP server entry
pointing at `agentscient mcp` (`.mcp.json` for Claude Code, the
equivalent for Codex; each harness's entry is declared in the tool per
harness, never guessed). Optionally `agentscient hooks install` puts
the commit trailer gate into the clone's git hooks. The result is
committed. Every checkout and worktree of that repository is then an
Agentscient project: the tracked part travels with the tree, the
untracked part lives in the state directory keyed by the repository.

Uninstalling from a project: delete the directory and the line.
Uninstalling from a machine: remove the binary and, if wanted, the two
user directories.

This repository is its own first project: `init` runs here too, and
the tracked half of `ops/` shrinks into `.agentscient/` as the verbs
land.

**PROPOSED:** the tool ships default workflows and concerns; a project
tracks only its overrides. **PROPOSED:** the target-language profile
is target-agnostic with Rust as the first profile.

### 2.2 Four projections of one service — RULED

Every capability is a service; the projections call it and carry no
logic of their own:

- **CLI** — the binary itself; every verb a Console command; the wire
  on every exit.
- **MCP** — `agentscient mcp`, the context-and-diagnostics plane.
  **RULED:** read-only by construction (a compiler pass refuses any
  MCP-exposed service that depends on a writing service). Reads and
  subscriptions over MCP; acts over the CLI.
- **API** — `agentscient serve`; API Platform resources over the same
  services; refusals as RFC 9457 problem details.
- **TUI** — `agentscient board`, on symfony/tui (experimental, no BC
  promise, API unmeasured; the first TUI unit begins by measuring it).

How the MCP server starts (**AGREED**): nobody starts it by hand. The
harness spawns `agentscient mcp` as a child process at session start,
working directory the project, and speaks JSON-RPC over the child's
stdin and stdout. It lives as long as the session. One per session.
No port, no daemon. Inside, the command boots the kernel, resolves the
project (refuses class `repo` if no `.agentscient/`), and hands the
container's `#[McpTool]` / `#[McpResource]` services to the official
SDK's server on its stdio transport. Stdout belongs to the protocol;
logs and refusals go to stderr. Verification is one line: pipe an
`initialize` request into `agentscient mcp` and read the capabilities
back.

### 2.3 Async — AGREED in intent, PROPOSED in shape

Two things the word covers:

1. **Async tool semantics, from day one.** A tool that does work
   returns immediately with a handle; the work is a Messenger message
   in a worker; completion and progress are pushed as MCP
   notifications or resource-updated events. MCP carries notifications
   over stdio too, so this does not depend on HTTP. Doctrine already
   says "terminal states pushed, never polled".
2. **A persistent server, later.** One long-lived process per machine
   holding subscriptions, workers, and live state for every session
   and the board. Streamable HTTP transport, which the SDK supports
   with sessions. **PROPOSED shape:** `agentscient mcp` becomes a thin
   stdio shim that connects to the shared `agentscient serve`,
   starting it if absent, and forwards; sessions never notice. The
   persistent server is designed against Messenger and the SDK's
   transport interfaces only, so raddy's app server (§10.1) becomes the
   runtime under the same code. Built when watch and dispatch exist,
   because those are the first things with something to push.

### 2.4 Runtime road — AGREED

| now | next | later |
|:--|:--|:--|
| one Symfony app, Messenger + workers, one container, SQLite, harness CLIs inside the container with auth directories mounted read-only | raddy as the app server: native messaging and queues, per-message snapshots, host-owned workers and connections | a hosted control plane on AWS; the CLI as its client; workers on spot instances inside Agent Lab containment (§10.2) |

Where a harness runs is a **launcher interface** (§3.6): a Process in
the container today; Agent Lab's `scripts/agent` with the project
mounted and the harness's egress recipe selected later. Agentscient
never knows which it got.

Three day-one choices that keep this road open at no cost: secrets
come from files, never environment (Agent Lab mounts them that way);
a job's inputs enter through the mounted project and its outputs
leave through a commit (the lane already does this); nothing assumes
network, the Docker socket, or host paths — a dispatch that needs
egress declares the destination.

For the AWS form, every store sits behind a Symfony abstraction with a
local and a hosted implementation, so hosting is configuration and
the local loop never needs an AWS account. The seams and the packages
that fill them are in §12. Identity becomes authentication behind a
token; scoping is per project from day one (§3.6). Compute is two
tiers: the server holds streams open (ECS or EC2, not Lambda); jobs are
workers pulling a queue. Versions negotiate: CLI, server, API protocol,
config schema; a mismatch is refused on the wire, never silently
degraded. **PROPOSED, all of it, and none of it is built before the
local loop works.**

### 2.5 Distribution — PROPOSED

1. **Now:** `composer install` in the clone; `ln -s <clone>/bin/agentscient ~/.local/bin/agentscient`. Needs PHP 8.4.
2. **Next:** a PHAR built by Box 4.7, attached to a GitHub release. Needs PHP 8.4.
3. **Later:** a single static binary, static-php-cli 2.8 `micro` SAPI (static PHP prefix concatenated with the PHAR), Linux and macOS. No PHP needed.

Rejected: FrankenPHP embed (a server-first binary; console commands
run as `./agentscient php-cli bin/console <verb>`) and symfony-docker
(answers "how do I serve a web app in containers", which this tool
does not need). The owner intends raddy as the eventual app server.

Symfony as a local application (**AGREED it can; the shape**):
`bin/console` is the app; the kernel boots without HTTP; the working
project is not the install directory (a locator resolves upward from
cwd; config layers defaults, project file, env, flags, and refuses
unknown keys); cache and logs are overridden to the user's state
directory and the container is warmed at build time so the shipped
artifact is read-only; prod environment, debug off; no dotenv; the
API projection is the only surface needing an HTTP runtime.

---

## 3. Architecture

### 3.1 Modules in `src/`, not bundles — AGREED

Code is organized as modules under `src/`, one namespace per
capability, with `src/Platform/` for the shared services. Boundaries
are enforced by deptrac from the first commit: modules depend on
Platform; Platform depends on no module; modules depend on each other
only through declared edges (Watch on Forge; Land on both git
services). Extracting a module into a bundle later is a move, not a
rewrite, and happens only when a boundary is proven. `packages/`
stays empty for now.

### 3.2 Platform services — AGREED (git as two services explicitly; the rest "so far, so good")

| service | wraps | owns | interface? |
|:--|:--|:--|:--|
| **Project** | Config component | resolving `.agentscient/` upward from cwd; the layered validated config; the project id from the git common dir; the state directory; a `ProjectContext` every other service takes | no |
| **Storage** | Flysystem bundle | named stores `state`, `records`, `snapshots`, `artifacts`; local adapter now, S3 later; modules never touch the filesystem directly | Flysystem is the interface |
| **Database** | Doctrine ORM + migrations | one database, a project column on every row; SQLite in the container's volume now, Postgres later; migrations from the first table; Messenger's transport table lives in it; entities belong to modules, the platform owns the connection | no |
| **Logging** | Monolog bundle | a channel per module; JSON to stderr; a processor stamping project, job, identity, session on every record; stdout reserved for the wire and MCP; logs are diagnostics, never evidence; Mate's Monolog extension for session reads | no |
| **Process** | Symfony Process | every subprocess: bounded timeout, captured output, exit mapped to a wire class, and a `Measurement` value back (command, stamp, output) — where "every claim from a command" becomes a byproduct | yes, for replay in tests |
| **Git (local)** | Process | worktrees under `../wt/`; rev-parse, fetch, status, log with trailers, diff, cherry-pick, plumbing commits; typed `Sha`, `Branch`, `Worktree`; the deny list as code (no force push, branch delete, rebase, amend); every crossing recorded | no; tested against real temp repositories |
| **Forge** | HttpClient + MockHttpClient | pull requests, checks per ref, runs, branches, rulesets, review comments over the GitHub API, token from a file; Gitea is the second implementation | yes |
| **Clock** | `ClockInterface` | everywhere, so tests freeze time | Symfony's |
| **Identity** | a value from config | stamped on every message and every write | no |

Rules: no `gh` subprocess (HttpClient is mockable and runs in a
container and on AWS without gh; at `init`, reading `gh auth token`
once to seed the token file is the only place gh appears). Absence is
a type: Forge returns `Unreachable` when it could not ask and an empty
list only when it asked and got none; local git distinguishes "no
worktree for that branch" from "git failed". Evidence flows from
Process, not from callers. Doctrine stays behind repository classes;
no query builder crosses a module's public surface. The two git
services are never merged into one: the local repository and the
forge are different systems with different failure modes, and the
land lever is exactly where one call needs both.

### 3.3 The messaging spine — AGREED

Every job is a message on the Messenger bus. A command never calls a
handler; it dispatches. Every envelope carries an identity stamp and a
project stamp. The transport is one line of config: Doctrine on SQLite
now, SQS or raddy's native queue later. Scheduler sits on Messenger
for cadence (the watch lever's polling). Workflow is the state
machine engine. Nothing is built against a specific transport's
behaviour.

### 3.4 Telemetry — AGREED ("so far, so good")

Three streams, kept apart:

- **Evidence** — the run record: what one job did, append-only,
  produced by the Process service. Read per job.
- **Logs** — diagnostics, per process, to stderr, thrown away.
- **Telemetry** — typed events shaped for aggregation across jobs,
  projects and time. Read never per job, always as a series.

Events (the lane's `ops/devlane/telemetry/` and the conductor's
stores are the spec):

| event | carries | answers |
|:--|:--|:--|
| harness usage | harness, model, tokens in/out/cached, cost, wall time, exit class, job, stage | what a run cost (the symfony/ai bridges already extract usage) |
| job lifecycle | dispatched, started, finished, retries, snapshot ref, resulting commit | throughput, latency, where jobs die |
| gate run | gate, project, duration, pass/fail | flakiness, slow gates |
| finding | stage, reviewer, severity, verified, applied | the marginal detection series per reviewer |
| concern verdict | concern, fixture, caught, missed, false alarm | calibration rates beside every verdict |
| probe outcome | pass, fail, unreachable per session close | whether hand-over works |
| refusal | class, verb, projection | dead classes vs missing levers |
| demand | a handwork declaration, a skill miss, a wish, a manual intervention | what to build next |
| crossing | a context boundary per session | how often the ground moved |
| ruling | proposed, ratified, superseded, latency between | how fast decisions clear |

Derived measures: **worth** = effect (merged PRs, tests added,
findings fixed) over cost (tokens, wall time, human interventions);
**human interventions** per job is the one number that says whether
the system does its job.

Mechanics: modules emit typed readonly domain events on the
EventDispatcher; one recorder subscriber in Platform persists them to
one table (id, time, project, job, session, identity, kind, schema
version, JSON payload, plus promoted columns harness, model, cost,
duration). Direct insert now; the same subscriber dispatching a
message later. A telemetry failure never fails a job. Our events are
our data model; OpenTelemetry is an export target for infrastructure
metrics later. Payloads carry shapes, never content: counts, ids,
hashes, durations; no prompt text, scope text, file contents, or
secrets. **The breaker** is the one place telemetry acts: a Messenger
middleware reads usage against a per-project spend cap and refuses
dispatch with class `breaker` when tripped. Surfaces: `agentscient
usage | pulse | worth` as CLI reports and as MCP resources.

### 3.5 The wire, in code — RULED (`docs/wire.md`), shape PROPOSED

- Four exit classes as one enum: `Ok = 0`, `Finding = 1`,
  `Rejection = 2`, `Abort = 3`.
- A refusal is a thrown `Refusal` value carrying `class`, `expected`,
  `found`, `needed`. A Console error listener turns it into exit 2 and
  one stderr line `class: expected …; found …; needed …`; an API
  Platform normalizer turns it into problem details with the same
  three fields; the MCP mapping turns it into an error result. No
  projection formats a refusal by hand.
- Writing verbs require an `Identity` (`Name <address>`) and refuse
  class `identity` without it. Reads never require one.
- Absence is declared: an empty list only when measured empty; a
  source that could not be read returns `Unreachable`, never an empty
  list and never null.
- A conformance gate runs every component's one refusal-provoking
  invocation and asserts the wire.

### 3.6 The eight day-one choices — AGREED

The whole "design for more" tax, all of it fitting in the first PR:

1. Every job is a message on the bus; commands dispatch, never call.
2. Every message carries who and which: identity and project stamps,
   and both columns on every row, even with one user and one project.
3. Every store is Doctrine, with migrations from the first table.
4. Every file is Flysystem.
5. Config is a validated tree that refuses unknown keys: defaults,
   project file, env, flags.
6. Every command exits on the wire; the four classes and the Refusal
   value go in first.
7. Interfaces only where a swap is already foreseeable: the harness
   launcher, the gate runner, the transport (and Forge, Process — §3.2).
   Nothing else gets an interface until it needs one.
8. Boundaries enforced by deptrac from the first commit.

---

## 4. The founding contracts — RULED, in `docs/`

Unchanged by anything above; they read the same whether the targets
are PHP or Rust. Summaries; the files are the law.

- **`docs/wire.md`** — four outcome classes; the one-line refusal on
  stderr; identity on writes; absence discipline (`UNREACHABLE`,
  declared emptiness); a conformance registry and gate.
- **`docs/workflow.md`** — a workflow is a declared graph where every
  transition names actor class, evidence duty, failure class, gate;
  declared as data, run by a generic engine; Symfony Workflow's
  markings; owner ratification is a Denial only one actor lifts; the
  audit ladder (sequential independent reviewers, floor re-run between
  stages, marginal detection recorded).
- **`docs/probes.md`** — hand-over tested by probe corpora (`serve`,
  `absent`, `nearmiss` rows), a runner, `UNREACHABLE` as a third
  outcome, a staging surface the session under test may see,
  session-close manifests.
- **`docs/concerns.md`** — single-concern reviewers as fixed tracked
  artifacts; findings are quotation pairs (declared vs practiced);
  calibration on planted faults and clean neighbours, rates reported
  beside verdicts; the first concern is hypocrisy, run on everyone.
- **`docs/verified-couplings.md`** — six obligations of every edge:
  closure both ways, shape, behaviour (gates that fire on planted
  faults), freshness (stamped to version and date), permission, blast
  radius; priced coupling; vendors consumed through contract + probe +
  mock.
- **`docs/mapping.md`** — what Symfony covers per capability and what
  is left over; measured against Packagist 2026-09-03; expires on
  read.

The mapping's §"what is left over" is still the product's quarter:
custody, calibration, evidence freshness and blast radius, the
producer firewall as a type constraint, the hypocrisy concern, the
refusal discipline on every projection, absence discipline, the
conformance harness, the breaker and worth, the projector/extractor
over the contract estate.

---

## 5. Standards and gates

The full draft is `.xor/tmp/standards-draft.md` (owner's exchange
directory, not tree content). It splits into Part A (enforced by a
tool behind one command), Part B (stated on a page that rides every
dispatch), Part C (owner decisions).

### 5.1 `composer check` — PROPOSED, tools AGREED via C1–C6

One command, same locally and in CI; `composer fix` applies the
fixers, `check` only reads. PHP-CS-Fixer (`@Symfony`, `@Symfony:risky`,
`@PHP84Migration`, `declare_strict_types`, `final_class`); PHPStan at
`max` with the symfony, strict-rules and deprecation-rules extensions;
Rector `--dry-run` with PHP 8.4, dead code, type declaration, code
quality and Symfony sets; deptrac; `composer validate --strict`,
normalize `--dry-run`, require-checker, unused, audit; PHPUnit with
the bridge; `lint:container`; `lint:yaml config`; `vendor/bin/mate
tools:list`; Infection (threshold after the first module, C4).

Later, with their triggers: ParaTest (suite over a minute), Castor
(scripts stop fitting on a screen), Behat + FriendsOfBehat (a feature
shelf that needs the kernel), DAMA + Foundry (a database), Panther (a
UI), Sentry / Prometheus / messenger-monitor (a runtime to observe).

Rejected: `symfony/lsp` and `maschmann/symfony-php-mcp` (absent from
Packagist; the claims about them are unverified), the third-party MCP
servers (mcp-bundle is ruled), Psalm (C6), roave/security-advisories
(dev-only; `composer audit` answers the same question).

### 5.2 Part B highlights — PROPOSED, in the draft for correction

Language: strict types; `final` by default, interfaces for extension;
`readonly` for values, messages, events, results; constructor
promotion; enums for closed sets; `match`; return types everywhere;
`mixed` only at the wire's parse boundary; no array shapes across a
module boundary; no static state; no baseline files.

Symfony: wiring by attribute; autowire and autoconfigure; services
private; PHP service config (C1); never inject the container;
interfaces only at a module boundary; commands are thin; time,
filesystem, process and HTTP through Symfony's abstractions so every
one is mockable.

Tests: PHPUnit 13; tests mirror `src/`; unit tests boot no kernel;
sentence-shaped names; every refusal in a refusal table has a test;
every fault corpus row is a data-provider row; a planted fault proves
it landed; deterministic (ClockMock, no network, no sleep); a mock of
a concrete class is a design finding; tests are written by a producer
other than the implementer.

### 5.3 Decisions — C1–C6 AGREED, C7 revised and AGREED, C8–C9 OPEN

| id | decision | status |
|:--|:--|:--|
| C1 | service definitions in PHP, not YAML | agreed |
| C2 | `final` enforced by the fixer | agreed |
| C3 | Rector as a dry-run failure inside `check` | agreed |
| C4 | Infection threshold after the first module | agreed |
| C5 | Composer scripts now, Castor when they outgrow a screen | agreed |
| C6 | no Psalm | agreed |
| C7 | **Makers in.** Our own makers on MakerBundle's extension point, under `src/Maker/`, MakerBundle as a dev dependency. Non-interactive (every input an option); the generator refuses to overwrite. Templates are the standards in executable form; the maker's tests generate into a temp dir and run the whole check on the output; the standards reviewer regenerates the skeleton and diffs it against a PR. `make:agentscient:module`, `make:agentscient:service` (service, boundary interface, Console command, MCP resource, API resource, a test stub per refusal; TUI stub until tui is measured), `make:agentscient:refusal`, `make:agentscient:workflow` later. Stock makers allowed only where no custom one exists and only if the output passes the check. The implement job template says: run the maker first, fill only the bodies it leaves open. Order: the wire by hand as the exemplar, then the maker whose templates reproduce it, proven by regenerating the wire's skeleton and diffing. | agreed |
| C8 | exception hierarchy: own marker interface per module, extending Symfony's where one fits | open |
| C9 | coverage floor per module as a PHPUnit gate | open (recommendation: no; Infection is the honest measure) |

---

## 6. Process

### 6.1 The loop — PROPOSED, accepted in direction ("we scope and spec here")

The imported lane's six-stage pipeline (scope, plan by Fable, tests
by Grok, check the tests by Codex, code by Opus, review by Grok and
Codex) was built for an owner who could neither plan well nor read
the code. This owner plans; nobody reads all the code. So:

1. **Scope and spec: the owner, in session.** One short spec per work
   order. Replaces the plan dispatch and the plan review.
2. **Tests from the spec: one harness**, never the one that will
   implement. This is the one rule that substitutes for reading code.
3. **Code to green: a different harness.** It sees the tests and the
   spec, nothing else. The maker runs first.
4. **Mechanical gates in CI on every PR** (§5.1) catch most of what a
   second reviewer would.
5. **One review, only when the change warrants it**, by a harness that
   wrote neither tests nor code, charged with one concern: quote every
   place the code departs from the standards page. Trivial changes
   merge on green.

Two or three dispatches per change instead of five. The producer
firewall (no producer owns two consecutive artifacts) survives; the
ceremony around it goes.

### 6.2 Records — PROPOSED

PR bodies (the four headings: What, Sources, Evidence, For reviewers)
and a decisions file the owner edits directly are the record. The
register's contract is kept for the register module; the AAR,
hand-off, probes-as-ceremony, ledger and skills telemetry are dropped
as process and reappear only as telemetry events (§3.4) where they
earn it. Sessions onboard from a short `CLAUDE.md` that says: read the
current spec, run the gates, dispatch through the lever, no producer
owns tests and code.

### 6.3 What the imported lane becomes — PROPOSED

The Python lane under `ops/` (about 60k lines, 8 suites, 1,033 tests
green on 2026-09-03) is the working machinery today and the machinery
the first slice is built with: `go.sh` dispatches tests and code to
the other harnesses, the Claude hooks guard every session, `suites.sh`
answers "is it green", the onboard instrument serves the brief. It is
**in use as-is** until each verb's `agentscient` twin passes the same
row, which is the strangler rule `ops/README.md` already states. It
is **not invested in**: no new instruments, no PR #10 engine, no House
freights, fixes only where a session is blocked. It is **retired verb
by verb**: `go.sh` when `agentscient go` passes the dispatch row,
`suites.sh` when `agentscient check` runs the gates, and so on, each
retirement a PR showing the twin passing. Each instrument's contract
and tests are the spec its module is built against. Its suites leave
the PHP critical path in CI: they run when `ops/` changes, not on
every PHP PR. Dropped outright:
the term wall (walls the product's own words), Serena for now (rewrites
a tracked file on every start; the codebase has one class), the Gitea
stack (nothing running), ten of twelve runners, the House records
under `ops/conductor/` that describe another repository (moved behind
an archive directory with a standing banner). PR #10 (the House's
workflow engine and 25-context CI shape) is not merged as it stands.

**Serena — AGREED and configured 2026-09-03** for developing this
Symfony application (not for the Python lane, which stays invisible
to it). Configured from two answer documents, one verified at the pin
`43ae0211` and one from the fork's author, both in the owner's exchange
directory, and verified by starting the server by hand:

- `.mcp.json`: the pinned `uvx` start, `--context claude-code
  --project . --enable-web-dashboard false`, and `env.SERENA_HOME =
  .serena/home`, so every checkout has its own Serena home (config,
  projects list, language-server download, logs) and never shares the
  House's `~/.serena`. Gitignored: `.serena/home/`, `cache/`,
  `project.local.yml`, `memories/`, Serena's generated `.gitignore`.
- `.serena/project.yml`: `language_servers: [php_phpactor]`;
  `ignore_all_files_in_gitignore: true`; `ignored_paths` for `ops/**`,
  `.dev/**`, `.xor/**`, `.serena/**`; `default_modes: [interactive,
  editing, no-memories]`; `included_optional_tools:
  [restart_language_server]`. Serena normalizes the file on every start
  (all keys, its own comments); the committed form is the normalized
  one, proven byte-identical across three starts.
- PHP server: Phpactor (needs only `php`; a 4.4 MB phar into the
  per-checkout home; started in 0.74 s). Intelephense needs node and
  npm, absent on this host. The tracked `.phpactor.json` enables
  Phpactor's Symfony extension, which reads the compiled dev container
  at `var/cache/dev/App_KernelDevDebugContainer.xml` (default path);
  Phpactor loads a local config only from a trusted absolute path
  (`~/.local/share/phpactor/trust.json`), so each new worktree runs
  `phpactor.phar config:trust --trust` once. `composer install` and
  `bin/console about` were run so the container XML exists.
- Roster measured: 15 tools — symbol readers and editors, regex
  editors, file diagnostics, `initial_instructions`,
  `restart_language_server`. No memory, onboarding, shell or
  whole-file tools. `get_symbols_overview` and `find_symbol` returned
  `App\Kernel` and its method through Phpactor.
- Known limits at the pin: no edit scoping beyond `read_only`; the
  symbol editors do not check `ignored_paths`; modes are fixed at
  startup; per-edit diagnostics disabled; cache writes not atomic, so
  after a hook or fixer reformats a file, call `restart_language_server`.
  Per-worker rosters later through `--mode <file>` or a planted
  `project.local.yml`, never `fixed_tools`; a Codex context must keep
  the name `codex`. `.serena/README.md` carries the per-checkout steps.

### 6.4 Git and PR rules — RULED (`AGENTS.md`, `CONTRIB.md`)

`dev` is the trunk, `master` the release; branch from `dev`, PR into
`dev`, draft first, ready is earned; no squash, no deleted branches,
no rewritten history; `Source:` and `Co-Authored-By:` trailers on
every commit; one line of work per worktree; the main checkout
belongs to nobody. Known inconsistencies to fix when `CONTRIB.md` is
trimmed: it says `main`, cites two `AGENTS.md` sections that do not
exist, and a plan file that is absent.

---

## 7. The first slice — PROPOSED, accepted in direction

What raddy needs, CLI only, one container:

| capability | what it does |
|:--|:--|
| **wire** | the enum, the Refusal value, the Console error listener, the conformance gate; the exemplar the maker reproduces |
| **init** | `.agentscient/` written and validated; the harness config line; the project id; `doctor` |
| **dispatch** | `agentscient go <intent> <branch|.> <scope>`: a job as a message; a worker consumes it; the launcher interface with the in-container Process implementation; the harness CLIs (claude, codex, grok) inside the image with auth mounted read-only; snapshot in, commit out; a run record per job with its measurements; the breaker middleware |
| **check** | runs the target's gate profile in its worktree (`just check`, `just bdd`, `cargo audit` for raddy) and reports on the wire; gate-run telemetry |
| **record** | the run record and the telemetry table; `agentscient usage` |

The container: one image (PHP 8.4 CLI, Composer, the app, the harness
CLIs), the worker as the entrypoint, one compose service, one volume
for the state directory. MCP, API, watch, land, register, board come
after, on the same services.

Acceptance: from a clean clone of raddy, `agentscient init`, then
`agentscient go tests . "<scope>"` and `agentscient go implement …`
produce commits on a worktree with trailers, a run record each, usage
rows, and `agentscient check` green on the result.

---

## 8. After the first slice — PROPOSED order

watch (Forge + Scheduler; push on settle) → land (both git services;
attribution from the record) → register (Workflow state machine
proposed → ratified → superseded; a voter on ratify; the first module
with all four projections) → MCP plane (board, brief, register,
records as resources; stdio) → API → persistent server and the stdio
shim → concerns (the standards concern first, then hypocrisy, each
with fixtures and rates) → probes runner → the genus engine on
Workflow → TUI → hosted control plane.

---

## 9. Repository state, measured 2026-09-03 at `32b91a4`

- 40 commits since genesis on 2026-09-01; `dev` is the trunk,
  `master` default and protected (code-owner review, the `ci` check);
  ruleset "dev is the trunk"; squash off; delete-on-merge off; private.
- The Symfony 8.1 shell exists (`bin/console`, `config/`,
  `src/Kernel.php`, `phpunit.dist.xml`); `packages/` is empty by
  declaration; no `vendor/` in the checkout, so Mate and its five
  skills are inert until `composer install`.
- The imported lane: `ops/devlane/` (dispatch, harness, task,
  telemetry, hooks, workflow checks, fixtures, infra) and
  `ops/conductor/` (nine Python instruments, thirteen suites,
  contracts, ideas, hand-offs, AARs). Local gates all green: term wall
  clean over 369 files, ruff clean, composer valid, 8 suites / 1,033
  tests OK in 3m54s. Claude hooks armed and refusing (one refused a
  clipped grep during the evaluation). 12 self-hosted runners online;
  CI green on `dev`.
- Toolchain on the host: PHP 8.4.25, Composer, gh (authenticated),
  Python 3.12, ruff 0.16.5, cue, docker, claude, codex, grok, uvx.
- Onboarding findings from the evaluation that led here: two reading
  lists that disagree (`CLAUDE.md` vs the onboard instrument's law
  table); two "law" files describing the House repository; `CONTRIB.md`
  contradicting `AGENTS.md`; Serena dirtying the tree on start; two
  instruments creating stores on read; the PR overview refusing whole
  on PR #10 (draft, conflicting, zero checks); ~1,860 lines of
  mandated reading before a session's first action.

---

## 10. Related projects

### 10.1 raddy — `xormania/raddy`, measured 2026-09-03

Public, Rust, default branch `master`, last pushed 2026-08-19. "High
Capacity PHP Web Server for Symfony": a Rust HTTP runtime for PHP and
Symfony on WebAssembly; boot once, snapshot with Wizer, resume a
pristine Wasmtime guest per request; the host owns HTTP, concurrency,
deadlines. Pre-alpha by its README: Hyper ingress and Wasmtime pooling
work; a locked PHP 8.2.6 CGI executor exists but is not selected by
the server binary; Symfony snapshots are not implemented; glibc Linux
only; Rust 1.97.1, wasi-sdk 33, Wizer 11.0.3, Wasmtime 47.0.3. Gates:
`just check`, `just bdd`, `just bench-check`, cargo audit in CI. Has
its own `AGENTS.md`, ADRs, a BDD crate, `.serena/project.yml`.

Relation: the first target project; and, per the owner, the intended
app server for Agentscient itself once it boots Symfony, providing
native messaging and queues beyond HTTP. Two requirements Agentscient
states now so the projects meet at a declared edge: a message maps to
a guest resume (the custody model); dispatch touches the host (process
spawn, filesystem), so either raddy exposes a supervised-process host
call or dispatch stays a host-side service the guests reach through
the queue (the session recommends the second).

### 10.2 Agent Lab — `uscient/agent-lab`, measured 2026-09-03

Public mirror, Apache 2.0, Shell, default `master`, last pushed
2026-08-07. A Docker Compose containment lab: an internal agent
network with no route to host, LAN or internet; CoreDNS for lab-local
names; Squid as the only dual-homed service with deny-by-default
egress and per-harness allowlist recipes (base, claude-code, codex,
node-dev, python-dev); read-only agent root filesystems, capabilities
dropped, no privilege escalation, CPU/memory/process limits; the
project mounted read-write at `/workspace`; file-backed secrets
mounted read-only; refuses broad home mounts, credential stores, the
Docker socket, privileged mode, host networking, public ports;
configuration parsed as data and validated before side effects;
Cedar + CUE for experiment admission (v0alpha1, onboarding evidence
only, does not run workloads yet).

Relation: the long-term containment substrate for dispatched
workers; a ways away. Its shape is why the launcher is an interface
and why the three day-one choices in §2.4 exist.

---

## 11. Questions for reviewers

Where a second opinion changes what gets built:

1. **Modules in `src/` with deptrac, no bundles** (§3.1): anything
   this makes harder later that a move would not fix?
2. **One database with a project column** vs one database per
   project (§3.2): the session chose one, for the hosted form. Costs?
3. **HttpClient over `gh`** for Forge (§3.2): any reason the CLI's
   auth model is worth keeping?
4. **The stdio shim → persistent server** shape for async MCP
   (§2.3): is a shim the right lifecycle, or should the harness config
   point at HTTP from the start?
5. **MCP read-only** (§2.2): keep the ruling, or let a harness
   trigger dispatch through a tool call?
6. **Telemetry as one event table with promoted columns** (§3.4):
   enough for worth and calibration queries, or per-kind tables from
   the start?
7. **Secrets from files, never env** (§2.4): friction on the local
   path worth the Agent Lab alignment?
8. **The first slice** (§7): is `check` needed before `watch`, or the
   other way round, for a project like raddy?
9. **Static-php-cli micro** for the binary (§2.5): anything known
   about its behaviour with Doctrine's SQLite driver, Symfony's
   compiled container, or Messenger workers in a micro binary?
10. **The process loop** (§6.1): with tests by one harness and code by
    another, is one standards-only review enough, or does the
    check-the-tests stage earn its place back for large changes?
11. **Makers** (C7): templates as the executable form of the
    standards, proven by regenerate-and-diff. Anything this misses
    that an exemplar module would catch?
12. **What raddy should promise** (§10.1): a supervised-process host
    call, or dispatch host-side behind the queue?

---

## 12. Measured versions — Packagist, 2026-09-03

Substrate: symfony/* 8.1.6 (console, process, messenger, lock,
scheduler, http-client, workflow 8.1.0), PHP >= 8.4; symfony/ai 0.13.0
(platform, agent, bundle, claude-code-platform, codex-platform,
failover, cache, mate, symfony-mate-extension, monolog-mate-extension);
symfony/mcp-bundle 0.13.0 on mcp/sdk 0.8.1 (stdio and HTTP, sessions);
symfony/tui 8.1.6 (experimental) on revolt/event-loop 1.0.9; API
Platform 4.3.17.

Quality: phpstan 2.2.12, phpstan-symfony 2.0.20, strict-rules 2.0.12,
deprecation-rules 2.0.5, extension-installer 1.4.3; php-cs-fixer
3.95.24; rector 2.6.6; deptrac/deptrac 4.7.1; infection 0.35.4;
composer-normalize 2.52.0; composer-require-checker 4.24.0;
composer-unused 0.9.6; paratest 7.24.1; phpunit 13.3; maker-bundle
1.67.0; castor 1.7.0.

Later: behat 3.32.0 + friends-of-behat/symfony-extension 2.7.0;
phpspec 8.3.1; panther 2.4.0; dama/doctrine-test-bundle 8.6.0;
zenstruck/foundry 2.12.1; sentry-symfony 5.13.0;
artprima/prometheus-metrics-bundle 1.22.1;
zenstruck/messenger-monitor-bundle 0.6.0; opentelemetry bundle: no
stable.

Distribution: humbug/box 4.7.0; crazywhalecc/static-php-cli 2.8.5;
FrankenPHP 1.12.7 (rejected for the CLI).

Hosting seams: symfony/amazon-sqs-messenger 8.1.5; async-aws core
1.29.2, sqs 2.9.0, s3 3.4.1, dynamo-db 3.11.0, secrets-manager 2.10.1,
ssm 2.4.2, cloud-watch-logs 2.10.0; league/flysystem-bundle 3.7.1 +
flysystem-async-aws-s3 3.31.0; symfony/lock 8.1.6; mercure-bundle
0.5.0; doctrine-bundle 3.3.1; amphp/http-server 3.4.6.

Absent from Packagist: `symfony/lsp`, `symfony/language-server`,
`maschmann/symfony-php-mcp`.
