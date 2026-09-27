# Plan — the conductor's live-state board

Plan for the tree at `9d465615248282476f10e2ba47966ed5b6c3bf21`.
Scope source: owner, 2026-08-30 — `#1 - YES; #2, #3 YES - get them
done.` This document plans #3 only. It does not implement the board.

## 1. Recommendation

Choose **(a): ship a read-only conductor CLI over the data that exists
now, then replace its source adapters as the ratified kernel and custody
capability land**.

This does not relax the settled order. The first version is neither an
MCP server nor a framework capability: it is a conductor instrument under
`ops/conductor/`, beside the supplied Meters instrument. The conductor is
its first consumer and asks for one section at the time the section is
needed. No `.mcp.json`, `ops/capabilities/surface/`, capability registry, or
MCP resource is added before the kernel.

Waiting for (b) would avoid transitional adapters, but it would leave the
known stale-assertion failure active through the framework plan's U0–U11
dependency chain, for which this planning snapshot supplies no delivery
date. Option (a) is justified only because the bridge has an explicit
deletion boundary: its output and rendering contract stay; kernel and
custody services later replace acquisition, cache, and provenance code.

### Rework cost of (a)

The first version knowingly creates these temporary pieces:

1. three local acquisition adapters that a later service can replace:
   dispatch history/liveness, last-verdict queries, and fact custody;
2. one forge-cache adapter whose future home is **not** settled by the
   ratified capability set and therefore remains a conductor adapter until
   a separate design ruling says otherwise;
3. one CUE output contract that later joins the ratified `law` package;
4. one cache envelope that later becomes a projection of custody facts.

The CLI verbs, concise renderer, JSON shape, owner-decision markers, and
the failure/control corpus are retained. The bridge is not permitted to
grow its own registry, dependency injection, service locator, MCP server,
or durable source of truth; those would be a second kernel and would turn
the bounded rework above into a rewrite.

## 2. Premises

Every premise used by a design decision is tagged as required. A tree
premise means the pinned snapshot or a supplied `in/` file was read; it
does not mean the named program was executed successfully.

| id | premise |
|:--|:--|
| P1 | `[owner]` The board must answer every lineage and tip, live dispatches and elapsed time, the last verdict per lineage, open decisions awaiting the owner, and CI/PR state per lineage, with measurement time and command on every value. |
| P2 | `[owner]` The motivating incident is four stale assertions about PR #83, including an all-green/count claim while `dev: gates (commit-trailers)` was red, plus a pass numbered from memory. |
| P3 | `[owner]` Context is supplied only when needed and at the right time; the conductor, not a UI or another app, is the first consumer. |
| P4 | `[owner]` Kernel precedes every MCP surface, and nothing under `ops/devlane/workflow` ledger code changes in this scope. |
| P5 | `[tree]` `ops/docs/scratch/agentscient-framework-ratification.md` keeps D-order standing: plan gate and vocabulary, then kernel and framework gate, then primitives, then surface. |
| P6 | `[tree]` The context-custody amendment defines a fact by command, environment, ref, time, actor/record, and raw-output hash; it also requires an explicit unmeasured answer and staleness across refs. |
| P7 | `[tree]` `.claude/skills/pr-overview/pr_overview.py --json` already reads the four forge objects, derives the expected check set from each PR's own head, distinguishes incomplete/skipped/cancelled/unreadable states, and refuses unavailable forge access. It currently emits only a seven-character `head` in its JSON row even though it reads the full head SHA internally. |
| P8 | `[tree]` `ops/devlane/dispatch/launch.py status --json` is the launcher-owned liveness read and distinguishes `running`, `finished`, `tripped`, `DIED`, and `unlaunched`; its rows contain only id and state. The in-progress record contract separately carries `at.launched`, stage, unit, lineage, job, and harness. |
| P9 | `[tree]` `.claude/skills/dev-subs/subs.py` requires `prompt.txt` plus a `launched` marker, while the current launcher contract names `state.json` and `exit`; it is therefore not a safe source to silently substitute for the launcher's status verb. |
| P10 | `[tree]` Supplied `in/meters.py` defines a rebuildable SQLite cache with dispatch lineage, status, raw verdict, record path, `ingested_at`, and the complete raw record. Its `query` verb is arbitrary SQL over a normal connection, not a named read-only board interface. |
| P11 | `[unmeasured]` The brief reports 200 dispatches and 1,252 findings in `~/.local/state/agentscient/meters.db`; the database is outside the allowed planning snapshot and was not opened. No acceptance criterion depends on either count. |
| P12 | `[tree]` The pinned snapshot has 41 committed dispatch-record JSON files, an informal `ops/docs/TODO.md`, and no `ops/conductor/` directory. These are snapshot facts, not claims about the owner's live checkout. |
| P13 | `[tree]` `ops/docs/TODO.md` contains owner decisions in prose with no stable machine-readable id; one bullet groups several parked decisions. A parser that guesses from the word “Owner” cannot prove it found every decision. |
| P14 | `[tree]` `ops/docs/refresh.py` writes an untracked `STATUS.md` from a bare PR listing and spend report. It does not carry per-value command/time, check completeness, review age, or dispatch state. |
| P15 | `[tree]` The framework plan's U9 already names `records` as the future source of board/running/record summaries, while the ratified capability table does not expose a forge/`gh` capability. |

