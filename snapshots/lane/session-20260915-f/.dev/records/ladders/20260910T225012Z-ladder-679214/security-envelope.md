security audit envelope, record 20260910T233738Z-review-codex-8f5dd0

{
  "artifacts": {},
  "counts": {
    "opinions": 0,
    "p1": 4,
    "p2": 1,
    "p3": 0
  },
  "findings": [
    {
      "claim": "Contract items 3 and 4 require the printed disposition command to satisfy the gate. The citation regex greedily captures the colon prescribed after the scope path, resolving `scope-gate-20260910.md:` instead of the real file; following the exact remedy leaves the correction permanently refused.",
      "reproduce": "python3 -c 'import re; from pathlib import Path; p=re.compile(r\"contract item (?P<item>[1-9][0-9]*) of (?P<path>[^\\s;,]+)\"); m=p.search(\"contract item 3 of .dev/ladder-inputs/scope-gate-20260910.md: found-text missing\"); print(m[\"path\"], Path(m[\"path\"]).is_file()); assert m[\"path\"].endswith(\":\") and not Path(m[\"path\"]).is_file()'",
      "severity": "p1",
      "where": ".dev/ladder-inputs/plan-gate-contracts.md:95; ops/devlane/dispatch/CONTRACT.md:777,976"
    },
    {
      "claim": "Contract item 4 requires a numbered item of a scope file, but the planned validator accepts any repository file containing that numbered line. An unrelated citation such as item 1 of `docs/verified-couplings.md` therefore unlocks a correction and defeats the gate's integrity.",
      "reproduce": "python3 -c 'import re; from pathlib import Path; p=re.compile(r\"contract item (?P<item>[1-9][0-9]*) of (?P<path>[^\\s;,]+)\"); m=p.search(\"contract item 1 of docs/verified-couplings.md\"); f=Path(m[\"path\"]); ok=any(re.match(r\"^\\s*\"+m[\"item\"]+r\"\\.\\s\",x) for x in f.read_text().splitlines()); print(f, ok); assert f.is_file() and ok and \".dev/ladder-inputs/scope-\" not in str(f)'",
      "severity": "p1",
      "where": ".dev/ladder-inputs/plan-gate-contracts.md:95-103"
    },
    {
      "claim": "Contract item 1 classifies `adjudicate` and `sweep` as review jobs, but the ledger importer excludes both and the planned ledger slice does not add them. Existing findings from those jobs can never acquire ledger rows, so their corrections are permanently refused with no override.",
      "reproduce": "python3 - <<'PY'\nimport ast,json\nfrom pathlib import Path\nt=ast.parse(Path('ops/conductor/tools/findings.py').read_text())\njobs=ast.literal_eval(next(n.value for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='REVIEW_JOBS' for x in n.targets)))\nmissing={'adjudicate','sweep'}-set(jobs)\nexcluded=[]\nfor p in Path('.dev/records/dispatches').glob('*.json'):\n r=json.loads(p.read_text()); n=len((((r.get('result') or {}).get('envelope') or {}).get('findings') or []))\n if r.get('job') in missing and n: excluded.append((r['id'],r['job'],n))\nprint(sorted(missing),excluded); assert missing=={'adjudicate','sweep'} and excluded\nPY",
      "severity": "p1",
      "where": ".dev/ladder-inputs/scope-gate-20260910.md:22-26; ops/conductor/tools/findings.py:41,121-125; .dev/ladder-inputs/plan-gate-contracts.md:223-249"
    },
    {
      "claim": "Contract item 3 makes the refusal's remedy an executable shell command, but its key is unquoted and the planned `^\\S+#[1-9][0-9]*$` validation admits shell substitutions. The ledger also derives keys from unvalidated record IDs, so vendor-produced record data can execute outside the job when the operator runs the required remedy.",
      "reproduce": "rg -n '\"key\": f|record\\.validate' ops/conductor/tools/findings.py; python3 -c 'import re; k=\"$(id)#1\"; print(k); assert re.fullmatch(r\"\\S+#[1-9][0-9]*\",k)' && bash -c 'printf \"argv=%s\\n\" $(id)#1'",
      "severity": "p1",
      "where": ".dev/ladder-inputs/plan-gate-contracts.md:128-136,246-248; ops/conductor/tools/findings.py:121-132"
    },
    {
      "claim": "Contract item 5 requires `disposed_at` to precede mint, but both timestamps have only second precision and the plan accepts `disposed_at <= stamp`. A concurrent disposition written after mint within the same second is accepted by that mint attempt.",
      "reproduce": "python3 -c 'from datetime import datetime,timezone; a=datetime(2026,9,10,12,0,0,100000,tzinfo=timezone.utc); b=datetime(2026,9,10,12,0,0,900000,tzinfo=timezone.utc); f=lambda x:x.isoformat(timespec=\"seconds\").replace(\"+00:00\",\"Z\"); print(a.isoformat(),b.isoformat(),f(a),f(b),f(b)<=f(a)); assert b>a and f(b)<=f(a)'",
      "severity": "p2",
      "where": ".dev/ladder-inputs/plan-gate-contracts.md:138-143; ops/devlane/dispatch/launch.py:141-142; ops/conductor/tools/findings.py:172-173"
    }
  ],
  "job": "security-audit",
  "note": "Covered argv/shell, SQL/template, secrets, path/ref containment, permission/sandbox records, vendor-output trust, and supply-chain deltas. No credential, SQL/template, or supply-chain finding was found. The delta adds contracts/tests rather than the live gate, so runtime enforcement and external vendor/network behavior could not be exercised.",
  "spend": {
    "harness": "codex",
    "out": 22048,
    "runs": 1,
    "total": 2310797
  },
  "stamp": {
    "ref": "fbc860b04457f1c70eedfe221f658a25c5e4eb1c"
  },
  "status": "ok",
  "verdict": "changes"
}
