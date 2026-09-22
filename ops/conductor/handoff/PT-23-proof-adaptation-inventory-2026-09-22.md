# PT-23 (Grunt, lane/session-20260922-d65f) — A/B/C findings, 2026-09-22

Plan read: `.xor/in/multi-agents/agentscient-dev-lane-multi-harness-integration-plan-2026-09-22.md`
§§2,4,6,7,11. Proof checked out at `/home/scientdb/projects/poc/multi-harness-proof`,
HEAD `a944f31` confirmed via `git -C ... rev-parse HEAD`; local `master` branch ref
also reads `a944f31` (behind origin/master by 2, `ad29439`); `git diff a944f31 ad29439 --stat`
shows only 8 doc files changed (README/OPERATIONS/REFERENCE/etc.), no `mhproof/` change —
matches the Lead's "differs by docs only".

## A. Proof adaptation inventory

Command for line counts/imports: `wc -l mhproof/*.py`, `grep -nE "^import |^from " mhproof/*.py`.
All ten files import stdlib only, plus intra-package `from . import ...` /
`from .X import Y` (no third-party deps anywhere in the ten).

| file | lines | imports | owns (one sentence) | §11 mapping |
|---|---|---|---|---|
| `adapters.py` | 465 | stdlib + `.contract .compat .evidence .relay .rpc .telemetry` | Persistent per-run Codex/Claude/Grok protocol-client processes: spawns the native binary, drives its RPC/hook loop for the run's lifetime, reports identity/version. | `ops/conductor/tools/session_adapters/` ("Adapted Codex/Claude/Grok protocol clients... capability probes and evidence normalization"); also the source for the `profiles.py` transport-projection argv (§6). |
| `rpc.py` | 115 | stdlib only | Full-duplex JSON-lines RPC transport so a blocked/held tool call never stalls the input reader. | `session_adapters/` — shared framing the plan's slice-1 contract page names as "the shared framing module tested offline". |
| `compat.py` | 98 | stdlib only | Installed-binary/capability probes and native startup observations (Codex schema/toolOutput probe, `ClaudeChannelLog` handler-registration reader) — no model calls. | `session_adapters/` (capability probes); feeds the "Retain installed-schema probe for toolOutput" obligation in §6's Codex row. |
| `capture.py` | 85 | stdlib + `.telemetry` | Tails only the native Claude transcript selected by this run's own hooks (`fcntl`-locked read). | `session_adapters/` (Claude evidence capture) and the Claude "exact-session diagnostic capture" obligation in §6. |
| `sessions.py` | 398 | stdlib + `.adapters .capture .compat .experiments .relay .reporting .telemetry` | Operator-owned tmux lifecycle: `prepare/start/supervise/operate/list_runs`, one run directory per run, never resumed/overwritten. | Directly the new `ops/conductor/tools/sessions.py` row ("Run/member lifecycle, tmux ownership, readiness, operator commands and recovery orchestration"). **Its `controller()` (line 223) calls `.suite.run_suite` — the withheld experiment driver, see below.** |
| `telemetry.py` | 117 | stdlib only | JSONL trace writer (`Trace`), secret `Redactor`, and an explicit-allowlist diagnostic-bundle/manifest builder. | Feeds "Existing monitor/watchdog integration... only the missing persistent-session readings are added" and the evidence-normalization duty of `session_adapters/`. |
| `mcp.py` | 112 | stdlib + `.contract .relay .telemetry` | The proof's own small stdio MCP server exposing `proof_*` tools, plus Claude channel notifications. | Superseded by the lane's `coordination_mcp.py`; only the stdio-server/Claude-channel wiring pattern is adaptable material for `session_adapters/` + the profiles.py Claude channel composition (§6). The proof MCP itself (its tool set) is proof-only, see below. |
| `cli.py` | 139 | stdlib + `.adapters .compat .contract .mcp .suite .telemetry` | The proof's own operator CLI (`main`): dispatches to `run_agent`/`run_mcp`/`run_suite`/`bundle`. | Not a 1:1 adaptation target; lane equivalent is the new `ops/bin/conduct.sh` + `sessions.py operate()`. Its `run_suite` path is withheld (below). |
| `evidence.py` | 171 | stdlib + `.contract` | Independent native-observation normalization used to qualify relay evidence: Grok tool identity/observation shaping, `native_call`/`tool_audit` cross-checks, the Claude hook entrypoint. | `session_adapters/` — this *is* the "evidence normalization" the plan names. |
| `contract.py` | 88 | stdlib only | "The entire model-visible protocol": `PEERS`, the proof's `INSTRUCTIONS` prompt text, `TOOLS` schema, `validate_tool`, `render`. | Not mapped to a lane owner — this is the withheld proof-only protocol/tool-restriction text itself (below), not adaptation material. |

### What must be withheld (per §4/§6)

