## Slice 1 phase timings, from the records

Measured 2026-09-23 at about 01:05Z. Sources: the dispatch records' `at.launched` and `at.closed`, and the commit times on origin (`git log --date=format-local` under TZ=UTC). Nothing here comes from memory. Eastern time is UTC-4.

| # | phase | record or commit | assignment | start (UTC) | close (UTC) | minutes | outcome |
|---|---|---|---|---|---|---|---|
| 1 | contract | 3daebdbd | — | 21:14:55 | — | — | sessions-lever.md and the author-tests scope |
| 2 | author-tests, first launch | 20260922T212631Z-code-grok-123236 | none | 21:26:31 | 21:27:46 | 1.2 | tripped: launched without --for, so the worker was unbound (LD-116) |
| 3 | author-tests | 20260922T213030Z-code-grok-1693c9 | A-477 | 21:30:30 | 21:53:21 | 22.9 | rows d078b68b and ea39ec55; envelope invalid (LD-122) |
| 4 | check-tests | 20260922T215604Z-review-codex-f6777b | A-478 | 21:56:04 | 22:12:09 | 16.1 | 26 findings, 3 p1; tripped by the forward merge da40a17d under the running job (LD-119) |
| 5 | revise tests, one job | 20260922T221641Z-code-grok-06f90e | A-483 | 22:16:41 | 22:46:46 | 30.1 | killed at the 1800 s cap; only d2a24d8c kept |
| 6 | revise tests, split part 1 | 20260922T224945Z-code-grok-a8b48e | A-489 | 22:49:45 | 23:14:17 | 24.5 | envelope invalid |
| 7 | revise tests, split part 2 | 20260922T231526Z-code-grok-312c63 | A-490 | 23:15:26 | 23:44:31 | 29.1 | head bba45f5c; close to the cap |
| 8 | re-check | 20260922T234512Z-review-codex-5b18d7 | A-484 | 23:45:12 | 23:55:51 | 10.7 | 1 p1, 4 p2 |
| 9 | implement, by hand | builder session 0a450951, commits 51f180d7 to 8aa28089 | A-491 | 23:13:21 | 00:15:54 | 62.6 | first code 23:31:48; supervisor 4c81e9d5 00:09:07 |
| 10 | contract rulings mid-build | b549b565, c1a69a78 | — | 00:02:40 | 00:10:48 | 8.1 | first bind is a worker; a cold store gets the schema |
| 11 | test fixes, dispatched | 20260922T235722Z-code-grok-710abd | A-493 | 23:57:22 | 00:25:00 | 27.6 | 5 of 5 fixed |
| 12 | tmux fake fix, dispatched | 20260923T000019Z-code-grok-075a27 | A-494 | 00:00:19 | 00:15:46 | 15.4 | new test_session_tmux.py |
| 13 | implementation lands on 69 | 3a1ef179 | — | 00:26:06 | — | — | 28 of 37 rows green |
| 14 | draft PR #271 | — | — | 00:32:03 | — | — | the claim-unmeasured row refused the body twice first |
| 15 | review, grok | 20260923T003019Z-review-grok-112f90 | A-480 | 00:30:19 | 00:57:05 | 26.8 | 3 p1, all already fixed by A-495; envelope invalid (LD-122) |
| 16 | review, codex | 20260923T003033Z-review-codex-c99cc9 | A-481 | 00:30:33 | 00:51:53 | 21.3 | 3 p1, 6 p2, 1 p3 |
| 17 | fixture fixes, by hand | 5c session 4f7515ad, commits 76799055 to 1424c375 | A-495 | 00:15:04 | 00:50:17 | 35.2 | 9 failures to 0; a planted lead-promotion row |
| 18 | fix round | cd1f9fbe (builder); d1ee3702, ba592a01, b8cba8f4 (5c) | A-491, A-495 | 00:51:53 | 01:00:39 | 8.8 | 69 at bab120dd: 39 OK, ruff clean |
| 19 | audit | A-492 | A-492 | pending | | | |
| 20 | flip and merge | | | pending | | | |

Contract to landing on 69 at 00:26:06: 191 minutes. Contract to the fix round's head at 01:00:39: 226 minutes.

### Minutes lost, by cause

| cause | measured | minutes |
|---|---|---|
| Implementation waited on tests (serial) | contract at 21:14:55; builder started at 23:13:21 | 118 |
| 1800 s cap on author-tests (A-483) | 06f90e ran 30.1 minutes and kept one commit; the redo was split into two serial jobs of 24.5 and 29.1 | about 30 lost; the revise phase took 88 (22:16:41 to 23:44:31) |
| Launch without --for (LD-116; LD-120 is the same class) | 123236 tripped at 1.2 minutes, relaunched at 21:30:30; #270's 74a84b died at 1.9 minutes, relaunched at 00:08:04 | 4.0 + 2.6 |
| Forward merge under a live job (LD-119) | f6777b tripped at 16.1 minutes; its findings were read from the record, so there was no rerun | 0 on the critical path; the store could not take its submission |
| amend-published guard (LD-117) | worked around with reset --soft and 71241d93 on #269 | not measured; off the slice 1 path |
| Proof body refused by claim-unmeasured | two retries before #271 opened | about 2 (not separately stamped) |
| Contract clauses ruled mid-build | b549b565 and c1a69a78, while the builder waited on each | 8.1 |

The largest avoidable cost: implementation waited 118 minutes for the test pipeline. Tests and code built from the same contract, by different producers and integrated at the end, remove it.
