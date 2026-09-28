#!/usr/bin/env python3
"""Extractor for observation `gatekinds` (plan SPEC section 5.3).

Reads every `gate-kinds/*.json` with the stdlib `json` parser and reports the
parsed value verbatim plus two digests: `sha256_raw` over the file's bytes as
they sit on disk, and `sha256_canonical` over
`json.dumps(obj, sort_keys=True, separators=(",",":"))` -- the same canonical
form 5.2 applies to the database's stored `spec_json`, so the two
observations are comparable digest-for-digest.

The `spec` value is emitted untouched: key order is the file's key order (no
sort_keys on output), no key is added, removed or renamed.

Never vacuous: an unparseable file yields {"unresolved": ...} for its spec
and its canonical digest, not a partial object.

Usage:
    python3 gatekinds.py [--root <app dir>] [--out <path>|-]
"""

import argparse
import hashlib
import json
import os
import sys

DIR_NAME = "gate-kinds"

RULE_KINDS = "5.3 kinds: gate-kinds/*.json, sorted by file"
RULE_RAW = "5.3 sha256_raw: sha256 over the file bytes on disk"
RULE_CANON = ("5.3 sha256_canonical: sha256 over "
              "json.dumps(obj, sort_keys=True, separators=(',',':'))")


def unresolved(reason):
    return {"unresolved": reason}


def default_root(script_path):
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(script_path))))


def emit(obs, out):
    text = json.dumps(obs, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if out is None or out == "-":
        sys.stdout.write(text)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def extract(root):
    prov = {
        "extractor": "contracts/extract/gatekinds.py",
        "method": "json.loads of each gate-kinds/*.json; digests over the raw bytes "
                  "and over the canonical dump. The parsed value is emitted untouched, "
                  "in the file's own key order.",
        "paths_relative_to": "ops/devlane/workflow",
        "file_field_form": "path relative to ops/devlane/workflow, e.g. gate-kinds/tdd.json "
                           "(SPEC section 4 provenance convention)",
        "facts": {},
    }
    facts = {}
    directory = os.path.join(root, DIR_NAME)

    if not os.path.isdir(directory):
        why = "no gate-kinds/ directory under the app root"
        facts["kinds"] = unresolved(why)
        prov["facts"]["kinds"] = {
            "file": DIR_NAME, "lines": "n/a", "text": "", "rule": RULE_KINDS,
            "unresolved": why,
        }
        return {"facts": facts, "provenance": prov}

    all_names = sorted(n for n in os.listdir(directory)
                       if os.path.isfile(os.path.join(directory, n)))
    names = [n for n in all_names if n.lower().endswith(".json")]
    prov["directory_listing"] = all_names
    prov["non_json_files_ignored"] = [n for n in all_names if n not in names]

    if not names:
        why = "gate-kinds/ contains no *.json file"
        facts["kinds"] = unresolved(why)
        prov["facts"]["kinds"] = {
            "file": DIR_NAME,
            "lines": "n/a (directory listing)",
            "text": "\n".join(all_names),
            "rule": RULE_KINDS,
            "unresolved": why,
        }
        return {"facts": facts, "provenance": prov}

    kinds = []
    for name in names:
        rel = DIR_NAME + "/" + name
        path = os.path.join(directory, name)
        with open(path, "rb") as fh:
            raw = fh.read()
        nlines = raw.count(b"\n") + (0 if raw.endswith(b"\n") or not raw else 1)
        line_range = "1-%d" % max(nlines, 1)
        text = raw.decode("utf-8", "replace")
        entry = {"file": rel, "sha256_raw": sha256_hex(raw)}
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            why = "%s is not parseable JSON: %s: %s" % (rel, type(exc).__name__, exc)
            entry["spec"] = unresolved(why)
            entry["sha256_canonical"] = unresolved(why)
        else:
            entry["spec"] = obj
            entry["sha256_canonical"] = sha256_hex(
                json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        # emit in the order the shape lists them
        kinds.append({
            "file": entry["file"],
            "spec": entry["spec"],
            "sha256_raw": entry["sha256_raw"],
            "sha256_canonical": entry["sha256_canonical"],
        })
        prov["facts"]["kinds[%s]" % rel] = {
            "file": rel,
            "lines": line_range,
            "text": text,
            "rule": RULE_KINDS,
            "bytes": len(raw),
            "ends_with_newline": raw.endswith(b"\n"),
        }
        prov["facts"]["kinds[%s].sha256_raw" % rel] = {
            "file": rel,
            "lines": line_range,
            "text": text,
            "rule": RULE_RAW,
        }
        prov["facts"]["kinds[%s].sha256_canonical" % rel] = {
            "file": rel,
            "lines": line_range,
            "text": text,
            "rule": RULE_CANON,
        }

    facts["kinds"] = sorted(kinds, key=lambda k: k["file"])
    return {"facts": facts, "provenance": prov}


def main(argv):
    ap = argparse.ArgumentParser(description="extract observation `gatekinds` from gate-kinds/*.json")
    ap.add_argument("--root", default=None, help="workflow app directory")
    ap.add_argument("--out", default="-", help="output path, or - for stdout")
    args = ap.parse_args(argv)
    root = args.root or default_root(__file__)
    emit(extract(root), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
