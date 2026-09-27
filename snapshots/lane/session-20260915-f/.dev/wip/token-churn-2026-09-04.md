# Why the session burns tokens — measured, 2026-09-04

Owner, 17:15Z: "if its that bad, I need to at least learn why and have it
documented - because i can't afford this long-term... We need to rethink
how you function - something is wrong."

Measured from the session's own transcript (session c1b9ce7c, 2026-09-03
19:00Z to 2026-09-04 17:10Z), by one script over the JSONL, at 17:12Z.
Nothing here is an impression.

## The numbers

| measure | value |
|---|---|
| API turns | 1377 |
| cache reads (tokens) | 613.3M |
| output (tokens) | 1.72M |
| cache reads per output token | 356x (thrift class 1 fires at 20x) |
| average context per turn | 448k |
| compactions in 22 hours | 4 |
| turns with no tool call (narration, answers) | 320, costing 158M |
| Bash turns | 913, costing 408M |
| Monitor turns | 106, costing 39M |
| all tool results, whole session | 1.48 MB, about 0.4M tokens |
| hook refusals seen in results | about 70 (clipped-sweep 25, unguarded-replace 7, matrix 6, permission denials 8, other 24) |
| harness notifications vs owner messages | 207 vs 186 |
| turns at 400k context or more | 780 of 1377 |

## What the numbers say

1. **The bill is turns times context.** Not output (1.72M), not tool
   output (0.4M in total). The same 450k of context was re-read about a
   thousand times. Halving either factor halves the bill.
2. **Context sat at 400k to 700k for most of the session.** Four
   compactions in 22 hours; the harness compacts near the window's end,
   and nothing compacted at 300k. The one manual compaction (owner,
   17:07Z) cut the next turns from 900k to 540k.
3. **One turn in four did no work.** 320 turns were text only: sit-reps,
   answers, and a sentence written before a tool call in its own API
   call. Each cost the same context read as a tool call. 26 percent of
   the bill.
4. **Refusals cost double.** A hook refusal is a full-context turn, and
   its retry is another. About 70 refusals, so about 140 turns, about
   60M tokens, ten percent of the bill. The clipped-sweep hook alone
   fired 25 times; the matrix hook's false positives (a pgrep argument,
   a `$SP` in a heredoc, prose in a heredoc) are in the ledger.
5. **Notifications outnumber the owner.** 207 harness notices against
   186 owner messages. Every monitor event, every duplicate monitor on
   the same dispatch, every heartbeat, is a wake, and a wake is a turn.
6. **Hand-run stages are the expensive path.** Item 31 ran by hand under
   grant 43 because it is the driver's own fix. Each hand stage cost ten
   to twenty turns: write the scope, write the run script, get refused,
   rewrite, launch, arm a monitor, wake, read the record, land, suites,
   ruff, hand-off. The driver exists to make that one stop event. Ten
   dispatches by hand is a few hundred turns at 450k.

## Root causes, in order of weight

- **RC1 The session works as the hands.** The design names the session
  as the conductor; in practice it ran every stage the driver could not
  (item 31, the adjudicate hole, the audits), and every hand stage is
  hundreds of thousands of tokens per turn times a dozen turns.
- **RC2 One session lives too long.** Twenty-two hours, four
  compactions, most turns above 400k. A fresh session opens near 40k
  with the law and the onboard brief. `ops/process/token-thrift.md`
  names this countermeasure for class 1; it was never applied.
- **RC3 Turn granularity.** A sentence, then a tool call, then a status
  check, each as its own API call. One command per turn where five could
  share one. Every turn is a full read regardless of what it does.
- **RC4 Refusals are priced as free.** A hook that refuses is right to
  refuse, but the harness pays a full turn for the refusal and one for
  the retry, and a false positive pays twice for nothing. No hook and no
  instrument counts refusals per session.
- **RC5 Polling dressed as events.** Two monitors on the same dispatch,
  a half-hour heartbeat, a log poller beside the watchdog that already
  reports closes.
- **RC6 Nothing measured the conductor.** `worth.py waste` reports
  `claude sessions=0` while listing every Grok and Codex dispatch (ledger
  item 48). The instrument built to answer this question is blind to
  the one actor that spends the most.

## The rethink (proposed; the owner rules)

- **R1 The session never runs a stage.** When the driver has a hole, the
  session parks the slice, files the hole as a ledger item, and
  dispatches a plan for the hole. It does not become the driver. Hand
  grants stay for landing and merging only. The item 31 hand run
  finishes as the last of its kind.
- **R2 One session per batch, hard context ceiling.** Open from the
  onboard brief, run one batch, close with the hand-off and probe rows.
  Compact or close at 300k, never wait for the harness. Whether the
  harness's auto-compact threshold can be lowered by setting was not
  checked in this session.
- **R3 One turn per boundary.** The session's unit of work is the stop
  event: one turn that reads the record, decides, and issues the next
  lever, with the status line in that same turn. No narration turns;
  sit-reps on request; the hand-off amended in the same turn as the
  action it records.
- **R4 Price the refusal.** A refusal's remedy is copy-ready so the retry
  is one turn; the false-positive rows are fixed (pgrep argument, `$SP`,
  prose inside heredocs); refusals per session become a `worth.py`
  signal with a threshold.
- **R5 One watchdog, no heartbeat, no per-dispatch monitors.** A wake
  only for a stop event or a deviation.
- **R6 A session row in `worth.py`** (item 48), so the next window's
  report is the test of R1 to R5 and not another impression.
- **R7 Long-term shape.** The conductor is not a chat session. The driver
  and the watchdog run a batch end to end; a session opens to rule on a
  stop or to merge, and closes. This is what the driver scope already
  says ("runs the loop end to end without a session at each boundary").
  The session is the fallback, and today the fallback was the main path.

## The test

Next window, `worth.py waste` with the session row: cache reads per
output token under 50x, turns per batch under 100, average context under
200k, refusals per session under 10. Miss any one and the rethink did
not take.
