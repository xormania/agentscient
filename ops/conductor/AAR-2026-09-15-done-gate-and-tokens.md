# AAR 2026-09-15: the done gate, and where the tokens go

Session agentscient-ab (Claude Fable 5.1), branch lane/session-20260915-a,
transcript 33baa9db-2014-4fde-a504-69204cdb026a. Written at the owner's
word, 2026-09-15: "aar and handoff - make sure token use issues are doc'd -
its top priority next session". Every number below names the command or
record it came from; a claim with no reading says not measured.

## Token use: the next session's first deliverable

The owner, 2026-09-15: "I want better token use effeciencies more than
anything right now". Read from the three session transcripts under
~/.claude/projects/-home-scientdb-projects-uscient-agentscient/ by a script
summing each assistant message's usage block, at dev 564ab769:

| session | requests | mean context per request | largest | cached tokens re-read | output |
|---|---|---|---|---|---|
| -b, 44f9de58 (the migration) | 1586 | 409k | 857k | 641,696,684 | 2,547,044 |
| -a, 836a47fd (the wall) | 823 | 419k | 737k | 335,200,311 | 1,396,655 |
| -ab, 33baa9db (this one) | 351 | 252k | 384k | 83,135,041 | 605,257 |

Readings that decide the class (ops/process/token-thrift.md, class 1,
context churn; the threshold is cached reads above 20 times output):

- Churn ratios: -b 252x, -a 240x, -ab 137x. Every session breaches.
- Share of input-side tokens spent on requests above 400k context:
  -b 73% (804 of 1586 requests), -a 75% (452 of 823), -ab 0%.
- The same requests capped at 400k context would have cost 77% (-b) and
  78% (-a) of what they did, with no change in turns.
- Output is under half a percent of the re-reads in every session.
- The fixed prefix every request carries, from /context in this session:
  system prompt 3.5k, harness tool schemas 21.4k, deferred tool names
  14.9k, the law 10.6k, skills 5.4k; about 56k. The connector schemas
  (Gmail, Calendar, Drive, Hugging Face, Serena) are deferred and cost
  their names only until loaded. The prefix is about 14% of a 400k
  request; it is not the lever.
- Dispatched workers churn the same way: worth.py waste over
  [2026-09-14T23:00Z, 2026-09-16T00:25Z) ranks the five heaviest
  author-tests workers at 8.5M to 12.6M cached tokens each, 579 to 786
  messages each, 30k to 66k output each (records
  20260915T053518Z-tests-codex-34dc59, 20260915T053520Z-tests-grok-c14b8c,
  20260915T045242Z-tests-codex-0353f2, 20260915T053525Z-tests-codex-f66d80,
  20260915T053516Z-tests-codex-b41d6c); 45 codex and 44 grok dispatches in
  the window.
- Refusals cost a full re-read plus a rewrite: -b met 30 claim-unmeasured
  refusals in its transcript (grep of the wire line); at its mean context
  that is about 12M tokens of re-reads for rewording.
- Requests per unit of work: -b 1586 requests and 853 Bash calls; -ab 351
  requests and 204 tool calls (tool_use counts from the transcripts).

The levers, in the order of their leverage, each with its test:

