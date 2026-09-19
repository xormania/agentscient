---
name: skills
description: Look up, manage, and meter the project's skills — the SQLite registry (sync from disk, CRUD, and telemetry on uses, failures, misses, and wishes). Invoke to find a skill, record one that failed or got bypassed, or file demand for one that should exist.
---

# skills — the skills registry and its telemetry

The engine is `python3 ops/conductor/tools/skills.py` (SQLite at
`~/.local/state/agentscient/skills.db`). Disk is the source of truth for what
exists; `sync` derives rows from `.claude/skills/*/SKILL.md` and never
deletes — a vanished directory marks its row `missing`, and a wished
skill whose directory appears is promoted to active. Events are
observations, the non-authoritative-mirror rule. Recording an event needs
`WF_AGENT` set, the same identity contract wf enforces; reading does not.

## When invoked

1. Run `sync` first — the table answers only for the tree it last saw.
2. Then do what was asked:
   - **look something up** — `list`, `show NAME`, or `report` (uses,
     fails, misses per skill; wished skills ranked by demand).
   - **add or annotate** — `add NAME DESC --kind=K --status=draft`,
     `note NAME TEXT`, `retire NAME REASON` (reason mandatory; rows
     never vanish).
   - **record telemetry** — the duties below.

## Standing telemetry duties (any session, not only when invoked)

- `log-use NAME [DETAIL]` — a skill was invoked. Since 2026-09-13 the
  PreToolUse hook `ops/devlane/hooks/claude/skill-use.py` records every
  Skill call with its arguments; log by hand only for a use the tool
  did not carry (a page read directly, a skill followed from memory).
- `log-fail NAME DETAIL` — an invocation broke; DETAIL carries the
  error's own words, never a summary of them.
- `log-miss NAME DETAIL` — a failed potential use: work was done another
  way while an active skill covered it. DETAIL says what was done
  instead. A recurring miss is an ergonomics defect in the skill, not in
  the session.
- `wish NAME DETAIL` — the skill does not exist and should. Refused if
  it exists (that is a miss, not a wish).

## Shared harness entry points

Claude, Codex, Grok, and Agy use this same registry and the same source
pages. Adapters translate events; they do not own another catalogue, identity
resolver, recovery policy, or telemetry store.

- `skills.py catalog` reads validated active pages from this checkout and
  emits JSON rows with `name`, `description`, `path`, `sha256`, and `status`.
  It never creates or syncs a store. A fresh host reads disk; an existing
  unreadable registry refuses rather than concealing lifecycle state.
- `skills.py read NAME` serves the complete canonical page without telemetry.
  Inspection is not invocation and needs no identity.
- `skills.py use NAME [DETAIL]` serves one validated page and records exactly
  one redacted `invoked` event. The event persists the exact canonical source
  path and SHA-256 of the bytes served. It replaces the page's manual
  `log-use` for that invocation; do not double-count it.
  Event detail is redacted and limited to 16 KiB of UTF-8 before any SQLite
  write; an oversized detail refuses on the standard wire.

The callable seams are `managed_catalog()`, `load_skill(name)` (the catalogue
row plus `content`), and `record_event(kind, name, detail=None)` (no stdout).
Names are unqualified local identifiers: vendor- or plugin-qualified names
are never silently credited to a project skill. The source is opened through
a held descriptor and checked against this checkout, so a link may target a
repository file but an escaped or swapped source refuses before content is
served. Retired, draft, wished, and missing rows are not invocable; a valid
on-disk page with no registry row is invocable without a separate sync.

Receipt guidance is deliberately narrow: paths beginning `./` or `../` are
relative to the served page's directory; a repository-relative path such as
`ops/...` or `docs/...` is relative to the checkout containing the receipt.
The page itself remains authoritative if it declares another resolution rule.
Identity remains `instrument.identity()` and sessions remain
`instrument.session()`; ordinary CLI environment precedence and validated
profile resolution are existing shared contracts, not a skills subsystem.

Interactive profiles may advertise this catalogue and route. Worker profiles
do not receive the operator catalogue or auto-onboarding: assignment scope
and isolation still govern. Telemetry grants no authority and does not retry a
refusal. A generic file read is not proof that a skill procedure ran.

## Honesty rules

- An event without its story is refused — counts alone are recollections
  wearing claims' clothes.
- `report`'s zero-misses line is a declared zero only while sessions
  actually declare; this skill exists to make declaring cheap.
- The future registry export (REGISTRY.md, drift-gated) derives from
  this table plus disk; neither is ever hand-edited.
