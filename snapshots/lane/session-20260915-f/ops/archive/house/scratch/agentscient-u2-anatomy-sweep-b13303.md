# First-pass report — definition-that-enforces-nothing under `ops/capabilities/contracts/`

Read-only sweep of tree `62bcdeeb3b43ba0c4861c8d126228d0f4de0280c` for the leftover
confirming review `b42c54` named: `#Anatomy` is never a vet target; directory
closure lives in a Python required-set, so editing the CUE definition changes
no check (class: `ops/docs/cue-aar-equality.md`).

Host `cue` at measurement: `v0.17.1`. CI pin `0.14.1` was UNREACHABLE on this
host (no 0.14.1 binary). Confirming-review export
`ops/docs/scratch/agentscient-u2-confirm-b42c54.md` is absent at this SHA;
the leftover is taken from
`.dev/records/dispatches/20260831T043228Z-review-grok-b42c54.json`
(`result.envelope.findings[0]`, severity p2).

Category covered: this class only. A definition is "read" when a check or test
passes it as `cue vet -d` / `cue export -e`, or when it is in the unification
path of such a target. Being printed by `cue def` of the file, named in a plan
sidecar, or `require_path`'d as a file that exists is not a read.

---

## 1. How far the class extends

Every `#` definition under `ops/capabilities/contracts/` (example/fault
`contract.cue` files carry no `#` definitions; they are scraped as text by
`anatomy.names_in`, never `cue vet`'d).

### `plan.cue` — all live via `plan_vet.py cue_vet -d #Plan`

| definition | reader |
|:--|:--|
| `#Plan` | `checks/plan_vet.py:128` (`cue vet -c -d`, default `#Plan`); `tests/test_plan_faults.py:189`; `tests/test_plan_vet.py:340` (`--definition #Plan`) |
| `#NonEmpty` `#Digest` `#Sha` `#Date` `#DeclaredAbsent` `#Interface` `#Premise` `#Parent` `#Scope` `#Settled` `#Decision` `#Open` `#Deliverable` `#Gate` `#Unit` `#Discharge` `#Economics` | unification path of `#Plan` (same `cue vet`) |

`PLAN_KEYS` in `plan_vet.py` restates `#Plan`'s field names for the raw-presence
pass. That is two sources, but `#Plan` is a vet target: editing it changes
`cue vet`. Not this class (see §Outside).

### `capabilities.cue` — all live via `registry_vet.py`

| definition | reader |
|:--|:--|
| `#Registry` | `checks/registry_vet.py:84` (`cue vet -c -d #Registry`); `tests/test_registry_faults.py:161` |
| `#Capability` `#Iface` `#Dep` `#Tag` `#NonEmpty` | unification path of `#Registry` (`capabilities!: [...#Capability]`) |
| `#RegistryRefusals` | `checks/registry_vet.py:26` (`cue export -e #RegistryRefusals`); `faults()` coverage |

### `capability.cue`

| definition | reader |
|:--|:--|
| `#Manifest` | `checks/anatomy.py:60` (`cue vet -c -d #Manifest`); `tests/test_anatomy_faults.py:474,511` (A5/A6) |
| `#Refusal` `#OutcomeClass` `#Iface` `#Dep` `#Tag` `#NonEmpty` | unification path of `#Manifest` |
| `#AnatomyRefusals` | `checks/anatomy.py:28` (`cue export -e #AnatomyRefusals`); `faults()` coverage |
| `#Anatomy` | **nothing** — finding |
| `#Capability` | **nothing** — finding (`#Manifest` restates the fields; it does not unify `#Capability & {refusals!: …}`) |

### `outcome.cue` — file is never a `cue` argv

| definition | reader |
|:--|:--|
| `#Refusal` `#OutcomeClass` `#NonEmpty` | **nothing** — finding. Tests `require_path` the file (`test_registry_vet.py:219`, docstring of `test_anatomy_vet.py`). The taxonomy that actually vets is the duplicate in `capability.cue` (`#Manifest.refusals`). `container/errors.py:2` restates the four classes as `OUTCOMES`. |

`cue export -e '#Refusal'` on either file fails the same way (required fields
absent): `#Refusal` is a schema, not a value. Only the copy sitting in the
file passed to `cue vet -d #Manifest` constrains a document.

### Class members (definitions read by nothing)

1. `capability.cue` `#Anatomy`
2. `capability.cue` `#Capability`
3. `outcome.cue` `#Refusal`, `#OutcomeClass`, `#NonEmpty` (one unused file)

No other `#` definition under this tree is unread.

---

## 2. Fix shape for `#Anatomy`

Plan §5.2 step 1 says directory closure is "against `#Anatomy`". The check
implements a hand-written set instead (`anatomy.py:92-99`, names without
trailing slashes, `module` taken from the manifest, `migrations` added from
`tags`).

### Measured against the schema as written

`#Anatomy` is an incomplete closed schema (`!: true` keys plus `module!: #NonEmpty`
plus `"migrations/"?: true`). At this host:

| command | result |
|:--|:--|
| `cue export -e '#Anatomy' capability.cue` | rc=1, every required field "not present" |
| `cue vet -c -d '#Anatomy' capability.cue goodcap/capability.json` | rc=1, `#Manifest` keys `field not allowed` (wrong document) |
| `cue vet -c -d '#Anatomy'` against a **synthesized listing** `{"capability.json": true, …, "module": "goodcap.py", "tests/": true, …}` | good rc=0; omit `tests/` rc=1 required; extra `notes.md` rc=1 not allowed; `migrations/` present rc=0; `module: ""` rc=1 |
| scratch-copy of the check tree with `"README.md"!: true` added to `#Anatomy`, then `anatomy.py vet goodcap` | **rc=0** (silence) |
| same copy with `"tests/"!: true` removed, then `vet goodcap` | **rc=0** (silence) |

So: naive export of `#Anatomy` does not work; naive vet against `capability.json`
does not work; a directory-listing JSON **can** be a vet instance; today's
Python check does not build one.

### Option A — derive the Python set from the parsed CUE

Python already does this for the sibling map: `cue export -e '#AnatomyRefusals'`.
Do the same for the directory names, then keep filesystem tests in Python.

Tradeoffs:

- Single source for the name set. A CUE edit becomes a check change. Matches
  the landed `#AnatomyRefusals` / `#RegistryRefusals` pattern.
- `cue export -e '#Anatomy'` **cannot** be that parse: the schema is incomplete.
  Dummy-unification (`#Anatomy & {…true…}`) is circular (you must already know
  the required keys to fill them). Real A against the schema-as-written is
  `cue def -e '#Anatomy'` (measured: prints the quoted keys with `!:` / `?:`)
  or a rewrite of `#Anatomy` into a **concrete value** (lists of required /
  optional / directory names) that `cue export -e` can emit.
- `module!: #NonEmpty` is not a directory entry; the deriver must skip it and
  keep reading the filename from the manifest. Trailing slashes on `"tests/"`
  must be stripped to match `Path.name`.
- `"migrations/"?: true` is CUE-optional, not "required iff `migrates` ∈ tags".
  Putting that conditional inside `close()` is cue-aar lesson 3 (un-closes).
  The iff stays in Python under either option.
- File-vs-directory (the `tests` file that must draw `anatomy.missing`) stays
  in Python, or is encoded only by the trailing-slash convention.

### Option B — make `#Anatomy` itself a `cue vet` target

Python walks the directory, writes a listing JSON (dirents → `true`, trailing
slash on directories, `module` from the manifest), and `cue vet -c -d #Anatomy`
that JSON. Missing required keys and extra keys then come from CUE closure.

Tradeoffs:

- Uses `#Anatomy` as written as a vet target. Measured: the listing shape
  already vets. Closest to the plan's "against `#Anatomy`" wording.
- The listing is a document **Python wrote**. cue-aar lesson 4: if the
  projection fills a default, missing evidence wears the shape of a complete
  record. A projection that forgets trailing slashes, drops `module`, or
  omits a dirent makes CUE agree with the lie.
- `module` mixed into a directory schema forces the projection to inject a
  string field and to **exclude** the module filename from extra-key dirents
  (`goodcap.py` is not an `#Anatomy` key). That adapter is load-bearing.
- Untagged `migrations/` is `anatomy.extra` in Python today and **legal**
  under `#Anatomy`'s `?:`. Option B as the sole closure check regresses that
  rule unless Python still owns the iff — in which case B does not replace
  the Python set, it duplicates it, and the two can disagree.
- File-vs-directory and `anatomy.migrates-empty` remain Python regardless.
- Cannot `cue vet` `capability.json` as `#Anatomy`; that was measured red.

### Recommendation: A, with `#Anatomy` exported as a concrete value

Do not make `#Anatomy` a vet target of a synthesized listing (B). The schema
mixes directory booleans, a module string, and an optional migrations key
whose real rule is conditional. B still needs Python for the parts CUE
cannot see, and the listing JSON is a second document that can hide a bad
walk. That is the class again, one layer down.

Do not parse `cue def` as a long-term deriver either: its output is a printer
format (`_#def`, `NONEMPTY.#x` at this cue), not a contract.

Rewrite `#Anatomy` to a concrete exportable value in the same shape as
`#AnatomyRefusals` (required files, required dirs, optional dirs), `cue export
-e '#Anatomy'` into `anatomy.py`, and drop the hand-written `required = {…}`.
Keep migrates-iff, empty-migrations, and file-vs-directory in Python. Delete
or stop claiming the `close({filename!: true})` schema unless a later unit
has a real instance document for it.

If the schema-as-written must be kept for plan-text stability, parse it once
via `cue def -e '#Anatomy'` **and** pin that parse with the CUE-edit tests
in §3; do not also cue-vet a listing.

---

## 3. Tests that would pin the chosen shape (A)

Existing A1 (`faults/` removed → `anatomy.missing`) and A2 (`notes.md` →
`anatomy.extra`) pin the **Python** set, not the CUE. A2's file body even
says `not in #Anatomy` and that string is not read. `test_goodcap_vets` is
the quiet arm for the current goodcap, not for a CUE edit.
`test_capability_cue_is_present_for_vet` only `require_path`s the file.
`ANATOMY_ENTRIES` in `tests/support.py:368-376` is a **third** hand copy
(trailing slashes, no `module`); `test_goodcap_is_a_complete_fixture_capability`
iterates it. After A, that tuple must die or be derived from the same export.

Pins that would catch today's silence (all scratch; never edit committed
`capability.cue`):

