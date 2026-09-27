# Context fixtures on a local model

Owner, 2026-09-04, in session, after reading the compaction
side-effects report (`.dev/tmp/compaction-side-effects-2026-09-04.md`,
whose third question asks whether the pre-compaction hand-off should
be produced by an instrument): "i was thinking the same thing about
upgrading the probes - i had a thought: can we do context fixture
testing with a local cheap model?"; then: "its a theoretical question
- using a local ollama hosted model for context fixtures in each
harness".

What exists today. The probes contract (`docs/probes.md`) has three row
kinds; every row carries a natural-language question and a command
with an expected substring, and the runner runs the command. The
question is the staging surface "a session under test may see", but
nothing plays that session: the corpus is fourteen rows across two
files (`ops/conductor/handoff/probes/`, ten serve and four nearmiss),
graded by command only. The firewall is proved mechanically in both
directions (withheld absent, given present), but nothing proves that
the context a harness is handed serves what its job needs. Measured
on the box the same hour: 32 cores, 30 GiB, an RTX 4070 Ti SUPER with
16 GiB visible under WSL (`/dev/dxg`), no local model runtime
installed.

The idea, in two readings, both worth keeping.

First reading, the lane's own context. A local model behind Ollama
plays the reader with no memory. The fixture is the exact bytes a
dispatch renders (`prompt.txt`, the `in/` files, the snapshot's
tracked text), or the hand-off and the compaction summary at a session
boundary. The runner puts the fixture in front of the model with each
probe question, tells it to answer with the exact value or `NOT IN
CONTEXT`, and grades the answer by the row's substring, the same
mechanical grade as today. Serve rows measure whether the context
carries the fact; absent rows stay grep, because a model's "I don't
know" is weak evidence and grep's silence is proof; nearmiss rows are
measured but not gated until the rates say a small model rejects a
wrong premise reliably. Every run is a row: fixture bytes, model,
question, answer, grade, time. Cost per run is seconds and no money,
so it can run before every expensive dispatch as a gate (refusal class
`context` on the wire when a required row is not served), at every
compaction as a score printed in the onboard brief, and across
alternative wordings of a hand-off or a prompt template to learn which
form a weak reader is served by best. That last use is the training
set the owner keeps naming (I-012).

Second reading, each harness's assembled context, which is the
owner's phrase. A harness assembles context the lane does not render:
Claude Code loads `CLAUDE.md`, skills, memory and hook output; Codex
loads `AGENTS.md`; Grok reads through the compatibility layer. Running
the harness's own CLI inside the job snapshot with a local model as its
backend, and asking it the probe questions, proves what that harness
actually assembled, per harness and per job, without spending a
frontier model on the question. Codex's configuration takes an
OpenAI-compatible base URL; Claude Code takes a base URL for its API
and needs an endpoint that speaks it; whether Ollama serves either
directly is measured when the seat is built, never assumed here.

What bounds it. A weak model's failure conflates "the context lacks
it" with "the model could not find it", so the check carries its
calibration (`docs/concerns.md`): planted faults it must catch (the
fixture with the fact removed fails its row), clean neighbors it must
pass, and the rates reported beside every verdict; a row the model
cannot answer on the clean fixture is a declared calibration gap, not
a gate. Ollama is a vendor edge like any other: a contract naming the
API relied on, a probe that checks the live endpoint, a mock that
answers the fixtures in tests, the model named at dispatch; when the
endpoint is down the gate reports UNREACHABLE and the dispatch proceeds
with that absence declared, never silently. The lane stays bounded: a
`probe-answer` job and a `local` harness in the launcher, the runner
extended, nothing new in the kernel.

The reading is the conductor's. Not ruled; not scoped; recorded so the
compaction report's third question and the probes contract's "session
under test" have a named answer when the queue reaches them: after the
lane conf, the ladder driver and the fixture apps land.
