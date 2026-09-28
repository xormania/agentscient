# opus adversarial-review 20260829T211259Z-review-claude-380689 — ref 938d5c7

verdict: CHANGES  counts: {'findings': 15, 'high': 3, 'medium': 7, 'low': 5, 'gates_rerun': 0, 'gates_rerun_blocked': 4, 'files_inspected': 24}

## note
What holds. The five homes are exactly the ratified set and agree across all four places they are written: SERVICE_HOMES (vocabulary_wall.py:58-64), the docstring reasons (:21-24), AGENTS.md:47-50, and HOME_REASONS (test_vocabulary_wall.py:50-56); each is pinned to exist (two separate tests) and .dev/infra/README.md was created so .dev/infra/ is not a rule about nothing. The four-hit rewording is faithful: AGENTS.md:32 and .dev/ONBOARDING.md:166 both take 'goes into use'; test_ci_shape.py:1306 takes 'whatever the runner host gave it', the plan's exact wording. test_promotion_round2.py:7 is the one that is not a one-word swap — 'Ahead therefore REFUSES service naming the two ways out' became 'Ahead therefore REFUSES while naming the two ways out', dropping the object of the refusal; the sense survives, so I am not filing it. The suite is genuinely adversarial in places the skeptic asked about: .dev/infra-not/ is proved not to match as a prefix, 'serviced' is proved not to fire, .github/ is proved to fire while .git/ does not, and both fixture families prove their plant against clean/ before asserting an exit code. Counting 34 + 9 checks out against the method list. Three things I would not merge without an answer. R1 is the one that matters most: the unit reserves two terms and the contract pins one, and the shipped fault proves it by still carrying 'capabilities' — the wall's plural can be deleted and cue vet will not notice. R2 makes pass 2's clean line overstate by 68 files on this tree and makes the zero-file guard unreachable when every pass-2 file is exempt, which is the precise thing the wall's own docstring says must never happen; the suite currently depends on the miscount rather than catching it. R3 is a scope question for the conductor, not a bug: extract/vocab.py and vet.py are on the plan's 'Not touched' list and both were edited to make U1's own assertions come out true, which is a decision the ratification never took. On the owner's aim: the conflation is walled on the dev lane in prose and in .py/.json, but the walled word is still reachable by the three spellings the docker lane will actually use — hyphenated compose service names (R5), compound identifiers and manifest file names (R6), and shell scripts (R7) — and .github/ is refused for syntax it cannot avoid (R4). Note also that the design tree is walled against 'capability' but not against the compose term in either direction, so a the House product design artifact can still call an injected object a service; that is what the plan says, but it is worth the owner seeing it stated plainly before U21 discharges these decisions.

## findings
### 1. severity: high | where: ops/devlane/workflow/contracts/cue/vocab.cue:122
- **id:** U1-R1
- **verdict:** CONFIRMED
- **category:** contract-coverage
- **also:** ops/devlane/workflow/contracts/faults/vocab.4.json:45, ops/devlane/workflow/tests/test_vocabulary_wall.py:624
- **summary:** VOC-S13 pins `capability` only. `capabilities` — the other term U1 adds to RESERVED — is pinned by nothing, because the substring trick that makes one row cover singular and plural for every other term fails here.
- **detail:** S01-S12 work because the singular is a prefix of the plural: strings.Contains(literal,"gate") is true of "gates", Contains(...,"claim") of "claims". "capabilities" does NOT contain "capability" (capabilit+ies vs capabilit+y), so the S13 comprehension never fires on it. The proof is in the shipped fault: the jq filter recorded at 20260829T175226Z-code-codex-1eae03.json:180 selected out every literal containing "capability", and vocab.4.json:45 still carries "capabilities" — yet the fault is asserted (and recorded) to draw vocab.capability-absent. So the row keys on one term. Delete "capabilities" from RESERVED and cue vet passes; the wall silently stops refusing the plural in the design tree and the contract does not notice. test_fault_vocab_4_removes_capability_from_literals cannot catch this either: assertNotIn("capability", "capabilities") is true.
- **reproduce:** grep -n '"capabilities"' ops/devlane/workflow/contracts/faults/vocab.4.json   # -> 45, still present in facts.literals
jq '.facts.literals |= map(select(. != "capabilities")) | .facts.joined = (.facts.literals|join("\n"))' ops/devlane/workflow/contracts/obs/vocab.json > /tmp/nocaps.json
cue vet -d '#Vocab' ops/devlane/workflow/contracts/cue/vocab.cue /tmp/nocaps.json; echo $?   # expected 0 — a wall that forgot `capabilities` is accepted
- **against:** plan §3 row vocab.cue ("same comprehension shape as S01-S12"); D-U1-capability-both-ways; ratification row 5

