# I-024 — after the testing and CI overhaul, fine-tune how we work with git and GitHub; re-using capabilities

- recorded: 2026-09-11, in session, after the flag on PR #141 landed (PR #143, dev `c2cdb40`)
- source: owner, verbatim below
- disposition: open

## In the owner's words
> i do think that at some point - after the testing and CI overhaul - we need to fine-tune how we work with git and github - just note it - i have ideas, and the concept of re-using capabilites - something that agents do poor at

## What was heard

The conductor's reading. Two things, in order after the testing and CI overhaul, and only noted now: the owner has ideas on the git and GitHub work that are not written here, and a concept, re-using capabilities, which the owner names as something agents do poorly. The record holds the place; the ideas are the owner's to state when the time comes.

What the day supplied as evidence for the second half: this session declared a hand grant, cut a worktree, wrote a commit message to a file, pushed, opened a draft PR, waited for checks, merged and settled the grant, nine times, each time by re-typing the sequence, and twice got a step wrong (PR #141 merged before its checks registered; PR #142 closed with a truncated commit message). The lane has levers for parts of it (`land.py`, `dispatch.sh`, `deliverable.py`, `hand.py`) and no lever for the whole records-branch round trip; the grant ledger's own line, a recurring absence is a lever demanding to be built, applies.

## Standing facts it must reconcile with

Measured 2026-09-11 against dev `c2cdb40`:

- `python3 ops/conductor/tools/hand.py report` → recurrence by class: other=123, worktree=18, pr-open=4, amend=1; the "other" class is the one with no lever.
- PRs opened by this session: #138, #139, #140, #141, #142 (closed unmerged, branch kept), #143; each by hand through `gh`.
- The lane's law on the trunk, draft-first PRs, never a deleted branch and never an amended pushed commit stands in `AGENTS.md` and the `refused` page; the ideas here would change how the work is done under that law, not the law.

## Next

Not scheduled. After the testing and CI overhaul, at the owner's word.
