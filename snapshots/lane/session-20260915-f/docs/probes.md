# Probes — deterministic hand-over

Context custody across a boundary — session to session, worker to
worker, version to version — is tested by probes, not trusted to
memory. A probe corpus is data; a runner executes it; the result is
a wire outcome, not a judgment.

## Corpus rows

One JSON object per row. Three kinds:

- **serve** — a command and a literal substring its stdout must
  contain: the record can answer this.
- **absent** — a command whose clean, silent, empty run proves the
  record does not carry the content. The secret appears only inside
  the search pattern, never as a stated answer; a pattern that would
  match the corpus's own directory is malformed and self-detects at
  first run.
- **nearmiss** — a question whose premise is deliberately wrong,
  plus the corrective fact the record serves. Accepting the premise
  fails on the missing correction.

Row commands are restricted to an allowlisted read set and run with
identity stripped, so read-only is enforced, never intended.

## Runner semantics

- serve and nearmiss: pass only on exit 0 with the expected
  substring present.
- absent: pass only on empty stdout AND empty stderr with exit 0 or
  1 — some tools exit 1 for any failure whatsoever, so silence is
  part of the proof. Any stderr, exit above 1, spawn failure, or
  timeout is UNREACHABLE.
- UNREACHABLE is never a pass and never a fail: an arm that could
  not look has no result. Reports carry pass, fail, and unreachable
  counts separately; unanswered rows fail — silence is not a
  declaration.

## The staging surface

A derived probes-only view (id and question, every key field
stripped) is the only surface a session under test may see; the
corpus is apparatus, withheld from every test snapshot by
construction. Grading is mechanical: status and substring only, with
its limits stated — what mechanical grading cannot check remains a
reviewer's question, and exit 0 is evidence, never authority.

## Session-close manifests

A closing actor converts its unique holdings into corpus rows; a
holding with neither a row nor an explicit left-behind declaration
is the hand-over failing, named. Close is computable: the runner
passing over the manifest the actor wrote.
