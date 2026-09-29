"""Bounded job handoffs over existing jobs, reports and artifacts."""

import json
from pathlib import Path, PurePosixPath

from .store import canonical
from .work import record


def valid_path(value):
    path = PurePosixPath(value)
    return bool(value and path.parts and value in {path.as_posix(), path.as_posix() + "/"} and not path.is_absolute()
                and not any(part in {".", "..", ".git", ".serena"} or part.startswith(".env") for part in path.parts)
                and not any(c in value for c in ("\\", "\0", "\n", "\r", ",")))


def covers(parent, path):
    parent, path = parent.rstrip("/"), path.rstrip("/")
    return path == parent or path.startswith(parent + "/")


def policy(store, project):
    path = Path(project.get("assignment_policy", Path(__file__).with_name("assignment-policy.json")))
    if not path.is_absolute():
        path = store.directory / path
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        raise ValueError("The operator must configure a readable assignment policy JSON file.") from None
    if not isinstance(value, dict) or set(value) != {"version", "protected_paths", "context_paths", "denied_makers", "inspection_commands"} or value["version"] != 1:
        raise ValueError("Unsupported assignment policy; start from devtools/assignment-policy.json.")
    for key in ("protected_paths", "context_paths"):
        if not isinstance(value[key], list) or any(not isinstance(p, str) or not valid_path(p) for p in value[key]):
            raise ValueError("Assignment policy paths must be relative project paths.")
    if not isinstance(value["denied_makers"], list) or any(not isinstance(p, str) or not p.startswith("make:") for p in value["denied_makers"]):
        raise ValueError("denied_makers must contain installed Maker command names.")
    if not isinstance(value["inspection_commands"], list) or any(not isinstance(p, str) or not p for p in value["inspection_commands"]):
        raise ValueError("inspection_commands must contain command names or patterns.")
    return value


def current(store, scope):
    if not scope or not scope["job"]:
        return {}
    with store.connect() as db:
        return json.loads(record(db, "jobs", scope["job"])["assignment"])


def snapshot(scope):
    return {key: scope[key] for key in ("member", "role", "work_order", "job", "reports_to", "revision", "updated")}


def prepare(db, control, scope, item, existing=None):
    from .workspaces import Workspaces

    value = dict(existing or {})
    spaces = Workspaces(control.store, control.member)
    rules = policy(control.store, spaces.config)
    for key in ("editable_paths", "context_paths"):
        if key not in item:
            continue
        paths = item[key]
        if len({p.rstrip("/") for p in paths}) != len(paths) or any(not valid_path(p) for p in paths):
            raise ValueError("Assignment paths must be distinct relative project paths.")
        if key == "editable_paths" and any(
            not spaces.permitted_path(path, item["role"], assignment={}) for path in paths
        ):
            raise ValueError("Assignment edit paths must stay within operator-configured role paths and exclude Makers.")
        value[key] = paths
    reference = item.get("plan", value.get("plan", {}).get("reference"))
    if reference:
        kind, update = control._reference(db, scope, reference)
        plan_scope = json.loads(update.get("binding") or "{}") if kind == "update" else {}
        if kind != "update" or update["kind"] != "result" or plan_scope.get("role") != "planner" or not update["artifact"]:
            raise ValueError("Use a planner's retained result update with plan evidence.")
        job = record(db, "jobs", update["job"])
        delivered = db.execute("SELECT * FROM deliveries WHERE job=? AND outcome='done'", (job["id"],)).fetchone()
        if job["status"] != "done" or not delivered or delivered["result_update"] != update["id"]:
            raise ValueError("Inspect and accept the planner's result before using it for implementation.")
        order = record(db, "work_orders", scope["work_order"])
        original = json.loads(update["mission"] or "{}")
        if any(original.get(key) != order[key] for key in ("objective", "done_when", "constraints")):
            raise ValueError("The mission changed after planning; request a current plan.")
        delegation = original.get("delegation")
        if delegation:
            from .control import binding

            parent = binding(db, delegation["member"])
            if not parent or parent["role"] != "nco" or parent["work_order"] != scope["work_order"] or parent["brief"] != delegation["brief"]:
                raise ValueError("The delegated mission changed after planning; request a current plan.")
        value["plan"] = {"reference": reference, "evidence": f"artifact:{update['artifact']}",
                         "author": update["actor"], "binding": plan_scope}
    if "plan" in value and "editable_paths" not in value and item["role"] in {"coder", "docs", "test_writer", "architect"}:
        raise ValueError("A planned implementation needs explicit editable_paths.")
    if "editable_paths" in value and "context_paths" not in value:
        value["context_paths"] = list(rules["context_paths"])
    return canonical(value)
