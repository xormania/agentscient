# Skeptic — U0 plan gate, grok's stage-3 suite at `fa0cecb`

```
VERDICT: CHANGES
STAMP: Claude Opus 5 (claude-opus-5)
```

Scope read: `ops/capabilities/tests/{support,test_plan_vet,test_plan_extract,test_plan_faults}.py`
(48 tests), `ops/capabilities/contracts/examples/*` (8 files) and
`contracts/faults/plan.{1..18}.json` + `.meta.json` + `plan.18.md`, against
`ops/docs/scratch/agentscient-u0-plan.md` §3–§5, §7, its ratification
`agentscient-u0-ratification.md`, the parent's §3.3/§3.4/§3.6, and
`in/BRIEF-U0-tests.md`. No implementation read — none exists at this ref.

**Execution note.** This dispatch's sandbox refused every `python3` and `cue`
invocation, so no mutant below was *run*. Each finding names the broken
implementation and carries the command that demonstrates it; findings 4 and 15
depend on a `cue` semantic I could not measure here and are marked PLAUSIBLE.
All others are CONFIRMED by reading the test source against the contract.

---

## Brief fact-check (`in/BRIEF-U0-tests.md`)

| brief claim | holds? |
|:--|:--|
| tests under `test_plan*.py`, stdlib `unittest`, 48 of them | yes — 14 + 7 + 27 = 48; `support.py` is reached because `unittest discover -s` puts the start dir on `sys.path` |
| the 18 faults + example live under the paths the plan names | yes; `plan.18.md` is also present and byte-identical to `examples/plan.md`, which is what lets `vet` reach §4 step 4 |
| the fixture parent binding is coherent | yes — `sha256sum examples/plan.root.json` = `07e04b28…986e` = `examples/plan.json`'s `parent.sha256`. Rule 3 also holds: the leaf's `settled` carries `D-root-one` because the parent's `D-root-one` is `ratified_by: owner`, so `test_settled_dropped` plants a real violation. |
| "every test is red now … not by an import error" | true **only where `cue` exists**. Grok's record (`20260829T170714Z-tests-grok-3ec2f6`) says `Ran 48, failures=48, 0 errors` — so `cue` was on `PATH` in the lane image. On the runner the brief itself measures as cue-less, the same suite is 13 failures and **35 skips**. See finding 2. |
| "the raw-presence, extract and **drift** tests must run without it" | **violated.** The only byte-order drift test (`test_fault_18_drift`) is behind `skip_without_cue()`, and 15 of 18 fault plant-proofs are too. Findings 2 and 3. |
| the two hand-written sidecars in the tree are inputs for the drift/binding tests | not acted on — no test touches `agentscient-u0.plan.json` or U1's. Not a defect (grok's own fixture pair is a better oracle), recorded for the review stage. |

---

## FINDINGS

### [P1] `ops/capabilities/tests/test_plan_vet.py:233` §DefinitionAndEconomics — `--economics` is pinned by two string literals

`test_economics_on_the_clean_leaf_is_quiet` asserts only
`assertIn("carry", text)` and `assertIn("change", text)` over
`stdout + stderr`. Nothing asserts a value, a unit, or a relationship.

Broken implementation it misses: `--economics` that computes nothing and
prints `carry: ?  change: ?`. §3.1 says carry is *bytes of the md + the
sidecar + `scope.owner_words`, × readers* and change is *the summed
`write.minutes` of every `*.plan.json` under `.dev/` whose `parent.id` is this
plan* — the revisit cascade. Neither derivation is observed by any test, so
D-U0-economics' central claim ("a number the gate can compute is never
hand-written") is enforced in one direction only: the refusal of a
hand-written key is tested (faults 15, and `test_a_change_key_…`), the
derivation is not. This is the catalogue's "a test a string can satisfy",
which the brief's own doctrine line calls a defect.

Aggravating: the test is `skip_without_cue()`-gated although carry/change
derivation needs no `cue` at all.

```
# throwaway clone; stub checks/plan_vet.py so `vet … --economics` prints
#   "carry change" and exits 0, then:
python3 -m unittest discover -s ops/capabilities/tests -p 'test_plan*.py' \
  -k economics_on_the_clean_leaf   # green
```

### [P1] `ops/capabilities/tests/support.py:48` §skip_without_cue — 35 of 48 tests skip on the CI runner, and every `vet` test that survives expects a refusal

