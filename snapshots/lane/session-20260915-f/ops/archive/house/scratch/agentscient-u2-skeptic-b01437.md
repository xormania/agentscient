# Skeptic — bounded check-tests pass 1, U2 tests vs the U2 plan

Record: `20260831T024411Z-check-tests-claude-b01437`. Role card:
`ops/process/roles/test-skeptic.md` at `b096541`.

VERDICT: CHANGES
STAMP: Claude Opus 5

Under judgment: `ops/capabilities/tests/{test_registry_vet,test_registry_faults,
test_anatomy_vet,test_anatomy_faults}.py` + the U2 half of `tests/support.py`
at `b096541`. 66 test methods (registry 34, anatomy 32). Contract:
`agentscient-u2-plan.md` §§2–6 as ratified by `agentscient-u2-ratification.md`.

STATIC pass. My permission surface refuses interpreters, so nothing below was
executed; every finding is derived from the sources and carries a reproduce
line the conductor can run. Where a finding is against the CONTRACT rather
than the tests it says so in its first clause. No implementation was read
(`checks/registry_vet.py` and `checks/anatomy.py` do not exist; I did not open
`container/errors.py`, and `container/plan_vet.py` was not opened either).
`tests/test_plan_faults.py` was read — it is a landed test, not an
implementation, and it is the precedent F4 measures against.

---

## Answers to the five bounded questions

1. **Fault-name coverage — satisfied for the shapes that are reachable.**
   Every R1–R9 / A1–A9 expectation routes through `support.assert_u2_refusal`,
   which anchors on `refused:\s*<exact name>` *and* asserts the name is the
   sole `registry.*` / `anatomy.*` claim in the output. Nothing is asserted by
   exit code alone or by a substring another refusal would satisfy — with one
   exception, F6 (`test_faults_fires_when_a_fault_matches_the_clean_example`
   asserts only `returncode != 0`). Direction is real: a mutant emitting
   `anatomy.member-missing` for both A3 and A4 dies on A4. The weakness is not
   in the assertion wording but in what the assertion is applied to — see F4.

2. **The undemonstrated gate — pinned two ways of three.** Green
   (`test_faults_is_quiet_…`, both families) and deleted-fixture
   (`test_r10_deleting_r4_…`, `test_deleting_a3_…`, both asserting the exact
   `*.undemonstrated` name, class `finding`, exit 1) are both present. The
   third behaviour §3.4 states — (c) *every fault draws exactly its
   meta-named refusal* — is not pinned on the `faults` runner at all (F7).
   And as written the green half and a faithful §3.4(d) implementation cannot
   both hold (F3).

3. **Both-ways member direction — discriminated, with two holes.** A3 is
   declared-not-present, A4 is present-not-declared in two variants (method
   and annotated attribute), each demanding its own name and naming the
   offending member via `actual=`. Dunder and private names are pinned as
   ignored in the undeclared direction (`test_dunder_and_private_…`, exit 0).
   Holes: the third direction — an `iface` whose named `Protocol` class is not
   in the module at all — has no refusal, no fixture and no test (F8); and
   every member plant lands in `iface[0]`, so an implementation that checks
   only the first declared interface is green (F9).

4. **Mutant CORRECT — yes, a correct implementation fails.** Three
   independent ways. R7 plants a cycle at equal layers, which under §3.2's
   strict `dep.layer < layer` and §5.1's stated first-failure order draws
   `registry.layer`, not `registry.cycle` (F1 — this one also makes
   `registry.cycle` structurally undrawable). The anatomy suite demands the
   drawn claim be the *sole* `anatomy.*` claim, but §5.2 never states
   first-failure-only, and A1/A7 legitimately trip two steps at once (F5).
   `Refusal.__str__` is required to render an `outcome:`/`class:` line that
   §5.3 never asks for (F12). The vacuous-scan honesty line itself is fine —
   `VACUOUS_HONESTY` in `support.py:353` is byte-exact against plan §5.2
   including the em dash — and the abort-on-missing-cue path is exactly
   contract-pinned (named refusal, class `abort`, exit 1, plus a real plant
   proof in `prove_cue_unreachable`).

5. **Green-by-skip — no skip path in the new files, but two silent-unrun
   shapes survive.** `unittest.SkipTest` appears nowhere in the four files;
   `support.skip_without_cue` is U0's and is not called by any U2 test; every
   missing artifact routes through `require_path` → `assertTrue` (a red), and
   the cue-dependent tests assert `shutil.which("cue") is not None` rather
   than skipping. Import failure of `container.errors` surfaces as an ERROR,
   not a pass. The shapes that do survive are at the implementation's end,
   not the harness's: the currency check may no-op on any export without a
   digest and no test notices (F2), and `faults` may never compare a drawn
   name to its meta (F7).

