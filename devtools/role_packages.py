"""Trusted role-package projections; CUE is needed only for maintainer generation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

SOURCE = Path(__file__).with_name("role-packages.cue")
GENERATED = SOURCE.with_suffix(".json")
HARNESSES = {"codex", "claude", "grok"}
GROUPS = {"bound", "session", "command", "advice", "job", "job_framework", "work_order", "work_order_framework"}
HOOK_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart", "Stop")
READ_ONLY_ROLES = {"co", "xo", "nco", "planner", "audit", "research"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _object(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"Invalid {where} fields")
    return value


def _text(value, where):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"{where} must be nonempty text")


def _strings(value, where, *, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{where} must be a {'nonempty ' if nonempty else ''}list")
    for item in value:
        _text(item, where)
    if len(set(value)) != len(value):
        raise ValueError(f"Duplicate {where} value")


def validate(value, source_sha256):
    """Inspect the raw export; do not infer missing observed configuration fields."""
    _object(value, {"source_sha256", "catalog"}, "role export")
    if value["source_sha256"] != source_sha256:
        raise ValueError("Role export is stale; regenerate devtools/role-packages.json from role-packages.cue")
    catalog = _object(value["catalog"], {"version", "framework_skills", "roles"}, "role catalog")
    if type(catalog["version"]) is not int or catalog["version"] != 1:
        raise ValueError("Unsupported role catalog version")
    _strings(catalog["framework_skills"], "framework skills")
    if not isinstance(catalog["roles"], dict) or not catalog["roles"]:
        raise ValueError("Role catalog needs role definitions")
    for name, package in catalog["roles"].items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z_]{0,31}", name):
            raise ValueError("Invalid role name")
        _object(package, {"version", "responsibility", "skills", "runtime", "hooks", "mcp", "workspace"}, name)
        if type(package["version"]) is not int or package["version"] != 1:
            raise ValueError("Unsupported role package version")
        _text(package["responsibility"], name + ".responsibility")
        skills = _object(package["skills"], {"shared", "role", "framework"}, name + ".skills")
        _strings(skills["framework"], name + ".skills.framework")
        for skill in [skills["shared"], skills["role"], *skills["framework"]]:
            if not isinstance(skill, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", skill):
                raise ValueError("Invalid role skill reference")
            if not (SOURCE.parent.parent / ".agents" / "skills" / skill / "SKILL.md").is_file():
                raise ValueError("Role package references a missing installed skill")
        runtime = _object(package["runtime"], {"harnesses", "model", "reasoning", "profiles"}, name + ".runtime")
        _strings(runtime["harnesses"], name + ".runtime.harnesses", nonempty=True)
        if set(runtime["harnesses"]) - HARNESSES or runtime["profiles"] != "operator":
            raise ValueError("Role runtime needs supported harnesses and operator profiles")
        for key in ("model", "reasoning"):
            option = _object(runtime[key], {"default", "allowed"}, name + ".runtime." + key)
            if option["default"] is not None:
                _text(option["default"], key + " default")
            if option["allowed"] is not None:
                _strings(option["allowed"], key + " allowed", nonempty=True)
                if option["default"] is not None and option["default"] not in option["allowed"]:
                    raise ValueError(f"{name}.{key} default is outside its allowed options")
        hooks = _object(package["hooks"], {"events", "policy", "native_delegation"}, name + ".hooks")
        if hooks["events"] != list(HOOK_EVENTS) or hooks["policy"] != "mcp_only" or hooks["native_delegation"] is not False:
            raise ValueError("Role hooks must preserve MCP-only standalone sessions")
        mcp = _object(package["mcp"], GROUPS, name + ".mcp")
        for group, names in mcp.items():
            _strings(names, name + ".mcp." + group)
            if any(not re.fullmatch(r"[a-z][a-z_]{0,63}", tool) for tool in names):
                raise ValueError("Invalid role MCP tool reference")
        if name == "co" and (mcp["command"] != ["direct", "monitor"] or
                             any(mcp[group] for group in GROUPS - {"bound", "session", "command"})):
            raise ValueError("CO package must remain an interface")
        workspace = _object(package["workspace"], {"editor", "paths", "serena"}, name + ".workspace")
        if type(workspace["editor"]) is not bool or type(workspace["serena"]) is not bool:
            raise ValueError("Role workspace permissions need booleans")
        if name in READ_ONLY_ROLES and workspace["editor"]:
            raise ValueError("Command and read-only roles cannot become job editors")
        if name == "co" and (workspace["serena"] or skills["framework"]):
            raise ValueError("CO package cannot enable execution providers or skills")
        _strings(workspace["paths"], name + ".workspace.paths", nonempty=workspace["editor"])
        if not workspace["editor"] and workspace["paths"]:
            raise ValueError("Read-only roles cannot have editable paths")
        for path in workspace["paths"]:
            if path.startswith(("/", "\\")) or "\\" in path or ":" in path or any(p in {"", ".", ".."} for p in path.rstrip("/").split("/")):
                raise ValueError("Role paths must stay relative to the project")
    return catalog


@lru_cache(maxsize=1)
def _catalog():
    try:
        value = json.loads(GENERATED.read_text())
    except (OSError, ValueError) as error:
        raise ValueError("Read a valid generated devtools/role-packages.json before starting services") from error
    return validate(value, hashlib.sha256(SOURCE.read_bytes()).hexdigest())


def catalog():
    return copy.deepcopy(_catalog())


def role(name):
    try:
        return copy.deepcopy(_catalog()["roles"][name])
    except (KeyError, TypeError) as error:
        raise ValueError("Unknown role package") from error


def descriptor(name):
    package = role(name)
    return {"role": name, "version": package["version"], "revision": digest([name, package])}


def require_capability(name, capability):
    """Apply a package ceiling before a backing service performs an action.

    Bindings, provider prerequisites and action-specific restrictions remain
    the caller's responsibility; a declared tool never grants those by itself.
    """
    package = role(name)
    if not any(capability in tools for tools in package["mcp"].values()):
        raise ValueError(f"{name} role package does not permit {capability}")


def validate_tools(names):
    known = set(names)
    for name, package in _catalog()["roles"].items():
        declared = {tool for group in package["mcp"].values() for tool in group}
        if declared - known:
            raise ValueError(f"{name} package references unknown MCP tools: " + ", ".join(sorted(declared - known)))


def runtime_profile(name, profile):
    """An operator profile may narrow a package, never enlarge its execution options."""
    execution = role(name)["runtime"]
    if profile.get("harness") not in execution["harnesses"]:
        raise ValueError(f"{name} package does not permit this harness")
    result = dict(profile)
    for key in ("model", "reasoning"):
        option = execution[key]
        value = profile.get(key)
        if value is None:
            value = option["default"]
        if value is not None:
            _text(value, key)
        if option["allowed"] is not None and value not in option["allowed"]:
            raise ValueError(f"{name} package needs an explicit permitted {key}; inherited values cannot satisfy its allowlist")
        result[key] = value
    result["role_package"] = descriptor(name)
    return result


def generate(cue):
    # Validate the entire source before selecting the concrete export expression.
    subprocess.run([cue, "vet", "-c", str(SOURCE)], check=True, capture_output=True, text=True, timeout=30)
    exported = subprocess.run([cue, "export", str(SOURCE), "-e", "packages"], check=True,
                              capture_output=True, text=True, timeout=30)
    value = {"source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(), "catalog": json.loads(exported.stdout)}
    validate(value, value["source_sha256"])
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--cue", default="cue", help="Maintainer CUE executable (never an MCP argument)")
    args = parser.parse_args()
    try:
        value = generate(args.cue)
        if args.write:
            GENERATED.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            print("Regenerated devtools/role-packages.json")
        elif json.loads(GENERATED.read_text()) != value:
            raise ValueError("Role export differs from CUE source; regenerate devtools/role-packages.json")
        else:
            print("Role CUE source and generated export agree")
    except subprocess.CalledProcessError as error:
        parser.exit(1, error.stderr or str(error))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
