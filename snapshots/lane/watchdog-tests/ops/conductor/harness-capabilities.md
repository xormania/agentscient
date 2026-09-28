# Harness and CLI capability contract — first draft

Standing: PROPOSED. Born 2026-09-01 from the owner's inventory ask
("produce the inventory as the first contract draft - in fact -
inventory of everything is on the docket"); the triangle it anchors
is the contract-verified-mock idea in the intake. Rows are
RELIANCES, not catalogs: each declares a surface the lane actually
depends on, which is what the probe re-checks and a mock must
implement. Every row is true of one version on one day — the
isolation probe's doctrine governs the whole file. Status markers:
MEASURED (with the day's evidence), DOCTRINE (standing recorded
law), UNPROBED (relied on without a probe yet — a named gap, never
a silent one).

## Claude Code — the maximally capturable runtime

| reliance | why the lane needs it | status |
|:--|:--|:--|
| settings files and precedence (user, project, local) | law and guards installed from files we own | MEASURED 2026-09-01 (guard install; both hooks verified by jq) |
| lifecycle hooks: pre-tool, post-tool, stop | the lane's law firing natively: trailer guard, clipped-sweep guard, backtick guard, delegation refusal, context guard | MEASURED 2026-09-01 (each fired at least once today) |
| stop-hook wire: transcript_path, stop_hook_active, last_assistant_message; block-decision JSON; platform block cap | the context guard's whole mechanism | MEASURED 2026-09-01 (adversarial review verified fields against the live version) |
| permission rules plus the auto-mode classifier | the acting surface's gate; the classifier is stochastic call-by-call | MEASURED 2026-09-01 (same command allowed then denied; one deterministic allow rule) |
| project MCP registration (.mcp.json), read-only servers | the context-and-diagnostics plane ruling | DOCTRINE (workflow server precedent); probe UNPROBED |
| skills and commands directories; description injection | the pipeline's entry points for two of three harnesses | DOCTRINE (AGENTS.md records the reach) |
| cross-session messaging and idle notices | the baton; teammate coordination | MEASURED 2026-09-01 (delivery works; held-then-dropped failure mode measured once) |
| background tasks with completion notifications | every watch and dispatch wait today | MEASURED 2026-09-01 (dozens of cycles) |
| session transcript JSONL shape (assistant rows, typed content parts) | the context guard's fallback path; future mining | MEASURED 2026-09-01 (19.8MB parsed in 0.095s) |
| headless and SDK invocation | the capture path for driving this harness as a worker | UNPROBED here (dispatch drives the other harnesses; this one unexercised today) |

## Codex CLI

| reliance | why | status |
|:--|:--|:--|
| reads AGENTS.md cwd-upward at session start | the only law it sees — repo skills are invisible to it | DOCTRINE, load-bearing (AGENTS.md records it) |
| dispatchable headless via the pinned launcher, model set at dispatch | the pipeline's implementer and reviewer seat | MEASURED 2026-09-01 (multiple runs) |
| self-stamp may diverge from the model that ran | evidence law: record what ran, quote what it stamps | MEASURED 2026-09-01 (stamped one name, ran another, then aligned) |
| envelope harvested into the record's out/ | reading verdicts without scraping stdout | MEASURED 2026-09-01 (consistent all day) |

## Grok CLI

| reliance | why | status |
|:--|:--|:--|
| claude-compat: reads CLAUDE.md and AGENTS.md, sees repo skills | law reach and test-author seat | DOCTRINE |
| dispatchable headless via the pinned launcher | test author, adversarial reviewer, hunter | MEASURED 2026-09-01 (multiple runs) |
| envelope harvest GAP: final message lands on stdout, out/ stays empty | exit 0 with empty out/ must read as a finding, never a pass | MEASURED TWICE 2026-09-01 — proposed register row demands the launcher-side fix |
| owner customizations exist and are not to be probed | owner's standing rule | DOCTRINE — this row records a deliberate non-probe |

## gh

| reliance | why | status |
|:--|:--|:--|
| pr list --json returns every requested field on every row (isCrossRepository included) | the census's row validation and the stub's fidelity | MEASURED 2026-09-01 (reviewer-driven; the stub now models it — the first partially contract-verified mock) |
| exit 1 means any failure whatsoever | absence is proved only by a silent empty run | MEASURED 2026-09-01 (drove the probes-contract fix) |
| a full page at the listing limit is an unmeasured total | the false-total law | DOCTRINE (two contracts carry it); probe UNPROBED |
| checks output, watch mode; graphql thread resolution; merge with merge commit | the review loop's plumbing | MEASURED 2026-09-01 (used end to end) |

## git

| reliance | why | status |
|:--|:--|:--|
| trailer parsing requires the blank-line-separated final block | the attribution law's machine readability | MEASURED 2026-09-01 (CI red; local hook and CI gate diverge — a two-contract state awaiting agreement) |
| update-ref with empty old-value is create-only | retire's idempotence semantics | MEASURED 2026-09-01 (the stuck-retry fix) |
| worktree add is a lock grab; one owner per worktree | multi-session safety | DOCTRINE, measured 2026-08-21 |
| merge-tree --write-tree for merged-floor checks | the merged-tree rule made cheap | MEASURED 2026-09-01 |

## The docket

The owner's words widen this beyond harnesses: "inventory of
everything is on the docket." Sibling inventories queued for the
same triangle treatment, each a registry with a probe: the levers
and their verbs; the stores and their schemas; installed hooks;
dispatch jobs; concern rows; contract-and-gate coverage (which
promises have which checkers — the coupling census). Each lands as
its own contract draft; this file is the pattern's first instance.
