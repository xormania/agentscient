# I-032 — compaction as a near-clear, once the session's holdings are extracted to records

- recorded: 2026-09-16, session agentscient-11 (Fable, lane/session-20260915-e), after the token-waste course was laid out
- source: owner, verbatim below
- disposition: open

## In the owner's words

> one thing about compaction - if we can get lessons out of a session and recorded (or any important info) - compaction becomes more like clear except for currently needed context. compaction destroys useful data, but if its been extracted, compaction may be something closer to a context clear (an optimized compaction removes everything not needed to go forward) - thoughts?

## What arrived with it

Measured the same evening: the master session's context read 186.8k by
`/context` at about 02:55Z, 154.7k of it messages, and by the close
the lock's reading put the session near 221k; the ledger rows, the AAR
(4f65ed06), the handoff draft and the lock already carried nearly all
of what those messages held. Codex workers compound 400 to 480 KB of
tool output over 70 to 98 completions into 9 to 13M cumulative input
(AAR-2026-09-15-token-mechanism.md, readings 8 and 9); codex-cli
0.154.0 carries model_auto_compact_token_limit (strings count 22) and
the launcher never sets it (grep count 0 in launch.py).

The lane's own law already points here: sessions coordinate by record,
never by memory (AGENTS.md); a closing actor converts its holdings into
corpus rows or declares what it left behind (docs/probes.md).
Compaction is that close in miniature.

## What a ruling would have to settle

- the forward set is declared, never judged: the lock line, the taken
  threads, the open grants, the branch and worktree, and an in-flight
  table (who was asked for what, when) that tonight lived only in the
  master's conversation;
- the owner's mid-session words are recorded the hour they arrive, as
  the ideas README demands, so no compaction can lose them;
- a pre-compaction hook runs the close manifest, the compaction
  instructions shrink to pointers and "onboard again", and the
  auto-compact window drops (100k to 150k);
- workers compact aggressively with no extraction step: their forward
  set is the scope and the file in hand, and their lessons leave
  through the output envelope;
- the test is a hand-over's: after compaction the session onboards and
  continues without a correction from the owner, and every probe row it
  wrote still answers from records.

Hardens through the register as a D- row when the owner rules.
