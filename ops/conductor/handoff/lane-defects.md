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
| LD-1 | 2026-09-10 | matrix guard vs `ops/README.md` | README says `launch.py wait ID` waits for closure; the guard refuses it as `direct-launch`. Documented verb, unusable by a session. | open | — |
| LD-2 | 2026-09-10 | `ladder.py`, ladder 679214 stage check-tests | the driver handed stages scope and plan only; a scope sentence citing the work order sent the skeptic after `in/` files never supplied; it refused. | PR 87, 05e5bc3, grant 51 | dispatched to Grok on `repair/ladder-inputs-tests-20260910` |
| LD-3 | 2026-09-10 | `ladder.py` resume | scope and plan are digest-pinned; correcting a scope sentence mid-ladder needs a hand edit of the record (grant 49). A corrected scope should be a recorded event. | open | — |
| LD-4 | 2026-09-04 → | conductor tests | five test files snapshot the shared live dispatch store; any concurrent launcher fails their teardown; every parallel session since PR 62 reran CI. | open; partial for onboard tests in 955e0a9 | — |

Not a lane defect: the setsid pid recorded for the resumed driver was the
intermediate shell, the session's own error.
