# AAR — 2026-09-13, the test kit plan, token thrift, the PR gate

Session record by Claude Fable 5.1 on `lane/session-20260912-n`, cut from
dev `8b863cf4`. Measured at write time: dev `92d28d13` (#176 landed after
this session's #175 at `4fdc6d0e`); PR #177 open and ready at `96f37834`;
grants 178 to 183 settled against `4fdc6d0e`, 185 open; the lock names
this branch. The [handoff](handoff/HANDOFF-2026-09-13-token-thrift.md)
carries the next thread.

## Request and outcome

The owner asked, in order: read the census handoff and run the plan job at
xhigh; "what's the situation with the dependabot PRs?"; "hand grant ok'd
for changes to dependabot"; "i'm worried - i'm running low on tokens -
don't act, just figure out if this is going the right way"; "let it close
- but i really need to focus on token usage optimization"; "hand grant
ok'd for #2, #3, #4 - get them done - be cheap"; "doc the issues"; "175
is red"; "merge it - and continue"; "a draft PR should never be marked
for review unless it can be merged immediately"; record I-029; "should
we start a new session?" (yes).

| PR | merge | what |
|---|---|---|
| #175 | 4fdc6d0e | the plan work order and record; thrift #2, #3, #4; dependabot.yml; corpus rows; pitfalls 23 to 27; LD-30 to LD-32; the ready ruling; the handoff |
| #177 | open, ready | I-029, the owner's intention: the PR process as MCP tools, issues and discussions for agents |

One dispatch: the plan job `20260913T034513Z-plan-claude-892490`, Claude
Fable 5.1 at xhigh, 27 minutes, 5.6M in, 131,632 out, exit 0, PLAN.md at
67,966 bytes with 50 machine lines, 6 p3 findings not yet imported.

## What was decided and why

- **Spend is the conductor sessions, not the jobs**: 261M of 275M tokens
  in the window, cached reads 190x to 390x output, mean context 243k to
  465k. The countermeasures the owner chose: five law files at onboard
  instead of seven; graft-first no longer refuses one named file or a
  data file; plan effort high by default. The test is the next window's
  `worth.py waste` with an absolute repo path.
- **Ready means mergeable now** (owner): the flip is the merge's gate
  applied early. Recorded in CONTRIB; LD-32 for the hook that gates only
  the merge verb.
- **Dependabot**: version updates to dev; security updates cannot be
  redirected (GitHub: "always use the default branch"); the fixture
  manifests are ignored for both. #169 and #170 closed by the owner, the
  alerts dismissed by the owner; the harness classifier refused those
  writes from the session.

## What went wrong

- **A piped suite hid its exit code twice** (cc04f7d9, 262b4a84); each
  commit claimed green over one red and was corrected in the next
  commit. Pitfall 23. The third run read the exit from the process.
- **My first spend reading over-counted tenfold** (1.37M output for the
  plan job): the stream repeats a message's cumulative usage on several
  rows; the breaker's per-message-id dedup gives 131,632. Corrected in
  session before any record carried it.
- **PR #175 flipped ready, then the merge refused pr-proof**: no Proof
  section, no corpus rows. A push, a corrected row and two ready notes
  later it merged; the owner's ruling above followed.
- **#175 went DIRTY** when #174 landed session -l's rows in the same two
  record tables; no CI run until dev was merged forward and this
  session's rows were renumbered (LD-29 became LD-30, pitfalls 22 to 26
  became 23 to 27).
- **Guard rows scan heredoc prose**: trunk-commit and pr-proof refused
  records whose text named the verbs; reworded, and noted in LD-32 and
  pitfall 27.
- **Hook refusals on my own command shapes**: 6 graft-first (the row is
  now narrower), 2 clipped-sweep, hand-write, input-absent, override,
  record-target, unguarded-replace, shell-expanded-prose; 3 harness
  classifier denials on outward writes.

## Calibration

- This session, `worth.py waste` at 04:14Z: 14.9M tokens, 61 turns, mean
  context 243k; by close roughly twice that, unmetered here.
- The plan job's cap-out (500,000) was never compared: the launcher's
  Claude store path does not exist (LD-30).
- Corpus: 23 rows OK at 96f37834, exit read from the process.