## 3. Alternatives considered

| choice | reasons for | reasons against | ruling |
|:--|:--|:--|:--|
| (a) board now | Existing Git, launcher status, Meters cache, TODO state, and PR overview cover the required questions; the live failure is active; a CLI does not violate kernel-before-MCP. [P1, P2, P4, P7–P10] | Acquisition and cache code will be replaced; Meters completeness is not proved; forge access has no ratified capability home. [P10, P11, P15] | **recommended** with the bridge boundary in §1 |
| (b) wait for kernel | The container, import graph, read/write tags, custody, and surface would provide one compiled architecture and fewer temporary adapters. [P5, P6] | No date is supplied; surface is after U0–U10; the stale-assertion failure remains live; a future forge source is not actually settled by that plan. [P2, P5, P15] | rejected for first delivery; it remains the adapter-cutover destination |

## 4. Design decisions

Each decision gives its reason and cites tagged premises above.

| id | decision and reason | premises |
|:--|:--|:--|
| D1 — bridge | Build a stdlib Python CLI under `ops/conductor/tools/board.py`, not an app or surface. This reaches the first consumer now without violating the ratified order. | P2 `[owner]`, P4 `[owner]`, P5 `[tree]`, P12 `[tree]` |
| D2 — pull context | Expose section verbs (`lineages`, `dispatches`, `verdicts`, `decisions`, `prs`) plus `all`; a section verb runs no unrelated provider. This makes “only what is needed” observable in tests. | P1 `[owner]`, P3 `[owner]` |
| D3 — custody-shaped output | Every fact references one or more observation records. An observation records argv as an array, UTC start/end, cwd, selected non-secret environment, repository ref or an explicit not-applicable reason, exit status, and SHA-256 of raw bytes. This lets the later custody capability replace storage without changing what the board returns. | P1 `[owner]`, P6 `[tree]` |
| D4 — three states | A section is exactly `measured`, `cached`, or `unmeasured`. A legitimate zero is `measured` with `items: []`; `unmeasured` has a refusal and no items; `cached` has the successful observation, current read time, cache age, and any failed refresh observation. | P1 `[owner]`, P6 `[tree]` |
| D5 — live local reads | Git refs, launcher liveness, in-progress record metadata, and the tracked owner-decision file are re-read on every relevant invocation and are never served from the board cache. They are local and cheap, and their value is specifically that they cannot be recalled. | P2 `[owner]`, P3 `[owner]`, P8 `[tree]` |
| D6 — cached expensive reads | `prs` runs the existing PR overview live whenever requested; `--offline` deliberately reads cache, and a live failure falls back to a visibly cached successful result. No TTL silently turns a cached value into a live one. | P3 `[owner]`, P7 `[tree]` |
| D7 — launcher owns state | Dispatch state comes from `launch.py status --json`. The board joins matching in-progress records found in the repository's listed worktrees to obtain launch time, lineage, unit, job, and stage; missing or ambiguous metadata stays explicit. It does not copy the process-state classifier from either launcher or `dev-subs`. | P8 `[tree]`, P9 `[tree]` |
| D8 — elapsed semantics | A running row reports `age_since_launch_s = observation_end - at.launched`; a tripped or DIED row never calls that runtime. If the launch timestamp is absent or invalid, the row remains visible and its duration is `unmeasured`. | P1 `[owner]`, P8 `[tree]` |
| D9 — verdict selection | Open the Meters DB with SQLite URI `mode=ro`; validate the required schema; read verdict-bearing rows and choose the latest per lineage by `raw.at.closed`, then envelope/attempt end time, then the UTC id timestamp, recording which key won. Preserve the raw verdict string; do not invent normalization. | P1 `[owner]`, P10 `[tree]` |
| D10 — cache honesty | A Meters result is labelled cached and carries the maximum `ingested_at`. A DB with no successful-ingest marker, a missing DB, a schema mismatch, or a malformed candidate is `unmeasured`, never “no verdicts.” | P6 `[tree]`, P10 `[tree]`, P11 `[unmeasured]` |
| D11 — owner queue | Give every currently known owner decision in `ops/docs/TODO.md` a unique `owner-decision:<id>` marker and split grouped decisions. The board reads open marked items from the captured Git ref and reports path and line. It calls the section “tracked open owner decisions”; it does not infer whether the owner answered somewhere unrecorded. | P1 `[owner]`, P6 `[tree]`, P13 `[tree]` |
| D12 — PR truth stays upstream | Invoke `pr_overview.py --json` and pass through its `blocking`, check buckets/names, threads, review age, and merge state; do not recompute a “green” boolean. Add a backward-compatible full `head_sha` JSON field so every PR observation names the exact tree. | P2 `[owner]`, P7 `[tree]` |
| D13 — no authority | The board reports observations, not approval. Human output never renders cached `ready to merge` as a current instruction: it says “cached as of …; refresh required” and preserves the old blocking text only as `blocking_at_observation`. | P2 `[owner]`, P6 `[tree]` |
| D14 — concurrent movement | Capture repository HEAD before and after an aggregate read. `all` refuses with `board.repo-moved` if it changed; tree-backed file reads use the captured SHA (`git show <sha>:<path>`) rather than a moving worktree file. | P1 `[owner]`, P6 `[tree]` |
| D15 — compatibility | Retire `refresh.py` as an alternate state collector by making it a thin compatibility entry point to `board.py all`; it no longer writes `STATUS.md`. Documentation names the board, not a generated page, as the current-state lookup. | P2 `[owner]`, P14 `[tree]` |
| D16 — kernel cutover | Keep the board as a consumer. When the ratified services exist, replace only adapters that have a settled service (`records`/Meters/custody); keep direct Git/forge adapters until a ratified capability explicitly covers them. Do not amend D-set inside this work. | P4 `[owner]`, P5 `[tree]`, P15 `[tree]` |