### 2. severity: high | where: ops/devlane/workflow/checks/vocabulary_wall.py:166-171,190
- **id:** U1-R2
- **verdict:** CONFIRMED
- **category:** false-evidence
- **summary:** Pass 2's `clean — N file(s) scanned` counts files it never opened. `service_scanned += 1` runs before `if exempt: continue`, so every file under the five homes is reported as scanned.
- **detail:** On this tree the pass-2 candidate set with the scanned suffixes is 647 files under .dev/.github/.claude/.serena plus 4 root ALLOWED_FILES = 651 (the figure in the code record), of which 68 are under .dev/records/, ops/docs/scratch/, .dev/handoffs/, .dev/infra/ and were skipped unread. This is the exact failure the wall's own docstring at lines 151-159 was written to prevent — "'nobody looked' reads exactly like 'we checked'" — and it defeats the zero-file guard at line 187: a tree whose only pass-2 files are all under a home reports a positive clean count having read nothing, so the `nothing to scan` branch is unreachable in that case. The repo's own suite encodes the bug rather than catching it: test_service_under_records_is_quiet (test_vocabulary_wall.py:369-378) builds exactly such a root and assert_both_passes_clean (line 242) demands `clean — [1-9]… file` for pass 2, which can only be satisfied by counting the unread record.
- **reproduce:** mkdir -p /tmp/w/design /tmp/w/.dev/records
echo 'Observations are stored and reproduced.' > /tmp/w/design/spec.md
echo '{"note": "anything"}' > /tmp/w/.dev/records/r.json
python3 ops/devlane/workflow/checks/vocabulary_wall.py --root /tmp/w
# pass 2 -> 'clean — 1 file(s) scanned, 2 compose term(s)'; zero files were read
# repo counts: find .dev .github .claude .serena -type f \( -name '*.md' -o -name '*.py' -o -name '*.json' -o -name '*.yaml' -o -name '*.yml' -o -name '*.toml' -o -name '*.txt' -o -name '*.cue' -o -name '*.rst' -o -name '*.adoc' \) | wc -l  -> 647
# find .dev/records ops/docs/scratch .dev/handoffs .dev/infra -type f \( same suffixes \) | wc -l  -> 68
- **against:** the wall's own stated principle, vocabulary_wall.py:151-159; plan §4 gate `wall-tree` ("both passes report clean — N file(s) with N >= 1 each")

### 3. severity: high | where: ops/devlane/workflow/contracts/extract/vocab.py:130-136, ops/devlane/workflow/contracts/vet.py:643-646
- **id:** U1-R3
- **verdict:** CONFIRMED
- **category:** scope-deviation
- **summary:** Both files are on the plan's explicit "Not touched" list (plan §3, last paragraph), and plan §3 says obs is regenerated "(no extractor change)". Both were changed, and both changes exist only to make U1's own assertions come out true. No decision covers either; the ratification has no row for them.
- **detail:** extract/vocab.py now post-processes its own rendered JSON with two re.sub calls that rewrite the compose term to a \u0073 escape, so the generated observation does not trip the rule the same commit introduces. Consequence: obs/vocab.json is no longer the plain output of json.dumps — any reformat (jq, a normaliser, a hand edit, or a caller that uses extract() directly instead of main()) re-introduces the bare spelling and pass 2 then fires on the repo's own contract observation. The escaping is not pinned anywhere near the extractor; the only thing that would catch its loss is test_pass2_surfaces_outside_homes_do_not_carry_the_compose_term, in a different file. vet.py's added loop logs every fault matched_line containing "vocab." for every contract, not just vocab.4 — its purpose is visible at record line 175 ("Verified CUE initially reported only the generic required capability field"): the refusal name had to be made to appear in vet's stdout for test_vet_py_draws_capability_absent_on_vocab_4 to pass.
- **reproduce:** sed -n '136,139p' ops/docs/scratch/agentscient-u1-plan.md    # 'Not touched: ... extract/vocab.py, vet.py'
git diff af3ff01 938d5c7 -- ops/devlane/workflow/contracts/extract/vocab.py ops/devlane/workflow/contracts/vet.py
python3 -c "import json;p='ops/devlane/workflow/contracts/obs/vocab.json';d=json.load(open(p));open(p,'w').write(json.dumps(d,sort_keys=True,indent=2))"
python3 ops/devlane/workflow/checks/vocabulary_wall.py   # pass 2 now fires on obs/vocab.json
- **against:** plan §3 "Not touched"; plan §3 obs row "(no extractor change)"; ratification (no row)

