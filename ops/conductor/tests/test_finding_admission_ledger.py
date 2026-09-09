"""Finding-admission ledger: import, dispute, corrections projection.

Written from ops/devlane/task/FINDING-ADMISSION.md. findings.py is the
subject and is not read here. Tests invoke a staged copy with HOME at a
scratch git repo. The live store must stay untouched.

Intended reds: `dispute` and `corrections` are unknown verbs (class
arguments); export has no evaluations/disputes arrays; mixed filtering
and incomplete/legacy refusals do not exist yet. Nearby valids use the
existing import/export verbs. A TypeError or missing file is not a red.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "ops" / "conductor" / "tools" / "findings.py"
FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "finding_admission"
    / "agy-sample-classifications.json"
)
LIVE_STORE = Path.home() / ".local" / "state" / "agentscient" / "findings.db"
AGENT = "Admission Tester <admission-tester@example.invalid>"
RUN_CAP = 30
REF = "fc9ad2c015d47c85b405018521b57fa57e212d90"
REC = "20260908T063559Z-review-claude-6eb510"
ABSENT_STUB = (
    b'"""Absent-tool stand-in: exit 0, no output."""\n'
    b"import sys\n"
    b"sys.exit(0)\n"
)


def _live_snapshot() -> tuple[str, bytes | None]:
    if LIVE_STORE.is_file():
        return ("file", LIVE_STORE.read_bytes())
    if LIVE_STORE.exists():
        return ("other", None)
    return ("absent", None)


def canonical_json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def finding_sha256(finding: dict) -> str:
    return sha256_text(canonical_json(finding))


class _LedgerFixture(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TOOL.is_file(), f"{TOOL} is missing")
        self.assertTrue(FIXTURE.is_file(), f"{FIXTURE} is missing")
        self._live_before = _live_snapshot()
        self._tmp = tempfile.TemporaryDirectory(prefix="finding-admission-")
        root = Path(self._tmp.name)
        self.home = root / "home"
        self.repo = root / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        self.store = (
            self.home / ".local" / "state" / "agentscient" / "findings.db"
        )
        self.assertFalse(self.store.exists())
        self.records = self.repo / ".dev" / "records" / "dispatches"
        self.records.mkdir(parents=True)
        self.staged = self.repo / "ops" / "conductor" / "tools" / "findings.py"
        self.staged.parent.mkdir(parents=True, exist_ok=True)
        data = TOOL.read_bytes()
        self.staged.write_bytes(data)
        self.assertEqual(self.staged.read_bytes(), data)
        self.assertNotEqual(self.staged.read_bytes(), ABSENT_STUB)
        self.sample = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.scope_text = self.sample["agreed_scope"]["text"]
        self.scope_sha256 = sha256_text(self.scope_text)
        self._git_init()

    def tearDown(self):
        try:
            self.assertEqual(
                _live_snapshot(),
                self._live_before,
                f"live store mutated: {LIVE_STORE}",
            )
        finally:
            self._tmp.cleanup()

    def _git_init(self) -> None:
        proc = subprocess.run(
            ["git", "init", "-b", "dev"],
            cwd=str(self.repo),
            env=self.env(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        (self.repo / "README").write_text("scratch\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "README"],
            cwd=str(self.repo),
            env=self.env(),
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Scratch Owner",
                "-c",
                "user.email=scratch-owner@example.invalid",
                "commit",
                "-m",
                "seed\n",
            ],
            cwd=str(self.repo),
            env=self.env(),
            capture_output=True,
            check=False,
        )

    def env(self, *, agent: str | None = AGENT) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        if agent is not None:
            env["WF_AGENT"] = agent
        return env

    def invoke(self, argv: list[str], *, agent: str | None = AGENT):
        env = self.env(agent=agent)
        if agent is None:
            self.assertNotIn("WF_AGENT", env)
        return subprocess.run(
            [sys.executable, str(self.staged), *argv],
            cwd=str(self.repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=RUN_CAP,
        )

    def assert_refusal(self, proc, class_name: str) -> None:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err)
        self.assertEqual((proc.stdout or "").strip(), "")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        line = lines[0]
        head = line.split(":", 1)[0].strip().lower().replace("_", "-")
        self.assertEqual(head, class_name, line)
        lower = line.lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, err)

    def _eval_for(self, row: dict) -> dict:
        evidence = None
        if row["evidence_kind"] == "reproduction":
            evidence = {
                "kind": "reproduction",
                "details": "recorded: " + row["reproduce"],
            }
        elif row["evidence_kind"] == "execution-path":
            evidence = {
                "kind": "execution-path",
                "details": row["justification"],
            }
        return {
            "classification": row["classification"],
            "scope_sha256": self.scope_sha256,
            "requirement": row["requirement"],
            "trigger": row["trigger"],
            "failure": row["failure"],
            "evidence": evidence,
            "refutation": row["unavailable"],
            "source": None,
            "ruling": None,
        }

    def _finding_from(self, row: dict, *, evaluate: bool) -> dict:
        finding = {
            "severity": row["severity"],
            "where": row["where"],
            "claim": row["claim"],
            "reproduce": row["reproduce"],
        }
        if evaluate:
            finding["evaluation"] = self._eval_for(row)
        return finding

    def plant_record(
        self,
        record_id: str,
        findings: list[dict],
        *,
        job: str = "adversarial-review",
        status: str = "ok",
        verdict: str = "changes",
        ref: str = REF,
        note: str | None = None,
    ) -> Path:
        envelope = {
            "job": job,
            "status": status,
            "verdict": verdict,
            "counts": {
                "p1": sum(1 for item in findings if item["severity"] == "p1"),
                "p2": sum(1 for item in findings if item["severity"] == "p2"),
                "p3": sum(1 for item in findings if item["severity"] == "p3"),
                "opinions": sum(
                    1 for item in findings if item.get("reproduce") is None
                ),
            },
            "findings": findings,
            "artifacts": {"raw": "/tmp/admission-raw"},
            "spend": {"harness": "grok", "total": 0, "out": 0, "runs": 0},
            "stamp": {"ref": ref, "started": None, "ended": None},
            "note": note,
        }
        rec = {
            "id": record_id,
            "lane": "dev",
            "stage": "review",
            "unit": "lane/agy-worker",
            "job": job,
            "role": "read",
            "status": "closed",
            "harness": {"name": "grok"},
            "model": {"ran": "grok-4.6"},
            "snapshot": {"ref_sha": ref},
            "result": {"envelope": envelope},
        }
        path = self.records / f"{record_id}.json"
        text = json.dumps(rec, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, text)
        self.assertIn(record_id, landed)
        return path

    def sample_row(self, item_id: str) -> dict:
        matched = [row for row in self.sample["findings"] if row["id"] == item_id]
        self.assertEqual(len(matched), 1, item_id)
        return matched[0]

    def export_rows(self) -> list[dict]:
        proc = self.invoke(["export"], agent=None)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = []
        for line in (proc.stdout or "").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def corrections(self, *records: str, ref: str = REF):
        return self.invoke(
            [
                "corrections",
                "--ref",
                ref,
                "--scope-sha256",
                self.scope_sha256,
                *records,
            ],
            agent=None,
        )


class ImportRetainsEvaluations(_LedgerFixture):
    def test_legacy_import_round_trips_without_inventing_evaluation(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=False)
        self.assertNotIn("evaluation", finding)
        self.plant_record(REC, [finding])
        proc = self.invoke(["import"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        exported = self.export_rows()
        self.assertGreaterEqual(len(exported), 1, exported)
        keys = [item["key"] for item in exported]
        self.assertIn(f"{REC}#1", keys)
        match = [item for item in exported if item["key"] == f"{REC}#1"]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]["claim"], row["claim"])
        self.assertEqual(match[0].get("evaluations") or [], [])

    def test_import_retains_an_evaluated_finding(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(REC, [finding])
        proc = self.invoke(["import"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        match = [item for item in self.export_rows() if item["key"] == f"{REC}#1"]
        self.assertEqual(len(match), 1, match)
        self.assertIn(
            "evaluations",
            match[0],
            "export dropped evaluations; found keys "
            + ",".join(sorted(match[0])),
        )
        events = match[0]["evaluations"]
        self.assertEqual(len(events), 1, events)
        self.assertEqual(events[0]["record"], REC)
        self.assertEqual(events[0]["n"], 1)
        self.assertEqual(
            events[0]["evaluation"]["classification"],
            "demonstrated-defect",
        )
        self.assertEqual(events[0]["evaluation"]["scope_sha256"], self.scope_sha256)


class CorrectionsFiltersAdmitted(_LedgerFixture):
    def test_mixed_sample_admits_defects_and_holds_unproven(self):
        rows = [
            self.sample_row("agy-closure"),
            self.sample_row("agy-fallthrough"),
            self.sample_row("agy-unverified-flags"),
        ]
        findings = [self._finding_from(row, evaluate=True) for row in rows]
        self.assertEqual(
            [item["evaluation"]["classification"] for item in findings],
            ["demonstrated-defect", "unproven", "unproven"],
        )
        self.plant_record(REC, findings)
        imported = self.invoke(["import"])
        self.assertEqual(imported.returncode, 0, imported.stderr)
        proc = self.corrections(REC)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual(
            set(body),
            {"ref", "scope_sha256", "admitted", "held"},
        )
        self.assertEqual(body["ref"], REF)
        self.assertEqual(body["scope_sha256"], self.scope_sha256)
        admitted_keys = [item["key"] for item in body["admitted"]]
        held_keys = [item["key"] for item in body["held"]]
        self.assertEqual(admitted_keys, [f"{REC}#1"])
        self.assertEqual(held_keys, [f"{REC}#7", f"{REC}#8"])
        self.assertEqual(
            body["admitted"][0]["evaluation"]["classification"],
            "demonstrated-defect",
        )
        self.assertEqual(
            {item["reason"] for item in body["held"]},
            {"unproven"},
        )
        self.assertNotEqual(
            rows[0]["old_verdict"],
            "approve",
            "old changes verdict is not the admission label",
        )

    def test_empty_admitted_is_still_exit_zero(self):
        row = self.sample_row("agy-unverified-flags")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(REC, [finding], verdict="approve")
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual(body["admitted"], [])
        self.assertEqual(len(body["held"]), 1)
        self.assertEqual(body["held"][0]["reason"], "unproven")

    def test_a_review_job_does_not_acquire_correction_authority(self):
        row = self.sample_row("agy-live-output-test")
        finding = self._finding_from(row, evaluate=True)
        rec = row["record"]
        self.plant_record(
            rec,
            [finding],
            job="review",
            ref=row["snapshot_ref"],
        )
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(rec, ref=row["snapshot_ref"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        admitted_keys = [item["key"] for item in body["admitted"]]
        self.assertNotIn(f"{rec}#1", admitted_keys)
        self.assertEqual(
            finding["evaluation"]["classification"],
            "demonstrated-defect",
        )

    def test_partial_ruling_admits_only_the_subclaim(self):
        original = self._finding_from(self.sample_row("agy-closure"), evaluate=True)
        original_hash = finding_sha256(original)
        subclaim = "WORKER_HARNESSES undeclared-read against closure(); not EXECUTABLE_* unread"
        ruling = dict(original["evaluation"])
        ruling.update(
            {
                "failure": subclaim,
                "source": {"key": f"{REC}#1", "sha256": original_hash},
                "ruling": "PARTIAL",
            },
        )
        adj = {
            "severity": "p2",
            "where": original["where"],
            "claim": "PARTIAL. " + subclaim,
            "reproduce": original["reproduce"],
            "evaluation": ruling,
        }
        adj_id = "20260908T065000Z-adjudicate-grok-c2ae09"
        self.plant_record(REC, [original])
        self.plant_record(adj_id, [adj], job="adjudicate")
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC, adj_id)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual([item["key"] for item in body["admitted"]], [f"{REC}#1"])
        self.assertEqual(body["admitted"][0]["evaluation"]["failure"], subclaim)
        self.assertEqual(body["admitted"][0]["evaluation"]["ruling"], "PARTIAL")
        self.assertEqual([item["key"] for item in body["held"]], [])


class CorrectionsRefuses(_LedgerFixture):
    def test_legacy_missing_evaluation_refuses_admission_evidence(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=False)
        self.plant_record(REC, [finding])
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC)
        self.assert_refusal(proc, "admission-evidence")

    def test_incomplete_review_refuses_admission_incomplete(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(
            REC,
            [finding],
            status="invalid",
            verdict=None,
            note="review stopped before self-evaluation finished",
        )
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC)
        self.assert_refusal(proc, "admission-incomplete")

    def test_duplicate_batch_records_refuse_admission_binding(self):
        row = self.sample_row("agy-closure")
        self.plant_record(REC, [self._finding_from(row, evaluate=True)])
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC, REC)
        self.assert_refusal(proc, "admission-binding")

    def test_ref_mismatch_refuses_admission_binding(self):
        row = self.sample_row("agy-closure")
        self.plant_record(REC, [self._finding_from(row, evaluate=True)])
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(REC, ref="0" * 40)
        self.assert_refusal(proc, "admission-binding")

    def test_malformed_evidence_refuses_admission_evidence(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        finding["evaluation"]["evidence"] = {
            "kind": "hearsay",
            "details": "someone said so",
        }
        self.plant_record(REC, [finding])
        imported = self.invoke(["import"])
        proc = self.corrections(REC)
        if imported.returncode != 0:
            self.assert_refusal(imported, "admission-evidence")
            return
        self.assert_refusal(proc, "admission-evidence")

    def test_nearby_valid_corrections_still_admits_the_defect(self):
        row = self.sample_row("agy-executable-identity")
        finding = self._finding_from(row, evaluate=True)
        rec = row["record"]
        self.plant_record(
            rec,
            [finding],
            job="security-audit",
            ref=row["snapshot_ref"],
        )
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(rec, ref=row["snapshot_ref"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout)
        self.assertEqual([item["key"] for item in body["admitted"]], [f"{rec}#1"])


class DisputeHolds(_LedgerFixture):
    def test_dispute_prints_key_tab_disputed_and_holds_corrections(self):
        row = self.sample_row("agy-closure")
        finding = self._finding_from(row, evaluate=True)
        self.plant_record(REC, [finding])
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        key = f"{REC}#1"
        proc = self.invoke(["dispute", key, "counter-evidence: closure did not run"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, f"{key}\tdisputed\n")
        held = self.corrections(REC)
        self.assertEqual(held.returncode, 0, held.stderr)
        body = json.loads(held.stdout)
        self.assertEqual(body["admitted"], [])
        self.assertEqual(body["held"][0]["key"], key)
        self.assertEqual(body["held"][0]["reason"], "disputed")

    def test_dispute_without_identity_refuses_identity(self):
        proc = self.invoke(
            ["dispute", f"{REC}#1", "counter-evidence"],
            agent=None,
        )
        self.assert_refusal(proc, "identity")


class DuplicateJsonMembersRefuse(_LedgerFixture):
    def test_duplicate_evaluation_members_refuse_before_dict_collapse(self):
        row = self.sample_row("agy-unverified-flags")
        finding = self._finding_from(row, evaluate=True)
        rec = {
            "id": REC,
            "lane": "dev",
            "stage": "review",
            "unit": "lane/agy-worker",
            "job": "adversarial-review",
            "role": "read",
            "status": "closed",
            "harness": {"name": "grok"},
            "model": {"ran": "grok-4.6"},
            "snapshot": {"ref_sha": REF},
            "result": {
                "envelope": {
                    "job": "adversarial-review",
                    "status": "ok",
                    "verdict": "changes",
                    "counts": {
                        "p1": 0,
                        "p2": 0,
                        "p3": 1,
                        "opinions": 0,
                    },
                    "findings": [finding],
                    "artifacts": {"raw": "/tmp/admission-raw"},
                    "spend": {
                        "harness": "grok",
                        "total": 0,
                        "out": 0,
                        "runs": 0,
                    },
                    "stamp": {"ref": REF, "started": None, "ended": None},
                    "note": None,
                }
            },
        }
        text = json.dumps(rec, indent=2)
        planted = text.replace(
            '"classification": "unproven"',
            '"classification": "unproven", "classification": "demonstrated-defect"',
            1,
        )
        self.assertIn('"classification": "unproven"', planted)
        self.assertIn('"classification": "demonstrated-defect"', planted)
        self.assertGreater(planted.count('"classification"'), 1)
        collapsed = json.loads(planted)
        collapsed_class = collapsed["result"]["envelope"]["findings"][0][
            "evaluation"
        ]["classification"]
        self.assertEqual(collapsed_class, "demonstrated-defect")
        path = self.records / f"{REC}.json"
        path.write_text(planted + "\n", encoding="utf-8")
        imported = self.invoke(["import"])
        if imported.returncode == 0:
            proc = self.corrections(REC)
            self.assert_refusal(proc, "admission-evidence")
            exported = [
                item for item in self.export_rows() if item["key"] == f"{REC}#1"
            ]
            self.assertEqual(len(exported), 1)
            self.assertNotEqual(
                exported[0]["evaluations"][0]["evaluation"]["classification"],
                "demonstrated-defect",
                "last-writer-wins duplicate must not admit a defect",
            )
        else:
            self.assert_refusal(imported, "admission-evidence")


if __name__ == "__main__":
    unittest.main()
