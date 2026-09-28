# U1 — vocabulary: `capability` reserved, `service` walled to `.dev/infra/`

Child plan `agentscient/U1` of `ops/docs/scratch/agentscient-framework-plan.md`
§7 row U1, for the tree at `bc5d2c4b5b047d033b125334d0d4fad5f53b3186`.
Read: the brief (`in/BRIEF-U1.md`), the parent plan, the narrow plan §3,
`capability-abstraction.md` §A, the wall (`checks/vocabulary_wall.py`), its
contract (`contracts/cue/vocab.cue`, `extract/vocab.py`, `examples/`,
`obs/`, `faults/vocab.{1,2,3}`), `vet.py`'s head, `test_vocabulary_wall.py`,
`test_guide.py`, `test_check.py` (registration), `gate-kinds/artifact.json`,
`AGENTS.md` §"This file is dev-lane surface", `.dev/ONBOARDING.md`.
Nothing was executed except `grep`, `sha256sum` and `git rev-parse`; every
count below is stamped with this ref. No U0 plan is visible in this
snapshot (no `agentscient/*` ref, no `.plan.json` anywhere under `.dev/`),
so the sidecar follows the parent's §3.2 shape verbatim.

## 0. Scope, settled, and what this unit is

Owner, 2026-08-29: *"frame work first"*; *"i'm worried about conflating
docker service and (Symfony) service"*. Ruling that followed: `service` is
compose's word only (a container, allowed under `.dev/infra/`); the
injected framework object is a **capability** — *"a single coherent thing
the dev-lane can do"* (`capability-abstraction.md` §A).

Settled above and carried by id, not re-argued: `capability` as the axis;
`service` is compose's; framework before surface; launcher pinned; beside
the old apps, fixture, explicit cutover; `wf`→`ledger`; the plan gate
(D-plan-cue, recommended — this plan does not depend on it, see §6).

The unit: make the ruling a **check**, in the mechanism the lane already
has — the vocabulary wall — extended, not forked. Done means the `vocab`
check fires on a planted `service` and on a wall that forgot
`capability`, and is quiet on the tree.

## 1. What the wall is today (measured at bc5d2c4)

- `checks/vocabulary_wall.py` polices **one direction**: dev-lane words
  (`RESERVED`, 12 terms with plurals) must not appear in the *design*
  tree — everything outside `ALLOWED_PREFIXES` (`.dev/ .git/ .github/
  .claude/ .serena/`) and `ALLOWED_FILES` (`AGENTS.md CONTRIB.md README.md
  ruff.toml`), text suffixes only (`.md .txt .rst .adoc .cue .toml .yaml
  .yml` — **not** `.py`, not `.json`). Exit 1 with every hit printed.
- `vocab.cue` (`#VocabFacts`) asserts each reserved term is a substring of
  some string literal in the wall (`_has_wf!: true` etc., 12 rows);
  `extract/vocab.py` produces `obs/vocab.json` by AST; `vet.py` vets the
  example, the observation and faults `vocab.1..3` (each removes one term
  from every literal that carries it; `reject_path` names the term).
- Agreement is already a test: `test_guide.TheSurfaceListsAgree` compares
  the backticked path tokens of the `AGENTS.md` sentence with
  `ALLOWED_FILES ∪ ALLOWED_PREFIXES` in both directions;
  `test_vocabulary_wall` pins `ALLOWED_FILES`, that the wall bites on a
  planted `receipt`, and that the real tree scans ≥ 1 design file.
- Registered once: `gate-kinds/artifact.json` row `vocabulary-wall`
  (`class: policy`, `ci: true`); `test_check` pins the name.

`service` in the tree, whole-word, case-insensitive (`grep -rwi`):

