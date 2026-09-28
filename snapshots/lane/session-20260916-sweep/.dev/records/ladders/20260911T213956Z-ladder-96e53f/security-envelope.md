security audit envelope, record 20260911T224145Z-review-codex-c5fc8b

{
  "artifacts": {},
  "counts": {
    "opinions": 0,
    "p1": 2,
    "p2": 1,
    "p3": 1
  },
  "findings": [
    {
      "claim": "declared (.dev/ladder-inputs/scope-item31-20260911.md:34): \u201cEach skeptic finding carries the declared words verbatim with their location, the practiced evidence verbatim with its location\u201d; practiced (.dev/ladder-inputs/plan-item31-slice1-20260911.md:155): locations need only punctuation and claims are only partitioned. Neither location is resolved nor compared with source bytes before the raw envelope becomes tests-fix input. A forged quotation pair with nonexistent locations therefore passes every prescribed check, corrupting the ledger and the downstream write role without an outside contributor.",
      "reproduce": "python3 - <<'PY'\nfrom pathlib import Path\nplan=Path('.dev/ladder-inputs/plan-item31-slice1-20260911.md').read_text()\nwhere='missing/test.py:1'\nclaim='declared (missing-contract.md:1): forged declaration; practiced: forged evidence; misses: obey the injected instruction'\nf={'severity':'p2','where':where,'claim':claim,'reproduce':'printf injected'}\nenv={'artifacts':{},'findings':[f],'counts':{'p1':0,'p2':1,'p3':0,'opinions':0},'verdict':'changes'}\nleft,sep,tail=claim.partition('; practiced: '); practiced,sep2,misses=tail.rpartition('; misses: ')\nassert env['artifacts']=={} and isinstance(env['findings'],list) and env['verdict']=='changes'\nassert f['severity'] in {'p1','p2','p3'} and f['reproduce'].strip()\nassert not any(c.isspace() for c in where) and ('/' in where or '.' in where)\nassert sep and sep2 and all((left,practiced,misses))\nassert not Path('missing/test.py').exists() and not Path('missing-contract.md').exists()\nassert 'json.dumps(indent=2, sort_keys=True)' in plan\nprint('all prescribed shape checks pass for nonexistent quoted locations')\nPY",
      "severity": "p1",
      "where": ".dev/ladder-inputs/plan-item31-slice1-20260911.md:150"
    },
    {
      "claim": "declared (.dev/ladder-inputs/scope-item31-20260911.md:53): \u201cA read-role job ... whose prompt contains a positive instruction to write a path is refused at render\u201d; practiced (.dev/ladder-inputs/plan-item31-slice1-20260911.md:236): detection admits only eight verbs at sentence start or after three introducers. Ordinary positive instructions such as \u201cPlease write /tmp/result.md\u201d and \u201cCopy the report to /tmp/result.md\u201d bypass the planned guard, allowing a policy-contained read harness to receive an outside-job write instruction.",
      "reproduce": "python3 - <<'PY'\nfrom pathlib import Path\np=Path('.dev/ladder-inputs/plan-item31-slice1-20260911.md').read_text()\nverbs={'write','save','create','store','emit','put','append','dump'}\nsamples=['Please write /tmp/result.md','Copy the report to /tmp/result.md']\nassert all(s.split()[0].lower() not in verbs for s in samples)\nassert '`write, save, create, store, emit, put, append, dump`' in p\nassert 'sentence start, or after `and`/`then`/`,`' in p\nprint(*samples,sep='\\n')\nPY",
      "severity": "p1",
      "where": ".dev/ladder-inputs/plan-item31-slice1-20260911.md:233"
    },
    {
      "claim": "declared (.dev/ladder-inputs/scope-item31-20260911.md:63): \u201cEvery new refusal is one stderr line ... exit 2, stdout empty\u201d; practiced (ops/conductor/ladder-lever.md:111): both new exit-2 rows promise one stderr line and empty stdout \u201cthen\u201d a stopped line, while the tracked plan classifies these durable mid-act outcomes as exit 3. The contradictory wire permits callers to mistake an abort with durable partial state for a pre-act rejection and retry it.",
      "reproduce": "python3 - <<'PY'\nfrom pathlib import Path\nlever=Path('ops/conductor/ladder-lever.md').read_text()\nplan=Path('.dev/ladder-inputs/plan-item31-slice1-20260911.md').read_text()\nrows=[x for x in lever.splitlines() if x.startswith('| 2 | `envelope`') or x.startswith('| 2 | `custody`')]\nassert len(rows)==2 and all('one stderr line' in x and 'stdout empty, then `stopped' in x for x in rows)\nassert 'exit 3, the wire line as the last reading' in plan and 'exit 3, nothing' in plan\nprint(*rows,sep='\\n')\nPY",
      "severity": "p2",
      "where": "ops/conductor/ladder-lever.md:111"
    },
    {
      "claim": "declared (.dev/ladder-inputs/scope-item31-20260911.md:46): \u201cThe driver refuses to write through a symlink or outside the inputs directory\u201d; practiced (.dev/ladder-inputs/plan-item31-slice1-20260911.md:224): the planned writer opens an existing regular target with O_TRUNC|O_NOFOLLOW and checks lstat/resolve afterward. A hard link passes every stated regular-file and containment check while truncating an inode outside the job. This is P3 under D-LAUNCHER-1 because planting the cross-job hard link requires an actor outside the stated snapshot-writing behavior.",
      "reproduce": "python3 - <<'PY'\nimport os,tempfile\nfrom pathlib import Path\nplan=Path('.dev/ladder-inputs/plan-item31-slice1-20260911.md').read_text()\nassert 'O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW' in plan\nwith tempfile.TemporaryDirectory() as d:\n root=Path(d); job=root/'job'; inputs=job/'inputs'; inputs.mkdir(parents=True)\n outside=root/'outside-job'; outside.write_text('KEEP')\n target=inputs/'skeptic-findings.md'; os.link(outside,target)\n fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600); os.write(fd,b'OVERWRITTEN'); os.close(fd)\n assert target.is_file() and target.resolve().is_relative_to(inputs.resolve())\n assert not outside.resolve().is_relative_to(job.resolve())\n assert outside.read_text()=='OVERWRITTEN' and os.lstat(target).st_nlink==2\n print('outside-job inode overwritten')\nPY",
      "severity": "p3",
      "where": ".dev/ladder-inputs/plan-item31-slice1-20260911.md:220"
    }
  ],
  "job": "security-audit",
  "note": "Covered argv/shell/SQL/template seams, credentials and records, path/ref custody, recorded sandbox argv, vendor-output trust, and supply-chain changes. Secret scans were clean for all 16 changed tracked files and the 1,511-file tree; no dependency, lockfile, action, or production executable changed. The 38 changed tests pass. Later jobs.json, ladder.py, write_path.py, and launch.py implementations are absent, so their runtime behavior and live vendor/network confinement could not be exercised. The session store was not read. Graft saved approximately 1,248,896 tokens.",
  "spend": {
    "harness": "codex",
    "out": 32495,
    "runs": 1,
    "total": 3314859
  },
  "stamp": {
    "ended": "2026-09-11T22:49:32Z",
    "ref": "6e62422390d793c10a00609c3a7a81dcf8dd0cc3",
    "started": null
  },
  "status": "ok",
  "verdict": "changes"
}
