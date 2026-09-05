"""Lane-MCP v2 context-read acceptance tests, written from the contracts.

Contracts (only): `ops/conductor/lane-mcp-v2.md` extending
`ops/conductor/lane-mcp-lever.md`, plus inherited
`ops/conductor/instrument-conventions.md`. Named counterparties are
the record envelope fields and the job-registry shape quoted in
lane-mcp-v2.md §9. `ops/conductor/tools/lane_mcp.py` and
`ops/conductor/tools/lane_read.py` are the subject and are not read
here.

Tests reuse the v1 fixture in test_lane_mcp.py, plant synthetic
records and registries, and invoke the documented CLI as a subprocess:
`python3 -B ops/conductor/tools/lane_mcp.py --config FILE
check|serve|query TOOL [JSON]`. No live dispatch store, tracked
record, real job registry, network, or harness call.

v2 is not implemented. A missing entrypoint is already pinned by
test_lane_mcp.TestLaneMcpPresence; this file stages the same
copy-tool-bytes stand-in so each assertion fails on the v2 promise.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_lane_mcp import (  # noqa: E402
    CONSUMER,
    COUNTS,
    FINDING,
    HEAD,
    JOB,
    JOB2,
    JOB_UNLISTED,
    MODEL,
    NOTE,
    PROMPT,
    SCHEMA,
    TOOLS,
    TRANSCRIPT,
    VERDICT,
    _LaneMcpFixture,
    notify,
    rpc,
)

REPO = Path(__file__).resolve().parents[3]
V1_EXAMPLE = REPO / "ops" / "conductor" / "lane-mcp.example.json"
V2_EXAMPLE = REPO / "ops" / "conductor" / "lane-mcp-v2.example.json"
V2_TOOLS = TOOLS + ("lane_findings", "lane_changes", "lane_jobs")
CURSOR_GRAMMAR = re.compile(r"^[0-9a-f]{16}:[1-9][0-9]{0,8}$")
REVISION_GRAMMAR = re.compile(r"^[0-9a-f]{16}$")
JOB_NAME_GRAMMAR = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
LEAKS = (PROMPT, TRANSCRIPT, "raw.out")
DISPATCHABLE = {
    "adapter": "harness",
    "role": "write",
    "snapshot": "whole",
    "prompt": "Write tests for {scope} at {ref} into {out}.",
    "deliverable": "a red test file",
    "constraints": ["do not edit the implementation", "no network"],
    "caps": {"timeout": 1800},
}


def revision_of(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:16]


class _V2Fixture(_LaneMcpFixture):
    """v1 fixture plus version-2 config, records and registries."""

    def plant_v2_config(
        self,
        *,
        job_ids: list[str] | None = None,
        job_registry: str | None = "jobs.json",
        **overrides,
    ) -> Path:
        payload = {
            "version": 2,
            "dispatch_store": "store",
            "job_ids": list(job_ids if job_ids is not None else [JOB]),
            "monitor_state": "monitor",
            "consumer": CONSUMER,
            "usage_rollout": "rollout.jsonl",
            "job_registry": job_registry,
        }
        payload.update(overrides)
        return self.plant_config(payload)

    def plant_context_record(
        self,
        rec_id: str = JOB,
        *,
        findings: list | None = None,
        note: object = NOTE,
        job: object = "author-tests",
        stage: object = "code",
        counts: dict | None = None,
        verdict: object = VERDICT,
        extra: dict | None = None,
        raw: bytes | None = None,
    ) -> Path:
        if raw is not None:
            return self.plant_record(rec_id, raw=raw)
        rows = findings
        if rows is None:
            rows = [
                {
                    "severity": "p2",
                    "where": "ops/conductor/lane-mcp-v2.md",
                    "claim": FINDING,
                    "reproduce": "python3 -m unittest ...test_lane_findings",
                }
            ]
        rec = {
            "id": rec_id,
            "job": job,
            "stage": stage,
            "status": "closed",
            "model": MODEL,
            "result": {
                "head": HEAD,
                "envelope": {
                    "verdict": verdict,
                    "counts": dict(counts if counts is not None else COUNTS),
                    "findings": rows,
                    "note": note,
                },
                "changed_paths": ["alpha.py"],
            },
            "attempts": [{}],
            "session": {
                "spend": {
                    "harness": "grok",
                    "total": 1,
                    "out": 0,
                    "runs": 1,
                    "secret": TRANSCRIPT,
                }
            },
            "prompt": PROMPT,
            "artifacts": {"log": "must-not-leak"},
            "commit": {"subject": "must-not-leak"},
        }
        if extra:
            rec.update(extra)
        return self.plant_record(rec_id, raw=(json.dumps(rec, indent=2) + "\n").encode())

    def plant_registry(
        self,
        jobs: dict | None = None,
        *,
        path: Path | None = None,
        raw: bytes | None = None,
    ) -> Path:
        dest = path if path is not None else self.work / "jobs.json"
        if raw is not None:
            self._plant_bytes(dest, raw)
            return dest
        body = json.dumps(jobs if jobs is not None else {}, indent=2) + "\n"
        self._plant_bytes(dest, body.encode("utf-8"))
        return dest

    def assert_v2(self, payload: dict, tool: str) -> dict:
        self.assertIsInstance(payload, dict, payload)
        self.assertEqual(payload.get("schema"), SCHEMA, payload)
        self.assertEqual(payload.get("query"), tool, payload)
        self.assertIn(payload.get("state"), ("ok", "unknown", "unavailable"), payload)
        dumped = json.dumps(payload)
        for leak in LEAKS:
            self.assertNotIn(leak, dumped)
        for banned in ("artifacts", "commit", "spend", "prompt"):
            self.assertNotIn(banned, payload)
        return payload

    def empty_findings_fields(self, payload: dict) -> None:
        self.assertEqual(payload.get("findings"), [])
        self.assertIsNone(payload.get("findings_total"))
        self.assertIsNone(payload.get("record"))
        self.assertIsNone(payload.get("note"))
        self.assertIsNone(payload.get("note_bytes"))
        self.assertIsNone(payload.get("page"))

    def rpc_error_line(self, obj: dict) -> str:
        result = obj.get("result")
        if isinstance(result, dict) and result.get("isError") is True:
            content = result.get("content") or []
            texts = [
                item.get("text")
                for item in content
                if isinstance(item, dict) and item.get("text")
            ]
            self.assertTrue(texts, obj)
            return str(texts[0])
        err = obj.get("error")
        self.fail(f"expected domain isError line, got {obj}; error={err}")

    def notifications(self, objs: list[dict]) -> list[dict]:
        return [obj for obj in objs if "method" in obj and "id" not in obj]


class TestLaneMcpContextConfig(_V2Fixture):
    def test_v1_check_and_example_stay_four_tools(self):
        proc = self.invoke(["check"])
        self.assertEqual(self.load_query(proc), {"valid": True, "tools": 4})
        self.assertTrue(V1_EXAMPLE.is_file(), V1_EXAMPLE)
        example = json.loads(V1_EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(example["version"], 1)
        self.assertNotIn("job_registry", example)
        via_example = self.invoke(["check"], config=V1_EXAMPLE)
        self.assertEqual(self.load_query(via_example), {"valid": True, "tools": 4})

    def test_v1_with_job_registry_and_v2_without_it_refuse_config(self):
        cases = [
            (
                "v1-with-registry",
                {
                    "version": 1,
                    "dispatch_store": "store",
                    "job_ids": [JOB],
                    "monitor_state": "monitor",
                    "consumer": CONSUMER,
                    "usage_rollout": "rollout.jsonl",
                    "job_registry": None,
                },
            ),
            (
                "v2-without-registry",
                {
                    "version": 2,
                    "dispatch_store": "store",
                    "job_ids": [JOB],
                    "monitor_state": "monitor",
                    "consumer": CONSUMER,
                    "usage_rollout": "rollout.jsonl",
                },
            ),
        ]
        for name, payload in cases:
            with self.subTest(name=name):
                self.plant_config(payload)
                line = self.assert_refusal(self.invoke(["check"]), "config")
                self.assertIn("job_registry", line)

    def test_v2_check_is_seven_tools_and_example_matches_the_declared_shape(self):
        self.plant_v2_config(job_registry=None)
        proc = self.invoke(["check"])
        self.assertEqual(self.load_query(proc), {"valid": True, "tools": 7})

        self.assertTrue(V2_EXAMPLE.is_file(), V2_EXAMPLE)
        example = json.loads(V2_EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(example["version"], 2)
        self.assertEqual(
            set(example),
            {
                "version",
                "dispatch_store",
                "job_ids",
                "monitor_state",
                "consumer",
                "usage_rollout",
                "job_registry",
            },
        )
        self.assertIsNone(example["dispatch_store"])
        self.assertEqual(example["job_ids"], [])
        self.assertIsNone(example["monitor_state"])
        self.assertEqual(example["consumer"], "conductor")
        self.assertIsNone(example["usage_rollout"])
        self.assertIsNone(example["job_registry"])
        via_example = self.invoke(["check"], config=V2_EXAMPLE)
        self.assertEqual(self.load_query(via_example), {"valid": True, "tools": 7})

    def test_v1_query_refuses_the_three_v2_tool_names(self):
        self.plant_config()
        for tool, arguments in (
            ("lane_findings", {"id": JOB}),
            ("lane_changes", {}),
            ("lane_jobs", {}),
        ):
            with self.subTest(tool=tool):
                proc = self.query(tool, arguments)
                self.assert_refusal(proc, "arguments")


class TestLaneMcpContextFindings(_V2Fixture):
    def test_lane_findings_projects_note_findings_and_recorded_counts(self):
        counts = {"p1": 0, "p2": 9, "p3": 0, "opinions": 0}
        rec = self.plant_context_record(counts=counts)
        self.plant_v2_config()
        proc = self.query("lane_findings", {"id": JOB})
        payload = self.assert_v2(self.load_query(proc), "lane_findings")
        self.assertEqual(payload["state"], "ok")
        self.assertIsNone(payload["reason"])
        record = payload["record"]
        self.assertEqual(record["id"], JOB)
        self.assertEqual(record["job"], "author-tests")
        self.assertEqual(record["stage"], "code")
        self.assertEqual(record["recorded_status"], "closed")
        self.assertEqual(record["verdict"], VERDICT)
        self.assertEqual(record["counts"], counts)
        self.assertNotEqual(record["counts"]["p2"], 1)
        self.assertEqual(record["revision"], revision_of(rec))
        self.assertRegex(record["revision"], REVISION_GRAMMAR)
        self.assertIn("record.json", str(record["evidence"]))
        self.assertEqual(payload["note"], NOTE)
        self.assertEqual(payload["note_bytes"], len(NOTE.encode("utf-8")))
        self.assertEqual(payload["findings_total"], 1)
        self.assertEqual(len(payload["findings"]), 1)
        entry = payload["findings"][0]
        self.assertEqual(entry["n"], 1)
        self.assertEqual(entry["severity"], "p2")
        self.assertEqual(entry["claim"], FINDING)
        self.assertEqual(entry["omitted"], [])
        page = payload["page"]
        self.assertEqual(page["from"], 1)
        self.assertEqual(page["to"], 1)
        self.assertEqual(page["count"], 1)
        self.assertFalse(page["more"])
        self.assertIsNone(page["next_cursor"])
        dumped = json.dumps(payload)
        self.assertIn(FINDING, dumped)
        self.assertIn(NOTE, dumped)
        self.assertNotIn("must-not-leak", dumped)
        self.assertNotIn("secret", dumped)

    def test_lane_findings_missing_unavailable_and_cursor_not_judged(self):
        self.plant_v2_config()
        bogus = "aaaaaaaaaaaaaaaa:1"

        missing_store = self.query("lane_findings", {"id": JOB})
        payload = self.assert_v2(self.load_query(missing_store), "lane_findings")
        self.assertEqual(payload["state"], "unknown")
        self.assertEqual(payload["reason"], "dispatch store is missing")
        self.empty_findings_fields(payload)

        self.store.mkdir()
        missing_record = self.query("lane_findings", {"id": JOB, "cursor": bogus})
        payload = self.assert_v2(self.load_query(missing_record), "lane_findings")
        self.assertEqual(payload["state"], "unknown")
        self.assertEqual(payload["reason"], "record is missing")
        self.empty_findings_fields(payload)
        self.assertNotIn("cursor", payload.get("reason") or "")

        self.plant_context_record(raw=b"{not-json\n")
        malformed = self.query("lane_findings", {"id": JOB, "cursor": bogus})
        payload = self.assert_v2(self.load_query(malformed), "lane_findings")
        self.assertEqual(payload["state"], "unavailable")
        self.assertEqual(payload["reason"], "record is unreadable or malformed")
        self.empty_findings_fields(payload)

        self.reset_sources()
        self.plant_v2_config()
        self.plant_context_record()
        unconfigured = self.query("lane_findings", {"id": JOB_UNLISTED})
        self.assert_refusal(unconfigured, "arguments")
        extra = self.query("lane_findings", {"id": JOB, "extra": 1})
        self.assert_refusal(extra, "arguments")

    def test_lane_findings_omitted_fields_note_rules_and_non_object_entries(self):
        long_where = "W" * 257
        long_claim = "C" * 1025
        long_repro = "R" * 1025
        long_note = "N" * 2049
        long_job = "j" * 300
        findings = [
            {
                "severity": "p1",
                "where": "here",
                "claim": "ok-claim",
                "reproduce": "ok-repro",
            },
            {
                "severity": "fatal",
                "where": long_where,
                "claim": long_claim,
                "reproduce": long_repro,
            },
            {
                "severity": "p3",
                "where": 12,
                "claim": None,
            },
            ["not", "an", "object"],
        ]
        rec = {
            "id": JOB,
            "job": long_job,
            "stage": "code",
            "status": "closed",
            "result": {
                "envelope": {
                    "verdict": VERDICT,
                    "counts": dict(COUNTS),
                    "findings": findings,
                    "note": long_note,
                }
            },
        }
        self.plant_context_record(raw=(json.dumps(rec) + "\n").encode("utf-8"))
        self.plant_v2_config()
        proc = self.query("lane_findings", {"id": JOB})
        payload = self.assert_v2(self.load_query(proc), "lane_findings")
        self.assertEqual(payload["state"], "ok")
        self.assertIsNone(payload["note"])
        self.assertEqual(payload["note_bytes"], len(long_note.encode("utf-8")))
        self.assertIsNone(payload["record"]["job"])
        self.assertEqual(payload["record"]["stage"], "code")
        self.assertEqual(payload["findings_total"], 4)
        self.assertEqual(len(payload["findings"]), 4)
        ok, bad, partial, broken = payload["findings"]
        self.assertEqual(ok["n"], 1)
        self.assertEqual(ok["omitted"], [])
        self.assertEqual(bad["n"], 2)
        self.assertIsNone(bad["severity"])
        self.assertIsNone(bad["where"])
        self.assertIsNone(bad["claim"])
        self.assertIsNone(bad["reproduce"])
        for field in ("severity", "where", "claim", "reproduce"):
            self.assertIn(field, bad["omitted"])
        self.assertEqual(partial["n"], 3)
        self.assertEqual(partial["severity"], "p3")
        self.assertIsNone(partial["where"])
        self.assertIsNone(partial["claim"])
        self.assertIsNone(partial["reproduce"])
        self.assertIn("where", partial["omitted"])
        self.assertNotIn("claim", partial["omitted"])
        self.assertNotIn("reproduce", partial["omitted"])
        self.assertEqual(broken["n"], 4)
        self.assertEqual(broken["omitted"], ["entry"])
        self.assertIsNone(broken["severity"])

        rec["result"]["envelope"]["note"] = 11
        rec["result"]["envelope"]["findings"] = []
        self.plant_context_record(raw=(json.dumps(rec) + "\n").encode("utf-8"))
        not_string = self.assert_v2(
            self.load_query(self.query("lane_findings", {"id": JOB})),
            "lane_findings",
        )
        self.assertEqual(not_string["state"], "ok")
        self.assertIsNone(not_string["note"])
        self.assertIsNone(not_string["note_bytes"])
        self.assertEqual(not_string["reason"], "note is not a string")

        rec["result"]["envelope"]["note"] = NOTE
        rec["result"]["envelope"]["findings"] = {"n": 1}
        self.plant_context_record(raw=(json.dumps(rec) + "\n").encode("utf-8"))
        not_list = self.assert_v2(
            self.load_query(self.query("lane_findings", {"id": JOB})),
            "lane_findings",
        )
        self.assertEqual(not_list["state"], "unavailable")
        self.assertEqual(not_list["reason"], "envelope findings is not a list")
        self.assertIsNone(not_list["findings_total"])
        self.assertEqual(not_list["findings"], [])
        self.assertIsInstance(not_list["record"], dict)
        self.assertEqual(not_list["record"]["id"], JOB)

        rec["result"]["envelope"]["findings"] = []
        rec["result"]["envelope"]["note"] = "ok"
        raw = (
            json.dumps(rec).replace('"note": "ok"', r'"note": "\uD800"') + "\n"
        ).encode("ascii")
        self.plant_context_record(raw=raw)
        bad_unicode = self.assert_v2(
            self.load_query(self.query("lane_findings", {"id": JOB})),
            "lane_findings",
        )
        self.assertEqual(bad_unicode["state"], "ok")
        self.assertIsNone(bad_unicode["note"])
        self.assertIsNone(bad_unicode["note_bytes"])
        self.assertEqual(bad_unicode["reason"], "note is not valid Unicode")

    def test_lane_findings_cursor_pages_revision_and_malformed_cursors(self):
        rows = [
            {
                "severity": "p2",
                "where": f"w{n}",
                "claim": f"claim-{n}-" + ("X" * 900),
                "reproduce": f"repro-{n}",
            }
            for n in range(1, 9)
        ]
        rec = self.plant_context_record(findings=rows, note="first-page-note")
        rev = revision_of(rec)
        self.plant_v2_config()
        first = self.assert_v2(
            self.load_query(self.query("lane_findings", {"id": JOB})),
            "lane_findings",
        )
        self.assertEqual(first["state"], "ok")
        self.assertEqual(first["findings_total"], 8)
        self.assertEqual(first["note"], "first-page-note")
        page = first["page"]
        self.assertGreaterEqual(page["count"], 1)
        self.assertEqual(len(first["findings"]), page["count"])
        self.assertEqual(first["findings"][0]["n"], page["from"])
        self.assertEqual(first["findings"][-1]["n"], page["to"])
        self.assertTrue(page["more"])
        self.assertRegex(page["next_cursor"], CURSOR_GRAMMAR)
        self.assertEqual(page["next_cursor"], f"{rev}:{page['to'] + 1}")

        second = self.assert_v2(
            self.load_query(
                self.query(
                    "lane_findings",
                    {"id": JOB, "cursor": page["next_cursor"]},
                )
            ),
            "lane_findings",
        )
        self.assertEqual(second["state"], "ok")
        self.assertIsNone(second["note"])
        self.assertEqual(second["note_bytes"], first["note_bytes"])
        self.assertEqual(second["findings"][0]["n"], page["to"] + 1)
        seen = [row["n"] for row in first["findings"] + second["findings"]]
        self.assertEqual(seen, list(range(1, seen[-1] + 1)))
        self.assertNotIn(1, [row["n"] for row in second["findings"]])

        stale = f"{'b' * 16}:1"
        self.assertNotEqual(stale.split(":")[0], rev)
        refused = self.query("lane_findings", {"id": JOB, "cursor": stale})
        line = self.assert_refusal(refused, "cursor")
        self.assertIn(f"cursor for revision {rev}", line)
        self.assertIn(stale.split(":")[0], line)
        self.assertIn("restart from the first page", line)

        past = self.query("lane_findings", {"id": JOB, "cursor": f"{rev}:9"})
        line = self.assert_refusal(past, "cursor")
        self.assertIn("supply an index within findings_total", line)

        for cursor in (f"{rev}:0", f"{rev}:01", f"{rev.upper()}:1", "nope"):
            with self.subTest(cursor=cursor):
                proc = self.query("lane_findings", {"id": JOB, "cursor": cursor})
                self.assert_refusal(proc, "arguments")

        rewritten = rec.read_bytes()
        rec.write_bytes(rewritten)
        self.assertEqual(revision_of(rec), rev)
        again = self.assert_v2(
            self.load_query(self.query("lane_findings", {"id": JOB})),
            "lane_findings",
        )
        self.assertEqual(again["record"]["revision"], rev)


class TestLaneMcpContextChanges(_V2Fixture):
    def test_lane_changes_checkpoint_identity_unknown_and_unavailable(self):
        first = self.plant_context_record(JOB)
        second = self.plant_context_record(JOB2, extra={"id": JOB2})
        rev1 = revision_of(first)
        rev2 = revision_of(second)
        self.plant_v2_config(job_ids=[JOB, JOB2])

        empty = self.assert_v2(
            self.load_query(self.query("lane_changes", {})),
            "lane_changes",
        )
        held_nothing = self.assert_v2(
            self.load_query(self.query("lane_changes", {"checkpoint": {}})),
            "lane_changes",
        )
        self.assertEqual(empty, held_nothing)
        self.assertEqual(empty["state"], "ok")
        self.assertEqual(empty["configured_ids"], [JOB, JOB2])
        self.assertEqual([row["id"] for row in empty["changed"]], [JOB, JOB2])
        self.assertEqual(empty["unchanged"], [])
        self.assertEqual(empty["unknown"], [])
        self.assertEqual(empty["unavailable"], [])
        self.assertEqual(empty["checkpoint"], {JOB: rev1, JOB2: rev2})
        for row in empty["changed"]:
            self.assertEqual(
                set(row),
                {"id", "revision", "recorded_status", "verdict", "evidence"},
            )
            self.assertNotIn("findings", row)
        self.assertNotIn(FINDING, json.dumps(empty))

        mixed = self.assert_v2(
            self.load_query(
                self.query("lane_changes", {"checkpoint": {JOB: rev1}})
            ),
            "lane_changes",
        )
        self.assertEqual(mixed["unchanged"], [JOB])
        self.assertEqual([row["id"] for row in mixed["changed"]], [JOB2])
        self.assertEqual(mixed["changed"][0]["revision"], rev2)

        first.write_bytes(first.read_bytes())
        still = self.assert_v2(
            self.load_query(
                self.query(
                    "lane_changes",
                    {"checkpoint": {JOB: rev1, JOB2: rev2}},
                )
            ),
            "lane_changes",
        )
        self.assertEqual(still["unchanged"], [JOB, JOB2])
        self.assertEqual(still["changed"], [])

        mutated = json.loads(second.read_text(encoding="utf-8"))
        mutated["status"] = "failed"
        second.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
        self.assertNotEqual(revision_of(second), rev2)
        after = self.assert_v2(
            self.load_query(
                self.query(
                    "lane_changes",
                    {"checkpoint": {JOB: rev1, JOB2: rev2}},
                )
            ),
            "lane_changes",
        )
        self.assertEqual(after["unchanged"], [JOB])
        self.assertEqual([row["id"] for row in after["changed"]], [JOB2])
        self.assertEqual(after["checkpoint"][JOB2], revision_of(second))

        self.assert_refusal(
            self.query("lane_changes", {"checkpoint": {JOB_UNLISTED: rev1}}),
            "arguments",
        )
        self.assert_refusal(
            self.query("lane_changes", {"checkpoint": {JOB: "not-a-revision"}}),
            "arguments",
        )

        self.reset_sources()
        self.plant_v2_config(job_ids=[JOB, JOB2])
        missing = self.assert_v2(
            self.load_query(self.query("lane_changes", {})),
            "lane_changes",
        )
        self.assertEqual(missing["state"], "unknown")
        self.assertEqual(missing["reason"], "dispatch store is missing")
        self.assertEqual(missing["changed"], [])
        self.assertEqual(missing["unchanged"], [])
        self.assertEqual(missing["unknown"], [JOB, JOB2])
        self.assertEqual(missing["unavailable"], [])
        self.assertEqual(missing["checkpoint"], {})

        self._plant_bytes(self.store, b"not-a-directory\n")
        blocked = self.assert_v2(
            self.load_query(self.query("lane_changes", {})),
            "lane_changes",
        )
        self.assertEqual(blocked["state"], "unavailable")
        self.assertEqual(blocked["reason"], "dispatch store is unavailable")
        self.assertEqual(blocked["unavailable"], [JOB, JOB2])
        self.assertEqual(blocked["unknown"], [])
        self.assertEqual(blocked["checkpoint"], {})


class TestLaneMcpContextJobs(_V2Fixture):
    def test_lane_jobs_cards_dispatchable_pairs_and_undeclared_name(self):
        jobs = {
            "author-tests": dict(DISPATCHABLE),
            "held-job": {**DISPATCHABLE, "withheld": True, "role": "read"},
            "zero-held": {**DISPATCHABLE, "withheld": 0, "role": "read"},
            "bad-slot": {
                **DISPATCHABLE,
                "prompt": "Use {scope} and {foo}",
            },
            "1nvalid": {"adapter": "harness"},
            "ok-object": "not-an-object",
        }
        self.plant_registry(jobs)
        self.plant_v2_config()
        listing = self.assert_v2(
            self.load_query(self.query("lane_jobs", {})),
            "lane_jobs",
        )
        self.assertEqual(listing["state"], "ok")
        self.assertIsNone(listing["job"])
        self.assertEqual(listing["evidence"]["path"], str(self.work / "jobs.json"))
        self.assertEqual(
            listing["evidence"]["revision"],
            revision_of(self.work / "jobs.json"),
        )
        names = [row["name"] for row in listing["jobs"]]
        self.assertEqual(len(listing["jobs"]), 6)
        self.assertEqual(names[0], "author-tests")
        self.assertEqual(names[1], "held-job")
        self.assertEqual(names[2], "zero-held")
        self.assertEqual(names[3], "bad-slot")
        self.assertIsNone(names[4])
        self.assertIsNone(names[5])
        self.assertNotIn("1nvalid", json.dumps(listing))
        by_name = {row["name"]: row for row in listing["jobs"] if row["name"]}
        self.assertTrue(by_name["author-tests"]["dispatchable"])
        self.assertFalse(by_name["held-job"]["dispatchable"])
        self.assertTrue(by_name["zero-held"]["dispatchable"])
        self.assertFalse(by_name["bad-slot"]["dispatchable"])
        self.assertEqual(by_name["author-tests"]["slots"], ["out", "ref", "scope"])
        for row in listing["jobs"]:
            self.assertEqual(
                set(row),
                {"name", "adapter", "role", "dispatchable", "slots"},
            )
            self.assertFalse(row["dispatchable"] is True and row["name"] is None)
        dumped = json.dumps(listing)
        self.assertNotIn(DISPATCHABLE["prompt"], dumped)
        self.assertNotIn("{scope}", dumped)

        card = self.assert_v2(
            self.load_query(self.query("lane_jobs", {"name": "author-tests"})),
            "lane_jobs",
        )
        self.assertEqual(card["jobs"], [])
        job = card["job"]
        self.assertEqual(job["name"], "author-tests")
        self.assertEqual(job["adapter"], "harness")
        self.assertEqual(job["role"], "write")
        self.assertEqual(job["snapshot"], "whole")
        self.assertTrue(job["dispatchable"])
        self.assertEqual(job["deliverable"], "a red test file")
        self.assertEqual(
            job["constraints"],
            ["do not edit the implementation", "no network"],
        )
        self.assertEqual(job["timeout"], 1800)
        self.assertEqual(
            job["prompt_bytes"],
            len(DISPATCHABLE["prompt"].encode("utf-8")),
        )
        self.assertNotIn("prompt", job)
        self.assertNotIn(DISPATCHABLE["prompt"], json.dumps(card))

        missing = self.assert_v2(
            self.load_query(self.query("lane_jobs", {"name": "no-such-job"})),
            "lane_jobs",
        )
        self.assertEqual(missing["state"], "ok")
        self.assertIsNone(missing["job"])
        self.assertEqual(missing["jobs"], [])
        self.assertEqual(missing["reason"], "job is not declared in the registry")

        self.assert_refusal(
            self.query("lane_jobs", {"name": "Author-tests"}),
            "arguments",
        )
        self.assert_refusal(
            self.query("lane_jobs", {"name": "bad_name"}),
            "arguments",
        )
        self.assertTrue(JOB_NAME_GRAMMAR.match("author-tests"))
        self.assertFalse(JOB_NAME_GRAMMAR.match("Author-tests"))

    def test_lane_jobs_source_boundaries_caps_and_no_default_registry(self):
        self.plant_v2_config(job_registry=None)
        decoy = {
            "author-tests": dict(DISPATCHABLE),
            "adversarial-review": dict(DISPATCHABLE),
        }
        self.plant_registry(decoy, path=self.cwd / "jobs.json")
        tracked = REPO / "ops" / "devlane" / "task" / "jobs.json"
        self.assertTrue(tracked.is_file(), "tracked registry exists in the tree")
        env = {
            "JOB_REGISTRY": str(tracked),
            "LANE_JOB_REGISTRY": str(self.cwd / "jobs.json"),
        }
        disabled = self.assert_v2(
            self.load_query(self.query("lane_jobs", {}, extra_env=env)),
            "lane_jobs",
        )
        self.assertEqual(disabled["state"], "unknown")
        self.assertEqual(disabled["jobs"], [])
        self.assertIsNone(disabled["job"])
        self.assertIsNone(disabled["evidence"]["path"])
        self.assertIsNone(disabled["evidence"]["revision"])
        blob = json.dumps(disabled)
        self.assertNotIn("author-tests", blob)
        self.assertNotIn("adversarial-review", blob)
        self.assertNotIn("implement", blob)

        nested = self.work / "nested" / "jobs.json"
        self.plant_registry({"rel-job": dict(DISPATCHABLE)}, path=nested)
        self.plant_v2_config(job_registry="nested/jobs.json")
        relative = self.assert_v2(
            self.load_query(self.query("lane_jobs", {})),
            "lane_jobs",
        )
        self.assertEqual(relative["state"], "ok")
        self.assertEqual(relative["jobs"][0]["name"], "rel-job")
        self.assertEqual(relative["evidence"]["path"], str(nested))

        many = {f"job-{n:02d}": dict(DISPATCHABLE) for n in range(65)}
        self.assertEqual(len(many), 65)
        self.plant_registry(many)
        self.plant_v2_config()
        overflow = self.assert_v2(
            self.load_query(self.query("lane_jobs", {})),
            "lane_jobs",
        )
        self.assertEqual(overflow["state"], "unavailable")
        self.assertEqual(overflow["reason"], "registry lists more than 64 jobs")
        self.assertEqual(overflow["jobs"], [])

        target = self.scratch / "elsewhere.json"
        self.plant_registry({"sym-job": dict(DISPATCHABLE)}, path=target)
        link = self.work / "jobs.json"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target)
        self.assertTrue(link.is_symlink())
        self.plant_v2_config()
        linked = self.assert_v2(
            self.load_query(self.query("lane_jobs", {})),
            "lane_jobs",
        )
        self.assertEqual(linked["state"], "unavailable")
        self.assertEqual(linked["jobs"], [])
        self.assertNotIn("sym-job", json.dumps(linked))

        self.plant_registry(raw=b"{not-json\n")
        bad = self.assert_v2(
            self.load_query(self.query("lane_jobs", {})),
            "lane_jobs",
        )
        self.assertEqual(bad["state"], "unavailable")
        self.assertEqual(bad["jobs"], [])

        long_path = "p" * 1025
        self.plant_v2_config(job_registry=long_path)
        self.assert_refusal(self.invoke(["check"]), "config")


class TestLaneMcpContextMeta(_V2Fixture):
    def test_request_meta_object_is_ignored_non_object_refused_no_progress(self):
        self.plant_record()
        self.plant_config()
        token = {"progressToken": "tok-aa41-context"}
        cli = self.assert_lane(
            self.load_query(self.query("lane_record", {"id": JOB})),
            "lane_record",
        )
        requests = [
            rpc("ping", 2, {"_meta": token}),
            rpc("tools/list", 3, {"_meta": token}),
            rpc("resources/list", 4, {"_meta": token}),
            rpc(
                "tools/call",
                5,
                {
                    "name": "lane_record",
                    "arguments": {"id": JOB},
                    "_meta": token,
                },
            ),
            rpc(
                "tools/call",
                6,
                {"name": "lane_record", "arguments": {"id": JOB}},
            ),
            rpc(
                "resources/read",
                7,
                {"uri": f"lane://record/{JOB}", "_meta": token},
            ),
            rpc("resources/read", 8, {"uri": f"lane://record/{JOB}"}),
            rpc(
                "tools/call",
                9,
                {
                    "name": "lane_record",
                    "arguments": {"id": JOB, "extra": 1},
                    "_meta": token,
                },
            ),
            rpc("ping", 10, {"_meta": "not-an-object"}),
            rpc("tools/list", 11, {"_meta": ["x"]}),
            rpc("resources/read", 12, {"uri": f"lane://record/{JOB}", "_meta": 1}),
            rpc(
                "initialize",
                13,
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "lane-mcp-oracle", "version": "0"},
                    "_meta": "not-an-object",
                },
            ),
        ]
        init = rpc(
            "initialize",
            1,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "lane-mcp-oracle", "version": "0"},
                "_meta": token,
            },
        )
        proc = self.serve([init, notify("notifications/initialized"), *requests])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("tok-aa41-context", proc.stdout)
        objs = self.rpc_objects(proc)
        self.assertEqual(self.notifications(objs), [])
        self.assertIn("result", self.rpc_by_id(objs, 1))
        self.assertEqual(self.rpc_by_id(objs, 2).get("result"), {})
        listed = [tool["name"] for tool in self.rpc_by_id(objs, 3)["result"]["tools"]]
        self.assertEqual(sorted(listed), sorted(TOOLS))
        with self.subTest("tools-call-with-meta"):
            self.assertEqual(self.lane_from_rpc(self.rpc_by_id(objs, 5)), cli)
        with self.subTest("tools-call-without-meta"):
            self.assertEqual(self.lane_from_rpc(self.rpc_by_id(objs, 6)), cli)
        with self.subTest("resource-read-with-meta"):
            self.assertEqual(self.lane_from_rpc(self.rpc_by_id(objs, 7)), cli)
        with self.subTest("resource-read-without-meta"):
            self.assertEqual(self.lane_from_rpc(self.rpc_by_id(objs, 8)), cli)
        with self.subTest("unknown-argument-still-refuses"):
            extra = self.rpc_by_id(objs, 9)
            self.assertEqual((extra.get("result") or {}).get("isError"), True)
            self.assertIn("expected", self.rpc_error_line(extra))
        for rpc_id, label in (
            (10, "ping-meta-not-object"),
            (11, "tools-list-meta-not-object"),
            (12, "resource-read-meta-not-object"),
            (13, "initialize-meta-not-object"),
        ):
            with self.subTest(label=label):
                obj = self.rpc_by_id(objs, rpc_id)
                self.assertIn("error", obj)
                self.assertEqual(obj["error"]["code"], -32602)


class TestLaneMcpContextSurface(_V2Fixture):
    def test_v2_lists_tools_resources_and_the_jobs_template(self):
        self.plant_context_record()
        self.plant_registry({"author-tests": dict(DISPATCHABLE)})
        self.plant_v2_config(job_ids=[JOB, JOB2])
        proc = self.serve(
            self.handshake(
                [
                    rpc("tools/list", 2),
                    rpc("resources/list", 3),
                    rpc("resources/templates/list", 4),
                    rpc("resources/read", 5, {"uri": "lane://jobs/author-tests"}),
                    rpc("resources/read", 6, {"uri": f"lane://findings/{JOB_UNLISTED}"}),
                    rpc("resources/read", 7, {"uri": f"lane://findings/{JOB}?cursor=1"}),
                ]
            )
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        objs = self.rpc_objects(proc)
        tools = self.rpc_by_id(objs, 2)["result"]["tools"]
        names = [tool["name"] for tool in tools]
        self.assertEqual(sorted(names), sorted(V2_TOOLS))
        self.assertEqual(len(tools), 7)
        by_name = {tool["name"]: tool for tool in tools}
        for name in V2_TOOLS:
            ann = by_name[name]["annotations"]
            self.assertEqual(ann["readOnlyHint"], True)
            self.assertEqual(ann["destructiveHint"], False)
            schema = by_name[name]["inputSchema"]
            self.assertEqual(schema.get("additionalProperties"), False)
        findings_schema = by_name["lane_findings"]["inputSchema"]
        self.assertIn("id", findings_schema.get("required") or [])
        self.assertIn("id", (findings_schema.get("properties") or {}))
        self.assertNotIn(
            "checkpoint",
            by_name["lane_changes"]["inputSchema"].get("required") or [],
        )
        self.assertNotIn(
            "name",
            by_name["lane_jobs"]["inputSchema"].get("required") or [],
        )

        uris = [item["uri"] for item in self.rpc_by_id(objs, 3)["result"]["resources"]]
        self.assertEqual(
            set(uris),
            {
                "lane://brief",
                "lane://alerts",
                "lane://usage",
                f"lane://record/{JOB}",
                f"lane://record/{JOB2}",
                f"lane://findings/{JOB}",
                f"lane://findings/{JOB2}",
                "lane://changes",
                "lane://jobs",
            },
        )
        self.assertNotIn("lane://jobs/author-tests", uris)
        self.assertNotIn(f"lane://findings/{JOB_UNLISTED}", uris)

        templates = self.rpc_by_id(objs, 4)["result"]["resourceTemplates"]
        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["uriTemplate"], "lane://jobs/{name}")
        self.assertEqual(template["name"], "Lane job card")
        self.assertEqual(template["mimeType"], "application/json")

        card = self.lane_from_rpc(self.rpc_by_id(objs, 5))
        self.assertEqual(card["query"], "lane_jobs")
        self.assertEqual(card["job"]["name"], "author-tests")
        for rpc_id in (6, 7):
            err = self.rpc_by_id(objs, rpc_id)
            self.assertEqual(err["error"]["code"], -32602)

    def test_v1_listings_omit_v2_surface_and_templates_stay_not_found(self):
        self.plant_record()
        self.plant_config(job_ids=[JOB])
        proc = self.serve(
            self.handshake(
                [
                    rpc("tools/list", 2),
                    rpc("resources/list", 3),
                    rpc("resources/templates/list", 4),
                    rpc("resources/read", 5, {"uri": f"lane://findings/{JOB}"}),
                    rpc("resources/read", 6, {"uri": "lane://changes"}),
                    rpc("resources/read", 7, {"uri": "lane://jobs"}),
                ]
            )
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        objs = self.rpc_objects(proc)
        names = [tool["name"] for tool in self.rpc_by_id(objs, 2)["result"]["tools"]]
        self.assertEqual(sorted(names), sorted(TOOLS))
        self.assertEqual(len(names), 4)
        uris = [item["uri"] for item in self.rpc_by_id(objs, 3)["result"]["resources"]]
        self.assertEqual(len(uris), 4)
        for uri in (
            f"lane://findings/{JOB}",
            "lane://changes",
            "lane://jobs",
        ):
            self.assertNotIn(uri, uris)
        self.assertEqual(self.rpc_by_id(objs, 4)["error"]["code"], -32601)
        for rpc_id in (5, 6, 7):
            self.assertEqual(self.rpc_by_id(objs, rpc_id)["error"]["code"], -32602)

    def test_cli_tool_resource_parity_on_the_three_v2_reads(self):
        rec = self.plant_context_record()
        self.plant_context_record(JOB2, extra={"id": JOB2})
        self.plant_registry({"author-tests": dict(DISPATCHABLE)})
        self.plant_v2_config(job_ids=[JOB, JOB2])
        before = rec.read_bytes()
        pairs = [
            ("lane_findings", {"id": JOB}, f"lane://findings/{JOB}"),
            ("lane_changes", {}, "lane://changes"),
            ("lane_jobs", {}, "lane://jobs"),
            ("lane_jobs", {"name": "author-tests"}, "lane://jobs/author-tests"),
            ("lane_record", {"id": JOB}, f"lane://record/{JOB}"),
        ]
        cli = {}
        for tool, arguments, _uri in pairs:
            first = self.load_query(self.query(tool, arguments))
            second = self.load_query(self.query(tool, arguments))
            self.assertEqual(first, second, tool)
            self.assert_v2(first, tool)
            self.assertLessEqual(len(json.dumps(first).encode("utf-8")), 16384, tool)
            cli[(tool, json.dumps(arguments, sort_keys=True))] = first
        requests = []
        rpc_id = 20
        for tool, arguments, uri in pairs:
            requests.append(
                rpc("tools/call", rpc_id, {"name": tool, "arguments": arguments})
            )
            rpc_id += 1
            requests.append(rpc("resources/read", rpc_id, {"uri": uri}))
            rpc_id += 1
        proc = self.serve(self.handshake(requests))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        objs = self.rpc_objects(proc)
        replies = [obj for obj in objs if obj.get("id") not in (None, 1)]
        self.assertEqual(len(replies), 10, objs)
        idx = 0
        for tool, arguments, _uri in pairs:
            call_payload = self.lane_from_rpc(replies[idx])
            read_payload = self.lane_from_rpc(replies[idx + 1])
            idx += 2
            expected = cli[(tool, json.dumps(arguments, sort_keys=True))]
            self.assertEqual(call_payload, expected, tool)
            self.assertEqual(read_payload, expected, tool)
        self.assertEqual(rec.read_bytes(), before)
        self.plant_config(job_ids=[JOB, JOB2])
        v1_payload = self.load_query(self.query("lane_record", {"id": JOB}))
        self.plant_v2_config(job_ids=[JOB, JOB2])
        v2_payload = self.load_query(self.query("lane_record", {"id": JOB}))
        self.assertEqual(v1_payload, v2_payload)

    def test_findings_resource_is_first_page_only_and_reads_need_no_identity(self):
        rows = [
            {
                "severity": "p3",
                "where": f"w{n}",
                "claim": f"page-claim-{n}-" + ("Y" * 900),
                "reproduce": None,
            }
            for n in range(1, 9)
        ]
        self.plant_context_record(findings=rows, note="resource-note")
        self.plant_v2_config()
        env = self.env()
        self.assertNotIn("WF_AGENT", env)
        cli_first = self.assert_v2(
            self.load_query(self.query("lane_findings", {"id": JOB})),
            "lane_findings",
        )
        self.assertTrue(cli_first["page"]["more"])
        proc = self.serve(
            self.handshake(
                [rpc("resources/read", 2, {"uri": f"lane://findings/{JOB}"})]
            )
        )
        resource = self.lane_from_rpc(self.rpc_by_id(self.rpc_objects(proc), 2))
        self.assertEqual(resource, cli_first)
        self.assertEqual(resource["note"], "resource-note")
        self.assertEqual(resource["page"]["next_cursor"], cli_first["page"]["next_cursor"])
        continued = self.assert_v2(
            self.load_query(
                self.query(
                    "lane_findings",
                    {"id": JOB, "cursor": cli_first["page"]["next_cursor"]},
                )
            ),
            "lane_findings",
        )
        self.assertNotEqual(continued["findings"], resource["findings"])
        self.assertIsNone(continued["note"])


if __name__ == "__main__":
    import unittest

    unittest.main()
