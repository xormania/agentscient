# I-001 — Symfony is the framework, whole

- recorded: 2026-09-03, in the conductor's first session, after the mapping was proposed
- source: owner, verbatim below
- disposition: ratified — `AGENTS.md` §Standing rulings, first bullet; register row D-SYM-1

## In the owner's words

> let's talk - we're not re-inventing the wheel - i decided to move Symfony because many of the issues we need to tackle already have packages that solve them. This is about that, and using a solid framework to deliver

> we use Symfony/ai - we use everything Symfony has to offer - the functionality we're porting - the value is proved, it just needs better organization and abstraction - hence symfony. And this about providing cli, mcp and api resources.

## What was heard

The ported lane is the oracle, not the blueprint: its contracts, rows,
and corpora say what correct means; its Python retires into packages
that already exist. symfony/ai is in, which supersedes the migration
doctrine's line that harness CLIs stay subprocesses and never SDKs —
reconciled by measurement: the symfony/ai Claude Code and Codex bridges
spawn those same CLIs as subprocesses under the Platform abstraction.
Every capability is projections of one service. The first question
before any contract is which package already covers it; `docs/mapping.md`
is the measured answer.

## Standing facts it must reconcile with

- The Claude Code bridge spawns the CLI: `gh api repos/symfony/ai/contents/src/platform/src/Bridge/ClaudeCode/ModelClient.php` — "Spawns the Claude Code CLI as a subprocess", measured 2026-09-03.
- symfony/ai is 0.13.0, pre-1.0, monthly cadence — Packagist, 2026-09-03T01:17Z; pinned exactly, probed, mocked.
