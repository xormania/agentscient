"""Retained long tool calls. Workers execute a fixed service action, never agent dispatch."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from .control import REQUEST_BINDING, Control, binding
from .store import Store, canonical, stamp

ACTIONS = {"framework_inspect", "framework_generate", "work_check", "work_submit"}


class Operations:
    def __init__(self, store, member):
        self.store, self.member = store, member
        self.control = Control(store, member)

    def start(self, action, arguments):
        scope = self.control.current()
        if (
            action not in ACTIONS
            or not scope
            or scope["paused"]
            or (not scope["job"] and (scope["role"] != "xo" or action not in {"work_check", "work_submit"}))
        ):
            raise ValueError("This operation requires active work in the corresponding role.")
        payload = canonical(arguments)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = binding(db, self.member)
            if current != scope:
                raise ValueError("Work context changed; inspect before retrying.")
            old = db.execute(
                "SELECT * FROM operations WHERE work_order=? AND job IS ? AND state IN ('queued','running')",
                (scope["work_order"], scope["job"]),
            ).fetchone()
            if old:
                if old["member"] != self.member or old["action"] != action or old["arguments"] != payload:
                    raise ValueError(
                        "An operation is already using this job. work_inspect with section operations shows progress."
                    )
                ident = old["id"]
            else:
                ident = db.execute(
                    "INSERT INTO operations(member,work_order,job,binding,action,arguments,state,created,updated) VALUES (?,?,?,?,?,?,'queued',?,?)",
                    (
                        self.member,
                        scope["work_order"],
                        scope["job"],
                        canonical(scope),
                        action,
                        payload,
                        stamp(),
                        stamp(),
                    ),
                ).lastrowid
        self.launch(ident)
        # A quick operation can return its result immediately; long calls never hold the harness conversation.
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            time.sleep(0.03)
            value = self.get(ident)
            if value["state"] not in {"queued", "running"}:
                return value
        return value

    def launch(self, ident):
        log = self.store.directory / "operations.log"
        with log.open("ab") as output:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).with_name("run.py")),
                    "operation",
                    "--state",
                    str(self.store.directory),
                    "--member",
                    self.member,
                    "--operation",
                    str(ident),
                ],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                start_new_session=True,
            )
        # Reap without waiting on the tool's work. The worker has its own lifetime and scoped context.
        import threading

        threading.Thread(target=process.wait, daemon=True).start()

    @staticmethod
    def public(row):
        return {
            "reference": "operation:" + str(row["id"]),
            "action": row["action"],
            "state": row["state"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
            "updated": row["updated"],
        }

    @classmethod
    def summary(cls, row):
        """Keep live notices small; the existing operation/evidence reads retain detail."""
        value = cls.public(row)
        result = value.pop("result")
        if value["error"]:
            value["error"] = value["error"][:500]
        if isinstance(result, dict):
            for key in ("passed", "revision", "evidence", "checkpoint", "pr"):
                if key in result:
                    value[key] = result[key]
            if "state" in result:
                value["outcome"] = result["state"]
            if result.get("message"):
                value["message"] = result["message"][:500]
            validation = result.get("validation") or result
            if isinstance(validation.get("checks"), list):
                checks = validation["checks"]
                value["passed"] = validation["passed"]
                value["checks"] = {"total": len(checks), "failed": sum(r["exit_code"] != 0 for r in checks)}
                value["checks"]["evidence"] = [
                    {"check": r["check"], "reference": r["evidence"]} for r in checks if r.get("evidence")
                ]
                value["uncommitted"] = len(validation.get("uncommitted", []))
            generated = result.get("result")
            if isinstance(generated, dict) and "exit_code" in generated:
                value["exit_code"] = generated["exit_code"]
                value["outside_role_paths"] = len(generated.get("outside_role_paths", []))
        value["details"] = 'Use work_context(reference=<this reference>); follow next_offset for the complete result.'
        return value

    def get(self, ident):
        scope = self.control.current()
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM operations WHERE id=? AND work_order=? AND job IS ?",
                (ident, scope["work_order"], scope["job"]),
            ).fetchone()
            if not row:
                raise ValueError("Operation is not in your current work.")
            return self.public(row)

    def inspect(self, offset=0):
        scope = self.control.current()
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM operations WHERE work_order=? AND job IS ? AND (?=0 OR id<?) ORDER BY id DESC LIMIT 11",
                (scope["work_order"], scope["job"], offset, offset),
            ).fetchall()
            return {
                "operations": [self.summary(row) for row in rows[:10]],
                "next_offset": rows[9]["id"] if len(rows) > 10 else None,
            }

    def tick(self):
        # OS locks establish whether a worker still exists, including across PID reuse.
        from .workspaces import Workspaces

        with self.store.connect() as db:
            rows = list(
                db.execute("SELECT * FROM operations WHERE member=? AND state IN ('queued','running')", (self.member,))
            )
        for row in rows:
            if row["state"] == "queued":
                self.launch(row["id"])
                continue
            try:
                with Workspaces(self.store, self.member).lock("operation-" + str(row["id"])):
                    with self.store.connect() as db:
                        db.execute(
                            "UPDATE operations SET state='uncertain',error=?,updated=? WHERE id=? AND state='running'",
                            (
                                "Worker stopped without recording completion. Inspect retained changes and provider state before repeating the operation.",
                                stamp(),
                                row["id"],
                            ),
                        )
            except ValueError:
                pass


def execute(directory, member, ident):
    from .development import Development
    from .workspaces import Workspaces

    store = Store(directory)
    spaces = Workspaces(store, member)
    try:
        with spaces.lock("operation-" + str(ident)):
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM operations WHERE id=? AND member=? AND state='queued'", (ident, member)
                ).fetchone()
                if not row:
                    return
                db.execute("UPDATE operations SET state='running',updated=? WHERE id=?", (stamp(), ident))
            scope = json.loads(row["binding"])
            token = REQUEST_BINDING.set((member, scope))
            try:
                with store.work_context(member, scope["work_order"], scope["job"]):
                    result, error = None, None
                    try:
                        current = spaces.scope(write=row["action"] in {"framework_generate", "work_submit"})
                        if current["paused"]:
                            raise ValueError("This work is paused; the operation did not start.")
                        arguments = json.loads(row["arguments"])
                        development = Development(store, member)
                        action = row["action"]
                        if action == "work_submit":
                            result = spaces.submit(**arguments)
                        else:
                            method = {
                                "framework_inspect": "inspect",
                                "framework_generate": "generate",
                                "work_check": "check",
                            }[action]
                            result = getattr(development, method)(**arguments)
                    except Exception as failure:
                        from .github_http import GitHubHTTP

                        error = GitHubHTTP().clean(str(failure))[:2000]
                    with store.connect() as db:
                        db.execute("BEGIN IMMEDIATE")
                        state = "failed" if error else "completed"
                        db.execute(
                            "UPDATE operations SET state=?,result=?,error=?,updated=? WHERE id=?",
                            (state, canonical(result) if result is not None else None, error, stamp(), ident),
                        )
                        completed = db.execute("SELECT * FROM operations WHERE id=?", (ident,)).fetchone()
                        body = canonical(Operations.summary(completed))
                        # Deliver to the original worker and supervisor only while their current scope still includes this job.
                        for recipient in {member, scope["reports_to"]} - {None}:
                            now = binding(db, recipient)
                            if now and now["work_order"] == scope["work_order"] and now["job"] in {None, scope["job"]}:
                                store._send(
                                    db,
                                    member,
                                    recipient,
                                    body,
                                    key="operation:" + str(ident) + ":" + recipient,
                                    work_order=scope["work_order"],
                                    job=scope["job"],
                                )
                        store._event(
                            db,
                            member,
                            "tool_operation_finished",
                            {
                                "operation": ident,
                                "action": row["action"],
                                "state": state,
                                "work_order": scope["work_order"],
                                "job": scope["job"],
                            },
                        )
            finally:
                REQUEST_BINDING.reset(token)
    except ValueError as error:
        if not str(error).startswith("Another operation"):
            raise
