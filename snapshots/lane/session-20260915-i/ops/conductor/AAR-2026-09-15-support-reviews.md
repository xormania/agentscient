# AAR 2026-09-15: the support session, two reviews and what the readings cost

Session 510b9b3e, Claude Opus 5 (1M context), on lane/session-20260915-d.
Opened by the owner's word, 2026-09-15: "co-ordinate with the other claude
session - its takes the lead - you support it - let it know that". The
lead was agentscient-11 (Claude Fable 5.1) on lane/session-20260915-c,
holding T-56. This session wrote nothing outside its own branch and led
nothing.

## The target, and what it reads

The lock's target for this branch was two lines, VERDICT and SUITES, in a
committed review record. `deliverable.py done lane/session-20260915-d`
read `2` against `until 2` — met — before the branch was lifted. After the
lift the same verb refuses: `absent: expected a branch the lock names
(...); found lane/session-20260915-d; needed deliverable.py show`. The
second target, set when the owner's AAR order arrived relayed through the
lead, is `aar=1 probes=1 draft=false`.

## What was asked, and what was delivered

Three jobs from the lead, then a fourth after a push voided the first
review's pin:

1. Readings for its AAR's lever 5 and 6 rows. Delivered: the prefix and
   context figures below, the deferred-tool census, and the serena census.
2. The lane suites on the lead's head merged with origin/dev. Delivered:
   `git merge --no-ff origin/dev` in a detached worktree of 75f6e9cf
   reported "Already up to date", so the tip was the merged tree, and
   `ops/bin/suites.sh` gave ruff 0.16.5 All checks passed with dispatch
   Ran 622, harness Ran 164, task Ran 356, telemetry Ran 229, hooks Ran
   311, fixtures Ran 221 (skipped=6), workflow Ran 62, testkit Ran 34,
   conductor Ran 1181, pr-overview Ran 8 — Ran 3188 tests, no FAIL, no
   ERROR, exit 0.
3. The second-producer review at 75f6e9cf. Delivered as record e8feeeef:
   verdict CHANGES, one P2 and three P3s, all five applied by the lead.
4. The re-review CONTRIB.md §Review protocol demands after the push.
   Delivered as record a4540f8e: verdict APPROVE, no findings, at
   26e45ef4.

Both records are on this branch and in draft PR #228.

## The findings, and the command behind each

- P2, the partial fix. At 75f6e9cf the `--repo` resolution sat inside
  `gather()`. Walking the file's ast showed `args.repo` reaching six call
  sites: 526 `gather` resolved, and 652 `repo_results`, 653 `stamp_block`,
  655, 716 `dispatch_rows`, 759 `stamp_block` unresolved — so one `waste`
  run had a session half and a dispatch-and-stamp half that agreed only
  while cwd happened to be the repo, while ops/process/worth.md declared
  the tool took an absolute path. Fixed at 26e45ef4 in `main()`. Verified
  closed: `grep -rl "import worth\|from worth" --include="*.py"` over the
  repo returns 0 files, so `main()` is the only door.
- P3, the unanchored wire. The predicate matched three substrings
  anywhere, so an errored tool result quoting a refusal counted as one.
  Demonstrated against the function itself. After the anchor, the same
  predicates over ~/.claude/projects for a 7-day window read old 256, new
  253, agreeing 253; all three dropped rows were read and none is a
  refusal — a Traceback, a test file's own regex literal, and a grep count
  of session 44f9de58's refusals. The old code was counting the act of
  measuring refusals as a refusal.
- P3, LD-44 named the wrong function: `collect()`, not `report`, and four
  readers, not three. Corrected at 8398cd9d.
- P3, a dated measurement inside a digest-pinned artifact. Moved to
  ops/process/token-thrift.md with five record ids; digest re-pinned to
  ff31dad2.
- Reported as a reading, not a finding: exact cwd equality also dropped
  rows whose directory is inside the repo. My count over a 7-day window
  was 80 rows under ops/conductor/tools (47), ops (21) and
  ops/conductor/ideas (12). The lead's count of the population the ranking
  actually consumes was 30 assistant-usage rows, and the lead's is the
  number the row needed. `_in_repo` at 26e45ef4 over six inputs: root
  True, /ops True, /ops/conductor/tools True, `agentscient-other` False,
  None False, /elsewhere False.

## What this session cost

