# Fixed conductor-task evaluation — 2026-09-05

Measured with the command below at `572a901a503e71ea3b255a8292e30515d5096529`.
The [machine-readable result](mcp-context-evaluation-2026-09-05.json)
includes source hashes, code hashes, argument sizes and transport overhead.

| Fixed question | Raw source bytes | Canonical payload bytes | Complete MCP response bytes |
| --- | ---: | ---: | ---: |
| Retrieve the selected review finding, including location and reproduction | 7,010 | 1,732 | 3,678 |
| Check the same two selected records again, with neither changed | 13,087 | 445 | 1,042 |
| Inspect the adjudication job's input slots without its prompt | 13,043 | 578 | 1,334 |

Each returned answer was compared with the exact source fields. The finding
was returned without omissions, the repeat checkpoint marked both records
unchanged, and the job card correctly showed no `scope` slot. CLI, MCP tool,
and matching resource payloads agreed. Request `_meta` was present in the
stdio probes. The sources' hashes were unchanged after the reads.

The MCP response counts include both textual and structured copies of the
payload. The tool catalogue response grows from 1,131 bytes in v1 to 1,966
bytes in v2: 835 bytes of additional discovery overhead. The configured v1
brief remains 1,560 payload bytes. These are fixed-task byte measurements,
not billed tokens, general savings percentages, or a comparison with an
optimal shell filter. Initialization, newline delimiters and the host's
context-selection policy are excluded; source-path lengths affect results.
The connected host's configuration was not changed by this measurement.

## Reproduce

Run from the repository root with the two named records present in the
operator's canonical dispatch store. Missing or changed evidence fails the
measurement rather than inventing replacement data. It creates only its own
temporary configuration files; the server reads the selected sources.

Extract and run the Python block, or execute it directly. This extraction
command reads the first Python block in this report:

```sh
python3 - <<'PY'
from pathlib import Path
report = Path("ops/conductor/reports/mcp-context-evaluation-2026-09-05.md")
code = report.read_text().split("```python\n", 1)[1].split("```", 1)[0]
exec(compile(code, str(report), "exec"))
PY
```