Additionally, outside the five: F2, F3, F6, F8, F10 and F16 are findings
against the CONTRACT — §§3.2, 3.3 and 3.4 name behaviours that either cannot
be implemented as stated or carry no enumerated refusal to assert. They
change the verdict and are reported as their own rows below.

---

FINDINGS:

- **[P1] `ops/capabilities/tests/test_registry_faults.py` §RuntimeRegistryFaults
  / CommittedRegistryFaults (R7):** the cycle plant sets both rows to
  `layer: 1` and makes them depend on each other, then demands the sole claim
  be `registry.cycle`. Under plan §3.2's `dep.layer < layer` (strict) each
  edge of that plant already violates the layer rule, and §5.1 step 3 lists
  `registry.layer` *before* `registry.cycle` with "first failure only" — so a
  correct implementation draws `registry.layer` and `test_r7_…` and
  `test_r7_committed_draws_registry_cycle` both fail. This is also a contract
  finding: a cycle requires an edge with `dep.layer >= layer`, so under the
  stated rule and order the cycle check is unreachable, `registry.cycle` can
  never be demonstrated by a fixture, and §3.4(d) then keeps
  `registry_vet faults` permanently red. Plan §6.2's own R7 parenthetical
  ("equal layers slip past R6's rule only if layer allows; plant accordingly")
  is the warning that was not taken. Broken implementation this hides: none —
  it is the inverse, a correct one is refused; the corpus author will be
  driven to reorder cycle before layer, at which point R6 (whose plant also
  forms a cycle: layer-0 → layer-1 while layer-1 already deps on layer-0)
  starts drawing `registry.cycle` and fails instead. One of §3.2/§5.1 or the
  R6/R7 plants must move.
  Reproduce: `grep -n "dep.layer < layer" ops/docs/scratch/agentscient-u2-plan.md; sed -n '295,320p;408,420p' ops/docs/scratch/agentscient-u2-plan.md; sed -n '193,230p' ops/capabilities/tests/test_registry_faults.py`
  Post-W4: `python3 -m unittest discover -s ops/capabilities/tests -p 'test_registry_faults.py' -k r6 -k r7 -v`

- **[P1] CONTRACT `agentscient-u2-plan.md` §3.2 (and the tests that pin both
  sides):** `#Registry` is `close({capabilities!: [...#Capability]})` — no
  digest field — yet the same section says the export "carries the sha256 of
  the canonical `cue export`", §6.1 says `registry.empty.json` is
  `{"capabilities": []}` "with a current digest", and R9 requires a stale
  digest to draw `registry.stale-export`. §5.1 step 2 runs
  `cue vet -c -d #Registry` on the file that step 4 then digest-checks, so an
  export carrying a digest is refused by closure before currency is reached.
  `test_empty_registry_example_vets` and `test_live_export_is_empty_and_vets`
  pin exit 0 through that path; `test_r9_committed_stale_digest_draws_registry_stale_export`
  pins the other side. Both cannot hold. Surviving mutant if the implementer
  resolves it by keeping the digest out of `#Registry`'s scope: step 4 becomes
  `if "digest" not in doc: return` — the currency check silently does not run
  on the two positive controls and on the live export, which is the exact
  "reports clean when it cannot run" shape §5.1 forbids for cue, and no test
  in this suite detects it. The plan must say where the digest lives (sidecar
  file, or a field `#Registry` admits) before W1.
  Reproduce: `sed -n '186,212p' ops/docs/scratch/agentscient-u2-plan.md; grep -n "registry.empty\|digest" ops/docs/scratch/agentscient-u2-plan.md | sed -n '1,20p'; sed -n '159,183p' ops/capabilities/tests/test_registry_vet.py`

