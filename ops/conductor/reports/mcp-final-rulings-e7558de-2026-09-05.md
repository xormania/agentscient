# MCP final review rulings — 2026-09-05

Artifact: `e7558dea9e10835f3fcfaeebb703199119833b38` over dev
`56b26b51fea0727ef75332c5d0469b2a9d11b3ee`. GPT-6 rules on Grok's quality
findings and on the additional observations in the independent Opus ruling.
GPT-6 produced neither the disputed query/test artifacts nor those findings;
the mechanical integration of dev's record guard is outside Grok's findings.
No code or tests were changed in response before these rulings.

Original reports remain in their canonical dispatch records:

- Quality: `20260905T074006Z-review-grok-d234f5`, actual model `grok-4.6`,
  accepted envelope, CHANGES (two P2, three P3).
- Security: `20260905T074014Z-review-codex-874fc0`, actual model
  `gpt-daybreak-blue-latest`, accepted envelope, CHANGES (one P3).
- Independent security ruling: `20260905T074734Z-adjudicate-claude-e8e593`,
  actual model `claude-opus-5`, accepted envelope, PARTIAL on the reported
  finding, with two additional P3 observations (one explicitly an opinion).

## Quality findings

| Finding | Ruling and disposition |
| --- | --- |
| Q1: BOM accepted for records but refused for the registry | PARTIAL: the decoder difference reproduces. The P2 contract-breach claim is rejected: section 5's parenthetical defines the shared bounds as size, regular-file type and no symlink following; it does not promise decoder parity. BOM tolerance is optional in JSON parsers. Retain this as a nonblocking interoperability observation. |
| Q2: 64 large legal rows trigger the whole-query overflow reading | REJECTED as a defect. Section 8 explicitly retains the 16384-byte whole-query cap and existing unavailable overflow reading. A 64-row input cap does not override that output bound. The probe returns exactly that reading; named lookup of one of the same rows succeeds. No new pagination promise is inferred. |
| Q3: registry accepts a 1200-deep value while record scanning has a 1024 guard | UPHELD as P3. The current runtime returns a sparse row without crashing. This is a known nesting-policy alignment gap, not a complete malformed-input survival proof. Deferred under the operator-selected local-source policy. |
| Q4: test header still says v2 is unimplemented | UPHELD as P3 documentation drift. Lines 17–19 retain the pre-implementation description. The assertions execute the implemented v2 surface; no test result is falsified by that stale header. Deferred, with no oracle changes. |
| Q5: invalid named card cannot be distinguished from an empty declared object | REJECTED as a defect. The two forms have distinct names: null for the non-object row, the actual key for an empty object. Section 5 separately declares the list shape and the extended named-card shape. Both preserve the invalid-row marker. |

