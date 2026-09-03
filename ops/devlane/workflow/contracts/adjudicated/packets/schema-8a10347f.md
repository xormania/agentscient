# packet schema-8a10347f

observation: `schema`  definition: `#Schema`
id: `<name>-<sha256(error path)[:8]>` = `schema` + `8a10347f`

## the disagreement

error path: `facts.tables.4._columnCount`

```
facts.tables.4._columnCount: conflicting values 5 and 3:
    ./cue/schema.cue:123:19
    ./cue/schema.cue:123:39
```

## what the extractor observed

The error path could not be resolved inside `obs/schema.json`: no value at facts.tables.4._columnCount.

## provenance for that fact

### `tables[artifacts]`

- file: `migrations/0001_foundation.sql`
- lines: `64-70`
- rule: 5.1 tables: sqlite_master + PRAGMA table_info after executescript

```
CREATE TABLE artifacts (
  digest     TEXT PRIMARY KEY,
  size       INTEGER NOT NULL,
  media_type TEXT    NOT NULL,
  class      TEXT    NOT NULL,
  created_at TEXT    NOT NULL
);

```

### `tables[artifacts].columns[class]`

- file: `migrations/0001_foundation.sql`
- lines: `68-68`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  class      TEXT    NOT NULL,
```

### `tables[artifacts].columns[created_at]`

- file: `migrations/0001_foundation.sql`
- lines: `69-69`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  created_at TEXT    NOT NULL
```

### `tables[artifacts].columns[digest]`

- file: `migrations/0001_foundation.sql`
- lines: `65-65`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  digest     TEXT PRIMARY KEY,
```

### `tables[artifacts].columns[media_type]`

- file: `migrations/0001_foundation.sql`
- lines: `67-67`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  media_type TEXT    NOT NULL,
```

### `tables[artifacts].columns[size]`

- file: `migrations/0001_foundation.sql`
- lines: `66-66`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  size       INTEGER NOT NULL,
```

### `tables[artifacts].primary_key`

- file: `migrations/0001_foundation.sql`
- lines: `64-70`
- rule: 5.1 tables[].primary_key: PRAGMA table_info pk ordinal

```
CREATE TABLE artifacts (
  digest     TEXT PRIMARY KEY,
  size       INTEGER NOT NULL,
  media_type TEXT    NOT NULL,
  class      TEXT    NOT NULL,
  created_at TEXT    NOT NULL
);

```

### `tables[attempts]`

- file: `migrations/0001_foundation.sql`
- lines: `106-129`
- rule: 5.1 tables: sqlite_master + PRAGMA table_info after executescript

```
CREATE TABLE attempts (
  attempt_id     TEXT    PRIMARY KEY,
  wo_id          TEXT    NOT NULL,
  verb           TEXT    NOT NULL,
  agent          TEXT    NOT NULL,
  argv           TEXT    NOT NULL,
  attempted_at   TEXT    NOT NULL,
  duration_ms    INTEGER NOT NULL,
  exit_code      INTEGER NOT NULL,
  record_kind    TEXT    NOT NULL,
  exhaustiveness TEXT    NOT NULL DEFAULT '',
  reason         TEXT    NOT NULL DEFAULT '',
  event_appended INTEGER NOT NULL,
  seq_before     INTEGER NOT NULL,
  seq_after      INTEGER NOT NULL,
  head_before    TEXT    NOT NULL DEFAULT '',
  head_after     TEXT    NOT NULL DEFAULT '',
  stage_before   TEXT    NOT NULL DEFAULT '',
  stage_after    TEXT    NOT NULL DEFAULT '',
  stdout_tail    TEXT    NOT NULL DEFAULT '',
  stderr_tail    TEXT    NOT NULL DEFAULT '',
  stdout_sha256  TEXT    NOT NULL DEFAULT '',
  stderr_sha256  TEXT    NOT NULL DEFAULT ''
);

```

### `tables[attempts].columns[agent]`

- file: `migrations/0001_foundation.sql`
- lines: `110-110`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  agent          TEXT    NOT NULL,
```

### `tables[attempts].columns[argv]`

- file: `migrations/0001_foundation.sql`
- lines: `111-111`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  argv           TEXT    NOT NULL,
```

### `tables[attempts].columns[attempt_id]`

- file: `migrations/0001_foundation.sql`
- lines: `107-107`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  attempt_id     TEXT    PRIMARY KEY,
```

### `tables[attempts].columns[attempted_at]`

- file: `migrations/0001_foundation.sql`
- lines: `112-112`
- rule: 5.1 tables[].columns: PRAGMA table_info, declaration order

```
  attempted_at   TEXT    NOT NULL,
```

_72 further provenance entries matched this fact and are not shown here; read `obs/schema.json` for all of them._

## the contract text cited above

### `./cue/schema.cue:123`

```
  121 | 				_columnNames: [for c in Cols {c._nameValue}]
  122 | 				// PLAN.md SS3.2 lines 98-103 (inferred: the documented name set is exhaustive).
  123 | 				_columnCount: len(_columnNames) & 3
  124 | 				// PLAN.md SS3.2 lines 98-103 (stated column names; exhaustive-set reading inferred).
  125 | 				_documentedColumns: [
```

## verdict required

Write `verdicts/schema-8a10347f.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