- **[P1] CONTRACT §3.4(d) vs `test_registry_faults.py` /
  `test_anatomy_faults.py` §FaultsSubcommand:** the coverage rule refuses any
  *enumerated* refusal that no committed fault draws, but three enumerated
  names cannot be drawn by a committed fixture at all.
  `registry.cue-unreachable` and `anatomy.cue-unreachable` require the `cue`
  binary to be absent from `PATH` — a property of the environment, not of any
  file in `contracts/faults/`. `anatomy.migrates-empty` has no committed
  fixture under the corpus the tests pin: `A_ROWS[7]` is
  `("anatomy.missing", "rejection")`, and §6.2's A7 row offers
  `migrates-empty` only as an uncommitted "(empty dir variant)". So
  `test_faults_is_quiet_when_every_enumerated_refusal_has_a_firing_fixture`
  (exit 0, both families) and a faithful §3.4(d) implementation are mutually
  exclusive. The surviving mutant is the resolution the implementer will
  reach for unaided: `faults` quietly excludes `abort`-class and
  `*.undemonstrated` names from the coverage set — an undocumented carve-out
  that also excludes anything else inconvenient, with no test standing
  against it. The plan must name the carve-out (or commit an environment-fault
  form), and A7's committed variant must be decided.
  Reproduce: `sed -n '243,262p' ops/docs/scratch/agentscient-u2-plan.md; grep -n "REGISTRY_CLAIMS\|ANATOMY_CLAIMS" -A 14 ops/capabilities/tests/support.py | sed -n '1,40p'; sed -n '361,372p' ops/capabilities/tests/test_anatomy_faults.py`

- **[P2] `ops/capabilities/tests/test_registry_faults.py:280-291` and
  `test_anatomy_faults.py:373-397` (`_assert_planted`):** the committed-corpus
  plant proof is opt-out, and for the anatomy corpus it does not exist.
  Registry: `site = meta.get("site")` with an `else` branch that degrades to
  "bytes differ + is a non-empty dict"; `support.META_FIELDS` is
  `("from","change","violates","reject_path")` — `site` is not required, and
  §6.2's stated meta form does not list it either, so in practice *no* U2
  fixture will carry one and `prove_plant`'s site/exclusivity proof never runs
  over the committed corpus. This is a regression against U0's own discipline:
  `test_plan_faults.py:82` asserts `site, f"fault {n} meta must name site"`
  and 17 of 18 landed `plan.*.meta.json` carry it. Anatomy is weaker still —
  the only proof is `assertNotEqual(rel_files(fault_dir), rel_files(source))`,
  a whole-directory inequality with no named path. Surviving mutant (fixture
  corpus, not code): commit `anatomy.7/` as a byte copy of `anatomy.1/` — both
  are pinned to `anatomy.missing`, `test_a7_committed_draws_anatomy_missing`
  passes, and the migrations rule is demonstrated by nothing. Same for a
  registry fixture rewritten wholesale, or one whose anchor moved so it
  refuses for a reason other than its meta's `change`.
  Reproduce: `sed -n '78,90p' ops/capabilities/tests/test_plan_faults.py; sed -n '263,292p' ops/capabilities/tests/test_registry_faults.py; sed -n '373,398p' ops/capabilities/tests/test_anatomy_faults.py; grep -n "META_FIELDS" ops/capabilities/tests/support.py`

- **[P2] `ops/capabilities/tests/test_anatomy_faults.py` §RuntimeAnatomyFaults
  (A1, A7, A8) — Mutant CORRECT:** `assert_u2_refusal` requires the named
  claim be the *sole* `anatomy.*` claim in the output, but plan §5.2 never
  states "first failure only" (§5.1 states it for the registry; §5.2 does
  not), and the plan's own doctrine — "a Finding is first-class, never
  skipped" — points the other way. A1 removes `faults/`: step 1 draws
  `anatomy.missing` *and* step 5 finds every declared `refusals[].name`
  undemonstrated. A7 removes `migrations/`: step 1 and step 3 both have
  something to say. A correct implementation that reports all outcomes per
  directory fails A1, A7, and any A-row whose plant trips more than one step.
  Either §5.2 gains an explicit ordering-and-stop rule (and the vacuous/finding
  cases are reconciled with it), or the tests must assert "the named claim is
  present and no *unrelated* claim is" rather than sole-claim.
  Reproduce: `sed -n '319,346p' ops/docs/scratch/agentscient-u2-plan.md; sed -n '56,70p;210,223p' ops/capabilities/tests/test_anatomy_faults.py; grep -n "must be the only" -B 4 ops/capabilities/tests/support.py`

