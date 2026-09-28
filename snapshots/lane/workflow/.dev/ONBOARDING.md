# Conductor onboarding — read this once per fresh session

**Branch of record: this doc reflects `origin/dev`, verified against a
worktree checked out from it on 2026-08-27.** It lives at
`.dev/ONBOARDING.md` — a canonical, discoverable dev-lane path — because
`.dev/xor/` (where an earlier draft of this file lived) is owner-personal
and branch-local: it does not exist on `dev` and nothing here assumes it
does. If your checkout disagrees with a claim below, your checkout is
right; re-verify with the commands in §7 and fix this file.

This is a **stable map**: levers and rules, not the current board. It
carries no PR numbers, no SHAs, no open-work state — those live wherever
your session tracks them fresh (see §7), never here.

---

## 1. What this repo is

Two lanes, sharply separated:

- **dev-lane** — the tooling and process that builds the House product: Python,
  lives under `.dev/`. Everything you as Conductor mostly touch. Per
  `AGENTS.md`, the dev-lane mini apps (`wf`, `task`, `harness`,
  `telemetry`, `fixtures`, `hooks`) are **being written, not being
  used** — see §5 for what that means in practice.
- **prod-lane** — the House product itself: Rust. **Confirmed greenfield on
  `dev`** — no `crates/` directory and no `Cargo.toml` anywhere in the
  tree (verified 2026-08-27, full-tree search). The `tdd` gate-kind
  (`ops/devlane/workflow/gate-kinds/tdd.json`) already names
  `crates/*/tests/**` and `cargo test --workspace` in anticipation of
  code that doesn't exist yet — that file is a forward-declared
  contract, not evidence prod-lane has started.

**The lane rule, enforced by a check, not a convention** (`AGENTS.md`
§"This file is dev-lane surface"): dev-lane vocabulary (work order,
gate, stage, receipt, red/green, chain, claim, marker) stays on
dev-lane surfaces — `.dev/`, `.git/`, the root dev-lane files
(`AGENTS.md`, `CONTRIB.md`, `README.md`, `ruff.toml`), and the
tool-configuration dot-directories (`.github/`, `.claude/`, `.serena/`).
It never appears in a the House product design artifact, contract, or spec. The
checker is `ops/devlane/workflow/checks/vocabulary_wall.py`; its allowlist
and `AGENTS.md`'s own sentence stating the rule must name the same
surfaces — that's the check's own self-check.
The same checker walls compose's container term to `.dev/infra/` while the
framework calls an injected object a capability.

**Don't conflate the method with the product.** The owner's broader
method for this kind of build (name and full write-up are owner-personal,
not checked into `dev`) is general and applies beyond this repo. the House product
is the specific Rust product this repo builds. The `ops/devlane/*` tooling
is scaffolding used to build the House product — it is neither the method nor
the House product itself, and root `README.md` says as much: "the machinery for
making changes trustworthy is worth having before there is code to make
trustworthy."

---

## 2. Your role: Conductor

You manage and delegate. You do not investigate or implement by hand —
every artifact (plan, test, code, review verdict, ruling) belongs to a
dispatched harness, never to a sentence you add yourself.