## 5. Public contract

### 5.1 CLI

```text
python3 ops/conductor/tools/board.py lineages   [--json]
python3 ops/conductor/tools/board.py dispatches [--json]
python3 ops/conductor/tools/board.py verdicts   [--json]
python3 ops/conductor/tools/board.py decisions  [--json]
python3 ops/conductor/tools/board.py prs        [--json] [--offline]
python3 ops/conductor/tools/board.py all        [--json] [--offline]
```

`METERS_DB` and `DISPATCH_JOBS` retain the paths already defined by the
supplied Meters and launcher tools. Test seams inject a clock, subprocess
runner, state root, and repository root in Python; they are not additional
public flags.

Exit status is part of the interface:

- `0`: every requested section was obtained in its declared mode; a Meters
  section may still be visibly cached because Meters is a derived cache;
- `4`: a live forge refresh failed or `--offline` was requested and a
  verified prior result was returned;
- `2`: at least one requested section is unmeasured, after printing the
  complete payload with the named refusal;
- argument/contract errors use the ordinary argparse/nonzero path and never
  print a partial JSON object.

The distinction between `4` and `2` is deliberate: cached evidence exists in
the first case, while the second has no answer.

### 5.2 JSON envelope

The CUE contract closes this shape (field names below are normative; example
values are illustrative):

