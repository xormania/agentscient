# Skeptic — U1 vocabulary tests at 3092e13

Role: `ops/process/roles/test-skeptic.md`. Judged: the 22 new methods in
`ops/devlane/workflow/tests/test_vocabulary_wall.py` and
`ops/devlane/workflow/tests/test_guide.py`, plus the four committed trees under
`ops/devlane/workflow/tests/fixtures/vocab/`, against
`ops/docs/scratch/agentscient-u1-plan.md` and
`agentscient-u1-ratification.md` (all seven decisions standing), and the
contract named for this job: owner 2026-08-29 *"frame work first"*.

Implementation not read: `checks/vocabulary_wall.py`, `contracts/cue/vocab.cue`,
`extract/vocab.py`, `vet.py`. The wall's current output wording is taken from
the **pre-existing tests** that assert it (`test_vocabulary_wall.py:110`,
`:101`), not from its source. Python execution is not available to this role
(plan §4 notes the same), so every finding below is established by reading the
tests and by `grep`; reproduce commands are given for each.

```
VERDICT: CHANGES
STAMP: Claude Opus 5 (claude-opus-5)
FINDINGS:
- [P1] ops/devlane/workflow/tests/test_vocabulary_wall.py §TheSecondPassWallsService.test_the_real_tree_is_quiet_on_both_passes_and_scans_files: the test files this commit adds are themselves pass-2 violations, so the tree test can never go green
- [P1] ops/devlane/workflow/tests/test_vocabulary_wall.py §TheWallBites.test_a_zero_file_scan_says_so_instead_of_claiming_clean: `assertNotIn("clean —", proc.stdout)` is asserted over the whole output while the same fixture gives pass 2 one scannable file — contradicts the new tests' `clean — N file` requirement
- [P1] ops/devlane/workflow/tests/test_vocabulary_wall.py §CLEAN_N vs TheWallBites.test_the_repo_wall_still_covers_at_least_one_design_file: pass 1's clean line is required to read both `clean — N design file` and `clean — N file`; no single wording satisfies both
- [P2] ops/devlane/workflow/tests/test_vocabulary_wall.py §test_the_four_english_hits_are_reworded_not_allowlisted: pins a hard-coded four-path list instead of the rule, and the list is already incomplete at the commit that wrote it
- [P2] ops/devlane/workflow/tests/test_vocabulary_wall.py §test_service_homes_are_the_documented_set: three of the five homes have no behavioural test; a wall that declares SERVICE_HOMES and honours only two passes every runnable test
- [P2] ops/devlane/workflow/tests/test_vocabulary_wall.py §TheVocabContractGainsCapability: the `vocab.capability-absent` refusal has no executed test — `vet.py` is never run, the refusal name appears nowhere, and the only behavioural check is skipped on the runner the brief describes
- [P3] ops/devlane/workflow/tests/test_guide.py §test_agents_md_names_the_service_homes: fixed-phrase anchor and an 800-char window, with 23 characters of slack left in the pre-existing 600-char window — prose placement decides the result
- [P3] ops/devlane/workflow/tests/test_vocabulary_wall.py §SERVICE_REFUSAL: the regex stops at the line number; the plan's `'service' in: <text>` tail is unpinned
- [P3] ops/devlane/workflow/tests/test_vocabulary_wall.py §TheSecondPassWallsService.prove_plant: the plant proof searches the whole dirty tree, and every fixture ships a carve-out file containing `services:` that satisfies it
- [P3] ops/devlane/workflow/tests/test_vocabulary_wall.py §test_a_zero_file_pass_2_says_so_instead_of_claiming_clean: never asserts the exit code
- [P3] ops/docs/scratch/agentscient-u1-plan.md §2, §3, §6: four rules the plan states that no test pins — the partition claim, the per-home stated reason, `SERVICE_TERMS`, and `.dev/ONBOARDING.md`'s second-direction lines
```

---

## What survives

These earn their place; each names a broken wall it would catch.

