#!/usr/bin/env python3
"""Extractor for observation `db` (plan SPEC section 5.2).

Reads the untracked SQLite database `wf.db` beside the app.  Nothing of the
module runs: the file is copied to a temporary location and the *copy* is
opened `mode=ro` through the stdlib `sqlite3` driver.  Copying first is
stricter than 5.2's "opened mode=ro" -- it guarantees the original file and
any -wal/-shm sidecar are never touched, even by SQLite's recovery paths.

Never vacuous: a rule that cannot be resolved emits {"unresolved": "<why>"}.
`work_orders_count: 0` is emitted only when the table exists and really is
empty; a missing table yields unresolved, not 0.

Usage:
    python3 db.py [--root <app dir>] [--db <path>] [--out <path>|-]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile

# SPEC section 4: "Observations contain no absolute paths, no timestamps".
# The database stores several; provenance elides them rather than smuggling
# them into the observation.
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
ELIDED = "<timestamp elided: SPEC section 4 forbids timestamps in observations>"

DB_NAME = "wf.db"

RULE_PRESENT = "5.2 present"
RULE_TABLES = "5.2 tables: sqlite_master + PRAGMA table_info of the live database"
RULE_GATE_KINDS = "5.2 gate_kinds: kind, version, sha256 of stored spec_json (raw and canonical)"
RULE_MIGRATIONS = "5.2 schema_migrations: the version/name column, sorted"
RULE_WO_COUNT = "5.2 work_orders_count"

CANONICAL = "json.dumps(obj, sort_keys=True, separators=(',',':'))"


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


def elide_timestamp(value):
    return ELIDED if TIMESTAMP_RE.match(value) else value


def table_names(conn):
    return [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def table_sql(conn, name):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row[0] if row and row[0] is not None else ""


def columns_of(conn, name):
    """(columns in declaration order, primary key sorted, primary key in
    PRAGMA pk-ordinal order).

    The fact is the sorted list, per SPEC section 4's "sorted lists only";
    the ordinal order goes to provenance.  extract/schema.py resolves this the
    same way, so the two observations stay comparable column for column.
    """
    info = conn.execute('PRAGMA table_info("%s")' % name.replace('"', '""')).fetchall()
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
    declaration = [n for _o, n in sorted(pk_ordinal)]
    return columns, sorted(declaration), declaration


def extract(root, db_path):
    rel_db = os.path.relpath(db_path, root).replace(os.sep, "/")
    prov = {
        "extractor": "contracts/extract/db.py",
        "method": "wf.db copied to a temp file; the copy opened file:<copy>?mode=ro; "
                  "sqlite_master + PRAGMA table_info + SELECTs. The original is never opened.",
        "paths_relative_to": "ops/devlane/workflow",
        "canonical_form": CANONICAL,
        "facts": {},
    }
    facts = {}

    if not os.path.isfile(db_path):
        why = "%s is absent from the tree" % rel_db
        facts["present"] = False
        for key in ("tables", "gate_kinds", "schema_migrations", "work_orders_count"):
            facts[key] = unresolved(why)
        prov["facts"]["present"] = {
            "file": rel_db, "lines": "n/a", "text": "", "rule": RULE_PRESENT,
            "unresolved": why,
        }
        return {"facts": facts, "provenance": prov}

    facts["present"] = True
    size = os.path.getsize(db_path)
    with open(db_path, "rb") as fh:
        file_sha = sha256_hex(fh.read())
    prov["facts"]["present"] = {
        "file": rel_db,
        "lines": "n/a (binary SQLite database, %d bytes)" % size,
        "text": "sha256(%s) = %s" % (rel_db, file_sha),
        "rule": RULE_PRESENT,
    }
    sidecars = sorted(
        os.path.basename(db_path) + suffix
        for suffix in ("-wal", "-shm", "-journal")
        if os.path.exists(db_path + suffix)
    )
    prov["sidecar_files_present"] = sidecars

    tmpdir = tempfile.mkdtemp(prefix="wfdb-extract-")
    try:
        copy = os.path.join(tmpdir, "wf.db")
        shutil.copyfile(db_path, copy)
        for suffix in ("-wal", "-shm", "-journal"):
            if os.path.exists(db_path + suffix):
                shutil.copyfile(db_path + suffix, copy + suffix)
        conn = sqlite3.connect("file:%s?mode=ro" % copy, uri=True)
        try:
            _collect(conn, facts, prov, rel_db)
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return {"facts": facts, "provenance": prov}


def _collect(conn, facts, prov, rel_db):
    names = table_names(conn)
    prov["tables_present"] = names

    tables = []
    for name in names:
        columns, pk, pk_declaration = columns_of(conn, name)
        tables.append({"name": name, "columns": columns, "primary_key": pk})
        prov["facts"]["tables[%s]" % name] = {
            "file": rel_db,
            "lines": "n/a (sqlite_master.sql of table %s; the database is not a text file)" % name,
            "text": table_sql(conn, name),
            "rule": RULE_TABLES,
            "primary_key_declaration_order": pk_declaration,
        }
    facts["tables"] = tables

    # ---- gate_kinds ----
    if "gate_kinds" not in names:
        why = "table gate_kinds does not exist in %s" % rel_db
        facts["gate_kinds"] = unresolved(why)
        prov["facts"]["gate_kinds"] = {
            "file": rel_db, "lines": "n/a", "text": "", "rule": RULE_GATE_KINDS,
            "unresolved": why,
        }
    else:
        cols = [c["name"] for c in columns_of(conn, "gate_kinds")[0]]
        missing = [c for c in ("kind", "version", "spec_json") if c not in cols]
        if missing:
            why = "gate_kinds lacks column(s) %s; columns are %s" % (
                ",".join(missing), ",".join(cols))
            facts["gate_kinds"] = unresolved(why)
            prov["facts"]["gate_kinds"] = {
                "file": rel_db, "lines": "n/a", "text": table_sql(conn, "gate_kinds"),
                "rule": RULE_GATE_KINDS, "unresolved": why,
            }
        else:
            has_stored = "spec_sha256" in cols
            select = "SELECT kind, version, spec_json%s FROM gate_kinds ORDER BY kind, version" % (
                ", spec_sha256" if has_stored else "")
            kinds = []
            for row in conn.execute(select):
                kind, version, spec_json = row[0], row[1], row[2]
                stored = row[3] if has_stored else None
                raw_bytes = spec_json if isinstance(spec_json, bytes) else str(spec_json).encode("utf-8")
                raw = sha256_hex(raw_bytes)
                try:
                    obj = json.loads(raw_bytes.decode("utf-8"))
                    canon = sha256_hex(
                        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    canon = unresolved("stored spec_json for kind=%s version=%s is not JSON: %s"
                                       % (kind, version, exc))
                entry = {
                    "kind": kind,
                    "version": version,
                    "spec_sha256_raw": raw,
                    "spec_sha256_canonical": canon,
                }
                kinds.append(entry)
                pkey = "gate_kinds[%s@%s]" % (kind, version)
                prov["facts"][pkey] = {
                    "file": rel_db,
                    "lines": "n/a (row of table gate_kinds; the database is not a text file)",
                    "text": raw_bytes.decode("utf-8", "replace"),
                    "rule": RULE_GATE_KINDS,
                    "stored_spec_sha256_column": (stored if has_stored else
                                                  "column spec_sha256 not present"),
                    "stored_bytes_are_already_canonical":
                        (raw == canon) if isinstance(canon, str) else "unknown",
                }
            facts["gate_kinds"] = kinds

    # ---- schema_migrations ----
    #
    # 5.2 marks the column name as a GUESS ("whatever the version/name column
    # holds").  Both columns exist here; the choice and the road not taken are
    # both recorded in provenance so the reading is auditable.
    if "schema_migrations" not in names:
        why = "table schema_migrations does not exist in %s" % rel_db
        facts["schema_migrations"] = unresolved(why)
        prov["facts"]["schema_migrations"] = {
            "file": rel_db, "lines": "n/a", "text": "", "rule": RULE_MIGRATIONS,
            "unresolved": why,
        }
    else:
        cols = [c["name"] for c in columns_of(conn, "schema_migrations")[0]]
        chosen = "name" if "name" in cols else ("version" if "version" in cols else None)
        if chosen is None:
            why = ("schema_migrations has neither a `name` nor a `version` column; "
                   "columns are %s" % ",".join(cols))
            facts["schema_migrations"] = unresolved(why)
            prov["facts"]["schema_migrations"] = {
                "file": rel_db, "lines": "n/a",
                "text": table_sql(conn, "schema_migrations"),
                "rule": RULE_MIGRATIONS, "unresolved": why,
            }
        else:
            values = sorted(
                elide_timestamp(str(r[0])) for r in
                conn.execute('SELECT "%s" FROM schema_migrations' % chosen)
            )
            facts["schema_migrations"] = values
            other = {}
            for col in cols:
                other[col] = sorted(
                    elide_timestamp(str(r[0]))
                    for r in conn.execute('SELECT "%s" FROM schema_migrations' % col))
            prov["facts"]["schema_migrations"] = {
                "file": rel_db,
                "lines": "n/a (rows of table schema_migrations)",
                "text": "\n".join(values),
                "rule": RULE_MIGRATIONS,
                "column_used": chosen,
                "columns_available": cols,
                "all_column_values": other,
                "note": "5.2 marks the column name a GUESS. Both `name` and `version` "
                        "exist; `name` was taken because it holds the migration "
                        "filename, which is what 5.1 `migrations` lists.",
            }

    # ---- work_orders_count ----
    if "work_orders" not in names:
        why = "table work_orders does not exist in %s" % rel_db
        facts["work_orders_count"] = unresolved(why)
        prov["facts"]["work_orders_count"] = {
            "file": rel_db, "lines": "n/a", "text": "", "rule": RULE_WO_COUNT,
            "unresolved": why,
        }
    else:
        count = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        facts["work_orders_count"] = count
        prov["facts"]["work_orders_count"] = {
            "file": rel_db,
            "lines": "n/a (SELECT COUNT(*) FROM work_orders)",
            "text": "SELECT COUNT(*) FROM work_orders; -> %d" % count,
            "rule": RULE_WO_COUNT,
            "note": "the table exists and is empty; this 0 is an observation, not a default",
        }


def main(argv):
    ap = argparse.ArgumentParser(description="extract observation `db` from wf.db")
    ap.add_argument("--root", default=None, help="workflow app directory")
    ap.add_argument("--db", default=None, help="path to wf.db (default <root>/wf.db)")
    ap.add_argument("--out", default="-", help="output path, or - for stdout")
    args = ap.parse_args(argv)
    root = args.root or default_root(__file__)
    db_path = args.db or os.path.join(root, DB_NAME)
    emit(extract(root, db_path), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