### 4. severity: medium | where: ops/devlane/workflow/checks/vocabulary_wall.py:58-64 (SERVICE_HOMES) vs :48 (ALLOWED_PREFIXES)
- **id:** U1-R4
- **verdict:** CONFIRMED
- **category:** docker-lane-collision
- **summary:** `.github/` is a pass-2 surface and not a home, so a CI job that declares container services is refused — and `services:` there is schema syntax, not prose that can be reworded.
- **detail:** This is the concrete answer to 'what will the docker lane legitimately need'. The owner's stated next work is "Gitea + act_runner in docker" (.dev/handoffs/2026-08-28T2328Z-fable-prs-resolved-launcher-fixes.md:117-121), and both GitHub Actions and Gitea Actions spell job containers as a top-level `services:` key. The same applies to systemd unit names: the boundary class is [\w-], and `.` is outside it, so `dispatch-runner.service` named from any ops/devlane/**.py or .dev/scripts/**.yml fires; .dev/handoffs/ is the only systemd home and it holds prose, not the launcher. The wall's carve-out set was measured at bc5d2c4, before any of the docker work exists; the ratification's own note (row 6) flags that env/docker-lane PR #82 brings a different .dev/infra/ layout to reconcile, but nothing was reserved for .github/ or for the launcher surfaces.
- **reproduce:** printf 'jobs:\n  t:\n    runs-on: self-hosted\n    services:\n      db:\n        image: postgres\n' > .github/workflows/probe.yml
python3 ops/devlane/workflow/checks/vocabulary_wall.py; echo $?   # 1, vocab.service-outside-infra on .github/workflows/probe.yml:4
rm .github/workflows/probe.yml
# systemd variant:
mkdir -p /tmp/s/design /tmp/s/.dev/app && echo x > /tmp/s/design/spec.md
printf 'UNIT = "dispatch-runner.service"\n' > /tmp/s/ops/devlane/launch.py
python3 ops/devlane/workflow/checks/vocabulary_wall.py --root /tmp/s; echo $?   # 1
- **against:** plan §2 carve-out table; D-U1-homes; ratification row 6 note

### 5. severity: medium | where: ops/devlane/workflow/checks/vocabulary_wall.py:68
- **id:** U1-R5
- **verdict:** CONFIRMED
- **category:** wall-bypass
- **summary:** Hyphenated compose service names slip past pass 2. The boundary class is [\w-], so `db-service`, `web-service`, `micro-service` are not hits — and hyphenated names are the compose convention.
- **detail:** patterns_for compiles (?<![\w-])TERM(?![\w-]). The hyphen in that class is load-bearing for the wall's own self-cleanliness: the refusal string at line 179, `vocab.service-outside-infra`, survives pass 2 only because a hyphen follows it (same for the fixture directory names service-in-app / service-in-json quoted at test_vocabulary_wall.py:309,319). So this cannot simply be widened — but as it stands the rule the unit exists to enforce does not cover the most common spelling of the thing it is walling. The skeptic list (plan §5.2) asked whether `serviced` false-fires; the opposite direction was not asked and is not tested.
- **reproduce:** mkdir -p /tmp/h/design /tmp/h/.dev/app
echo 'Observations are stored and reproduced.' > /tmp/h/design/spec.md
printf 'db-service:\n  image: postgres\nweb-service:\n  image: nginx\n' > /tmp/h/ops/devlane/compose.yaml
python3 ops/devlane/workflow/checks/vocabulary_wall.py --root /tmp/h; echo $?   # 0, both passes 'clean'
- **against:** plan §2 ("SERVICE_TERMS, word-boundary, case-insensitive"); D-U1-homes intent