1. One deliverable per session, then a fresh session; as a backstop, the
   auto-compact window set near 300k instead of the 1M default
   (code.claude.com/docs/en/model-config, "set the auto-compact window",
   read 2026-09-15). Test: mean context per request under 300k in the
   next window's worth comparison. The paraphrase risk of compaction is
   covered by the brief printing the owner's words and every target
   reading (#221, ad11c6bb) and by the done gate.
2. Fewer requests: batch independent calls into one turn; write the
   commit message and PR body right the first time (the claim skill);
   count refusals per session as a waste signal. Test: requests per
   landed PR, and refusals per session, both falling.
3. The workers' job brief: narrow what an author-tests worker reads and
   cap its steps in ops/devlane/task/jobs.json. Test: cached tokens per
   dispatch under 3M in the next window.
4. worth.py waste is blind to Claude sessions: for the window above it
   reported "claude sessions=0" while three ran (the same command that
   found the 89 dispatches). Until it is corrected, the transcript sums
   above are the reading. This is a lever defect for the sweep session.
5. The prefix, last: trim AGENTS.md, and turn off the unused connectors
   for Claude Code sessions; 5k to 10k per request, 1% to 2% of today's
   spend, worth doing for adherence more than cost.
6. Memory, not tokens: eleven Serena servers at about 250MB each were
   running at 21 GB available; the harness killed this session's
   background suite twice for low memory at peaks (task ids bv4u5n08b,
   biahld8jc). A role profile that loads Serena only for sessions that
   navigate code is one settings line.

## What the session was asked, and what it did

The owner's first order, 2026-09-15: "i need an agent that help me figure
out to make sure that my instructions are carried out ... co-ordinate
with the two other claude sessions to find out what has failed, then i
want you to research how to stop this."

The failure, read from transcript 44f9de58 and the plan record
20260913T034513Z-plan-claude-892490: the owner's order of 2026-09-12
("a framework going forward that avoids one-off tests in favor of a
testing framework") was narrowed at the plan (PLAN.md line 384: the other
families "migrate family by family under the same evidence rule; not
this plan's slices"); the session adopted the plan as the meaning of
"all done"; the compaction summary froze the paraphrase ("i.e. land the
entire test kit plan (slices 3-21)"); the onboard brief after compaction
printed the handoff thread "the plan landed ... to a later session" and
never printed the lock; and no gate read a "done" said in chat
(boundaries.json at da04bae4: 22 rows, all PreToolUse; no
UserPromptSubmit hook). The session reported the plan all done with the
lock's target reading off_kit=205 short (04:46Z answer; target set
04:56:53Z).

The research (sources in the session's reply of 2026-09-15; the pages
read that day): Claude Code 2.1.272 has /goal, a separate small model
judging a typed condition after every turn; prompt-based and agent-based
Stop hooks; a Stop hook is overridden after eight consecutive blocks
(stop_hook_active). isitdone is the reference design for a claim-gated
Stop hook with an attempt cap; obra/superpowers verification-before-
completion is the reference skill; a study of 20,574 sessions puts
inaccurate self-reporting at 22.58% of misalignment episodes; AgentLiar
names the scope-narrowing words. Spec Kit, OpenSpec and GSD give the
shape (criteria before work, a verify step after) but their verify step is
a checklist, not a gate.

The five corrections and where they stand (gh pr view, 2026-09-16):

| # | correction | PR | merge sha | by |
|---|---|---|---|---|
| 1 | the lock carries a measured target; done is a reading | #219 | 287364c3 | session -a |
| 4, 1 | the finish line shown to the owner before work; the owner types /goal | #220 | c378f259 | this session |
| 2 | prompt-based Stop hook (the model-judged layer) | #220 | c378f259 | this session |
| 2 | the deterministic done-gate row at Stop; the brief prints the lock; close page line | #221 | ad11c6bb | session -a |
| 2 | the refused page's done-gate row and the lifted-branch case | #222 | b123181b | session -a |
| 2 | the prompt hook corrected after its first wrong block (LD-43) | #224 | 126d27e8 | this session |
| 2 | the engine row's no-lock case | #225 | 564ab769 | session -a |
| 5 | the narrowing check at collect | thread T-40 | not started | waits on the owner |

Session -b's migration merged as #223 (5e00c406). The census on dev at
126d27e8: modules=226 on_kit=214 exempt=13 off_kit=-1; the minus one is a
counting overlap (three modules import the kit and also quote the
exemption string), a flaw in the measure, not the work.

Live readings of the gate, all in this session or reported to it:

- The engine row's first block: this session, at ad11c6bb, on a reply
  reporting merges with no lock line; correct.
- The engine row's second block: this session, at 126d27e8, lock empty,
  keyword "landed" said of a file; the no-lock gap, corrected in #225;
  the keyword breadth is the owner's ruling (thread on H-10).
- The prompt hook's first wrong block: session -b, the refusal line
  inside a code fence read as absent; LD-43, corrected in #224.
- The prompt hook's second wrong block: this session, at 564ab769, an
  analysis reply with no completion claim; recommendation to the owner:
  remove the prompt-based hook and keep the engine row (thread below).

## What went wrong in this session, and what it cost

- Editing a tracked file while the suite ran in the background failed one
  ladder test (its tearDown diffs the tree); one full re-run. Rule kept:
  no edits or commits during a suite run.
- The harness killed the background suite twice for low memory at
  547fafd1; the lane check of run 34940773665 was the same command on the
  same head and is the reading in #224's ready note. Local exit at
  547fafd1: not measured.
- The defects lever writes at the working directory: LD-43 landed in the
  main checkout and was moved by hand (the same pitfall as ledger.py,
  thread T-24).
- A handoff thread cannot be closed once its branch has left the lock;
  the lock was re-added for one call to close T-41.
- A commit subject with "done" and no reading was refused once
  (claim-unmeasured) and reworded with a corpus row id.
- The clipped-sweep guard refused two multi-alternation greps; both
  rewritten count-first.

## What the three-session shape showed

Three sessions, coordinated by message and record, caught three defects
in each other's work within hours: session -a corrected this hook's
accepted line shapes before it shipped, session -b found its first wrong
block, this session found the engine row's no-lock gap. The lock stopped
session -a and this session from writing the same hook once both had
named their branches. Context per session stayed a third to a half of
what one session doing all of it would carry; the cost was memory at
peaks and the coordination messages, which lived in transcripts rather
than the store.

Source: owner 2026-09-15