- **[P2] `ops/capabilities/tests/test_registry_faults.py:373-385`
  (`test_faults_fires_when_a_fault_matches_the_clean_example`) — proxy
  assertion:** the only assertion after the plant is
  `assertNotEqual(proc.returncode, 0)`. Any nonzero exit satisfies it — an
  unhandled traceback, an `argparse` error, a refusal about an entirely
  different fixture. Surviving mutant: `faults()` that crashes with
  `KeyError` on any corpus it cannot parse; the test is green and the
  §3.4(b) "every fault differs from its source" behaviour is unproven. It
  cannot be strengthened today, which is the contract half of this finding:
  §3.4(b)/(c) name no refusal, so `#RegistryRefusals`/`#AnatomyRefusals` have
  no `*.fault-intact` / `*.fault-mismatch` entry to assert — even though
  §5.3 records that U0 already has `plan.fault-*` names for exactly this, and
  §5.1 requires every refusal drawn to carry "the enumerated name from
  `#RegistryRefusals`". Add the names to §3.4, then assert them.
  Reproduce: `sed -n '373,386p' ops/capabilities/tests/test_registry_faults.py; grep -n "plan.fault-\*\|fault-" ops/docs/scratch/agentscient-u2-plan.md`

- **[P2] `ops/capabilities/tests/{test_registry_faults,test_anatomy_faults}.py`
  §FaultsSubcommand — §3.4(c) unpinned:** three of the four `faults`
  behaviours are tested ((a) clean vets, (b) fault identical to source, (d)
  undemonstrated name); (c) "proves every fault draws exactly its meta-named
  refusal" is tested nowhere against the *runner*. `_assert_draws` does check
  the name, but through `vet` on the fixture path, not through `faults`.
  Surviving mutant: `faults()` iterates the corpus, asserts each fixture exits
  nonzero, and never reads `meta["violates"]`/`meta["reject_path"]` — the
  whole suite is green, and a fixture that starts drawing the wrong refusal
  (the exact drift §3.4(c) exists to catch) lands silently. The missing test:
  rewrite one committed fixture in a scratch tree so it draws a different
  enumerated name than its meta claims, and require `faults` to refuse.
  Reproduce: `sed -n '334,386p' ops/capabilities/tests/test_registry_faults.py; sed -n '438,482p' ops/capabilities/tests/test_anatomy_faults.py`

- **[P2] `ops/capabilities/tests/test_anatomy_faults.py` / `test_anatomy_vet.py`
  §BothWaysMemberCheck — the third direction is uncovered:** every member test
  assumes the `Protocol` class named by `iface[].name` exists in the module
  (`insert_protocol_body` raises if it does not, and A3 plants only a member
  name). No test covers a manifest declaring an `iface` whose class is absent
  from the module entirely. Surviving mutant: `anatomy.py` builds its
  declared↔source comparison only over classes it can locate, so an iface
  with no matching class contributes nothing in either direction and a
  capability may declare interfaces that do not exist — the whole suite stays
  green. Contract half: §5.2 step 4 and `#AnatomyRefusals` enumerate no
  refusal for a declared-but-absent interface, so there is no name to assert;
  §2's "absent from the named `Protocol` class body" silently assumes the
  class is there.
  Reproduce: `sed -n '103,145p' ops/capabilities/tests/test_anatomy_vet.py; sed -n '550,559p' ops/capabilities/tests/support.py; sed -n '326,334p' ops/docs/scratch/agentscient-u2-plan.md`

