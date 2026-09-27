# AAR — 2026-09-13, the Codex review of the release, asks only where critical, the test-system census

Session record by Claude Fable 5.1. Measured at write time against dev
`edb398a4`, master `2fed5317`. The
[handoff](handoff/HANDOFF-2026-09-13-test-census.md) carries state and
the next thread. The morning of the same session is recorded in
[AAR-2026-09-12-proof-at-boundaries.md](AAR-2026-09-12-proof-at-boundaries.md).

## Request and outcome

The owner asked, in order: "i need you to resolve the codex comments on
PR 158"; "atfer yu fix them - resolve the conversations in the PR
comments from codex"; "with evidence"; "an update the branch as well -
and verify CI is green - if not, fix it - hand grant ok'd"; "i mean
update PR"; "wtf was that permission req about - i intend to walk away -
and i'd like to think that i can"; "i don't want asks unless they're
critical - so what gives?"; "hand grant given to fix - just get PR 158
done / ci green"; then the test and CI documents: "lets talk", "is the
testing and ci still over accreted?", "we need consolidate the existing
system ... then we'll wire in a formal path for adding tests and CI -
thoughts?", "go - hand grant given - dispatch the census".

| PR | merge | what |
|---|---|---|
| #166 | 1fabcf72 | the corpus runner refuses an rg row whose option spawns a process (`--pre`, `-z`); wall grant 172 |
| #167 | 3f4b2aec | pr-proof reads the repository `-R`/`--repo` selects; a relocated job's MCP config is rewritten on resume; the stale `mcp-unwired` row replaced; LD-27 |
| #168 | b6fc0184 | an ask only where it is critical: force-push and prune ask, three hard rows deny again; the law and the refused page say so |
| #158 | 2fed5317, by the owner | the release, dev into master, #150 to #168, its four Codex threads each answered with the fix sha and readings and resolved |
| #171 | edb398a4 | the test-system census: the work order, the dispatch record with four lane MCP calls proven, the artifact, seven findings in the ledger |

Every merged head had lane, app, CodeQL and both Analyze checks green.
One dispatch ran, the census sweep on Codex (record
`20260913T023636Z-review-codex-bdbe55`, 7.58M tokens in, 46k out); the
rest was by hand under grants 171 to 177 at the owner's word.

## What was decided and why

- **An ask is a request for the owner's hand.** The claim-unmeasured
  row put a harness click in front of the owner for a sentence in the
  release PR body (skills registry event 102, 10:54:17Z). The owner: "i
  don't want asks unless they're critical". Only a forced push and a
  prune destroy history; those keep `ask`. A trunk commit, an unmeasured
  claim and an unproven ready or merge have remedies the agent owns, so
  they deny. Recorded in AGENTS.md; test_engine.py pins the split on the
  live registry.
- **The Codex findings were fixed on two branches, one per grant class**,
  because the runner is wall and the hook, the launcher and a corpus row
  are not. The wall row names no test path, so the runner's red test was
  written under an ordinary grant and the runner under the wall grant on
  the same branch; LD-27.
- **The census is a read job, not a build.** Its scope names six
  disjoint categories, its brief gives the artifact shape and the
  baselines with their commands, and it chooses no framework. It is the
  first work order to run on the day's worker wiring, and its record
  shows what that wiring produces: four lane MCP calls, a `reused:`
  line, the baselines reproduced independently.
- **What follows is a new session's.** The kit is wall work in
  isolation, and the plan wants the census and the three documents as
  its whole context. The handoff carries the settled order.

## What went wrong

- **A ruff red on the first wall push**: a variable named `token`
  compared to a literal (S105). Renamed; one extra CI round.
- **Three count-pinned corpus rows went stale in one afternoon**, each
  found by the runner before commit or CI: a docstring added a third
  `config.toml`, the ask count moved from 5 to 2, a law sentence was
  rewritten. Each became a presence or a sentence row.
- **An edit script ran twice** and inserted its tests twice; the
  duplicate block was removed by hand. Scripts that insert before an
  anchor are not idempotent.
- **A compound command was refused whole**: the lock is read at
  PreToolUse, so `deliverable.py add X && git worktree add -b X` never
  runs; the add goes first, alone.
- **The lock cannot drop one branch**: with two sessions in it, leaving
  means `set` with the other session's words; LD-28.
- **Eight hook refusals on my own command shapes** (graft-first twice,
  wall-write once, shell-expanded prose once, claim-unmeasured once,
  deliverable twice, HAND_GRANT not first token once), each with its
  remedy stated; none was worked around.

## Calibration

- Spend: the census dispatch 7.58M tokens in, 46k out on Codex; the
  session's hand work not metered.
- Grants 171 to 175 settled "claimed; unverified (git object)" as every
  grant in this ledger is until a verifier reads the evidence; 176 and
  177 open at write time.
- Corpus: 90 of 90 PASS at c1fd1e89 and, with this record's rows, at
  the head named in the PR body.
- The `close` page was followed for this record: worktrees, PRs, grants
  and the lock are the readings above; the findings export was refreshed
  in #171 (807 rows).
