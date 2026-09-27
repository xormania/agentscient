# AAR — 2026-09-12, token waste, and proof generated and verified at the boundaries

Session record by Claude Fable 5.1. Measured at write time against dev
`4bf38d66` (the live record and its scope on top of merge #156
`4d95ae64`). The [handoff](handoff/HANDOFF-2026-09-12-proof-at-boundaries.md)
carries state and the next thread. The session before this one is
[AAR-2026-09-12-item31-stage-set.md](AAR-2026-09-12-item31-stage-set.md).

## Request and outcome

The owner asked, in order: "let's take a moment and look at how we
minimize token waste"; "hand grant - cap turns and drop grok to high -
in fact effort is something we need to look at - per role - xhigh or
max is ok for the initial planing - but that's it. Everything else
should be high"; "i thought we had fixed that - instead of harness, it
by task type based on model and effort parameters"; "do you see the
issue? every work-order works in isolation from the rest of the code -
its doesn't use any previous work, it works blind"; "between hooks and
mcp - can't we get this close enough to functioning?"; "don't you have
evidence req's to prove its done?"; "you can't take any agents word on
anything - you need proof, evidence"; "it has to be made impossible";
"no grep - grep is shit - use Graft or ripgrep"; "i think you need to
enforce usage - not doc it"; "proof needs to be part of the system - it
has to generated and verified at boundaries"; "not just proof at PR -
proof for every dispatch"; "blanket hand grant is given - just be sure
to verify you're doing the work".

Outcome, all on dev, every merge through the checks on its head:

| PR | merge | what |
|---|---|---|
| #154 | e6cc6aa0 | effort per job in the tracked conf (plan xhigh, everything else high); `caps.turns` per job and `--max-turns` on Claude and Grok; Codex and agy declare they have no such flag |
| #155 | 3de55a7f | `probes.py`, the corpus runner the lever promised on 2026-09-01 and never got; CI runs the 38 rows (now 57) on every push; the grep rows became ripgrep rows |
| #156 | 4d95ae64 | every worker gets the lane MCP (Claude `--mcp-config`, Codex `-c`, Grok `config.toml` in its isolated home), a measured what-exists brief in every prompt, a required `reused:` line in write envelopes, and `result.proof` on every record: the lane MCP calls counted from the worker's own store; a wired worker that never called is invalidated |
| #157 | 794cb4cf | the `pr-proof` hook row: ready and merge refuse without a `## Proof` section naming corpus rows present at the head and a green run on that head; no grant escape |

Records committed straight to dev: I-028 (139735d8), LD-25 (b4426c4d),
the live sweep record d3badaa3 and its scope 4bf38d66, and this AAR
with the handoff, the findings export and the live-proof corpus rows.

## What was measured, and what it showed

- **Two days of dispatch spend**: Grok 149M tokens over 64 dispatches,
  Codex 112M over 62, Claude 31M over 17; nine tenths cache reads of
  each worker's own growing conversation. One Grok test author: 393
  messages, 109 tool calls, 26 patch edits, 7.7M tokens, four test
  files. It read forty files to write four, from nothing.