Census by reading the `skip_without_cue()` calls: without `cue`, the suite
runs 13 tests — 2 `RawPresence`, `test_economics_does_not_skip_a_hand_written_carry`,
faults 7 / 15 / 17, and the 7 extract tests. Skipped: all 9 `RelationalRules`,
15 of 18 fault tests (**including their `prove_plant` calls**, because
`skip_without_cue()` runs before `_assert_planted`), `test_fault_17_passes_cue_vet_c_alone`,
`FaultsSubcommand`, and **all 7 `PositiveControls`**. §7's gate
`plan-vet-tests` is `unittest discover`, which exits 0 on skips.

So in CI there is not one positive control, and **every surviving `vet`
invocation asserts a non-zero exit**. Broken implementation it misses — the
whole of `vet`, replaced by:

```python
doc = json.load(open(sys.argv[2]))
if "parent" not in doc:            die("refused: plan.root-parent")
if [k for k in PLAN_KEYS if k not in doc]: die("refused: plan.absent-key")
e = doc.get("economics") or {}
if "carry" in e or "change" in e:  die("refused: plan.derived-key")
die("refused: plan.stale-parent")   # never exits 0
```

That ten-line stub satisfies all six cue-free `vet` tests, including
`test_fail_fast_names_absent_key_before_derived_key`'s `assertNotIn`. No CUE
contract, no relational rule, no economics, no drift. Because the 15 skipped
faults skip their plant-proof too, a fault file silently degraded to a byte
copy of `examples/plan.json` is also invisible in CI.

```
env -i PATH=/usr/bin:/bin python3 -m unittest discover \
  -s ops/capabilities/tests -p 'test_plan*.py' -v 2>&1 | grep -c skipped   # 35
```

### [P1] `ops/capabilities/tests/test_plan_extract.py:51` §ExtractForm — no cue-free test distinguishes byte drift from semantic drift

`test_check_draws_drift_when_the_sidecar_differs` plants
`planted["id"] = "example/leaf-reordered"` — a **value** change. The staged
sidecar is `shutil.copyfile(EXAMPLES / "plan.json")`, already in sorted-key
form, so no cue-free test ever presents a sidecar that is JSON-equal but
byte-different. The one test that does is `test_fault_18_drift`, which routes
through `vet` and is therefore `skip_without_cue()`-gated.

Broken implementation it misses: `--check` implemented as
`json.loads(sidecar.read_bytes()) == extracted_obj`. Green on every extract
test, and blind to exactly the defect fault 18 was written to catch — the
prose and the sidecar drifting apart in key order. D-U0-extract-form says
"any byte difference"; the brief says drift tests must run without `cue`.

```
# stub extract --check with a semantic compare, then:
env -i PATH=/usr/bin:/bin python3 -m unittest discover \
  -s ops/capabilities/tests -p 'test_plan*.py'   # extract suite green
```

### [P1] `ops/capabilities/tests/test_plan_faults.py:126` §test_fault_17_passes_cue_vet_c_alone — the after-action case is asserted with an invocation that validates nothing (PLAUSIBLE)

The test runs `cue vet -c <plan.cue> <plan.17.json>` and asserts exit 0. A CUE
*definition* is not unified with top-level data unless it is selected —
`cue vet -c -d '#Plan' schema.cue data.json`. Without `-d`, the JSON unifies
with the package's (empty) top level, so the command exits 0 for **any**
document, including faults CUE genuinely catches, and for a `plan.cue`
containing nothing but `package agentscient`.

§9 stage 3 names this the one case to insist on, and §5 says fault 17 "must be
shown to pass `cue vet -c` alone and fail the raw check". As written the first
half is unprovable by this test: it does not distinguish "CUE cannot see an
omitted key" from "this invocation checks nothing". Note the test also uses a
different invocation than §4 step 2 specifies ("with the named definition"),
so it is not evidence about the implementation's own CUE step either.

```
# lane image, once plan.cue exists:
cue vet -c ops/capabilities/contracts/plan.cue ops/capabilities/contracts/faults/plan.6.json
# if this also exits 0 (premises[0].tag = "guessed" is a closed-disjunction
# violation), the test's premise is vacuous. Fix: add -d '#Plan'.
```

### [P1] `ops/capabilities/tests/test_plan_faults.py:152` §FaultsSubcommand — the `faults` subcommand has no negative

`test_faults_is_quiet_when_every_fault_draws_its_refusal` checks that 36 files
exist and that six meta keys are truthy, then asserts `run_plan_vet("faults")`
exits 0. §7's gate `plan-faults` declares it fires on "a fault that vets clean,
or matches the example, or misses its `reject_path`" — **none of the three is
tested**, and the test is `skip_without_cue()`-gated on top.