| test | the broken wall it catches |
|:--|:--|
| `test_service_under_infra_not_as_a_prefix_fires` | a carve-out matched by `str.startswith(".dev/infra")` without the trailing slash, or by `"infra" in path` — `.dev/infra-not/compose.yaml` would be silently exempt |
| `test_serviced_does_not_match_as_service` | `SERVICE_TERMS` applied with `in` or `re.search("service")` instead of a word boundary — `def serviced()` fires |
| `test_service_in_an_app_json_fires` | a pass 2 that inherits `TEXT_SUFFIXES` and never opens `.json` (D-U1-code-suffixes) |
| `test_service_in_an_app_module_fires` | the same for `.py`; also a wall matching case-sensitively — the plant is `class Service` |
| `test_service_in_docs_outside_scratch_fires` | a carve-out spelled `ops/docs/` instead of `ops/docs/scratch/` (the exact miss plan §5 asks the skeptic to look for) |
| `test_a_planted_capabilities_in_design_is_caught` | `RESERVED` gaining `capability` but not the plural |
| `test_each_service_home_exists` | a carve-out naming a path that does not exist (D-U1-infra-readme) — legitimately red now, `.dev/infra/` is absent |

`test_a_clean_fixture_is_quiet_on_both_passes` is also a genuine negative
control in one respect: `clean/ops/devlane/x/x.py` says *capability* and the
fixture must stay quiet, which pins that pass 1 does not reach `.dev/`.

---

## [P1] The tests make their own tree test unpassable

`test_the_real_tree_is_quiet_on_both_passes_and_scans_files` (`:339`) runs the
wall over `REPO` and asserts `returncode == 0` and no
`vocab.service-outside-infra`. The two files this commit adds are `.py` files
under `ops/devlane/workflow/tests/` — a pass-2 surface (`.dev/` prefix,
`CODE_SUFFIXES`), not in `SERVICE_HOMES` — and both carry whole-word
`service`/`services` by the test suite's own `SERVICE_WORD` regex:

```
$ grep -cPi "(?<![\w-])services?(?![\w-])" \
    ops/devlane/workflow/tests/test_vocabulary_wall.py \
    ops/devlane/workflow/tests/test_guide.py
ops/devlane/workflow/tests/test_vocabulary_wall.py:14
ops/devlane/workflow/tests/test_guide.py:4
```

Fourteen lines in the wall test (`PLANT_TOKENS` values at `:46`–`:48`, the
`SERVICE_WORD` and `:220` regex literals, the `prove_plant(..., "service")`
arguments at `:232`/`:243`, `assertIn("class Service", ...)` at `:235`,
`assertIn('"service"', ...)` at `:248`, the planted strings at `:260`/`:278`/
`:297`, the docstring at `:10`, the message at `:370`) and four in
`test_guide.py` (`:173`, `:179`, `:196`, `:199`).

The author knew the technique — the committed fixtures carry
`__VOCAB_SERVICES__` tokens precisely "so the real tree is not itself a hit"
(module docstring, `:14`–`:15`) — and did not apply it to the test modules'
own source.

Re-measured at HEAD (3092e13), pass-2 surfaces minus `SERVICE_HOMES`:

```
$ grep -rlPi "(?<![\w-])services?(?![\w-])" \
    --include=*.py --include=*.json --include=*.md --include=*.txt \
    --include=*.rst --include=*.adoc --include=*.cue --include=*.toml \
    --include=*.yaml --include=*.yml \
    .dev .github AGENTS.md CONTRIB.md README.md \
  | grep -v "^.dev/\(docs/scratch\|handoffs\|records\|infra\)/"
.dev/ONBOARDING.md
ops/devlane/workflow/tests/test_vocabulary_wall.py     <- new
ops/devlane/workflow/tests/test_promotion_round2.py
ops/devlane/workflow/tests/test_guide.py               <- new
ops/devlane/workflow/tests/test_ci_shape.py
AGENTS.md
```

