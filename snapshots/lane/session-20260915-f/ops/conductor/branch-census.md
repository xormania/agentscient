# The branch census — contract

Standing: ratified mandate — the owner approved all three branch-system
moves ("#1,2,3 - go for", 2026-09-01; I-017): branches become derived
nodes in the custody graph, the law fast-lane replaces stacks
(D-OPS-9), and dispatch refs gain a lifecycle (D-OPS-10). This
instrument is move #1 and carries move #3's sweep. Source of demand:
the owner's seat sat on a stale branch for days undetected, and PR
#106 merged into a stacked base silently — branch roles, states, and
feed edges existed only as convention in heads.

## Conventions

This instrument inherits `ops/conductor/instrument-conventions.md`.
The census is a read (no `WF_AGENT`); the `retire` sweep writes tags
and requires identity (`--dry-run` writes nothing and, as a read,
needs none).

## Instrument

`python3 ops/conductor/tools/branches.py <verb> …`, stdlib only,
subprocess for `git` and `gh` under bounded timeouts. Everything is
**derived** — from branch names, PR history, envelopes, and refs —
never curated; re-running re-derives.

## Roles and states, derived

Role from name: `trunk` (dev), `release` (main), `unit`
(`<namespace>/<slug>` — conductor/, dispatch/, infra/, repo/, and the
other prefixes in use), `transport` (`refs/dispatch/*`), `unknown`
(anything else — a Finding, not a default). State from history: a
branch whose tip is reachable from dev or main is `merged-kept`; one
with an open same-repository PR is `active` (a fork's PR never
claims an origin branch); one with neither, whose tip is older
than the stale window (default 14 days), is `stray`; younger, `idle`.

## Verbs

- `census [--json]` — every branch (local refs under `origin/`), one
  line: name, role, state, base distance (`behind dev by N`), and the
  feeds edge (`-> dev` for units, `-> main` for dev, none for
  strays). Sorted: strays and unknowns first, then active, then
  idle, then merged-kept. Exit 1 (Finding) when any stray, unknown,
  or **STACKED** row exists; 0 otherwise. The census queries open PRs
  unconditionally; `--json` emits one object `{branches, stacked}`
  carrying the same STACKED evidence the text form prints.
- `stacked` — open PRs whose base is neither dev nor main (via `gh pr
  list --json baseRefName,…`), one line each: `STACKED #N base=<b>
  retarget before merge` (D-OPS-8's flag made executable). Exit 1
  when any exist, else 0.
- `transport [--window D]` — the dispatch refs: total count, how many
  are landed (their tip commits patch-present on dev — the land
  lever's `--cherry-pick` reading), how many closed in the record
  store, how many older than the retention window (default 30 days),
  landed, and closed — the retire candidates, exactly what `retire`
  would sweep, listed. Retention age is measured from the record's
  closure (the exit file's time), never from the tip commit's date —
  a fresh ref on an old base is young. Exit 0 always (a report).
- `retire [--window D] [--dry-run]` — for each retire candidate
  (landed AND older than the window AND its record closed): create
  `refs/archive/dispatch/<id>` pointing at the same commit, then
  delete `refs/dispatch/<id>`. Kept, not destroyed — the archive tag
  preserves the commit and the name (the owner's kept-branches
  preference, D-OPS-10). `--dry-run` prints the plan and changes
  nothing. Prints one line per ref and a summary `retired n=N`; a
  ref that fails to tag is skipped with the reason and the run exits
  1 (Finding); nothing is ever deleted without its archive tag
  written first.

## Refusals

Beyond the inherited wire and classes:

| refusal | fires when |
|---|---|
| repo | not inside a git work tree, or no dev trunk resolves — the trunk is never substituted |
| gh-error | gh is absent, exits nonzero, returns a full 1000-row page (an unmeasured total), or returns a PR row missing number, headRefName, baseRefName, or a boolean isCrossRepository — on `census` or `stacked`; stderr quoted, newlines normalized |
| window | `--window` is not a positive integer |
| identity | `retire` without `WF_AGENT`, except under `--dry-run` (inherited; reads need none) |

## Lint

Inherited. The tool shells to `git` and `gh` — it earns its
THIS-FILE-ONLY row (S603), stated in the PR.
