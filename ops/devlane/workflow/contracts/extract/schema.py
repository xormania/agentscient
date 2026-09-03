#!/usr/bin/env python3
"""Extractor for observation `schema` (plan SPEC section 5.1).

Reads `migrations/*.sql` under the workflow app directory and reports the
tables they declare.

Method, exactly as 5.1 prescribes: load each migration in filename order into
an in-memory `sqlite3` database with `executescript`, then read
`sqlite_master` + `PRAGMA table_info`.  That executes a *data artifact* with
the stdlib's reference SQL parser; no Python of the module under inspection
is imported or run.

Never vacuous: a rule that cannot be resolved emits {"unresolved": "<why>"}
in place of its value.  It never emits [] or 0 as a stand-in for "unknown".

Usage:
    python3 schema.py [--root <app dir>] [--out <path>|-]
"""

import argparse
import json
import os
import sqlite3
import sys

RULE_MIGRATIONS = "5.1 migrations: filenames under migrations/, sorted"
RULE_TABLES = "5.1 tables: sqlite_master + PRAGMA table_info after executescript"
RULE_COLUMNS = "5.1 tables[].columns: PRAGMA table_info, declaration order"
RULE_PK = "5.1 tables[].primary_key: PRAGMA table_info pk ordinal"


# --------------------------------------------------------------------------
# shared plumbing (each extractor is self-contained on purpose: vet.py runs
# every extract/*.py as its own process and nothing else may be importable)
# --------------------------------------------------------------------------

def unresolved(reason):
    return {"unresolved": reason}


def default_root(script_path):
    # contracts/extract/<name>.py  ->  the app directory two levels up
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(script_path))))


