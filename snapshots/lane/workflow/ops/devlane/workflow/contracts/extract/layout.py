#!/usr/bin/env python3
"""Extractor for observation `layout` (plan SPEC section 5.5).

Walks the workflow app directory and reports the files and directories it
contains, excluding `contracts/` (this tooling), `__pycache__/` and `*.pyc`.
Then it looks for the .gitignore rule that would cover `wf.db`.

5.5 marks the location of that ignore rule as a GUESS ("at repo root or under
ops/").  This extractor searches both, records every candidate path it
considered in provenance, and distinguishes the two outcomes that a bare `[]`
would blur together:

  * at least one .gitignore exists and none of its lines contains "db"
    -> `[]`, a real observation;
  * no .gitignore exists anywhere in the searched scope
    -> {"unresolved": ...}, because "no rule found" and "nowhere to look"
       are not the same answer.

Usage:
    python3 layout.py [--root <app dir>] [--repo-root <path>] [--out <path>|-]
"""

import argparse
import json
import os
import sys

EXCLUDED_DIRS = ("contracts", "__pycache__")
EXCLUDED_SUFFIXES = (".pyc",)
NEEDLE = "db"

RULE_FILES = ("5.5 files: paths relative to ops/devlane/workflow, sorted, "
              "excluding contracts/, __pycache__/, *.pyc")
RULE_DIRS = "5.5 dirs: directories relative to ops/devlane/workflow, sorted, same exclusions"
RULE_GITIGNORE = ('5.5 gitignore: every line of every .gitignore at repo root or under '
                  'ops/ whose text contains "db"')


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


def find_repo_root(app_root):
    """Locate the repo root and say how it was decided (no absolute path is
    ever emitted -- only the method)."""
    probe = os.path.abspath(app_root)
    while True:
        if os.path.exists(os.path.join(probe, ".git")):
            return probe, "directory containing a .git entry, found by walking up from the app root"
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    parts = os.path.abspath(app_root).split(os.sep)
    if "ops" in parts:
        idx = parts.index("ops")
        root = os.sep.join(parts[:idx]) or os.sep
        return root, ("parent of the ops/ directory (no .git entry exists anywhere "
                      "above the app root in this tree)")
    return os.path.dirname(os.path.abspath(app_root)), \
        "parent of the app root (neither a .git entry nor a ops/ component was found)"


def walk_app(root):
    files = []
    dirs = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir != ".":
            dirs.append(rel_dir)
        for name in sorted(filenames):
            if name.endswith(EXCLUDED_SUFFIXES):
                continue
            rel = name if rel_dir == "." else rel_dir + "/" + name
            files.append(rel)
    return sorted(files), sorted(dirs)


def gitignore_candidates(repo_root):
    """Every .gitignore at repo root or under ops/, sorted, as (rel, abs)."""
    found = []
    top = os.path.join(repo_root, ".gitignore")
    if os.path.isfile(top):
        found.append((".gitignore", top))
    dev = os.path.join(repo_root, "ops")
    if os.path.isdir(dev):
        for dirpath, dirnames, filenames in os.walk(dev):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
            if ".gitignore" in filenames:
                abspath = os.path.join(dirpath, ".gitignore")
                rel = os.path.relpath(abspath, repo_root).replace(os.sep, "/")
                found.append((rel, abspath))
    return sorted(set(found))


