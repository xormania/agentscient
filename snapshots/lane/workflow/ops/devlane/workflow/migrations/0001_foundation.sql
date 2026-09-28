-- 0001_foundation.sql — the nine tables of PLAN §3.2.
--
-- Applied once, inside a transaction, and recorded in schema_migrations with
-- the digest of this file. Extended only by adding new numbered files beside
-- it, never by rewriting what has already been applied (PLAN §6).
--
-- Everything that must be *evidence* lives in the chain, not in a table.
-- These tables are the registry, the projection, and the coordination state
-- around it; fewer tables is the point.

CREATE TABLE schema_migrations (
  version    INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  sha256     TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE work_orders (
  wo_id        TEXT PRIMARY KEY,
  objective    TEXT NOT NULL,
  kind         TEXT NOT NULL,
  kind_version INTEGER NOT NULL,
  spec_sha256  TEXT NOT NULL,
  created_at   TEXT NOT NULL
);

-- payload holds the exact canonical bytes of the complete event, its own hash
-- field included; hash is over the same object without that field. Verification
-- and projection re-parse from payload, so the columns beside it can only ever
-- be a derived index — and are checked against it.
CREATE TABLE events (
  wo_id        TEXT    NOT NULL REFERENCES work_orders(wo_id),
  seq          INTEGER NOT NULL,
  hash         TEXT    NOT NULL,
  prev         TEXT    NOT NULL,
  time         TEXT    NOT NULL,
  payload      TEXT    NOT NULL,
  state_sha256 TEXT    NOT NULL,
  PRIMARY KEY (wo_id, seq)
);
CREATE INDEX events_by_hash ON events(hash);

-- A derived read view carrying the seq/hash it was derived from. A read that
-- finds it disagreeing with the chain refuses with an integrity error.
CREATE TABLE wo_state (
  wo_id        TEXT PRIMARY KEY REFERENCES work_orders(wo_id),
  state_json   TEXT    NOT NULL,
  state_sha256 TEXT    NOT NULL,
  last_seq     INTEGER NOT NULL,
  last_hash    TEXT    NOT NULL
);

-- Convenience mirror of the tracked JSON registry. The chain's pin is the
-- authority; verify checks the two agree.
CREATE TABLE gate_kinds (
  kind        TEXT    NOT NULL,
  version     INTEGER NOT NULL,
  spec_json   TEXT    NOT NULL,
  spec_sha256 TEXT    NOT NULL,
  synced_at   TEXT    NOT NULL,
  PRIMARY KEY (kind, version)
);

CREATE TABLE artifacts (
  digest     TEXT PRIMARY KEY,
  size       INTEGER NOT NULL,
  media_type TEXT    NOT NULL,
  class      TEXT    NOT NULL,
  created_at TEXT    NOT NULL
);

-- Transient coordination, not evidence: claims and sessions are deliberately
-- not exported, and losing them on rebuild is correct (PLAN §8). The verbs
-- arrive in Slice 2; the tables are here so the schema does not move for them.
CREATE TABLE claims (
  wo_id       TEXT PRIMARY KEY REFERENCES work_orders(wo_id),
  agent       TEXT NOT NULL,
  note        TEXT NOT NULL DEFAULT '',
  acquired_at TEXT NOT NULL,
  expires_at  TEXT NOT NULL
);

CREATE TABLE sessions (
  session_id  TEXT PRIMARY KEY,
  agent       TEXT    NOT NULL,
  wo_id       TEXT    NOT NULL DEFAULT '',
  status      TEXT    NOT NULL,
  started_at  TEXT    NOT NULL,
  last_seen   TEXT    NOT NULL,
  ttl_seconds INTEGER NOT NULL
);

-- Every attempted transition, refusals included. Append-only: there are
-- deliberately no UPDATE or DELETE queries against it.
--
--   record_kind separates an attempt that changed nothing from an accepted
--   transition that recorded a failure. Both are "non-zero exit" in casual
--   speech and they mean completely different things.
--
--   exhaustiveness records that validation is fail-fast: a refusal names the
--   FIRST failed precondition, never all of them.
--
--   the before/after bindings are what keep a stored reason falsifiable. A
--   reason explains the work order only while it still has the seq, head hash
--   and stage it had when the reason was produced.
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
CREATE INDEX attempts_by_wo ON attempts(wo_id, attempted_at);
