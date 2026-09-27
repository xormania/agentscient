# The mapping — what we have, what Symfony has, what is left

Scope correction, owner 2026-09-05: this is dated application research.
[AGENTS.md §Lane boundary and precedence](../AGENTS.md#lane-boundary-and-precedence)
supersedes its dev-lane replacement recommendations. The rows may inform
prod application design after remeasurement; they neither require Symfony
in dev tooling nor authorize moving its responsibilities into the app.
The measurements below retain their original ref/date, not current standing.

Standing: RECORD, measured. Written at the owner's word (2026-09-03:
"record the ruling and do the mapping") under the standing ruling in
`AGENTS.md` §Standing rulings: Symfony is the framework, whole; four
projections of one service. Every row below answers one question
before any application contract is written — *which package already
covers this?* — and names what is left over once it does. The left-over column is
the product.

Every figure here was produced by a command at the moment of writing
and expires the moment you read it: re-measure before relying.

## How this was measured

- Versions: the Packagist package API (`https://repo.packagist.org/p2/<name>.json`),
  expanded from Composer's minified form, latest stable = the highest
  `version_normalized` of the form N.N.N.N, dated by its `time`. 88
  names, measured at `2026-09-03T01:17:33+00:00`. The script and its raw output live
  with the session that wrote this; the table is its rendering.
- The project's pin: the application shell is materialized at
  `symfony/*` `8.1.*` and PHP `>=8.4` (`composer.json` at the root), so
  the Symfony column that matters is the latest 8.1 tag, which for
  every component below is also its latest stable.
- Sources read, not just described: `ClaudeCode/ModelClient.php` in
  symfony/ai (spawns the CLI with `--output-format stream-json`),
  `Command.php` in symfony/console (the exit constants), the
  `composer.json` requires of symfony/tui, symfony/mcp-bundle and the
  Claude Code bridge.
- Not measured: package internals beyond that, per-package licences,
  performance, the symfony/tui API. Each is an absence, named in
  §Absences, not a silent assumption.

## The pins, measured

**Symfony 8.1 — the substrate pin**

