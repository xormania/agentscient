# Investigation brief — a dedicated harness probe and eval system

Written 2026-09-04 by the session (Fable 5.1) at the owner's request.
An investigation brief, not a scope: nothing here is ruled, nothing is
built, and the queue is unchanged. Every figure was measured when
written; re-measure before relying.

## What the owner said, in order

- "i was thinking the same thing about upgrading the probes - i had a
  thought: can we do context fixture testing with a local cheap model?"
- "its a theoretical question - using a local ollama hosted model for
  context fixtures in each harness"
- "write it up for further investigation - i like this idea - but I
  want to create a dedicated stand alone harness probe, eval system
  (the probes used here are from another project of mine)"
- "in fact - the symfony app can do it - can't it?"
- "not now - just write it up"

Reading: the probe design in use here (`docs/probes.md`, the corpus
under `ops/conductor/handoff/probes/`) was carried over from the
owner's previous project. The owner wants a system of its own, built
to stand alone, that probes and evaluates harnesses; and the Symfony
app is the place to build it. Idea I-016 (merged, PR #35) holds the
first thought; this brief is the next step past it.

## What exists, measured 2026-09-04

| item | measured |
|:--|:--|
| probe contract | `docs/probes.md`: serve, absent, nearmiss rows; runner semantics; UNREACHABLE; the staging surface; session-close manifests |
| probe corpus | 14 rows in two files (10 serve, 4 nearmiss), each a question, a command and an expected substring |
| probe runner | none in this repository (`grep -rl nearmiss` over `.py`, `.sh`, `.php` outside `vendor/`: only the corpus and the docs); the runner lives in the previous repository |
| mapping | `docs/mapping.md` row "probes": a Console command with Process under an allowlisted read set, identity stripped; Scheduler for cadence; PHPUnit for mechanics |
| harness CLIs on the box | claude 2.1.260, codex-cli 0.153.2, grok 1.0.13; ollama absent |
| the box | 32 cores, 30 GiB, RTX 4070 Ti SUPER with 16 GiB visible under WSL (`/dev/dxg`); no local model runtime installed |
| symfony/ai here | `symfony/ai-mate` 0.13.0 and its Symfony extension only; the platform package is not installed |
| symfony/ai upstream | `ai-platform` v0.13.0 released 2026-08-30; bridges in the repository include Ollama, LmStudio, DockerModelRunner, TransformersPhp, ClaudeCode, Codex, Anthropic, OpenAi, Generic, Failover, Cache |

The last row is the answer to "the symfony app can do it": the
platform the standing ruling already commits to ships a bridge for a
local Ollama model, bridges that spawn the Claude Code and Codex CLIs
as subprocesses, a generic bridge for any OpenAI-shaped endpoint, and
a cache and a failover wrapper. The model is named at dispatch, never
in a table, as the ruling requires.

## The system in one paragraph

A standalone package that holds fixtures and rows as data, puts a
fixture in front of a reader, asks the rows' questions, grades the
answers mechanically, carries its own calibration, and stores every
run as a row that is never pruned. A reader is any of: a local model
behind Ollama; a vendor model behind its bridge; a harness CLI run
inside a snapshot, pointed at either its vendor or a local backend.
Outcomes are wire outcomes (`docs/wire.md`): served, failed,
unreachable, refused. The system knows nothing about Agentscient's
lane; the lane consumes it as a vendor edge (contract, probe, mock)
and so can any other project of the owner's.

## What it evaluates

1. **Context serve.** Given a fixture context, does the reader serve
   fact X? Serve rows by substring; absent rows by grep, because a
   model's "I don't know" is weak evidence and grep's silence is
   proof; nearmiss rows measured, gated only when the rates earn it.
   Fixtures: the exact bytes a dispatch renders (prompt, inputs,
   snapshot text); a hand-off file; a compaction summary lifted from a
   transcript; a harness's own assembled context (next item).
2. **Harness assembly, per harness and per version.** What a harness
   actually loads on its own (Claude Code: the project file, skills,
   memory, hook output; Codex: its agents file; Grok: through its
   compatibility layer) is not rendered by anyone. The way to see it
   is to be the backend: the app exposes the endpoint the harness
   speaks, records the full request the CLI assembles, and answers it
   from the local model through the Platform. The recorded request is
   the fixture for item 1, and it is the data that says what each
   harness version puts in front of a model. Codex takes an
   OpenAI-shaped base URL by configuration; Claude Code takes a base
   URL for its own API. Whether a given Ollama or Platform endpoint
   speaks each is measured at the pin, not assumed.
3. **Instruction following.** A rule stated in the context, checked
   against the practice in the answer or the diff: "answer with the
   exact value or NOT IN CONTEXT", "do not write an implementation",
   "one commit per file". This is the hypocrisy concern
   (`docs/concerns.md`) turned on harnesses, and it is where "the
   harness ignored the scope" stops being an anecdote.
4. **Hand-over fidelity.** Before and after a compaction or a session
   close: which rows the summary and the hand-off still serve, so the
   compact instructions and the hand-off form are tuned by
   measurement (the compaction side-effects report, question 4).
5. **Cost and latency.** Per reader, per fixture size: tokens, ticks,
   seconds, first-token time, so a gate that runs before every
   dispatch is known to cost seconds and nothing else.
6. **Drift.** Every result is stamped with the harness version, the
   model, and the date (`docs/verified-couplings.md`, freshness).
   Harness CLIs move weekly; a serve rate that falls between two
   versions is a finding with a version beside it.

## Shape, in Symfony terms

- **Corpus**: fixtures and rows as data files, validated by the
  Validator against a declared shape; a row that names a secret in the
  clear is malformed and self-detects, as the probes contract already
  says.
- **Readers**: the AI Platform's bridges (Ollama for local; the vendor
  bridges; ClaudeCode and Codex bridges, or Process, for the CLIs in
  a snapshot). The recording endpoint of item 2 is a controller in
  the same app.
