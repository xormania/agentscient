# U2 adversarial review — Claude Opus 5 (bda7e2), exported verbatim from the envelope

VERDICT: CHANGES | STATIC pass (execution refused by the role's surface; labeled by the reviewer)

## [P1] U2-R1 — W0 rebind correctness
**W0 is half-landed: the root amendment and the U0 rebind are correct, but plans/U2.plan.json and plans/U2.plan.md were never written, so U2 has no sidecar at all.**

W0's acceptance is 'plan_vet.py vet exits 0 on all three sidecars'. Only two exist. The root U2 row is expanded correctly (agentscient.plan.json:59-70, ten deliverables), D-new-2 is flipped to superseded (line 38), F1's stale U1 row is corrected (line 55), and U0's rebind is exact — sha256sum of agentscient.plan.json is 5db2de97e6e2be1ceb001d01c8bb055ae870feb54be60fbbecdf8ee46c4fd75a and U0.plan.json parent.sha256 matches it byte for byte, with the same digest carried once in U0.plan.md. But no U2 child sidecar was authored, and nothing in the tree references one. Consequence: the seven ratified D-U2-* decisions live only in ops/docs/scratch/agentscient-u2-ratification.md, bound to nothing; plan.stale-parent, plan.deliverables-mismatch, plan.settled-dropped, plan.scope-drift and plan.leaf-open never execute against U2; the §8 gate plan-vet-u2 cannot run; and the root row sits at stage 'code' with no child projecting it. The unit gate 'all three sidecars plan vet green' is unmeetable as landed. 

Reproduce:
```
ls ops/capabilities/plans/   # only U0.plan.json, U0.plan.md
python3 ops/capabilities/checks/plan_vet.py vet ops/capabilities/plans/U2.plan.json   # no such file
grep -rn 'U2.plan.json' .dev/   # no hit anywhere, including .dev/records/
sha256sum ops/capabilities/agentscient.plan.json && grep -n 'sha256' ops/capabilities/plans/U0.plan.json   # rebind half is correct
```

## [P1] U2-R2 — whether every enumerated refusal is truly demonstrated
**The enumerated refusal maps #RegistryRefusals and #AnatomyRefusals are read by nothing. Coverage is asserted between two hand-maintained Python tables, so a refusal added to the CUE contract stays green everywhere.**

D-U2-undemonstrated's load-bearing sentence is 'the check list is the test manifest, structurally'. Structurally, it is not. grep shows #RegistryRefusals and #AnatomyRefusals appear only at their own definition sites (capabilities.cue:19, capability.cue:41) plus three test docstrings — no check parses them, no test vets against them. registry_vet.faults() iterates a hardcoded ROWS dict keyed by fixture number, and anatomy.faults() does the same; the §3.4(d) rule 'refuse any enumerated refusal no fault draws' is inverted into 'refuse if a fixture named in ROWS is missing'. The suite's coverage test (test_registry_faults.py:118-121, test_anatomy_faults.py:96-105) compares support.REGISTRY_CLAIMS / ANATOMY_CLAIMS — themselves hand tuples in support.py:300-329 — against test-local R_ROWS / A_ROWS. Three hand tables agreeing with each other is not the contract being enforced. Separately, the tests silently widen U2-A1 F3: the amendment says the carve-out from committed-file demonstration 'is exactly two names' and 'nothing else may join', while support.py:331-355 adds registry.fault-intact, registry.fault-mismatch, registry.undemonstrated, anatomy.fault-intact and anatomy.fault-mismatch as a second exempt category ('runner claims'). That reinterpretation may well be right — those five have no file subject — but it is a contract change made in a test helper comment, not a ruled amendment. 

Reproduce:
```
grep -rn 'RegistryRefusals\|AnatomyRefusals' ops/capabilities/   # definitions + docstrings only
# then, in a scratch copy: append to capabilities.cue #RegistryRefusals
#   "registry.orphan": {name: "registry.orphan", class: "rejection", remedy: "x"}
python3 ops/capabilities/checks/registry_vet.py faults   # exits 0; no registry.undemonstrated
python3 -m unittest discover -s ops/capabilities/tests -p 'test_registry*.py'   # green
```

## [P1] U2-R3 — anything a green suite hides
**The directory-closure pass reads manifest fields before cue vet has validated the manifest, so manifest defects are reported under anatomy.extra instead of anatomy.manifest; §5.2 step 2's raw-presence pass has no implementation and no enumerated name.**

vet() computes module_name = Path(manifest.get('module','')).name and consults manifest.get('tags',[]) at lines 111-113, builds `allowed`, refuses anatomy.extra at 115-123, and only then calls cue_check at 124. Both reads default silently. A capability.json missing 'module' yields module_name='' so the real module file falls outside `allowed` and draws anatomy.extra with actual ['goodcap.py']. A capability.json missing 'tags' drops 'migrations' from `allowed` and draws anatomy.extra with actual ['migrations']. Both are #Manifest violations and must draw anatomy.manifest. §5.2 step 2 specifies 'capability.json raw-presence + cue vet -c' — the registry check implements exactly that discipline (registry_vet.py:99-108, FIELDS loop, with U0's mini-app-lessons §12 cited for why it must precede CUE); anatomy implements no raw-presence pass at all, and #AnatomyRefusals carries no absent-key name to draw if it did. No fault fixture and no test covers the module/tags-absent case (A5/A6 plant only inside refusals rows), which is why the suite is green over it. 

Reproduce:
```
cp -r ops/capabilities/contracts/examples/anatomy/goodcap /tmp/g
python3 -c "import json,pathlib; p=pathlib.Path('/tmp/g/capability.json'); d=json.loads(p.read_text()); d.pop('module'); p.write_text(json.dumps(d))"
python3 ops/capabilities/checks/anatomy.py vet /tmp/g   # draws anatomy.extra, expected anatomy.manifest
# same with d.pop('tags') -> anatomy.extra, actual ['migrations']
```

## [P2] U2-R4 — anything a green suite hides
**anatomy.refusals-disagree is decided by scraping every lowercase dotted token out of CONTRACT.md and contract.cue, so an ordinary prose mention of the module filename fails the check, and the rule silently requires every refusal name to be prefixed by the capability id.**

names_in() is re.findall(r'[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+') over the whole file text — it cannot tell a refusal name from a filename, a package path, or a sentence-final abbreviation. The equality arm is `{n in md_names if n.startswith(id + '.')} == manifest_names`. Two consequences. (a) False positive: a CONTRACT.md that says 'implemented in `goodcap.py`' contributes goodcap.py to the id-prefixed set and the three sets are declared to disagree even though they agree perfectly. Real capability contracts will mention their own module. (b) Undocumented constraint: a capability whose refusals are not id-prefixed — nothing in #Refusal's regex, §3.1, §3.3 or U2-A1 F10 requires that — is refused no matter how exactly the three files agree, because the id-prefixed slice is empty while manifest_names is not. The oracle F10 asked for exists, but it answers a different question than the claim it was given a name for. goodcap passes only because its one refusal happens to be `goodcap.denied` and its CONTRACT.md happens to mention no other dotted token. 

Reproduce:
```
cp -r ops/capabilities/contracts/examples/anatomy/goodcap /tmp/g2
printf '\nImplemented in `goodcap.py`.\n' >> /tmp/g2/CONTRACT.md
python3 ops/capabilities/checks/anatomy.py vet /tmp/g2   # anatomy.refusals-disagree on a file that agrees
# (b): rename the refusal to store.full in all three files, keep id goodcap -> still refused
```

## [P2] U2-R5 — the digest sidecar's refuse-on-absence / anything a green suite hides
**refuse-on-absence is correct and demonstrated, but the digest is computed from the export file itself rather than from a cue export of the source, so registry.stale-export cannot detect a stale export — only a stale or absent sidecar.**

The absence half of U2-A1 F2 is right: sidecar missing -> actual 'ABSENT' -> registry.stale-export, and test_registry_faults.py:288 plants the absence and asserts the refusal with outcome rejection. No finding there. The currency half does not hold. digest(doc) hashes json.dumps(parsed_export, sort_keys, compact) — a canonicalisation of the committed export, not of `cue export` of capabilities.cue. Nothing in the tree derives capabilities.json from the CUE. So the check proves sidecar-agrees-with-file, a self-consistency property, while §3.2 claims 'the committed export is current' and §5.1 step 4 calls it 'currency'. Any hand-edited export whose sidecar is refreshed with the same one-liner passes with the CUE source untouched. V4's ratified consequence — 'the digest is pinned to the lane's cue 0.14.1 and a cue bump is a digest-changing event by policy' — is not a property of what is actually computed: this digest is cue-version-independent by construction. Either the digest must be taken over `cue export` output, or §3.2/§5.1/V4 must be amended to say what the sidecar actually pins. 

Reproduce:
```
python3 - <<'EOF'
import json,hashlib,pathlib
p=pathlib.Path('ops/capabilities/capabilities.json'); d=json.loads(p.read_text())
d['capabilities'].append({"id":"ghost","layer":0,"module":"ghost.py","iface":[{"name":"G","members":["g"]}],"deps":[],"tags":[],"stores":[],"serves":["ghost.res"]})
p.write_text(json.dumps(d))
raw=json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
pathlib.Path('ops/capabilities/capabilities.json.digest').write_text(hashlib.sha256(raw).hexdigest()+'\n')
EOF
python3 ops/capabilities/checks/registry_vet.py vet ops/capabilities/capabilities.json   # exits 0; capabilities.cue never consulted for currency
```

## [P2] U2-R6 — whether every enumerated refusal is truly demonstrated
**registry.fault-intact is structurally unfireable on the committed corpus: examples/registry.json is pretty-printed and every fault is a compact one-liner, so the byte compare passes on whitespace alone — and for R9 the runner never looks at the planted artifact at all.**

faults() proves the plant landed with `fault.read_bytes() == clean`, where clean is the six-line pretty-printed examples/registry.json. All eight committed registry.N.json files are single-line compact JSON, so the comparison is false for reasons that have nothing to do with the plant. A fixture reverted to semantically clean content but left compact would sail through fault-intact (it would then be caught by fault-mismatch, so nothing escapes the corpus outright — but the gate that exists to prove the plant landed proves nothing). R9 is the sharp case: its meta declares site ['digest'] and its planted artifact is registry.9.json.digest (64 zeros), while registry.9.json is semantically identical to the clean example; the runner compares only the .json and never reads the .digest sidecar, so R9's actual plant is unproven by the gate that runs in the lane. The unit suite compensates (test_registry_faults.py:324-341 special-cases the digest site), but the suite is not a registered check — see U2-R10. The anatomy corpus does not have this problem: its fixtures are byte copies of goodcap plus a plant, and snapshot() covers the whole directory. 

Reproduce:
```
head -c 120 ops/capabilities/contracts/examples/registry.json; echo; head -c 120 ops/capabilities/contracts/faults/registry.3.json   # pretty vs compact
cat ops/capabilities/contracts/faults/registry.9.json.digest   # the plant the runner never reads
diff <(python3 -c "import json;print(json.load(open('ops/capabilities/contracts/faults/registry.9.json')))") <(python3 -c "import json;print(json.load(open('ops/capabilities/contracts/examples/registry.json')))")   # identical documents
```

## [P2] U2-R7 — anything a green suite hides
**#Anatomy is dead contract — it is the declared interface of capability.cue in the root U2 deliverable row, but nothing vets anything against it; the directory closure is a hand-written Python set that already spells the entries differently.**

The root sidecar declares capability.cue's interface as {name: '#Anatomy', fields: [...'tests/','faults/'...]}. Every cue invocation in the tree — anatomy.cue_check, and the two cue-level tests at test_anatomy_faults.py:468 and 505 — passes -d '#Manifest'. #Anatomy is never a vet target. The closure it describes is re-stated as the literal `required` set at anatomy.py:83-90, which writes 'tests' and 'faults' without the trailing slashes #Anatomy uses and omits the migrations/ optionality that is instead re-derived at lines 113 and 125. Two spellings of one rule with no gate between them: an edit to #Anatomy changes no behaviour and fires no check, which is the same class of drift the plan's own §12 F1 flagged against the root U1 row. 

Reproduce:
```
grep -rn '#Anatomy' ops/capabilities/   # definition + one plan row + one test string, no vet target
grep -n "'-d'" -A2 ops/capabilities/checks/anatomy.py   # -d #Manifest only
```

## [P3] U2-R8 — the both-ways member check's ast reading
**The member check never confirms the resolved class is a Protocol, and reads only that class's own top-level body, so inherited members are invisible in both directions.**

classes is built from `tree.body` ClassDef nodes by name alone (line 154); nothing inspects bases. anatomy.iface-unresolved renders expected 'a Protocol class' but is satisfied by any class of the right name — replace `class Reader(Protocol):` with `class Reader:` in goodcap.py and vet still exits 0, so D-U2-iface-manifest's 'declaration ↔ Protocol source' is really 'declaration ↔ same-named class'. Members are collected only from direct children of that class body (FunctionDef / AsyncFunctionDef / AnnAssign-with-Name, lines 165-170), which matches the contract's stated surface ('method or annotated attribute') but not its stated scope: a Protocol that inherits from a base Protocol has its inherited members counted in neither direction — declaring one draws a false anatomy.member-missing, and a public inherited member escapes anatomy.member-undeclared. §12's accepted risk 2 covers only members 'built dynamically'; static inheritance is a different and more likely case, and U3's boot-time presence re-check closes the second half but not the false-positive half. The dunder/private carve-out at line 181 is correct and is tested (test_anatomy_vet.py:121). 

Reproduce:
```
cp -r ops/capabilities/contracts/examples/anatomy/goodcap /tmp/g3
sed -i 's/^class Reader(Protocol):/class Reader:/' /tmp/g3/goodcap.py
python3 ops/capabilities/checks/anatomy.py vet /tmp/g3   # exits 0; no anatomy.iface-unresolved
# inheritance: make Writer(Reader, Protocol) with read only on Reader, declare members ['read','write'] on Writer -> false anatomy.member-missing
```

## [P3] U2-R9 — anything a green suite hides
**Both checks crash with an unclassified traceback on parseable-but-non-object input instead of drawing a classified refusal.**

registry_vet.vet calls `set(doc)` at line 91 before any type guard; the guard that handles a non-dict is inside the refuse() arguments on line 96, which is only reached if set(doc) succeeded. A registry file containing `3` or `null` raises TypeError before that. anatomy.vet has the same shape: `manifest.get('module','')` at line 111 on a capability.json holding a JSON list raises AttributeError. Exit status is still non-zero, so no gate reports green, but the output is a Python traceback with no `refused:` line, no class and no remedy — precisely the 'generic error' the four-class taxonomy and #Refusal.remedy exist to eliminate, and precisely the case a finding-class refusal is for. No fault fixture or test plants a non-object document. 

Reproduce:
```
printf '3' > /tmp/r.json && python3 ops/capabilities/checks/registry_vet.py vet /tmp/r.json   # TypeError traceback, no refused: line
cp -r ops/capabilities/contracts/examples/anatomy/goodcap /tmp/g4 && printf '[]' > /tmp/g4/capability.json && python3 ops/capabilities/checks/anatomy.py vet /tmp/g4   # AttributeError traceback
```

## [P3] U2-R10 — anything a green suite hides (outside the listed aims; reported because it changes what 'green' means)
**Both registered CI rows are vacuous today: registry-vet runs against a 21-byte empty export, and anatomy runs with no path and takes the zero-scanned branch, so nothing in U2's corpus or suite is exercised on a PR.**

The two rows W6 asks for are present, ci:true, with the pinned argv, and ci-dev.yml:140 installs cue 0.14.1 in the shape D-U2-cue-in-ci specified — that part is done. What it buys is smaller than it looks. `registry-vet vet ops/capabilities/capabilities.json` vets `{"capabilities": []}` against its sidecar; every relational rule loops over an empty list. `anatomy vet` with no path scans ops/capabilities/capabilities/, which does not exist, so main() prints the honesty line and returns 0 unconditionally — goodcap is never vetted by any registered check. Neither `faults` runner, neither positive control, and none of the seven agentscient test modules is registered in gate-kinds/artifact.json, so the whole 19-fixture corpus and both §3.4(d) coverage gates run only by hand. §8 names eight unit gates; two reach CI and both are green over nothing. This is the same class as §12's F3/F4 (U0's plan-vet unregistered, the runner cue-free), now applying to U2's own gates — worth routing to the same desk rather than assuming CI covers the unit. 

Reproduce:
```
ls ops/capabilities/   # no capabilities/ directory
python3 ops/capabilities/checks/anatomy.py vet; echo $?   # honesty line, 0, nothing scanned
grep -n '"name"' ops/devlane/workflow/gate-kinds/artifact.json   # no registry-faults, anatomy-faults, or agentscient test row
```

