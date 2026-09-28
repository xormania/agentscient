# tdd-valid-red-20260909.patch — an owner-directed law correction that never reached dev

Found 2026-09-16 at the wind-down of session -e in the ended worktree
of docs/tdd-valid-red-20260910 (no commits beyond dev; two modified
files never committed, mtime 2026-09-09 22:04): AGENTS.md and
ops/process/tdd.md carrying "Manual prerequisite: valid RED before
implementation. Owner-directed correction, 2026-09-09." Measured on dev
at f23f1884: `grep -c 'valid RED before implementation'
ops/process/tdd.md` reads 0; the diff against that dev is 52 changed
lines in AGENTS.md and 167 in tdd.md, taken from a 2026-09-09 base, so
it does not apply to the current law as it stands.

Saved as a patch, not applied: a law change lands only when a session
re-reads it against the current AGENTS.md and tdd.md and the owner's
word covers it. Whoever takes it: `git apply --check` will refuse on
the moved base; read the intent from the hunks and rewrite it against
the law as it is now, then land it on its own PR.