For Q1, [RFC 8259 section 8.1](https://www.rfc-editor.org/rfc/rfc8259#section-8.1)
permits parsers to ignore a BOM instead of treating it as an error; neither
choice is mandatory. This source supports the interoperability ruling, not
an assertion that every UTF-8 byte sequence is JSON.

## Security ruling and additional observations

Opus ruled N1 PARTIAL: UTF-16 acceptance and the section 3 wording mismatch
are real, but the byte decoder already exists at the dev base, and an actor
able to plant a UTF-16 record can plant equivalent UTF-8 content in the same
selected source. The ruling therefore classifies it as a P3 contract-fidelity
gap, nonblocking under the lever's local-source policy. Root independently
reproduced UTF-8, UTF-16 and UTF-32 records returning `ok` from both
`lane_record` and `lane_findings` at the artifact. Do not rely on section 3 as
an enforced UTF-8-only source gate. The gap is deferred, not repaired or
represented as an approval verdict.

Opus N2 is UPHELD as a P3 coverage gap: searching the new test file for UTF-16
and UTF-32 finds no such encoding fixtures. Any future encoding-policy change
must include an independently authored positive/negative row and preserve
v1 compatibility. This does not justify changing tests merely to match code.

Opus N3 is retained as an unvalidated opinion about the raw-byte depth scanner
and UTF-16 code units. Opus explicitly could not execute that probe. Root does
not promote it into either a reproduced defect or a proof that the guard's
failure mode is safe. Reassess it with the encoding-policy follow-up.

The standing handoff at retained branch `records/codex-closeout-20260905`,
`ce2bbf97aba915fcf0b3583f5ef04dfadcbdd52e`, lines 37–38 says functionality first
and not to chase P3s or automatically make every P2 a blocker. The tracked
MCP lever also explicitly limits its malformed-input assurance to selected
local sources. These rulings leave no blocking finding and make no claim of
complete conformance to every malformed-source clause. No new code push is
needed for these dispositions; the candidate remains stationary.

## Reproduction

Root ran the following scratch command at the artifact. It uses owned
synthetic sources, no live registry or dispatch records. The observations
were: BOM-free controls both ok; BOM record ok/registry unavailable; large
list unavailable with the exact whole-query reason; named large card ok;
1200-deep registry ok; invalid/empty card names null versus job.

```python
from pathlib import Path
import json, subprocess, sys, tempfile
entry = Path("ops/conductor/tools/lane_mcp.py").resolve()
with tempfile.TemporaryDirectory(prefix="ag-mcp-quality-ruling-") as temporary:
    root = Path(temporary)
    record = root / "store/job/record.json"
    record.parent.mkdir(parents=True)
    registry = root / "jobs.json"
    cfg = root / "config.json"
    cfg.write_text(json.dumps({"version":2,"dispatch_store":"store","job_ids":["job"],"monitor_state":None,"consumer":"ruling","usage_rollout":None,"job_registry":"jobs.json"}))
    def ask(name, args=None):
        run = subprocess.run([sys.executable,"-B",str(entry),"--config",str(cfg),"query",name,json.dumps(args or {})],text=True,capture_output=True)
        assert run.returncode == 0 and not run.stderr, (run.returncode,run.stderr)
        return json.loads(run.stdout)
    payload = {"status":"closed","result":{"envelope":{"findings":[],"note":"control"}}}
    raw = json.dumps(payload).encode()
    record.write_bytes(raw)
    registry.write_bytes(b"{}")
    result = {"bom_control": {"record":ask("lane_findings",{"id":"job"})["state"],"registry":ask("lane_jobs")["state"]}}
    record.write_bytes(b"\xef\xbb\xbf" + raw)
    registry.write_bytes(b"\xef\xbb\xbf{}")
    result["bom"] = {"record":ask("lane_findings",{"id":"job"})["state"],"registry":ask("lane_jobs")["state"]}
    registry.write_text(json.dumps({f"job-{n:02d}":{"adapter":"A"*256,"role":"R"*256,"snapshot":"whole","prompt":"x {ref}"} for n in range(64)}))
    result["fat_list"] = ask("lane_jobs")
    card = ask("lane_jobs",{"name":"job-00"})
    result["fat_card"] = {"state":card["state"],"name":card["job"]["name"]}
    registry.write_text('{"deep-job":' + '{"k":'*1200 + '0' + '}'*1200 + '}')
    result["deep_registry"] = ask("lane_jobs")
    registry.write_text(json.dumps({"job":"not-an-object"}))
    bad = ask("lane_jobs",{"name":"job"})
    registry.write_text(json.dumps({"job":{}}))
    good = ask("lane_jobs",{"name":"job"})
    result["invalid_and_empty_names"] = [bad["job"]["name"],good["job"]["name"]]
    print(json.dumps(result,indent=2))
```

Additional checks: `sed -n '1,20p' ops/conductor/tests/test_lane_mcp_context.py`
for Q4; `rg -n 'utf-16|utf_16|utf-32|utf_32'` on that file for N2 (no hits).
The security reviewer and Opus could not run the full fixtures in their read
sandboxes; quality ran eight targeted methods. Those are declared review
limits. The independent local and GitHub suite results are separate evidence.
