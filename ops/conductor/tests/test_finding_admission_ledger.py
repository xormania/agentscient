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
# FINDING-ADMISSION.md / task CONTRACT.md: dispatch, replay and the
# ledger consume the same semantic validator (ops/devlane/task/envelope.py).
VALIDATOR = REPO / "ops" / "devlane" / "task" / "envelope.py"
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
        self.assertTrue(VALIDATOR.is_file(), f"{VALIDATOR} is missing")
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
        self.validator = self.repo / "ops" / "devlane" / "task" / "envelope.py"
        self._stage_declared_dependencies()
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

    def _stage_declared_dependencies(self) -> None:
        # Copy declared runtime counterparts as bytes. Do not inspect them.
        tool = TOOL.read_bytes()
        self.staged.parent.mkdir(parents=True, exist_ok=True)
        self.staged.write_bytes(tool)
        self.assertEqual(self.staged.read_bytes(), tool)
        self.assertNotEqual(self.staged.read_bytes(), ABSENT_STUB)
        validator = VALIDATOR.read_bytes()
        self._plant_bytes(self.validator, validator)
        self.assertNotEqual(self.validator.read_bytes(), ABSENT_STUB)
        self.assertNotEqual(self.validator.read_bytes(), tool)

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

    def assert_refusal(self, proc, class_name: str | None = None) -> None:
        err = proc.stderr or ""
        self.assertEqual(proc.returncode, 2, err)
        self.assertEqual((proc.stdout or "").strip(), "")
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, f"refusal must be one line: {err!r}")
        line = lines[0]
        if class_name is not None:
            head = line.split(":", 1)[0].strip().lower().replace("_", "-")
            self.assertEqual(head, class_name, line)
        lower = line.lower()
        for word in ("expected", "found", "needed"):
            self.assertIn(word, lower, err)

    def _plant_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        landed = path.read_bytes()
        self.assertEqual(landed, data, f"plant did not land intact: {path}")
        self.assertTrue(path.is_file(), path)

    def dispatch_job_dir(self, record_id: str) -> Path:
        path = (
            self.home
            / ".local"
            / "state"
            / "agentscient"
            / "dispatch"
            / record_id
        )
        (path / "in").mkdir(parents=True, exist_ok=True)
        (path / "out").mkdir(parents=True, exist_ok=True)
        return path

    def retain_owner_scope(self, record_id: str) -> dict[str, str]:
        path = self.dispatch_job_dir(record_id) / "in" / "owner-scope.md"
        data = self.scope_text.encode("utf-8")
        self._plant_bytes(path, data)
        digest = sha256_bytes(data)
        self.assertEqual(digest, self.scope_sha256, path)
        return {"path": str(path), "sha256": digest}

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
        harness: str = "grok",
        model_ran: str = "grok-4.6",
        role: str | None = None,
        stage: str | None = None,
        extra_inputs: list[tuple[str, bytes]] | None = None,
        extra_outputs: list[tuple[str, bytes]] | None = None,
    ) -> Path:
        if role is None:
            role = "write" if job == "implement" else "read"
        if stage is None:
            stage = "code" if job == "implement" else "review"
        job_dir = self.dispatch_job_dir(record_id)
        scope_input = self.retain_owner_scope(record_id)
        inputs = [scope_input]
        for name, data in extra_inputs or []:
            self.assertNotEqual(name, "owner-scope.md", name)
            dest = job_dir / "in" / name
            self._plant_bytes(dest, data)
            inputs.append({"path": str(dest), "sha256": sha256_bytes(data)})
        stream_path = job_dir / "home" / harness / "sessions" / "stream.json"
        stream = (canonical_json({"model": model_ran}) + "\n").encode("utf-8")
        self._plant_bytes(stream_path, stream)
        artifacts: dict[str, str] = {}
        for name, data in extra_outputs or []:
            dest = job_dir / "out" / name
            self._plant_bytes(dest, data)
            artifacts[Path(name).stem.lower()] = str(dest)
        if "raw" not in artifacts:
            report = job_dir / "out" / "REPORT.md"
            report_text = note or f"synthetic report for {record_id}\n"
            self._plant_bytes(report, report_text.encode("utf-8"))
            artifacts["raw"] = str(report)
        envelope = {
            "job": job,
            "status": status,
            "verdict": verdict,
            "counts": {
                "p1": sum(1 for item in findings if item.get("severity") == "p1"),
                "p2": sum(1 for item in findings if item.get("severity") == "p2"),
                "p3": sum(1 for item in findings if item.get("severity") == "p3"),
                "opinions": sum(
                    1 for item in findings if item.get("reproduce") is None
                ),
            },
            "findings": findings,
            "artifacts": artifacts,
            "spend": {"harness": harness, "total": 0, "out": 0, "runs": 0},
            "stamp": {"ref": ref, "started": None, "ended": None},
            "note": note,
        }
        rec = {
            "id": record_id,
            "lane": "dev",
            "stage": stage,
            "unit": "lane/agy-worker",
            "lineage": {"branch": "lane/agy-worker", "base_sha": ref},
            "follows": [],
            "job": job,
            "role": role,
            "dispatched_by": AGENT,
            "at": {
                "launched": "2026-09-08T06:00:00Z",
                "closed": "2026-09-08T06:01:00Z",
            },
            "snapshot": {
                "mode": "whole",
                "ref_name": ref,
                "ref_sha": ref,
                "behind_tip": 0,
                "root": str(job_dir / "snapshot"),
            },
            "harness": {
                "name": harness,
                "isolation": {
                    "mechanism": "home",
                    "observed": {
                        "unresolved": "behavioural probe has not run",
                    },
                    "home": str(job_dir / "home" / harness),
                },
                "sandbox": "always-approve",
                "containment": "policy",
                "argv": [harness],
            },
            "model": {
                "requested": model_ran,
                "effort_requested": None,
                "effort_argv": [],
                "ran": model_ran,
                "read_from": str(stream_path),
            },
            "session": {
                "id": "00000000-0000-4000-8000-000000000001",
                "stream": str(stream_path),
                "stream_sha256_at_close": sha256_bytes(stream),
            },
            "brief": {
                "template": {
                    "path": "ops/devlane/task/jobs.json",
                    "sha256": "c" * 64,
                },
                "scope": self.scope_text,
                "inputs": inputs,
                "sha256": self.scope_sha256,
                "bytes": len(self.scope_text.encode("utf-8")),
            },
            "caps": {"cap-out": 500000, "source": "wires.py"},
            "overrides": [],
            "attempts": [],
            "result": {"envelope": envelope},
            "status": "closed",
        }
        path = self.records / f"{record_id}.json"
        text = json.dumps(rec, indent=2) + "\n"
        self._plant_bytes(path, text.encode("utf-8"))
        landed = path.read_text(encoding="utf-8")
        self.assertEqual(landed, text)
        self.assertIn(record_id, landed)
        self.assertIn(self.scope_sha256, landed)
        self.assertIn(scope_input["path"], landed)
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
        planted_keys = [f"{REC}#{index}" for index in range(1, len(findings) + 1)]
        admitted_keys = [item["key"] for item in body["admitted"]]
        held_keys = [item["key"] for item in body["held"]]
        self.assertEqual(admitted_keys, planted_keys[:1])
        self.assertEqual(held_keys, planted_keys[1:])
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
        # FINDING-ADMISSION.md: correction sources are check-tests,
        # security-audit, adversarial-review, and adjudication against
        # those keys. A generic review job has no correction authority.
        # The selected batch may contain only those jobs; do not require
        # successful selection of an unsupported job.
        row = self.sample_row("agy-live-output-test")
        finding = self._finding_from(row, evaluate=True)
        rec = row["record"]
        key = f"{rec}#1"
        self.plant_record(
            rec,
            [finding],
            job="review",
            ref=row["snapshot_ref"],
        )
        self.assertEqual(self.invoke(["import"]).returncode, 0)
        proc = self.corrections(rec, ref=row["snapshot_ref"])
        self.assertEqual(
            finding["evaluation"]["classification"],
            "demonstrated-defect",
        )
        if proc.returncode == 0:
            body = json.loads(proc.stdout)
            admitted_keys = [item["key"] for item in body["admitted"]]
            self.assertNotIn(key, admitted_keys)
        else:
            self.assert_refusal(proc)

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
        artifact_id = "20260908T060000Z-code-codex-a1fc01"
        review_path = self.plant_record(
            REC,
            [original],
            harness="claude",
            model_ran="claude-opus-4-6",
        )
        artifact_path = self.plant_record(
            artifact_id,
            [],
            job="implement",
            verdict=None,
            harness="codex",
            model_ran="gpt-5.4",
        )
        review_report = self.dispatch_job_dir(REC) / "out" / "REPORT.md"
        self.assertTrue(review_report.is_file(), review_report)
        ruling_text = f"## {REC}#1 — PARTIAL\n\n{subclaim}\n"
        adj_path = self.plant_record(
            adj_id,
            [adj],
            job="adjudicate",
            harness="grok",
            model_ran="grok-4.6",
            extra_inputs=[
                ("artifact-producer.json", artifact_path.read_bytes()),
                ("finding-producer.json", review_path.read_bytes()),
                ("original-report.md", review_report.read_bytes()),
                ("supplied-keys.txt", f"{REC}#1\n".encode("utf-8")),
            ],
            extra_outputs=[("RULING.md", ruling_text.encode("utf-8"))],
        )
        adj_rec = json.loads(adj_path.read_text(encoding="utf-8"))
        review_rec = json.loads(review_path.read_text(encoding="utf-8"))
        artifact_rec = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(review_rec["harness"]["name"], "claude")
        self.assertEqual(artifact_rec["harness"]["name"], "codex")
        self.assertEqual(adj_rec["harness"]["name"], "grok")
        self.assertNotEqual(
            adj_rec["harness"]["name"],
            review_rec["harness"]["name"],
        )
        self.assertNotEqual(
            adj_rec["harness"]["name"],
            artifact_rec["harness"]["name"],
        )
        self.assertIsNotNone(review_rec["model"]["ran"])
        self.assertIsNotNone(artifact_rec["model"]["ran"])
        self.assertIsNotNone(adj_rec["model"]["ran"])
        self.assertIsNotNone(review_rec["model"]["read_from"])
        self.assertIsNotNone(artifact_rec["model"]["read_from"])
        self.assertIsNotNone(adj_rec["model"]["read_from"])
        input_names = [Path(item["path"]).name for item in adj_rec["brief"]["inputs"]]
        self.assertEqual(
            set(input_names),
            {
                "owner-scope.md",
                "artifact-producer.json",
                "finding-producer.json",
                "original-report.md",
                "supplied-keys.txt",
            },
        )
        ruling_file = Path(adj_rec["result"]["envelope"]["artifacts"]["ruling"])
        self.assertEqual(ruling_file.read_text(encoding="utf-8"), ruling_text)
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
        # Import-stage decode class is unnamed; corrections-stage is admission-evidence.
        if imported.returncode != 0:
            self.assert_refusal(imported)
            return
        proc = self.corrections(REC)
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
        scope_input = self.retain_owner_scope(REC)
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
            "brief": {
                "template": {
                    "path": "ops/devlane/task/jobs.json",
                    "sha256": "c" * 64,
                },
                "scope": self.scope_text,
                "inputs": [scope_input],
                "sha256": self.scope_sha256,
                "bytes": len(self.scope_text.encode("utf-8")),
            },
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
            # Import-stage decode class is unnamed; do not invent admission-evidence.
            self.assert_refusal(imported)


if __name__ == "__main__":
    unittest.main()