| surface | hits | nature |
|:--|--:|:--|
| `ops/devlane/` (`.py .md .json .cue`) | 2 | both docstrings under `workflow/tests/` — English (`test_ci_shape.py:1306` "the service gave it"; `test_promotion_round2.py:7`) |
| `AGENTS.md:32`, `.dev/ONBOARDING.md:164` | 2 | the idiom "goes into service" |
| `ops/design/ ops/guide/ ops/process/ ops/contracts/ .dev/scripts/` | 0 | — |
| `.github/ .claude/ .serena/`, `CONTRIB.md`, `README.md`, `ruff.toml` | 0 | — |
| `ops/docs/scratch/` | 42 | 40 are research naming Symfony/OSGi/.NET *services* in their own words; 2 are the idiom |
| `.dev/handoffs/` | 2 | systemd "user services" (the runners) |
| `.dev/records/` | 6 | committed dispatch records — immutable evidence |
| `.dev/infra/` | — | **does not exist** |

`capability` in the design tree (`CLAUDE.md`, `README.md`): 0. The design
tree the wall scans today is essentially `CLAUDE.md` (the one file the
existing test says it must still cover).

## 2. The design — one script, two directions

The wall gains a **second pass** in the same file, same registration, same
exit code, reported as a second section of the same output:

```
pass 1  design ← dev-lane words     (unchanged; RESERVED += capability, capabilities)
pass 2  dev-lane ← `service`        (new; scans exactly the surfaces pass 1 exempts)
```

Pass 2, `SERVICE_TERMS = ("service", "services")`, word-boundary,
case-insensitive, over `ALLOWED_PREFIXES ∪ ALLOWED_FILES` (the dev-lane
surface `AGENTS.md` names — so the two passes partition the tree and
nothing is scanned by neither), with suffixes `TEXT_SUFFIXES ∪ {.py, .json}`
(a framework word lands in code and manifests first). Carve-outs, a tuple
`SERVICE_HOMES` with one stated reason each, pinned by test the way
`ALLOWED_FILES` is:

| carve-out | reason (from the table above) |
|:--|:--|
| `.dev/infra/` | compose's home — the *only* place the word is the right word |
| `ops/docs/scratch/` | research that names other frameworks' objects by their names (40 hits); walling it would make the framework unable to describe what it is not |
| `.dev/handoffs/` | dated session handoffs; "user services" is systemd's word for the runners, and a handoff is not rewritten |
| `.dev/records/` | dispatch records are committed evidence and are never edited (`dispatch/CONTRACT.md` §The record) |
| `.git/` | not a tree surface |

