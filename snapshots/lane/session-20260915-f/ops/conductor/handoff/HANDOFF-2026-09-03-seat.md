# Hand-off — 2026-09-03, at the close of the seat session

For the next session. Run `python3 ops/conductor/tools/onboard.py`
first; it serves `AAR-2026-09-03T15-seat.md` §Calibration as the
thread. Then read `.dev/wip/overview.md`, the owner's working
specification, which this file does not repeat. This file holds what
only a person can say.

## The model, unchanged

`master` is the release, `dev` the trunk; branch from `dev`, PR into
`dev`, draft first; no squash, no deleted branches, no rewritten
history; trailers on every commit; one line of work per worktree; the
main checkout belongs to nobody.

## What changed in how we work

- **The owner scopes and specs in session.** The plan dispatch and its
  review are gone. Tests by one harness, code by another, the
  mechanical gates, one review only when the change warrants it.
- **The lane is in use as-is** — `go.sh`, the hooks, `suites.sh`, the
  brief — and is not invested in. Each verb retires when its
  `agentscient` twin passes the same row.
- **Modules in `src/`, not bundles.** `packages/` stays empty.
- **Serena is on the seat** (PR #12, merged). Mate is a composer
  dependency and works after `composer install`. Makers are decided
  and not yet built.

## State at close, measured

| item | value |
|:--|:--|
| `origin/dev` | `e64a470`, PR #12 merged |
| open PRs | #10 draft, conflicting, zero checks; this records PR |
| register | 6 ratified, 1 proposed (D-VOCAB-1), 1 superseded |
| worktrees | 11 `ag-*` under `~/projects/uscient/wt/`; main checkout on `dev` |
| Serena | pinned `43ae0211`, Phpactor, 15 tools on the merged configuration |

## The levers, as of today

- `bash ops/bin/suites.sh` — every lane suite, from the root.
- `bash ops/bin/go.sh <intent> <branch|.> <scope…>` — dispatch through
  the launcher; conf at `ops/conductor/tools/dispatch.conf`.
- `python3 ops/conductor/tools/onboard.py` — the brief.
- `vendor/bin/mate tools:list` — runtime truth from the compiled
  container, after `composer install` and any `bin/console` run.
- Serena connects on its own per session; after a fixer reformats a
  file, call its `restart_language_server` tool.

## Machine-local

- `~/.local/share/phpactor/trust.json` — per absolute path; each new
  worktree needs `config:trust --trust` once (see `.serena/README.md`).
- `~/.local/state/agentscient/` — `decisions.db`, plus `handwork.db`
  and `skills.db` created empty by read commands during the evaluation.
- `.serena/home/` in the main checkout and in `wt/ag-serena-seat`,
  gitignored; each holds a Phpactor phar.
- `.xor/tmp/` — the owner's exchange directory: the standards draft,
  the Serena questions and answers, the two survey documents.

## Open items, in priority order

1. **The standards PR**: `composer check` and `composer fix`, the PHP
   after-edit hook, the standards page, the dispatch job templates.
   Everything after assumes it. Source: `.xor/tmp/standards-draft.md`,
   C1 through C7 agreed.
2. **`ops/bin/seat.sh`**: install, warm the container, trust Phpactor,
   check readiness.
3. **The wire module**, by hand, as the exemplar; then the makers.
4. **PR #10**: the owner's ruling on the House engine and CI shape.
5. **Owner decisions**: C8, C9, the records simplification, state
   location, project-law defaults, target profile, MCP writes.
6. **The onboard naming finding**: a same-day topic-suffixed AAR never
   becomes the thread; fix in `onboard-lever.md` and the instrument.
