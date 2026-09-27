# AAR 2026-09-15: three sessions on one thread, the close

Session -c (Claude Fable 5.1, transcript a4c50a70) leading; the Opus 5
session (transcript 510b9b3e, branch lane/session-20260915-d) and the
Sonnet 5 session (transcript 37ebd312, branch lane/session-20260915-b)
supporting. Written after the three PRs merged, at the owner's word:
"get PRs merged when ready - then have other two session do AAR - you do
AAR and handoff when they're done". Every figure names its command or
record; what was not measured says so. The work itself is in
AAR-2026-09-15-token-levers.md; the support sessions' own accounts are
AAR-2026-09-15-support-reviews.md (Opus, #228) and
AAR-2026-09-15-support-sessions.md (Sonnet, #227). This record is the
coordination, measured.

## The owner's three orders, and what each became

1. "first priority is Token Effeciency work": T-56, the levers in the
   tree, #226 merged at b95aac46.
2. "i have another claude session using Opus 5 - use it to minimize your
   context and token waste if possible (i'm testing this out)": the Opus
   session ran the merged-tree suite, reviewed the diff blind (CHANGES,
   five findings, all applied), re-read and approved, and took the lever
   5 and 6 readings; the Sonnet session, offering itself later, took the
   settings-key reading, T-54 (#227 merged at 78117de5) and a second
   suite run. Their review records: #228 merged at b82ddc86.
3. "Fable is expensive - my goal (always has been) is for you (Fable) to
   make the decisions and delegate ... Your context and token usage is
   valuable and should be specialized for your strength": recorded as
   H-14 T-69, the standing instruction the next session reads first.

## What the evening cost, per session

`python3 ops/devlane/telemetry/worth.py waste --repo . --since
2026-09-16T00:30:00Z --top 4`, dev at b95aac46, generated
2026-09-16T01:40:40Z:

| session | turns | mean context | cached re-read | output | refusals |
|---|---|---|---|---|---|
| Fable, lead | 119 | 219k | 26.0M | 140k | 4 |
| Opus, support | 133 | 165k | 21.9M | 129k | 6 |
| Sonnet, support | 133 | 137k | 18.2M | 59k | 7 |
| together | 385 | | 66.2M | 328k | 17 |

Against the T-56 window (AAR-2026-09-15-done-gate-and-tokens.md): one
session alone re-read 83M (-ab), 335M (-a) and 642M (-b) cached tokens.
Three sessions together re-read 66M for three merged PRs, one fix with
two red-green rounds, three AARs and a review round. Every session's
mean context stayed under 300k; the lead's grew from 147k at 00:55Z to
219k at 01:40Z because every peer report landed in its context. Churn
ratio, cached over output: lead 185x, Opus 170x, Sonnet 309x; all above
the 20x threshold of ops/process/token-thrift.md class 1, which the
harness's caching makes structural, not a session's fault.

## What the coordination produced that one session would not have

- Two of the five review findings named defects the author did not see:
  a session run from a directory under the checkout counted as no one's
  (30 usage rows in the store), and the refusal counter counted the act
  of measuring refusals as refusals (three of 256 errored results over
  seven days).
- An independent verification of the fix: old predicate against new over
  the live store (256, 253, 253 agreeing), six inputs to the cwd test.
- Readings no single session could take of itself: 27 Serena processes
  at 2,751 MB with 2,097 MB nine days old under another account; 94
  deferred tool names in every request; the settings key present in
  Claude Code 2.1.273.

## What it cost that one session would not have paid

- Overlap: two sessions ran the merged-tree suite, once each at two
  heads, when CI ran it on both; two sessions derived the same
  `lane/merge-check-26e45ef4` name and collided on the branch.
- Inbound reports: each landed in the lead's context; the four longest
  from the Opus session were about 1.5k tokens each. The lead's own
  count: eleven messages sent, nine received, from the transcript.
- Collisions from ids taken from the working directory: pitfall 40
  minted on two branches (renumbered 41 in 8398cd9d); the T-24 class,
  H-14 T-65.
- A one-shot `claude config get` the Sonnet session ran by mistake
  spawned a real invocation (its own report).

## What broke, in the order met

- The term wall refused two AARs in one night for the same reason: an
  AAR about this host spells the host's name (runs 35041981990 and
  35044404285). Both fixed by naming the directory by what it is. It
  will recur for every AAR on token use.
- The done gate blocked the lead three times and the Opus session
  twice: once correctly (a paraphrased reading), the rest on replies
  that carried no claim of the deliverable or carried the line after a
  prefix. The keyword breadth is H-10's open question.
- Lifting the lock at PR open strands the branch's open threads
  (handoff.py refuses a transition on an unlisted branch); the Opus
  session needed four commands to close one. H-14 T-66.
- `hand.py settle 246` read "claimed; unverified" because the merge sha
  was not yet fetched; the T-31 class; cannot be re-settled.
- The lock's `grep -c` measure with zero matches exits 1 and reads
  `unreachable`; the measure needs a trailing `; :` to read short.
- The lead's `deliverable.py set lane/...-b lane/...-d lane/...-c`
  replaced all three branches' targets with the lead's closing-AAR
  measure, with no signal to the two sessions whose work had already
  merged; both had to lift their entries with `--unmet`, putting a
  false "unmet" in the record of sessions that shipped (H-13 T-71,
  the Opus session). Rule until a target belongs to its branch's holder:
  beside other sessions, `add` and never `set`.
- `test_skills_registry.TestEvents` tearDown snapshots the live state
  directory and tripped twice while three sessions wrote it; CI, alone
  on its runner, was green. H-14 T-67.
- `/context` at 01:35Z in the lead's session: 306.6k of 1m, messages
  274.5k, deferred MCP tool schemas 47.5k and deferred system tools
  20.9k, the law 10.6k, skills 5.4k, the system prompt 3.5k. The
  auto-compact window read 1m: the setting landed on dev during the
  session and was not loaded at its start. The next session's
  `/context` is the reading for H-13 T-60.

## The split the owner's words ask for, measured against this evening

The lead spent 119 turns, most of them on edit scripts, red and green
runs, commits, pushes, PR bodies and probe rows under grant 246, which
any support session could have carried. What only the lead had to do:
read the brief, set the target and show it, decide on the five findings,
merge. The next session takes T-69 first: Fable decides, one support
session per job with an output cap, no check run in two places, and
readings arrive as a bounded table.

## Open

H-13 T-60 (does autoCompactWindow bind: the next session's /context),
T-61 (the Serena orphans, owner), T-57 (the prompt-based Stop hook,
owner); H-14 T-62 (the next-window comparison, the test of all of it),
T-63 (LD-44), T-64 (clipped-sweep off the wire), T-65 (ids from the
working directory), T-66 (lock-lift and settle), T-67 (the live-state
teardown), T-68 (levers 5 and 6), T-69 (the standing instruction); H-13
T-71 (`set` reaches across sessions).
