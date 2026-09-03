# Plan — CUE contracts for the workflow mini-app

Planner: Fable 5. Inputs read: `SCOPE.md`, `ops/devlane/workflow/PLAN.md` (611 lines,
the only documentation), `INVENTORY.txt` (49 files, names and sizes only). No
implementation code was available to the planner; every statement below about
what code *looks like* is marked **GUESS** and must be confirmed or reported
infeasible by the worker who actually reads the code.

This file is an input to the contract author's prompt. It does **not**
paraphrase PLAN.md. It names PLAN.md sections and line ranges; the author
reads them directly.

---

## 1. Context

SCOPE.md asks for: CUE contracts over the interfaces the workflow app exposes;
mechanical extractors (stdlib Python, no model, no execution of the inspected
module, no network, deterministic) producing observed JSON; one command that
vets every contract against every observation; and, for each disagreement, a
verdict (documentation / code / contract wrong). Every contract must be shown
to reject something. No module code is edited; no CI wiring.

The pipeline: Conductor (Claude) scoped — done. Planner (this). GPT-5.6 Sol
writes contracts and **does not read implementation code**. Grok 4.6
adjudicates. `cue vet` (v0.17.1) compares.

The central design problem: the contract author may not see code or
artifacts, and the extractor author must not tune extraction to the contracts.
So this plan fixes a **neutral observation shape** per interface (§5) that both
sides implement against independently. The observation is a *container*
(e.g. `tables: [{name, columns}]`), never the documented *values*; the values
come from the code side, the constraints from PLAN.md. Disagreement is the
product, not a failure.

---

## 2. Roles, and what each is given / withheld

Stage each role in a directory holding exactly its "given" set (as this
snapshot was staged for the planner). "Withheld" = not staged and instructed
not to read.

