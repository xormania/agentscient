# Item 31 audit fix round — inputs, records verbatim

## Security audit envelope — record 20260904T170030Z-review-codex-10274e

```json
{
  "job": "security-audit",
  "status": "ok",
  "verdict": "changes",
  "counts": {
    "p1": 1,
    "p2": 2,
    "p3": 0,
    "opinions": 0
  },
  "findings": [
    {
      "severity": "p1",
      "where": ".dev/ladder-inputs/PLAN-check-tests-json-2.md:83-86; ops/conductor/tools/ladder.py:184-191,1012-1019",
      "claim": "Declared: the plan says the payload \u201cmust be a regular file inside `inputs_dir`\u201d and \u201chost target unchanged; no follow.\u201d Practiced: `replace_text` calls `tempfile.mkstemp(..., dir=path.parent)` and `os.replace(temporary_path, path)` without verifying that the parent directory is not a symlink. A tests-stage worker can replace the predictable, initially absent ladder input directory with a symlink, causing both the payload and published link to be created outside the worktree.",
      "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/conductor/tools python3 -c 'import tempfile; from pathlib import Path; from types import SimpleNamespace as N; import ladder; td=tempfile.TemporaryDirectory(); root=Path(td.name); wt=root/\"wt\"; wt.mkdir(); outside=root/\"outside\"; outside.mkdir(); inputs=wt/\"inputs\"; inputs.symlink_to(outside,target_is_directory=True); d=object.__new__(ladder.Driver); d.worktree=wt; d.inputs_dir=inputs; d.findings=wt/\"findings.py\"; d.stage_by_name={\"check-tests\":{}}; d.commit=lambda *a:None; ladder.run=lambda *a,**k:N(returncode=0,stdout=\"\",stderr=\"\"); p=ladder.Pending(\"check-tests\",\"id\",wt/\"r\",\"m\",\"e\",\"b\",0.0); env={\"verdict\":\"changes\",\"counts\":{\"p1\":1,\"p2\":0,\"p3\":0,\"opinions\":0},\"findings\":[{\"severity\":\"p1\",\"where\":\"x\",\"claim\":\"y\",\"reproduce\":\"true\"}]}; d.ledger_result(p,env); escaped=outside/\"check-tests-findings.payload.json\"; assert escaped.is_file(); print(escaped)'"
    },
    {
      "severity": "p2",
      "where": ".dev/ladder-inputs/PLAN-check-tests-json-2.md:89-92; ops/devlane/task/write_path.py:7-15; ops/devlane/task/tests/test_check_tests_json.py:131-137",
      "claim": "Declared: the edge requires \u201ca write verb plus a path-shaped token,\u201d while the test says it \u201crejects any write path, not a blacklist.\u201d Practiced: `_WRITE_PATH` recognizes only `create|persist|save|store|write`. The read-role prompt `Generate REVIEW in the repository` passes all 21 relevant guard tests, so the new recognizer remains a verb blacklist.",
      "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/devlane/task/tests python3 -c 'import json,unittest; from pathlib import Path; import test_check_tests_json as a,test_jobs as b; jobs=json.loads(Path(\"ops/devlane/task/jobs.json\").read_text()); jobs[\"check-tests\"][\"prompt\"]=\"Generate REVIEW in the repository. Return the JSON envelope on stdout and leave artifacts empty.\"; F=type(\"F\",(),{\"is_file\":lambda self:True,\"read_text\":lambda self,encoding=None:json.dumps(jobs)}); a.JOBS_PATH=b.JOBS_PATH=F(); s=unittest.TestSuite(); [s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(c)) for c in (a.CheckTestsPromptCarriesNoFilePath,a.ReadRolePromptRejectsAnyWritePath,b.CheckTestsReadRolePromptRejectsAnyWritePath)]; r=unittest.TextTestRunner(verbosity=0).run(s); print(\"wrong generate-write prompt accepted\",r.wasSuccessful()); raise SystemExit(not r.wasSuccessful())'"
    },
    {
      "severity": "p2",
      "where": "ops/devlane/task/jobs.json:68-72; ops/conductor/tools/ladder.py:783-825,1052-1055",
      "claim": "Declared: check-tests has \u201cno file\u201d and must \u201cleave artifacts empty.\u201d Practiced: `validate_check_tests` validates only findings, counts, and verdict, accepting a schema-valid envelope whose artifacts name `/etc/passwd`; `inputs_for` then appends the complete check-tests record to the write-role tests-fix inputs. The no-file boundary therefore trusts an unchecked vendor artifact handle.",
      "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/conductor/tools:ops/devlane/dispatch python3 -c 'from pathlib import Path; import ladder,launch; p=ladder.Pending(\"check-tests\",\"id\",Path(\"r\"),\"m\",\"e\",\"base\",0.0); env={\"job\":\"check-tests\",\"status\":\"ok\",\"verdict\":\"changes\",\"counts\":{\"p1\":0,\"p2\":1,\"p3\":0,\"opinions\":0},\"findings\":[{\"severity\":\"p2\",\"where\":\"x:1\",\"claim\":\"Declared: d; Practiced: p\",\"reproduce\":\"true\"}],\"artifacts\":{\"report\":\"/etc/passwd\"},\"spend\":{},\"stamp\":{\"ref\":\"deadbeef\"},\"note\":None}; assert launch._schema_valid(env); ladder.Driver.validate_check_tests(p,env); src=Path(\"ops/conductor/tools/ladder.py\").read_text(); assert \"inputs.append(record_path)\" in src; print(\"accepted\",env[\"artifacts\"])'"
    }
  ],
  "artifacts": {},
  "spend": {
    "harness": "codex",
    "total": 3826087,
    "out": 24959,
    "runs": 1
  },
  "stamp": {
    "ref": "9be13730203c664f773e5dcd9b138ef8b3adadde",
    "started": null,
    "ended": null
  },
  "note": "Covered injection seams, credentials, path/ref custody, permissions, vendor-output validation, supply-chain changes, and all named edge cases. No direct argv/shell/SQL/template injection, real credential, ref escape, dependency/action change, sandbox-field/argv mismatch, other-job catalogue drift, empty-changes acceptance, stale slots claim, or remaining absence-only named test was found. The 21 and 16 task guard tests passed. Dynamic symlink and full conductor suites could not run because this audit sandbox has no writable temporary directory; the supplied symlink reproducer requires one. Live vendor containment was not re-probed. The session store was not read."
}
```