- **[P2] `ops/capabilities/tests/test_anatomy_vet.py:92` and
  `test_anatomy_faults.py` (A3, A4 ×2) — single-interface blind spot:**
  `goodcap` is pinned only to `assertGreaterEqual(len(manifest["iface"]), 1)`,
  and every member plant targets `manifest["iface"][0]`. Surviving mutant:
  `for iface in manifest["iface"][:1]:` in the member check — only the first
  declared interface is verified in either direction; every later interface is
  unchecked and the suite is green. Note the registry example *is* pinned to
  two ifaces on its layer-0 row (`test_clean_registry_has_two_rows_…:153`);
  `goodcap`, where the member check actually runs, is not. Fix: require
  `goodcap` to declare ≥2 ifaces (§6.1 already says "a module whose `Protocol`
  bodies match the declared members exactly", plural) and plant A4 into the
  last one.
  Reproduce: `grep -n 'iface\[0\]\|iface"\]\[0\]\|assertGreaterEqual' ops/capabilities/tests/test_anatomy_vet.py ops/capabilities/tests/test_anatomy_faults.py`

- **[P2] CONTRACT §3.3 last line — `CONTRACT.md` / `contract.cue` agreement has
  no refusal, no fixture, and no test:** "`CONTRACT.md`'s refusals section and
  `contract.cue` name the same set; the anatomy check compares (§5.2)" — but
  §5.2's five numbered steps never mention either file, `#AnatomyRefusals`
  enumerates no name for a mismatch, §6.2 has no A-row for it, and no test in
  this suite opens them beyond `test_goodcap_is_a_complete_fixture_capability`
  asserting they exist (a presence proxy, catalogue item 5). Surviving mutant:
  `anatomy.py` never reads `CONTRACT.md` or `contract.cue` at all; `goodcap`'s
  three refusal lists may disagree with each other and every test passes. Give
  it a name and an A-row, or delete the claim from §3.3.
  Reproduce: `sed -n '234,242p' ops/docs/scratch/agentscient-u2-plan.md; sed -n '319,340p' ops/docs/scratch/agentscient-u2-plan.md; grep -n "CONTRACT.md\|contract.cue" ops/capabilities/tests/*.py`

- **[P2] CONTRACT §5.2 / §3.4 — the exit code for a `finding`-class outcome on
  `vet` is unstated, and the tests decide it:** A8 and A9 assert
  `returncode == 1` (via `assert_u2_refusal`'s `assertNotEqual(…, 0)`) for
  `anatomy.undemonstrated` and `anatomy.unparsed`, both class `finding`, while
  the vacuous-scan finding exits 0 by §5.2's explicit instruction. `anatomy` is
  registered `ci: true` (§5.4), so whether a finding fails the gate decides
  whether a capability declaring an undemonstrated refusal can land. The
  tests' choice is the right one, but it is inference, not contract: §3.5 says
  only that findings are "recorded rather than absent". State it in §5.2 so
  the implementer is not choosing.
  Reproduce: `sed -n '334,346p' ops/docs/scratch/agentscient-u2-plan.md; sed -n '244,278p' ops/capabilities/tests/test_anatomy_faults.py`

- **[P2] `ops/capabilities/tests/test_registry_faults.py:354-385`,
  `test_anatomy_faults.py:459-481` — the coverage tests mutate the committed
  corpus in the working tree:** `registry.4.json` is `unlink()`ed,
  `registry.1.json` is overwritten with the clean example's bytes, and
  `contracts/faults/anatomy.3/` is `rmtree`'d, each restored only by
  `addCleanup`. A `KeyboardInterrupt`, a crash in the runner, or a concurrent
  gate run (`registry-vet faults` / `anatomy faults` are §8 gates and §5.4 CI
  rows over the same paths) leaves the repo missing a committed fixture — and
  the anatomy restore, `shutil.copytree(snapshot/"anatomy.3", target)`, raises
  `FileExistsError` if anything recreated the directory first, so cleanup can
  fail silently after the test has already reported. Contract half: §5.1/§5.2
  give `faults` no corpus-root argument, so the test author had no scratch
  corpus to point at. Add an optional root argument (or `AGENTSCIENT_FAULTS_DIR`)
  to both `faults` subcommands and run these two tests against a copy.
  Reproduce: `sed -n '354,386p' ops/capabilities/tests/test_registry_faults.py; sed -n '459,482p' ops/capabilities/tests/test_anatomy_faults.py; sed -n '295,332p' ops/docs/scratch/agentscient-u2-plan.md`

- **[P3] `ops/capabilities/tests/support.py:431-456` and
  `test_registry_vet.py:72-88` — `Refusal` rendering is over-specified against
  §5.3:** `assert_u2_refusal` requires every refusal's output to contain a line
  matching `^(?:outcome|class):\s*<class>$`, and
  `test_str_renders_outcome_class_and_remedy` requires the same of `str()`.
  §5.3 requires only that `Refusal` gain a required `outcome` field and that
  `needed` "is documented as the remedy and surfaces as such in `str()`" — it
  never says the class is rendered, let alone on its own line with that label.
  An implementation correct per §5.3 fails every U2 refusal assertion in both
  suites. Relatedly, `test_omitting_outcome_is_refused_construction` accepts
  only `TypeError` while W3 says "`TypeError`/refused construction"; a
  `ValueError` implementation is refused by the test but not by the contract.
  Cheapest fix is to §5.3: state the rendered form, since the tests are
  otherwise right to pin it.
  Reproduce: `sed -n '431,456p' ops/capabilities/tests/support.py; sed -n '286,292p;449,453p' ops/docs/scratch/agentscient-u2-plan.md`

- **[P3] `ops/capabilities/tests/test_registry_faults.py:352`,
  `test_anatomy_vet.py:54-55,114-115,164`, `test_anatomy_faults.py:457` —
  negative-substring assertions can red a correct implementation:**
  `assertNotIn("registry.undemonstrated", combined(proc))` on a *green*
  `faults` run, `assertNotIn("anatomy.member-missing"/"member-undeclared", …)`
  on a green `vet`, and `assertNotIn("clean", text.lower())` on the vacuous
  scan all fail if the check prints a coverage or summary line that merely
  *names* the refusals it verified ("11 enumerated refusals demonstrated:
  …registry.undemonstrated") — which §3.4's "the check list is the test
  manifest" arguably invites. Assert on the refusal grammar
  (`refused:\s*<name>`) rather than bare name presence.
  Reproduce: `grep -n "assertNotIn" ops/capabilities/tests/test_anatomy_vet.py ops/capabilities/tests/test_registry_faults.py ops/capabilities/tests/test_anatomy_faults.py`

- **[P3] `ops/capabilities/tests/test_anatomy_faults.py:224-242` (A7 empty
  variant) and `:244-260` (A8) — the plant proof re-derives its own
  expectation:** both compute `removed` from the observed before/after diff of
  the deletion they just performed and then pass that set to `prove_dir_plant`
  as the *named* paths. The exclusivity property ("changed nothing else")
  therefore compares the operation to itself and can never fail — catalogue
  item 1. Both do assert the set is non-empty, so a no-op plant is still
  caught; the loss is confined to exclusivity. Name the paths from the
  contract instead (`migrations/*`, `faults/*`), as A1 does.
  Reproduce: `sed -n '224,260p' ops/capabilities/tests/test_anatomy_faults.py; sed -n '476,512p' ops/capabilities/tests/support.py`

- **[P3] `ops/capabilities/tests/support.py:550-558` (`insert_protocol_body`)
  — unproven plant:** the anchor is a single-line `^class <Name>\b.*$` and the
  injection uses a hard-coded four-space indent. A `goodcap` module whose
  class header wraps (`class Store(\n    Protocol,\n):`) puts the injected
  lines inside the base list; a differently indented body puts them at the
  wrong level. Either makes the module a `SyntaxError`, and A4 then draws
  `anatomy.unparsed` instead of `anatomy.member-undeclared`. The plant proof
  is `assertIn("def drop", …)` — text presence, not "the module still parses
  and the class still holds the member" (catalogue item 5). The failure is
  loud rather than green, so this is a robustness finding, not a hole; parse
  the planted source with `ast` and assert `drop` is in the class body.
  Reproduce: `sed -n '550,559p' ops/capabilities/tests/support.py; sed -n '113,140p' ops/capabilities/tests/test_anatomy_faults.py`

---

## What survived — named, so the record is not one-sided

These shapes I tried to refute and could not:

- `assert_u2_refusal`'s sole-claim-of-family rule kills the whole class of
  implementations that emit a generic refusal and let the test's substring
  find it — including a check that prints its entire enumerated refusal list
  on every failure.
- `prove_cue_unreachable` is a real plant proof, not an assumption: it
  re-resolves `cue` against the mutated `PATH` and fails if the plant did not
  land. Mutant it catches: an implementation that resolves `cue` through a
  cached absolute path or a `CUE_BIN` env var would… actually survive, since
  only `PATH` is stripped — but the refusal is still required, so the mutant
  fails the assertion, not the plant proof.
- The empty-set trap is closed everywhere I looked: every `for` over fixture
  content is preceded by a count or truthiness assertion
  (`assertEqual(len(caps), 2)`, `assertTrue(manifest["refusals"])`,
  `assertGreaterEqual(len(manifest["iface"]), 1)`, `assertTrue(removed, …)`),
  and the corpus loops iterate a hard-coded `R_ROWS`/`A_ROWS` table drawn from
  §6.2 rather than a glob.
- Every fixture path is guarded by `require_path`, whose failure mode is
  `assertTrue` — a missing U2 artifact is a red with a named reason, never a
  skip and never a silently-passing loop over nothing.
- `VACUOUS_HONESTY` is byte-exact against §5.2 including the em dash, and the
  test requires it on a run that also exits 0 — the mutant that prints
  "0 directories scanned, clean" is caught by the `assertNotIn("clean", …)`
  half (which is also F13's cost, and worth keeping at that price).
- A4's two variants (method *and* annotated attribute) close the mutant that
  walks only `FunctionDef` nodes and ignores `AnnAssign` — §2's "a method or
  annotated attribute" is pinned in both forms.
