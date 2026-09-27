# Brief: regression tests for the scoped freshness pre-check (LD-10)

Lane defect LD-10, owner-authorized 2026-09-11. The pre-check hook
`ops/devlane/hooks/claude/context-precheck.py` compares every
remote-tracking ref before and after its fetch and refuses an outward
command when any of them moved. Two worktrees on two branches in one
session therefore refuse each other's merges. The owner ruled that a
push depends only on the pushed branch's own remote ref, and a PR on its
base as well. The repaired hook, supplied separately after these tests
land, compares only those.

## The rule, verbatim from the repaired hook's docstring

> Fetch before every such command, then compare the refs the command
> depends on: the pushed branch's own remote ref, and for a PR its base.
> If none moved, the command proceeds silently. If one did, it stops.
> Movement on other refs is another lineage's business.

> `relevant_refs(cmd, selected, refs)`: a push depends on the pushed
> branch's own remote ref (the checked-out branch, and every explicit
> `git push <remote> <refspec>` destination); opening or editing a PR
> depends on its base too, the `--base` named one or else the remote's
> default branch (`origin/HEAD`). Detached HEAD with no explicit push
> target keeps the old breadth: every ref.

The fetch itself is unchanged: it always runs, in the repository the
command names, and refreshes every remote-tracking ref there.

## Tests to write

New file `ops/devlane/hooks/tests/test_context_precheck_scope.py`, on the
existing `support` fixture (the seeded remote, the clone on `main`,
`old_sha`/`new_sha`, `restale`), each case run through the hook as a
subprocess with a Bash payload the way `test_context_precheck.py` does:

- from a clone checked out on a branch `records` created off the seed,
  `git push origin records` while only `origin/main` moved → allow, and
  the fetch still landed: `origin/main` in the clone equals `new_sha`.
- the same clone, `git push origin records` while `origin/records` moved
  on the remote → deny naming `origin/records`.
- from `records`, `gh pr create --base main --fill` while `origin/main`
  moved → deny naming `origin/main`.
- from `records`, `gh pr create --fill` with no base while the remote's
  default branch moved → deny naming `origin/HEAD` or `origin/main`.
- detached HEAD, `git push origin records` while `origin/main` moved →
  deny, the old breadth kept.
- `git push origin HEAD:refs/heads/records` while only `origin/main`
  moved → allow: the explicit refspec destination is read.

One existing test changes its expectation, because it pins the old rule:
`test_minus_c_linked_worktree_of_other_denies_and_refreshes_other` in
`test_context_precheck_selected_repo.py`. Its linked worktree is on
`wt-topic` and pushes `topic` while the other repository's `origin/main`
moved. Under the ruling that push is allowed. Keep everything the test
proves about repository selection: the hook must still fetch in the
OTHER repository, so assert allow, `other`'s `origin/main` refreshed to
its `new_sha`, and `cwd`'s refs untouched. Rename it to say so. The D2
and D3 cases in `test_context_precheck.py` are unchanged: their clone is
on `main`, so a push there while `origin/main` moved still refuses.

Prove each new case red at this ref against the unrepaired hook (the
allow cases refuse today; the deny-naming-`origin/records` case is red
because today's message names every moved ref), commit, and list the
files in artifacts.

Frozen command:
`python3 -m unittest discover -s ops/devlane/hooks/tests -p 'test_context_precheck*.py'`

## First-run walkthrough

- assumption: the snapshot is a whole tree at the branch ref with no
  network; the fixture builds its own bare remote under a temp dir, so
  no network is needed — measured in `support.py`.
- assumption: at this ref the hook refuses on any ref movement, so the
  allow cases are red — measured 2026-09-10 in session: a push of a
  records branch refused for movement on `origin/dev`.
- assumption: the worker cannot push — refusal: commit locally, the
  conductor lands.