Broken implementation it misses: `def cmd_faults(): raise SystemExit(0)`. The
18 `_assert_draws` tests exercise `vet`, not `faults`, so the subcommand that
§1 names as one of U0's two done-commands is unpinned end to end.

```
# stub `faults` as an unconditional exit 0, then:
python3 -m unittest discover -s ops/capabilities/tests -p 'test_plan*.py' \
  -k faults_is_quiet   # green (or skipped, which is worse)
```

### [P1] `ops/capabilities/contracts/examples/plan.md:13` — `extract` is never shown a non-empty `units` table

`examples/plan.md`'s third table is a header with zero data rows, and the only
fixture that has a unit (`plan.root.json`) has no `.md` beside it. All seven
extract tests therefore round-trip a document whose `units` is `[]`.

Broken implementation it misses: `units = []`, hard-coded, ignoring the table
entirely — green on all 7.

Worse, the mandated header makes the correct implementation impossible to
demonstrate: §4 fixes it as `| # | unit | deliverables | gate | needs |`,
while §3's `#Unit` is `{id, deliverables, needs, stage}`. There is no `stage`
column and there is a `gate` column with no field behind it, so no `#Unit`
can round-trip through the form the contract prescribes. That is a contract
fault the corpus should have surfaced at stage 2; instead the empty table
hides it. `stage` is not incidental — rule 7 (`plan.stage-blocked`) is keyed
on it, and `plan-drift` (§7) is what is supposed to keep `U0.plan.md` and
`U0.plan.json` one artifact.

```
# add a unit row to a copy of examples/plan.md and re-run extract; there is
# no column for `stage`, so the emitted sidecar cannot equal plan.root.json.
```

### [P2] `ops/capabilities/tests/support.py:76` §prove_plant — the plant-proof is site-blind

`prove_plant` asserts only: `planted != clean`, `planted` is a non-empty dict,
and the top-level key set is intact (or missing exactly `omitted_keys`).
`meta["change"]` — the field that names *where* the plant landed — is only
ever `assertTrue`'d for truthiness (`test_plan_faults.py:168`); it is never
compared against the actual diff.

Broken fixture it misses: a plant whose anchor moved. `plan.6.json` changes the
tag in *two* places (`decisions[0].premises[0]` and `premises[0]`) while its
meta says "premises[0].tag"; nothing notices. §4 requires the fault "differ
from `examples/plan.json` **at the site its `.meta.json` names**". A future
regeneration that lands the change in the wrong field keeps the suite green
while the corpus stops testing the rule it is named for — catalogue item 3.

```
# swap plan.2.json's planted path change onto `discharge.design_to` instead of
# `deliverables[0].path`; prove_plant still passes.
```

### [P2] `ops/capabilities/tests/test_plan_vet.py:177` §RelationalRules — rule 7 has two negatives and no positive at `stage: code`

`test_pending_blocks_a_unit_from_code` and `test_revisit_blocks_a_unit_from_code`
both take `plan.root.json`, set `units[0].stage = "code"`, and flip one
decision field. Every positive control in the corpus sits at `stage: "plan"`.

Broken implementation it misses: `if any(u["stage"] == "code" for u in units):
die("plan.stage-blocked")` — refusing `code` unconditionally, reading neither
`ratified_by` nor `status`. Green on both tests, and it would refuse the root
sidecar the moment U0 itself reaches `code`. §5's own rule ("a negative control
with no positive beside it proved nothing four times") is the one grok applied
to `new: false`, `boundary`, `superseded` and `scope-append` but not here.

```
# stub: refuse any unit at stage code; -k blocks_a_unit_from_code → green
```

### [P2] `ops/capabilities/tests/test_plan_vet.py:226` §DefinitionAndEconomics — `--definition` is pinned by passing its own default

`test_definition_plan_vets_the_clean_leaf` runs `vet … --definition #Plan` —
the documented default — and asserts exit 0. `test_definition_plan_vets_…` is
also the *only* mention of the flag.

Broken implementation it misses: `parser.add_argument("--definition")` with the
value discarded. No test passes a non-default definition, and no test asserts
that an unknown one is refused. D-U0-vet-shape's entire stated purpose is that
"a later `#Workflow` is vetted by the same command without redesign"; §4 grants
that U0 writes no `#Workflow` fixture, but a refusal for `--definition #Nope`
costs one test and would pin the seam.

```
# stub: ignore --definition entirely; -k definition_plan_vets → green
```