- **Three capabilities recorded as done and never consumed**: the
  per-job effort key (PR #20, 2026-09-04) with no per-job row ever set;
  lane MCP v2 (admitted 2026-09-05) with zero references in the
  launcher and isolation stripping MCP from every worker on purpose;
  the probes lever (ratified 2026-09-01) with a corpus and no runner.
  "Done" had been the merge, never the use.
- **Live probes before the code**: with the exact wiring later shipped,
  Codex, Grok and Claude each called `lane_jobs` and answered `JOBS=9`.
- **The first live dispatch after the merge** (record
  `20260912T042714Z-review-codex-063615`, a sweep on Codex at effort
  high): `result.proof.mcp_calls` 3 (`lane_brief`, `lane_changes`,
  `lane_jobs`), reuse declared, 11 findings, all one class: the
  conductor contract names `ops/conductor/tools/board.py`, which is not
  in the tree (the board is `ops/bin/board.sh`). Open in the ledger.
- **The gate fired on its first boundary**: this session's own ready
  command for #156 was refused by the hook, "expected a completed ci
  run on 1da27abc; found in_progress", and the same command went
  through once the run on the next head was green.

## What was decided and why

- **Enforcement over documentation** (owner: "enforce usage - not doc
  it"; "doc it too - but we need enforcement"). Every claim this
  session made now has a mechanical reader: the effort policy is a test
  over the tracked conf and a dry run; the corpus runs in CI; the PR
  boundary is a hook with no grant escape; the dispatch boundary counts
  the worker's calls from its own store and invalidates silence.
- **A capability is done when a reading shows it consumed**, never when
  it exists; the close page says so, and the corpus is where the
  reading lives.
- **Blanket grant for the hour**, at the owner's word; every grant
  settled against a git object or a dispatch record, verified by the
  lever, none "claimed".

## What went wrong

- **I wrote pages before gates, twice**, and the owner had to say
  "enforce usage - not doc it" before the CI step and the hook row
  existed. The pattern the owner named is the pattern I was repeating.
- **Mid-run edits broke two suite runs**: committing LD-25 to dev and
  correcting a corpus row while the suite lever was reading the tree
  produced two false failures that cost reruns.
- **Three CI rounds on #155 and two on #156** for things a local
  `ruff check .` and a run over the whole corpus in the branch would
  have caught: an unquoted shell split, a regex the runner could not
  parse, lane literals in a docstring, the records branches missing
  from a CI checkout.
- **LD-25**: the dispatch fixture inherits a deleted working directory
  in suite order; repaired in the fixture, the predecessor not found.
- **The pr-proof row reads prose**: a records commit whose python
  heredoc quoted the ready command was refused by the row this session
  built. Records are written with data heredocs; a pitfall row follows.

## Calibration

- Spend for this session's hand work is not recorded; the three live
  probes cost cents (Claude $0.02 measured); the live sweep 528k tokens,
  nine tenths cached.
- Grants 155 to 160: all settled verified (five git objects, one
  dispatch record).
- The corpus: 57 rows, 57 PASS at 4bf38d66; CI executes it on every
  push; the `pr-proof` row reads it at ready and merge.
- Not measured: whether the brief and the reuse clause shorten a test
  author's run. The next ladder's records carry `caps.turns`,
  `result.proof` and `result.reuse`; that is the first reading.

## Addendum, later the same session: one branch per session

Owner, 2026-09-12: "why are the branches always out of date - or some
other bullshit git issue - why can't it just fucking work"; "maybe we
need to have everything merge into a branch off of dev first"; "one
brench per session - lets try it"; "as long you account for the fact
that i'll have multiple sessions running soon".

Measured cause: dev moved 14 times in four hours (eight merges, six
record commits), three branches ran in parallel, and the stale-base row
refused any worktree not containing origin/dev as fetched. Two refusals
and two merge-noise commits came from that alone.

Landed on `lane/session-20260912`, the first branch of the new shape:

- the law: a session cuts one branch from dev, names it in the lock with
  the new additive `deliverable.py add` (a second session adds beside,
  never over), commits every change and record there, and lands one
  draft PR at close through the proof gate; this supersedes the "choice
  #2" of records straight to dev, made earlier the same day;
- `dispatch.sh` merges `origin/dev` forward into the worktree before
  each launch (a dry run says "would merge"; a dirty worktree or a
  conflict refuses with the files named and the worktree as it was);
- the hook's stale-base row refuses only a merge that `git merge-tree`
  reports as conflicting; behind alone passes;
- tests first: two matrix rows, four wrapper tests, one lock-lever test,
  red then green with the same commands; the corpus 61 of 61.

Two sessions still meet at their PRs into dev; they meet once, there.
The findings export is the likeliest conflict; it is regenerated, never
merged by hand.

## Addendum, the evening: the hooks as a framework, and where they stand

Owner, in order: "one brench per session - lets try it" (#159, fcef5190);
"you have to enforce it before you state it as fact - with evidence"
and "i want something in the hook matrix that stops you from lie-ing"
(#160, ad2739c4: trunk-commit, claim-unmeasured, the boundary
registry); "build the engine - just make it a specific registry of
intentional conditions that can be added to any hook in the session
lifecycle" (#161, f88dd4fe: engine.py at every event, five rows as
data, force-push as a row no code names); "so hand grant isn't actually
enforced?" (#162, 3ca4e317: LD-26, the bound-name write that passed
the hand-write row); "all these systems are for you - not me" (#163,
2b6a8e7b: the owner's word is the grant, the session declares it);
"i am the authoritative figure ... it can't get in the way in-session",
four answers, and "i have the right to issue a hand grant to change CI
and tests - but only in isolation" (#164, d5169bc6: the five hard rows
answer ask; wall-write; the wall lever class).

Readings that mattered:

- The trunk-commit code row refused my own work twice, blind to `cd`
  and to `git -C`; fixed in the engine's predicates with tests before
  #161 landed. The closure gate caught eleven test names I had written
  from memory on its first run.
- The bound-name python write passed hand-write with no grant open,
  and every branch-scoped grant of the day covered no path (a scope is
  path prefixes). LD-26; three tests red then OK; the live probe after
  merge refused the exact shape (3ca4e317).
- The transcript-reading design (the owner's typed turns as the
  unforgeable grant channel, lifting every row) was refused by Claude
  Code's permission layer as self-modification. Nothing of it landed;
  the owner chose the harness approval click instead.
- Live after #164 (d5169bc6): a dry-run commit on dev answered ask and
  the auto-mode classifier let it run; a forced push answered ask and
  the classifier denied it; a write to the CI workflow with no wall
  grant refused wall-write. In auto mode an ask is answered by the
  classifier, not the owner; in a hand-driven session it is the
  owner's click. The owner: "we'll see what happens and work from
  there".

Calibration: grants 155 to 170 settled verified; the corpus 82 of 82
at cee0cbed; the suite lever OK on every landed branch (the fixture
suite reports no OK line by design). Not measured: the hooks at
SessionStart and Stop in a running session; the fourteen code rows as
data; whether the claim row changes what a session writes. Count-pinned
corpus rows (classes, ask rows) cascade on removal; they should become
presence rows.
