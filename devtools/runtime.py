"""Operator-owned role policy and vendor availability, resolved behind MCP."""

import hashlib
import json
import shutil
from pathlib import Path

from .adapters import names as adapter_names
from .adapters import registry as adapter_registry
from .harnesses import get as harness_adapter
from .role_packages import adapter, catalog, default_role, names_for_adapter, runtime_profile
from .store import canonical, stamp


def co_role(scope=None):
    """Use the appointed interface's bound identity, or its initial catalog default."""
    role = scope["role"] if scope else default_role("co")
    if adapter(role) != "co":
        raise ValueError("The appointed CO's current binding must use the CO behavior.")
    return role


def defaults(directory):
    from .profiles import write_json

    directory = Path(directory)
    choices = list(adapter_names("harness"))
    vendors = {name: harness_adapter(name).vendor for name in choices}
    write_json(
        directory / "roles.json",
        {
            "version": 1,
            "max_sessions": 12,
            "profiles": {h: {"harness": h, "vendor": v, "model": None, "reasoning": None} for h, v in vendors.items()},
            "roles": {role: list(package["runtime"]["harnesses"])
                      for role, package in catalog()["roles"].items()},
        },
    )
    write_json(
        directory / "vendors.json",
        {
            "version": 1,
            "vendors": {v: {"available": False, "reason": "Enable after login"} for v in vendors.values()},
        },
    )


def load(directory):
    directory = Path(directory)
    policy = json.loads((directory / "roles.json").read_text())
    availability = json.loads((directory / "vendors.json").read_text())
    if not isinstance(policy, dict) or set(policy) != {"version", "max_sessions", "profiles", "roles"}:
        raise ValueError("roles.json needs version, max_sessions, profiles and roles")
    if not isinstance(availability, dict) or set(availability) != {"version", "vendors"}:
        raise ValueError("vendors.json needs version and vendors")
    if policy["version"] != 1 or availability["version"] != 1:
        raise ValueError("Unsupported runtime config version")
    if type(policy["max_sessions"]) is not int or not 1 <= policy["max_sessions"] <= 100:
        raise ValueError("max_sessions must be between 1 and 100")
    profiles, roles, vendors = policy["profiles"], policy["roles"], availability["vendors"]
    if not isinstance(profiles, dict) or not profiles or not isinstance(vendors, dict):
        raise ValueError("profiles and vendors must be objects")
    if not isinstance(roles, dict) or not roles:
        raise ValueError("roles.json needs a nonempty map of configured role preferences")
    unknown = set(roles) - set(catalog()["roles"])
    if unknown:
        raise ValueError("roles.json references unknown catalog roles: " + ", ".join(sorted(map(str, unknown))))
    for vendor, row in vendors.items():
        if not isinstance(row, dict) or set(row) - {"available", "reason", "reset_at"}:
            raise ValueError("Unknown vendor availability field")
        if type(row.get("available")) is not bool or any(
            key in row and not isinstance(row[key], str) for key in ("reason", "reset_at")
        ):
            raise ValueError("Vendor availability needs a boolean and optional reason/reset_at text")
    for name, row in profiles.items():
        if not isinstance(row, dict) or set(row) - {"harness", "vendor", "model", "reasoning", "binary", "provider"}:
            raise ValueError("Unknown runtime profile field")
        if row.get("harness") not in adapter_names("harness") or row.get("vendor") not in vendors:
            raise ValueError("Every profile needs a supported harness and a declared vendor")
        for key in ("model", "reasoning", "binary", "provider"):
            if row.get(key) is not None and (not isinstance(row[key], str) or not row[key] or "\0" in row[key]):
                raise ValueError(f"{name}.{key} must be a nonempty string or null")
        if row.get("provider") and not harness_adapter(row["harness"]).supports_provider:
            raise ValueError("provider is not supported by this harness adapter")
    for role, choices in roles.items():
        if (
            not isinstance(choices, list)
            or not choices
            or any(not isinstance(c, str) or c not in profiles for c in choices)
        ):
            raise ValueError(f"{role} needs an ordered nonempty list of known profiles")
        if len(set(choices)) != len(choices):
            raise ValueError("Duplicate runtime preference")
        for choice in choices:
            runtime_profile(role, profiles[choice])
    revision = hashlib.sha256(canonical([policy, availability, catalog(), adapter_registry()]).encode()).hexdigest()
    return policy, availability, revision