```json
{
  "schema": "agentscient.board/v1",
  "query": "all",
  "started_at": "2026-08-30T00:00:00Z",
  "ended_at": "2026-08-30T00:00:01Z",
  "repository": {
    "root": "/path/to/repo",
    "head": "40-hex-sha",
    "branch": "agentscient/board",
    "evidence": ["obs.repo"]
  },
  "observations": {
    "obs.git.refs": {
      "state": "measured",
      "started_at": "2026-08-30T00:00:00Z",
      "ended_at": "2026-08-30T00:00:00Z",
      "command": ["git", "-C", "/path/to/repo", "for-each-ref", "..."],
      "cwd": "/path/to/repo",
      "environment": {"lane": "dev"},
      "ref": "40-hex-sha",
      "exit": 0,
      "raw_sha256": "64-hex-digest"
    }
  },
  "sections": {
    "lineages": {
      "state": "measured",
      "evidence": ["obs.git.refs"],
      "items": [
        {
          "lineage": "agentscient/board",
          "tip": "40-hex-sha",
          "scope": "local-head-ref",
          "evidence": ["obs.git.refs"]
        }
      ]
    }
  }
}
```

Rules enforced by CUE plus relational validation:

1. every repository value, section, and item has a non-empty `evidence`
   reference and every reference resolves;
2. a measured observation has exit `0`, command, time interval, ref (or an
   explicit not-applicable record), and raw hash;
3. a cached section cites both the original successful observation and the
   cache-read/current-attempt observation, and carries `observed_at`,
   `read_at`, and `age_seconds`;
4. an unmeasured section carries a refusal with `expected`, `found`, and
   `satisfy`, and cannot carry `items`;
5. `items: []` is legal only on a measured or verified-cache section;
6. derived fields name their expression and evidence inputs; elapsed time
   uses the board's frozen end time;
7. timestamps are UTC and ordered, SHAs/digests have their full length,
   observation ids are unique, and no environment key outside the allowlist
   is emitted;
8. JSON mode writes only the envelope to stdout. Diagnostics go to stderr.

### 5.3 Section values

| section | values returned | source and freshness |
|:--|:--|:--|
| `lineages` | every `refs/heads/*` name and full tip SHA in the selected repository; DB-only lineage names are also listed but their current tip is explicitly unmeasured | `git for-each-ref`, every call; no fetch and no claim about the forge's remote tip |
| `dispatches` | every non-finished launcher job first, then finished only in JSON detail: id, state, stage/harness from the id, joined record metadata when available, launch time, age since launch, and ambiguity/unmeasured fields | `launch.py status --json` plus `git worktree list --porcelain` and exact in-progress record reads, every call |
| `verdicts` | each known lineage and either its latest raw verdict record (id, stage, record path, ref, chosen time/basis) or an explicit “no verdict-bearing row in this cache” | SQLite read transaction in `mode=ro`; visibly cached as of `MAX(ingested_at)` |
| `decisions` | unique id, complete open question, source path/line, captured source ref | marked open items from `git show <captured-head>:ops/docs/TODO.md`, every call |
| `prs` | PR number/title, lineage, full head SHA, base, draft/merge state, current check buckets and names, expected-set-aware blocking sentence, review age/reviewer, unresolved threads/paths | live `pr_overview.py --json` on request; verified cache only after explicit offline use or live failure |

Human rendering begins each section with `MEASURED`, `CACHED`, or
`UNMEASURED HERE`, its timestamp, and the command. A measured empty prints
`none (measured)`. Cached PR rows are prefixed `CACHED — refresh required`;
the renderer never emits an unqualified all-green count of its own.

