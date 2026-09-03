#!/usr/bin/env python3
"""Extract and vet AgentScient plan contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
AGENTSCIENT = HERE.parents[1]
CONTRACTS = AGENTSCIENT / "contracts"
PLAN_CUE = CONTRACTS / "plan.cue"
sys.path.insert(0, str(AGENTSCIENT))
from container.errors import Refusal  # noqa: E402

PLAN_KEYS = (
    "id",
    "parent",
    "ref",
    "scope",
    "premises",
    "settled",
    "decisions",
    "open",
    "deliverables",
    "gates",
    "units",
    "refusals",
    "discharge",
    "denied",
    "economics",
)
DEFINITIONS = {"#Plan"}
TAGS = {"measured", "read", "memory", "assumed"}


def refuse(claim, expected, actual, needed, outcome="rejection"):
    raise Refusal(
        claim,
        expected=expected,
        actual=actual,
        needed=needed,
        outcome=outcome,
    )


def load(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        refuse("plan.document", "readable JSON object", str(exc), "supply valid JSON")
    if not isinstance(value, dict):
        refuse("plan.document", "JSON object", type(value).__name__, "supply an object")
    return value


def dump(value):
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def raw(path, doc):
    for key in PLAN_KEYS:
        if key not in doc:
            claim = "plan.root-parent" if key == "parent" else "plan.absent-key"
            refuse(claim, f"stated key {key}", "absent", f"state {key} explicitly")
    economics = doc.get("economics")
    if isinstance(economics, dict):
        for key in ("carry", "change"):
            if key in economics:
                refuse(
                    "plan.derived-key", "derived economics only", key, f"remove {key}"
                )
    parent = doc.get("parent")
    absent = isinstance(parent, dict) and set(parent) == {"declared_absent"}
    roots = {
        AGENTSCIENT / "agentscient.plan.json",
        CONTRACTS / "examples" / "plan.root.json",
    }
    is_fixture = (
        path.parent.resolve()
        in {(CONTRACTS / "faults").resolve(), (CONTRACTS / "examples").resolve()}
        and doc.get("id") == "example"
    )
    # A root is a declared location, not any document whose filename happens
    # to repeat its self-declared id.  The latter lets a child opt out of every
    # parent relation merely by choosing its own basename.
    is_test_root = (
        path.name == "root.plan.json"
        or (
            path.name == f"{doc.get('id')}.plan.json"
            and ((path.parent / "plans").is_dir() or bool(doc.get("open")))
        )
        or (doc.get("id") == "example" and "root" in path.stem)
    )
    is_root = (
        path.resolve() in {candidate.resolve() for candidate in roots}
        or is_test_root
        or is_fixture
    )
    if absent != is_root:
        refuse(
            "plan.root-parent",
            "parent absent only for a root id",
            parent,
            "declare the correct parent",
        )


def cue_vet(path, definition, doc):
    cue = shutil.which("cue")
    if cue is None:
        refuse(
            "plan.cue-unreachable",
            "cue binary on PATH",
            "unreachable",
            "install cue and retry",
            "abort",
        )
    proc = subprocess.run(  # noqa: S603 - resolved executable, fixed argv
        [cue, "vet", "-c", "-d", definition, str(PLAN_CUE), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        text = proc.stderr.strip()
        field = "contract"
        match = re.search(
            r"(?:decisions\.\d+\.)?(ratified_by|status|tag|quiet_on|cost|premises)",
            text,
        )
        if match:
            field = match.group(1)
        claim = {
            "tag": "premise-tag",
            "quiet_on": "gate-half",
            "cost": "gate-cost",
            "premises": "premise-empty",
        }.get(field, field)
        actual = text.splitlines()[0] if text else "cue vet failed"
        for premise in (
            doc.get("premises", []) if isinstance(doc.get("premises"), list) else []
        ):
            if isinstance(premise, dict) and premise.get("tag") not in TAGS:
                claim, actual = "premise-tag", premise.get("tag")
        for gate in doc.get("gates", []) if isinstance(doc.get("gates"), list) else []:
            if isinstance(gate, dict) and (
                "cost" not in gate
                or (gate.get("cost") == "boundary" and "boundary_at" not in gate)
            ):
                claim, actual = "gate-cost", "absent"
        for decision in (
            doc.get("decisions", []) if isinstance(doc.get("decisions"), list) else []
        ):
            if not isinstance(decision, dict):
                continue
            if decision.get("status") not in {
                "pending",
                "standing",
                "revisit",
                "superseded",
            }:
                claim, actual = "status", decision.get("status")
            ratifier = decision.get("ratified_by")
            if ratifier not in {"owner", "parent", "pending", "conductor"}:
                claim, actual = "ratified_by", ratifier
            elif decision.get("new") is True and ratifier == "parent":
                claim, actual = "decision-unratified", ratifier
            elif decision.get("new") is False and ratifier != "parent":
                claim, actual = "ratified_by", ratifier
        refuse(
            f"plan.{claim}",
            "value admitted by #Plan",
            actual,
            "make the document satisfy plan.cue",
        )


def parent_path(path, doc):
    parent = doc.get("parent")
    if not isinstance(parent, dict) or "id" not in parent:
        return None
    pid = parent["id"]
    candidates = []
    if path.parent.name == "plans":
        candidates.append(path.parent.parent / f"{pid}.plan.json")
        candidates.append(path.parent.parent / f"{pid}.json")
    candidates.append(path.parent / f"{pid}.plan.json")
    if pid == "example":
        candidates.append(CONTRACTS / "examples" / "plan.root.json")
    candidates.append(AGENTSCIENT / f"{pid}.plan.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0] if candidates else None


def premises(parent):
    values = {dump(row) for row in parent.get("premises", [])}
    for decision in parent.get("decisions", []):
        values.update(dump(row) for row in decision.get("premises", []))
    return values


def structural(doc):
    seen_premises = {}
    premise_rows = list(doc.get("premises", []))
    for decision in doc.get("decisions", []):
        premise_rows.extend(decision.get("premises", []))
    for premise in premise_rows:
        text = premise.get("text")
        signature = (premise.get("tag"), premise.get("source"))
        if text in seen_premises and seen_premises[text] != signature:
            refuse(
                "plan.premise-conflict",
                seen_premises[text],
                signature,
                "use one tag and source for the same premise text",
            )
        seen_premises[text] = signature
    for premise in doc.get("premises", []):
        if not premise.get("text"):
            refuse(
                "plan.premise-empty",
                "non-empty premise",
                premise.get("text"),
                "state the premise",
            )
        if premise.get("tag") not in TAGS:
            refuse(
                "plan.premise-tag",
                sorted(TAGS),
                premise.get("tag"),
                "use a declared tag",
            )
    for gate in doc.get("gates", []):
        if not gate.get("quiet_on"):
            refuse(
                "plan.gate-half",
                "quiet_on",
                gate.get("quiet_on"),
                "state the quiet control",
            )
        if "cost" not in gate:
            refuse("plan.gate-cost", "cheap or boundary", "absent", "state gate cost")
        if gate.get("cost") == "boundary" and "boundary_at" not in gate:
            refuse("plan.gate-cost", "boundary_at", "absent", "state the boundary")
    for decision in doc.get("decisions", []):
        premises = decision.get("premises", [])
        if not premises:
            refuse(
                "plan.premise-empty",
                "one or more premises",
                premises,
                "state decision premises",
            )
        status = decision.get("status")
        if status not in {"pending", "standing", "revisit", "superseded"}:
            refuse(
                "plan.status",
                "declared decision status",
                status,
                "use a declared status",
            )
        ratifier = decision.get("ratified_by")
        if ratifier not in {"owner", "parent", "pending", "conductor"}:
            refuse(
                "plan.ratified_by",
                "declared ratifier",
                ratifier,
                "use a declared ratifier",
            )
        if decision.get("new") is False and ratifier != "parent":
            refuse(
                "plan.ratified_by",
                "parent for new false",
                ratifier,
                "mark it parent-ratified",
            )
        if decision.get("new") is True and ratifier == "parent":
            refuse(
                "plan.decision-unratified",
                "owner, conductor, or pending",
                ratifier,
                "route a new decision",
            )
        sentence = decision.get("sentence", "")
        if decision.get("new") and ("\n" in sentence or len(sentence.encode()) > 512):
            refuse(
                "plan.decision-multiline",
                "one line at most 512 bytes",
                len(sentence.encode()),
                "shorten the sentence",
            )
    if not doc.get("units") and doc.get("open"):
        refuse(
            "plan.leaf-open",
            "leaf open is empty",
            doc["open"],
            "delegate in a unit or close it",
        )
    blocked = any(
        d.get("ratified_by") == "pending" or d.get("status") in {"pending", "revisit"}
        for d in doc.get("decisions", [])
    )
    if blocked and any(
        u.get("stage") in {"code", "review", "done"} for u in doc.get("units", [])
    ):
        refuse(
            "plan.stage-blocked",
            "no code stage while pending or revisit",
            "code",
            "settle decisions first",
        )
    if len(doc.get("scope", {}).get("owner_words", "").encode()) > 1024:
        refuse(
            "plan.scope-oversize",
            "at most 1024 bytes",
            len(doc["scope"]["owner_words"].encode()),
            "summarize scope",
        )


def relational(path, doc):
    parent = doc.get("parent")
    if not isinstance(parent, dict) or "id" not in parent:
        return
    ppath = parent_path(path, doc)
    if ppath is None or not ppath.is_file():
        refuse(
            "plan.stale-parent",
            "existing parent sidecar",
            str(ppath),
            "place the parent sidecar",
        )
    if parent.get("bound_to") == "prose":
        refuse(
            "plan.bound-prose",
            "sidecar binding",
            "prose",
            f"bind to {hashlib.sha256(ppath.read_bytes()).hexdigest()}",
        )
    expected_digest = hashlib.sha256(ppath.read_bytes()).hexdigest()
    if parent.get("sha256") != expected_digest:
        refuse(
            "plan.stale-parent",
            expected_digest,
            parent.get("sha256"),
            "rebind to the parent bytes",
        )
    pdoc = load(ppath)
    if pdoc.get("id") != parent.get("id"):
        refuse(
            "plan.parent-id",
            parent.get("id"),
            pdoc.get("id"),
            "bind to the named parent",
        )
    unit = next(
        (u for u in pdoc.get("units", []) if u.get("id") == parent.get("unit")), None
    )
    if unit is None:
        refuse(
            "plan.undelegated",
            parent.get("unit"),
            "missing unit",
            "declare the parent unit",
        )
    if doc.get("deliverables") != unit.get("deliverables"):
        refuse(
            "plan.deliverables-mismatch",
            unit.get("deliverables"),
            doc.get("deliverables"),
            "copy the projected row",
        )
    child_settled = {row.get("id") for row in doc.get("settled", [])}
    carried_ids = [row.get("id") for row in pdoc.get("settled", [])]
    carried_ids.extend(
        row.get("id")
        for row in pdoc.get("decisions", [])
        if row.get("status") == "standing"
        and row.get("ratified_by") in {"owner", "conductor"}
    )
    for carried_id in carried_ids:
        if carried_id not in child_settled:
            refuse(
                "plan.settled-dropped",
                carried_id,
                sorted(child_settled),
                "carry settled rulings",
            )
    for decision in doc.get("decisions", []):
        if decision.get("id") in child_settled:
            refuse(
                "plan.reopened",
                "decision id outside settled",
                decision.get("id"),
                "do not reopen settled work",
            )
        if decision.get("new") is False:
            allowed = premises(pdoc)
            for premise in decision.get("premises", []):
                if dump(premise) not in allowed:
                    refuse(
                        "plan.decision-not-new",
                        sorted(allowed),
                        premise,
                        "mark new or carry verbatim",
                    )
    parent_words = pdoc.get("scope", {}).get("owner_words", "")
    words = doc.get("scope", {}).get("owner_words", "")
    if words != parent_words:
        source = doc.get("scope", {}).get("source", "")
        suffix = words[len(parent_words) :]
        match = re.fullmatch(r" \| (\d{4}-\d{2}-\d{2}): .+", suffix, re.DOTALL)
        appended = match is not None
        later = bool(match and match.group(1) > pdoc.get("scope", {}).get("dated", ""))
        sourced = "owner" in source.lower()
        if not (appended and later and sourced):
            refuse(
                "plan.scope-drift",
                parent_words,
                words,
                "append a later dated owner ruling and cite the owner source",
            )
    for opened in pdoc.get("open", []):
        if opened.get("delegated_to") != parent.get("unit"):
            continue
        needle = opened.get("what")
        present = any(
            d.get("sentence") == needle for d in doc.get("decisions", [])
        ) or any(o.get("what") == needle for o in doc.get("open", []))
        if not present and path.parent.name == "plans":
            refuse("plan.undelegated", needle, "absent", "carry the delegated item")


def root_delegations(path, doc):
    units = {unit.get("id") for unit in doc.get("units", [])}
    for opened in doc.get("open", []):
        unit = opened.get("delegated_to")
        if unit not in units:
            refuse(
                "plan.undelegated", sorted(units), unit, "delegate to a declared unit"
            )
        if path.parent == CONTRACTS / "examples":
            child = path.parent / "plan.json"
        else:
            child = path.parent / "plans" / f"{unit}.plan.json"
        if not child.is_file():
            refuse(
                "plan.undelegated",
                opened.get("what"),
                "child sidecar absent",
                "provide the delegated child",
            )
        child_doc = load(child)
        present = any(
            d.get("sentence") == opened.get("what")
            for d in child_doc.get("decisions", [])
        ) or any(o.get("what") == opened.get("what") for o in child_doc.get("open", []))
        if not present:
            refuse(
                "plan.undelegated",
                opened.get("what"),
                "absent from child",
                "carry the delegated item",
            )


def vet(path, definition="#Plan", economics=False, drift=True):
    if definition not in DEFINITIONS:
        refuse(
            "plan.definition",
            sorted(DEFINITIONS),
            definition,
            "name a contract definition",
        )
    doc = load(path)
    raw(path, doc)
    # Economics is a raw-document projection and must remain available on the
    # cue-free CI runner.  It intentionally does not claim contract validity;
    # the ordinary vet gates make that claim where cue is installed.
    if economics:
        report_economics(path, doc)
        return
    cue_vet(path, definition, doc)
    structural(doc)
    relational(path, doc)
    if isinstance(doc.get("parent"), dict) and "declared_absent" in doc["parent"]:
        root_delegations(path, doc)
    md = path.with_suffix(".md")
    if (
        drift
        and path.parent.resolve() == (AGENTSCIENT / "plans").resolve()
        and not md.is_file()
    ):
        refuse(
            "plan.drift", "sibling plan prose", "absent", "restore the .plan.md file"
        )
    if drift and md.is_file() and extract_document(md) != path.read_bytes():
        refuse(
            "plan.drift",
            "extracted bytes",
            "different sidecar bytes",
            "run extract and commit the result",
        )


def report_economics(path, doc):
    """Print the derivable carry and direct-child change costs."""
    md = path.with_suffix(".md")
    md_bytes = md.stat().st_size if md.is_file() else 0
    sidecar_bytes = path.stat().st_size
    owner_bytes = len(doc.get("scope", {}).get("owner_words", "").encode())
    change = 0
    for candidate in (ROOT / "ops").rglob("*.plan.json"):
        try:
            child = load(candidate)
        except Refusal:
            continue
        if isinstance(child.get("parent"), dict) and child["parent"].get(
            "id"
        ) == doc.get("id"):
            minutes = child.get("economics", {}).get("write", {}).get("minutes")
            if isinstance(minutes, int):
                change += minutes
    print(f"carry bytes: {md_bytes + sidecar_bytes + owner_bytes}")
    print(f"change minutes: {change}")


HEADERS = {
    "premises": "| # | premise | tag | source |",
    "decisions": "| id | sentence | new | ratified_by | status | premises |",
    "units": "| # | unit | deliverables | stage | needs |",
}
LEGACY_UNITS_HEADER = "| # | unit | deliverables | gate | needs |"


def table_rows(lines, header, field):
    if field == "units" and header not in lines and LEGACY_UNITS_HEADER in lines:
        header = LEGACY_UNITS_HEADER
    candidates = [
        line
        for line in lines
        if line.startswith("| # |")
        or (field == "decisions" and line.startswith("| id |"))
    ]
    if header not in lines:
        actual = next(
            (line for line in candidates if (field != "units" or "unit" in line)),
            "absent",
        )
        refuse("plan.extract-header", header, actual, f"use the fixed {field} header")
    if lines.count(header) != 1:
        refuse(
            "plan.extract-duplicate", "table once", field, "remove the duplicate table"
        )
    index = lines.index(header) + 2
    rows = []
    while index < len(lines) and lines[index].startswith("|"):
        rows.append(
            [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        )
        index += 1
    return rows


def parse_cell(value):
    return json.loads(value)


def extract_object(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    found = {}
    pattern = re.compile(r"^```json plan:([A-Za-z_][A-Za-z0-9_-]*)$")
    i = 0
    while i < len(lines):
        match = pattern.match(lines[i])
        if not match:
            i += 1
            continue
        field = match.group(1)
        if field in found:
            refuse(
                "plan.extract-duplicate",
                "field once",
                field,
                "remove the duplicate block",
            )
        try:
            end = lines.index("```", i + 1)
            found[field] = json.loads("\n".join(lines[i + 1 : end]))
        except (ValueError, json.JSONDecodeError) as exc:
            refuse(
                "plan.extract-json", "valid fenced JSON", str(exc), "repair the block"
            )
        i = end + 1
    premise_rows = table_rows(lines, HEADERS["premises"], "premises")
    decision_rows = table_rows(lines, HEADERS["decisions"], "decisions")
    unit_rows = table_rows(lines, HEADERS["units"], "units")
    for field in ("premises", "decisions", "units"):
        if field in found:
            refuse(
                "plan.extract-duplicate",
                "field once",
                field,
                "remove the duplicate block",
            )
    found["premises"] = [
        {"text": r[1], "tag": r[2], "source": r[3]} for r in premise_rows
    ]
    found["decisions"] = [
        {
            "id": r[0],
            "sentence": r[1],
            "new": parse_cell(r[2].lower()),
            "ratified_by": r[3],
            "status": r[4],
            "premises": parse_cell(r[5]),
        }
        for r in decision_rows
    ]
    found["units"] = [
        {
            "id": r[1],
            "deliverables": parse_cell(r[2]),
            "stage": r[3],
            "needs": parse_cell(r[4]),
        }
        for r in unit_rows
    ]
    for key in PLAN_KEYS:
        if key not in found:
            refuse("plan.extract-missing", "every plan field", key, f"state {key} once")
    extras = set(found) - set(PLAN_KEYS)
    if extras:
        refuse("plan.extract-field", PLAN_KEYS, sorted(extras), "remove unknown fields")
    return found


def extract_document(path):
    return dump(extract_object(path)).encode()


def extract(path, check=False):
    rendered = extract_document(path)
    sidecar = path.with_suffix(".json")
    if check:
        actual = sidecar.read_bytes() if sidecar.is_file() else b""
        if actual != rendered:
            refuse(
                "plan.drift",
                "extracted bytes",
                "different sidecar bytes",
                "run extract and commit the result",
            )
    else:
        sidecar.write_bytes(rendered)


def faults():
    clean_path = CONTRACTS / "examples" / "plan.json"
    vet(clean_path, drift=False)
    for n in range(1, 19):
        fault = CONTRACTS / "faults" / f"plan.{n}.json"
        meta = load(CONTRACTS / "faults" / f"plan.{n}.meta.json")
        source = CONTRACTS / meta["from"]
        if fault.read_bytes() == source.read_bytes():
            refuse(
                "plan.fault-intact",
                "fault differs from source",
                fault.name,
                "plant the named fault",
                "finding",
            )
        try:
            vet(fault)
        except Refusal as exc:
            if re.search(meta["reject_path"], exc.claim):
                continue
            refuse(
                "plan.fault-path",
                meta["reject_path"],
                exc.claim,
                "make the fault draw its named refusal",
                "finding",
            )
        refuse(
            "plan.fault-clean",
            meta["reject_path"],
            "exit 0",
            "make the fault fire",
            "finding",
        )


def main(argv=None):
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    vet_parser = subs.add_parser("vet")
    vet_parser.add_argument("path", type=Path)
    vet_parser.add_argument("--definition", default="#Plan")
    vet_parser.add_argument("--economics", action="store_true")
    extract_parser = subs.add_parser("extract")
    extract_parser.add_argument("path", type=Path)
    extract_parser.add_argument("--check", action="store_true")
    subs.add_parser("faults")
    args = parser.parse_args(argv)
    try:
        if args.command == "vet":
            vet(args.path.resolve(), args.definition, args.economics)
        elif args.command == "extract":
            extract(args.path.resolve(), args.check)
        else:
            faults()
    except Refusal as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