| package | latest stable | released | PHP | note |
|---|---|---|---|---|
| `symfony/console` | v8.1.6 | 2026-08-25 | >=8.4.1 |  |
| `symfony/process` | v8.1.6 | 2026-08-21 | >=8.4.1 |  |
| `symfony/messenger` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/workflow` | v8.1.0 | 2026-05-29 | >=8.4.1 |  |
| `symfony/lock` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/scheduler` | v8.1.5 | 2026-08-21 | >=8.4.1 |  |
| `symfony/http-client` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/event-dispatcher` | v8.1.5 | 2026-08-21 | >=8.4.1 |  |
| `symfony/security-core` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/validator` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/serializer` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/config` | v8.1.5 | 2026-08-20 | >=8.4.1 |  |
| `symfony/dependency-injection` | v8.1.5 | 2026-08-21 | >=8.4.1 |  |
| `symfony/stopwatch` | v8.1.0 | 2026-05-29 | >=8.4.1 |  |
| `symfony/finder` | v8.1.5 | 2026-08-21 | >=8.4.1 |  |
| `symfony/filesystem` | v8.1.6 | 2026-08-23 | >=8.4.1 |  |
| `symfony/clock` | v8.1.0 | 2026-05-29 | >=8.4.1 |  |
| `symfony/uid` | v8.1.5 | 2026-08-11 | >=8.4.1 |  |
| `symfony/yaml` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/expression-language` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/rate-limiter` | v8.1.6 | 2026-08-07 | >=8.4.1 |  |
| `symfony/cache` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/framework-bundle` | v8.1.6 | 2026-08-30 | >=8.4.1 |  |
| `symfony/runtime` | v8.1.0 | 2026-05-29 | >=8.4.1 | 8.1.0 is the latest 8.1 tag; a newer 8.0.x maintenance tag exists |
| `symfony/flex` | v2.11.0 | 2026-05-29 | >=8.1 |  |
| `symfony/twig-bundle` | v8.1.2 | 2026-06-05 | >=8.4.1 | 8.1.2 is the latest 8.1 tag; a newer 7.4.x maintenance tag exists |
| `symfony/phpunit-bridge` | v8.1.6 | 2026-08-30 | >=8.1.0 |  |
| `symfony/tui` | v8.1.6 | 2026-08-27 | >=8.4.1 | experimental, no BC promise; requires revolt/event-loop, no Console dependency; no documentation found (see §Absences) |
| `symfony/webhook` | v8.1.1 | 2026-06-06 | >=8.4.1 |  |
| `symfony/remote-event` | v8.1.0 | 2026-05-29 | >=8.4.1 |  |
| `symfony/doctrine-messenger` | v8.1.6 | 2026-08-07 | >=8.4.1 |  |
| `symfony/amazon-sqs-messenger` | v8.1.5 | 2026-08-14 | >=8.4.1 |  |
| `symfony/redis-messenger` | v8.1.4 | 2026-08-01 | >=8.4.1 |  |

**symfony/ai 0.13 — pinned exactly, probed monthly**

| package | latest stable | released | PHP | note |
|---|---|---|---|---|
| `symfony/ai-platform` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-agent` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-bundle` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-store` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-chat` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-claude-code-platform` | v0.13.0 | 2026-08-30 | >=8.2 | spawns the claude binary found on PATH via Process; stream-json parsed; token usage extracted |
| `symfony/ai-codex-platform` | v0.13.0 | 2026-08-30 | >=8.2 | same shape as the Claude Code bridge, for the codex binary |
| `symfony/ai-anthropic-platform` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-open-ai-platform` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-failover-platform` | v0.13.0 | 2026-08-30 | >=8.2 | one platform falling to the next — the harness-substitution seam |
| `symfony/ai-cache-platform` | v0.13.0 | 2026-08-30 | >=8.2 | cached responses — the replay-fixture seam |
| `symfony/ai-generic-platform` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-models-dev-platform` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-doctrine-message-store` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-sqlite-store` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-filesystem-tool` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-clock-tool` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-mate` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-symfony-mate-extension` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-monolog-mate-extension` | v0.13.0 | 2026-08-30 | >=8.2 |  |
| `symfony/ai-mate-composer-plugin` | v0.13.0 | 2026-08-30 | >=8.2 |  |

**MCP**

| package | latest stable | released | PHP | note |
|---|---|---|---|---|
| `symfony/mcp-bundle` | v0.13.0 | 2026-08-30 | — | requires mcp/sdk ^0.8.1 (official PHP SDK) |
| `symfony/mcp-sdk` | NONE | — | — | no stable release; superseded by the official mcp/sdk 0.8.1, which mcp-bundle requires |
| `api-platform/mcp` | v4.3.17 | 2026-07-03 | >=8.2 | exposes API Platform resources over MCP |

**API Platform 4.3 — 5.0 is alpha at measure time**

| package | latest stable | released | PHP | note |
|---|---|---|---|---|
| `api-platform/core` | v4.3.17 | 2026-07-12 | >=8.2 |  |
| `api-platform/symfony` | v4.3.17 | 2026-07-08 | >=8.2 |  |
| `api-platform/openapi` | v4.3.17 | 2026-06-16 | >=8.2 |  |
| `api-platform/json-schema` | v4.3.17 | 2026-06-29 | >=8.2 |  |
| `api-platform/state` | v4.3.17 | 2026-07-11 | >=8.2 |  |

**Stores, push, logs, tests**