def extract(root, repo_root_override=None):
    if repo_root_override:
        repo_root = os.path.abspath(repo_root_override)
        how = "supplied on the command line with --repo-root"
    else:
        repo_root, how = find_repo_root(root)

    prov = {
        "extractor": "contracts/extract/layout.py",
        "method": "os.walk of the app directory; .gitignore search at repo root and under ops/",
        "paths_relative_to": "ops/devlane/workflow",
        "gitignore_paths_relative_to": "the repo root",
        "repo_root_determined_by": how,
        "exclusions": {"dirs": list(EXCLUDED_DIRS), "suffixes": list(EXCLUDED_SUFFIXES)},
        "facts": {},
    }
    facts = {}

    if not os.path.isdir(root):
        why = "the app root directory does not exist"
        facts["files"] = unresolved(why)
        facts["dirs"] = unresolved(why)
        facts["gitignore"] = unresolved(why)
        prov["facts"]["files"] = {"file": ".", "lines": "n/a", "text": "",
                                  "rule": RULE_FILES, "unresolved": why}
        return {"facts": facts, "provenance": prov}

    files, dirs = walk_app(root)
    facts["files"] = files
    facts["dirs"] = dirs

    prov["facts"]["files"] = {
        "file": ".",
        "lines": "n/a (directory walk, %d entries)" % len(files),
        "text": "\n".join(files),
        "rule": RULE_FILES,
    }
    prov["facts"]["dirs"] = {
        "file": ".",
        "lines": "n/a (directory walk, %d entries)" % len(dirs),
        "text": "\n".join(dirs),
        "rule": RULE_DIRS,
    }
    for rel in files:
        abspath = os.path.join(root, rel.replace("/", os.sep))
        parent = os.path.dirname(rel) or "."
        prov["facts"]["files[%s]" % rel] = {
            "file": rel,
            "lines": "n/a (directory entry in %s)" % parent,
            "text": os.path.basename(rel),
            "rule": RULE_FILES,
            "bytes": (os.path.getsize(abspath) if os.path.isfile(abspath)
                      else "not a regular file"),
            "is_symlink": os.path.islink(abspath),
        }
    for rel in dirs:
        parent = os.path.dirname(rel) or "."
        prov["facts"]["dirs[%s]" % rel] = {
            "file": rel,
            "lines": "n/a (directory entry in %s)" % parent,
            "text": os.path.basename(rel),
            "rule": RULE_DIRS,
        }

    # ---- gitignore (GUESS: where the ignore rule lives) ----
    candidates = gitignore_candidates(repo_root)
    prov["gitignore_files_searched"] = [rel for rel, _abs in candidates]
    prov["gitignore_search_scope"] = ["<repo root>/.gitignore",
                                      "every .gitignore under <repo root>/ops/"]

    if not candidates:
        why = ("no .gitignore exists at the repo root or anywhere under ops/ in this "
               "tree, so the rule 5.5 asks about has nowhere to live here; this is "
               "not the same as a .gitignore that carries no db line")
        facts["gitignore"] = unresolved(why)
        prov["facts"]["gitignore"] = {
            "file": ".gitignore",
            "lines": "n/a",
            "text": "",
            "rule": RULE_GITIGNORE,
            "unresolved": why,
        }
    else:
        entries = []
        loose = []
        for rel, abspath in candidates:
            with open(abspath, "r", encoding="utf-8", newline="") as fh:
                content = fh.read()
            for lineno, line in enumerate(content.splitlines(), 1):
                if NEEDLE in line:
                    entries.append({"file": rel, "line": line})
                    prov["facts"]["gitignore[%s:%d]" % (rel, lineno)] = {
                        "file": rel,
                        "lines": "%d-%d" % (lineno, lineno),
                        "text": line,
                        "rule": RULE_GITIGNORE,
                    }
                elif NEEDLE in line.lower():
                    loose.append({"file": rel, "line": line, "lineno": lineno})
        facts["gitignore"] = sorted(entries, key=lambda e: (e["file"], e["line"]))
        prov["facts"]["gitignore"] = {
            "file": ", ".join(rel for rel, _a in candidates),
            "lines": "n/a (line-filtered across %d file(s))" % len(candidates),
            "text": "\n".join("%s: %s" % (e["file"], e["line"]) for e in entries),
            "rule": RULE_GITIGNORE,
            "match": 'case-sensitive substring "db", as 5.5 words it',
            "case_insensitive_only_matches": loose,
            "note": ("an empty list here means the .gitignore files listed in "
                     "gitignore_files_searched were read and none carried a db line"),
        }

    return {"facts": facts, "provenance": prov}


def main(argv):
    ap = argparse.ArgumentParser(description="extract observation `layout` from a directory walk")
    ap.add_argument("--root", default=None, help="workflow app directory")
    ap.add_argument("--repo-root", default=None, help="override the repo root used for .gitignore search")
    ap.add_argument("--out", default="-", help="output path, or - for stdout")
    args = ap.parse_args(argv)
    root = args.root or default_root(__file__)
    emit(extract(root, args.repo_root), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