**The canonical sequence is `ops/process/pipeline.md`** (confirmed on
`dev`), not a fixed table to memorize here — read it fresh each time you
need it, because the concrete stage/harness pairing is the *owner's*
current standing choice, not something baked into the process (the
process itself keeps roles interchangeable: `AGENTS.md` — "any harness
may lead a change... the owner names the model that fills each role").
As of this verification, the pipeline is:

`scope (owner) -> plan (Fable) -> tests (Grok) -> check tests (Codex)
-> code (Claude) -> review (Grok and Codex)`

One rule in that sequence *is* written into `AGENTS.md` as an owner
standing rule, not just a pipeline default: **"Planning is Fable,
always"** — any delegation whose deliverable is a plan or approach goes
to Fable, full stop.

The owner's separate standing allocation for *which harness does what
kind of work* (not itself a file on `dev` — carry it as session
context, re-confirm with the owner if it feels stale): Grok for
investigation/tests, Codex for implementation and security work
(the owner holds an OpenAI TAC seat, which is why Codex specifically
gets security audits other harnesses don't).

**No producer owns two consecutive artifacts** — the harness that writes
an implementation does not author or approve its own tests when a second
harness is reachable. A CHANGES/REJECT verdict is ruled on by a harness
that produced neither the artifact nor the finding. Measured cost of
skipping this (`AGENTS.md`): of fourteen review findings against two
checkers built the same way, eleven were missing test cases, not coding
errors — the code did what the tests specified and the tests were
incomplete.

---

## 3. The levers — custody-isolated harness dispatch

**Working launcher scripts, if any exist in a given session, live in
that session's scratchpad and do not survive a crash or a new session.**
Do not go hunting for one from a prior session; rebuild from the durable
source, confirmed present on `dev` at `ops/devlane/harness/`:

- **`isolation.py`** — a `HARNESSES` dict, one entry per harness
  (`claude`, `codex`, `grok`), each with a mechanism (`flags` or `home`)
  and `auth_files` — **the only thing allowed to cross** from the
  operator's real config. An unlisted harness is refused (`NotIsolated`),
  not launched blind.
- **`probe.py`** — re-verifies the isolation still holds against the
  current harness binary. Verdict `INVALID` means "the question was
  never asked" — fail-closed, never read it as a pass.
- **`context.cue`** — the law. `#Context` is the observed shape of a
  dispatch; `#Dispatchable` is the closed subset allowed to actually
  launch (`operator_config_present: false`, no withheld files present,
  no unmet requirements, no dangling references). `observed.
  harness_version` must match the binary actually dispatched.
- **`stage.py`** — builds a role's snapshot from a manifest
  (`given`/`withheld` globs, withheld always wins) and proves the
  firewall held before handing back the directory.
- **`wires.py`** — breaker thresholds (`stall`, `budget`) as measured
  data; tokens-out is the live signal, raw token totals are disabled.

Also present alongside these (not in the original lever list, worth
knowing): `evidence.cue` and `vet_context.py`, and a built-out
`controls/` corpus (`build.py` plus paired `rejects/*.json` /
`*.reason.json` fixtures) — a set of positive/negative controls proving
each rejection path actually rejects. If you inherited a note claiming
`controls/` doesn't exist yet, that note is stale: it's real and
populated on `dev` as of this verification.

Full teaching material for this app: `ops/guide/harness.md`.

---

## 4. The MCPs — read/query plane only (MCP reads, CLI writes)

Lane-scoped, one MCP per lane:

- **`wf`** — dev-lane. Registered project-wide in this worktree's
  `.mcp.json` (`python3 ops/devlane/workflow/mcp_launch.py --root
  ops/devlane/workflow` — confirmed, and it's the *only* entry in that
  file). Tools: `wf_status`, `wf_next` (ask this first — its `advances`
  field is a runnable command), `wf_checks`, `wf_agents`, `wf_log`. All
  read-only by design — there is no write tool and there will not be
  one; recording evidence is the CLI's job (`python3
  ops/devlane/workflow/wf.py <verb>`).
- **`serena`** — prod-lane Rust coding hands and code navigation.
  Registered at the **user level**, not in this repo's `.mcp.json` —
  confirmed only `wf` appears there. Since prod-lane has no code yet
  (§1), serena currently has nothing to navigate; it becomes
  load-bearing once `crates/` exists.

An MCP serves projections/insight, never authority.

---

## 5. The process — TDD/BDD/cross-review

**Load-bearing nuance, easy to miss:** the dev-lane mini apps
(`ops/devlane/*`) are themselves *built by* this process, and building them
is explicitly **not** recorded through `wf` yet. Per `AGENTS.md`: no
work order has ever been opened, `wf status` returns empty on every
branch, and "no change that edits `ops/devlane/` may also record a work
order" — building the dev lane and using it must never share a record.
Until `wf` goes into use, the gate-kind sequences below are the
protocol followed *by hand*, with commits and PRs as the evidence trail
— not something you'll see reflected in `wf_status` today.

Canonical docs, shared by every harness (Claude, Codex, Grok), all
confirmed present under `ops/process/`:

| doc | governs |
|:--|:--|
| `pipeline.md` | the sequence: who produces scope, plan, tests, code, in what order, and what each is denied |
| `tdd.md` | the wf-governed gate: spec → red → impl → review → ratify. Red must fail on the intended assertion, never on a collection/import error |
| `bdd.md` | Given/When/Then scenarios written at spec stage, traceable into tests by scenario name (examples exist: `ops/design/features/**/*.feature`) |
| `cross-review.md` | the other harnesses review the leader against a detached snapshot — never the live worktree |
| `roles/test-author.md` | writes tests from the contract, never opens the implementation |
| `roles/test-skeptic.md` | refutes "these tests would catch the code being wrong"; defaults to refuting |
| `token-thrift.md` | where tokens go, and the checklist for spending fewer |
| `worth.md` | what a window of work cost, joined to what it produced |

Gate kinds (registered in `ops/devlane/workflow/gate-kinds/`, confirmed
`tdd.json` and `artifact.json`):
- **tdd**: spec → red → impl → review → ratify (checks include
  `cargo-test`, `cargo audit`, `secret-scan`, `lint`, `diagnostics`)
- **artifact**: draft → review → fix → ratify (checks include
  `vocabulary-wall`, `secret-scan`, `commit-trailers`, `imports`,
  `doc-commands`)

**Ratify is always the owner's act.** CI is the enforcement surface: a
PR is "not accepted" if the code-contract doesn't align with the
required contract. The `must_draw` attack-corpus binding (see the
`controls/` corpus under `ops/devlane/harness/`, §3) exists so gates prove
they actually bite — each planted fault must draw the exact constraint
named for it — rather than reading clean by accident.

Git workflow (from `AGENTS.md`, restated because it is load-bearing):
branch from `dev`, PR into `dev`, **never push to `dev` or `main`
directly, never open or merge a PR into `main`** — that is the owner's
act alone. Set `WF_AGENT='Name <noreply@vendor>'` before any `wf` verb
that appends evidence — reads need no identity, writes always do.

`CONTRIB.md` owns naming, the PR-body template (What / Sources /
Evidence / For reviewers), the fix-commit template, and the review wire
format (`VERDICT / STAMP / FINDINGS` with P1–P3). It also owns worktree
discipline: one line of work, one worktree
(`git worktree add ../wt/<branch-slug> <branch>`); never switch branches
in a checkout you did not create.

---

## 6. The architecture, in one paragraph

Rust's type system and CUE's law are both independently-checked,
deterministic guarantee-machines (`rustc`/rust-analyzer on one side,
`cue vet` on the other); certification is their **alignment**, not one
of them certifying the other. Two graphs are maintained — a contract
graph and a code graph — with certified edges drawn between them by a
two-producer method (one author reads only the spec, the other reads
only the code with the spec withheld; `cue vet` compares what neither
could quietly reconcile). Diagnostics warn continuously; CI refuses at
the gate. Everything is deterministic — same `(contract, code)` pair,
same verdict, every time — which is what turns "certified" into a
reproducible function instead of a probabilistic judgment, and why a
closed-contract guarantee dominates a sampled test for anything
shape-expressible ("gaps not errors," not edge-case archaeology). A
fuller record of this argument exists, but as owner-personal notes on
a branch-local path outside `.dev/` — it is not part of `dev` and no
path to it is stable enough to print here; ask the owner for the
current pointer rather than assuming one.

---

## 7. How to take a fresh measurement

**Never trust a stale fact — "a fact is true of a state," not of the
codebase forever.** Before acting on any claim about current state,
re-derive it:

| question | command / place |
|:--|:--|
| what's open, what's green | `gh pr list`, `gh pr checks <n>` |
| where branches actually point | `git log --oneline -15`, `git branch -a`, `git status` |
| this session's own context stamp | printed at session start — do not carry a prior session's stamp forward |
| dev-lane work-order state | `wf_next` / `wf_status` via the `wf` MCP, or `python3 ops/devlane/workflow/wf.py status` (expect empty — see §5) |
| a harness's isolation, still true of the current binary | `python3 ops/devlane/harness/probe.py` |
| the registered checks, and which run in CI | `wf_checks` via the `wf` MCP |

Fresh-measurement tools confirmed present under `ops/devlane/hooks/claude/`:
`context-stream.sh` (who moved what, across every worktree) and
`test-guard.py` (verifies a planted fault actually landed — referenced
by `ops/process/roles/test-author.md`).

---

## 8. Key docs index

Only paths confirmed to exist on `dev` as of 2026-08-27 are listed.

| path | one line |
|:--|:--|
| `ops/guide/README.md` | the dev-lane guide's own entry point — teaching material, read in order, distinct from the owner's working shelf below |
| `ops/guide/harness.md` | the harness app explained: environment, visibility, what stops a dispatch |
| `ops/guide/task.md` | the task app: delegated work as one call returning one typed envelope, so a Conductor's context stays flat across rounds |
| `ops/guide/workflow.md` | the `wf` app: work orders, stages, gates, the evidence chain |
| `ops/docs/README.md` | the owner's working shelf index — current state, distinct from the stable guide above |
| `ops/docs/cue-sys.md` | what CUE turned out to be for in agent work: bounding and proving an agent's context, not validating data |
| `ops/docs/cue-aar-equality.md` | four CUE constructs that read as constraints and enforced nothing, each caught by a negative control |
| `ops/docs/rust-agent-tooling.md` | verified landscape of Rust CI/diagnostic tools for the lane: adopt now, adopt with the workspace, avoid |
| `ops/devlane/workflow/PLAN.md` | the `wf` app's own design plan, referenced by `CONTRIB.md` for undecided conventions (e.g. work-order-form decision D6) |
| `AGENTS.md` | the operating contract — read this before anything else if you haven't |
| `CONTRIB.md` | naming, PR-body and fix-commit templates, the review wire format |

Dropped from the source draft because they don't exist on `dev`:
`.dev/xor/out/countract-2/two-contracts-aligning.md`, `.dev/xor/out/
contract-synthesis.md`, `.dev/xor/out/cue-sys.md` and `-cue-aar-
equality.md` (superseded by the `ops/docs/` copies above, which *do*
exist on `dev`), `.dev/xor/lessons/supervising.md`, and `.dev/xor/
HANDOFF.md`. All of these live under `.dev/xor/`, which is owner-
personal and branch-local — it is not on `dev` at all (confirmed: the
path does not exist in this worktree). If you're on a branch that has
a `.dev/xor/` tree, treat it as that branch's local supplement to this
file, not a replacement for it.
