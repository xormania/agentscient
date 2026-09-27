# AAR 2026-09-15: the token levers, and three sessions on one thread

Session -c (Claude Fable 5.1), branch lane/session-20260915-c, transcript
a4c50a70, draft PR #226. Owner's words at the start: "first priority is
Token Effeciency work" (the onboard argument), on T-56, whose body carries
"I want better token use effeciencies more than anything right now". Mid
session: "i have another claude session using Opus 5 - use it to minimize
your context and token waste if possible (i'm testing this out)". Every
number below names the command or record it came from; what was not
measured says so.

## The target, and what it reads

Lock: `deliverable.py add lane/session-20260915-c`, measure a `sh -c`
over `worth.py waste --repo . --top 1` on the window
[2026-09-14T23:00Z, 2026-09-16T00:25Z) plus a grep of the settings file,
until `claude-rows=1 rows-with-refusals=1 autocompact-300k=1`. Shown to
the owner before the first write, reading `claude-rows=0
rows-with-refusals=0 autocompact-300k=0`. The owner did not type `/goal`
(not observed in the transcript). The measure runs from the main checkout,
so it reads met only once #226 is on dev; the branch's own worth.py from
the main checkout printed `claude sessions=4` at 00:55Z.

## Lever 4, the defect, and what the report had been hiding

`worth.py waste --repo .` printed `claude sessions=0` at dev 564ab769 for
the window in which sessions -a, -b and -ab ran; `--repo
/home/.../agentscient` printed `sessions=4`. Cause: `gather()` compared
the literal argument with the transcripts' absolute `cwd`. Second defect
in the same row: `refusals=0` on every session, while a grep of the wire
line found 34 `claim-unmeasured` lines in transcript 44f9de58. Cause: the
counter required the text `hook returned a deny decision`, and a hook's
refusal reaches the transcript as `[engine:<row>] <class>: expected ...;
found ...; needed ...` with `is_error: true` and no marker (a script over
the transcript's tool_result blocks: 30 such results; the reviewer's
seven-day reading: 0 of 250 errored results carried the marker).

Fixed in #226: `--repo` resolved once at the CLI boundary
(`os.path.abspath`, no symlink resolution; abspath and realpath agree on
this host); the wire counted as a line-anchored pattern so a result that
quotes a refusal inside an assertion message is not one; a `cwd` under the
repo root counted as the repo's (30 usage rows under ops/ and
ops/conductor/tools in the store read as no session's). Rows: 646f1129
and a52085b4 red, 3adf53da and abf766b5 green; telemetry Ran 230, OK.
Live reading with the fixed tool over the T-56 window: refusals 30 (-b), 5
(-a), 4 (-ab).

Not fixed, recorded: usage.py has the same relative-path defect (LD-44).
The counter sees only refusals on the wire; the `clipped-sweep` row's
text is prose ("Count first, then look"), so this session's three
clipped-sweep refusals read as none (the fixed report at 00:55Z: refusals=1
for this session, the one claim-unmeasured). That is a finding against the
hook, not the counter: docs/wire.md asks one line, class, expected, found,
needed.

## The six levers, where each stands

| lever | done here | reading | test |
|---|---|---|---|
| 1 fresh session, compact window | `.claude/settings.json` autoCompactWindow 300000; the deliverable skill: one deliverable per session, then a fresh session | key accepted by Claude Code 2.1.273 (Sonnet session: `strings` over the binary, in the settings-key allowlist and the compact-cap message); whether it bound in a live session: not measured | next window: mean context under 300k |
| 2 fewer requests | refusals counted (above); this session batched independent calls | this session at 00:55Z: 47 turns, mean context 147k, 6.9M cached, 75k out | requests per landed PR, refusals per session, falling |
| 3 the worker brief | author-tests brief names its spend discipline and the 3M target, citing token-thrift.md where the dated figures live; caps.turns kept | Codex has no turn-cap flag (launch.py turns note); the cap reaches Grok only | next window: cached per dispatch under 3M |
| 4 worth.py blind | fixed, above | `claude sessions=4`, refusals 30/5/4 | the rows |
| 5 the prefix | nothing in the tree | Opus session: first-turn context 41.4k, of which law about 7.8k and skills 2.2k; 94 deferred tool names, 56 from five claude.ai connectors none of which any session used | owner: turn the connectors off |
| 6 Serena memory | nothing in the tree | Opus session, `ps`: 27 serena processes, 2,751 MB; 2,097 MB under user `work` from Sep 6 and 7, orphans; about 340 MB per live session here | owner: reap the orphans; load Serena per session |

## Three sessions on one thread, what it cost and saved

The owner put an Opus 5 session (agentscient-1c) and then a Sonnet 5
session (agentscient-4c) at this session's disposal. Handed off: the full
suite on the merged tree (Opus: `ops/bin/suites.sh`, 3188 tests, exit 0,
at 75f6e9cf; the merge with origin/dev 564ab769 was already up to date),
the second-producer review (Opus, record review-20260915-75f6e9cf.md at
e8feeeef on its branch: CHANGES, one P2, three P3, one extra finding, all
five applied in abf766b5 and 8398cd9d), the lever 5 and 6 readings (Opus),
the settings-key reading (Sonnet), and thread T-54 (Sonnet, #227). What it
cost: the Opus session's own reading, 51 turns, 4.66M cached for 54k out,
mean context 94k; the Sonnet session ran a one-shot `claude config get`
that spawned a real invocation (its own report). What it saved this
session: one full suite run's output, one review's reading of the diff, two
`ps` and transcript sweeps. The AAR's own token comparison of the three
sessions is the next window's `worth.py waste`, not this paragraph.

## What went wrong here

- `ops/bin/board.sh` printed 65 KB (every worktree of the organisation)
  and `probes.py run` printed the corpus as one JSON line; both read into
  context. Pitfall 41.
- The pitfall minted here as 40 collided with the Sonnet session's 40 on
  its branch: both ledgers number from the working directory's files.
  Renumbered here to 41 (8398cd9d). T-24's class, now measured twice.
- Four guard refusals: three `clipped-sweep` on one multi-alternation grep
  with `head` (rewritten with evgrep.sh), one `claim-unmeasured` on a
  commit subject carrying "(green)" with the reading in the body.
- The lane check refused the cherry-picked AAR at the term wall (run
  35041981990, line 13 spelled the host path); fixed in 5baf3978.
- The done gate blocked twice. First correctly: the reply paraphrased the
  reading. Second on a reply that carried the `target: expected ...` line
  inline in backticks after a prefix, and said "CI is green": the engine
  wants the line at a line start, and the keyword breadth is H-10's open
  question.
- `findings.py import` reads dispatch records; a session's review record is
  not importable, so the review's dispositions live in the commits
  (Finding/Verified pairs) and this AAR, not the findings ledger. A
  declared gap.

## Open, to the handoff

The next window's comparison; LD-44; the clipped-sweep text off the wire;
T-57 (the prompt-based Stop hook, owner's decision); levers 5 and 6 for
the owner; ledgers numbering from the working directory.
