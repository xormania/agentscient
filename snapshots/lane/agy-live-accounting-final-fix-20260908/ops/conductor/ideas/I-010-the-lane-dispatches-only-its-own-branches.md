# The lane dispatches only its own branches

The dispatcher runs the launcher that sits beside it, the worktree's
own copy, unless a pin names another (lane fix batch 1, item 11). The
launcher runs on the host as the operator, before any sandbox exists,
so a branch that carried a hostile launcher would run it the moment
someone dispatched from its worktree. The security audit of the batch
(Codex Daybreak, record `20260904T040646Z-review-codex-7fbe5c`, finding
1) named this P1.

The ruling: this repository is private; every branch here is the
owner's or a session's, and workers write only inside snapshots whose
commits reach a branch by cherry-pick onto one the lane controls. No
outside pull request exists to dispatch from, so the sibling launcher
is the default and the pin stays the operator's optional lock. The
safe way to audit a commit that is not the lane's own, should one ever
appear, is to dispatch from a trusted worktree with that commit as the
`--ref`, so the trunk's launcher runs and the foreign commit is only
the snapshot. This ruling is re-read the day the repository stops being
private or gains an outside contributor.

Owner, 2026-09-04, in session: "its a private repo"; and on the day
it is not: "if it public - i'll hit it with a shitload of security
audits and red teams - so let's find a balance that works for now".
The balance for now: the default stands; the pin is the lock an
operator sets when the trust changes; going public is preceded by
the owner's audits and red teams, and this ruling is re-read then.