- **Runner**: a Console command, the first of the four projections
  (Console, TUI, MCP resource, API resource); Messenger for runs in
  the background; Workflow for the ladder of a calibrated eval
  (plant, run clean, run faulted, rate, report); Scheduler for the
  cadence of the live probes against each harness.
- **Calibration**: every eval carries planted faults it must catch
  (the fixture with the fact removed fails its row) and clean
  neighbors it must pass, and reports its rates beside every verdict;
  a row the reader cannot answer on the clean fixture is a declared
  gap, not a gate.
- **Store**: SQLite through Doctrine, every run a row (fixture hash,
  reader, version, model, question, answer, grade, cost, time), never
  pruned. The export is a dataset row per run, the same rule the lane
  conf carries for job directories.
- **Reports**: per harness and version, the served, failed and
  unreachable counts separately (unanswered rows fail; silence is not
  a declaration), the calibration rates, the drift since the last pin.
- **Where it lives**: a package under `packages/`, type
  `symfony-bundle`, its own `composer.json`, tests and README, reaching
  siblings only through Composer path repositories, so that "stand
  alone" is true from the first commit and graduation to its own
  repository is a subtree split and a Flex recipe (AGENTS.md, the
  standing ruling on packages).

## Bounds and risks

- A weak reader's failure conflates "the context lacks it" with "the
  reader could not find it". The calibration rates are the only honest
  answer, and they are reported, never hidden inside a verdict.
- The Platform is pinned exactly (0.13.0 today), pre-1.0, probed and
  mocked; no bridge becomes load-bearing. A down endpoint is
  UNREACHABLE, declared, and whatever depended on the gate proceeds
  with that absence stated.
- The recording endpoint sees everything a harness sends, including
  any secret the harness puts in a request. The store is on a private
  box, and the corpus rule about secrets applies to what is recorded.
- Grading is mechanical (status and substring). What mechanical
  grading cannot check stays a reviewer's question, stated as such.
- This would be the first product code in PHP. The owner's boundary
  stands: no PHP or Symfony in the product until the owner is
  comfortable with the dev machinery. So the order is the queue's
  order: the lane conf, the ladder driver, the fixture apps (the
  Symfony fixture app proves the PHP toolchain profile), and then this
  package as a work order through the ladder, written by the lane and
  not by hand. That is the dogfood the owner named.

## First measurements, when the queue reaches it

1. Install a local runtime on the box with GPU support; load two or
   three current instruct models in the 7B to 14B range; measure
   prefill throughput for a 30k-token fixture and answer stability at
   temperature 0 over ten repeats.
2. Run the 14 existing rows against three fixtures: the current
   hand-off, the two compaction summaries in this session's transcript
   (rows 2,986 and 6,477 of the transcript file), and a faulted copy
   of each with one fact removed. Report served, failed, unreachable
   and the calibration rates. This is the first data set and the first
   answer to "does the hand-off serve a reader with no memory".
3. Stand up the recording endpoint and point one harness at it for a
   one-line job; keep the recorded request as the first assembled
   context fixture, stamped with the harness version.
4. Cost the gate: seconds and tokens for the 14 rows against a
   30k-token fixture, so the pre-dispatch use is priced before it is
   proposed.

## Open questions for the owner

- The package's name, and whether it starts under `packages/` here or
  in its own repository from the first commit.
- Which harnesses and versions are in the first pin (the three on the
  box today, plus the local reader).
- Whether the recording endpoint may forward to a vendor as well as to
  the local model (it doubles as a full request log for every
  dispatch; that is data, and it is also every prompt in one place).
- The first eval to run for real: hand-over fidelity (the pain of the
  day) or harness assembly (the unknown).
- Whether idea I-016 takes a disposition line pointing here (ideas are
  amended only on that line, by commit).

## Pointers

`ops/conductor/ideas/I-016-context-fixtures-on-a-local-model.md`;
`.dev/tmp/compaction-side-effects-2026-09-04.md`; `docs/probes.md`;
`docs/concerns.md`; `docs/verified-couplings.md`; `docs/mapping.md`
(the probes row and the symfony/ai row); AGENTS.md standing rulings
(Symfony whole; four projections; packages gestate here).