| package | latest stable | released | PHP | note |
|---|---|---|---|---|
| `doctrine/orm` | 3.6.8 | 2026-08-05 | ^8.1 |  |
| `doctrine/dbal` | 4.4.4 | 2026-07-21 | ^8.2 |  |
| `doctrine/doctrine-bundle` | 3.3.1 | 2026-07-23 | ^8.4 | 3.x line (needs PHP ^8.4); a 2.19.0 tag exists on the 2.x line |
| `doctrine/doctrine-migrations-bundle` | 4.0.1 | 2026-08-26 | ^8.4 |  |
| `symfony/mercure-bundle` | v0.5.0 | 2026-08-11 | >=8.2 |  |
| `symfony/mercure` | v0.8.0 | 2026-08-11 | >=8.2 |  |
| `symfony/monolog-bundle` | v4.0.2 | 2026-04-02 | >=8.2 |  |
| `monolog/monolog` | 3.11.0 | 2026-09-02 | >=8.1 |  |
| `twig/twig` | v3.28.0 | 2026-07-03 | >=8.1.0 |  |
| `phpunit/phpunit` | 13.3.2 | 2026-08-27 | >=8.4.1 |  |

**Candidates outside the Symfony organisation**

| package | latest stable | released | PHP | note |
|---|---|---|---|---|
| `php-tui/php-tui` | 0.2.1 | 2024-09-08 | ^8.1 | third-party Ratatui port; last release 2024-09; the comparison row for symfony/tui, not a choice |
| `ackintosh/ganesha` | 4.0.0 | 2025-02-22 | ^8.1 | circuit breaker; Symfony core has none — a candidate for the breaker row, or ours on rate-limiter storage |
| `knplabs/github-api` | v3.16.1 | 2026-08-18 | ^7.2.5 || ^8.0 | a client the House never used; HttpClient direct with MockHttpClient is the triangle's shape |

## The mapping

Rows are the House census (`.dev/conductor/census-package-map.md`
at dev `99334f7`) plus the five founding contracts and the four
projections. *What we have* is the proven functionality now under
`ops/devlane/`; *what Symfony has* is the package that covers it;
*left over* is what Agentscient still has to build — thin, and ours.

### The instruments (freight 3)

| what we have | what it does | what Symfony has | left over |
|---|---|---|---|
| onboard (the brief) | serves a session its orientation, measured not recalled | Console; Twig for rendering; symfony/tui for the live seat; mcp-bundle resource | the brief's rules: every figure from a command, absence declared |
| decisions register | rulings added, ratified, superseded, shown | Doctrine ORM + migrations; Workflow state machine proposed → ratified → superseded; Security voter on the ratifying transition; Console, API Platform resource, MCP resource | ratification non-delegable: a recorder never confers standing on itself; recording-on-behalf demands the principal's words |
| handwork ledger | declare before doing; grants; settle | Doctrine; Workflow declared → settled; Console; Scheduler for the recurrence telemetry | the demand signal: a third "other"-class declaration names a lever to build |
| watch lever | PR checks polled until settled | HttpClient over the GitHub API with MockHttpClient for the mock; Messenger + Scheduler for cadence; Mercure to push the settle | the pinned reading: settled ⇔ rows > 0 and pending = 0, never "no pending" |
| land lever | fetch, cherry-pick, validate trailers, attribute | Process for git; Workflow guards; Validator constraints for trailers | attribution from the record, never from the actor at the keyboard |
| ci store | runs and checks per repository | HttpClient; Cache; Doctrine | the same settled reading |
| branch census | branches, worktrees, ahead/behind | Process for git; Console tables; a TUI view | nothing — a pure projection |
| skills registry, co_doc | ABSENT contracts (census) | — | the contracts, before any twin |

### The apps (freights 4 and 5)

