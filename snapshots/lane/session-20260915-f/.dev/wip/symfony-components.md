# Symfony components and features for Agentscient

Built 2026-09-03 from the Symfony documentation index
(symfony.com/doc/current, the 8.1 docs) and the package pins the
mapping measured on Packagist the same day (`docs/mapping.md`). One
row per component or framework feature. "Fits" says where it lands in
the shape the overview describes; "standing" says whether the mapping
measured a pin for it, or it is a candidate, or it is not needed. A
row with "candidate" has not been measured beyond the docs page.

Owner's working document, untracked, like the overview.

## A. The spine: used by the first slice (wire, init, dispatch, check, record)

| component / feature | what it is | fits | standing |
|:--|:--|:--|:--|
| Console | commands, exit codes, input/output, the `bin/console` app | every verb is a Console command; the wire's exit classes map onto `Command::SUCCESS/FAILURE/INVALID` plus Abort; the refusal line goes out on a `ConsoleEvents::ERROR` listener | pin measured: 8.1.6 |
| DependencyInjection + Config | the container, autowiring, attributes, compiler passes; validated configuration trees | modules in `src/`, services wired by attribute; the `.agentscient/` config as a tree that refuses unknown keys; the MCP read-only rule as a compiler pass | pins measured: 8.1.5 each |
| Messenger | messages, buses, transports, workers, retries, failure transport, stamps | every job is a message; workers consume; retry strategy replaces resume; a stamp carries identity and project; the breaker as middleware | pin measured: 8.1.6; doctrine-messenger 8.1.6 for the SQLite transport |
| Process | run a subprocess with timeout, captured output, exit code | the one way any CLI or git runs; every command becomes a Measurement (command, stamp, output) | pin measured: 8.1.6 |
| Workflow | state machines and workflows, places, transitions, guards, audit trail | the genus engine: work orders, the register's proposed → ratified → superseded, readiness flips; a voter on ratify | pin measured: 8.1.0 |
| Scheduler | recurring messages on a schedule, on top of Messenger | the watch lever's polling cadence; probe cadence; usage rollups | pin measured: 8.1.5 |
| Clock | `ClockInterface`, mock clocks for tests | every timestamp, so tests freeze time | pin measured: 8.1.0 |
| Filesystem + Finder | file operations; find files by rule | staging snapshots from manifests; walking trees for checks (the dangling-reference check, the wall) | pins measured: 8.1.6 / 8.1.5 |
| Serializer + Validator | normalize and denormalize objects; constraint validation | the result envelope and the job messages as typed, validated objects; the same shape for every harness; trailers as constraints | pins measured: 8.1.6 each |
| Lock | mutual exclusion across processes | one worktree per line of work; one dispatch per lineage at a time | pin measured: 8.1.6 |
| Uid | UUID/ULID generation | job ids, record ids, message ids | pin measured: 8.1.5 |
| EventDispatcher | events and listeners | typed domain events per module; the one telemetry recorder subscribes | pin measured: 8.1.5 |
| Runtime | boots the app for a given runtime (CLI, HTTP) | `bin/console` as the app; the API projection later | pin measured: 8.1.0 |
| PHPUnit Bridge | deprecation handling, clock mocking, PHPUnit integration | the test floor | pin measured: 8.1.6 |
| Monolog bundle (Logger) | channels, handlers, processors | a channel per module, JSON to stderr, a processor stamping project, job, identity; Mate's Monolog extension for session reads | pin measured: monolog-bundle 4.0.2 |

## B. Platform services and stores