### 6. severity: medium | where: ops/devlane/workflow/checks/vocabulary_wall.py:166-181
- **id:** U1-R6
- **verdict:** CONFIRMED
- **category:** wall-bypass
- **summary:** Pass 2 reads file contents only, never path components, and compound identifiers do not match. `class ServiceRegistry`, `service_container = ...`, and a file named `services.yaml` all pass — yet `services.yaml` is one of the two things D-U1-code-suffixes cites as the reason to scan .py/.json at all.
- **detail:** D-U1-code-suffixes (plan §6) premises: "the object being guarded is a code/manifest word (`class Service`, `services.yaml`, a manifest key)". Of the three, only the bare `class Service` form is caught — which is the one form the fixture uses (fixtures/vocab/service-in-app/ops/devlane/x/x.py:1). Real Symfony-shaped code names things ServiceRegistry / ServiceContainer / service_locator, and the trailing/leading word char blocks every one. A file literally named ops/devlane/services.yaml is invisible because service_files yields paths but only searches text lines.
- **reproduce:** mkdir -p /tmp/c/design /tmp/c/.dev/app && echo 'Observations are stored and reproduced.' > /tmp/c/design/spec.md
printf 'class ServiceRegistry:\n    pass\n\nservice_container = {}\n' > /tmp/c/ops/devlane/x.py
printf 'db:\n  image: postgres\n' > /tmp/c/ops/devlane/services.yaml
python3 ops/devlane/workflow/checks/vocabulary_wall.py --root /tmp/c; echo $?   # 0
- **against:** D-U1-code-suffixes premises; ratification row 4

### 7. severity: medium | where: ops/devlane/workflow/checks/vocabulary_wall.py:55-56
- **id:** U1-R7
- **verdict:** CONFIRMED
- **category:** coverage-gap
- **summary:** `.sh` is a pass-2 surface with an unscanned suffix. 15 shell scripts under ops/devlane/ — the launchers and hooks — are exactly where `docker compose up <service>` and `systemctl --user start x.service` will land, and pass 2 never opens them.
- **detail:** CODE_SUFFIXES is (.py, .json); TEXT_SUFFIXES has no .sh, and no extensionless files (Dockerfile, Makefile) or .env. The lane's dispatch levers are shell: ops/devlane/dispatch/levers/{grok-dispatch.sh,apply-push.sh,selftest.sh,codex/codex-dispatch.sh,claude/fable-dispatch.sh,claude/selftest.sh} plus 9 hooks under ops/devlane/hooks/. The reasoning that justified adding .py and .json applies verbatim to .sh, and the docker lane is a shell-and-Dockerfile lane.
- **reproduce:** find .dev .github -type f -name '*.sh' | wc -l   # 15
mkdir -p /tmp/sh/design /tmp/sh/.dev/app && echo x > /tmp/sh/design/spec.md
printf '#!/bin/sh\ndocker compose up service\n' > /tmp/sh/ops/devlane/run.sh
python3 ops/devlane/workflow/checks/vocabulary_wall.py --root /tmp/sh; echo $?   # 0
- **against:** D-U1-code-suffixes rationale

### 8. severity: medium | where: ops/devlane/workflow/tests/test_vocabulary_wall.py:518-538 vs ops/docs/scratch/agentscient-u1-ratification.md:7
- **id:** U1-R8
- **verdict:** CONFIRMED
- **category:** decision-vs-code
- **summary:** The passes do NOT partition the tree, and the implementation now pins the gap as intended behaviour without the ratified decision being amended.
- **detail:** D-U1-two-passes (plan §6) and ratification row 1 both state the passes "partition the tree"; plan §2 spells it out — "so the two passes partition the tree and nothing is scanned by neither". What is true is that the two *surface* sets partition; the *suffix* sets do not. Pass 1 reads only TEXT_SUFFIXES, pass 2 only the dev-lane surfaces, so any .py or .json in the design tree is read by neither pass — a design-tree .py may say `work order`, `capability` or the compose word freely. test_a_py_in_the_design_tree_is_scanned_by_neither_pass encodes this as correct, which is honest of the test but leaves the standing decision text false on the record the discharge (§9) will copy into DECISIONS.md.
- **reproduce:** python3 -m unittest -v -s ops/devlane/workflow/tests discover -p 'test_vocabulary_wall.py' 2>&1 | grep neither   # green
sed -n '7p' ops/docs/scratch/agentscient-u1-ratification.md
sed -n '82,86p' ops/docs/scratch/agentscient-u1-plan.md
- **against:** D-U1-two-passes; ratification row 1; plan §2