| role | who | given | withheld |
|:--|:--|:--|:--|
| Contract author | GPT-5.6 Sol (ultra) | `SCOPE.md`; `ops/devlane/workflow/PLAN.md` (whole); this plan (whole); `cue` v0.17.1 usage notes in §4 | the other 48 app files (incl. `gate-kinds/*.json`, `migrations/*.sql`, `meta.json`), `wf.db`, `INVENTORY.txt`, all observations, extractors, faults |
| Extractor author | Claude, fresh context (not the conductor's context) | `SCOPE.md`; this plan §§4–6 (layout, observation shapes, vet.py spec); a staged copy of `ops/devlane/workflow/` **with `PLAN.md` removed**, plus `wf.db` | `PLAN.md`, contracts, examples, faults |
| Fault planter | Claude, fresh context | `PLAN.md`; this plan §§4–5 and §8 (fault list); the **clean observations** `obs/*.json` produced by the conductor running `vet.py` in the real tree | contracts, examples, implementation code |
| Adjudicator | Grok 4.6 | per-disagreement **packets** (§9) only, plus `SCOPE.md` and `PLAN.md` whole, plus this plan §5 (shapes) and §9 (verdict schema) | repository access; implementation code beyond the verbatim provenance quotes inside the packet; other roles' notes except the entries cited in the packet |
| Conductor | Claude | everything | — |

The contract author is the only role that never sees code in any form; on
remediation (§7 item 8) it receives the verdict with provenance source quotes
**redacted**.

---

## 3. Interfaces in scope

Everything below is an interface PLAN.md documents *and* that a mechanical
extractor can observe from tracked files (or, for `db`, from the local
`wf.db`). Twelve contracts; the exact PLAN.md sections each draws from are
listed so the author reads them rather than a summary.

| contract (`#Def`) | PLAN.md sections to read | vetted against (artifact) | extractor reads |
|:--|:--|:--|:--|
| `schema` (`#Schema`) | §3.2 (lines 91–108), §2 row for `claims` (line 55), §6 "Migrations" (361–364) | `obs/schema.json` from `migrations/*.sql` | `migrations/0001_foundation.sql` (and any later `00NN_*.sql`) |
| `db` (`#Db`) — optional, environment-local | §3.2, §6 "Gate kinds are data" (328–331), §6 "Migrations" | `obs/db.json` from `wf.db` (read-only) — skipped with a note if absent | `wf.db` via `sqlite3` `mode=ro` |
| `gatekinds` (`#GateKinds`) | §6 (328–360), §3.5 (181–199), §3.3 "Advance is mechanical" (165–167), §3.4 (171–177) | `obs/gatekinds.json` — the spec files verbatim | `gate-kinds/tdd.json`, `gate-kinds/artifact.json` |
| `meta` (`#Meta`) | §6 line 363, §8 (453–479) | `obs/meta.json` | `meta.json` |
| `layout` (`#Layout`) | §8 tree (468–479), §13 "Layout" (565–571), §6 "Migrations" (361–364), D1 (539–540) | `obs/layout.json` | directory walk of `ops/devlane/workflow/`, `.gitignore` files |
| `cli` (`#Cli`) | §4 whole (236–283), §5 "When commits fire" (289–303), D3 (542–543), §11 Slice 1 list (513–519) | `obs/cli.json` | `wf.py` (argparse, by AST) |
| `exitcodes` (`#ExitCodes`) | §4 "Exit codes" (271–274), §2 row (59), §3.1 (86–89) | `obs/exitcodes.json` | `errors.py`, `wf.py` (AST) |
| `canonical` (`#Canonical`) | §2 row for event chain (52), §13 build-order item 1 (574–575), §3.1 | `obs/canonical.json` | `canonical.py` (AST) |
| `events` (`#Events`) | §3.1 (71–89), §3.2 "Chain-resident records" (110–121), §3.3 (123–167), §3.5 (181–199), §3.6 (201–209), §6 "Versioning" (354–360) | `obs/events.json` | every non-test `.py` in the app dir (AST) |
| `commitmsg` (`#CommitMsg`) | §5 "Message format" (305–319), D7 (549–550) | `obs/commitmsg.json` | `gitio.py` (AST) |
| `mcp` (`#Mcp`) | §9 first bullet (485–488), §13 "Layout" for module names | `obs/mcp.json` | `mcp_server.py`, `mcp_launch.py` (AST) |
| `vocab` (`#Vocab`) | §10 (499–507) | `obs/vocab.json` | `checks/vocabulary_wall.py` (AST) |

**Out of scope** (stated, not silently dropped):
- `.github/workflows/wf-verify.yml` (§7) — outside `ops/devlane/workflow/`, not in the inventory, and "no CI wiring".
- Runtime behaviour: exit code per situation, idempotency, compare-and-swap, refusal vs integrity, CAS verify-before-write, git operations, `verify --deep`. Not mechanically observable without executing the module.
- Runtime bytes of chains/attempts/export: there are **no work orders** (SCOPE facts) and no `chains/`, `attempts/`, `objects/` in the inventory, so there is no chain artifact to vet `#Events` against at the byte level. `#Events` is vetted against static literals only (§5.9). See Risks.
- Tests (`tests/*`): not an interface.

---

## 4. Layout and conventions (both sides implement these)

All deliverables live under `ops/devlane/workflow/contracts/` (new directory;
no existing file is edited). If the conductor finds the app's own tooling
objects to a sibling directory, relocate to `ops/contracts/workflow/` — the
plan does not depend on the location.

```
contracts/
  vet.py                  # THE one command
  extract/<name>.py       # one extractor per observation; stdlib only
  obs/<name>.json         # generated by vet.py; never hand-edited
  cue/<name>.cue          # one contract per observation, defines #<Name>
  examples/<name>.json    # contract author's doc-derived positive fixture
  faults/<name>.<k>.json  # fault planter's mutated observation
  faults/<name>.<k>.md    # what changed, PLAN.md lines violated, reject_path
  packets/<id>.md         # generated by vet.py for each disagreement
  verdicts/<id>.json      # adjudicator output
  CONTRACT-NOTES.md       # contract author: every ambiguity and the reading taken
  EXTRACTION-NOTES.md     # extractor author: every GUESS confirmed/adapted/infeasible
  FINDINGS.md             # generated from verdicts + §10 of this plan
  REPORT.json             # generated
```

Name → definition map (fixed): `schema→#Schema`, `db→#Db`,
`gatekinds→#GateKinds`, `meta→#Meta`, `layout→#Layout`, `cli→#Cli`,
`exitcodes→#ExitCodes`, `canonical→#Canonical`, `events→#Events`,
`commitmsg→#CommitMsg`, `mcp→#Mcp`, `vocab→#Vocab`.

**Observation container** (every `obs/*.json`, `examples/*.json`, `faults/*.json`):

```json
{"facts": { ...per §5... }, "provenance": { ...free-form... }}
```

Contracts constrain `facts` with a **closed** definition (CUE definitions are
closed; undocumented extra keys therefore surface as errors — intended) and
declare `provenance: _`.

**Provenance** (extractor side): for every fact, `{"file": "<path relative to
ops/devlane/workflow>", "lines": "a-b", "text": "<verbatim source lines>",
"rule": "<which §5 rule produced it>"}`. The `text` field is what the
adjudicator sees of the code; it must be verbatim.

**Never-vacuous rule** (extractor side): if a rule cannot be resolved, emit
`{"unresolved": "<why>"}` in place of the value — never `null`, never `[]`
— so the contract fails there and the gap becomes a recorded mismatch with a
verdict rather than a silent pass. Observations contain no absolute paths, no
timestamps, sorted lists only (determinism).

**cue usage** (contract side): one standalone file per contract, no
`cue.mod`, no imports beyond the built-ins `list`, `strings`, `struct`,
`regexp`. `vet.py` runs
`cue vet -d '#<Name>' cue/<name>.cue <data.json>` and treats exit ≠ 0 as a
mismatch. Every constraint carries a comment `// PLAN.md §x lines a–b`.

**Fault sidecar** (`faults/<name>.<k>.md`) header fields:
`change:` one line; `violates:` PLAN.md § and line range; `reject_path:` a
regex that must match a line of `cue vet`'s stderr for the faulted file.

---

## 5. Observation shapes (the neutral spec both sides implement)

Shapes are containers. Values are whatever the code/artifact shows. Where a
shape depends on an assumption about code, the line is marked **GUESS** —
the extractor author confirms in `EXTRACTION-NOTES.md` or reports infeasible;
the contract author must not read GUESS lines as statements about the code.

### 5.1 `schema` — from `migrations/*.sql`
```
facts:
  migrations: [string]                 # filenames under migrations/, sorted
  tables: [ {name: string,
             columns: [ {name: string, type: string, notnull: bool, pk: bool} ],  # declaration order
             primary_key: [string] } ]  # sorted by table name
```
Method: load each migration in filename order into an in-memory `sqlite3`
database (`executescript`) and read `sqlite_master` + `PRAGMA table_info`.
Decision: this executes a **data artifact** with the stdlib's reference
parser, not the module's Python — allowed under SCOPE's "no execution of the
module being inspected". Fallback if the conductor rules otherwise:
regex-parse `CREATE TABLE` blocks (and say so in provenance).
Contract draws on §3.2 table (names and columns in code font), §2 line 55
(`owner`→`agent`), §6 migration naming.

### 5.2 `db` — from `wf.db` (optional)
```
facts:
  present: true
  tables: [ ...same shape as 5.1 tables... ]
  gate_kinds: [ {kind: string, version: int|string, spec_sha256_raw: string, spec_sha256_canonical: string} ]
  schema_migrations: [string]          # whatever the version/name column holds, sorted — GUESS: column name unknown
  work_orders_count: int
```
`spec_sha256_canonical` = sha256 over `json.dumps(obj, sort_keys=True,
separators=(",",":"))` of the stored `spec_json`; `_raw` over the stored
bytes. `obs/gatekinds.json` carries the same two digests per file so the
contract can require DB-registry equals files (§6 lines 328–331). Which
digest is "the" `spec_sha256` of §6 is **not stated in PLAN.md** — the
contract author picks one, writes the choice in CONTRACT-NOTES, and the other
is a documented gap. Opened `mode=ro`; nothing of the module runs. Skipped
when the file is absent (REPORT says so).

### 5.3 `gatekinds` — from `gate-kinds/*.json`
```
facts:
  kinds: [ {file: string, spec: <the parsed JSON, verbatim, untouched>,
            sha256_raw: string, sha256_canonical: string} ]   # sorted by file
```
The contract constrains `spec` with a closed `#GateKindSpec` written from §6
(the enumerated field list at lines 330–333 and the illustration 335–348),
§3.5 (outcome values and effect vocabulary, actor: owner), §3.3/§6 (stages
and leave requirements). The illustration is labelled "Illustrative" in
PLAN.md; the author decides, and records in CONTRACT-NOTES, which parts are
normative (field names, effect vocabulary, outcome set for `artifact`) and
which are example values (stage names, globs, argv). Closedness will surface
every field the 61-line `tdd.json` has beyond the illustration — intended.

### 5.4 `meta` — from `meta.json`
```
facts:
  bytes: int
  is_json: bool
  raw: <parsed JSON> | {"unresolved": "not json"}
  version_keys: [string]               # top-level keys matching /version/i, sorted; [] is a real observation here
```
INVENTORY reports `meta.json` as 0 lines. That may mean empty or a single
line with no trailing newline — **not knowable here**; the extractor reports
what is there. PLAN.md §6 line 363 says it carries a format version.

### 5.5 `layout` — from a directory walk
```
facts:
  files: [string]                      # paths relative to ops/devlane/workflow, sorted, excluding contracts/, __pycache__/, *.pyc
  dirs:  [string]
  gitignore: [ {file: string, line: string} ]   # every line of every .gitignore at repo root or under .dev/ whose text contains "db" — GUESS: where the ignore rule lives
```
Contract draws on §8 tree, §13 layout, §6 migration naming, D1. §13 says
"small stdlib-only modules beside it": the contract must *require* the named
files and *allow* others (open list; not closed). `wf.db` will appear in
`files` when present; the contract decides from §8/D1 what that requires
(a matching gitignore line).

### 5.6 `cli` — from `wf.py` by AST  (**GUESS**: argparse with literal strings)
```
facts:
  global_arguments: [ {flags: [string], dest: string|null, action: string|null, nargs: string|null, choices: [string]|null, default_env: string|null} ]
  commands: [ {name: string,
               arguments: [ {flags: [string] | positional: string, action, nargs, choices, required: bool|null} ],
               next_json_keys: [string] | {"unresolved": string},   # only meaningful for name=="next" — see below
               helpers_applied: [string] } ]   # sorted by name
  env_literals: [string]               # string constants matching /^WF_[A-Z_]+$/ anywhere in wf.py
```
Rules: `add_parser("<name>")` → command; `add_argument(...)` on that
sub-parser → argument; arguments added to the root parser → `global_arguments`;
**GUESS**: common flags (`--json`, `--agent`, `--source`, `--no-commit`,
`--allow-dirty`) may be added by a helper function — the extractor follows
one level of helper call statically and lists the helper in `helpers_applied`;
if it cannot, it emits `{"unresolved"}` for that command's arguments.
`next_json_keys`: **GUESS** — keys of dict literals inside the function the
`next` command dispatches to (via `set_defaults(func=…)` or a dispatch table);
else `{"unresolved"}`. For all commands other than `next`, `next_json_keys`
is the literal string `"n/a"`.
Contract draws on §4's table (the verb set — §4 says "One line per command",
so the set is exact, not a subset), the flags named in code font per verb,
"Agent contract" (--json everywhere, --agent/$WF_AGENT on chain-appending
verbs), §5 (`--no-commit`, repeatable `--source`), D3 (`--allow-dirty`), the
`wf next --json` sketch at 278–283 (it is labelled "sketch" — the author
records how much weight it gets). `--json` may be global or per-command: the
contract accepts either by checking `global_arguments` first.