| component / feature | what it is | fits | standing |
|:--|:--|:--|:--|
| Doctrine (ORM, DBAL, migrations bundle) | entities, repositories, migrations | every store: run records, the register, the ledger, telemetry; SQLite now, Postgres later; Messenger's transport table | pins measured: orm 3.6.8, dbal 4.4.4, bundle 3.3.1, migrations 4.0.1 |
| Flysystem bundle (league) | filesystem abstraction, local and S3 adapters | the named stores: state, records, snapshots, artifacts; the answer to host paths in records | pin measured: 3.7.1; async-aws S3 3.31.0 |
| HttpClient | HTTP requests with a mock client for tests | the Forge service: GitHub and Gitea APIs, checks per ref, PRs, rulesets; MockHttpClient for the mock half of the triangle | pin measured: 8.1.6 |
| Cache | PSR-6/16 caches, adapters | the CI store's cached readings; Packagist lookups | pin measured: 8.1.6 |
| RateLimiter | token bucket, sliding window, storage | counters behind the breaker; a per-project spend cap | pin measured: 8.1.6 |
| Semaphore | limited concurrent access | at most N workers per project or per harness | on the docs index; not measured |
| Stopwatch | timing sections of code | gate-run durations for telemetry | pin measured: 8.1.0 |
| ExpressionLanguage | expressions evaluated at runtime | guards on workflow transitions declared as data; gate conditions | pin measured: 8.1.6 |
| Yaml | parse and dump YAML | reading the config that Symfony itself does not (Serena's project file, CI workflows) | pin measured: 8.1.6 |
| Security (core, voters) | authentication, authorization, voters | ratification is the owner's: a voter on the ratify transition; custody as `IsGranted` on edges | pin measured: security-core 8.1.6 |
| Contracts | the interfaces the components share | the seams we code against, never the implementations | on the docs index |
| String | unicode-safe string helpers, slugger | slugs for ids and branch names | on the docs index; not measured |
| OptionsResolver | option arrays with defaults and validation | job option sets at the CLI boundary; otherwise Config trees | on the docs index; not measured |
| PropertyAccess, PropertyInfo, TypeInfo | read and write object properties by path; type metadata | the Serializer's underpinnings; the extractor over contracts if it reads PHP types | on the docs index; not needed directly |
| VarExporter | export PHP values as code; lazy objects | the compiled, read-only container in the shipped artifact | on the docs index; not measured |
| VarDumper | dumping values for debugging | dev only | on the docs index |
| JsonPath | query JSON documents by path | reading harness streams and records in tests and probes | on the docs index; not measured |
| Dotenv | `.env` loading | not used: the overview says no dotenv, config from files | not needed |

## C. Projections: the four surfaces of one service

| component / feature | what it is | fits | standing |
|:--|:--|:--|:--|
| Console | see A | the CLI projection | measured |
| symfony/mcp-bundle on mcp/sdk | expose services as MCP tools and resources over stdio or HTTP | the MCP projection, read-only by construction; `agentscient mcp` | pins measured: 0.13.0 on sdk 0.8.1 |
| API Platform | REST/GraphQL resources, OpenAPI, problem details | the API projection; refusals as RFC 9457 problem details; api-platform/mcp exposes the same resources over MCP | pin measured: 4.3.17 (5.0 alpha) |
| symfony/tui | terminal UI on revolt/event-loop | the TUI projection, `agentscient board`; experimental, no BC promise, API unmeasured | pin measured: 8.1.6; the first TUI unit measures it |
| HttpFoundation + HttpKernel + Routing | the request/response layer | only the API projection needs them | pins measured (framework) |
| Mercure bundle | server-sent push over the Mercure hub | terminal states pushed to the board; a browser board later | pin measured: 0.5.0 |
| Webhook + RemoteEvent | receive and parse webhooks from third parties | GitHub check and PR events pushed to the watch lever instead of polled | pins measured: 8.1.1 / 8.1.0 |
| Notifier | send notifications over chat, SMS, push | telling the owner a PR settled, a breaker tripped; a later convenience | docs topic; not measured |
| Mailer | send email | not needed now | not needed |

## D. AI, agents, diagnostics

| component / feature | what it is | fits | standing |
|:--|:--|:--|:--|
| symfony/ai Platform, with the Claude Code and Codex platform bridges | one model interface; the two bridges spawn the CLIs as subprocesses and parse their streams, usage included | dispatch: the launcher's argv building and stream scraping become the bridge's job; Grok gets the one adapter we write against the same interface | pins measured: 0.13.0, monthly cadence, pinned exactly |
| symfony/ai Agent + AI bundle | agents with fixed prompts and tool sets, wired by config | one agent per concern: the security audit, the standards review, hypocrisy | pins measured: 0.13.0 |
| ai-failover-platform, ai-cache-platform | one platform falling to the next; cached responses | harness substitution; replay fixtures for tests | pins measured: 0.13.0 |
| symfony/ai Mate + Symfony and Monolog extensions | diagnostic tools over the compiled container and the logs, served to the harness | already on the seat (`vendor/bin/mate`); the measured-truth plane for sessions | pins measured: 0.13.0 |
| ai-store, ai-chat, doctrine and sqlite stores | vector stores, chat history | not needed for the first slice | measured; later |

## E. Quality and tests

| component / feature | what it is | fits | standing |
|:--|:--|:--|:--|
| PHPUnit 13 + the bridge | the test runner | the floor; tests by a producer other than the implementer | pin measured: 13.3 |
| BrowserKit, DomCrawler, CssSelector, Panther | simulate a browser, crawl HTML | only if a browser board ever exists | not needed now |
| Testing guide: `KernelTestCase`, `MockHttpClient`, `ClockMock` | integration tests without a server; mocked HTTP and time | Forge tests against recorded responses; frozen time everywhere | measured via the pins above |
| The quality tools outside Symfony (mapping and standards draft) | PHPStan, PHP-CS-Fixer, Rector, deptrac, Infection, composer plugins | `composer check`; deptrac enforces module boundaries | pins measured 2026-09-03 in the overview §12 |

## F. Not needed, and why

| component / feature | why not |
|:--|:--|
| Form, CSRF, Sessions, Templates/Twig for pages, AssetMapper, Encore, Stimulus, WebLink, HTTP Cache, Translation, Intl, Emoji, Asset | web-page concerns; Agentscient has no HTML surface. Twig may still render text briefs and the onboarding brief, which is a different use |
| Mailer, LDAP, PasswordHasher | no email, no directory, no passwords; identity is a name and an address stamped on writes, authentication comes with the hosted form |
| Dotenv | ruled out by the overview: config from files, never the environment |
| Polyfills, PSR-7 bridge | transitive at most |

## Absences, named

- Semaphore, String, OptionsResolver, VarExporter, JsonPath, Notifier: on the docs index, no pin measured here; measure before relying.
- symfony/tui: experimental, undocumented at the time of the mapping; the first TUI unit begins by measuring its API.
- Symfony AI's own docs section (`/doc/current/ai/`) was not read for this table; the package pins come from the mapping's Packagist measurement.
- Not read: any component's internals. This is the docs index and the mapping, joined.