def resolve(directory, role, *, installed=True, profile=None):
    policy, availability, revision = load(directory)
    if role not in policy["roles"]:
        raise ValueError(f"Configure {role} preferences in roles.json before assigning that role.")
    if profile is not None and profile not in policy["roles"][role]:
        raise ValueError("Select a profile from this role's configured preferences")
    skipped = []
    for name in [profile] if profile is not None else policy["roles"][role]:
        profile = policy["profiles"][name]
        vendor = availability["vendors"][profile["vendor"]]
        reason = None
        binary = profile.get("binary") or profile["harness"]
        if not vendor["available"]:
            reason = vendor.get("reason") or "Vendor disabled"
        elif installed and not shutil.which(binary):
            reason = "Harness executable is not installed"
        if reason:
            skipped.append({"profile": name, "vendor": profile["vendor"], "reason": reason})
            continue
        return {
            **runtime_profile(role, profile),
            "binary": binary,
            "selection": {
                "role": role,
                "profile": name,
                "revision": revision,
                "skipped": skipped,
            },
        }
    raise ValueError(f"No runtime available for {role}; inspect operator runtime_status and vendor availability.")


def allocate(store, db, config, role, existing=None):
    """Called inside the work allocation transaction; failed batches leave no seats."""
    if existing:
        return dict(db.execute("SELECT * FROM members WHERE name=?", (existing["member"],)).fetchone())
    policy, _, _ = load(store.directory)
    interfaces = names_for_adapter("co")
    query = "SELECT count(*) FROM member_bindings"
    if interfaces:
        query += " WHERE role NOT IN (" + ",".join("?" for _ in interfaces) + ")"
    count = db.execute(query, interfaces).fetchone()[0]
    if count >= policy["max_sessions"]:
        raise ValueError("No available collaborator capacity; stop/release finished work or ask the operator.")
    selected = resolve(store.directory, role)
    workspace = config["members"][0]["workspace"]
    # Reuse an unbound, stopped dynamic seat. Roles are not fixed seat names.
    row = db.execute(
        "SELECT m.* FROM members m LEFT JOIN member_bindings b ON m.name=b.member "
        "WHERE m.name LIKE 'runtime-%' AND b.member IS NULL AND m.pid IS NULL AND m.state IN ('stopped','failed') "
        "ORDER BY m.name LIMIT 1"
    ).fetchone()
    if row:
        name = row["name"]
        db.execute("UPDATE members SET harness=?,updated=? WHERE name=?", (selected["harness"], stamp(), name))
    else:
        index = 1
        while db.execute("SELECT 1 FROM members WHERE name=?", (f"runtime-{index}",)).fetchone():
            index += 1
        name = f"runtime-{index}"
        db.execute(
            "INSERT INTO members(name,harness,workspace,updated) VALUES (?,?,?,?)",
            (name, selected["harness"], workspace, stamp()),
        )
    return {"name": name, "workspace": workspace, **selected}


def status(store):
    policy, vendors, revision = load(store.directory)
    choices = {}
    for role in catalog()["roles"]:
        try:
            choices[role] = resolve(store.directory, role)
        except ValueError as error:
            choices[role] = {"error": str(error)}
    return {
        "revision": revision,
        "policy": policy,
        "availability": vendors,
        "resolved": choices,
        "sessions": store.members(),
        "note": "Live sessions keep their launch snapshot. reset_at is advisory.",
    }
