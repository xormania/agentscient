#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from container.errors import Refusal  # noqa: E402

CONTRACTS = HERE / "contracts"
EXAMPLE = CONTRACTS / "examples" / "registry.json"
FAULTS = CONTRACTS / "faults"
FIELDS = ("id", "layer", "module", "iface", "deps", "tags", "stores", "serves")


def refusal_map():
    cue = shutil.which("cue")
    if cue is None:
        return {"registry.cue-unreachable": {"class": "abort"}}
    proc = subprocess.run(  # noqa: S603
        [cue, "export", str(CONTRACTS / "capabilities.cue"), "-e", "#RegistryRefusals"],
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


def digest(path):
    cue = shutil.which("cue")
    if cue is None:
        refuse(
            "registry.cue-unreachable",
            "cue 0.14.1 on PATH",
            "ABSENT",
            "install cue 0.14.1 on PATH",
        )
    proc = subprocess.run(  # noqa: S603
        [cue, "export", str(CONTRACTS / "capabilities.cue"), str(path)],
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        refuse(
            "registry.contract",
            "a canonical cue export",
            proc.stderr.decode().strip(),
            "satisfy the closed registry contract",
        )
    import hashlib

    return hashlib.sha256(proc.stdout).hexdigest()


def cue_check(path):
    cue = shutil.which("cue")
    if cue is None:
        refuse(
            "registry.cue-unreachable",
            "cue 0.14.1 on PATH",
            "ABSENT",
            "install cue 0.14.1 on PATH",
        )
    proc = subprocess.run(  # noqa: S603
        [
            cue,
            "vet",
            "-c",
            "-d",
            "#Registry",
            str(CONTRACTS / "capabilities.cue"),
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        refuse(
            "registry.contract",
            "#Registry",
            (proc.stderr or proc.stdout).strip(),
            "satisfy the closed registry contract",
        )


def vet(path):
    path = Path(path)
    try:
        doc = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        refuse(
            "registry.contract",
            "a JSON registry",
            str(exc),
            "supply parseable registry JSON",
        )
    if set(doc) != {"capabilities"} or not isinstance(doc["capabilities"], list):
        refuse(
            "registry.contract",
            "closed #Registry",
            sorted(doc) if isinstance(doc, dict) else type(doc).__name__,
            "state only capabilities",
        )
    for i, cap in enumerate(doc["capabilities"]):
        missing = [key for key in FIELDS if key not in cap]
        if missing:
            refuse(
                "registry.absent-key",
                "every capability field",
                f"capabilities[{i}] missing {missing[0]}",
                "state the missing field",
            )
    cue_check(path)
    caps = doc["capabilities"]
    ids = [cap["id"] for cap in caps]
    if len(ids) != len(set(ids)):
        refuse(
            "registry.duplicate-id",
            "unique ids",
            ids,
            "rename the duplicate capability",
        )
    by_id = {cap["id"]: cap for cap in caps}
    for cap in caps:
        for dep in cap["deps"]:
            if dep["id"] not in by_id:
                refuse(
                    "registry.unknown-dep",
                    "registered dependency id",
                    dep["id"],
                    "register the dependency or change the id",
                )
            target = by_id[dep["id"]]
            names = [row["name"] for row in target["iface"]]
            if dep["iface"] not in names:
                refuse(
                    "registry.unknown-iface",
                    names,
                    dep["iface"],
                    "name a declared dependency interface",
                )
            if target["layer"] >= cap["layer"]:
                refuse(
                    "registry.layer",
                    "dep.layer < layer",
                    f"{target['layer']} !< {cap['layer']}",
                    "depend only on a lower layer",
                )
    served = [name for cap in caps for name in cap["serves"]]
    if len(served) != len(set(served)):
        refuse(
            "registry.serves-duplicate",
            "globally unique serves",
            served,
            "assign each served name once",
        )
    sidecar = path.with_name(path.name + ".digest")
    actual = sidecar.read_text().strip() if sidecar.is_file() else "ABSENT"
    expected = digest(path)
    if actual != expected:
        refuse(
            "registry.stale-export",
            expected,
            actual,
            "refresh the digest sidecar",
        )


def faults(root):
    root = Path(root)
    clean = EXAMPLE.read_bytes()
    declared = refusal_map()
    metas = sorted(root.glob("registry.*.meta.json"))
    demonstrated = {
        json.loads(meta.read_text())["reject_path"].replace("\\", "") for meta in metas
    }
    required = {
        name
        for name, row in declared.items()
        if row["class"] != "abort"
        and ".fault-" not in name
        and name != "registry.undemonstrated"
    }
    missing = sorted(required - demonstrated)
    if missing:
        refuse(
            "registry.undemonstrated",
            "a firing fixture for every refusal",
            missing[0],
            "restore the missing fault and meta",
        )
    for meta in metas:
        number = meta.name.removeprefix("registry.").removesuffix(".meta.json")
        fault = root / f"registry.{number}.json"
        claim = json.loads(meta.read_text())["reject_path"].replace("\\", "")
        if claim not in declared or not fault.is_file():
            refuse(
                "registry.undemonstrated",
                "a firing fixture for every refusal",
                claim,
                "restore the missing fault and meta",
            )
        meta_doc = json.loads(meta.read_text())
        if meta_doc.get("site") == ["digest"]:
            intact = (
                fault.with_name(fault.name + ".digest").read_bytes()
                == EXAMPLE.with_name(EXAMPLE.name + ".digest").read_bytes()
            )
        else:
            intact = json.loads(fault.read_text()) == json.loads(clean)
        if intact:
            refuse(
                "registry.fault-intact",
                "fault bytes differ from source",
                fault.name,
                "plant the declared fault",
            )
        proc = subprocess.run(  # noqa: S603
            [sys.executable, __file__, "vet", str(fault)],
            capture_output=True,
            text=True,
            check=False,
        )
        expected = claim
        if expected not in proc.stderr:
            refuse(
                "registry.fault-mismatch",
                expected,
                proc.stderr.strip(),
                "make the fixture draw its meta refusal",
            )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("vet")
    v.add_argument("path")
    f = sub.add_parser("faults")
    f.add_argument("corpus_root", nargs="?", default=str(FAULTS))
    args = parser.parse_args()
    try:
        vet(args.path) if args.cmd == "vet" else faults(args.corpus_root)
    except Refusal as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