## 6. Files and boundaries

Planned deliverables:

```text
ops/conductor/CONTRACT.md
ops/conductor/contracts/board.cue
ops/conductor/contracts/examples/board.json
ops/conductor/contracts/faults/*.json
ops/conductor/tools/board.py
ops/conductor/tests/test_board_contract.py
ops/conductor/tests/test_board_local.py
ops/conductor/tests/test_board_cache.py
ops/conductor/tests/test_board_cli.py
ops/docs/TODO.md                         # stable owner-decision markers only
ops/docs/README.md                       # live board replaces STATUS.md claim
ops/docs/refresh.py                      # thin compatibility exec, no generated file
.dev/ONBOARDING.md                        # current-state command table
AGENTS.md                                 # repo-scoped board command/consumer rule
.claude/skills/pr-overview/pr_overview.py # full head_sha in JSON
.claude/skills/pr-overview/tests/test_pr_head_expected.py
```

The supplied `ops/conductor/tools/meters.py` from #2 is a runtime
prerequisite, not copied or redesigned by #3. The board reads its database
schema in read-only mode; if #2 has not landed or the DB is not populated,
only `verdicts` becomes unmeasured and the rest of the board still answers.

Denied in this scope:

- every path under `ops/devlane/workflow/`;
- `.mcp.json`, any MCP tool/resource, and `ops/capabilities/surface/`;
- a capability-registry change or a new forge capability;
- ingesting/rebuilding Meters data as a side effect of a board read;
- `git fetch`, `git pull`, ref updates, PR comments, reviews, merges, or any
  other repository/forge write;
- a web UI, TUI, daemon, watcher, polling loop, or automatic prompt dump;
- parsing conductor prose, handoff prose, or a prompt to guess state;
- verdict normalization, merge approval, model routing, or decision
  ratification.

The only writes performed by the delivered CLI are atomic replacements of
its derived forge cache under
`${XDG_STATE_HOME:-$HOME/.local/state}/agentscient/board/`; successful cache
bytes, provenance, and digest are written together. A failed refresh does
not alter the last successful cache. Nothing in the repository is written.

## 7. Units and executable acceptance

Each artifact follows the repository pipeline: contract first; tests from
the contract by a different producer; skeptic pass; implementation; two
reviews. No implementation author approves the tests. Commands below are
the unit gates and state the observable, not merely the intended feature.

### U0 — output contract and tracked owner-decision syntax

Deliver the prose/CUE contract, positive example, fault corpus, and unique
`owner-decision:<id>` markers for the currently known open decisions. Split
the grouped parked-decision bullet without changing the questions.

Acceptance:

```sh
python3 ops/conductor/tests/test_board_contract.py
```

It prints one line per control, including
`measured-empty: PASS`, `missing-command: board.observation-command`,
`cached-without-age: board.cache-custody`,
`unmeasured-with-items: board.absent-is-not-none`, and
`duplicate-owner-id: board.owner-decision-id`, followed by
`controls: all expected refusals drawn; clean example quiet` and exits 0.

### U1 — frozen red suite

An independent tests author writes the local, cache, and CLI tests from U0
and the brief, with implementation withheld. A skeptic must plant the PR #83
shape, a genuinely empty repository/decision set, and each unavailable
source.

Acceptance before implementation:

```sh
python3 -m unittest discover -s ops/conductor/tests -p 'test_board_*.py' -v
```

It collects every named test and fails on missing board behavior, not import,
fixture, network, or collection errors. The red receipt records the exact
test count and intended assertion at its commit; this plan does not invent
that future measurement.

### U2 — local board core

Implement the closed envelope, observation registry, Git lineage provider,
launcher-status/in-progress-record join, elapsed derivation, read-only
Meters provider, tracked decision provider, human renderer, and section-only
dispatch. Do not implement forge access in this unit.

Acceptance:

