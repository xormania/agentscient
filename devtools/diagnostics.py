"""Scoped recovery guidance and a conservative projection of retained context.

This module never authorizes an action, deletes a fact, or judges completion. The
backing services keep those responsibilities. Native hooks do not call Jev.
"""

from __future__ import annotations

import json
import math
import re

from .advice import Advice, digest
from .configuration import resolve
from .control import Control, binding
from .development import configured as development_configured
from .onboarding import document
from .role_packages import adapter
from .role_packages import role as role_package
from .work import record


def unavailable(store, member, kind, error, **data):
    try:
        store.event(member, kind, error_type=type(error).__name__, **data)
    except Exception:
        # An advisory telemetry failure cannot replace the actual tool outcome.
        pass


def project_context(store, member, context):
    try:
        return Diagnostics(store, member).project(context)
    except Exception as error:
        unavailable(store, member, "context_projection_unavailable", error)
        return context


def deliver_guidance(store, member, action, result=None, error=None):
    try:
        return Diagnostics(store, member).guidance(action, result, error)
    except Exception as cause:
        unavailable(store, member, "diagnostic_guidance_unavailable", cause, trigger=action)
        return {}


def failed(value):
    """A finished operation can contain a failed check without an exception."""
    if not isinstance(value, dict):
        return False
    if (value.get("passed") is False or value.get("isError") is True or
            value.get("state") in {"failed", "needs_attention"}):
        return True
    if isinstance(value.get("exit_code"), int) and value["exit_code"] != 0:
        return True
    checks = value.get("checks")
    return any(failed(value.get(key)) for key in ("result", "validation")) or (
        isinstance(checks, list) and any(failed(check) for check in checks)
    )


def byte_excerpt(text, limit):
    return text.encode("utf8")[:limit].decode("utf8", errors="ignore")


def diagnostic_text(value, field_bytes, total_bytes):
    """Bound diagnostic input before regex routing, including nested failures."""
    parts = []
    remaining = total_bytes

    def append(text):
        nonlocal remaining
        text = byte_excerpt(str(text or ""), min(field_bytes, remaining))
        if text:
            parts.append(text)
            remaining = max(0, remaining - len(text.encode("utf8")) - 1)

    def visit(item):
        if not isinstance(item, dict) or remaining <= 0:
            return
        for key in ("error", "message", "output"):
            append(item.get(key))
        for key in ("result", "validation"):
            visit(item.get(key))
        if isinstance(item.get("checks"), list):
            for check in item["checks"]:
                if remaining <= 0:
                    break
                if failed(check):
                    visit(check)
        if item.get("isError") and isinstance(item.get("content"), list):
            for block in item["content"]:
                if remaining <= 0:
                    break
                if isinstance(block, dict):
                    append(block.get("text"))

    visit(value)
    return byte_excerpt(" ".join(parts), total_bytes)


def indexed(value, index):
    """Substitute the one policy placeholder without interpreting other braces."""
    if isinstance(value, str):
        return value.replace("{index}", str(index))
    if isinstance(value, dict):
        return {key: indexed(item, index) for key, item in value.items()}
    if isinstance(value, list):
        return [indexed(item, index) for item in value]
    return value