### 9. severity: medium | where: AGENTS.md:47-50, .dev/ONBOARDING.md:44-45, ops/devlane/workflow/checks/vocabulary_wall.py:21-24
- **id:** U1-R9
- **verdict:** CONFIRMED
- **category:** unstatable-rule
- **summary:** The rule cannot be stated on the surface that must state it. Plan §3 required AGENTS.md to say "`service` is compose's word"; because AGENTS.md is a pass-2 surface and not a home, it says "Compose's container term" instead — and the agreement test therefore cannot check that the sentence is about the right term.
- **detail:** test_guide.test_agents_md_names_the_service_homes selects the paragraph by the presence of the words "compose" and "capability" and then compares only backticked dot-prefixed tokens against SERVICE_HOMES. Nothing ties the paragraph to the walled term. Mutating the sentence to name a different compose concept leaves the whole suite green. The same euphemism runs through ONBOARDING.md and the wall's own docstring; only .dev/infra/README.md:4 — a home — can print the word. A reader of AGENTS.md cannot learn which term is reserved.
- **reproduce:** sed -i "s/Compose's container term/Compose's network term/" AGENTS.md
python3 -m unittest discover -s ops/devlane/workflow/tests -p 'test_guide.py'   # still 9/9 green
git checkout AGENTS.md
- **against:** plan §3 row AGENTS.md ("one added sentence: `service` is compose's word")

### 10. severity: medium | where: ops/devlane/workflow/contracts/cue/vocab.cue:124,129
- **id:** U1-R10
- **verdict:** CONFIRMED
- **category:** contract-shape
- **summary:** VOC-S13 adds a visible (non-hidden) required field `"vocab.capability-absent"` to #VocabFacts. Every other row uses only a hidden `_has_*`. The plan authorised `_has_capability!: true`, "same comprehension shape as S01-S12".
- **detail:** S01-S12 use underscore-prefixed hidden fields, invisible to cue export and absent from the data. `"vocab.capability-absent"` has no underscore, so it becomes part of the exported value of facts for every vocab observation — a schema-injected data field that exists in no observation file. Its name is also inverted: it is set to true exactly when capability is PRESENT, and its absence is what produces the error text. It exists purely to get the refusal name into cue's stderr (record line 175 records that cue "initially reported only the generic required capability field"). A refusal name should be produced by the vetting layer, not smuggled in as a data field of the observed facts.
- **reproduce:** cue export -d '#Vocab' ops/devlane/workflow/contracts/cue/vocab.cue ops/devlane/workflow/contracts/obs/vocab.json | grep 'capability-absent'
# field is present in the export and absent from obs/vocab.json:
grep -c 'capability-absent' ops/devlane/workflow/contracts/obs/vocab.json   # 0
sed -n '124p;129p' ops/devlane/workflow/contracts/cue/vocab.cue
- **against:** plan §3 row vocab.cue; ratification row 5 ("one row per term, a `_has_capability!` raw check")

### 11. severity: low | where: ops/devlane/workflow/checks/vocabulary_wall.py:4-11
- **id:** U1-R11
- **verdict:** CONFIRMED
- **category:** stale-doc
- **summary:** The docstring — which §9 makes the design's permanent home and which extract/vocab.py treats as the contract's source — still lists 11 dev-lane concepts and omits `capability`, and still says exit 1 happens "when a reserved term appears there", not on either pass.
- **detail:** Plan §3 required the docstring to name both directions, every carve-out with its reason, and "exit 1 on either pass". The carve-outs and reasons are there (lines 21-24); the reserved-term enumeration was not updated when RESERVED grew, and the exit contract at line 11 still describes pass 1 only. test_wall_docstring_states_each_home_reason checks the homes but nothing checks the term list against RESERVED.
- **reproduce:** sed -n '1,12p' ops/devlane/workflow/checks/vocabulary_wall.py   # no 'capability' in the term list; line 11 exit contract
sed -n '36,41p' ops/devlane/workflow/checks/vocabulary_wall.py   # RESERVED includes capability, capabilities
- **against:** plan §3 row vocabulary_wall.py; plan §9