## Adversarial review envelope — record 20260904T170050Z-review-grok-41c1f5

```json
{
  "job": "adversarial-review",
  "status": "ok",
  "verdict": "changes",
  "counts": {
    "p1": 1,
    "p2": 3,
    "p3": 0,
    "opinions": 0
  },
  "findings": [
    {
      "severity": "p1",
      "where": ".dev/ladder-inputs/PLAN-check-tests-json-2.md:80-86; ops/conductor/tools/ladder.py:184-193,1011-1019,1062-1071",
      "claim": "Declared: the slice-2 plan says \"the driver may write the findings payload only as a regular file inside `inputs_dir` (`.dev/records/ladders/<id>/` in the worktree)\" and \"the ladder writes under that inputs dir, not through a symlink to the host\"; \"A pre-existing symlink is a planted fault, not a destination.\" Practiced: `replace_text` does `tempfile.mkstemp(..., dir=path.parent)` then `os.replace` (ladder.py:186,191), which follow a directory symlink at `inputs_dir`; `findings_file.parent.mkdir(exist_ok=True)` (1013) leaves that symlink in place; `inputs_for` then bounds with `candidate.is_relative_to(self.inputs_dir.resolve())` (1064), so the host directory counts as ladder inputs and tests-fix is given a path outside the worktree. The payload-file symlink plant is no longer followed; the target moved to the directory.",
      "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/conductor/tools python3 -c 'import os,tempfile; from pathlib import Path; from types import SimpleNamespace as N; import ladder; td=tempfile.TemporaryDirectory(); root=Path(td.name); wt=root/\"wt\"; wt.mkdir(); host=root/\"hostdir\"; host.mkdir(); inputs=wt/\"inputs\"; inputs.symlink_to(host); d=object.__new__(ladder.Driver); d.worktree=wt; d.inputs_dir=inputs; d.findings=wt/\"findings.py\"; d.stage_by_name={\"check-tests\":{}}; d.commit=lambda *a:None; d.plan=None; ladder.run=lambda *a,**k:N(returncode=0,stdout=\"\",stderr=\"\"); p=ladder.Pending(\"check-tests\",\"id\",wt/\"r\",\"m\",\"e\",\"b\",0.0); d.ledger_result(p,{\"verdict\":\"changes\",\"counts\":{\"p1\":1,\"p2\":0,\"p3\":0,\"opinions\":0},\"findings\":[{\"severity\":\"p1\",\"where\":\"x\",\"claim\":\"y\",\"reproduce\":\"true\"}]}); payload=host/\"check-tests-findings.payload.json\"; assert payload.is_file() and \"claim\" in payload.read_text(); d.row=lambda name: d.stage_by_name[\"check-tests\"] if name==\"check-tests\" else {}; out=d.inputs_for(\"tests-fix\",{\"check-tests\":\"rec\"},None); resolved=[Path(x).resolve() for x in out]; assert any(str(x).startswith(str(host.resolve())+os.sep) for x in resolved); print(\"directory symlink write landed on host and tests-fix received it\")'"
    },
    {
      "severity": "p2",
      "where": ".dev/ladder-inputs/PLAN-check-tests-json-2.md:91-92; ops/devlane/task/tests/test_check_tests_json.py:132-136,217-233; ops/devlane/task/tests/test_jobs.py:150-151,229-245; ops/devlane/task/write_path.py:7-15",
      "claim": "Declared: the plan says \"a write verb plus a path-shaped token. Path-shaped includes an extensionless relative name (`REVIEW`), not only slash, extension, or `{out}`\"; the tests say the read-role prompt \"rejects any write path, not a blacklist\" and \"path-shaped includes an extensionless relative name.\" Practiced: `_WRITE_PATH` still lists `create|persist|save|store|write` and treats an extensionless name as a path only with `(?=\\s+in\\s+(?:the\\s+)?repository\\b)`. `Create REVIEW on disk` and `Dump REVIEW in the repository` return None from `write_path_ask`. Planting `Create REVIEW on disk. Return the JSON envelope on stdout and leave artifacts empty.` as the live check-tests prompt leaves all 21 tests in CheckTestsPromptCarriesNoFilePath, ReadRolePromptRejectsAnyWritePath, and CheckTestsReadRolePromptRejectsAnyWritePath green. The named `Create REVIEW in the repository` plant is now red; the bypass class is not.",
      "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/devlane/task/tests python3 -c 'import json,unittest,sys; from pathlib import Path; import test_check_tests_json as a,test_jobs as b; sys.path.insert(0,\"ops/devlane/task\"); import write_path; jobs=json.loads(Path(\"ops/devlane/task/jobs.json\").read_text()); prompt=\"Create REVIEW on disk. Return the JSON envelope on stdout and leave artifacts empty.\"; assert write_path.write_path_ask(prompt) is None; assert write_path.write_path_ask(\"Dump REVIEW in the repository\") is None; jobs[\"check-tests\"][\"prompt\"]=prompt; F=type(\"F\",(),{\"is_file\":lambda self:True,\"read_text\":lambda self,encoding=None:json.dumps(jobs)}); a.JOBS_PATH=b.JOBS_PATH=F(); s=unittest.TestSuite(); [s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(c)) for c in (a.CheckTestsPromptCarriesNoFilePath,a.ReadRolePromptRejectsAnyWritePath,b.CheckTestsReadRolePromptRejectsAnyWritePath)]; r=unittest.TextTestRunner(verbosity=0).run(s); print(\"wrong extensionless write prompt accepted\", r.wasSuccessful()); raise SystemExit(not r.wasSuccessful())'"
    },
    {
      "severity": "p2",
      "where": ".dev/ladder-inputs/PLAN-check-tests-json-2.md:48-49; ops/conductor/tests/test_ladder_lever.py:3375-3382,3529-3617",
      "claim": "Declared: CheckTestsEnvelopeValidatedBeforeFindingsFile says \"Validate verdict, counts, and findings shape before writing\" and \"verdict=changes with an empty findings list is an envelope stop\"; the plan says pin the refusal, \"Do not leave the method as an absence-only test,\" and names `test_findings_none_does_not_move_to_tests_fix` as the instance. Practiced: that one method now calls `assert_stopped(..., reason=\"envelope\")`. `test_counts_that_disagree_with_findings_do_not_move_to_tests_fix` (3529-3559), `test_a_finding_missing_its_shape_does_not_move_to_tests_fix` (3561-3591), and `test_approve_with_findings_does_not_skip_to_implement` (3593-3617) still assert only that `tests-fix`/`code` and payload files are absent. A driver that silently returns success passes all three.",
      "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/conductor/tests python3 -c 'import test_ladder_lever as t; names=[\"test_counts_that_disagree_with_findings_do_not_move_to_tests_fix\",\"test_a_finding_missing_its_shape_does_not_move_to_tests_fix\",\"test_approve_with_findings_does_not_skip_to_implement\"];\ndef run(n):\n c=t.CheckTestsEnvelopeValidatedBeforeFindingsFile(n); c.patch_plant=lambda **kw:None; c.files_before_run=lambda:set(); c.run_ladder=lambda:object(); c.dispatch_names=lambda:[]; c.combined=lambda proc:\"silent success\"; c.findings_payload_files=lambda before:[]; c.plant_check_tests_findings=lambda **kw:[{\"severity\":\"p2\"}]; c.counts_from_findings=lambda planted:{\"p2\":1}; getattr(c,n)(); print(n, \"absence-only test accepted a result with no returncode or refusal\")\nlist(map(run, names))'"
    },
    {
      "severity": "p2",
      "where": "ops/conductor/ladder-lever.md:88-91; .dev/ladder-inputs/PLAN-check-tests-json-2.md:86; ops/conductor/tools/ladder.py:1019,1117-1122,1688-1692",
      "claim": "Declared: ladder-lever.md says \"If its stopped dispatch record is now closed with an accepted envelope, resume consumes and lands it without relaunching\"; the plan says \"Replacing the symlink with a regular file inside inputs, or stopping before the write, are both refusals of the bypass.\" Practiced: after a symlink-safe payload replace, the published name is created with `findings_file.symlink_to(findings_payload.name)` (ladder.py:1019), which neither replaces a pre-existing path nor raises `Stopped`. A second `ledger_result` \u2014 resume of a closed check-tests envelope whose row outcome is not `ok` (`finish(..., already_closed=...)` at 1117-1122) \u2014 raises `FileExistsError`. `main` catches only `Refused` and `Stopped` (1688-1692), so the ladder crashes off the wire instead of `stopped stage=check-tests reason=findings-file`.",
      "reproduce": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=ops/conductor/tools python3 -c 'import tempfile; from pathlib import Path; from types import SimpleNamespace as N; import ladder; td=tempfile.TemporaryDirectory(); wt=Path(td.name)/\"wt\"; wt.mkdir(); d=object.__new__(ladder.Driver); d.worktree=wt; d.inputs_dir=wt/\"inputs\"; d.inputs_dir.mkdir(); d.findings=wt/\"findings.py\"; d.stage_by_name={\"check-tests\":{}}; d.commit=lambda *a:None; ladder.run=lambda *a,**k:N(returncode=0,stdout=\"\",stderr=\"\"); p=ladder.Pending(\"check-tests\",\"id\",wt/\"r\",\"m\",\"e\",\"b\",0.0); env={\"verdict\":\"changes\",\"counts\":{\"p1\":1,\"p2\":0,\"p3\":0,\"opinions\":0},\"findings\":[{\"severity\":\"p1\",\"where\":\"x\",\"claim\":\"y\",\"reproduce\":\"true\"}]}; d.ledger_result(p, env); exec(\"try:\\\\n d.ledger_result(p, env)\\\\n print(\\\"second publish ok\\\")\\\\nexcept FileExistsError:\\\\n print(\\\"second publish FileExistsError not Stopped\\\")\")'"
    }
  ],
  "artifacts": {},
  "spend": {
    "harness": "grok",
    "total": 2165337,
    "out": 50094,
    "runs": 1
  },
  "stamp": {
    "ref": "9be13730203c664f773e5dcd9b138ef8b3adadde",
    "started": "2026-09-04T17:00:50Z",
    "ended": "2026-09-04T17:13:00Z"
  },
  "note": "Looked and found clean at 9be13730203c664f773e5dcd9b138ef8b3adadde vs 340badebd2deb9a5209689f414c5fdf70e60cc2c: schema-valid verdict=changes with findings=[] is refused by Driver.validate_check_tests as reason=envelope (launch._schema_valid still True, as the plan left envelope.py out of scope); a payload-file symlink (absolute or relative ../../) is replaced, host body stays HOST; consume-time absolute, ../, and file-symlink plants are Stopped reason=findings-file; no catalogue job other than check-tests differs from the merge-base; CONTRACT.md:133-135 matches practiced plan/check-tests/adjudicate slots and no longer claims all three read jobs name {inputs}; the live check-tests prompt is not a write_path_ask hit. Full ladder fixture suite not run; hunts used unit reproduces against this tree."
}
```

## ruff check over the task tests directory at ebdca50 dispatch: record 20260904T170050Z-review-grok-41c1f5 (measured 17:19Z)

```
ops/devlane/task/tests/test_jobs.py:474:13: SIM300 [*] Yoda condition detected
ops/devlane/task/tests/test_jobs.py:480:13: SIM300 [*] Yoda condition detected
ops/devlane/task/tests/test_jobs.py:486:13: SIM300 [*] Yoda condition detected
Found 3 errors.
[*] 3 fixable with the `--fix` option.
```

## First-run walkthrough

First run of this unit = the tests half of the audit fix round (Grok, write, whole snapshot); the code half (Codex) follows after these tests land.

- assumption: the tree is the commit named in the ruff heading, on lane/check-tests-json, both slices landed — measured: `git log --oneline -1` this turn, quoted above.
- assumption: ruff reports exactly three SIM300 findings, all in one test file the ruff block names — measured: the ruff block above, this turn.
- assumption: the test command is the discover form, one `-s` directory and `-p` file per suite — measured: `ops/conductor/ladder-lever.md:50-53` this session; a package-form command failed with `No module named 'support'` this session.
- assumption: Grok's harness relocates `HOME` to the job home — measured: `ops/devlane/harness/isolation.py:118-127` (`also_env: ["HOME"]`) this session; that file is not in this batch's bucket.
- assumption: writable roots are the snapshot cwd, `/tmp`, and the job `out/` — measured: the launcher, lines 418-422, this session; the launcher is not in this batch's bucket.
- assumption: `python3` 3.12.3 and unittest are present — measured: this session.
- assumption: every finding can be pinned red without touching implementation code — refusal: if one cannot, say so in the envelope with the finding's number; do not change `ladder.py`, `write_path.py`, or `CONTRACT.md`.