```
python3 -m unittest discover -s ops/conductor/tests -p 'test_board_local.py' -v
python3 ops/conductor/tools/board.py lineages --json
python3 ops/conductor/tools/board.py dispatches --json
python3 ops/conductor/tools/board.py verdicts --json
python3 ops/conductor/tools/board.py decisions --json
```

The first command prints all local-provider tests `ok`. Each CLI command
prints one closed `agentscient.board/v1` object; every item resolves to an
observation with time, argv, ref/applicability, and raw hash. The lineage
output includes every local head with a 40-character SHA. Dispatch output
distinguishes running from DIED and labels age versus runtime. Verdict output
prints the Meters `ingested_at` boundary or a named unmeasured refusal.
Decision output prints every open marker with id, path, line, and captured
ref. None of the four commands invokes `gh`.

### U3 — forge adapter and honest cache

Add the full `head_sha` to PR overview JSON, invoke that program unchanged in
meaning, and add atomic verified caching/fallback. The board stores no
independent green/merge verdict.

Acceptance:

```sh
python3 -m unittest discover -s ops/conductor/tests -p 'test_board_cache.py' -v
python3 .claude/skills/pr-overview/pr_overview.py --selftest
```

The tests print these paired cases as `ok`: live success/verified cache,
offline with cache/cached age visible, offline without cache/unmeasured,
live failure preserving cache, corrupt cache/unmeasured, expected skipped
check/extra skipped check, and PR #83's “many pass plus one current fail”/all
expected current passes. The upstream self-test remains green and prints its
derived expected-check set.

With a seeded fixture cache:

```
python3 ops/conductor/tools/board.py prs --offline --json
```

prints state `cached`, the original observation time and command, current
read time, age, digest, full PR head SHA, and
`blocking_at_observation`; it exits 4. With neither network nor cache it
prints state `unmeasured`, expected/found/satisfy, no PR items, and exits 2.

### U4 — first-consumer cutover and legacy entry point

Make the board command the current-state lookup in `AGENTS.md` and
`.dev/ONBOARDING.md`. Point `ops/docs/README.md` at it. Convert
`ops/docs/refresh.py` into a thin `exec`-style compatibility entry point so
an old command receives a live board and never generates a competing
`STATUS.md`.

Acceptance:

```sh
python3 ops/docs/refresh.py --offline
```

prints the same human board as
`python3 ops/conductor/tools/board.py all --offline`, including a measurement
header for every section and `UNMEASURED HERE` or `CACHED — refresh required`
where applicable; it creates or edits no `STATUS.md`.

```
python3 ops/conductor/tools/board.py decisions --json
```

does not invoke Git refs, launcher status, Meters, or `gh`; the CLI wiring
test proves those providers were not called. Equivalent isolation tests cover
all five section verbs.

### U5 — full gate and review

Acceptance at the implementation head:

```sh
python3 -m unittest discover -s ops/conductor/tests -p 'test_board_*.py' -v
python3 .claude/skills/pr-overview/pr_overview.py --selftest
git diff --exit-code 9d465615248282476f10e2ba47966ed5b6c3bf21 -- ops/devlane/workflow
git status --short
```

The suites print zero failures; the PR self-test remains green; the workflow
diff command prints nothing and exits 0; status lists only the planned paths.
The two reviewers separately confirm that JSON output contains no unqualified
`green`/`ready` field, no source failure becomes an empty measured list, no
board read changes the repository, and no MCP/kernel surface was added.

## 8. Failure/control corpus

Every failure has the nearest legitimate control, because a board that only
rejects bad evidence can still reject useful context.