1. **CUE-add → missing (negative).** Scratch-copy the check package
   (`checks/anatomy.py` + `contracts/capability.cue` + `container/errors.py`,
   because `CONTRACTS` is `Path(__file__).parents[1] / "contracts"` and is
   not overridable). Add `"README.md"!: true` (or a concrete-value equivalent).
   `vet` goodcap must draw `anatomy.missing` with `README.md` in `actual`.
   Today this copy exits 0 — that is the class. After A it must fire.
2. **CUE-remove → extra (negative).** Drop `guide.md` from the CUE name set.
   `vet` goodcap must draw `anatomy.extra` with `guide.md` in `actual`.
   Today exits 0.
3. **Comment-only / `#AnatomyRefusals` remedy-text edit (positive).** goodcap
   still vets 0. Stops a parser that treats any CUE byte change as a miss.
4. **Keep A1 and A2** as filesystem plants against an unedited CUE, so a
   deriver that returns `[]` cannot hide behind CUE-edit tests that fail
   everything.
5. **Keep the `tests` file (wrong kind) → `anatomy.missing`.** Trailing-slash
   strip must not re-open b42c54's closed P1.
6. **Untagged `migrations/` → `anatomy.extra`; tagged empty → `anatomy.migrates-empty`.**
   The iff must remain Python; a CUE `?:` must not start accepting untagged
   migrations.

