# token-thrift.md — not spending what the work doesn't need

`worth.py waste` points at where spend concentrated; this page names
the classes that put it there and the countermeasure for each. The
discipline: every class is detectable from the stores, so a claim
that spend improved is a `worth.py` comparison between two windows,
never an impression.

| # | waste class | signal in the stores | countermeasure |
|:--|:--|:--|:--|
| 1 | **context churn** — the same context re-read turn after turn | `cache-churn`: cached reads more than 20x output | narrower reads (offset/limit), never re-read after edit, keep long transcripts compacted, split long lanes into fresh sessions |
| 2 | **unbounded tool output** — a command dumped its whole world into context | `heavy-turn` on tool-heavy sessions | bound every command (`head`, `--short`, `-c` counts); the count-first grep shape; `Read` with limits |
| 3 | **re-derivation** — state rebuilt from scratch instead of read from the stream | many short turns re-running status/log/diff | context stream + stamps: read what moved, re-take only what a crossing expired |
| 4 | **doc reloading** — agents loading whole process docs each run | repeated large cached reads across agent sessions | compact aggregates for agents (pulse, usage report lines); docs stay for humans and first reads |
| 5 | **oversized fan-out** — parallel agents where one would do | many concurrent sessions, low per-session output | size the pattern to the surface; say the agent count before launching; solo for routine work |
| 6 | **polling** — asking again instead of being told | dozens of identical cheap turns | `--watch` modes, background tasks with notifications, breaker supervision instead of manual checks |
| 7 | **runaway reviewers** — a hung or looping background run burning quietly | breaker trips; grok runs with huge `modelCalls` | always arm the battery (cross-review.md); caps are the contract, `--disable` is refused on the armed line |
| 8 | **retry storms** — the same failing operation repeated verbatim | bursts of near-identical turns | after two failures, change the approach or surface the blocker; never loop a denied call |

The rule behind all eight: **tokens buy state changes, not activity.**
A turn that moved no file, landed no commit, and decided nothing was
either a read that should have been narrower or a wait that should
have been a notification.

Worker briefs carry the same rule. The author-tests brief in
`ops/devlane/task/jobs.json` names its spend discipline and a target of
under 3M cached tokens per run; measured 2026-09-15 at dev 564ab769 over
[2026-09-14T23:00Z, 2026-09-16T00:25Z), the five heaviest author-tests
runs re-read 8.5M to 12.6M cached tokens each for 30k to 66k of output
(records 20260915T053518Z-tests-codex-34dc59, 20260915T053520Z-tests-grok-c14b8c,
20260915T045242Z-tests-codex-0353f2, 20260915T053525Z-tests-codex-f66d80,
20260915T053516Z-tests-codex-b41d6c). A turn cap does not reach Codex,
which offers no such flag; the brief is the lever for both harnesses,
and the next window's `worth.py waste` is its test.

Review cadence: run `worth.py waste` over the last day before closing
a lane; anything ranked in the top 5 twice in a row gets a class
assigned from this table and a countermeasure applied, and the next
window's report is the test of whether it worked.
