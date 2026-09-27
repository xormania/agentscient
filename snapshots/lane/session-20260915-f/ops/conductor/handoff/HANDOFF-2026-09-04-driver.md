# HANDOFF — 2026-09-04, the driver session, for the next actor (Codex expected)

Written 17:30Z by the Claude Fable 5.1 session
(https://claude.ai/code/session_01G4v6DAdY5nJuaBqfNWUEKJ) at the owner's
instruction, with the owner's Claude budget at 95 percent of the week
until 2026-09-06. The report is `ops/conductor/AAR-2026-09-04T17-driver.md`.
The full untracked log of the day is `.dev/wip/handoff-2026-09-04.md`;
the ledger is `.dev/wip/scope-lane-fixes.md` (items 1 to 49). Paths
below are on this machine; `W` is the item 31 worktree.

    W=/home/scientdb/projects/uscient/wt/ag-check-tests-json
    D=$W/.dev/ladder-inputs/fix-round      # durable inputs and run scripts
    S=/home/scientdb/.local/state/agentscient/dispatch   # records

## Rules that bind whoever takes over

- Read `AGENTS.md` and `ops/README.md` before dispatching. Every launch
  goes through `ops/bin/dispatch.sh`; every landing through
  `ops/conductor/tools/land.py RECORD_ID` run inside the worktree with
  `WF_AGENT="Name <address>"` set and alone in its command. Commits are
  authored xormania through LANE_AUTHOR in `ops/lane.conf`.
- Do not run a stage by hand except the steps below, which finish an
  already-hand-run batch under open grant 43. A driver hole is a ledger
  item and a plan, never a hand run (owner, 17:28Z: "why would you not
  fix the issue instead of doing the one thing that is fatal?").
- Never merge trunk into a branch mid-ladder. Merge `origin/dev` only
  before the PR, after the batch's last stage.
- Plans and reads run on Grok while the Claude budget is out: `--job
  plan --harness grok`. The conf's Claude models are not usable.
- TALK as the first word of an owner message means pause and talk.
- Bound every command's output; one turn per stop event; compact or
  close at 300k context. Tokens are the constraint this week.

## Runbook: finish item 31 (skeptic report custody), then merge it

Running now on Grok, no Claude tokens: `20260904T172006Z-code-grok-7aaf95`,
the fix round's tests half (pins the two audits' findings as red tests,
fixes three ruff SIM300 lines). The audits it answers: security
`20260904T170030Z-review-codex-10274e` (changes, 1 P1, 2 P2) and
adversarial `20260904T170050Z-review-grok-41c1f5` (changes, 1 P1, 3 P2).
Both envelopes verbatim are in `$D/input-check-tests-json-2-fix-tests.md`.

1. Wait for the record to close, then read its verdict:

       python3 -c "import json;d=json.load(open('$S/20260904T172006Z-code-grok-7aaf95/record.json'));print(d['status'],(d.get('result') or {}).get('envelope'))"

2. Land it (alone in its command, inside `$W`):

       cd $W && python3 ops/conductor/tools/land.py 20260904T172006Z-code-grok-7aaf95

   Suites may be red now: the new tests pin the findings until step 3 lands.

3. Sol's code half (Codex implement; the run script carries
   `HAND_GRANT=43` on line 1 and the discover-form test command as scope):

       setsid nohup bash $D/run-fix-code.sh > $D/fix-code.log 2>&1 < /dev/null &

   Wait for its record (`grep record: $D/fix-code.log`) to close; land it
   as in step 2; then `bash ops/bin/suites.sh && ruff check .` must be
   green. Retry cap is 2; a third failure stops the batch (ledger).

4. Security re-audit only:

       setsid nohup bash $D/run-reaudit.sh > $D/reaudit.log 2>&1 < /dev/null &

   Verdict ok: step 5. Verdict changes: STOP. `findings.py import` the
   envelope, add a ledger item, plan the leftovers as the next slice. No
   second fix round (owner: no eighteen-hour loops).

5. Draft PR into dev, then merge:

       cd $W && git merge origin/dev && bash ops/bin/suites.sh && ruff check . \
         && git push -u origin lane/check-tests-json
       gh pr create --draft --base dev --title "task: check-tests returns its report on the wire; the driver keeps custody" --body-file BODY.md

   BODY.md: What / Sources (record ids above) / Evidence (suite and ruff
   lines, measured) / For reviewers, then the footer `🤖 Generated with
   [Claude Code](https://claude.com/claude-code)` and the session URL if a
   Claude session wrote it. Watch the checks (lane, app, CodeQL), then
   `gh pr ready N` and `gh pr merge N --merge`, then
   `git -C /home/scientdb/projects/uscient/agentscient pull`.

6. Settle the grant with an evidence file (a long string fails):

       python3 ops/conductor/tools/hand.py settle 43 --evidence <file>

## Then: the parked ladders, through the driver

In each worktree: `git merge origin/dev`, then
`ops/bin/ladder.sh resume <ladder id>`.

| ladder id | worktree |
|---|---|
| 20260904T132749Z-ladder-f5d171 | ../wt/ag-dispatch-job-scratch |
| 20260904T132831Z-ladder-50b74b | ../wt/ag-fixture-fix-2 |
| 20260904T154352Z-ladder-82c80f | ../wt/ag-context-contracts |
| 20260904T164941Z-ladder-334f07 | ../wt/ag-noguess |
| 20260904T114835Z-ladder-3d3c79 | ../wt/ag-record-wall |

Each stopped at the skeptic with the defect 31 fixes; if one stops there
again after 31 is merged, 31 did not fix it: ledger, not hand.

## Then: item 49, the session budget

Grok plan running: `20260904T172250Z-plan-grok-2c8a8f`; its `out/PLAN.md`
is under `$S/20260904T172250Z-plan-grok-2c8a8f/`. One plan file per
slice, whitespace-separated bucket files, then `ops/bin/ladder.sh
<scope> <branch> <plan>` per slice. Inputs it was given: the token-churn
analysis (`$D/token-churn-2026-09-04.md`), ledger items 48 and 49, the
matrix contract v4.

## Open owner rulings

- The seven proposed rules R1 to R7 in `$D/token-churn-2026-09-04.md`.
- No-hardcoding plan (Grok d5892c): deny at write time; JSON exception
  table not CUE; CI strict on the PR diff only until identities are
  clean; the record's lane field reads TRUNK_BRANCH.
- The straggler sweep (one security audit, one adversarial review on
  dev's merged tree) after the first-pass merges; the release draft dev
  to master, merged by the owner alone.

## Known traps, measured today

- The matrix hook (Claude sessions only) refuses: a lane test path as a
  read-only argument inside a heredoc (hand-write); `grep -E a|b | head`
  over a log (clipped-sweep; count first, then `tail`); a pgrep argument
  naming the launcher (direct-launch); `$SP` in a heredoc dispatch line
  (input-absent). Write run scripts with literal absolute paths.
- The driver refuses a plan with more than one slice; bucket files are
  whitespace-separated; a resume refuses untracked inputs, so driver
  inputs live under `<worktree>/.dev/ladder-inputs/` and are committed as
  record commits.
- `test_branch_census` is flaky on the shared ref store while other
  workers land; re-run it alone.
- `hand.py settle --evidence` takes a file path.
- The land lever must be alone in its command (an auto-mode classifier
  blocked a compound landing once).