Six files, not four. The commit message's measured claim — *"Whole-word
service on pass-2 surfaces excluding homes: 4 hits"* — is stamped at
`4e2be2b`, the commit **before** the one that made it false. The brief said to
re-measure at HEAD (`in/BRIEF-U1-tests.md` §Measured facts); the measurement
was taken at the parent instead.

Consequence: gate `wall-tree` (plan §4, "quiet on the tree at the PR head")
and gate `wall-suite` cannot both be green for any correct implementation.
`TheWallBites.test_the_repo_wall_still_covers_at_least_one_design_file`
(`:103`, pre-existing) also asserts `returncode == 0` over `REPO` and falls
with it. This is not a weak test — it is a test that refuses the correct wall.

**Reproduce:** the two greps above; then, once the wall lands,
`python3 -m unittest test_vocabulary_wall.TheSecondPassWallsService.test_the_real_tree_is_quiet_on_both_passes_and_scans_files`
from `ops/devlane/workflow/tests`.

**Fix direction:** spell the word through the same `__VOCAB_*` token
indirection in the test sources (or build the strings from parts), and replace
the four-path list in `test_the_four_english_hits_are_reworded_not_allowlisted`
with the rule (see the [P2] below) so this class of regression is caught by the
suite instead of by the tree gate.

## [P1] The pre-existing zero-scan test now contradicts pass 2

