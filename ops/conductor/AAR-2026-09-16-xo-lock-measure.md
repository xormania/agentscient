# AAR 2026-09-16 — three sessions, one target, three wrong explanations

Seat: PT-11, the XO (agentscient-43). Grant 290, provenance M-124 from
PT-9, validated 19:14:35Z. Branch `lane/session-20260916-43`, cut from
d919c982. Rows: LD-95, LD-96, LD-97, in commits 4031fe6a and 57ea17f6.
Threads: H-19, T-131 to T-135.

The rows were filed as LD-81, LD-82 and LD-83 and renumbered to LD-95,
LD-96 and LD-97 at 20:09Z, because the id lever handed out ids that
were free on the trunk and taken elsewhere. See "The id collision"
below.

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

- **LD-95** — a measure reads once. A measure that invokes the same
  reader twice is not a measure. The tests field forbids, by name,
  proving anything about a measure by reconstructing it in a shell.
  The row carries all three wrong accounts, mine included, so the next
  session reads why the prohibition is there rather than just that it
  is.
- **LD-96** — the gate that asks a session for a lock line asks it of a
  lever that is not a reliable read. `deliverable.py show` answered in
  full at 19:15:5xZ and timed out at 30s at 19:17:59Z from the same
  directory; the compaction onboard logged it UNREACHABLE after a 5s
  and a 20s try. It runs all branches' measures serially and gets
  slower each time a session joins the lock — including when I joined
  it at 19:24Z, taking the lock to 24 branches. A session whose `show`
  times out cannot produce the line the gate asks for and cannot
  satisfy it by working.
- **LD-97** — `usage.py report` answers an unusable path with silence
  at exit 0. e3's finding, measured by e3 at 19:16Z, filed attributed
  and not re-measured by me.

## The class underneath all of it: LD-99

agentscient-f2 named it at 20:21Z, after each of us had caught our own
instance: "the measurement answered about something other than what was
asked", and if it recurs it is a class rather than a coincidence. It had
already recurred. Counting the day, there are seven instances, six
inside four hours, and they are filed as LD-99.

It is not the same as LD-97. There a tool returns a silent empty answer
where absence discipline wants an explicit marker. Here every tool
answered honestly about what it was actually handed; the operator handed
it the wrong subject and read the reply as the answer to a different
question. `grep -c` counted a pattern in a file that was not there.
`merge-tree` merged a branch against a trunk that already contained it.
A shell expanded a measure the lever never expands. An mtime on
`.git/index` answered a question about `~/.cache/phpactor/index`.

In five of the seven the wrong answer was published to other sessions
before anyone re-measured. In two it was caught only because the result
was impossible — dev cannot have taken a branch whose PR is still a
draft, and eight identical clauses cannot produce three different
readings — and not because the measurement was checked.

The repair is not care, because care is what everyone was already
exercising. It is a positive control in the same command: a case known
to produce the opposite answer, beside the case under test. The one
instance today where the operator got it right the first time is
agentscient-e3 measuring `/tmp` at 246 bytes beside `/nonexistent` at 0
bytes, which is why its `usage.py` reading held up when everything else
that hour did not. `docs/probes.md` already demands exactly this of
`absent` corpus rows and self-detects a pattern that would match its own
directory. The rule exists; it is simply not applied to measurement
outside the corpus.

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

## A fourth instance, and the first the mechanism caught

Three of the day's faults were caught by a peer. The fourth was caught
by the lock.

agentscient-e3 wrote its own lock measure to `echo` only on success, so
"this is not on dev yet" came back through `reading()` as
`unreachable (exit 1)` — could-not-look reported where looked-and-found-
nothing was true. That is LD-97, the row e3 itself found against
`usage.py report` at 19:16Z and which I filed on its behalf at 19:25Z,
reproduced by its author in its own lock entry while the row was open.
e3 reports it corrected: the measure now prints `donegate=not-on-dev`
and exits 0, and the `done` verb returns a refusal carrying the finding
instead of an unreachable.

    target: expected the measure to read donegate=on-dev; found
    donegate=not-on-dev; needed keep going; done is the reading, never
    the named slices

Short, and correctly short. The distinction the wire asks for is the
difference between those two readings, and the lever now makes it.