Every hit prints as `vocab.service-outside-infra: <path>:<line>: 'service'
in: <text>` and exits 1 — the refusal name the parent §10 assigns, printed
so a reader can grep for it. The four in-scope English hits (§1 rows 1–2)
are **reworded in this unit** ("goes into use"; "whatever the runner host
gave it"), not allowlisted: narrow plan §3's rule that a hit is a rename,
and every allowlist entry shrinks what the wall measures
(`test_vocabulary_wall` docstring). `AGENTS.md` and `ONBOARDING.md` are
edited by this unit anyway (§3); the two test docstrings are two words.

Pass 1 grows `capability`, `capabilities` in `RESERVED`, so the design
tree may not borrow the framework's word either (the owner's definition
is the dev-lane's), and `vocab.cue` grows `_has_capability!: true` (VOC-S13)
so a wall that forgets the word is refused by `cue vet` — that is
`vocab.capability-absent`, drawn by `vet.py` on `faults/vocab.4.json`.

`.dev/infra/` is created with one `README.md` (five lines: compose's home;
the only surface where `service` means what compose means; nothing lives
here yet) so the carve-out names a path that exists — `test_guide` refuses
a named path that does not, and an allowlist entry for a phantom directory
is a rule about nothing.

## 3. Deliverables (the row, as paths)

| path | change |
|:--|:--|
| `ops/devlane/workflow/checks/vocabulary_wall.py` | `RESERVED` += `capability`, `capabilities`; `SERVICE_TERMS`, `SERVICE_HOMES`, `CODE_SUFFIXES`; pass 2; docstring names both directions and every carve-out with its reason; exit 1 on either pass |
| `ops/devlane/workflow/contracts/cue/vocab.cue` | row VOC-S13 `_has_capability!: true` (same comprehension shape as S01–S12) |
| `ops/devlane/workflow/contracts/examples/vocab.json` | `capability` added to `literals`/`joined` (positive control) |
| `ops/devlane/workflow/contracts/obs/vocab.json` | regenerated by `extract/vocab.py` (no extractor change) |
| `ops/devlane/workflow/contracts/faults/vocab.4.json` + `vocab.4.meta.json` | `capability` removed from every literal that carries it; `reject_path: "facts\\.(joined\|literals)\\b\|capability"`; `violates` cites the parent §10 line and this plan §2 |
| `ops/devlane/workflow/tests/fixtures/vocab/` | committed trees: `clean/` (a `.dev/infra/compose.yaml` saying `services:`; an app file saying `capability`); `service-in-app/` (`ops/devlane/x/x.py` with `class Service`); `service-in-json/` (`ops/devlane/x/capability.json` with `"service"`); `capability-in-design/` (`design/spec.md` saying "capability") |
| `ops/devlane/workflow/tests/test_vocabulary_wall.py` | pins `SERVICE_HOMES`; fixtures above: fires with the refusal name / quiet; the real tree is quiet on pass 2 and scans ≥ 1 file on each pass |
| `ops/devlane/workflow/tests/test_guide.py` | `TheSurfaceListsAgree` gains the second sentence ↔ `SERVICE_HOMES` comparison, both directions |
| `AGENTS.md` §"This file is dev-lane surface" | one added sentence: `service` is compose's word and lives only under `.dev/infra/`; `capability` is the framework's; the carve-outs named in backticks; "into service" reworded at line 32 |
| `.dev/ONBOARDING.md` | lines 35–41 name the second direction; line 164 reworded |
| `ops/devlane/workflow/tests/test_ci_shape.py:1306`, `test_promotion_round2.py:7` | one-word rewordings |
| `.dev/infra/README.md` | new, five lines |

Not touched: `gate-kinds/artifact.json` (one row stays), `extract/vocab.py`,
`vet.py`, `imports.json`, the launcher, `levers/`, anything under
`ops/docs/scratch/`.

## 4. Gates — the commands the conductor runs for done

| name | argv | fires on | quiet on |
|:--|:--|:--|:--|
| `wall-tree` | `python3 ops/devlane/workflow/checks/vocabulary_wall.py` | any fixture of §3 planted at the root | the tree at the PR head: both passes report `clean — N file(s)` with N ≥ 1 each |
| `wall-suite` | `python3 ops/devlane/workflow/tests/test_vocabulary_wall.py` | a wall missing `SERVICE_HOMES`, a fixture that no longer fires, a tree hit | the PR head |
| `agreement` | `python3 ops/devlane/workflow/tests/test_guide.py` | `AGENTS.md` and the wall naming different surfaces in either direction | the PR head |
| `contract` | `python3 ops/devlane/workflow/contracts/vet.py` | `faults/vocab.4.json` not drawing `vocab.capability-absent`; `examples/vocab.json` failing; `obs/` stale | the PR head |

The conductor stamps each with the ref. Read roles cannot run python
(handoff 2026-08-28 §4), so these four are the whole of "done".

## 5. Pipeline (pipeline.md) and what each role is denied

1. **tests** — a harness that does not implement, given §§2–4 and the
   current `test_vocabulary_wall.py` / `test_guide.py` as the files to
   extend; denied the wall's new code. It writes the fixtures and the
   red suite; every fixture must prove its plant (differs from `clean/`,
   contains the word) before asserting the exit code.
2. **skeptic** — asks what passes these tests and is still wrong: a pass
   2 that scans only `.md`; a carve-out spelled `ops/docs/` (wider than
   `ops/docs/scratch/`); a `service` regex that also matches `serviced`;
   a wall that reports pass 2 clean after scanning zero files; a fixture
   that fires for a pass-1 reason.
3. **code** — §3, in one PR to `agentscient/dev`, PR body per `CONTRIB.md`.
4. **two reviews** — the four gates green with the ref stamped.

## 6. New decisions — one sentence each, premises tagged

- **D-U1-two-passes** — The `service` rule is a second pass of the same
  `vocabulary_wall.py` over exactly the surfaces the first pass exempts,
  so the two passes partition the tree. *Premises:* the wall's allowlist
  is already the enumerated dev-lane surface and `AGENTS.md` must name
  the same set [read: `test_guide.TheSurfaceListsAgree`]; extend, do not
  fork [read: brief §Constraints]; a second registered row is a second
  thing to keep in agreement [read: `AGENTS.md` §Keep it small]. Status:
  recommended.
- **D-U1-homes** — `service` is allowed under `.dev/infra/`,
  `ops/docs/scratch/`, `.dev/handoffs/`, `.dev/records/` and `.git/`, each
  with a stated reason pinned by test, and nowhere else on the dev lane.
  *Premises:* 40 non-idiomatic hits in scratch research naming other
  frameworks' objects, 2 in handoffs (systemd), 6 in immutable records
  [measured: `grep -rwi` at bc5d2c4]; records are never edited [read:
  `dispatch/CONTRACT.md` §The record]. Status: recommended.
- **D-U1-rename** — The four English hits in scope are reworded, not
  allowlisted. *Premises:* 4 hits, all idiom [measured]; a hit is a rename
  [read: narrow plan §3]; every allowlist entry shrinks the wall [read:
  `test_vocabulary_wall` docstring]. Status: recommended.
- **D-U1-code-suffixes** — Pass 2 scans `.py` and `.json` as well as the
  text suffixes. *Premises:* the object being guarded is a code/manifest
  word (`class Service`, `services.yaml`, a manifest key) [read: parent
  §2.2–2.3]; the two in-app hits are in `.py` files the current wall
  never reads [measured]. Status: recommended.
- **D-U1-capability-both-ways** — `capability` joins pass 1's `RESERVED`
  and `vocab.cue` gains `_has_capability!`. *Premises:* the owner's
  definition is the dev-lane's [read: brief; memo §A]; 0 hits in the
  design tree today [measured]; the contract's shape is one row per term
  [read: `vocab.cue`]. Status: recommended.
- **D-U1-infra-readme** — `.dev/infra/README.md` is created so the
  carve-out names an existing path. *Premises:* `.dev/infra/` is absent
  [measured]; `test_guide` refuses named paths that do not exist [read].
  Status: recommended.
- **D-U1-parent-binding** — Until U0 lands, `parent.sha256` is the
  sha256 of the parent's prose, and U0's `plan extract` re-binds it to
  the parent's `.plan.json`. *Premises:* no `.plan.json` exists at this
  ref [measured]; the brief asks for a prose-digest binding [read].
  Status: recommended.

## 7. Refusals this unit's code draws

`vocab.service-outside-infra` (pass 2, printed per hit, exit 1);
`vocab.capability-absent` (`vet.py` on `faults/vocab.4.json` via
`_has_capability!`). Both from the parent §10.

## 8. Risks stated

(1) `ops/docs/scratch/` is the widest carve-out; it is where the
framework's own plans live, and a plan could write `service` for the
injected object without the wall noticing — the mitigation is the review
stage, and U21 (discharge) removes the scratch docs. (2) `capability` in
`RESERVED` means a future the House product design document cannot use an ordinary
English word; the owner reserved it, and the fix if it bites is a ruling,
not an allowlist. (3) Rule 2 of §3.3 (child deliverables == parent row)
cannot be checked until U0 turns the parent's prose row into data; the
sidecar lists paths and U0's extractor is what makes the equality
mechanical.

## 9. Discharge

Decisions → `DECISIONS.md` under U21; the design (§2) → the wall's own
docstring (already the contract's source); lessons → `mini-app-lessons.md`.