`TheWallBites.test_a_zero_file_scan_says_so_instead_of_claiming_clean`
(`:90`–`:101`) builds a root holding exactly `.dev/note.md` ("gate receipt
claim") and asserts, over the **whole** stdout:

```python
self.assertIn("nothing to scan", proc.stdout)
self.assertNotIn("clean —", proc.stdout)
```

Under the two-pass design that file is a pass-2 target: `.dev/` is an
`ALLOWED_PREFIXES` entry, `.md` is a text suffix, and `.dev/note.md` is in no
`SERVICE_HOME`. Pass 2 scans one file, finds nothing, and must report
`clean — 1 file(s)` — because `test_a_clean_fixture_is_quiet_on_both_passes`
(`:226`–`:229`), `test_service_under_docs_scratch_is_quiet` (`:289`) and
`test_serviced_does_not_match_as_service` (`:324`) each require at least two
`CLEAN_N` matches, and `CLEAN_N` is `clean [—-] ([1-9]\d*) file`.

So `assertNotIn("clean —", ...)` fails. No implementation satisfies both.

The new `test_a_zero_file_pass_2_says_so_instead_of_claiming_clean` (`:327`)
does the right thing — it slices the report at `"pass 2"` before asserting —
which shows the author had the technique in hand and did not go back to scope
the pass-1 test the same way.

**Reproduce:** `python3 -m unittest test_vocabulary_wall.TheWallBites.test_a_zero_file_scan_says_so_instead_of_claiming_clean`
after the wall lands; it fails on line 101 with a stdout containing pass 2's
clean line.

## [P1] `CLEAN_N` and `clean — N design file` cannot both hold

`TheWallBites.test_the_repo_wall_still_covers_at_least_one_design_file`
(`:110`, pre-existing and unchanged — `git diff --numstat HEAD~1 HEAD` shows
368 insertions and 0 deletions in this file) asserts:

```python
self.assertRegex(proc.stdout, r"clean — [1-9]\d* design file")
```

i.e. the digits must be followed immediately by `" design file"`. The new
`CLEAN_N = re.compile(r"clean [—-] ([1-9]\d*) file")` requires the digits to
be followed immediately by `" file"`, and four new tests require **two**
matches of it (`:227`, `:290`, `:325`, `:347`) — one per pass.

`clean — 1 design file(s)` yields zero `CLEAN_N` matches (`design` intervenes),
so pass 2 alone gives one match and every `assertGreaterEqual(len(nums), 2)`
fails. Dropping `design` from pass 1's wording to satisfy `CLEAN_N` breaks
`:110`. The only escapes are contortions — pass 1 emitting two clean lines, or
a duplicated `clean — N` fragment — which the reviewer would then have to
accept as the wall's report format.

**Reproduce:** `python3 -m unittest test_vocabulary_wall.TheWallBites.test_the_repo_wall_still_covers_at_least_one_design_file test_vocabulary_wall.TheSecondPassWallsService.test_a_clean_fixture_is_quiet_on_both_passes`
— whichever wording the wall picks, one of the two fails.

**Fix direction:** pick one report grammar and pin it once, in one regex used
by both classes.

## [P2] The four-hit test pins a list, not the rule

`test_the_four_english_hits_are_reworded_not_allowlisted` (`:351`) hard-codes
`AGENTS.md`, `.dev/ONBOARDING.md`, `test_ci_shape.py`, `test_promotion_round2.py`
and asserts each carries no whole-word `service`. Its own comment claims *"A
count is not the rule"* — but a four-element literal tuple **is** a count, and
`self.assertEqual(len(paths), 4)` at `:360` asserts that a four-element literal
has four elements: vacuous, catalogue entry 4.

D-U1-rename's rule is *a hit is a rename* — no pass-2 surface outside
`SERVICE_HOMES` carries the word. The gap between the rule and the list is not
hypothetical: the commit that wrote this test added two more violating files
(the [P1] above), and this test passes over both. A reviewer reading a green
`wall-suite` would conclude the rename was complete.

**Broken implementation it misses:** none — worse, it misses a broken *tree*,
which is what D-U1-rename is about. It also cannot notice a fifth English hit
introduced by any later commit.

**Reproduce:** `python3 -m unittest test_vocabulary_wall.TheSecondPassWallsService.test_the_four_english_hits_are_reworded_not_allowlisted`
passes at HEAD while the grep in the [P1] above reports six files.

**Fix direction:** walk the pass-2 surface from `ALLOWED_PREFIXES ∪
ALLOWED_FILES` minus `SERVICE_HOMES` and assert the hit list is empty, naming
every offender. That is the same walk the wall does, but derived from the
contract rather than from the wall's output.

## [P2] Three of the five homes have no behavioural test

`test_service_homes_are_the_documented_set` (`:189`) `ast.literal_eval`s the
`SERVICE_HOMES` assignment out of the wall's source and compares it to a tuple
literal in the test. `test_guide.test_agents_md_names_the_service_homes` and
`test_guide.test_each_named_service_home_exists` do the same read. All three
are assertions about a **declared constant** — catalogue entry 5. A wall that
declares

```python
SERVICE_HOMES = (".dev/infra/", "ops/docs/scratch/", ".dev/handoffs/",
                 ".dev/records/", ".git/")
```

and then exempts only `.dev/infra/` and `ops/docs/scratch/` in the matching
code satisfies every one of them.

Behavioural coverage of the homes, exhaustively:

| home | behavioural test |
|:--|:--|
| `.dev/infra/` | yes — `clean/` fixture's `compose.yaml` says `services:` and the tree must stay quiet |
| `ops/docs/scratch/` | yes — `test_service_under_docs_scratch_is_quiet` |
| `.dev/handoffs/` | **none** |
| `.dev/records/` | **none** |
| `.git/` | **none** |

The tree does carry the word in two of them —

```
$ grep -rlPi "(?<![\w-])services?(?![\w-])" .dev/handoffs .dev/records
.dev/handoffs/2026-08-28T2110Z-fable-relocation-runners-launcher.md
.dev/handoffs/2026-08-28T2328Z-fable-prs-resolved-launcher-fixes.md
.dev/records/dispatches/20260829T154339Z-plan-claude-567623.json
  (+4 more record files)
```

— so `test_the_real_tree_is_quiet_on_both_passes_and_scans_files` *would* have
covered `.dev/handoffs/` and `.dev/records/` incidentally. It cannot: it is the
test the [P1] above shows can never pass. The coverage therefore rests on a
test that will be red for an unrelated reason, which is exactly how a rule
stops being measured. `.git/` is covered by nothing at all, and no test
distinguishes "`.git/` is a home" from "the wall never walks `.git/`" — if the
latter, the entry is a rule about nothing, the same defect D-U1-infra-readme
was written to prevent.

**Broken implementation it misses:** a pass 2 whose exemption is
`path.startswith((".dev/infra/", "ops/docs/scratch/"))` with `SERVICE_HOMES`
declared but unused. Every runnable test stays green.

**Reproduce:** copy `checks/vocabulary_wall.py` to a scratch directory, drop
`.dev/handoffs/`, `.dev/records/` and `.git/` from the exemption test while
leaving the `SERVICE_HOMES` literal intact, and run
`python3 -m unittest test_vocabulary_wall` with the tree test deselected.

**Fix direction:** a positive fixture per home — `.dev/handoffs/h.md`,
`.dev/records/dispatches/r.json`, `.git/config` — each carrying the planted
word and each asserted quiet, the way `ops/docs/scratch/` already is.

## [P2] `vocab.capability-absent` has no executed test

Plan §7 names two refusals. `vocab.service-outside-infra` is asserted by name
in six tests. `vocab.capability-absent` is asserted **nowhere**:

```
$ grep -rn "capability-absent\|vet.py\|obs/vocab" \
    ops/devlane/workflow/tests/test_vocabulary_wall.py \
    ops/devlane/workflow/tests/test_guide.py
(no output)
```

What `TheVocabContractGainsCapability` actually does:

- `test_vocab_cue_has_a_raw_has_capability_check` (`:414`) — three
  `assertRegex` calls against the **text** of `vocab.cue`. A comment line
  containing `_has_capability!: true` satisfies all three. This is the "raw
  check in front of `cue vet`" the doctrine asks for, and as a raw check it is
  fine; it is not evidence that the contract rejects anything.
- `test_fault_vocab_4_exists_and_names_capability` (`:432`) — `is_file()` on
  two paths and `assertIn("capability", data["reject_path"])`. A
  `reject_path` of the bare string `"capability"` passes; the plan's
  `"facts\\.(joined|literals)\\b|capability"` is not pinned, and a fault file
  whose payload is identical to `examples/vocab.json` passes too, because
  nothing checks that `capability` was actually *removed* from the literals.
- `test_cue_vet_draws_capability_absent_on_vocab_4` (`:446`) — the only
  behavioural check, and it is `@unittest.skipUnless(shutil.which("cue"))`.
  The brief states `cue` is absent on the GitHub runner. It also asserts only
  `returncode != 0` and that the output mentions `capability` — it does not
  assert the refusal name.

`vet.py` — the program plan §4 names as the `contract` gate — is never
invoked by any test, and `obs/vocab.json` (plan §3: regenerated) is asserted by
nothing, so a stale observation is invisible to the suite.

**Broken implementation it misses:** `vocab.cue` carrying `_has_capability!`
inside a comment, or `faults/vocab.4.json` that still contains `capability` in
its literals. On CI both are green; the refusal draws on nothing.

**Reproduce:** `python3 -m unittest test_vocabulary_wall.TheVocabContractGainsCapability -v`
on a runner without `cue` — one skip, three text assertions, no behaviour.

**Fix direction:** run `contracts/vet.py` from the suite and assert
`vocab.capability-absent` appears in its output; and assert
`json.load(faults/vocab.4.json)` contains no literal carrying `capability`,
so the fault is proven planted (catalogue entry 3) rather than assumed.

## [P3] The agreement tests turn on prose offsets

`test_agents_md_names_the_service_homes` (`test_guide.py:172`) anchors on the
literal phrase `"compose's word"` (straight apostrophe) and takes an 800-char
window forward. The pre-existing `test_agents_md_names_the_walls_allowlist`
anchors on `"stays on dev-lane surfaces"` and takes 600 chars forward.

```
$ grep -ob "stays on dev-lane surfaces" AGENTS.md   -> 1952
$ grep -ob "^## Attribution" AGENTS.md              -> 2530
```

The existing paragraph ends at byte 2529; the 600-char window ends at 2552.
That leaves **23 characters** of slack before the U1 sentence, which plan §3
places in this same section. If the new sentence opens with a path-shaped
backticked token within those 23 bytes, `named - wall` picks up `.dev/infra`,
`ops/docs/scratch`, `.dev/handoffs` and `.dev/records` — none of which are in
`ALLOWED_PREFIXES` — and the pre-existing test fails. If the implementer
places the new sentence *before* the existing one, both windows move and both
tests fail.

Either way the result turns on prose layout, not on the invariant "AGENTS.md
and `SERVICE_HOMES` name the same set" — catalogue entry 4. The new test also
requires a specific English phrase to appear in a hand-written document, which
is a proxy for the invariant, not the invariant (catalogue entry 5).

**Reproduce:** insert `` `.dev/infra/` `` as the first backticked token of a
sentence appended after `AGENTS.md:45`, then
`python3 -m unittest test_guide.TheSurfaceListsAgree`.

**Fix direction:** delimit the two sentences explicitly (a heading, or a
sentence-terminated slice) instead of a character count, and assert the anchor
was found rather than relying on `str.index` raising.

## [P3] `SERVICE_REFUSAL` stops before the part that carries the evidence

```python
SERVICE_REFUSAL = re.compile(r"vocab\.service-outside-infra: .+:[0-9]+:")
```

Plan §2 fixes the line as `vocab.service-outside-infra: <path>:<line>:
'service' in: <text>` and says it is printed "so a reader can grep for it". The
regex pins the name, a path and a line number, and stops. A wall that prints
`vocab.service-outside-infra: ops/devlane/x/x.py:1:` and nothing further — no
term, no source text — passes all six call sites. The companion
`assertIn("x.py", proc.stdout)` assertions are also unbound to the refusal
line: any occurrence of the substring anywhere in the report satisfies them,
including a banner listing scanned files.

**Broken implementation it misses:** a pass 2 that reports the file but not
which word or which text triggered it, making a hit undiagnosable.

**Reproduce:** `python3 -m unittest test_vocabulary_wall.TheSecondPassWallsService.test_service_in_an_app_module_fires`
against a wall printing the truncated form — green.

## [P3] `prove_plant` can be satisfied by the carve-out file

```python
blob = b"\n".join(file_map(dirty_root).values()).decode("utf-8")
self.assertRegex(blob, rf"(?i)(?<![\w-]){re.escape(word)}(?![\w-])")
```

The proof searches the concatenation of the **whole** dirty tree. Every fixture
ships `.dev/infra/compose.yaml` containing `__VOCAB_SERVICES__` → `services:`,
which matches `(?i)service` on a word boundary. So `prove_plant("service-in-app",
"service")` would report a landed plant even if `__VOCAB_SERVICE_TITLE__` were
never substituted in `x.py` — the corruption is asserted about a file the test
is not testing. Catalogue entry 3.

Both call sites happen to recover: `:235` asserts `class Service` and `:248`
asserts `'"service"'` in the materialised fault file afterwards. The helper is
still the wrong shape, and the next fixture added through it will not have that
luck. `materialize()` itself is a silent `str.replace` — a renamed or misspelt
token leaves the fixture clean and raises nothing.

**Fix direction:** have `prove_plant` take the fault file's relative path and
assert the word landed *in that file*, and have `materialize` raise when a
declared token was not found.

## [P3] The empty pass 2 never checks the exit code

`test_a_zero_file_pass_2_says_so_instead_of_claiming_clean` (`:327`) asserts
`"pass 2"` and `"nothing to scan"` appear and that the pass-2 slice says no
`clean -`. It never asserts `proc.returncode`. A wall that treats an empty
pass 2 as a refusal and exits 1 passes this test — the opposite of the
`test_a_clean_design_artifact_passes` promise for the same shape of tree.

**Reproduce:** `python3 -m unittest test_vocabulary_wall.TheSecondPassWallsService.test_a_zero_file_pass_2_says_so_instead_of_claiming_clean`
against a wall exiting 1 on an empty pass 2 — green.

## [P3] Plan rules no test pins

1. **The partition claim.** D-U1-two-passes: the two passes scan exactly the
   surfaces the other exempts "so the two passes partition the tree and nothing
   is scanned by neither". No test checks it, and as written the claim is false
   for `CODE_SUFFIXES`: a `.py` or `.json` outside `ALLOWED_PREFIXES ∪
   ALLOWED_FILES` (say `design/tool.py`) is skipped by pass 1 on suffix and by
   pass 2 on prefix. Either the plan's claim needs qualifying or pass 1 needs
   the code suffixes; the tests take no position, so whichever the implementer
   picks is unreviewable.
2. **Each home pinned "with its stated reason".** D-U1-homes and the brief both
   say each carve-out is pinned by a test *with its reason*, and plan §3 says
   the wall's docstring "names both directions and every carve-out with its
   reason". The tests pin the tuple only. A wall shipping `SERVICE_HOMES`
   with no reasons anywhere passes.
3. **`SERVICE_TERMS`.** Named as a deliverable in plan §3; `SERVICE_HOMES` and
   `CODE_SUFFIXES` are pinned by `ast` reads, this one is not. Behaviour covers
   the singular and plural, so this is bookkeeping — but the inconsistency is
   worth closing while the other two are being reconsidered.
4. **`.dev/ONBOARDING.md`.** Plan §3 requires lines 35–41 to name the second
   direction. Gate `agreement` (`test_guide.py`) covers `AGENTS.md` only;
   nothing reads `ONBOARDING.md`. A cutover that updates one and not the other
   ships two different texts of the same rule — the defect
   `TheSurfaceListsAgree` exists to prevent.

---

## Brief facts checked

| claim in `in/BRIEF-U1-tests.md` | at 3092e13 |
|:--|:--|
| `.dev/infra/` is absent on this lineage | **confirmed** — `ls .dev/infra` → no such directory; `test_each_service_home_exists` is legitimately red |
| planner measured 4 hits in scope; re-measure at HEAD | **stale** — 6 files at HEAD, two of them added by this very commit (see [P1]) |
| `service` does not occur in `.dev/app` outside tests and `.dev/infra` | **confirmed** — every `.dev/app` hit is under `workflow/tests/` |
| `cue` absent on the runner; those tests skip with a reason | **confirmed in shape** — `skipUnless(shutil.which("cue"))`; see [P2] for what that leaves uncovered |
| ratification: all seven decisions standing | **confirmed** — `agentscient-u1-ratification.md` |
| tests are additions only, implementation untouched | **confirmed** — `git diff --numstat HEAD~1 HEAD`: 435 insertions, 0 deletions, no file under `checks/` or `contracts/` |

## The red run, checked (catalogue entry 6)

The commit claims 22 new methods each red at `4e2be2b` with `FAIL
(failures=1)`, 0 errors. The claim is *shaped* right — per-method runs, a
failure rather than an error, so nothing was red on collection or import. It
could not be re-executed here (this role has no Python), so it is taken as
stated, with one observation: at `4e2be2b` the wall has no `SERVICE_HOMES`, so
`wall_const("SERVICE_HOMES")` returns `None` and the fixture tests fail on the
tuple comparison or on an exit code of 0 — a real assertion failure, but for
several tests the *same* one. Once the constant exists, three of the [P1]/[P2]
findings above change which way those tests fail. A red at the parent is
therefore not evidence that the suite is satisfiable at the child; the three
[P1] contradictions say it is not.

---

Findings: 3 × P1, 3 × P2, 5 × P3. Verdict **CHANGES**. Nothing here asks for a
change to `vocabulary_wall.py`, `vocab.cue` or any prose surface — every
finding is in the tests or in a rule the tests do not yet pin.