| planted failure | required refusal/result | quiet control |
|:--|:--|:--|
| Git command fails | `board.git-unmeasured` with command and stderr digest | a valid repo with zero head refs is `measured`, `items: []` |
| HEAD changes during `all` | `board.repo-moved`, naming before/after SHAs | another branch ref moves while captured HEAD stays fixed |
| launcher reports a live pid but no record can be joined | job remains `running`; metadata and duration source are explicit/unmeasured | one exact record in one worktree enriches the same row |
| two worktrees expose different records for one id | `board.dispatch-ambiguous`, with both paths | byte-identical duplicate metadata is deduplicated and its paths retained |
| id/timestamp is malformed | state stays visible; age is unmeasured | valid `at.launched` produces frozen integer age |
| Meters path is absent | `board.meters-missing`; no items | valid populated schema with zero verdict rows produces measured absence within a cache that has an ingest boundary |
| Meters DB has tables but no ingest boundary | `board.meters-unproven` | populated dispatches plus `MAX(ingested_at)` reports cached-as-of |
| a newer dispatch has no verdict | it does not erase the prior verdict | a later verdict-bearing dispatch wins and names its selection timestamp/basis |
| verdict spelling differs by case/style | raw spelling is preserved | selection remains deterministic without normalization |
| owner marker is duplicated or grouped | named contract refusal | unique open markers, and checked markers omitted as measured closed |
| forge returns many passes and one fail | current failing check stays the blocking line | all expected current checks pass, permitting upstream `ready` only on live measurement |
| expected check has not registered | `checks incomplete` passes through | an extra passing check does not satisfy the missing expected name |
| forge fails after a success | verified cache, age, failed attempt, exit 4 | a new success atomically replaces cache and is measured |
| forge fails before any success | `unmeasured`, no items, exit 2 | a measured empty open-PR list prints `none (measured)` |
| cache bytes or digest are corrupt | `board.cache-corrupt`, never partial rows | valid cache hash returns the exact prior bytes |
| only `decisions` is requested | no other provider called | `all` calls each provider exactly once |

## 9. Kernel/custody handoff

The bridge is ready to cut over when the supplying service exists and its
contract covers the corresponding section; “kernel exists” alone is not
enough.

1. Add the board CUE shape to `law` without changing `agentscient.board/v1`.
2. Replace the dispatch/history adapter with the ratified `records` read
   interface after U9 is in service and its fixture produces the same board
   facts.
3. Replace local observation/cache records with custody fact ids after the
   context-custody unit is in service; preserve board evidence references as
   aliases to those ids.
4. Replace the Meters query only after the spend/yield amendment has a
   registered read interface with an equivalent “latest verdict by lineage”
   projection and a proved ingestion boundary.
5. Do **not** put the forge adapter behind the surface by invention. The
   ratified set has no forge capability; it stays a direct, read-only
   conductor adapter until a separate plan/ruling adds one or explicitly
   leaves it outside.
6. Delete the replaced adapters and local cache only after old/new outputs
   are compared on the fixture repository and a planted stale observation
   fires on the new path while a current observation stays quiet.

This is the exact rework boundary: source acquisition and cache custody are
temporary; the consumer contract is not.

## 10. Risks and explicit unknowns

- `[unmeasured]` Meters currently has no separate ingest-run/completeness row
  in the supplied schema. `MAX(ingested_at)` proves when present rows were
  written, not that every repository/worktree was included. The board must
  label that limitation and may not turn the brief's 200/1,252 counts into an
  acceptance claim.
- `[unmeasured]` A live owner may have answered a tracked question without a
  repository update. The board answers repository-recorded owner decisions
  at a named ref, not the owner's unrecorded state of mind.
- `[unmeasured]` Local `refs/heads/*` may differ from forge branch tips. The
  lineage section says `local-head-ref`; PR rows separately carry live or
  cached forge heads. No `git fetch` is hidden in a read.
- `[unmeasured]` The future home of forge reads is unsettled by the ratified
  capability list. This plan records the seam and does not alter that list.
- `[tree]` The supplied Meters script is not present in the pinned snapshot.
  Missing #2 therefore produces a partial board with an explicit verdicts
  refusal, rather than delaying every other section.

## 11. Discharge

After cutover, durable output/freshness/refusal rules move to
`ops/conductor/CONTRACT.md`; operator usage remains in `AGENTS.md` and
`.dev/ONBOARDING.md`; future framework bindings move to capability contracts.
The ordering, units, and bridge-rework list in this plan are then spent. No
runtime code or later contract may cite this plan as its source of truth.
