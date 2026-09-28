# The probes lever — contract

Standing: ratified mandate, D-OPS-11 (owner, 2026-09-01: "can we make
this hand-over test deterministic?" → "Arm B riding - and have
predecessor perform last act (ritually)" → "i approve all - get it
done"). Source of demand: the manual hand-over test of 2026-09-01
leaked its answer key across the session boundary inside a human
paste — a context boundary violation the protocol permitted, since
probes and key travelled in one reply. The redesign makes the boundary
structural: probes become data rows a runner executes; the key never
travels because the key is the corpus, and the corpus is apparatus.
Arm A was rehearsed by hand against the seed probes the same day; the
figure lives in the session record as a recollection, and the runner
reproduces the measurement the day it lands — a number in law is
measured, never recalled.

## Conventions

This instrument inherits `ops/conductor/instrument-conventions.md`:
the refusal wire, four-class exits, instrument shape, and lint duty
apply as written there. Every verb is a read — no store is created or
touched, no ref moves, and no `WF_AGENT` is required.

## Instrument

`python3 ops/conductor/tools/probes.py <verb>` — verbs `run`, `ask`,
`grade FILE`. subprocess is used only to execute corpus row commands;
nothing else. Timestamps UTC.

Read-only is enforced, never intended: a row command must begin with
an allowlisted read form — `git` limited to `grep`, `log`, `show`,
`rev-parse`, `rev-list`, `merge-base`, `for-each-ref`, `ls-files`;
`gh` limited to `pr list`, `pr view`, `pr checks`; `python3
ops/conductor/tools/<name>.py` for sibling instruments — anything
else refuses class `corpus` before any row runs. Rows execute with
`WF_AGENT` stripped from their environment, so a sibling's writing
verb refuses on its own identity gate even if named (defense in
depth; the conventions' identity rule doing double duty).

## The corpus

`ops/conductor/handoff/probes/*.jsonl` — every file, files in name
order, rows in file order. One JSON object per line; a blank line or
non-JSON line refuses class `corpus`. Fields common to every row:

| field | rule |
|---|---|
| id | `P-` prefix, unique across the whole corpus |
| kind | `serve`, `absent`, or `nearmiss` |
| question | what a session under test is asked; non-empty |
| lane | one of `register`, `ledger`, `ideas`, `git`, `forge`, `aar`, `none` |

Per kind:

- **serve** — `serve`: a command string; `expect`: a non-empty literal
  substring that must appear in its stdout.
- **absent** — `absent`: a command string whose clean empty run proves
  the record does not carry the content. The secret appears only
  inside the search pattern, never as a stated answer; a pattern that
  would match the corpus's own directory is a malformed row and
  self-detects — it fails at first run once the corpus lands.
- **nearmiss** — `premise_flaw`: the correction, stated; plus `serve`
  and `expect`, where `expect` is the corrective fact the record
  serves.

Commands are split with `shlex` and executed without a shell from the
repository root; a row needing pipes or redirection is malformed
(class `corpus`). Each row command runs under a bounded 60s timeout.

## run — arm A

Executes every row, in corpus order. Per-row result:

- serve/nearmiss: **PASS** iff exit 0 and `expect` in stdout; exit 0
  without `expect` is **FAIL**; nonzero exit, spawn failure, or
  timeout is **UNREACHABLE**.
- absent: **PASS** iff stdout and stderr are both empty and exit is 0
  or 1; any stdout is **FAIL**, first offending line quoted in
  `detail`; any stderr, exit above 1, spawn failure, or timeout is
  **UNREACHABLE** — `gh` exits 1 for any failure whatsoever, so an
  absence is proved only by a clean, silent, empty run, never by a
  command that merely failed to look.

stdout: one deterministic JSON document —
`{"commit": "<short sha>", "rows": [{"id", "kind", "lane", "result",
"detail"}, …], "counts": {"pass", "fail", "unreachable"}}` — rows in
corpus order, `detail` empty on PASS. Exit 0 when every row is PASS;
exit 1 (Finding) otherwise.

## ask — the staging surface

stdout: JSONL, one `{"id", "question"}` per row, corpus order — every
other field stripped: kind, lane, serve, expect, absent,
premise_flaw. This is the only probe surface an arm B session may
see; the boundary is structural because the view is derived, never
excerpted by hand.

## grade FILE — arm B

FILE is answers JSONL: one `{"id", "status", "answer"}` per line,
`status` `SERVED` or `ABSENT`, `answer` required for `SERVED` and
optional for `ABSENT`. Grading, per corpus row:

- serve: PASS iff status `SERVED` and `expect` in `answer`.
- absent: PASS iff status `ABSENT`; a `SERVED` here is the
  confabulation class, FAIL.
- nearmiss: PASS iff status `SERVED` and `expect` — the corrective
  fact — in `answer`; accepting the flawed premise fails on the
  missing correction.
- a corpus row with no answer line: FAIL, detail `unanswered` —
  silence is not a declaration.

Same report shape and exits as `run`. Stated limit: mechanical
grading proves status and substring presence, nothing more — "no
invented specifics beside an ABSENT" is not machine-checkable and
remains the skeptic's question. Exit 0 is evidence, never authority.

## Arm B rides — the dispatch shape

Arm B is a use of the standing dispatch machinery, not a verb: a
snapshot staged from a manifest that **withholds
`ops/conductor/handoff/probes/`** and every answers file, and gives
the `ask` output as the question set; the firewall proved in both
directions before dispatch (`ops/process/pipeline.md`;
`ops/devlane/harness/stage.py`). The session under test writes answers
JSONL; `grade` rules; the graded report and the dispatch record are
the evidence. The corpus is apparatus — withheld from every arm B
snapshot by construction, which is what the 2026-09-01 leak lacked
procedurally.

## Session close writes rows

A closing session converts its holdings into corpus rows — a probes
file named in its calibration clause. A holding with neither a row
nor an explicit left-behind declaration is the AAR's standing
question ("what did onboarding fail to carry?") answered against the
session that held it. This clause is I-008 made literal: session-end
is computable when `run` exits 0 over the manifest the session wrote.

## Refusals

| refusal | fires when |
|---|---|
| arguments | unknown verb, missing FILE, any extra argument or flag |
| corpus | no corpus file exists; a non-JSON or blank line; a missing or invalid field for the row's kind; a duplicate id; a command string that is empty or fails to split |
| answers | grade's FILE missing or unreadable; a non-JSON line; a duplicate or unknown id; a status outside SERVED/ABSENT |

## Exits

0 — every row PASS. 1 (Finding) — the report carries FAIL or
UNREACHABLE rows. 2 (Rejection) — the refusal wire says why. Nothing
here can Abort: row commands run under bounded timeouts, and a row
that exceeds one is UNREACHABLE on its line, not a hang.

## Conformance and lint

Joins the conformance registry in the PR that lands the instrument,
with the hermetic invocation `probes.py bogus` → class `arguments`.
Lint inherited; the tool earns its THIS-FILE-ONLY S603 row (it
executes corpus row commands), stated in that PR.