- **In-memory relay**: `mhproof/relay.py` (`Client`, `write_json`), imported by `adapters.py`, `sessions.py`, `mcp.py`. Not in the ten but is their transport backbone; it is the proof's own loopback/queue relay, explicitly not a lane work-store replacement.
- **Workload / experiments**: `mhproof/workload.py` and `mhproof/experiments.py` (`load_config`, imported by `sessions.py` line 17) — synthetic work fixtures and experiment configuration.
- **Fixed three-peer controller**: `sessions.py:controller()` (line 223) calls `from .suite import run_suite` and runs it against exactly `settings["peers"]` — this is the proof's fixed-roster experiment driver (`mhproof/suite.py`, not one of the ten but pulled in by both `sessions.py` and `cli.py`). The reusable part of `sessions.py` is `Tmux`, `prepare`, `start`, `supervise`, `operate`, `list_runs` minus the `controller`/`run_suite` call.
- **Proof-only tool restrictions**: `contract.py`'s `INSTRUCTIONS` text (lines 5–29) literally states "Use only the proof_* tools... Do not use shell, file, web, delegation, or configuration tools. Do not create other agents. Do not inspect the run directory." — this is the policy §6 says must NOT be retained as real development policy.

### MIT notice location

`/home/scientdb/projects/poc/multi-harness-proof/LICENSE` (repo root), read directly:
"MIT License / Copyright (c) 2026 xor / Permission is hereby granted, free of charge...".
No LICENSE or MIT-notice file exists at the Agentscient repo root or in `ops/`
(checked: `find . -iname "LICENSE*" -maxdepth 1` in agentscient returns nothing) — a source
manifest adapting these files needs to carry the notice itself per §4's "retaining its MIT
notice for copied portions".

## B. Launch-shape gap

Grammar: `ops/devlane/hooks/profiles.py:276` `interactive_args(harness, tokens)`, dev tip `f81be8f1`.
Groups defined at lines 278–287; positional-token handling at lines 297–306; unknown-option
refusal at line 312 (`"native interactive option is not admitted: " + name`); unknown-positional
refusal at line 304 (`"unknown native command; supply prompt after --"`). `native_launch` at line 330;
worker-mode denylist at line 345 (`--settings` explicitly denied there for `mode == "worker"`).

Required argv, read from `mhproof/adapters.py`:

- **Codex `app-server`** (line 156): `[binary, "app-server", "--listen", "stdio://"]`.
  Grammar admits for `codex`: value `--model -m`; flag `--no-alt-screen --strict-config --help -h --version -V`.
  The only bare positional the codex branch admits is `resume` (line 298); any other bare token
  (`app-server`) hits the line-304 refusal. `--listen` is in no group → line-312 refusal.
  **Every token of this argv is refused**, both the subcommand and the flag.

- **Grok `agent stdio`** (`adapters.py` lines 274, 279): `[binary, "--no-auto-update", ("--model", model)?, ("--effort", reasoning)?, "agent", "stdio"]`.
  Grammar admits for `grok`: value `--model -m --reasoning-effort --effort --output-format --max-turns`;
  prompt `--single -p`; optional `--resume -r`; flag `--continue -c --minimal --fullscreen
  --no-alt-screen --include-partial-messages --help -h --version -v`.
  `--no-auto-update` is not in any group → line-312 refusal. `--model`/`--effort` would be admitted.
  `agent` and `stdio` are bare positionals; the grammar has no positional-admission path for `grok`
  at all (the `if harness == "codex" ...` branches at lines 298/301 are codex-only, so any bare
  token for grok falls to the `else` at line 303) → line-304 refusal on `agent`.

- **Claude channel invocation** (`adapters.py` lines 421–432): `[binary, "--session-id", session,
  "--strict-mcp-config", "--mcp-config", cfg, "--settings", settings, "--debug-file", path,
  "--dangerously-load-development-channels", "server:coord_proof", "--tools", "", "--allowedTools",
  "...", "--append-system-prompt", INSTRUCTIONS, ("--model", model)?, ("--effort", reasoning)?,
  "--", prompt]`.
  Grammar admits for `claude`: value `--model --effort --output-format --input-format
  --max-budget-usd`; optional `--resume -r`; flag `--continue -c --print -p --verbose
  --include-partial-messages --include-hook-events --help -h --version -v`. Only `--model` and
  `--effort` of this argv are admitted; `--session-id`, `--strict-mcp-config`, `--mcp-config`,
  `--settings`, `--debug-file`, `--dangerously-load-development-channels`, `--tools`,
  `--allowedTools`, `--append-system-prompt` are each refused at line 312 (none is in any group).
  `--settings` is additionally named in the explicit worker-mode denylist at line 345, so even
  a future grammar admission would still need that denylist addressed for worker mode. The
  trailing `-- <prompt>` shape (one token after `--`) is the one part the grammar already admits
  (lines 293–296).

