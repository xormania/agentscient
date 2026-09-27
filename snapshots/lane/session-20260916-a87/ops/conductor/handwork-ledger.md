# The handwork ledger — contract

Standing: PROPOSED. The owner's mandate is standing law ("anytime you
find yourself doing something by hand - you need to log it somewhere -
SQLite if possible"; "maybe you have to log it to get temp permission to
do it?", 2026-08-31). The first instrument honoring it lived in a
session scratchpad and died with the session — seed-learnings entry 5:
**operational instruments must be repo citizens**. This contract brings
the ledger in-tree against the database that survived it.

Declare-before-do is the grant: naming the by-hand act, why it cannot
wait for a lever, and which lever is missing IS the temporary
permission. Settling with evidence closes it. Recurring absence is a
demand signal for the next lever to build.

## Instrument

`python3 ops/conductor/tools/hand.py <verb> …`, stdlib only (sqlite3,
argparse, subprocess only for evidence verification). Database:
`~/.local/state/agentscient/handwork.db`.

## The database is the schema of record

The surviving table is adopted verbatim — 19 rows of session history
predate this tool and must remain readable:

```sql
CREATE TABLE handwork(
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session TEXT NOT NULL,
    agent TEXT NOT NULL, action TEXT NOT NULL, why_by_hand TEXT NOT NULL,
    missing_lever TEXT, evidence TEXT, lever_class TEXT, scope TEXT,
    ttl_s INTEGER, status TEXT DEFAULT 'settled', settled_ts TEXT,
    verified INTEGER, late INTEGER DEFAULT 0, settle_note TEXT)
```

`CREATE TABLE IF NOT EXISTS` with exactly this shape; no destructive
migration, ever. Historical rows with NULL `lever_class` stay as they
are.

## Identity

Every writing verb requires `WF_AGENT` matching `.+ <addr>`; `agent`
and `session` (from `CLAUDE_CODE_SESSION_ID`, else `CLAUDE_SESSION_ID`,
else `unknown`) are
stamped on every row. Reads need no identity.

## The lever registry

Classes, each with an optional probe path relative to the repo root; a
probe that exists means the lever is built:

| class | probe |
|---|---|
| dispatch | `ops/devlane/dispatch/launch.py` |
| collect | `ops/devlane/dispatch/launch.py` |
| gate-run | `ops/conductor/tools/gate.sh` |
| land | `ops/conductor/tools/land.py` |
| verify-record | — |
| pr-open | — |
| bulk-push | — |
| amend | — |
| worktree | — |
| log-tooling | — |
| other | — |

`declare` for a class whose probe path exists **refuses**: the lever is
built; use it. The table is data in the tool, amended by commit — a new
lever's landing flips its class from grantable to refused in the same
PR that builds it.

## Verbs

- `declare ACTION WHY LEVER_CLASS [--scope S] [--ttl MIN]` — opens a
  grant (status `open`, ttl default 30 minutes), prints the grant id and
  the standing reminder. After inserting, count open-plus-settled rows
  naming the same class among `other`/unprobed classes: at three or
  more, print the recurrence note — "a recurring absence is a lever
  demanding to be built."
- `settle ID --evidence E [--note TEXT]` — closes an open grant.
  Evidence is verified by shape: a 7–40 hex string is checked with
  `git cat-file -e` in the current repo; an existing directory under
  `~/.local/state/agentscient/dispatch/` verifies as a record; an existing
  file path verifies as a file. Verification result lands in
  `verified` (1/0); an unverifiable shape stores as claimed with
  `verified` 0 and says so. Settling past the ttl sets `late` 1 and
  says so. Settling a settled grant refuses.
- `open` — the open grants, oldest first, with age against ttl.
- `report` — counts by status, open grants, recurrence counts by
  class and by named missing lever, debt line (open, settled-unverified,
  settled-late).

## Refusals

Expected / found / needed, exit 2 on stderr:

| refusal | fires when |
|---|---|
| identity | `WF_AGENT` unset or malformed on a writing verb |
| why-short | WHY under four words — a stamp, not a reason |
| class | unknown lever class (name the known ones; add a class rather than blur one) |
| lever-exists | declaring a class whose probe path exists |
| unknown | settle/… on an id not in the store |
| resettle | settling a grant not `open` |

## Lint

Repo `ruff.toml` governs. Evidence verification shells to `git`
(S603/S607) — the tool earns the same per-file row shape its siblings
carry, stated in the PR.