| what we have | what it does | what Symfony has | left over |
|---|---|---|---|
| workflow (`wf.py`: work orders, stages, gates, receipts, claims, markers, its MCP) | the pipeline engine | Workflow — the genus's engine, as the record already says: places, transitions, guard events, audit-trail listener, marking stores; Messenger for stages as messages; Doctrine for the store; mcp-bundle for the read plane; Scheduler | gate kinds as guard listeners generated from the genus contract; receipts as evidence; ratification as a Denial only one actor lifts |
| dispatch (`launch.py`, the levers) | mint a snapshot, launch a harness, supervise, collect, record | ai-platform with the Claude Code and Codex bridges — the CLIs spawned as Process subprocesses, stream parsed, usage extracted; failover-platform for substitution; Messenger workers with timeouts, retries, the failure transport; Lock for one worktree per line; Workflow for the job lifecycle | the snapshot minted from a manifest and proved; the record's shape; a kill leaves commits, never residue |
| task (`jobs.json`, envelopes, filesets, verify) | the job registry, the envelope contract, parity | Config trees (jobs as validated configuration); Serializer + Validator for envelopes; Messenger stamps for caps with their source; Finder for filesets | the four-class status on every envelope; no operating parameter session-resident |
| harness (stage, isolation, probe, wires) | the firewall | Finder + Filesystem for staging; Validator for the manifest; Process for probing a harness; Config | custody: withheld absent AND given present, refuse an unprovable snapshot; the isolation law per harness |
| hooks (context stream, precheck, boundary, guards) | record crossings; refuse before outward | EventDispatcher and Console events; git hooks stay git hooks and call commands | the boundary corpus; consequence-not-risk as the precheck's rule |
| telemetry (usage, breaker, pulse, worth) | spend, trip, yield | Stopwatch; Monolog with the Mate extension; token usage from the ai-platform bridges; rate-limiter storage for counters; Doctrine; Scheduler | the breaker (no core circuit breaker; ganesha or ours); worth = effect ÷ cost, live |
| fixtures (synthetic envelopes, stores) | replay data | ai-cache-platform for cached responses as replay; MockHttpClient; PHPUnit data providers; phpunit-bridge | synthetic, never captured |
| infra (Gitea, act_runner, the lane image) | local CI muscle | stays compose, outside the framework | — |

### The founding contracts and the cross-cutting rows

| what we have | what it does | what Symfony has | left over |
|---|---|---|---|
| the wire | four outcome classes; the refusal line | Console exit constants measured in `Command.php`: SUCCESS 0, FAILURE 1, INVALID 2 — Finding and Rejection already exist; a `ConsoleEvents::ERROR` listener formats the line; API Platform problem details (RFC 9457) for the API projection; mcp-bundle error results for MCP | Abort = 3; the Refusal type with expected, found, needed; identity on writing verbs; the conformance harness that runs any binary and asserts the wire |
| the workflow genus | actor, evidence, failure, gate per transition | Workflow, whole | the evidence duty per transition; owner ratification as a voter-guarded Denial |
| probes | serve, absent, nearmiss corpora; the runner | a Console command with Process under an allowlisted read set, identity stripped; Scheduler for cadence; PHPUnit for mechanics | UNREACHABLE as the third outcome; the staging surface; session-close manifests |
| concerns | single-concern reviewers as fixed artifacts | ai-agent: one agent per concern, fixed prompt and tool set, wired by ai-bundle; models named at dispatch through ai-platform; ai-cache-platform for replay | calibration as measured rates on planted faults and clean neighbours; quotation-pair findings; the hypocrisy concern |
| verified couplings | six obligations of every edge | the compiled container is the code graph; compiler passes are build-time gates; `debug:container`; `composer.lock` as the practiced graph; api-platform/json-schema and Validator for shape | freshness stamped to a version; blast radius; permission as an edge constraint; priced coupling |
| the contract estate (31 CUE schemas, 297 faults) | the declared graph and its acceptance suites | Config trees carry the constraint half; the projector emits YAML the container eats natively; compiler passes are `cue vet`'s twin; fault corpora become PHPUnit data providers | the `cue` binary via Process; the projector and the extractor meeting in unification; the one alignment test |
| capability registry (0 entries) | what is installed and what it may do | the container, Flex recipes, `debug:container`, Config manifests | the anatomy vets; read/write tags the container refuses at boot |
| custody | who may see what, who may produce what | Security voters and `IsGranted`; the harness manifests | custody as a queryable property of the graph |
| MCP — the context plane | resources served read-only; levers act | mcp-bundle on the official mcp/sdk; api-platform/mcp exposes API resources over MCP; ai-mate and its Symfony and Monolog extensions for the dev-time probe of the container | read-only by import graph, as a compiler pass; superseded 2026-09-16 (D-MCP-1): MCP acts as well as reads |
| TUI — the seat | board, watches, records, the ladder, live | symfony/tui on revolt/event-loop; Mercure for live updates | the board's content |
| push | terminal states pushed, never polled | mercure-bundle; ux-turbo-mercure for a browser board later | — |
| API resources | | api-platform/core and symfony; openapi; json-schema | — |