### 12. severity: low | where: ops/devlane/workflow/checks/vocabulary_wall.py:128,166
- **id:** U1-R12
- **verdict:** CONFIRMED
- **category:** cli-contract
- **summary:** Explicit PATH mode is now only half-honoured: `args.paths` is passed to design_files but service_files always walks the whole root, so `vocabulary_wall.py <file>` can exit 1 for a hit in a file the caller never named.
- **detail:** The documented usage line (:15) is `vocabulary_wall.py [--root DIR] [PATH ...]`, and before U1 the exit code answered a question about the named paths. It no longer does. The registered check runs with no paths so CI is unaffected, but anyone using the wall to pre-check one edited file gets an answer about the tree.
- **reproduce:** python3 ops/devlane/workflow/checks/vocabulary_wall.py CLAUDE.md
# pass 2 reports 651 files scanned, not 1; a compose-term hit anywhere on the dev lane would make this exit 1
- **against:** vocabulary_wall.py:15 usage; plan §2 (pass 2 "scans exactly the surfaces pass 1 exempts")

### 13. severity: low | where: ops/devlane/workflow/tests/test_vocabulary_wall.py:278-284
- **id:** U1-R13
- **verdict:** CONFIRMED
- **category:** test-strength
- **summary:** test_wall_docstring_states_each_home_reason checks only that each home string and each reason word appear somewhere in the docstring, not that they are paired. Swapping every reason between homes leaves it green.
- **detail:** D-U1-homes and ratification row 2 rest on 'each home pinned by a test with a reason, so the carve-out cannot grow silently'. The stated reason is the whole justification for each carve-out; the test proves only that five strings and five words coexist in one docstring.
- **reproduce:** # in vocabulary_wall.py, swap the parentheticals: `.dev/infra/` (research), `ops/docs/scratch/` (compose)
python3 -m unittest discover -s ops/devlane/workflow/tests -p 'test_vocabulary_wall.py'   # still 34/34
- **against:** D-U1-homes; ratification row 2

### 14. severity: low | where: ops/devlane/workflow/tests/test_guide.py (test_agents_md_names_the_service_homes, `named` comprehension)
- **id:** U1-R14
- **verdict:** CONFIRMED
- **category:** test-strength
- **summary:** The AGENTS.md-to-SERVICE_HOMES agreement is one-directional for any home that does not start with a dot: `named` filters on `tok.startswith(".")`, so AGENTS.md could name a non-dot home the wall does not allow and the test stays green.
- **detail:** Relevant now rather than hypothetically: ratification row 6 records that env/docker-lane (PR #82) brings its own .dev/infra/ layout to reconcile at merge, and the docker lane's own tree is referred to by a non-dot path in the handoffs. The wall-to-AGENTS.md direction is still covered (wall - named); only the AGENTS.md-to-wall direction has the hole.
- **reproduce:** # append a backticked non-dot path to the AGENTS.md compose paragraph, e.g. `env/docker-lane/`
python3 -m unittest discover -s ops/devlane/workflow/tests -p 'test_guide.py'   # still green; the token is filtered out before comparison
- **against:** plan §3 row test_guide.py ("both directions")

### 15. severity: low | where: ops/devlane/workflow/contracts/faults/vocab.4.meta.json:6,10,11
- **id:** U1-R15
- **verdict:** CONFIRMED
- **category:** metadata-accuracy
- **summary:** `violates` cites only the U1 plan §2; plan §3 required it to cite the parent §10 line as well. `sites: 2` and the note describe one literal plus joined, but the plural term is still present (see U1-R1), so the sidecar's own account of the fault does not match the fault.
- **reproduce:** cat ops/devlane/workflow/contracts/faults/vocab.4.meta.json
sed -n '127p' ops/docs/scratch/agentscient-u1-plan.md   # 'violates cites the parent §10 line and this plan §2'
grep -n '"capabilit' ops/devlane/workflow/contracts/faults/vocab.4.json
- **against:** plan §3 row faults/vocab.4