### [P2] `ops/capabilities/tests/test_plan_vet.py:137,154` §RelationalRules — two tests pin refusal names that exist nowhere in the contract

`test_an_unknown_decision_status_is_refused` demands `plan.decision-status`;
`test_new_false_cannot_be_owner_ratified` demands `plan.ratified_by`.
`grep -n "decision-status\|ratified_by" ops/docs/scratch/agentscient-u0-plan.md
ops/docs/scratch/agentscient-framework-plan.md` returns neither name.
`plan.decision-status` appears only inside grok's own
`examples/plan.root.json` `refusals` array (fixture data, not contract);
`plan.ratified_by` appears nowhere at all, not even there.

Both conditions are ones §3 says CUE states (`status` is a closed disjunction;
`new: false ⇒ ratified_by: "parent"` is a direct field reference), and §4 step
2 says CUE's errors are re-issued as **`plan.<field>`** — which yields
`plan.status` and `plan.ratified_by`, not `plan.decision-status`. So one test
follows the mechanical rule and the other contradicts it, and neither has a
fault fixture. The implementer must guess a string to turn these red tests
green; a guessed string is not a contract.

Related, unpinned: the ratification adds `ratified_by: "conductor"` for design
decisions, and `examples/plan.conductor.json` is a positive control for it —
but there is no negative anywhere for a `ratified_by` outside the enum, so
`ratified_by: string` in `plan.cue` passes every test that runs.

```
grep -rn "decision-status" ops/docs/scratch/   # only the ratification-era fixture
```

### [P2] `ops/capabilities/tests/test_plan_extract.py:65,80,110` §ExtractForm — three refusals asserted by two-letter substrings

`test_a_field_stated_twice_is_refused` and `test_a_field_stated_nowhere_is_refused`
both assert `assertIn("id", proc.stderr)`; `test_a_wrong_premises_header_is_refused`
asserts `assertIn("premise", proc.stderr)`. The plants themselves are proved
properly — that part is good work — but the observations are proxies.

Broken implementation it misses: `sys.exit("extract: invalid plan document")`.
"id" is a substring of *invalid*, *identifier*, *considered*, *provided*, and
of any `KeyError` traceback naming those; the tests never require a `plan.*`
refusal name, never require the offending field to be named, and never
distinguish "stated twice" from "stated nowhere" — one generic message
satisfies both. §4 is explicit that these are refusals in the copied
`Refusal(claim, expected=, actual=, needed=)` shape.

`test_stale_parent_refusal_uses_the_copied_shape` (test_plan_vet.py:213) is the
only test that inspects the shape at all, and it checks for `refused:`,
`expected`, `needed:` while omitting `actual` and never asserting that the
expected digest is *named* — which is what §4 rule 1 and §2 item 1 promise
("says which digest it expected"). `print("refused: expected needed:")`
passes it.

```
# stub extract to exit 1 with "invalid plan document" on any refusal path;
# -k "stated_twice or stated_nowhere" → green
```

### [P2] `ops/capabilities/contracts/faults/plan.4.meta.json` — rule 6's cross-document half is untested, and the positive controls forbid it

§4 rule 6 words `plan.undelegated` as "every parent `open` lands in a unit's
`decisions` or `open`" — the parent's §3.3 rule 6 second clause, which requires
reading the *child* plan. Fault 4 plants the *first* clause instead
(`open[0].delegated_to = "nosuchunit"`, a within-document check).

Worse than a gap: `plan.root.json`'s sole `open` item is
`{delegated_to: "leaf", what: "author the leaf plan"}`, and its child
`examples/plan.json` has `open: []` and one decision whose sentence is
"The leaf delivers the plan gate as named by the root." — the open item is
listed in neither. So `test_the_clean_root_vets` and `test_the_clean_leaf_vets`
*require* the implementation to skip the clause §4 actually states.

Broken implementation it misses: a `vet` that never opens a child plan. Which
may well be the intended design — but then §4 rule 6 is worded wrong, and that
is a finding to return to the plan, not to leave for the implementer to
discover at stage 4.

### [P2] `ops/capabilities/tests/test_plan_vet.py:58` §RelationalRules — parent resolution is unpinned, and the corpus can be satisfied by hard-coding the fixture

Rules 1, 2, 3, 5 and §3.2's `new: false` check all need `vet` to *find* the
parent sidecar. The only handle in the document is `parent.id: "example"`; the
file is `examples/plan.root.json`, a name that id does not yield. No test says
how the lookup works, and the tests demand it work from two directories that
contain no parent at all: `_planted_child` writes to a
`tempfile.TemporaryDirectory` (`test_settled_dropped`, `test_scope_oversize`,
`test_a_multiline_new_decision…`), and faults 1, 2, 3, 10, 13 and 16 live in
`contracts/faults/`.