```python
"""One-run measurement of fixed conductor questions; no source writes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys
import tempfile

repo_root = Path.cwd()
entrypoint = repo_root / "ops/conductor/tools/lane_mcp.py"
baseline = json.loads(r'''
{
  "records": [
    {
      "id": "20260905T022311Z-review-codex-1a849a",
      "bytes": 7010,
      "sha256": "e991a980943d1f3543407c77eb1fb0b2bf7bb1d165e4098fa33369bafd33e80c"
    },
    {
      "id": "20260905T024911Z-review-codex-1af0d3",
      "bytes": 6077,
      "sha256": "5e5c073b95895bba25fb2b01852ef68c30ddc9fb364d9408e3cef1e9fd97e79c"
    }
  ],
  "registry_sha256": "6e0479fb8976ca9143f013ac355a950eb9b89bdcad253ed2e37ae7f315e77bec",
  "job": "adjudicate",
  "questions": [
    "What is finding 1, where is it, and how is it reproduced?",
    "Which selected record bytes changed since the previous checkpoint?",
    "Which placeholders does adjudicate take and does it take scope?"
  ],
  "comparison": "canonical response bytes versus full raw selected sources; exclude tool schemas and request bytes, report separately"
}
''')
dispatch_store = Path.home() / ".local/state/agentscient/dispatch"
registry_path = repo_root / "ops/devlane/task/jobs.json"
record_ids = [row["id"] for row in baseline["records"]]


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def run(config_path, verb, *arguments, stdin=None):
    result = subprocess.run(
        [sys.executable, "-B", str(entrypoint), "--config", str(config_path), verb, *arguments],
        input=stdin, text=True, capture_output=True, check=True,
    )
    if result.stderr:
        raise AssertionError("Unexpected stderr: " + result.stderr)
    return result.stdout


def ask(config_path, name, arguments):
    raw = run(config_path, "query", name, encoded(arguments).decode())
    payload = json.loads(raw)
    assert raw.rstrip("\n").encode() == encoded(payload)
    return payload


def rpc(config_path, requests):
    init = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "conductor-evidence-measurement", "version": "1"},
        "_meta": {"progressToken": "measurement"},
    }}
    ready = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    raw = run(config_path, "serve", stdin="\n".join(encoded(r).decode() for r in [init, ready, *requests]) + "\n")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert all("error" not in row for row in rows)
    return {row["id"]: row for row in rows}


records = []
for row in baseline["records"]:
    raw = (dispatch_store / row["id"] / "record.json").read_bytes()
    assert len(raw) == row["bytes"]
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    records.append(json.loads(raw))
registry_raw = registry_path.read_bytes()
assert hashlib.sha256(registry_raw).hexdigest() == baseline["registry_sha256"]

with tempfile.TemporaryDirectory(prefix="ag-mcp-eval-") as scratch:
    config_path = Path(scratch) / "v2.json"
    config = {"version": 2, "dispatch_store": str(dispatch_store), "job_ids": record_ids,
              "monitor_state": None, "consumer": "measurement", "usage_rollout": None,
              "job_registry": str(registry_path)}
    config_path.write_bytes(encoded(config))
    assert json.loads(run(config_path, "check")) == {"valid": True, "tools": 7}
    finding = ask(config_path, "lane_findings", {"id": record_ids[0]})
    original = records[0]["result"]["envelope"]["findings"][0]
    assert finding["state"] == "ok" and finding["findings_total"] == 1
    assert finding["record"]["revision"] == baseline["records"][0]["sha256"][:16]
    assert finding["findings"][0]["omitted"] == []
    for field in ("severity", "where", "claim", "reproduce"):
        assert finding["findings"][0][field] == original[field]
    initial = ask(config_path, "lane_changes", {})
    checkpoint = {"checkpoint": initial["checkpoint"]}
    unchanged = ask(config_path, "lane_changes", checkpoint)
    assert unchanged["changed"] == [] and unchanged["unchanged"] == record_ids
    assert unchanged["unknown"] == [] and unchanged["unavailable"] == []
    job = ask(config_path, "lane_jobs", {"name": baseline["job"]})
    original_job = json.loads(registry_raw)[baseline["job"]]
    slots = sorted(set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", original_job["prompt"])))
    assert job["job"]["slots"] == slots and "scope" not in slots
    assert "prompt" not in job["job"]
    assert job["job"]["prompt_bytes"] == len(original_job["prompt"].encode())
    brief = ask(config_path, "lane_brief", {})
    cases = [("lane_findings", {"id": record_ids[0]}, finding),
             ("lane_changes", checkpoint, unchanged),
             ("lane_jobs", {"name": baseline["job"]}, job)]
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
    for index, (name, arguments, _) in enumerate(cases, 2):
        requests.append({"jsonrpc": "2.0", "id": index, "method": "tools/call",
                         "params": {"name": name, "arguments": arguments, "_meta": {"progressToken": index}}})
    resource_cases = [("lane://findings/" + record_ids[0], finding),
                      ("lane://changes", initial), ("lane://jobs/" + baseline["job"], job)]
    for index, (uri, _) in enumerate(resource_cases, 5):
        requests.append({"jsonrpc": "2.0", "id": index, "method": "resources/read",
                         "params": {"uri": uri, "_meta": {}}})
    wire = rpc(config_path, requests)
    measurements = []
    raw_sizes = [baseline["records"][0]["bytes"], sum(row["bytes"] for row in baseline["records"]), len(registry_raw)]
    for index, ((name, arguments, payload), source_bytes) in enumerate(zip(cases, raw_sizes), 2):
        result = wire[index]["result"]
        assert result["isError"] is False and result["structuredContent"] == payload
        assert json.loads(result["content"][0]["text"]) == payload
        measurements.append({"tool": name, "raw_source_bytes": source_bytes,
                             "canonical_payload_bytes": len(encoded(payload)),
                             "mcp_response_bytes": len(encoded(wire[index])),
                             "argument_bytes": len(encoded(arguments)), "answer_matches_source": True})
    for index, (_, payload) in enumerate(resource_cases, 5):
        assert json.loads(wire[index]["result"]["contents"][0]["text"]) == payload
    config_v1 = {key: value for key, value in config.items() if key != "job_registry"}
    config_v1["version"] = 1
    v1_path = Path(scratch) / "v1.json"
    v1_path.write_bytes(encoded(config_v1))
    v1_wire = rpc(v1_path, [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
    report = {"measured_at": datetime.now(timezone.utc).isoformat(), "head_at_measurement": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "source_records": baseline["records"], "registry_sha256": baseline["registry_sha256"],
              "code_sha256": {str(p.relative_to(repo_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (entrypoint, entrypoint.with_name("lane_read.py"))},
              "measurements": measurements, "existing_brief_payload_bytes": len(encoded(brief)),
              "tools_list_v1_bytes": len(encoded(v1_wire[1])), "tools_list_v2_bytes": len(encoded(wire[1])),
              "transport": "standalone stdio, protocol 2025-06-18, request _meta included",
              "limits": ["Fixed tasks and raw-source baselines, not a comparison with an optimal shell filter.",
                         "Response sizes include configured source path lengths; MCP response includes text and structuredContent.",
                         "Tool catalogue overhead and argument bytes are separate; initialization, newline delimiters and host context policy are excluded.",
                         "No billed-token or universal-savings claim; connected-host configuration was not changed."]}
for row in baseline["records"]:
    assert hashlib.sha256((dispatch_store / row["id"] / "record.json").read_bytes()).hexdigest() == row["sha256"]
assert hashlib.sha256(registry_path.read_bytes()).hexdigest() == baseline["registry_sha256"]
print(json.dumps(report, indent=2, sort_keys=True))
```