class Diagnostics:
    def __init__(self, store, member):
        self.store, self.member = store, member
        self.control = Control(store, member)

    def current(self):
        scope = self.control.current()
        return scope if scope and scope == self.control.snapshot() and not scope["paused"] else None

    def settings(self, scope):
        return resolve(self.store, role=scope["role"], job=scope["job"])

    def unchanged(self, scope, identity, settings):
        return (self.current() == scope and self.identity(scope) == identity and
                self.settings(scope)["revision"] == settings["revision"])

    def projection_failure(self, context, settings, error):
        policy = settings["filtering"]
        unavailable(self.store, self.member, "context_projection_unavailable", error,
                    configuration_revision=settings["revision"], failure_mode=policy["failure_mode"])
        if policy["failure_mode"] == "notice":
            return {**context, "context_projection": {"state": "unavailable", "message": policy["failure_message"]}}
        return context

    def identity(self, scope, context=None):
        """Include mission/plan changes which need not replace a role binding."""
        with self.store.connect() as db:
            if binding(db, self.member) != scope:
                return None
            order = record(db, "work_orders", scope["work_order"])
            if context is not None and (
                context.get("work") != Control._summary(order) or
                context.get("context") != json.loads(order["context"]) or
                context.get("plan_revision") != order["plan_revision"] or
                context.get("responsibility") != scope["brief"]
            ):
                return None
            material = [scope, Control._summary(order), order["context"], order["plan_revision"]]
            if scope["job"]:
                job = record(db, "jobs", scope["job"])
                if context is not None and context.get("job") != Control._summary(job):
                    return None
                material += [Control._summary(job), job["assignment"], job["dependencies"]]
            if scope.get("assignment_id"):
                assigned = record(db, "role_assignments", scope["assignment_id"])
                material += [assigned["brief"], assigned["details"], assigned["status"]]
            return digest(material)

    def project(self, context):
        """Omit only clearly irrelevant background reports from the routine brief.

        Core instructions, incoming messages, evidence-bearing reports and explicit
        reference reads remain intact. Operator policy selects eligible kinds and
        protected text. Raw reports remain readable through their authorized refs.
        """
        scope = self.current()
        if (not scope or not isinstance(context, dict) or context.get("role") != scope["role"] or
                context.get("context_revision") != scope["revision"]):
            return context
        settings = self.settings(scope)
        policy = settings["filtering"]
        if (not settings["features"]["filtering"] or scope["role"] in policy["excluded_roles"] or
                adapter(scope["role"]) in policy["excluded_adapters"]):
            return context
        protected = re.compile(policy["protected_pattern"], re.I)
        activity = context.get("recent_activity")
        if not isinstance(activity, list) or not activity:
            return context
        identity = self.identity(scope, context)
        candidates = []
        with self.store.connect() as db:
            for index, item in enumerate(activity):
                if len(candidates) >= policy["max_facts"]:
                    break
                if (not isinstance(item, dict) or item.get("kind") not in policy["candidate_kinds"] or
                        not isinstance(item.get("text"), str) or
                        not isinstance(item.get("reference"), str) or
                        not re.fullmatch(r"update:[1-9][0-9]*", item["reference"]) or
                        item.get("evidence") or item.get("evaluation") or item.get("truncated") or
                        protected.search(item.get("text", ""))):
                    continue
                try:
                    kind, row = self.control._reference(db, scope, item["reference"])
                except (KeyError, ValueError):
                    continue
                if kind != "update" or Control._update(row, preview=True) != item:
                    continue
                candidates.append((index, item, digest(row)))
        if not candidates or identity is None:
            return context
        brief = {key: value for key, value in context.items() if key not in {"recent_activity", "incoming"}}
        facts = [item for _, item, _ in candidates]
        questions = {f"fact_{index}": indexed(policy["question"], index) for index in range(len(facts))}
        state = {"brief": brief, "facts": facts, "context_identity": identity}
        if len(json.dumps(state, ensure_ascii=False).encode("utf8")) > policy["state_bytes"]:
            return self.projection_failure(context, settings, ValueError("Relevance state exceeds configured byte budget"))
        sources = [{"reference": item["reference"], "source_sha256": source_hash}
                   for _, item, source_hash in candidates]
        try:
            assessment = Advice(self.store, self.member).evaluate(
                "context_relevance", state, questions, sources, policy=settings,
            )
            values = [assessment["answers"][name]["noul"] for name in questions]
            if any(type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 1 for value in values):
                raise ValueError("Invalid relevance assessment")
        except Exception as error:
            # Relevance failure does not hide facts or replace the original context.
            return self.projection_failure(context, settings, error)
        if not self.unchanged(scope, identity, settings):
            return context
        omitted = {candidates[index][0] for index, value in enumerate(values) if value < policy["threshold"]}
        projected = {**context, "recent_activity": [item for index, item in enumerate(activity) if index not in omitted]}
        self.store.event(
            self.member, "context_projected", role=scope["role"], context_identity=identity,
            threshold=policy["threshold"], evaluation=assessment["evidence"],
            configuration_revision=settings["revision"],
            facts=[{"reference": item["reference"], "source_sha256": source_hash,
                    "noul": values[index], "delivered": candidate_index not in omitted}
                   for index, (candidate_index, item, source_hash) in enumerate(candidates)],
        )
        return projected

    def allowed_skills(self, scope):
        package = role_package(scope["role"])
        names = [package["skills"]["shared"], package["skills"]["role"]]
        if development_configured(self.store) and (scope["job"] or adapter(scope["role"]) == "planner"):
            if "framework_inspect" in package["mcp"]["job_framework"]:
                names += package["skills"]["framework"]
        return names

    def guidance(self, action, result=None, error=None):
        """Deliver a configured permitted method without changing the tool outcome."""
        scope = self.current()
        if not scope or not (error or failed(result)):
            return {}
        settings = self.settings(scope)
        policy = settings["guidance"]
        if (not settings["features"]["guidance"] or scope["role"] in policy["excluded_roles"] or
                adapter(scope["role"]) in policy["excluded_adapters"]):
            return {}
        identity = self.identity(scope)
        if identity is None:
            return {}
        allowed = self.allowed_skills(scope)
        fallback = policy["fallback"]
        name = fallback["skill"]
        if name == "role" or name not in allowed:
            name = role_package(scope["role"])["skills"]["role"]
        description = byte_excerpt(
            byte_excerpt(str(error or ""), policy["diagnostic_field_bytes"]) + " " +
            diagnostic_text(result, policy["diagnostic_field_bytes"], policy["diagnostic_bytes"]),
            policy["diagnostic_bytes"],
        )
        next_action = None
        for route in policy["routes"]:
            if (route["skill"] in allowed and self.matches(route, action, scope["role"]) and
                    re.search(route["diagnostic_pattern"], description, re.I)):
                name, next_action = route["skill"], route["next_action"]
                break
        if next_action is None:
            next_action = next((entry["next_action"] for entry in policy["actions"]
                                if self.matches(entry, action, scope["role"])), fallback["next_action"])
        try:
            skill = document(name)
        except Exception as cause:
            unavailable(self.store, self.member, "diagnostic_guidance_unavailable", cause,
                        trigger=action, configuration_revision=settings["revision"],
                        failure_mode=policy["failure_mode"])
            if policy["failure_mode"] != "fallback" or not self.unchanged(scope, identity, settings):
                return {}
            return {"next_action": fallback["next_action"]}
        if not self.unchanged(scope, identity, settings):
            return {}
        content = byte_excerpt(skill["content"], policy["delivery_excerpt_bytes"])
        self.store.event(
            self.member, "skill_guidance_delivered", role=scope["role"], context_identity=identity,
            trigger=action, name=name, source=skill["source"], sha256=skill["sha256"],
            configuration_revision=settings["revision"],
        )
        return {"next_action": next_action, "skill": {
            "name": name, "content": content, "truncated": content != skill["content"],
        }}

    @staticmethod
    def matches(entry, action, role):
        return ((not entry["roles"] or role in entry["roles"]) and
                (not entry["adapters"] or adapter(role) in entry["adapters"]) and
                re.fullmatch(entry["action_pattern"], action, re.I) is not None)
