---
name: close
description: Measure the board and write the record from the output - before an AAR, a handoff, a ready note, a merge, or the word done. Every worktree's unpushed commits, every ladder's state on dev, every open finding, grant, dispatch and PR, quoted, then the record. Use at every session close and before any claim that work landed.
---

# close — nothing is complete until dev says so

Why it exists, measured: the 2026-09-11 AAR said slice 5's records were
complete while five record commits sat unpushed in a worktree, counted
LD-16 among the second-producer tests, and described a merged release
as open; eleven findings the tests-fix stages had answered stayed
`open` in the store. On 2026-09-10 settlement commits left record bytes
outside git and an edit was left uncommitted on a docs branch. Today
the ledger holds 567 open findings of 765 and 82 grants settled without
verification. Every one of these was a claim written from memory.

The order matters: measure, then write. A record written first and
checked after is the record that was wrong today.

## The measurements, pasted in this order

1. **Worktrees.** Uncommitted and unpushed, per worktree the session
   touched. No upstream means everything on it is unpushed:

   ```sh
   git worktree list --porcelain | awk '/^worktree /{print $2}'
   git -C <wt> status --short | wc -l
   git -C <wt> log --oneline @{u}..HEAD 2>&1 | head -5
   ```

   A table: worktree, branch, uncommitted, unpushed. Any non-zero line
   is either pushed now or named in the handoff as left behind on
   purpose, with the reason.

2. **Pull requests.** State and checks of every PR the session opened
   or touched:

   ```sh
   gh pr list --state all --limit 20 --json number,state,isDraft,headRefName,mergeCommit
   gh pr checks <number>
   ```

   "Merged" in the record is a merge commit sha from this output.

3. **Ladders.** For each ladder record the session ran or resumed, the
   copy on dev against the copy in its worktree:

   ```sh
   git show origin/dev:.dev/records/ladders/<id>.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["status"], d["stopped"])'
   python3 -c 'import json; d=json.load(open("<wt>/.dev/records/ladders/<id>.json")); print(d["status"], d["stopped"])'
   ```

   The two lines agree, or the worktree's records are not on dev and
   step 1 was wrong.

4. **Dispatches.** Anything still running, and any record on dev that
   still reads `launched`:

   ```sh
   python3 .claude/skills/dev-subs/subs.py
   python3 -c 'import json,glob; print([p for p in glob.glob(".dev/records/dispatches/<today>*.json") if json.load(open(p))["status"] == "launched"])'
   ```

5. **Findings.** Open rows on every record the session's reviews
   produced, then the export refreshed and committed:

   ```sh
   sqlite3 ~/.local/state/agentscient/findings.db "select record, count(*) from findings where disposition='open' and record like '<today>%' group by 1"
   python3 ops/conductor/tools/findings.py export --write
   ```

   An open row is disposed with its citation or named in the handoff
   as open, with why. It is never left silent.

6. **Grants and the lock.** Read the text, not a line count (pitfall
   6: `no open grants` is one line):

   ```sh
   python3 ops/conductor/tools/hand.py open
   python3 ops/conductor/tools/deliverable.py show
   ```

   Every grant settled with evidence; this session's branches removed from the lock (`deliverable.py remove`) when the
   deliverable has landed, or left set with the reason in the handoff.

6b. **Handoffs.** What this branch still has claimed, then the package for
   whoever comes next, both in the state engine's store and never in a
   file (`handoff-lever.md`; owner, 2026-09-13: "a new branch/PR per
   session handoff is excessive"):

   ```sh
   python3 ops/conductor/tools/handoff.py held --branch <branch>
   python3 ops/conductor/tools/handoff.py open '<title>' --summary '<the owner's register>' --branch <branch> --prs '#n #m'
   python3 ops/conductor/tools/handoff.py thread H-<n> '<title>' --body '<where to pick it up: record ids, PRs, files>' [--to <role or session>]
   ```

   `held` prints `none held` with exit 0 before the session calls
   itself finished; a thread it took is closed with `done T-n
   --evidence <sha, #PR, record id or P- row>` or given back with
   `release T-n --why`. Every open thread of the session is a `thread`
   row; the next session reads them at onboard (`== handoffs`) and
   claims with `take`. No row needs the merge sha, so no records PR
   trails the work: the AAR, when one is written, rides the session's
   own PR, and what went wrong goes to the pitfalls and defects
   ledgers.

7. **Then write.** Every "merged", "complete", "green", "settled" in
   the AAR or handoff names the sha, PR number, record id or grant id
   from the lines above. What was not measured is written as "not
   measured", never as a default that reads as an answer.

## What this page never accepts

- A record written before the last merge it describes, unless the
  record says which merges are still open.
- "Complete" for a worktree that is not in the step 1 table.
- A count of "second-producer tests" or "regression tests" that is not
  matched one to one against PR numbers in step 2.
- A close without the export in step 5 committed.
- A capability written as done, wired, or in use without the reading that
  shows it consumed: the dispatch record id whose argv or brief carries
  it, or the dispatcher dry-run argv pasted in. Built and tested is not
  done (owner, 2026-09-12: "you can't take any agents word on anything -
  you need proof, evidence"; measured that day: the per-job effort key,
  the lane MCP and the onboard brief were each recorded as done and
  never consumed by a worker).

Record the use: `python3 ops/conductor/tools/skills.py log-use close "<record written>"`
with `WF_AGENT` set.
