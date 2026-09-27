adversarial audit envelope, record 20260910T234542Z-review-grok-9e3b5d

{
  "artifacts": {},
  "counts": {
    "opinions": 0,
    "p1": 1,
    "p2": 0,
    "p3": 1
  },
  "findings": [
    {
      "claim": "Contract item 3 requires the needed half to name the exact findings.py disposition command that would satisfy the refusal; item 4 requires evidence to contain `contract item N` and to name that scope file by path. The declared grammar `contract item (?P<item>[1-9][0-9]*) of (?P<path>[^\\s;,]+)` (plan D3, quoted in CONTRACT.md, pinned once by test_launch_correction_contract.py) together with the prescribed evidence `contract item N of <scope path>: <why>` (CONTRACT.md correction row; plan D3 example and D5 needed command) captures the trailing colon inside `path`, so the planned citation_holds file check cannot resolve the scope file. Following the printed remedy therefore stays uncited, and item 6 gives no override.",
      "reproduce": "python3 -c \"import re; from pathlib import Path; p=re.compile(r'contract item (?P<item>[1-9][0-9]*) of (?P<path>[^\\\\s;,]+)'); ev='contract item 3 of .dev/ladder-inputs/scope-gate-20260910.md: found-text missing'; m=p.search(ev); print(m['path']); assert m['path'].endswith(':') and not Path(m['path']).is_file() and Path('.dev/ladder-inputs/scope-gate-20260910.md').is_file()\"",
      "severity": "p1",
      "where": ".dev/ladder-inputs/plan-gate-contracts.md:97-136; ops/devlane/dispatch/CONTRACT.md:777-778,976; ops/devlane/dispatch/tests/test_launch_correction_contract.py:22-24"
    },
    {
      "claim": "Contract item 7: a write job that follows a plan, tests, or implement record, or follows nothing, is not a correction and is not inspected by this gate. Plan D7 inspects that job when `--answers` is present and refuses class arguments.",
      "reproduce": "python3 -c \"from pathlib import Path; t=Path('.dev/ladder-inputs/plan-gate-contracts.md').read_text(); s=Path('.dev/ladder-inputs/scope-gate-20260910.md').read_text(); print([ln.strip() for ln in t.splitlines() if 'not a correction is refused' in ln][0]); assert 'is not inspected by this gate' in s and 'on a write job that is not a correction is refused' in t\"",
      "severity": "p3",
      "where": ".dev/ladder-inputs/plan-gate-contracts.md:151-157; .dev/ladder-inputs/scope-gate-20260910.md:50-51"
    }
  ],
  "job": "adversarial-review",
  "note": "Read both scope files and in/plan-gate-contracts.md whole; reviewed 94ab7a0..7b6664a (slice-1 contracts, pins, and the plan). Independently reproduced the citation-colon failure; the slice-1 pin locks that regex. Slice-1 document pins: 23 tests OK. Did not read the findings store. Live gate code is not in this slice. Did not adopt the security-audit envelope: adjudicate/sweep import is a store boundary (item 1 shape can still name imported keys); same-second `<=` is the plan's documented reading of item 5 at second resolution.",
  "spend": {
    "harness": "grok",
    "out": 52738,
    "runs": 1,
    "total": 1588793
  },
  "stamp": {
    "ended": "2026-09-11T00:01:16Z",
    "ref": "7b6664a420c391c511d2c419b6448772cdf7de37",
    "started": "2026-09-10T23:45:43Z"
  },
  "status": "ok",
  "verdict": "changes"
}
