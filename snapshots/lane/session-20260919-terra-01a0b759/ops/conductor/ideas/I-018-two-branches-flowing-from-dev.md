# Two branches flowing from dev

Owner, 2026-09-04, in session, after a day in which three pull
requests in a row met the trunk's up-to-date rule or a conflict at
merge time (#37 behind dev by nine commits; #38 conflicting on the
conventions registry table so the forge ran no workflow on it; #39
behind again after #38, then refused by its own new checks once dev
was merged in): "Idea for recording - i think we should have two
branches that flow from dev -> `dev-lane` and `prod-lane` - that's how
we sort out CI and keep conflicts to a min - thoughts?"

Reading: two long-lived integration branches under the trunk, one for
the dev machinery (`ops/`, `.claude/`, the Python lane) and one for the
product (`src/`, `packages/`, PHP and Symfony), each with its own CI
shape, work branches targeting one of them, and each merging into
`dev` on a cadence. The two named goals: CI that runs what the change
touches, and fewer conflicts.

What the day measured, for the record. Every conflict was lane
against lane, not lane against product: two lane branches landed in
parallel and both added a row to the same registry table in
`test_instrument_conventions.py` (three times), and the lane conf's new
checks refused the other lane's literal and its colliding variable
name (fix scope item 33). A `dev-lane` branch would have carried the
same collisions to the same table. The up-to-date rule on `dev` is
what forced a merge of dev before each merge; it is also what
guarantees CI ran on the exact tree that lands.

The conductor's reading of the trade. Long-lived integration branches
move integration later: two branches that diverge for a week meet at
the `dev` merge with a week of conflicts, found by whoever merges them
rather than by the author of each change at PR time. They add two
integration steps a session must perform, and two more places where
"is it green" is measured on a tree that is not the one released. The
two goals have cheaper answers that keep one trunk: CI as two always-on
jobs, a lane job and an app job, each running its own suites on every
pull request (both under two minutes today; a `paths:` filter is
refused by the lane's policy because a check that reports only
sometimes cannot be counted); the registry table as one row-file per
instrument, so two lanes adding instruments never touch the same line;
a merge queue on `dev` if the organisation's plan allows it, which
builds the merged tree and runs CI before the merge and serialises
pull requests without a session merging dev by hand; and the lane conf
naming the trunk, so if the owner rules for `dev-lane` and `prod-lane`
after all, every reader follows one line and no code changes.

Where it may become right: when the lane leaves for its own
repository, which the conf now makes a copy-and-edit act; a `dev-lane`
branch is a half-step to that, and the full step is cleaner. And when
product CI (composer install, kernel boot, phpunit across packages)
costs minutes, the two-job split keeps lane pull requests from paying
it while every check still reports on every pull request.

Not ruled; recorded with the day's measurements beside it, for the
owner's decision. The reading is the conductor's.