Not proposing a fix (wall session's work per the slice-1 contract page, see below); this is the
inventory only.

## C. Codex schema probe

Host: this session's WSL2 container. Commands run, into scratchpad only:

- `codex --version` → `codex-cli 0.155.1` (binary at `/home/scientdb/.local/bin/codex`).
- `codex app-server generate-json-schema --out "$SCRATCHPAD/codex-schema" --experimental` → exit 0,
  wrote 44 top-level files + `v1/` and `v2/` subdirs including `codex_app_server_protocol.schemas.json`
  (845 KB) and the v2 variant (734 KB).
- **Yes, it runs on this host.**
- **Yes, the generated schema carries `TurnStartParams.toolOutput`.** File
  `v2/TurnStartParams.json`: `properties` includes a `toolOutput` key whose schema is
  `{"anyOf": [{"$ref": "#/definitions/TurnToolOutput"}, {"type": "null"}]}` — confirmed by
  loading the JSON with `python3 -c "import json; ..."` and printing `'toolOutput' in properties`
  → `True`.

## Addendum — the Lead's follow-up (2026-09-22, after PT-23 bound)

Read first: `ops/conductor/sessions-lever.md` at `origin/lane/session-20260922-af333fa2`
(`git fetch origin lane/session-20260922-af333fa2`, then `git show .../sessions-lever.md`).
Note: the Lead cited it "at 985e28af"; the branch tip is now `13664232` (one commit later,
"Answer the XO's reading of the sessions contract (F3, F4)"). `git diff 985e28af 13664232 --
ops/conductor/sessions-lever.md` shows two small clarifications (tmux "session" not "server"
wording; doctor's `missing adapter` reading for absent codex/grok adapters) — nothing that
changes this reading.

The page itself states plainly (its own §"What slice 1 is, and is not"): the Codex/Grok adapters
"wait on the transport projection in `profiles.py`, whose tests live under
`ops/devlane/hooks/tests/` and so are wall work for a separate wall session" — this matches
finding B above independently.

### The two 2026-09-19 unpushed branches

Both exist locally only (`git rev-parse --verify origin/<branch>` fails for each; local
`git rev-parse --verify <branch>` succeeds). Merge-base of each with `dev` is `f81be8f1`
(current dev tip) — both are current, no rebase debt.

**`lane/session-20260919-skill-hooks-01a0b7596f92`** (local sha `39a1305`) touches
`ops/devlane/hooks/profiles.py` (+28/−9 across 6 hunks, via `git diff dev <branch> --
ops/devlane/hooks/profiles.py`): adds an `operator_skills` parameter to `source_pins()` that
pins `.claude/skills/*/SKILL.md` pages into the policy closure for interactive mode only;
adds `"PreInvocation"` to the helper's event loop in `helper_text()`; changes `configuration()`
to preserve the native event name (`PreInvocation` itself) instead of mapping it to
`SessionStart` before building the hook command, for Agy `injectSteps` support; threads
`operator_skills=` through `generate()`/`validate()`/`relocate()`. **It does not touch
`interactive_args` (line 276) or `native_launch` (line 330)** — no functional overlap with
the transport-projection work §6/§11 ask for. It does share the file, so a wall session
editing `interactive_args`/`native_launch` will need to merge against this unpushed branch
(or the branch against the wall session's landed change) since it isn't on origin and a
session unaware of it could silently diverge from it.

**`lane/session-20260919-terra-01a0b759`** (local sha `60c8d80`) touches
`ops/conductor/tools/skills.py` (+"214 added lines" by `git diff --stat` count) and adds
`.claude/skills/skills/SKILL.md` + `ops/conductor/tests/test_skills_managed.py` (433 lines).
It does not touch `profiles.py`. It adds a managed/canonical skill-catalogue serving path:
`catalog`/`read NAME`/`use NAME` CLI verbs, `_managed_pages()`/`managed_catalog()`/`load_skill()`,
with symlink-boundary and TOCTOU-hardened reads (`_read_canonical_page` opens by fd with
`O_NONBLOCK`, checks `S_ISREG` via `/proc/self/fd/<fd>`, verifies the resolved target stays
under the repo root and is named `SKILL.md`), a 256 KiB page-size cap, sha256-stamped
`skill_events` rows (`source_path`, `source_sha256` columns added by migration). This is
functionally relevant to plan §6 step 7 ("Ensure the exact launch path discovers the required
skills/tools") and to the `onboard.py, role guidance and registered skills` row in §11 — a
verified, hashed way to serve a participant's skill pages — but **`sessions-lever.md` does not
mention skills or this branch anywhere** (`grep -n -i skill` over the fetched page: no matches),
so there is no declared overlap in the contract page itself, only an unclaimed functional
adjacency for whoever builds the onboarding-brief piece.
