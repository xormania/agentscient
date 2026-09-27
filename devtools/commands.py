"""CO/XO outcomes over the existing work, binding, and live-session services."""

from __future__ import annotations

import hashlib
import json

from . import launch
from .control import BRIEF_FIELDS, ROLES, Control, binding
from .store import canonical, stamp
from .work import Work, record

ROLE_TOOLS = {"co": {"direct", "monitor", "conclude"}, "xo": {"orchestrate", "monitor", "steer"}}


def capabilities(spec):
    text = {"type": "string", "minLength": 1, "maxLength": 2000}
    name = {**text, "maxLength": 100}
    setting = {**text, "maxLength": 120, "pattern": "[A-Za-z0-9][A-Za-z0-9_./:@+-]{0,119}"}
    selection = {
        "type": "object",
        "description": "Optional filters for an available configured harness slot; monitor shows capacity.",
        "properties": {
            "harness": {"type": "string", "enum": sorted(launch.HARNESSES)},
            "model": setting,
            "reasoning": setting,
        },
        "additionalProperties": False,
    }
    goal = {"objective": text, "done_when": text, "constraints": {**text, "minLength": 0}}
    return [
        spec(
            "direct",
            "CO: establish or revise the current objective and boundaries; bind XO and deliver relevant briefs.",
            {"title": name, **goal, "selection": selection},
            ("title", "objective", "done_when", "constraints"),
        ),
        spec(
            "orchestrate",
            "XO: organize named work and live collaborators. Records, slot allocation, briefs and startup are automatic.",
            {
                "work": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": name,
                            "role": {"type": "string", "enum": [r for r in ROLES if r not in ROLE_TOOLS]},
                            **{key: {**value, "maxLength": 800} for key, value in goal.items()},
                            "selection": selection,
                        },
                        "required": ["name", "role", "objective", "done_when", "constraints"],
                        "additionalProperties": False,
                    },
                }
            },
            ("work",),
        ),
        spec(
            "monitor",
            "CO/XO: read scoped progress, blockers, observed sessions, recent measured usage and available capacity.",
            {
                "offset": {"type": "integer", "minimum": 0},
                "work": {**name, "description": "Optional named job to inspect its current review packet and CI."},
                "path": {**text, "description": "Changed file to inspect within the named job's PR."},
                "page": {"type": "integer", "minimum": 1, "description": "Changed-file page for a named job."},
            },
            readonly=True,
        ),
        spec(
            "steer",
            "XO: guide collaborators, revise a named brief, or accept/cancel a named job with an assessment.",
            {
                "action": {"type": "string", "enum": ["guide", "pause", "resume", "stop", "accept", "cancel"]},
                "work": {**name, "description": "A name supplied to orchestrate; omit to address your team."},
                "role": {
                    "type": "string",
                    "enum": [r for r in ROLES if r not in ROLE_TOOLS],
                    "description": "Optional collaborator role when a job has both a producer and auditor.",
                },
                "direction": text,
                **{key: {**value, "maxLength": 1000} for key, value in goal.items()},
            },
            ("action",),
        ),
        spec(
            "conclude",
            "CO: record your assessment of the completed work order and release its team; retain all history.",
            {"assessment": text},
            ("assessment",),
        ),
    ]


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Commands:
    def __init__(self, store, member, control):
        self.store, self.member, self.control = store, member, control
        self.work = Work(store, member)

    def appointed_co(self):
        path = self.store.directory / "team.json"
        return path.is_file() and launch.team_config(self.store.directory).get("co") == self.member

    def role(self, scope):
        return scope["role"] if scope else "co" if self.appointed_co() else None

    def _config(self):
        config = launch.team_config(self.store.directory)
        self.store.initialize(config["members"])
        return config

    def _scope(self, db, roles, *, bootstrap=False):
        current, expected = binding(db, self.member), self.control.current()
        identity = ("role", "work_order", "job", "reports_to", "revision")
        if (tuple(current[key] for key in identity) if current else None) != (
            tuple(expected[key] for key in identity) if expected else None
        ):
            raise ValueError("Your role or work changed during this call; read your current context and retry.")
        if current is None and bootstrap and self.appointed_co():
            return None
        if not current or current["role"] not in roles or current["job"] is not None:
            raise ValueError("This command requires the corresponding work-order command role.")
        return current

    @staticmethod
    def _descendants(db, scope):
        return [
            dict(row)
            for row in db.execute(
                "WITH RECURSIVE team(member) AS (SELECT member FROM member_bindings WHERE reports_to=? "
                "AND work_order=? UNION SELECT b.member FROM member_bindings b JOIN team t ON b.reports_to=t.member "
                "WHERE b.work_order=?) SELECT b.* FROM member_bindings b JOIN team t ON t.member=b.member ORDER BY b.member",
                (scope["member"], scope["work_order"], scope["work_order"]),
            )
        ]

    @staticmethod
    def _matches(row, selection):
        return all(row.get(key) == value for key, value in (selection or {}).items())

    @staticmethod
    def _settings(db, slot):
        session = db.execute("SELECT state FROM members WHERE name=?", (slot["name"],)).fetchone()
        if session["state"] in {"starting", "idle", "active"}:
            event = db.execute(
                "SELECT data FROM events WHERE actor=? AND kind='session_starting' ORDER BY id DESC LIMIT 1",
                (slot["name"],),
            ).fetchone()
            settings = json.loads(event["data"]).get("settings") if event else None
            return (
                (settings, "session_start")
                if settings
                else ({"harness": slot["harness"], "model": None, "reasoning": None}, "unknown")
            )
        return {key: slot.get(key) for key in ("harness", "model", "reasoning")}, "configured"

    def _slot(self, db, config, selection, existing=None):
        if existing:
            row = next((r for r in config["members"] if r["name"] == existing["member"]), None)
            if not row or not self._matches(self._settings(db, row)[0], selection):
                raise ValueError("This work already has a collaborator with different configured settings.")
            return row
        for row in config["members"]:
            if row["name"] == config.get("co") or row["name"] == self.member or not self._matches(row, selection):
                continue
            session = db.execute("SELECT state,pid FROM members WHERE name=?", (row["name"],)).fetchone()
            if not binding(db, row["name"]) and session["state"] in {"stopped", "failed"} and not session["pid"]:
                return row
        raise ValueError("No available configured collaborator matches this work. Monitor capacity or ask CO for help.")

    @staticmethod
    def _touch(db, member):
        db.execute("UPDATE member_bindings SET revision=revision+1,updated=? WHERE member=?", (stamp(), member))

    @staticmethod
    def _brief(db, scope):
        order = record(db, "work_orders", scope["work_order"])
        result = {
            "role": scope["role"],
            "work_state": "paused" if scope["paused"] else "active",
            "responsibility": scope["brief"],
            "work": {key: order[key] for key in BRIEF_FIELDS},
        }
        if scope["job"]:
            job = record(db, "jobs", scope["job"])
            result["job"] = {key: job[key] for key in BRIEF_FIELDS}
        return result

    def _direction(self, db, scope, text):
        body = canonical({"direction": text, "context_revision": scope["revision"], "brief": self._brief(db, scope)})
        key = "direction:" + digest([scope["member"], scope["revision"], body])
        sender = scope["reports_to"] or self.member
        exists = db.execute("SELECT id FROM messages WHERE sender=? AND request_key=?", (sender, key)).fetchone()
        message = self.store._send(
            db, sender, scope["member"], body, key=key, work_order=scope["work_order"], job=scope["job"]
        )
        if not exists:
            self.store._event(
                db,
                self.member,
                "direction_issued",
                {"message": message["id"], "work_order": scope["work_order"], "job": scope["job"]},
            )
        db.execute("UPDATE messages SET category='direction' WHERE id=?", (message["id"],))
        # Retain earlier direction as history, but do not deliver stale queued briefs.
        db.execute(
            "UPDATE messages SET delivery='superseded' WHERE recipient=? AND work_order=? AND job IS ? "
            "AND category='direction' AND delivery='queued' AND id<?",
            (scope["member"], scope["work_order"], scope["job"], message["id"]),
        )
        return {"reference": f"message:{message['id']}", "delivery": message["delivery"]}

    @staticmethod
    def _start_intent(db, scope, slot):
        session = db.execute("SELECT * FROM members WHERE name=?", (scope["member"],)).fetchone()
        if (
            slot["harness"] != "external"
            and not scope["paused"]
            and (session["state"] in {"stopped", "failed"} or session["desired"] == "stopped")
        ):
            db.execute(
                "UPDATE member_bindings SET launch_pending=1,launch_error=NULL WHERE member=?", (scope["member"],)
            )

    def direct(self, title, objective, done_when, constraints, selection=None):
        config = self._config()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self._scope(db, {"co"}, bootstrap=True)
            fields = dict(title=title, objective=objective, done_when=done_when, constraints=constraints)
            changed = False
            if scope:
                old = record(db, "work_orders", scope["work_order"])
                changed = any(old[key] != value for key, value in fields.items())
                self.work.update_in(db, "work_orders", scope["work_order"], None, **fields)
            else:
                order = self.work.create_in(db, "work_orders", **fields, select=False)["work_order"]["id"]
                scope = self.control.bind_in(db, self.member, "co", order)
            team = self._descendants(db, scope)
            candidates = [row for row in team if row["role"] == "xo" and row["reports_to"] == self.member]
            if len(candidates) > 1:
                raise ValueError("More than one XO is bound to CO; resolve the trusted setup before directing work.")
            slot = self._slot(db, config, selection, candidates[0] if candidates else None)
            xo = self.control.bind_in(
                db,
                slot["name"],
                "xo",
                scope["work_order"],
                reports_to=self.member,
                brief=candidates[0]["brief"] if candidates else "",
            )
            if changed:
                for row in [scope, *self._descendants(db, scope)]:
                    self._touch(db, row["member"])
            xo = binding(db, xo["member"])
            self._start_intent(db, xo, slot)
            sent = self._direction(db, xo, "Carry out the current objective within its boundaries.")
            if changed:
                for row in self._descendants(db, scope):
                    if row["member"] != xo["member"]:
                        self._direction(db, row, "The work-order brief has changed. Apply it to your responsibility.")
            return {"work": title, "xo": self._participant(db, xo, config), "direction": sent}

    def orchestrate(self, work):
        config = self._config()
        names = [item["name"].strip().casefold() for item in work]
        if (
            not work
            or "" in names
            or len({(name, item["role"]) for name, item in zip(names, work, strict=True)}) != len(names)
        ):
            raise ValueError("Supply distinct, nonempty work names.")
        results = []
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self._scope(db, {"xo"})
            if scope["paused"]:
                raise ValueError("Your work is paused. Report or request guidance before expanding it.")
            for item, name in zip(work, names, strict=True):
                key = "orchestrate:" + digest([scope["work_order"], name])
                old = db.execute(
                    "SELECT * FROM jobs WHERE created_by=? AND request_key=?", (self.member, key)
                ).fetchone()
                fields = {key: item[key] for key in ("objective", "done_when", "constraints")}
                changed = old and any(old[key] != value for key, value in fields.items())
                if old:
                    job = old["id"]
                    if old["status"] in {"done", "cancelled"}:
                        raise ValueError("That responsibility is finished. Use a new work name for a new job.")
                    if item["role"] != "audit":
                        self.work.update_in(db, "jobs", scope["work_order"], job, **fields)
                else:
                    job = self.work.create_in(
                        db,
                        "jobs",
                        title=item["name"].strip(),
                        **fields,
                        key=key,
                        work_order=scope["work_order"],
                        select=False,
                    )["job"]["id"]
                existing = db.execute("SELECT * FROM member_bindings WHERE job=?", (job,)).fetchall()
                if any(row["reports_to"] != self.member for row in existing):
                    raise ValueError("This work has another reporting arrangement; request guidance.")
                same = [row for row in existing if row["role"] == item["role"]]
                if (
                    len(same) > 1
                    or item["role"] != "audit"
                    and any(row["role"] not in {"audit", item["role"]} for row in existing)
                ):
                    raise ValueError(
                        "A job has one producer and an optional auditor; use another name for separate work."
                    )
                prior = dict(same[0]) if same else None
                slot = self._slot(db, config, item.get("selection"), prior)
                target = self.control.bind_in(
                    db,
                    slot["name"],
                    item["role"],
                    scope["work_order"],
                    job,
                    self.member,
                    canonical(fields) if item["role"] == "audit" else prior["brief"] if prior else "",
                )
                if changed and item["role"] != "audit":
                    self._touch(db, target["member"])
                    for other in existing:
                        if other["member"] != target["member"]:
                            self._touch(db, other["member"])
                            self._direction(
                                db,
                                binding(db, other["member"]),
                                "The job brief changed. Apply the current objective and boundaries.",
                            )
                target = binding(db, target["member"])
                self._start_intent(db, target, slot)
                direction = self._direction(db, target, "Carry out your responsibility using the current brief.")
                results.append({**self._participant(db, target, config), "direction": direction})
        return {"work": results}

    def steer(self, action, work=None, direction=None, role=None, **fields):
        if role == "audit" and fields:
            raise ValueError(
                "Guide the audit with direction or revise its responsibility through orchestrate; job criteria apply to the whole job."
            )
        if action in {"accept", "cancel"}:
            if not work or not direction or fields or role:
                raise ValueError(
                    "Name one job and supply its acceptance assessment or cancellation reason as direction."
                )
            with self.store.connect() as db:
                scope = self._scope(db, {"xo"})
                job = self._named_job(db, scope, work)
            from .delivery import Delivery

            return Delivery(self.store, self.member).finish_job(job["id"], direction, cancel=action == "cancel")
        if fields and not work:
            raise ValueError("Name one responsibility when revising its objective, completion criteria or constraints.")
        if action == "guide" and not direction and not fields:
            raise ValueError("Supply direction or a revised job brief.")
        config = self._config()
        results = []
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self._scope(db, {"xo"})
            targets = self._descendants(db, scope)
            if role:
                targets = [row for row in targets if row["role"] == role]
            if scope["paused"] and action not in {"pause", "stop"}:
                raise ValueError("Your work is paused. Request guidance before restarting or redirecting it.")
            if work:
                targets = [
                    row
                    for row in targets
                    if row["job"] and record(db, "jobs", row["job"])["title"].casefold() == work.strip().casefold()
                ]
                if not targets:
                    raise ValueError("Name a responsibility in your current team.")
            if not targets:
                raise ValueError("No collaborators are bound to this responsibility yet.")
            for target in targets:
                changed = False
                if fields:
                    old = record(db, "jobs", target["job"])
                    changed = any(old[key] != value for key, value in fields.items())
                    self.work.update_in(db, "jobs", scope["work_order"], target["job"], **fields)
                paused = 1 if action in {"pause", "stop"} else 0 if action == "resume" else target["paused"]
                brief = direction if direction is not None else target["brief"]
                if changed or paused != target["paused"] or brief != target["brief"]:
                    db.execute(
                        "UPDATE member_bindings SET paused=?,brief=? WHERE member=?", (paused, brief, target["member"])
                    )
                    self._touch(db, target["member"])
                if action in {"pause", "stop"}:
                    db.execute("UPDATE member_bindings SET launch_pending=0 WHERE member=?", (target["member"],))
                if action == "stop":
                    db.execute("UPDATE members SET desired='stopped' WHERE name=?", (target["member"],))
                target = binding(db, target["member"])
                if action == "resume":
                    slot = self._slot(db, config, None, target)
                    self._start_intent(db, target, slot)
                sent = self._direction(
                    db,
                    target,
                    {
                        "guide": "Apply the current direction.",
                        "pause": "Pause new work; remain available for guidance.",
                        "resume": "Resume work within the current brief.",
                        "stop": "Stop work; the managed session will close.",
                    }[action],
                )
                self.store._event(
                    db,
                    self.member,
                    "work_steered",
                    {
                        "action": action,
                        "member": target["member"],
                        "work_order": target["work_order"],
                        "job": target["job"],
                    },
                )
                results.append({**self._participant(db, target, config), "direction": sent})
        return {"work": results}

    def _participant(self, db, scope, config):
        current = binding(db, scope["member"])
        session = db.execute("SELECT * FROM members WHERE name=?", (scope["member"],)).fetchone()
        slot = next(
            (row for row in config["members"] if row["name"] == scope["member"]),
            {"name": scope["member"], "harness": session["harness"]},
        )
        settings, settings_source = self._settings(db, slot)
        job = record(db, "jobs", scope["job"]) if scope["job"] else None
        update = db.execute(
            "SELECT * FROM work_updates WHERE actor=? AND work_order=? AND job IS ? ORDER BY id DESC LIMIT 1",
            (scope["member"], scope["work_order"], scope["job"]),
        ).fetchone()
        usage = db.execute(
            "SELECT id,at,data FROM events WHERE actor=? AND work_order=? AND job IS ? AND kind='native_usage' ORDER BY id DESC LIMIT 1",
            (scope["member"], scope["work_order"], scope["job"]),
        ).fetchone()
        observed_usage = None
        if usage:
            value = json.loads(usage["data"]).get("observation")
            encoded = canonical(value)
            observed_usage = {"at": usage["at"], "observation": value, "truncated": False}
            if len(encoded) > 3000:
                observed_usage.update(observation=None, preview=encoded[:3000], truncated=True)
        return {
            "role": scope["role"],
            "work": job["title"] if job else "work-order coordination",
            "work_state": "paused" if current["paused"] else "active",
            "status": job["status"] if job else record(db, "work_orders", scope["work_order"])["status"],
            "blocker": job["blocker"] if job else "",
            "settings": settings,
            "settings_source": settings_source,
            "session": {
                "observed": session["state"],
                "desired": session["desired"],
                "launch_pending": bool(current["launch_pending"]),
                "error": current["launch_error"] or json.loads(session["detail"]).get("error"),
                "managed": slot.get("harness") != "external",
            },
            "latest_report": Control._update(update, preview=True) if update else None,
            "latest_usage": observed_usage,
        }

    @staticmethod
    def _named_job(db, scope, name):
        rows = [
            dict(row)
            for row in db.execute("SELECT * FROM jobs WHERE work_order=?", (scope["work_order"],))
            if row["title"].casefold() == name.strip().casefold()
            and (scope["role"] == "co" or row["created_by"] == scope["member"])
        ]
        if len(rows) != 1:
            raise ValueError("Name a unique responsibility in your current work order.")
        return rows[0]

    def conclude(self, assessment):
        from .delivery import Delivery

        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self._scope(db, {"co"})
            if db.execute(
                "SELECT 1 FROM jobs WHERE work_order=? AND status NOT IN ('done','cancelled')", (scope["work_order"],)
            ).fetchone():
                raise ValueError(
                    "Jobs remain unfinished. Monitor their results and have XO accept or explicitly cancel them first."
                )
            Work(self.store, self.member).update_in(
                db, "work_orders", scope["work_order"], None, status="done", next_action="", blocker=""
            )
            for row in [*self._descendants(db, scope), scope]:
                Delivery.release(db, row["member"])
            self.store._event(
                db, self.member, "work_order_concluded", {"work_order": scope["work_order"], "assessment": assessment}
            )
        return {
            "outcome": "done",
            "assessment": assessment,
            "history": "retained",
            "next": "Use direct when the user authorizes another objective.",
        }

    def monitor(self, offset=0, work=None, path=None, page=1):
        if work:
            with self.store.connect() as db:
                scope = self._scope(db, ROLE_TOOLS)
                job = self._named_job(db, scope, work)
            from .delivery import Delivery

            return {
                "work": {key: job[key] for key in BRIEF_FIELDS},
                "delivery": Delivery(self.store, self.member).inspect(
                    job=job["id"], path=path, offset=offset, page=page
                ),
            }
        if path is not None or page != 1:
            raise ValueError("Review path and page require a named work responsibility.")
        config = self._config()
        with self.store.connect() as db:
            db.execute("BEGIN")
            scope = self._scope(db, ROLE_TOOLS, bootstrap=True)
            team = self._descendants(db, scope) if scope else []
            jobs = (
                [
                    dict(row)
                    for row in db.execute("SELECT * FROM jobs WHERE work_order=? ORDER BY id", (scope["work_order"],))
                    if scope["role"] == "co" or row["created_by"] == self.member
                ]
                if scope
                else []
            )
            capacity = {}
            for slot in config["members"]:
                if slot["name"] in {self.member, config.get("co")} or binding(db, slot["name"]):
                    continue
                session = db.execute("SELECT state,pid FROM members WHERE name=?", (slot["name"],)).fetchone()
                if session["state"] not in {"stopped", "failed"} or session["pid"]:
                    continue
                settings = {key: slot.get(key) for key in ("harness", "model", "reasoning")}
                key = canonical(settings)
                capacity.setdefault(key, {**settings, "available": 0})["available"] += 1
            return {
                "work": self._brief(db, scope)["work"] if scope else None,
                "collaborators": [self._participant(db, row, config) for row in team[offset : offset + 10]],
                "next_offset": offset + 10 if len(team) > offset + 10 else None,
                "capacity": list(capacity.values()),
                "jobs": [
                    {key: row[key] for key in ("title", "status", "next_action", "blocker", "pull_request")}
                    for row in jobs[offset : offset + 10]
                ],
                "next_job_offset": offset + 10 if len(jobs) > offset + 10 else None,
                "usage_note": "Latest raw observations only; absent usage is unknown, and observations are not additive totals.",
            }

    def tick(self):
        """Resume persisted launch intents after a server restart; never dispatch work."""
        with self.store.connect() as db:
            pending = list(
                db.execute("SELECT member,revision FROM member_bindings WHERE launch_pending=1 AND paused=0")
            )
        for row in pending:
            try:
                launch.start(self.store.directory, row["member"], binding_revision=row["revision"])
            except BlockingIOError:
                continue
            except Exception as error:
                with self.store.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    current = binding(db, row["member"])
                    if not current or current["revision"] != row["revision"] or not current["launch_pending"]:
                        continue
                    detail = str(error)[:600]
                    db.execute(
                        "UPDATE member_bindings SET launch_pending=0,launch_error=? WHERE member=?",
                        (detail, row["member"]),
                    )
                    parent = binding(db, current["reports_to"])
                    if parent and parent["work_order"] == current["work_order"]:
                        self.store._send(
                            db,
                            row["member"],
                            parent["member"],
                            "Session startup failed: " + detail,
                            key="launch-failed:" + digest([row["member"], current["revision"], detail]),
                            work_order=current["work_order"],
                            job=current["job"],
                        )
                    self.store._event(
                        db,
                        row["member"],
                        "command_launch_failed",
                        {"error": detail, "work_order": current["work_order"], "job": current["job"]},
                    )