def emit(obs, out):
    text = json.dumps(obs, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if out is None or out == "-":
        sys.stdout.write(text)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# SQL source locating
# --------------------------------------------------------------------------

def split_statements(src):
    """Split SQL source into (start_line, end_line, text) using sqlite3's own
    statement-completeness test.  Line numbers are 1-based and inclusive.

    Leading comment blocks attach to the statement that follows them; callers
    that want only the DDL trim with `trim_to_keyword`.
    """
    out = []
    buf = ""
    start = None
    for lineno, line in enumerate(src.splitlines(keepends=True), 1):
        if buf == "" and line.strip() == "":
            continue
        if start is None:
            start = lineno
        buf += line
        if sqlite3.complete_statement(buf):
            out.append((start, lineno, buf))
            buf = ""
            start = None
    if buf.strip():
        out.append((start, start + buf.count("\n"), buf))
    return out


def trim_to_keyword(start, text, keyword):
    """Drop leading comment/blank lines so the range begins at `keyword`."""
    lines = text.splitlines(keepends=True)
    for offset, line in enumerate(lines):
        if line.lstrip().upper().startswith(keyword):
            return start + offset, "".join(lines[offset:])
    return start, text


def statement_table_name(text):
    """Return the table name of a CREATE TABLE statement, or None."""
    head = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("CREATE TABLE"):
            head = stripped
            break
    if head is None:
        return None
    rest = head[len("CREATE TABLE"):].strip()
    upper = rest.upper()
    if upper.startswith("IF NOT EXISTS"):
        rest = rest[len("IF NOT EXISTS"):].strip()
    name = ""
    for ch in rest:
        if ch.isalnum() or ch == "_":
            name += ch
        elif ch in '"`[' and not name:
            continue
        else:
            break
    return name or None


def locate_column(start, text, column):
    """Line number and verbatim text of a column declaration inside a CREATE
    TABLE statement, or (None, None) when it cannot be pinned down."""
    for offset, line in enumerate(text.splitlines()):
        stripped = line.strip().strip('"`[]')
        if not stripped.lower().startswith(column.lower()):
            continue
        tail = stripped[len(column):]
        if tail and (tail[0].isalnum() or tail[0] == "_"):
            continue
        return start + offset, line
    return None, None


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def extract(root):
    prov = {
        "extractor": "contracts/extract/schema.py",
        "method": "sqlite3 in-memory executescript of migrations/*.sql in filename order; "
                  "sqlite_master + PRAGMA table_info read back",
        "paths_relative_to": "ops/devlane/workflow",
        "facts": {},
    }
    facts = {}
    mig_dir = os.path.join(root, "migrations")

    if not os.path.isdir(mig_dir):
        why = "no migrations/ directory under the app root"
        facts["migrations"] = unresolved(why)
        facts["tables"] = unresolved(why)
        prov["facts"]["migrations"] = {
            "file": "migrations", "lines": "n/a", "text": "", "rule": RULE_MIGRATIONS,
            "unresolved": why,
        }
        return {"facts": facts, "provenance": prov}

    names = sorted(n for n in os.listdir(mig_dir) if os.path.isfile(os.path.join(mig_dir, n)))
    facts["migrations"] = names
    prov["facts"]["migrations"] = {
        "file": "migrations",
        "lines": "n/a (directory listing)",
        "text": "\n".join(names),
        "rule": RULE_MIGRATIONS,
    }

    sql_names = [n for n in names if n.lower().endswith(".sql")]
    prov["migrations_loaded"] = sql_names
    prov["migrations_not_loaded"] = [n for n in names if n not in sql_names]

    if not sql_names:
        why = "migrations/ contains no *.sql file to load"
        facts["tables"] = unresolved(why)
        return {"facts": facts, "provenance": prov}

    # Apply one migration at a time so each table can be attributed to the
    # file that created it.
    conn = sqlite3.connect(":memory:")
    sources = {}
    origin = {}
    seen = set()
    for name in sql_names:
        path = os.path.join(mig_dir, name)
        src = read_text(path)
        sources[name] = src
        try:
            conn.executescript(src)
        except sqlite3.Error as exc:
            why = "sqlite3 refused %s: %s: %s" % (name, type(exc).__name__, exc)
            facts["tables"] = unresolved(why)
            prov["facts"]["tables"] = {
                "file": "migrations/" + name,
                "lines": "1-%d" % len(src.splitlines()),
                "text": src,
                "rule": RULE_TABLES,
                "unresolved": why,
            }
            conn.close()
            return {"facts": facts, "provenance": prov}
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for (tname,) in rows:
            if tname not in seen:
                seen.add(tname)
                origin[tname] = name

    # index the CREATE TABLE statements of each source file
    located = {}
    for name, src in sources.items():
        for start, end, text in split_statements(src):
            tname = statement_table_name(text)
            if tname is None:
                continue
            tstart, ttext = trim_to_keyword(start, text, "CREATE TABLE")
            located[(name, tname)] = (tstart, end, ttext)

    tables = []
    for tname in sorted(seen):
        info = conn.execute('PRAGMA table_info("%s")' % tname.replace('"', '""')).fetchall()
        columns = []
        pk_ordinal = []
        for (_cid, cname, ctype, cnotnull, _cdflt, cpk) in info:
            columns.append({
                "name": cname,
                "type": ctype,
                "notnull": bool(cnotnull),
                "pk": bool(cpk),
            })
            if cpk:
                pk_ordinal.append((cpk, cname))
        src_name = origin.get(tname)
        key = (src_name, tname)
        entry = {
            "name": tname,
            "columns": columns,
            "primary_key": sorted(n for _o, n in pk_ordinal),
        }
        tables.append(entry)

        if key in located:
            tstart, tend, ttext = located[key]
            prov["facts"]["tables[%s]" % tname] = {
                "file": "migrations/" + src_name,
                "lines": "%d-%d" % (tstart, tend),
                "text": ttext,
                "rule": RULE_TABLES,
            }
            for col in columns:
                cline, ctext = locate_column(tstart, ttext, col["name"])
                pkey = "tables[%s].columns[%s]" % (tname, col["name"])
                if cline is None:
                    prov["facts"][pkey] = {
                        "file": "migrations/" + src_name,
                        "lines": "%d-%d" % (tstart, tend),
                        "text": ttext,
                        "rule": RULE_COLUMNS,
                        "note": "column reported by PRAGMA table_info but its "
                                "declaration line could not be located in the source",
                    }
                else:
                    prov["facts"][pkey] = {
                        "file": "migrations/" + src_name,
                        "lines": "%d-%d" % (cline, cline),
                        "text": ctext,
                        "rule": RULE_COLUMNS,
                    }
            prov["facts"]["tables[%s].primary_key" % tname] = {
                "file": "migrations/" + src_name,
                "lines": "%d-%d" % (tstart, tend),
                "text": ttext,
                "rule": RULE_PK,
                "declaration_order": [n for _o, n in sorted(pk_ordinal)],
                "note": "the fact is sorted per SPEC section 4 'sorted lists only'; "
                        "PRAGMA pk-ordinal order is recorded here",
            }
        else:
            prov["facts"]["tables[%s]" % tname] = {
                "file": "migrations/" + (src_name or "?"),
                "lines": "n/a",
                "text": "",
                "rule": RULE_TABLES,
                "note": "table exists after executescript but no CREATE TABLE "
                        "statement for it was found in the migration source "
                        "(created indirectly, e.g. by ALTER or a trigger)",
            }

    conn.close()
    facts["tables"] = tables
    return {"facts": facts, "provenance": prov}


def main(argv):
    ap = argparse.ArgumentParser(description="extract observation `schema` from migrations/*.sql")
    ap.add_argument("--root", default=None, help="workflow app directory")
    ap.add_argument("--out", default="-", help="output path, or - for stdout")
    args = ap.parse_args(argv)
    root = args.root or default_root(__file__)
    emit(extract(root), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
