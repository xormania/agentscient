# I-009 — the test writer and the test skeptic never see the implementation

- recorded: 2026-09-04, when the token-meter plan put two rulings to the owner
- source: owner, verbatim below
- disposition: ratified — register row D-FIREWALL-1

## In the owner's words

> what do you think on the two rulings - do we have data so help?

> withhold for both - record it and continue

## What was heard

The lane's law (`ops/process/pipeline.md` row 3, `ops/process/roles/test-author.md`) denies the test author the implementation and the skeptic's brief says "do not read any implementation", but both jobs stage the whole tree, so the denial was a request the worker reported honouring and nobody could check. From now on both jobs stage a file set that withholds the implementation, proved both ways by the harness's own `stage.prove`. The job prompts move with it: the writer runs its tests to check they collect, the red is proven by the caller against the implementation; the skeptic names the broken implementation each weak test would miss and does not plant a mutant. The first two withheld runs are the measurement against today's baseline.

## Standing facts it must reconcile with

- Today's baseline, 2026-09-03: the test writer (Grok 4.6) reported "Implementation unread" on both runs with the whole tree staged; the skeptic (Codex) found three weak tests in 294 lines, two upheld; no test named a function or field that did not exist; the session, not the writer, proved the reds (25 before the code, 0 after) — run records 20260903T222700Z-code-grok-49641f, 20260903T224231Z-review-codex-312a39, 20260903T233939Z-code-grok-c9c4c4.
- The House's measurement, `ops/process/pipeline.md`: of 14 review findings against two checkers built the other way round on 2026-08-24, 11 were missing test cases; the contract-work variant with the specification withheld produced 38 disagreements against the extractor.
- Every catalogue job declares `"snapshot": "whole"` and the launcher refuses any other mode; the fileset mechanism (`ops/devlane/task/fileset.py`, `ops/devlane/harness/stage.py`) exists and is unused — plan 20260904T000335Z-plan-claude-28b1a2 §1, §4.
- The risk named: tests that name interfaces that do not exist; the mitigation is the plan's quoted names and the neighbouring tests kept in the file set; if the first two withheld runs produce more name mismatches than skeptic findings, the writer gets the interface files back and nothing else.