### 5.7 `exitcodes` — from `errors.py` and `wf.py` by AST
```
facts:
  constants: [ {name: string, value: int, file: string} ]    # module-level NAME = <int> and class attributes, names containing EXIT or CODE — GUESS
  exit_literals: [int]                 # ints passed to sys.exit(...), SystemExit(...), or any call whose callee name contains "exit" — sorted unique
  all_codes: [int]                     # union of the two, sorted
```
Contract draws on §4 lines 271–274: the set is exactly {0,1,2,3,64}. Meanings
and which verb returns what are not observable — out of scope, listed in
Risks.

### 5.8 `canonical` — from `canonical.py` by AST
```
facts:
  json_dumps_calls: [ {line: int, keywords: {<kw>: <literal value or "non-literal">} } ]
  hashlib_algorithms: [string]         # attribute names used on hashlib, sorted unique
```
Contract draws on §2 line 52 and §13 line 574–575 (byte-identical to
`json.dumps(obj, sort_keys=True, separators=(",",":"))`) and sha256 throughout
§3. Whether extra kwargs (e.g. `ensure_ascii`) break byte-identity is the
author's reading to record.

### 5.9 `events` — from every non-test `.py` by AST
```
facts:
  types: [ {value: string, files: [string]} ]   # string constants matching /^[a-z]+\.[a-z_]+$/ — GUESS: event types are dotted literals; the regex also catches filenames like "meta.json"; the contract asserts documented ⊆ observed, not equality
  shapes: [ {type: string, keys: [string], file: string, line: int} ]   # GUESS: dict literals containing key "type" whose value is a string constant; keys = its literal keys plus subscript-assigned keys on the same name in the same function
```
Contract draws on §3.1 (event fields in code font), §3.2 chain-resident
records table (the type names), §3.3 receipt fields in code font, §3.5/§3.6.
Constrain only names PLAN.md gives **verbatim in code font**; fields named
only in prose ("check name", "bound red seq", "frozen-set hash", the opening
event's type at §6 line 356) are unconstrained and listed in CONTRACT-NOTES
as doc gaps.

### 5.10 `commitmsg` — from `gitio.py` by AST
```
facts:
  trailer_keys: [string]               # from string constants matching /^[A-Z][A-Za-z-]*:/ — the key before the colon, sorted unique — GUESS
  subject_literals: [string]           # string constants containing "wf(" — GUESS
  literals: [string]                   # all string constants of gitio.py containing ":" (fallback evidence), sorted
```
Contract draws on §5 lines 306–319, D7.

### 5.11 `mcp` — from `mcp_server.py`, `mcp_launch.py` by AST
```
facts:
  server_imports: [string]             # local module names imported by mcp_server.py (a name is local iff <name>.py exists in the app dir), sorted
  launch_imports: [string]
  verb_literals: [string]              # string constants in mcp_server.py equal to one of the §4 verb names — extractor uses the fixed list init open claim release red green check outcome marker advance next status log commit verify export
  uri_literals: [string]               # string constants matching /^[a-z]+:\/\//
```
Contract draws on §9 first bullet only (serves status/next/log; imports the
query layer, not the append layer) with §13's module names (`chain.py` =
append/verify/project, so "append layer" is ambiguous — record the reading).
Everything else about MCP is undocumented (§10 of this plan).

