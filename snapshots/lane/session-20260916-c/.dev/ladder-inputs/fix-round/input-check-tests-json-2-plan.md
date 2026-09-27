# Input: plan the item 31 batch's second slice from the security re-audit's findings

The item 31 batch (lane/check-tests-json: the skeptic's report is its JSON envelope, not a file; the driver writes a findings file for tests-fix) had its one fix round and its security re-audit returned changes again: the findings below, verbatim. By D-LADDER-1 the batch gets no second fix round; the unresolved findings are this slice's scope and it runs the whole ladder on this branch under the driver: tests (Grok) → skeptic → implement (Codex) per S bucket → audits once → one fix round → security re-audit → draft PR.

## Rules the plan must follow (owner, 2026-09-04)

- Buckets: S = 1–3 files, one implement run under 10 minutes; M = two named S buckets (run A, run B), each landed and green alone; L = split. Name the files of every bucket. Every bucket names the tests by file and why each is red at this ref, and the named implement command, which is those test files and never `suites.sh` or the whole suite.
- Walk the first run of every bucket against the environment: the worker's isolated HOME, no network, a read-only .git for Codex, the job prompt as in ops/devlane/task/jobs.json at this ref, the self-hosted runner's workspace. Every assumption is measured at write time or made a refusal the run will hit; an assumption that is neither is a finding against the plan. Write the walkthrough under a heading `## First-run walkthrough` per bucket, with lines `- assumption: … — measured: …` or `- assumption: … — refusal: …`.
- Never stub, never substitute a dependency, never bypass a validation to get green (owner: "when i hear stubs because of fuckup - i want to scream"). Finding 2 below is exactly that class and its removal is in scope; a test must pin that the bypass is gone.
- The symfony fixture's ignored vendor tree (finding 3): the fix is a refusal, class `toolchain`, when the trial has no vendor, stated expected–found–needed; installing from the host composer cache is the toolchain batch's work (a separate, planned slice), not this one's. Do not copy ignored files; do not install.
- Read-only probes (finding 1): docs/probes.md is the law (an allowlisted read set, identity stripped, read-only enforced not intended). Say how the allowlist is declared as data and how a manifest probe outside it refuses.
- Objects outside the job (finding 4): the job directory is the only place a dispatch writes (ops/devlane/dispatch/CONTRACT.md); name where the index copy and objects go instead and the test that pins no path under /tmp is written.
- Edges and guarantees per bucket from docs/verified-couplings.md; which slice deserves its own PR; value order; a calibration row per bucket (declared files, tests, lines, minutes).
- Machine lines in the driver's grammar at the end: `slice<TAB>name<TAB>S|M` and `bucket<TAB>name<TAB>S<TAB>files`; an M slice has exactly two named S buckets.

- The symfony rule above does not apply here; the rules on stubs, bypasses and walkthroughs do. The tests must pin the refusal, not the absence (finding 4 below is a test that passes on silence).

## Findings, verbatim — record 20260904T140242Z-review-codex-69d0fb, tree 4a6f097: verdict changes, counts {"p1": 2, "p2": 2, "p3": 1, "opinions": 0}

### 1. p1

```json
{
 "severity": "p1",
 "where": "ops/devlane/task/jobs.json:72; ops/conductor/tools/ladder.py:799-805,1419-1423",
 "claim": "Declared: jobs.json says \u201cverdict is changes when any finding exists and approve otherwise.\u201d Practiced: validation rejects only `verdict == \"approve\" and bool(findings)`. A schema-valid `changes` envelope with no findings is accepted and dispatches tests-fix with an empty specification. This is a new incomplete-validation regression.",
 "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/conductor/tools:ops/devlane/dispatch python3 -c 'import ladder,launch; p=ladder.Pending(\"check-tests\",\"id\",None,\"m\",\"e\",\"base\",0.0); env={\"job\":\"check-tests\",\"status\":\"ok\",\"verdict\":\"changes\",\"counts\":{\"p1\":0,\"p2\":0,\"p3\":0,\"opinions\":0},\"findings\":[],\"artifacts\":{},\"spend\":{\"harness\":\"codex\",\"total\":0,\"out\":0,\"runs\":0},\"stamp\":{\"ref\":\"deadbeef\",\"started\":None,\"ended\":None},\"note\":None}; assert launch._schema_valid(env); ladder.Driver.validate_check_tests(p,env); print(\"accepted changes with no findings\")'"
}
```

### 2. p1

```json
{
 "severity": "p1",
 "where": "ops/conductor/ladder-lever.md:99-111; ops/conductor/tools/ladder.py:997-1007",
 "claim": "Declared: the ladder record names a \u201cdriver-written check-tests findings file.\u201d Practiced: `findings_payload.write_text(...)` follows a pre-existing symlink, after which `findings_file.symlink_to(...)` deliberately creates another symlink. A write-stage worker can plant the predictable payload symlink and redirect the driver's later write outside the worktree. The earlier symlink-write finding is not fixed; its target merely moved.",
 "reproduce": "PYTHONPATH=ops/conductor/tools python3 -c 'import tempfile; from pathlib import Path; from types import SimpleNamespace as N; import ladder; td=tempfile.TemporaryDirectory(); root=Path(td.name); wt=root/\"wt\"; wt.mkdir(); outside=root/\"outside\"; outside.write_text(\"HOST\"); d=object.__new__(ladder.Driver); d.worktree=wt; d.inputs_dir=wt/\"inputs\"; d.inputs_dir.mkdir(); (d.inputs_dir/\"check-tests-findings.payload.json\").symlink_to(outside); d.findings=wt/\"findings.py\"; d.stage_by_name={\"check-tests\":{}}; d.commit=lambda *a:None; ladder.run=lambda *a,**k:N(returncode=0,stdout=\"\",stderr=\"\"); p=ladder.Pending(\"check-tests\",\"id\",wt/\"r\",\"m\",\"e\",\"b\",0.0); d.ledger_result(p,{\"verdict\":\"changes\",\"counts\":{\"p1\":1,\"p2\":0,\"p3\":0,\"opinions\":0},\"findings\":[{\"severity\":\"p1\",\"where\":\"x\",\"claim\":\"y\",\"reproduce\":\"true\"}]}); assert outside.read_text() != \"HOST\"; print(outside.read_text())'"
}
```

### 3. p2

```json
{
 "severity": "p2",
 "where": "ops/devlane/task/tests/test_check_tests_json.py:44-68,121-226; ops/devlane/task/tests/test_jobs.py:41-63,269-332",
 "claim": "Declared: the tests say the read-role prompt \u201crejects any write path, not a blacklist.\u201d Practiced: the regex still lists selected write verbs and requires a slash, extension, or `{out}`. The extensionless relative path in `Create REVIEW in the repository` passes all 13 relevant tests. This is a new bypass of the fix tests.",
 "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/devlane/task/tests python3 -c 'import json,unittest; from pathlib import Path; import test_check_tests_json as a,test_jobs as b; jobs=json.loads(Path(\"ops/devlane/task/jobs.json\").read_text()); jobs[\"check-tests\"][\"prompt\"]=\"Create REVIEW in the repository. Return the JSON envelope on stdout and leave artifacts empty.\"; F=type(\"F\",(),{\"is_file\":lambda self:True,\"read_text\":lambda self,encoding=None:json.dumps(jobs)}); a.JOBS_PATH=b.JOBS_PATH=F(); s=unittest.TestSuite(); [s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(c)) for c in (a.CheckTestsPromptCarriesNoFilePath,a.ReadRolePromptRejectsAnyWritePath,b.CheckTestsReadRolePromptRejectsAnyWritePath)]; r=unittest.TextTestRunner(verbosity=0).run(s); print(\"wrong extensionless write prompt accepted\",r.wasSuccessful()); raise SystemExit(not r.wasSuccessful())'"
}
```

### 4. p2

```json
{
 "severity": "p2",
 "where": "ops/conductor/tests/test_ladder_lever.py:3367-3400",
 "claim": "Declared: the test class says malformed check-tests envelopes must be validated before routing. Practiced: `test_findings_none_does_not_move_to_tests_fix` asserts only that later stages and payload files are absent; it never requires a nonzero result or the `envelope` refusal. A driver that silently returns success passes this test. This is a new absence-only test.",
 "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/conductor/tests python3 -c 'import test_ladder_lever as t; n=\"test_findings_none_does_not_move_to_tests_fix\"; c=t.CheckTestsEnvelopeValidatedBeforeFindingsFile(n); c.patch_plant=lambda **kw:None; c.files_before_run=lambda:set(); c.run_ladder=lambda:object(); c.dispatch_names=lambda:[]; c.combined=lambda proc:\"silent success\"; c.findings_payload_files=lambda before:[]; getattr(c,n)(); print(\"absence-only test accepted a result with no returncode or refusal\")'"
}
```

### 5. p3

```json
{
 "severity": "p3",
 "where": "ops/devlane/task/CONTRACT.md:131-138; ops/devlane/task/jobs.json:55-72,90-95",
 "claim": "Declared: CONTRACT.md still says \u201call three read jobs name `{inputs}`.\u201d Practiced: plan's prompt names only `{ref}`, `{out}`, and `{scope}`; only check-tests and adjudicate name `{inputs}`. The prior adversarial documentation finding is not fixed.",
 "reproduce": "python3 -c 'import json,re; from pathlib import Path; jobs=json.loads(Path(\"ops/devlane/task/jobs.json\").read_text()); slots={n:re.findall(r\"\\{([A-Za-z_][A-Za-z0-9_]*)\\}\",jobs[n][\"prompt\"]) for n in (\"plan\",\"check-tests\",\"adjudicate\")}; print(slots); assert \"inputs\" not in slots[\"plan\"]; assert \"all three read\\njobs name `{inputs}`\" in Path(\"ops/devlane/task/CONTRACT.md\").read_text()'"
}
```

note: Prior findings at 4a6f097: security-1 fixed — declared jobs.json:72 “verdict is changes when any finding exists and approve otherwise”; practiced ladder.py:799-805 now rejects approve-with-findings. Security-2 not fixed — declared ladder-lever.md:99-111 “driver-written check-tests findings file”; practiced ladder.py:1045-1057 fixes record-path consumption, but ladder.py:1000-1005 retains a redirectable symlink write (finding 2). Security-3 fixed — declared CONTRACT.md:123 “no file” and jobs.json:72 “leave artifacts empty”; practiced test_check_tests_json.py:168-210 rejects the original REPORT.rst and reports/findings.json plants. Adversarial-1 fixed — declared jobs.json:72 “Return the JSON envelope on stdout and leave artifacts empty”; practiced test_check_tests_json.py:147-157 positively requires it. Adversarial-2 fixed — declared envelope.py:241-268 says a wrong container type refuses; practiced ladder.py:775-805 rejects findings=None, malformed findings, and disagreeing counts. Adversarial-3 fixed — declared ladder.py:359-384 requires recorded paths inside the worktree; practiced ladder.py:1045-1057 resolves and rejects /etc/passwd and ../ paths. Adversarial-4 not fixed — CONTRACT.md:133-135 still contradicts jobs.json:60. The 16 and 9 catalogue tests passed. Looked at argv/shell/SQL/template seams, credentials, path/ref custody, sandbox records, vendor-output validation, and supply-chain files. No direct changed production argv/shell/SQL injection, real credential, dependency/action change, or sandbox-record/argv mismatch was found; all nine added dispatch records matched their recorded sandbox flag. The full ladder suite and dynamic symlink reproduction could not run because the audit environment has no writable temporary directory; the symlink path was verified statically and its reproducer is supplied for a writable test environment. The session store was not read.