## What is left over — the quarter

Collected from the fourth column. Each is a thin layer over the
packages above; none is a system beside them.

1. custody: snapshots staged from manifests and proved in both
   directions; refuse what cannot be proved
2. calibration: every stochastic checker measured on planted faults
   and clean neighbours, verdicts reported beside rates
3. evidence: stamped to a version and a date, void when the
   counterparty moves; blast radius computed from the graph
4. the producer firewall as a type constraint on edges — no producer
   owns two consecutive artifacts, founder included
5. the hypocrisy concern, run on everyone
6. the refusal discipline on every projection: expected, found,
   needed, and Abort as a fourth class
7. absence discipline: UNREACHABLE and declared emptiness, never a
   default that reads as an answer
8. the conformance harness: any binary, one refusal-provoking
   invocation, the wire asserted
9. the breaker, and worth as effect over cost
10. the projector and the extractor over the contract estate, and the
    one test that says every contract aligns with the law

## What this settles about the first package

The wire, as a bundle: an enum of the four classes; a Refusal value
that formats and parses the line; the Console error listener that
turns a thrown Refusal into exit 2 and one stderr line; the API
Platform normalizer that turns it into problem details carrying the
same three fields; the MCP error mapping; the conformance harness,
Process-driven over any binary; gestated under `packages/wire/` in
this project and composed by its application shell, its Flex recipe
written at graduation. Smallest surface, most doctrine, and it proves
the four-projection shape before any capability rides it.

### Superseded migration proposal — historical only

The following proposal is retained as provenance, withdrawn by the
2026-09-05 owner correction above. It cannot direct current operation or
make application conformance a retirement trigger for dev tooling.

The strangler order this map proposes, each step on the owner's
word: the wire; the decisions register (smallest instrument that
exercises Workflow, Doctrine, a voter, and all four projections); the
watch lever (HttpClient, Scheduler, Mercure); dispatch on the
ai-platform bridges; the genus engine on Workflow; then the remaining
rows in census order. Every twin passes the row it inherits before its
predecessor under `ops/devlane/` retires.

## Absences, named

- **symfony/tui** is experimental and outside the backward-compatibility
  promise; no documentation page was found (`symfony.com/doc/current/tui.html`
  returned not-found; no `tui.rst` under `symfony-docs` at the three
  paths tried). Its API is unmeasured here; the first TUI unit begins
  by measuring it.
- **symfony/mcp-sdk** has no stable release (one `dev-main` tag from
  2025-09) and is superseded by the official `mcp/sdk`, which
  `symfony/mcp-bundle` requires at `^0.8.1`.
- **API Platform 5.0** is at alpha 2; this map pins 4.3 until 5.0 is
  stable and probed.
- **symfony/ai** is pre-1.0 on a monthly cadence; the Claude Code
  bridge needs a `claude` binary on `PATH` (it uses ExecutableFinder).
  Pinned exactly, probed on cadence, consumed through the triangle.
- **No core circuit breaker** exists in Symfony; the breaker row names
  a candidate and a fallback, not a choice.
- **Not measured**: package internals beyond the three sources read,
  licences per package, performance, and how symfony/tui composes
  with Console (it does not depend on it).
