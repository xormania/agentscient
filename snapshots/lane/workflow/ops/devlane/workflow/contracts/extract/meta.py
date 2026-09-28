#!/usr/bin/env python3
"""Extractor for observation `meta` (plan SPEC section 5.4).

Reads `meta.json` and reports its byte length, whether it parses as JSON, the
parsed value, and the top-level keys matching /version/i.

5.4 notes that the inventory reports meta.json as 0 lines and that "empty" and
"one line with no trailing newline" are not distinguishable from the inventory
alone.  This extractor does not guess: it records the byte count, the presence
of a trailing newline, and the physical line count it actually observes, in
provenance.

5.4 says explicitly that `[]` is a real observation for `version_keys` -- so an
empty `version_keys` on a file that parsed is emitted as `[]`, while a file
that did not parse yields {"unresolved": ...} for both `raw` and
`version_keys`.

Usage:
    python3 meta.py [--root <app dir>] [--out <path>|-]
"""

import argparse
import hashlib
import json
import os
import re
import sys

FILE_NAME = "meta.json"
VERSION_RE = re.compile(r"version", re.IGNORECASE)

RULE_BYTES = "5.4 bytes: byte length of meta.json"
RULE_IS_JSON = "5.4 is_json: does meta.json parse with json.loads"
RULE_RAW = "5.4 raw: the parsed JSON, or {'unresolved': 'not json'}"
RULE_VERSION_KEYS = "5.4 version_keys: top-level keys matching /version/i, sorted"


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


def extract(root):
    prov = {
        "extractor": "contracts/extract/meta.py",
        "method": "byte read of meta.json, then json.loads of the same bytes",
        "paths_relative_to": "ops/devlane/workflow",
        "facts": {},
    }
    facts = {}
    path = os.path.join(root, FILE_NAME)

    if not os.path.isfile(path):
        why = "%s is absent from the tree" % FILE_NAME
        for key in ("bytes", "is_json", "raw", "version_keys"):
            facts[key] = unresolved(why)
        prov["facts"]["bytes"] = {
            "file": FILE_NAME, "lines": "n/a", "text": "", "rule": RULE_BYTES,
            "unresolved": why,
        }
        return {"facts": facts, "provenance": prov}

    with open(path, "rb") as fh:
        raw = fh.read()

    # Physical line accounting, so "0 lines" in an inventory can be checked
    # rather than assumed.
    newline_count = raw.count(b"\n")
    ends_with_newline = raw.endswith(b"\n")
    if not raw:
        physical_lines = 0
    elif ends_with_newline:
        physical_lines = newline_count
    else:
        physical_lines = newline_count + 1
    text = raw.decode("utf-8", "replace")

    base_prov = {
        "file": FILE_NAME,
        "lines": "1-%d" % physical_lines if physical_lines else "0-0 (file is empty)",
        "text": text,
        "bytes": len(raw),
        "newline_count": newline_count,
        "ends_with_newline": ends_with_newline,
        "physical_lines": physical_lines,
        "sha256_raw": hashlib.sha256(raw).hexdigest(),
    }

    facts["bytes"] = len(raw)
    prov["facts"]["bytes"] = dict(base_prov, rule=RULE_BYTES)

    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        facts["is_json"] = False
        facts["raw"] = unresolved("not json")
        facts["version_keys"] = unresolved(
            "top-level keys are not observable: %s does not parse as JSON (%s: %s)"
            % (FILE_NAME, type(exc).__name__, exc))
        prov["facts"]["is_json"] = dict(base_prov, rule=RULE_IS_JSON,
                                        parse_error="%s: %s" % (type(exc).__name__, exc))
        prov["facts"]["raw"] = dict(base_prov, rule=RULE_RAW,
                                    parse_error="%s: %s" % (type(exc).__name__, exc))
        prov["facts"]["version_keys"] = dict(base_prov, rule=RULE_VERSION_KEYS,
                                             unresolved="file does not parse as JSON")
        return {"facts": facts, "provenance": prov}

    facts["is_json"] = True
    facts["raw"] = obj
    prov["facts"]["is_json"] = dict(base_prov, rule=RULE_IS_JSON)
    prov["facts"]["raw"] = dict(base_prov, rule=RULE_RAW)

    if isinstance(obj, dict):
        keys = sorted(k for k in obj if isinstance(k, str) and VERSION_RE.search(k))
        facts["version_keys"] = keys
        prov["facts"]["version_keys"] = dict(
            base_prov, rule=RULE_VERSION_KEYS,
            top_level_keys=sorted(obj.keys()),
            note="5.4 states that [] is a real observation for this fact")
    else:
        why = ("meta.json parsed to a %s, not an object; it has no top-level keys"
               % type(obj).__name__)
        facts["version_keys"] = unresolved(why)
        prov["facts"]["version_keys"] = dict(base_prov, rule=RULE_VERSION_KEYS,
                                             unresolved=why)

    return {"facts": facts, "provenance": prov}


def main(argv):
    ap = argparse.ArgumentParser(description="extract observation `meta` from meta.json")
    ap.add_argument("--root", default=None, help="workflow app directory")
    ap.add_argument("--out", default="-", help="output path, or - for stdout")
    args = ap.parse_args(argv)
    root = args.root or default_root(__file__)
    emit(extract(root), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