Broken implementation it misses: `if doc["parent"]["id"] == "example": parent =
CONTRACTS / "examples" / "plan.root.json"` — a hard-coded fixture path. Green
on all 48, and useless the first time `plan vet` is pointed at
`agentscient.plan.json` and `plans/U0.plan.json`, which is the gate §7 calls
`plan-vet-root` / `plan-vet-self`. Fault 16 (`plan.bound-prose`, "beside an
existing parent sidecar") is entirely a statement about resolution and pins
none of it. One test vetting a real `plans/<unit>.plan.json` layout would close
this.

### [P3] `ops/capabilities/tests/test_plan_vet.py:79,119` §RelationalRules — neither numeric cap has a boundary fixture

`scope.owner_words`: the negative pads to ~2 KB; the largest positive
(`plan.scope-append.json`) is 60 bytes. A cap set anywhere in (60, 2014] is
green. `decision.sentence`: the negative is 513 `x`; the longest positive
sentence is ~55 bytes. A cap anywhere in (55, 513] is green.

Broken implementation it misses: `> 256` in place of `> 1024`, and `> 128` in
place of `> 512`. §10 risk 4 calls the 1024 "a first number, a gate so that
raising it is a diff" — a cap nobody can locate to within a factor of thirty is
not that gate. One 1024-byte positive and one 512-byte positive fix both.

### [P3] `ops/capabilities/contracts/faults/plan.{5,6,9}.meta.json` — three faults name relational refusals for conditions the CUE step catches first (PLAUSIBLE)

`#Gate` declares `quiet_on!`; `#Premise.tag` is a closed disjunction;
`#Decision.premises` is `[#Premise, ...#Premise]`. Under §4's fail-fast order,
step 2 (`cue vet -c`) fires on faults 5, 6 and 9 before the relational rules
run — and §4 says step 2 re-issues CUE's errors as `plan.<field>`, i.e.
`plan.quiet_on`, `plan.tag`, `plan.premises`. The metas demand `plan.gate-half`,
`plan.premise-tag`, `plan.premise-empty`, which §4 lists under step 3 "where
CUE cannot say them precisely enough" — but here CUE can.

Because `_assert_draws` uses `assertRegex` on a substring, an implementation
that prints *both* names passes; so does one that prints the whole 22-name
refusal catalogue on every failure (§5 says "exactly its named refusal"; no
test asserts exclusivity — `test_fail_fast_names_absent_key_before_derived_key`
is the only `assertNotIn` in the suite). Either the CUE step needs a stated
field→name map for those three, or the definitions need loosening; the tests
decide neither.

```
# once plan.cue exists, on the lane image:
cue vet -c -d '#Plan' ops/capabilities/contracts/plan.cue \
  ops/capabilities/contracts/faults/plan.5.json   # expect a quiet_on error
```

---

## What survives

Named here so the review stage knows the refutation was not blanket:

- `test_fail_fast_names_absent_key_before_derived_key` — the suite's only
  ordering assertion, and the only `assertNotIn`. Catches a `vet` that collects
  refusals instead of stopping at the first.
- `test_extract_emits_sorted_keys_indent_2_and_a_trailing_newline` — byte-exact
  on the emitted sidecar, including the trailing newline and `ensure_ascii`
  escaping. Catches `indent=4`, unsorted keys, and a missing final newline.
- `test_prose_outside_tables_and_fences_is_not_read` — plants `example/forged`
  in prose and asserts the landed `id` is `example/leaf`. Catches an extract
  that regexes the whole document.
- `test_fault_13_decision_not_new` and `test_fault_14_decision_unratified` —
  cleanly isolated plants with the matching positives (`plan.new-false.json`)
  beside them. Catches a `new: false` check that compares ids instead of
  premise text.
- The fixture arithmetic: `parent.sha256` really is `sha256sum
  examples/plan.root.json`, and the leaf's `settled` really does carry the
  parent's ratified `D-root-one`, so rule 3's plant is a genuine violation.
  Those were the two ways this corpus could have been quietly unsatisfiable,
  and neither is.

The pattern in the fifteen findings is one thing said three ways: **the plants
are careful and the observations are not.** Almost every assertion is
`assertIn(<name>, stderr)` with no companion assertion about the value, the
exclusivity, or the positive case — and the `cue` skip removes even that from
the runner where the gate actually fires.
