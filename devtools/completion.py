"""Proof-backed completion boundaries over existing reports, artifacts and Jev telemetry."""

from __future__ import annotations

import json
import math

from .advice import Advice, digest
from .artifacts import Artifacts
from .assignments import snapshot
from .commands import Commands
from .configuration import resolve
from .control import Control, binding, includes
from .jev import JevUnavailable
from .role_packages import adapter, names_for_adapter
from .store import canonical
from .telemetry import clean
from .work import record

FIELDS = ("objective", "done_when", "constraints")
BOUNDARIES = {"assignment", "job", "work_order"}


def requirements(row):
    return {key: row.get(key, "") for key in FIELDS}


class Completion:
    def __init__(self, store, member):
        self.store, self.member = store, member
        self.control = Control(store, member)
        self.artifacts = Artifacts(store, member)

    def settings(self, boundary, job=None, assignment=None):
        """Resolve only trusted role/job identities, including disabled gate receipts."""
        scope = self.control.current()
        with self.store.connect() as db:
            if not scope or scope != binding(db, self.member) or scope["paused"] or adapter(scope["role"]) not in {"xo", "nco"}:
                raise ValueError("Completion requires the current active execution officer.")
            if boundary == "assignment":
                ident = assignment["id"] if isinstance(assignment, dict) else assignment
                assigned = record(db, "role_assignments", ident)
                if assigned["work_order"] != scope["work_order"]:
                    raise ValueError("The completion assignment is outside current work.")
                team = {self.member, *(r["member"] for r in Commands._descendants(db, scope))}
                if assigned["job"] is None and assigned["created_by"] not in team:
                    raise ValueError("The completion assignment is outside the current command team.")
                job = assigned["job"]
            if job is not None:
                work = record(db, "jobs", job)
                if not includes(scope, work["work_order"], job) or not Commands._owns_job(db, scope, work):
                    raise ValueError("The completion job is outside current work.")
            if boundary == "job" and job is None or boundary == "work_order" and (job is not None or adapter(scope["role"]) != "xo"):
                raise ValueError("Select the existing job or XO work-order boundary.")
        return resolve(self.store, role=scope["role"], job=job), digest(scope)

    def collect(self, boundary, job, assignment, revision, mechanical):
        scope = self.control.current()
        with self.store.connect() as db:
            if not scope or scope != binding(db, self.member) or scope["paused"] or adapter(scope["role"]) not in {"xo", "nco"}:
                raise ValueError("Completion requires the current active execution officer.")
            order = record(db, "work_orders", scope["work_order"])
            team = {self.member, *(r["member"] for r in Commands._descendants(db, scope))}
            if boundary == "work_order" and db.execute("SELECT 1 FROM member_bindings WHERE work_order=? AND role IN (SELECT value FROM json_each(?)) AND member!=?", (order["id"], canonical(names_for_adapter("xo")), self.member)).fetchone():
                raise ValueError("Completion requires owner-level coordination across independent command teams.")
            if boundary == "assignment":
                ident = assignment["id"] if isinstance(assignment, dict) else assignment
                assigned = record(db, "role_assignments", ident)
                job = assigned["job"]
                if assigned["work_order"] != order["id"]:
                    raise ValueError("The completion assignment is outside current work.")
            else:
                assigned = None
            work = record(db, "jobs", job) if job is not None else None
            if work and (not includes(scope, work["work_order"], job) or not Commands._owns_job(db, scope, work)):
                raise ValueError("The completion job is outside current work.")
            if boundary == "job" and not work or boundary == "work_order" and (job is not None or adapter(scope["role"]) != "xo"):
                raise ValueError("Select the existing job or XO work-order boundary.")
            target = json.loads(assigned["brief"]) if assigned else work if work else order
            target = requirements(target)
            if not target["objective"] or not target["done_when"]:
                raise ValueError("Completion requires the original objective and completion conditions.")
            clause, args = "work_order=?", [order["id"]]
            if boundary != "work_order":
                clause += " AND job IS ?"
                args.append(job)
            assignments = [dict(r) for r in db.execute("SELECT * FROM role_assignments WHERE " + clause + " ORDER BY id", args)]
            assignments = [r for r in assignments if r["job"] is not None or r["created_by"] in team]
            if assigned:
                assignments = [assigned]
            scopes = [dict(r) for r in db.execute("SELECT * FROM member_bindings WHERE " + clause + " ORDER BY member", args)]
            scopes = [r for r in scopes if r["member"] in team]
            if assigned:
                scopes = [r for r in scopes if r.get("assignment_id") == assigned["id"]]
                if assigned["status"] == "active" and not scopes or assigned["job"] is None and assigned["created_by"] not in team:
                    raise ValueError("The completion assignment is outside the current command team.")
            reports = {}
            for current in scopes:
                for row in db.execute("SELECT * FROM work_updates WHERE actor=? AND work_order=? AND job IS ? AND kind='result' ORDER BY id DESC", (current["member"], order["id"], current["job"])):
                    if row["binding"] and json.loads(row["binding"]) == snapshot(current):
                        reports[row["id"]] = dict(row)
                        break
            for item in assignments:
                if item["status"] == "done" and item["result_update"]:
                    row = record(db, "work_updates", item["result_update"])
                    reports[row["id"]] = row
            rows = [dict(r) for r in db.execute("SELECT * FROM operations WHERE " + clause + " ORDER BY id DESC", args)]
            retained_members = {r["actor"] for r in reports.values()}
            rows = [r for r in rows if r["job"] is not None or r["member"] in team or r["member"] in retained_members]
            if assigned:
                identities = {canonical(snapshot(r)) for r in scopes}
                identities.update(r["binding"] for r in reports.values() if r["binding"])
                rows = [r for r in rows if canonical(snapshot(json.loads(r["binding"]))) in identities]
            if boundary == "work_order":
                if any(not Commands._owns_job(db, scope, dict(r)) for r in db.execute("SELECT * FROM jobs WHERE work_order=?", (order["id"],))):
                    raise ValueError("Completion requires owner-level coordination across independent command teams.")
            jobs = [dict(r) for r in db.execute("SELECT j.id,j.title,j.objective,j.done_when,j.constraints,j.status,j.updated,d.revision AS accepted_revision FROM jobs j LEFT JOIN deliveries d ON d.job=j.id WHERE j.work_order=? ORDER BY j.id", (order["id"],))] if boundary == "work_order" else []
            accepted_revisions = {r["id"]: r["accepted_revision"] for r in jobs if r["accepted_revision"]}
        operations, checks, artifact_ids, measured, seen = [], {}, {r["artifact"] for r in reports.values() if r["artifact"]}, {}, set()
        for row in rows:
            result = json.loads(row["result"]) if row["result"] else None
            validation = (result.get("validation") or result) if isinstance(result, dict) else {}
            expected_revision = accepted_revisions.get(row["job"], revision)
            if expected_revision is not None and validation.get("revision") not in {None, expected_revision}:
                continue
            if row["action"] not in {"work_check", "work_submit"}:
                continue
            key = (row["action"], row["arguments"] if row["action"] == "work_check" else None, row["job"])
            if key in seen:
                continue
            seen.add(key)
            if row["state"] in {"queued", "running"}:
                raise ValueError("Completion awaits an active measurement operation.")
            if row["action"] == "work_check" and row["state"] != "completed":
                raise ValueError("Completion needs a completed current measurement; inspect operation:" + str(row["id"]))
            if validation.get("uncommitted"):
                raise ValueError("Completion needs measurements on saved source; the retained check included uncommitted changes.")
            if validation.get("passed") is False and not validation.get("checks"):
                raise ValueError("Completion needs the current retained measurement to pass; inspect operation:" + str(row["id"]))
            # Each named check's latest result wins. A later unrelated check cannot erase a failure.
            for check in validation.get("checks", []):
                name = ("job " + str(row["job"]) + ": " if row["job"] is not None else "") + check["check"]
                if name not in checks:
                    checks[name] = {"exit_code": check["exit_code"], "operation": row["id"]}
                    reference = check.get("evidence")
                    if reference and reference.startswith("artifact:"):
                        artifact = int(reference.split(":")[1])
                        artifact_ids.add(artifact)
                        measured.setdefault(artifact, []).append({"job": row["job"], "revision": validation.get("revision"), "expected_revision": expected_revision})
            compact = {key: validation[key] for key in ("passed", "revision") if key in validation}
            compact["checks"] = [{key: check[key] for key in ("check", "exit_code", "evidence") if key in check} for check in validation.get("checks", [])]
            operations.append({"reference": "operation:" + str(row["id"]), "job": row["job"], "expected_revision": expected_revision, "state": row["state"], "action": row["action"], "measurement": compact, "error": row["error"][:500] if row["error"] else None})
        state = {"boundary": boundary, "target": {"work_order": order["id"], "job": job, "assignment": assigned["id"] if assigned else None}, "requirements": target, "owner": requirements(order),
                 "job": requirements(work) if work else None, "jobs": jobs,
                 "assignment": {"role": assigned["role"], "requirements": target} if assigned else None,
                 "reports": [{"reference": "update:" + str(r["id"]), "text": r["text"], "artifact": "artifact:" + str(r["artifact"]) if r["artifact"] else None} for r in reports.values()],
                 "operations": operations, "mechanical": mechanical or {}, "source_revision": revision}
        identity = digest([scope, order, work, assigned, assignments, list(reports.values()), rows, mechanical, revision])
        return state, sorted(artifact_ids), checks, identity, measured

    def require(self, boundary, *, job=None, assignment=None, revision=None, mechanical=None):
        if boundary not in BOUNDARIES:
            raise ValueError("Unknown completion boundary.")
        parameters = {"boundary": boundary, "job": job, "assignment": assignment["id"] if isinstance(assignment, dict) else assignment,
                      "revision": revision, "mechanical": mechanical}
        config, scope_identity = self.settings(boundary, job, assignment)
        receipt = {"boundary": boundary, "_configuration": config["revision"], "_scope": scope_identity, "_parameters": parameters}
        if not config["features"]["completion"]:
            return {**receipt, "state": "disabled"}
        evidence, target = None, {}
        try:
            policy = config["completion"]
            state, artifacts, checks, identity, measured = self.collect(boundary, job, assignment, revision, mechanical)
            target = state["target"]
            state["boundary_rule"] = policy["boundaries"][boundary]
            for name, check in (mechanical or {}).items():
                if isinstance(check, dict) and (check.get("passed") is False or check.get("clean") is False):
                    raise ValueError("Completion needs the current " + name + " check to pass.")
                if isinstance(check, dict) and revision and check.get("revision", revision) != revision:
                    raise ValueError("Completion needs " + name + " evidence for the current source revision.")
            if any(check["exit_code"] != 0 for check in checks.values()):
                raise ValueError("Completion needs passing measurements: " + ", ".join(name for name, check in checks.items() if check["exit_code"] != 0))
            if not artifacts:
                raise ValueError("Completion needs retained proof of the objective and completion conditions; a result claim alone is insufficient.")
            sources = []
            for ident in artifacts:
                # References originate only in these trusted current reports/operations; verify their retained work link.
                with self.store.connect() as db:
                    scope = self.control.current()
                    self.control._reference(db, scope, "artifact:" + str(ident))
                value = self.artifacts.read(ident, limit=policy["artifact_bytes"])
                if value["encoding"] != "utf8":
                    continue
                measurement_scopes = measured.get(ident) or []
                measurement = measurement_scopes[0] if measurement_scopes else {}
                source_revision = measurement.get("revision")
                expected_revision = measurement.get("expected_revision", revision)
                proof_kind, workspace_clean = ("measured_check", True) if measurement else ("retained_artifact", None)
                if not measurement:
                    reports = {r["reference"] for r in state["reports"] if r["artifact"] == "artifact:" + str(ident)}
                    captures = [p for p in value["sources"] if p.get("provider") == "work_report" and p.get("reference") in reports]
                    metadata = [p["metadata"] if isinstance(p.get("metadata"), dict) else p for p in captures]
                    capture = next((p for p in metadata if p.get("source_revision") == expected_revision and p.get("workspace_clean") is True), metadata[0] if metadata else {})
                    source_revision = capture.get("source_revision")
                    proof_kind = capture.get("revision_kind", proof_kind)
                    workspace_clean = capture.get("workspace_clean")
                source = {"reference": "artifact:" + str(ident), "content": value["content"],
                          "partial": value["next_offset"] is not None, "source_revision": source_revision,
                          "expected_revision": expected_revision, "measurement_scopes": measurement_scopes,
                          "kind": proof_kind, "workspace_clean": workspace_clean,
                          "current_source": None if expected_revision is None or source_revision is None else source_revision == expected_revision and workspace_clean is not False}
                state.setdefault("proof", []).append(source)
                with self.store.connect() as db:
                    sha256 = db.execute("SELECT sha256 FROM artifacts WHERE id=?", (ident,)).fetchone()[0]
                sources.append({"reference": source["reference"], "source_sha256": sha256, "partial": source["partial"]})
            if not state.get("proof"):
                raise ValueError("Completion needs readable retained proof, such as measured output or a verifiable deliverable.")
            if revision and not any(source["current_source"] is True for source in state["proof"]):
                raise ValueError("Completion needs retained proof measured or captured against the current source revision.")
            if len(canonical(clean(state)).encode()) > policy["state_bytes"]:
                raise ValueError("Completion proof exceeds the bounded assessment; retain a concise measurement that covers all requirements.")
            try:
                result = Advice(self.store, self.member).evaluate("completion", state, policy["questions"], sources, policy=config)
            except JevUnavailable:
                if policy["failure_mode"] != "mechanical_only":
                    raise
                # The explicit operator fallback skips only unavailable semantic assessment.
                # Current proof and mechanical checks above remain mandatory.
                self._unchanged(receipt, during=True)
                if self.collect(boundary, job, assignment, revision, mechanical)[3] != identity:
                    raise ValueError("Completion requirements or proof changed during assessment; inspect the current work before retrying.")
                self.store.event(self.member, "completion_assessed", **target, boundary=boundary,
                                 outcome="skipped_unavailable", policy=config["revision"],
                                 failure_mode=policy["failure_mode"], required=list(FIELDS))
                return {**receipt, "state": "skipped_unavailable", "_identity": identity}
            self._unchanged(receipt, during=True)
            if not isinstance(result, dict) or not isinstance(result.get("evidence"), str) or not result["evidence"].startswith("artifact:"):
                raise ValueError("Completion assessment is incomplete; retain a valid assessment before accepting work.")
            evidence = result["evidence"]
            if self.collect(boundary, job, assignment, revision, mechanical)[3] != identity:
                raise ValueError("Completion requirements or proof changed during assessment; inspect the current work before retrying.")
            answers = result.get("answers")
            if not isinstance(answers, dict) or set(answers) != set(FIELDS):
                raise ValueError("Completion assessment is incomplete; obtain a valid judgment for every required criterion.")
            missing = []
            for name in FIELDS:
                answer = answers[name]
                probability = answer.get("noul") if isinstance(answer, dict) else None
                if type(probability) not in {int, float} or not math.isfinite(probability) or not 0 <= probability <= 1:
                    raise ValueError("Completion assessment has an invalid required-criterion probability.")
                if probability < policy["minimum_probability"]:
                    missing.append(name)
            self.store.event(self.member, "completion_assessed", **target, boundary=boundary, outcome="blocked" if missing else "ready", evidence=evidence, required=list(FIELDS), unresolved=missing, policy=config["revision"])
            if missing:
                raise ValueError("Completion needs stronger current proof for " + ", ".join(missing) + ". Inspect " + evidence + " and measure the unmet requirement.")
            return {**receipt, "state": "ready", "evidence": evidence, "cache_hit": result["cache_hit"], "_identity": identity}
        except ValueError as error:
            self.store.event(self.member, "completion_blocked", **target, boundary=boundary, evidence=evidence, reason=str(error))
            raise

    def _unchanged(self, receipt, *, during=False):
        params = receipt["_parameters"]
        config, scope_identity = self.settings(params["boundary"], params["job"], params["assignment"])
        when = "during" if during else "after"
        if config["revision"] != receipt["_configuration"] or scope_identity != receipt["_scope"]:
            raise ValueError("Completion policy changed " + when + " assessment; obtain a current assessment.")

    def verify(self, receipt):
        """Recheck an internal receipt immediately before a service commits acceptance."""
        self._unchanged(receipt)
        if receipt["state"] == "disabled":
            return
        params = receipt["_parameters"]
        if self.collect(params["boundary"], params["job"], params["assignment"], params["revision"], params["mechanical"])[3] != receipt["_identity"]:
            raise ValueError("Completion requirements or proof changed after assessment; inspect current work before acceptance.")