If B were chosen instead (not recommended), the argv pin is: `anatomy.cue_check`
(or the closure step) contains `-d`, `#Anatomy`, and a listing path that is
not `capability.json`; plus (1)–(3) still, because a `-d #Anatomy` against
the manifest was measured to fail for the wrong reason and would not pin
closure.

The check-path binding is a test constraint either way: a CUE plant that
edits the committed file is not a test, and `anatomy.py` cannot see a
scratch `capability.cue` unless the test copies the package (as this sweep
did) or the check grows a contracts-root argument (`faults` already takes
`corpus_root`).

---

## Outside these questions (changes the picture only as noted)

- **Confirming-review markdown absent** at the path the brief named. The
  leftover was recovered from the dispatch record at this SHA. Does not
  change the class; changes only the citation.
- **Host cue v0.17.1 vs CI 0.14.1.** Export-failure of incomplete `#Anatomy`
  and listing-JSON vet behaviour were measured on 0.17.1. 0.14.1 is
  UNREACHABLE here; do not treat the listing-JSON rc=0 as proved on the pin.
- **Dual-source Python keys that are NOT this class:** `PLAN_KEYS` vs `#Plan`,
  `FIELDS` vs `#Capability` in `capabilities.cue`, `MANIFEST_KEYS` vs
  `#Manifest`. Those CUE definitions are vet targets. They can still drift
  from the raw-presence lists, but editing CUE is not silent. `#Anatomy` and
  `outcome.cue` are.
- **b42c54 P3** still holds: tests pin `REGISTRY_CLAIMS` / `ANATOMY_CLAIMS`
  and `R_ROWS` / `A_ROWS` while checks no longer have `ROWS`. That is the
  test-side of the same class for the *refusal maps* (which the checks now
  export). Out of scope except that §3's `ANATOMY_ENTRIES` is the anatomy
  directory's copy of that P3.
- **No `cue import` among the four contract files.** Duplicated
  `#NonEmpty` / `#Iface` / `#Dep` / `#Tag` / `#Capability` / `#Refusal` /
  `#OutcomeClass` cannot unify across files. `outcome.cue` cannot become a
  vet target by being the "canonical" copy until something loads it.
- **Example/fault `contract.cue`** have no `#` definitions and are never
  `cue vet`'d; `names_in` is a regex scrape. Not this class (they are not
  definitions). A later unit that treats `contract.cue` as CUE would need
  its own sweep.
