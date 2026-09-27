# grok third review 20260829T220023Z-review-grok-02d142 — U1 at b4d176a

verdict: changes  counts: {'p1': 0, 'p2': 3, 'p3': 0, 'opinions': 0}

## note
Gates at b4d176a: test_vocabulary_wall 34/34, test_guide 9/9, ruff check ops/devlane/workflow exit 0, wall pass 1 clean 1 design file / 21 terms, pass 2 clean 659 files / 2 terms. P1 original reproduce now hits (UserService, api-service, user_service=1, bare py/json service, yaml db-service). Finding 5 path stem services.yaml and service_container= now hit. Finding 3 (passes partition named surfaces not the tree; design/spec.md and design/tool.py stay quiet; .mcp.json neither; p1=1 p2=659 overlap=0) still reproduces; D-U1-two-passes standing covers leaving it. Codex's claim that the other leftover P2 conflicts with ratification is false: no row names extract/vocab.py or vet.py.

## findings
### 1. severity: p2 | where: ops/devlane/workflow/checks/vocabulary_wall.py §compound_service_patterns
- **claim:** Codex 30e41d claimed compound and hyphenated compose names now caught, and that ServiceRegistry fired. class ServiceRegistry and class ServiceContainer stay quiet: the CamelCase pattern [A-Z][A-Za-z0-9]*Service consumes the leading S of Service*, so only a prefix before Service (UserService) matches. Hyphenated names in .json also stay quiet because compounds attach only to .py/.yaml/.yml, against D-U1-code-suffixes scanning .json as a manifest word. UserService and yaml api-service do fire.
- **reproduce:** python3 -c "import tempfile,shutil,subprocess,sys; from pathlib import Path; W='ops/devlane/workflow/checks/vocabulary_wall.py'
def go(rel,text):
 t=Path(tempfile.mkdtemp()); (t/'design').mkdir(); (t/'design'/'spec.md').write_text('Observations are stored and reproduced.\n'); p=t/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); r=subprocess.run([sys.executable,W,'--root',str(t)],capture_output=True,text=True); print(rel, r.returncode, 'hit' if 'vocab.service-outside-infra' in r.stdout else 'quiet'); shutil.rmtree(t)
go('ops/devlane/x/x.py','class ServiceRegistry:\n    pass\n')
go('ops/devlane/x/x.py','class ServiceContainer:\n    pass\n')
go('ops/devlane/x/x.py','class UserService:\n    pass\n')
go('ops/devlane/x/c.json','{\"api-service\":1}\n')
go('ops/devlane/x.yaml','api-service:\n  image: x\n')"

### 2. severity: p2 | where: ops/devlane/workflow/contracts/obs/vocab.json:3
- **claim:** Grok-3 not closed and not covered by ratification. Array literals are \u0073ervice but facts.joined source still contains ruff.toml\nservice\nservices. The wall lookbehind fails because the previous source character is n, so pass 2 reports clean — 659 file(s) while the committed observation carries the compose term. json.dumps of the loaded obs reintroduces four line-hits. No ratification row names joined, obs, or this encoding.
- **reproduce:** python3 -c "from pathlib import Path; import json,re; t=Path('ops/devlane/workflow/contracts/obs/vocab.json').read_text(); i=t.find('ruff.toml'); print(t[i:i+70]); pat=re.compile(r'(?<![\\w-])services?(?![\\w-])', re.I); print('line-hits', [(n,ln[:70]) for n,ln in enumerate(t.splitlines(),1) if pat.search(ln)]); d=json.loads(t); plain=json.dumps(d,sort_keys=True,indent=2); print('reformat-hits', [n for n,ln in enumerate(plain.splitlines(),1) if pat.search(ln)]); print('joined_contains_service', 'service' in d['facts']['joined'])"; python3 ops/devlane/workflow/checks/vocabulary_wall.py | sed -n '/pass 2/,+2p'

### 3. severity: p2 | where: ops/devlane/workflow/contracts/extract/vocab.py:134 / vet.py:645
- **claim:** Opus-R3 not closed. Codex 30e41d left this as conflicting with ratified decisions; agentscient-u1-ratification.md has seven standing rows and none names extract/vocab.py or vet.py (D-U1-parent-binding's extract is plan extract). Both files remain edited against plan §3 Not touched. extract/vocab.py still re.sub \bservices? after json.dumps (and that \b is why joined is not escaped). vet.py still logs every matched_line containing vocab. so test_vet_py_draws_capability_absent_on_vocab_4 can pass.
- **reproduce:** sed -n '128,137p' ops/devlane/workflow/contracts/extract/vocab.py; sed -n '643,647p' ops/devlane/workflow/contracts/vet.py; sed -n '136,139p' ops/docs/scratch/agentscient-u1-plan.md; python3 -c "from pathlib import Path; t=Path('ops/docs/scratch/agentscient-u1-ratification.md').read_text(); print('vet.py' in t, 'extract/vocab.py' in t); print([ln.strip() for ln in t.splitlines() if ln.startswith('| D-U1')])"
