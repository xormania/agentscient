# I-025 — records commit straight to dev; draft-first is for work

- recorded: 2026-09-12 00:1xZ, in session, after the question of one branch and PR per record
- source: owner, verbatim below
- disposition: ratified by the owner's word; the law's sentences amended by PR

## In the owner's words
> agreed - batch the records into the close-out - and this is something that puzzled me - i want to keep the records - but i new branch and PR for each? seems excessive

> choice #2 - commit to dev for records

## What was heard

The conductor's reading. The one-branch-one-PR habit for records was the lane's own sentences written for code (branch from dev, open PRs into dev, draft-first; one line of work, one worktree; work arrives as draft PRs), not a GitHub constraint: dev carries no branch protection and all three rulesets are disabled. Records now commit straight to dev from the main checkout, the hour they arrive, under the conductor's identity with the usual trailers; the trailer gate and the term wall run on the push and CI stamps every dev commit. Records are the paths the hooks already exempt from the code freeze (`ops/conductor/ideas/`, `ops/conductor/handoff/`, `ops/conductor/AAR-*`, `ops/conductor/probes/`) plus the findings export. Law text, skill pages, contracts and code stay draft-first. This is the first commit made under the ruling.

## Standing facts it must reconcile with

Measured 2026-09-12 against dev `c5ba368`:

- `gh api repos/uscient/agentscient/branches/dev/protection` → required pull request false, required checks none, enforce admins false; `gh api repos/uscient/agentscient/rulesets` → three rulesets, all disabled.
- `ops/devlane/hooks/claude/matrix.py` `RECORD_PREFIXES` names the four record paths as not code; the deliverable hook matches worktree creation, branch creation, PR creation and dispatch, not commits or pushes.
- Records merged today by PR before the ruling: #140, #141, #143, #144, one to two commits each, a worktree and a wait for checks each; PR #142 closed unmerged on a truncated message inside that round trip.
- `AGENTS.md` §Ground rules and `ops/README.md` §The rules the lane binds carry the sentences to amend; `ops/README.md` also says the main checkout belongs to nobody, which records now use.
