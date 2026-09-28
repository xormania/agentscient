# grok adversarial-review 20260829T211256Z-review-grok-daf4b6 — ref 938d5c7

verdict: changes  counts: {'p1': 1, 'p2': 3, 'p3': 0, 'opinions': 0}

## note
Wall and suites re-run at 938d5c7: pass 1 clean 1 design file / 21 terms, pass 2 clean 651 files / 2 terms, 34+9 tests OK. Five homes match D-U1-homes with reasons. Four English hits reworded (AGENTS.md:32 and ONBOARDING.md:164 goes into use; test_ci_shape.py:1306 runner host; test_promotion_round2.py:7 while naming) and pass-2 surfaces minus homes have zero remaining hits. JSON keys and bare py strings of service fire; hyphenated names and UserService do not. docker-lane-plan.md is not in this snapshot (UNREACHABLE).

## findings
### 1. severity: p1 | where: ops/devlane/workflow/checks/vocabulary_wall.py:68
- **claim:** Pass 2 compiles SERVICE_TERMS with (?<![\w-])term(?![\w-]), copied from pass 1, so hyphenated compose names (api-service, service-name) and Symfony-style UserService / user_service do not fire. Bare-token py strings and JSON keys of service do fire. Plan §2 said word-boundary; \b would still miss UserService but would catch api-service. Tests only plant class Service and serviced, so this hole is green. This is the owner's docker-vs-Symfony conflation.
- **reproduce:** python3 -c "import tempfile,shutil,subprocess,sys; from pathlib import Path; W='ops/devlane/workflow/checks/vocabulary_wall.py'
def go(rel,text):
 t=Path(tempfile.mkdtemp()); (t/'design').mkdir(); (t/'design'/'spec.md').write_text('Observations are stored and reproduced.\n'); p=t/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); r=subprocess.run([sys.executable,W,'--root',str(t)],capture_output=True,text=True); print(rel, r.returncode, 'hit' if 'vocab.service-outside-infra' in r.stdout else 'quiet'); shutil.rmtree(t)
go('ops/devlane/x/x.py','class UserService:\n    pass\n')
go('ops/devlane/x/x.py','n=\"api-service\"\n')
go('ops/devlane/x/x.py','user_service=1\n')
go('ops/devlane/x/x.py','x=\"service\"\n')
go('ops/devlane/x/c.json','{\"service\":1}\n')"

### 2. severity: p2 | where: ops/devlane/workflow/checks/vocabulary_wall.py:76
- **claim:** Pass 1 and pass 2 partition ALLOWED_PREFIXES union ALLOWED_FILES, not the tree. Measured at 938d5c7: overlap 0, pass1=1 (CLAUDE.md), pass2=651; design-tree .py/.json and root .mcp.json are scanned by neither; design/spec.md saying the service is injected is quiet. Parent U1 required service reserved outside .dev/infra/; plan §2 said nothing is scanned by neither. test_a_py_in_the_design_tree_is_scanned_by_neither_pass pins the hole.
- **reproduce:** python3 -c "
import tempfile,shutil,subprocess,sys,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('w','ops/devlane/workflow/checks/vocabulary_wall.py'); w=importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
root=Path('.').resolve(); p1={p.relative_to(root).as_posix() for p in w.design_files(root,[])}; p2={p.relative_to(root).as_posix() for p,_ in w.service_files(root)}
print('p1',len(p1),'p2',len(p2),'overlap',len(p1&p2))
W='ops/devlane/workflow/checks/vocabulary_wall.py'
t=Path(tempfile.mkdtemp()); (t/'design').mkdir(); (t/'design'/'spec.md').write_text('The service is injected.\n'); (t/'design'/'tool.py').write_text('class Service:\n    pass\n')
r=subprocess.run([sys.executable,W,'--root',str(t)],capture_output=True,text=True); print('rc',r.returncode); print(r.stdout); shutil.rmtree(t)
"

### 3. severity: p2 | where: ops/devlane/workflow/contracts/obs/vocab.json:3
- **claim:** obs/vocab.json is a pass-2 .json under .dev/ (not a home). Its facts.joined source contains \nservice\n; the wall regex does not match because the previous source character is n. extract/vocab.py:134 re.sub uses \b and misses the same encoding. Pretty JSON keys of service do fire (fixture service-in-json). The committed observation therefore carries the compose term while pass 2 reports clean on 651 files.
- **reproduce:** python3 -c "
from pathlib import Path
import re
t=Path('ops/devlane/workflow/contracts/obs/vocab.json').read_text()
i=t.find('service'); print('first', i, repr(t[i-8:i+16]))
pat=re.compile(r'(?<![\w-])services?(?![\w-])', re.I)
print('line-hits', [(n,ln[:80]) for n,ln in enumerate(t.splitlines(),1) if pat.search(ln)])
"; python3 ops/devlane/workflow/checks/vocabulary_wall.py | sed -n '/pass 2/,+2p'

### 4. severity: p2 | where: ops/devlane/workflow/checks/vocabulary_wall.py:48
- **claim:** SERVICE_HOMES is the ratified five (.dev/infra/, ops/docs/scratch/, .dev/handoffs/, .dev/records/, .git/) with docstring reasons compose/research/systemd/evidence/not a tree surface. .github/ is a pass-2 surface and not a home, so a workflow services: key is vocab.service-outside-infra. Compose YAML under .dev/infra/ is quiet. Docker-lane (env/docker-lane, PR #82) compose files in that home are fine; GitHub Actions service-containers, .dev/app or .dev/guide prose, and any services.yaml outside infra will be refused. Dockerfiles, *.service units, and .sh are not scanned (suffix). .dev/infra/README.md:5 Nothing is deployed from this directory yet will not survive that merge.
- **reproduce:** python3 -c "
import tempfile,shutil,subprocess,sys
from pathlib import Path
W='ops/devlane/workflow/checks/vocabulary_wall.py'
def go(rel,text):
 t=Path(tempfile.mkdtemp()); (t/'design').mkdir(); (t/'design'/'spec.md').write_text('Observations are stored and reproduced.\n'); p=t/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); r=subprocess.run([sys.executable,W,'--root',str(t)],capture_output=True,text=True); print(rel, r.returncode, 'hit' if 'vocab.service-outside-infra' in r.stdout else 'quiet'); shutil.rmtree(t)
go('.github/workflows/ci.yml','jobs:\n  t:\n    services:\n      postgres:\n        image: postgres\n')
go('.dev/infra/compose.yaml','services:\n  web:\n    image: nginx\n')
go('ops/devlane/x/compose.yaml','services:\n  web:\n    image: nginx\n')
go('ops/devlane/x/Dockerfile','FROM service\n')
"; sed -n '1,5p' .dev/infra/README.md
