# I-008 — the port stops at the specification: PR #10 closes unmerged

- recorded: 2026-09-03, after the session measured PR #10 for the owner
- source: owner, verbatim below
- disposition: open — register row D-PORT-2 proposed; it narrows D-PORT-1's "whole" and would supersede D-CI-2, and neither moves until the owner rules

## In the owner's words

> lets figure out PR10 first - what is its status?

> its 150k lines of code - i feel like something got screwed up here. What happened?

> i understand the fixtures - don't need them; what do we need from it?

> ok do the extraction PR and close #10 - just make sure we're not overriding the decisions we've alread made

## What was heard

The second freight of the House lane does not merge. What the twins
need from it is specification, not code: the workflow plan, the twelve
CUE contracts and their notes, the seed's four contracts, the BDD
feature shelf, the four shelf pages the process law cites, and the
idea record D-VOCAB-1 points at. The House's design memos about this
framework cross as archived reference behind a banner, never as law.
The engine runtime, its suites, the fault corpora and observations,
the packets and verdicts, the House CI shape, the seed's vets and
plans, the guide pages, and the cross-app import boundary stay on
`lane/workflow`, which is never deleted.

"Not overriding the decisions we've already made" is read two ways
and both are honored: no extracted file changes a ruling in
`AGENTS.md` or `docs/`, and no ratified register row changes standing
by the session's hand. D-PORT-1 (the lane crosses whole) and D-CI-2
(CI takes the House shape) both demand what PR #10 carries; closing it
leaves them ratified with their claim unmet, so D-PORT-2 is proposed
with these words as evidence, for the owner to ratify or reject.

## Standing facts it must reconcile with

- PR #10 at head `e354dac`: 677 files, +150,686 / −97 lines; draft; CONFLICTING against `dev` at `477fd28`; zero check runs, zero workflow runs, zero reviews — `gh pr view 10 --json ...`, `gh api repos/uscient/agentscient/commits/e354dac.../check-runs`, 2026-09-03.
- It conflicted from the minute it opened: `git merge-tree --write-tree e59ffb9 origin/lane/workflow` (dev's tip 18 minutes before the PR opened) exits 1 on `.github/workflows/ci.yml`; a `pull_request` workflow needs a merge commit to run, and the branch's own workflows push-trigger only on `main` and `dev`.
- The lines: 85,856 JSON, 36,920 Python, 24,058 Markdown; 66,345 under `contracts/faults` where each corpus is a whole copy of a 3,700-line observation with 1 to 70 lines mutated — `git diff --numstat cdb88bb origin/lane/workflow`, `diff obs/cli.json faults/cli.10.json`, 2026-09-03.
- The copy is faithful: the House's `.dev/app/workflow` at `99334f7` is 399 files and 129,950 lines; the PR's `ops/devlane/workflow` is 391 files, 12 new here, 9 not carried.
- Every lane suite on the PR head, `bash ops/bin/suites.sh` in a detached worktree at `e354dac`: 8 of 9 OK; workflow 993 tests, 11 failures, 3 errors, all in the guide index, the vocabulary wall, the CI-shape pins and one promotion test; 7m01s.
- The branch's own CI derivation lists 24 contexts, not the 25 the PR body states — `python3 ops/devlane/workflow/checks/ci_contexts.py checks.json` on the PR head; the dev ruleset and master protection require only `ci`, which the PR deletes.
- Register at the moment of recording: D-PORT-1 and D-CI-2 ratified, D-VOCAB-1 proposed with its home (I-007) on `lane/workflow` only — `python3 ops/conductor/tools/decisions.py list`.
