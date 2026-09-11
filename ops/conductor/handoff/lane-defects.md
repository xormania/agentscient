# Lane defects — observed live, repaired directly

Owner, 2026-09-10: "these issues keep popping up - and we need to get them
fixed - and it may need to be a direct fix - immediately - the process to
be reliable." A lane defect is a stop or refusal not caused by the change
under test. Each gets a direct repair on a `repair/` branch under a
declared hand grant, a by-hand red-then-green in the commit, a draft PR,
and a regression test dispatched afterwards to a harness other than the
fixer's. Product code and contract guarantees are not repaired this way.
Reliability is the count below trending to zero per ladder.

| id | observed | where | defect | repair | tests |
|---|---|---|---|---|---|
| LD-1 | 2026-09-10 | matrix guard vs `ops/README.md` | README says the launcher's `wait ID` verb waits for closure; the guard refuses it as `direct-launch`. Documented verb, unusable by a session. | blocked: the session's edit to the guard was denied as self-modification (grant 59, no change); three-line fix handed to the owner, worktree `ag-matrix-read-verbs-20260910` | — |
| LD-2 | 2026-09-10 | `ladder.py`, ladder 679214 stage check-tests | the driver handed stages scope and plan only; a scope sentence citing the work order sent the skeptic after `in/` files never supplied; it refused. | PR 87, 05e5bc3, grant 51 | PR 90: 13 Grok tests; 3 found LD-6, 2 corrected per ruling cd4bef |
| LD-3 | 2026-09-10 | `ladder.py` resume | scope and plan are digest-pinned; correcting a scope sentence mid-ladder needs a hand edit of the record (grant 49). A corrected scope should be a recorded event. | PR 89, d9a455f, grant 57: `resume --rescope` records the change | to follow |
| LD-4 | 2026-09-04 → | conductor tests | five test files snapshot the shared live dispatch store; any concurrent launcher fails their teardown; every parallel session since PR 62 reran CI. | PR 88, 83eb1c2, grant 55: one shared guard, exclusions declared | retained 24-case test_store_guard.py holds; helper test to follow |
| LD-5 | 2026-09-10 | `findings.py import` | imports only the three ladder review jobs; a `sweep` or `adjudicate` record's findings never reach the ledger, so a third-harness ruling (20260910T233710Z-review-codex-cd4bef) cannot be disposed in the store and its dispositions ride in commit messages instead. The gate work order's slice 2 reads the same store. | open | — |
| LD-6 | 2026-09-10 | `ladder.py` refusal texts | three `--input` refusal texts disagreed with the contract the regression tests were written from (ruling cd4bef #2 #3 #4, UPHELD) | this branch, bc18ce7, grant 61 | the three Grok tests on PR 90 |
| LD-7 | 2026-09-11 | `ladder.py` custody markers | every string of the implement envelope became a withheld marker, file paths and `p3` included; the audits named the changed files, so ladder 679214 stopped `withheld` at fix-tests with no real leak | this branch, grant 68: markers are the record id and distinctive envelope lines only, applied on load | to follow |
| LD-8 | 2026-09-10 | `test_monitor_malformed_git` | failed once on PR 89's CI (0 ls-remote calls for the healthy sibling), passed on rerun and locally; no other occurrence in the last ten dev runs | open, count it: 2 (PR 89 run 34542589843, PR 93 run 34545228312), both passed on rerun and locally | — |
| LD-9 | 2026-09-11 | `test_handwork_ledger` | snapshots the live handwork ledger bytes and fails when the conductor declares or settles a grant during the run (PR 90 run 34545099924); same class as LD-4 | open; the fixture (I-020) retires it | — |
| LD-10 | 2026-09-11 | freshness pre-check hook | compares every remote-tracking ref and refuses on any movement, so independent lineages in one session refuse each other's merges; three refusals on 2026-09-10, all for movement on dev while pushing unrelated branches | owner-authorized; this branch, grant 72: only the refs the command depends on | Grok, tests first, on this branch |
| LD-11 | 2026-09-11 | `ladder.py` stop | a resume rewrites stage inputs for stages it then finds already done; at the exit-1 stop after security-re the rewritten `implementation-records.md` stayed uncommitted and `land.py` refused `dirty` | this branch, grant 79: every commit of the record adds the record's inputs directory | to follow |
| LD-12 | 2026-09-11 | term wall vs the findings export | the export copies reviewer claims verbatim from the exempt dispatch captures into a tracked file the wall scans; one claim quoting a host path slug turned PR 96 red | this branch, grant 81: the export joins the captured-data exemption | to follow |

Not a lane defect: the setsid pid recorded for the resumed driver was the
intermediate shell, the session's own error.
