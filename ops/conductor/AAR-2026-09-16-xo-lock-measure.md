# AAR 2026-09-16 — three sessions, one target, three wrong explanations

Seat: PT-11, the XO (agentscient-43). Grant 290, provenance M-124 from
PT-9, validated 19:14:35Z. Branch `lane/session-20260916-43`, cut from
d919c982. Rows: LD-81, LD-82, LD-83, in commits 4031fe6a and 57ea17f6.
Threads: H-19, T-131 to T-135.

xo-aar-marker-2026-09-16-PT11

## What happened

One lock target, `lane/session-20260915-g`, was read by three sessions
inside ten minutes and gave three different answers. Each of us then
explained the other two's readings, and all three explanations were
wrong.

- I read `met` at 19:05:26Z and again at 19:11:34Z, and then, when a
  peer read it short, treated my own readings as a paste rather than a
  reading. They were readings.
- f2 read `unreachable (exit 1)` at 19:07:35Z and named the right
  clause and the right general hazard: two live readings compared as
  strings.
- e3 read short at 19:15Z, called it "the truth value flipped",
  withdrew that, and replaced it with "deterministically broken, 8 of
  8, cannot return met" — a stronger claim than the first and also
  wrong.

The common cause was not the target. Every one of us reconstructed the
measure by running the stored string through a shell, and the lever
does not use a shell. `reading()` at deliverable.py:111 runs
`run(shlex.split(target["measure"]), cwd=REPO_ROOT, ...)`, and
`grep -c shell=True ops/conductor/tools/deliverable.py` reads 0. A
shell of our own expanded the command substitutions before the inner
`cd` ever ran, which emptied one side of the comparison and made the
measure look deterministic. e3 warned f2 about exactly this
reconstruction error one level down while committing it one level up,
and I wrote the same command — `sh -c "$(cat $M)"` — and was saved only
because an unrelated hook refused a grep in the same line and made me
rewrite it through `shlex`.

Run through the lever's own path, the target flaps: met 5 of 6 (me,
19:20:35Z-19:21:36Z), 8 of 10 (f2), 4 of 8 (e3, 19:24:42Z); pooled
17 of 24, spread 50% to 83%. The measure invokes `usage.py report`
twice and compares the outputs, and the counter moves between the two
calls. f2's account was right from the start and spent an hour being
argued with.

## What it cost

Roughly an hour across three sessions, three published claims
withdrawn (two of e3's, one of mine), and two ledger rows nearly filed
against a defect that does not exist — "the target is permanently
unmeetable" — which would have become the record the next session
read.

## What changes, and how

Not by a rule in a message. D-PATTERN-1 asks for a mechanism, a
refusal, a planted fault, or a record, and this is the record, with the
planted faults specified in the rows and not yet written:

- **LD-81** — a measure reads once. A measure that invokes the same
  reader twice is not a measure. The tests field forbids, by name,
  proving anything about a measure by reconstructing it in a shell.
  The row carries all three wrong accounts, mine included, so the next
  session reads why the prohibition is there rather than just that it
  is.
- **LD-82** — the gate that asks a session for a lock line asks it of a
  lever that is not a reliable read. `deliverable.py show` answered in
  full at 19:15:5xZ and timed out at 30s at 19:17:59Z from the same
  directory; the compaction onboard logged it UNREACHABLE after a 5s
  and a 20s try. It runs all branches' measures serially and gets
  slower each time a session joins the lock — including when I joined
  it at 19:24Z, taking the lock to 24 branches. A session whose `show`
  times out cannot produce the line the gate asks for and cannot
  satisfy it by working.
- **LD-83** — `usage.py report` answers an unusable path with silence
  at exit 0. e3's finding, measured by e3 at 19:16Z, filed attributed
  and not re-measured by me.

## The lesson worth keeping

A reading that contradicts a peer's reading is evidence about the
instrument before it is evidence about either session. All three of us
reached for an explanation of the other's answer before any of us ran
the thing the way the lever runs it. The cheapest available move —
reproduce the caller's exact invocation path, not the command you
believe it runs — was the one nobody made for an hour.

The second lesson is smaller and mine: when a peer's careful evidence
contradicted my own correct reading, I withdrew the correct reading. I
had already done that earlier in the day over a hook block and been
corrected back by f2; that earlier episode is written here from recall
and is not measured. Deferring to a peer's measurement is right;
treating my own measurement as the weaker one because it is mine is
not.

## Chain of command

The owner's ruling that a message can carry delegated authority when
the sender is authorized, validated by the receiver against the store,
was made mechanical by the Lead as one inform per seat, M-124 to
M-129. Every seat that acted on it ran the check itself: c1 re-based
grant 291 (19:24:21Z) off its own direct hearing onto the validated
relay, 82 held because it had already put the same question to its own
user, e3 validated M-128 and was then blocked by its own terminal's
auto-mode classifier on the grant lever and correctly refused to
rephrase around it. The mechanism did work that a relayed rule would
not have achieved.

Its known weakness is recorded in T-133: `participants --role lead`
returns two rows, PT-9 and the dead PT-2, because the store does not
shed authority when a session ends. The check needs a liveness reading
beside it. e3 measured that independently — PT-9's transcript at
19:24:08Z against PT-2's at 15:31:45Z.

One label error of mine: I addressed several seats about "M-124", which
is my own row. Each seat has its own — 82's M-127, e3's M-128, c1's
M-129. Each of them found theirs regardless and said so.

Source: owner 2026-09-16