### 5.12 `vocab` — from `checks/vocabulary_wall.py` by AST
```
facts:
  literals: [string]                   # all string constants, sorted unique (f-string literal segments included, flagged in provenance)
  joined: string                       # "\n".join(literals)
```
Contract draws on §10 lines 501–503: each of the twelve reserved terms is a
substring of some literal. **GUESS**: terms may be encoded as a regex (e.g.
`work[ -]order`) — then the vet fails and adjudication decides.

---

## 6. `vet.py` — the one command

`python3 ops/devlane/workflow/contracts/vet.py` (run from the repo root, in the
real tree). Stdlib + `cue` subprocess only. Steps, in order:

1. Run every `extract/<name>.py` → `obs/<name>.json` (skip `db` if `wf.db`
   absent; record the skip). `--check-determinism` runs them twice into a
   temp dir and byte-compares; any diff is a failure.
2. For each `cue/<name>.cue`:
   a. `examples/<name>.json` must **pass** (positive control; a contract that
      rejects the doc's own illustration is wrong).
   b. `obs/<name>.json` must pass **or** every error line must be covered by
      a `verdicts/<id>.json` (id = `<name>-<sha256(error path)[:8]>`).
   c. every `faults/<name>.<k>.json` must: differ byte-wise from
      `obs/<name>.json` and still parse (the fault *landed*); make `cue vet`
      exit ≠ 0; produce a stderr line matching the sidecar's `reject_path`;
      and that line must not already appear in the clean run's stderr
      (attributable to the fault). At least two faults per contract.
3. For every uncovered error in 2b, write `packets/<id>.md` (§9).
4. Validate every `verdicts/<id>.json` (§9): enum, required citations, each
   `quote` appears verbatim in the packet.
5. Write `REPORT.json` and regenerate `FINDINGS.md` from verdicts with
   `doc-wrong` / `code-wrong` / `ambiguous` plus §10 of this plan.
6. Exit 0 iff: all examples pass; every obs mismatch has a valid verdict; all
   faults fire; determinism holds. Otherwise exit 1 and list what is missing.

---

## 7. Work items (each one harness call)

Items 1–4 run in parallel; 5 after 1–2; 6 after 1–5; 7 after 6; 8 after 7;
6→8 at most two rounds; 9 closes.

1. **Extractors A + vet.py** — Claude, fresh context (extractor author).
   Given: SCOPE.md; this plan §§4–6; staged copy of `ops/devlane/workflow/`
   without PLAN.md, plus `wf.db`. Withheld: PLAN.md, contracts, faults.
   Returns: `extract/{schema,db,gatekinds,meta,layout}.py`, `vet.py` per §6,
   `EXTRACTION-NOTES.md` (every GUESS in §5.1–5.5 confirmed/adapted/
   infeasible, with the provenance rule used). Must show determinism
   (two runs, identical bytes) on the staged copy.
2. **Extractors B** — Claude, fresh context (extractor author, may be the
   same prompt template, separate call). Given/withheld as item 1 (plus
   item 1's `vet.py` interface if already available; not required).
   Returns: `extract/{cli,exitcodes,canonical,events,commitmsg,mcp,vocab}.py`,
   appended `EXTRACTION-NOTES.md` (every GUESS in §5.6–5.12). Every
   unresolvable rule emits `{"unresolved": …}`, never a vacuous value.
3. **Contracts A** — GPT-5.6 Sol. Given: SCOPE.md; PLAN.md; this plan.
   Withheld: everything else (see §2). Returns:
   `cue/{schema,db,gatekinds,meta,layout,canonical,exitcodes}.cue`,
   `examples/<same>.json` built only from PLAN.md's own illustrations and
   tables, `CONTRACT-NOTES.md` (every ambiguity, every "illustrative"/
   "sketch" weighting, every prose-named field left unconstrained, with
   PLAN.md line refs). Self-check with `cue vet` against the examples if
   `cue` is on PATH in that harness; otherwise item 6 does it.
4. **Contracts B** — GPT-5.6 Sol, separate call, same given/withheld.
   Returns: `cue/{cli,events,commitmsg,mcp,vocab}.cue`, their
   `examples/*.json`, appended `CONTRACT-NOTES.md`.
5. **Faults** — Claude, fresh context (fault planter). Given: PLAN.md; this
   plan §§4–5 and §8; the clean `obs/*.json` produced by the conductor
   running `vet.py` once in the real tree after items 1–2. Withheld:
   contracts, examples, implementation code. Returns: ≥2 faults per
   contract per §8 (the list in §8 is the minimum; the planter may add),
   each as a full mutated observation + sidecar naming the PLAN.md lines
   the mutation violates and the `reject_path`.
6. **Vet run** — conductor, mechanical: `python3 contracts/vet.py
   --check-determinism` in the real tree. Returns: `REPORT.json`,
   `packets/*.md`, the list of faults that failed to fire (those are
   contract-too-loose defects routed to item 8 as `contract-wrong`).
7. **Adjudication** — Grok 4.6. Given: packets (batched per contract name is
   fine), SCOPE.md, PLAN.md, this plan §5 and §9. Withheld: repo access.
   Returns: one `verdicts/<id>.json` per packet, schema in §9.
8. **Remediation** — routed by verdict `action`:
   `amend-contract` → Sol (given: its own `cue/<name>.cue`, the verdict, the
   cue error, PLAN.md; the packet with provenance `text` **redacted** — Sol
   still reads no code); `amend-extractor` → Claude extractor author (given:
   the verdict + packet, its own extractor); `record-finding` → nothing to
   do, `vet.py` regenerates `FINDINGS.md`; `needs-more-context` → conductor
   extends the packet mechanically (more provenance lines from the same
   file) once, re-adjudicates; a second `needs-more-context` → BLOCKED entry.
   Faults that did not fire → Sol tightens the contract (given the fault
   sidecar, not the fault JSON's origin). Then re-run item 6. Two rounds
   maximum.
9. **Close-out** — conductor: confirm `vet.py` exits 0 (or list BLOCKED
   items), confirm every contract has ≥2 fired faults, deliver
   `FINDINGS.md` (owner-facing: doc-wrong / code-wrong / ambiguous /
   undocumented) and `REPORT.json`.

---

## 8. Firing — minimum faults per contract (doc-derived; planter may add)

Each fault is one change to the clean observation; sidecar cites the PLAN.md
lines it violates.

| contract | faults |
|:--|:--|
| schema | remove table `attempts` (§3.2 l.107); rename `claims.agent`→`owner` (§2 l.55); add a tenth table (§3.2 l.93 "Nine tables") |
| db | drop the `artifact` registry row (§6 l.328–331 registry = files); add `0002_x` to `schema_migrations` with no such file (§6 l.361–364) |
| gatekinds | outcome effect `"approve"` (§3.5 l.185–186 effect vocabulary); `artifact` outcomes missing `denied` (§3.5 l.183); a `checks[]` entry lacking `class` (§6 l.332); `version` as a string (§6 l.336) |
| meta | `version_keys: []` (§6 l.363); `is_json: false` |
| layout | migration named `migrations/1_foundation.sql` (§6 l.361, §8 l.472); `wf.py` removed (§8 l.471); `wf.db` present with no gitignore line (D1 l.539) |
| cli | `red` removed (§4 l.248); `freeze` added (§4 l.238 merged away); `verify` without `--deep` (§4 l.258); `green` without `--json` and no global `--json` (§4 l.265); `open` without `--agent` (§4 l.261–263) |
| exitcodes | add `4`; remove `64` (§4 l.271–274) |
| canonical | separators `[", ", ": "]`; `sort_keys: false` (§2 l.52, §13 l.574); `hashlib_algorithms` gains `md5` (§3 sha256 throughout) |
| events | `receipt.green` removed from `types` (§3.2 l.116); `receipt.red` shape without `exit_code` (§3.3 l.125); `commit.landed` shape without `sha` (§3.6 l.206) |
| commitmsg | drop `Co-Authored-By` (§5 l.314); drop `Event` (§5 l.312) |
| mcp | `server_imports` without `query` (§9 l.487–488); `verb_literals` without `log` (§9 l.485) |
| vocab | drop `packet`; drop `frozen set` (§10 l.501–502) |

`vet.py` proves each fault landed (≠ clean, still JSON), fires (exit ≠ 0),
is attributable (`reject_path` matches a line absent from the clean run).
A contract that fails to reject one of its faults is routed to the contract
author as `contract-wrong (too permissive)` — the fault sidecar is the brief.

---

## 9. Adjudication — packet and verdict

**Packet** `packets/<id>.md`, generated by `vet.py`, contains verbatim:
1. `cue vet` stderr for `obs/<name>.json`, the error line(s) for this id.
2. The whole `cue/<name>.cue` (small), so its `// PLAN.md §…` citations are
   visible.
3. The PLAN.md lines the contract cites for that path, quoted with line
   numbers (Grok also has PLAN.md whole, to catch a wrong citation).
4. The `facts` excerpt at the failing path and every provenance entry for it:
   `file`, `lines`, verbatim `text`, `rule`.
5. The `CONTRACT-NOTES.md` and `EXTRACTION-NOTES.md` entries that mention
   this contract (pre-declared readings and guesses).

**Verdict** `verdicts/<id>.json`:
```json
{"id": "...",
 "verdict": "doc-wrong" | "code-wrong" | "contract-wrong" | "extraction-wrong" | "ambiguous",
 "rule":     "one sentence: what PLAN.md requires here",
 "observed": "one sentence: what the artifact/code shows",
 "because":  [ {"artifact": "PLAN.md" | "cue/<name>.cue" | "<source file>" | "obs/<name>.json",
                "lines": "a-b", "quote": "verbatim, copied from the packet"} ],
 "action":   "amend-contract" | "amend-extractor" | "record-finding" | "needs-more-context"}
```
SCOPE asks for doc / code / contract; `extraction-wrong` is added because an
observation can misrepresent the code, and without it those would be misfiled
as `code-wrong`. `ambiguous` requires `action: record-finding` and goes to the
owner.

**Checkability**: Grok has no repository access — only the packet, PLAN.md,
SCOPE.md and this plan — so a verdict can rest on nothing outside the packet.
`vet.py` enforces: `because` has ≥1 PLAN.md citation and ≥1 citation of the
observation or a source file; every `quote` occurs verbatim in the packet. A
reader who was not there opens the packet, finds the quotes, and re-derives
the one-sentence `rule` vs `observed`. Contradictory or uncited verdicts fail
validation and are returned.

---

## 10. Undocumented — found, and decided

| item | documentation | decision |
|:--|:--|:--|
| `mcp_server.py` (431 l.), `mcp_launch.py` (242 l.) | §9, one bullet, "seams only … not designed here" | contract `#Mcp` limited to the two statements in §9 (three resource names; read-only import rule). Transport, tool list, launch: **no contract**; recorded in FINDINGS as undocumented interface |
| `checks/secret_scan.py` | D8 "day-one security seed: still open" | no contract; recorded as undocumented (D8 open) |
| `checks/diagnostics.py` | §9 one line (class `diagnostics`, `receipt.check` shape) | no dedicated contract; recorded |
| `checks/ci_matrix.py` | §7 parenthetical "(Later: derive the matrix from `wf status --checks --json`)" | no contract; if `status --checks` appears in `obs/cli.json` the `#Cli` closed verb/flag set surfaces it → adjudication → likely doc-gap finding |
| `coord.py` (claims/sessions) | §3.2 tables, §4 verbs | covered by `#Schema` and `#Cli`; no separate contract |
| `query.py`, `gatekinds.py`, `cas.py`, `errors.py`, `verify.py` | internal modules (§13 names neither) | not interfaces; `errors.py` feeds `#ExitCodes`; no other contract |
| `meta.json` reported as 0 lines | §6 l.363 "format version in `meta.json`" | contract written from the doc; the observation decides; expected to be a finding |
| the chain's opening event type (§6 l.356) | unnamed | `#Events` cannot name it; listed as doc gap in CONTRACT-NOTES |
| `wf next --json` keys | §4 "sketch" | contract from the sketch, weight recorded; any mismatch carries the word "sketch" into adjudication via the quoted lines |
| `.github/workflows/wf-verify.yml` | §7 | out of scope (outside the app dir, not in inventory, "no CI wiring") |
| exit-code meanings per verb, idempotency, CAS, compare-and-swap | §3.1, §4 | behavioural; no static observation; out of scope, in Risks |
| runtime chain/export bytes (time format, hash discipline) | §3.1 | no chain artifact exists (no work orders); `#Events` vetted against literals only; Risks |

---

## 11. Risks — what this plan will not catch

1. **Static extraction misses dynamic construction.** AST rules (§5.6–5.12)
   assume literal strings/dicts; helper indirection, loops, or `**kwargs`
   produce `unresolved` entries (surfacing as mismatches) or, worse, partial
   lists that look complete. Mitigation: never-vacuous rule, provenance per
   fact, EXTRACTION-NOTES; not a cure.
2. **The evidence format is vetted only by vocabulary.** No chain artifact
   exists, so §3.1's byte discipline (canonical payload, `time` format, hash
   links, `state_sha256`) is not vetted. A follow-up could generate a fixture
   walk in a throwaway clone (`--no-commit`) — deliberately not in this plan
   because it executes the module and is fiddly; the app's own tests cover it.
3. **"Illustrative"/"sketch" sections** (§6 example, §4 `next` sketch) will
   generate adjudications that are really doc-precision issues; adjudicator
   budget goes there. Mitigation: CONTRACT-NOTES pre-declares the weighting.
4. **Closed gate-kind specs** will flag every key in the 61-line `tdd.json`
   beyond the 13-line illustration — intended, but high volume; batch per
   contract in item 7.
5. **Faults are per-path.** A contract can reject all its faults and still be
   too loose elsewhere. Mitigation: closed definitions and the doc-example
   positive control; not complete coverage.
6. **`db` is environment-local** (`wf.db` untracked); the vetted set differs
   by machine. It is optional and reported as such.
7. **Behaviour is out of scope**: exit-code semantics per verb, refusal vs
   integrity, idempotency, CAS verify-before-write, `verify --deep`,
   auto-commit — PLAN.md's most important promises are behavioural and this
   plan does not test them.
8. **Planner guesses.** Every GUESS line may prove infeasible; then that
   observation is `unresolved`, the contract fails there, and the item is a
   recorded gap — not silently dropped, but not vetted either.
9. **Single adjudicator, packet-bounded.** If the decisive source line is
   outside the provenance excerpt, the verdict is wrong-but-checkable; one
   `needs-more-context` round is allowed.
10. **Location collision**: `ops/devlane/workflow/contracts/` might be walked by
    the app's own tooling; unknown without code. Relocation is one `mv`.

---

## 12. Verification (how the conductor confirms Done)

- `python3 ops/devlane/workflow/contracts/vet.py --check-determinism` exits 0.
- `REPORT.json` shows, per contract: example pass; obs pass or all errors
  covered by valid verdicts; ≥2 faults landed+fired+attributable; extractors
  deterministic; `db` marked skipped or vetted.
- `FINDINGS.md` lists every `doc-wrong`, `code-wrong`, `ambiguous` verdict
  with its packet id, plus the §10 undocumented items.
- `git status` shows only additions under `contracts/` — no module file
  modified (SCOPE boundary).
- No extractor imports anything from the app (`grep -n "^import\|^from"
  contracts/extract/*.py` shows stdlib only) and none opens a socket.
