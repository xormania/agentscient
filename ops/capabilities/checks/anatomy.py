#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from container.errors import Refusal  # noqa: E402

CONTRACTS = HERE / "contracts"
GOOD = CONTRACTS / "examples" / "anatomy" / "goodcap"
FAULTS = CONTRACTS / "faults"
CAPS = HERE / "capabilities"


def refusal_map():
    cue = shutil.which("cue")
    if cue is None:
        return {"anatomy.cue-unreachable": {"class": "abort"}}
    proc = subprocess.run(  # noqa: S603
        [cue, "export", str(CONTRACTS / "capability.cue"), "-e", "#AnatomyRefusals"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return json.loads(proc.stdout)


def refuse(name, expected, actual, needed):
    outcome = refusal_map()[name]["class"]
    raise Refusal(
        name, outcome=outcome, expected=expected, actual=actual, needed=needed
    )


def cue_check(manifest):
    cue = shutil.which("cue")
    if cue is None:
        refuse(
            "anatomy.cue-unreachable",
            "cue 0.14.1 on PATH",
            "ABSENT",
            "install cue 0.14.1 on PATH",
        )
    p = subprocess.run(  # noqa: S603
        [
            cue,
            "vet",
            "-c",
            "-d",
            "#Manifest",
            str(CONTRACTS / "capability.cue"),
            str(manifest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode:
        refuse(
            "anatomy.manifest",
            "#Manifest",
            (p.stderr or p.stdout).strip(),
            "repair capability.json",
        )


def names_in(path):
    text = path.read_text()
    if path.suffix == ".md":
        section = re.split(r"(?m)^##\s+", text)
        text = next(
            (part for part in section if part.lower().startswith("refusals")), ""
        )
    return set(
        re.findall(r'(?:name:\s*"|`)([a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+)', text)
    )


def vet(root):
    root = Path(root)
    manifest_path = root / "capability.json"
    required = {
        "capability.json",
        "CONTRACT.md",
        "contract.cue",
        "tests",
        "faults",
        "guide.md",
    }
    entries = {p.name: p for p in root.iterdir()} if root.is_dir() else {}
    present = set(entries)
    missing = sorted(required - present)
    if missing:
        refuse(
            "anatomy.missing",
            "required anatomy entries",
            missing,
            "add the missing entry",
        )
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        refuse(
            "anatomy.manifest",
            "a JSON manifest",
            str(exc),
            "repair capability.json",
        )
    if not isinstance(manifest, dict) or any(
        key not in manifest for key in ("module", "tags")
    ):
        refuse(
            "anatomy.manifest",
            "module and tags stated in a JSON object",
            type(manifest).__name__ if not isinstance(manifest, dict) else "absent",
            "repair capability.json",
        )
    module_name = Path(manifest["module"]).name
    allowed = required | {module_name}
    if "migrates" in manifest.get("tags", []):
        allowed.add("migrations")
    extra = sorted(present - allowed)
    if extra:
        refuse(
            "anatomy.extra",
            sorted(allowed),
            extra,
            "remove unnamed entries",
        )
    cue_check(manifest_path)
    files = {"capability.json", "CONTRACT.md", "contract.cue", "guide.md", module_name}
    directories = {"tests", "faults"}
    if "migrates" in manifest["tags"]:
        directories.add("migrations")
    wrong_kind = sorted(
        name for name in files if name in entries and not entries[name].is_file()
    )
    wrong_kind += sorted(
        name for name in directories if name in entries and not entries[name].is_dir()
    )
    if wrong_kind:
        refuse(
            "anatomy.missing",
            "files and directories of the declared anatomy",
            wrong_kind,
            "replace each entry with the required file or directory",
        )
    if "migrates" in manifest.get("tags", []):
        mig = root / "migrations"
        if not mig.is_dir():
            refuse(
                "anatomy.missing",
                "migrations/ for migrates",
                "ABSENT",
                "add migrations/",
            )
        if not any(p.is_file() and p.name != ".gitkeep" for p in mig.rglob("*")):
            refuse(
                "anatomy.migrates-empty",
                "a migration entry",
                ".gitkeep only",
                "add a migration",
            )
    module = root / module_name
    try:
        tree = ast.parse(module.read_text())
    except (OSError, SyntaxError) as exc:
        refuse(
            "anatomy.unparsed",
            "a parseable module",
            str(exc),
            "repair the module syntax",
        )
    class_rows = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    classes = {n.name: n for n in class_rows}
    duplicates = {
        n.name for n in class_rows if sum(row.name == n.name for row in class_rows) > 1
    }
    for iface in manifest["iface"]:
        name = iface["name"]
        if name not in classes or name in duplicates:
            refuse(
                "anatomy.iface-unresolved",
                "a Protocol class",
                name,
                "define the declared interface class",
            )
        members = set()
        for stmt in ast.walk(classes[name]):
            if stmt is classes[name] or isinstance(stmt, ast.ClassDef):
                continue
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                members.add(stmt.name)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                members.add(stmt.target.id)
        declared = set(iface["members"])
        absent = sorted(declared - members)
        if absent:
            refuse(
                "anatomy.member-missing",
                sorted(declared),
                absent[0],
                "implement the declared member",
            )
        public = {m for m in members if not m.startswith("_")}
        undeclared = sorted(public - declared)
        if undeclared:
            refuse(
                "anatomy.member-undeclared",
                sorted(declared),
                undeclared[0],
                "declare or remove the public member",
            )
    manifest_names = {r["name"] for r in manifest["refusals"]}
    md_names = names_in(root / "CONTRACT.md")
    cue_names = names_in(root / "contract.cue")
    if (
        not manifest_names.issubset(md_names)
        or not manifest_names.issubset(cue_names)
        or (md_names & {n for n in md_names if n.startswith(manifest["id"] + ".")})
        != manifest_names
        or (cue_names & {n for n in cue_names if n.startswith(manifest["id"] + ".")})
        != manifest_names
    ):
        refuse(
            "anatomy.refusals-disagree",
            sorted(manifest_names),
            {"CONTRACT.md": sorted(md_names), "contract.cue": sorted(cue_names)},
            "make all refusal sets agree",
        )
    demonstrated = {p.stem for p in (root / "faults").iterdir() if p.is_file()}
    absent = sorted(manifest_names - demonstrated)
    if absent:
        refuse(
            "anatomy.undemonstrated",
            sorted(manifest_names),
            absent[0],
            "ship a fault fixture for every refusal",
        )


def faults(root):
    root = Path(root)
    declared = refusal_map()
    metas = sorted(root.glob("anatomy.*.meta.json"))
    demonstrated = {
        json.loads(meta.read_text())["reject_path"].replace("\\", "") for meta in metas
    }
    required = {
        name
        for name, row in declared.items()
        if row["class"] != "abort" and ".fault-" not in name
    }
    missing = sorted(required - demonstrated)
    if missing:
        refuse(
            "anatomy.undemonstrated",
            "a firing fixture for every refusal",
            missing[0],
            "restore the missing fixture",
        )
    for m in metas:
        number = m.name.removeprefix("anatomy.").removesuffix(".meta.json")
        d = root / f"anatomy.{number}"
        claim = json.loads(m.read_text())["reject_path"].replace("\\", "")
        if claim not in declared or not d.is_dir():
            refuse(
                "anatomy.undemonstrated",
                "a firing fixture for every refusal",
                claim,
                "restore the missing fixture",
            )

        # A byte-identical staged directory is an intact fault.
        def snapshot(p):
            return {
                str(x.relative_to(p)): x.read_bytes()
                for x in p.rglob("*")
                if x.is_file()
            }

        if snapshot(d) == snapshot(GOOD):
            refuse(
                "anatomy.fault-intact",
                "fault differs from source",
                d.name,
                "plant the declared fault",
            )
        p = subprocess.run(  # noqa: S603
            [sys.executable, __file__, "vet", str(d)],
            capture_output=True,
            text=True,
            check=False,
        )
        expected = claim
        if expected not in p.stderr:
            refuse(
                "anatomy.fault-mismatch",
                expected,
                p.stderr.strip(),
                "make the fixture draw its meta refusal",
            )


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("vet")
    v.add_argument("path", nargs="?")
    f = sub.add_parser("faults")
    f.add_argument("corpus_root", nargs="?", default=str(FAULTS))
    a = ap.parse_args()
    try:
        if a.cmd == "faults":
            faults(a.corpus_root)
        elif a.path:
            vet(a.path)
        else:
            dirs = [p for p in CAPS.iterdir() if p.is_dir()] if CAPS.is_dir() else []
            for p in sorted(dirs):
                vet(p)
            if not dirs:
                print("0 capability directory(ies) scanned — none was looked at")
    except Refusal as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