What is worth keeping is not that a fourth session made the same class
of mistake. It is that this one was caught by the instrument rather
than by another session reading the report afterwards. The first three
cost an hour of peer argument each; this one cost a minute and one
message, and the reason is that the fault landed somewhere a mechanism
was already looking.

## The fifth instance: the row finding its own fourth defect

agentscient-e3 reports, and I have not re-measured it, that
`LOCK_LINES` anchored at column 0. All four accepted forms are rejected
under two spaces, four spaces, a tab, a fenced block or a `>` quote. A
session pasting a reading the way output is normally pasted was not
seen to have pasted anything.

The case that names it: the row prints
`target: expected the measure to read ...`, lists that line as one of
its three accepted remedies, and then refuses it when the session
pastes it indented. e3 ran `done`, pasted its refusal in a fenced block
exactly as instructed, and was refused for carrying no lock line. The
remedy the row hands out did not satisfy the row.

Two mechanisms in one gate were also contradicting each other. The
model-judged layer registered beside the deterministic one publishes
that a reading counts "inside a fenced code block, a quote or plain
text alike". So a session complying with the published rule of one
layer was refused by the other, with no way to satisfy both.

This is the fifth instance and it has the shape of the fourth, not the
first three. The mechanism caught it, not a peer; it cost one block
rather than an hour of cross-session argument. What is particular about
it is how it was found: the row refused the report of its own first
three fixes, and that refusal was the only thing that could have
surfaced the fourth. A defect that hides every pasted reading cannot be
found by reading pasted readings.

The count for the day is five instances of a session committing the
fault it had just documented. Three cost an hour each and were caught
by a peer. Two cost minutes and were caught by an instrument. That
ratio is the whole argument for D-PATTERN-1 preferring a mechanism to a
rule relayed by message, and the day made it without anyone arguing it.

## The gate refusing the report of its own fix

e3 reports that the deterministic done-gate blocked its previous reply
although that reply carried a conforming lock line, because the main
checkout still runs the old anchor and e3's line carried a `(by ...)`
stamp that the old anchor does not admit. The fix for exactly that
anchor is the change e3 was reporting at the time, in #258. The gate
stops refusing it when #258 reaches dev.

I did not see that block myself and am not reproducing its text here;
this paragraph is e3's reading, attributed, and the verbatim refusal is
in e3's own transcript. What I did measure is the same anchor defect
from the other side earlier this evening: of 21 target lines in the
lock, only the four unstamped 2026-09-15 ones satisfy the old anchor,
and my own stop passed only because those four happened to be in the
output I pasted.

## The id collision, found while routing another seat's stranded work

`defects.py next` fetches `origin/dev` and answers with the first id
free there. It answered LD-81 for me at 19:25:34Z, and LD-81 was
genuinely absent from `d919c982`, the commit this branch was cut from
— `git cat-file -e d919c982:ops/conductor/handoff/lane-defects/LD-81.md`
reads ABSENT. By 20:08Z `origin/dev` had moved 21 commits to 5e707cfa
and carried a different LD-81, about the conductor suite's per-test
time. Two rows, one id, neither aware of the other.

The trunk is only half of it. Measured at 20:07:55Z, branch
`lane/session-20260916-09` holds seven commits that are on no other
branch, has no pull request in any state
(`gh pr list --state all --head` returns `[]`), and its last commit is
stamped 2026-09-16T15:20:09Z. It carries LD-81 and LD-83 of its own,
plus LD-84 through LD-90. Its session is PT-7, which last wrote before
16:02Z. So five to nine records have no route to the trunk, and the
ids they hold are invisible to the lever that hands out the next one.

Counted across `origin/dev`, `lane/session-20260916-09`,
`lane/session-20260916-f2` and this branch at 20:08Z, the highest id
observed anywhere is 93, while `ledger.py next defects` answers 94 and
agentscient-f2 read an LD-94 at 18:43:26Z that is on no origin branch.
These three rows took 95, 96 and 97 to clear all of it.

This is the collision S2 exists to close, measured live, with three
seats inside it: PT-7's stranded rows, f2's LD-94 reading, and mine.
It is also the second time today that a lever answered a question
about the world by looking at one branch: LD-95 is a measure that
reads a moving counter twice, and this is an id allocator that reads
one ref once. The shape is the same — a reading taken where the
answer does not live.

Source: owner 2026-09-16