`worth.py waste --repo . --since 2026-09-16T00:30:00Z` run from the trunk
copy at dev b95aac46, window ending 2026-09-16T01:27:30Z, session
510b9b3e: turns=97, avg_context=137022.28, cached=13290967, out=102971,
total=13394132, refusals=6. It carries a cache-churn signal at
cached=13089397 against out=102971. Measured separately from this
session's own transcript at its 51st turn: the fixed prefix costs 41414
tokens on turn one before any work, of which the imported law is 31073
bytes (~7768 tokens at 4 chars per token) and the 27 project skill
listings 8695 bytes (~2173 tokens); the rest is system prompt, tool
schemas and 94 deferred tool names, 56 of them claude.ai connector tools
this session never called, and that split is not measured because no
command inside a session reaches it.

Against the lead's own target for worker briefs — under 3M cached per run
— a support session that only read, measured and reviewed spent 13.29M.
The shape is in the per-turn table: context never falls, so every turn
re-reads the whole of it.

## The serena census

`ps -eo user,pid,ppid,rss,lstart,args`, one bounded call: 27 serena-family
processes, RSS sum 2817084 kB. The owner's account holds 6 of them, 678 MB,
exactly two live session chains — the lead's 2629402 and this session's
2659435 — each with a serena and a phpactor language server that grows
(201 MB and 172 MB when measured). User `work` holds the other 20, 2097
MB, MCP servers started Sun Sep 6 09:21 and Mon Sep 7 00:33 and 01:40
under contexts grok, codex, codex and claude-code. They are another
account's and nine days dead. Nothing was killed.

## What went wrong here

- **A reply said done without the lock's reading, twice.** The done-gate
  refused both, correctly: the first reply reported the onboarding
  complete and the second the close complete, each with no deliverable.py
  line. The remedy both times was the lever, not a rewording.
- **A hook reads the literal command text, not the resolved command.** A
  prepared script whose `git worktree add` built its branch name from `$1`
  was refused by `matrix:deliverable` with `found git worktree add
  ${1:?usage:` — the name would have been right at run time and the hook
  cannot know that. Every worktree add ran directly with a literal name
  after that.
- **Two support sessions derived the same branch name from the same sha.**
  `git worktree add -b lane/merge-check-26e45ef4` failed with "a branch
  named ... already exists"; the branch was already at the lead's sha with
  a worktree at ../wt/ag-merge-check-26e45ef4 that this session did not
  create and did not touch (CONTRIB.md: a worktree has one owner, its
  creator). The lock held both intents correctly — the collision is in the
  name, which is derived from a sha and therefore identical for any two
  sessions checking one head. A session id in the name removes the class.
  This became pitfall material rather than a change to #226.
- **Lifting the lock strands the branch's open threads.** Told to lift the
  lock when the PR opened, this session did, and then `handoff.py done
  T-59` refused `place: expected place taken for done; found place open`,
  and `take` refused `deliverable: expected the branch
  lane/session-20260915-d named in the deliverable lock`. Closing one
  thread took four commands: add, take, done, remove. Either the lock is
  lifted after the threads are settled, or `done` accepts a branch the
  lock no longer names.
- **A figure in the PR body was wrong.** The Evidence section said 2 files
  changed, 231 insertions where `git diff --stat origin/dev..HEAD` reads
  211. Caught after opening and corrected in place. It was a recollection
  written beside commands that were real, which is the easiest kind to
  miss.
- **My 80 was the wrong population.** Counting every transcript row with a
  cwd under the repo answered a different question from the one the
  session ranking asks, which consumes assistant-usage rows. The lead's 30
  was right. A count is only as good as the population named beside it.

## Open, to the handoff

H-13 carries three threads. T-59, the two review records, is done with
evidence #228. T-60 asks whether the harness binds `autoCompactWindow`:
the Sonnet session read the key out of 2.1.273's settings allowlist, which
shows the binary knows the name, and that a live session honours the value
is not measured by anyone. T-61 carries the 2097 MB of nine-day-old serena
processes under user `work`, addressed to the owner.

Two residuals of the anchored wire are the lead's to carry in its own AAR
as stated here: a wire line quoted on its own indented line still counts
(measured True at 26e45ef4, live rate 0 in the window), and a genuine
refusal delivered mid-line after a prefix is now missed (measured False,
live rate 0 genuine among the three dropped). Both are limits of what text
can decide.

Not measured by this session, declared: the merged-tree suite on 26e45ef4,
which another session held; the red-then-green of a52085b4 and abf766b5,
where the predicates those tests pin were verified directly instead; and
whether a live session honours `autoCompactWindow`.
