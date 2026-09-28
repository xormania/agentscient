# Ratification — U1 vocabulary (child plan cf38c7), by the conductor, 2026-08-29

Parent: `agentscient-framework-plan.md` row U1. Policy behind it is the owner's ("i'm worried about conflating docker service and (Symfony) service"); the seven below are design.

| decision | ruling | reason | premise |
|---|---|---|---|
| D-U1-two-passes | standing | one script, two passes that partition the tree — extends the wall instead of forking it, one allowlist to keep in agreement with AGENTS.md | `read`: test_guide.TheSurfaceListsAgree |
| D-U1-homes | standing | `service` stays legal where it names other systems' objects (infra, scratch research, handoffs) or cannot be edited (records); each home pinned by a test with a reason, so the carve-out cannot grow silently | `measured`: 50 hits, 6 in immutable records |
| D-U1-rename | standing | four English hits are idiom, and every allowlist entry shrinks the wall; rewording is cheaper than a permanent exemption | `measured`: 4 hits |
| D-U1-code-suffixes | standing | the word being guarded is a code/manifest word; a wall that never reads `.py`/`.json` cannot guard it | `measured`: the two in-app hits are in `.py` the wall never reads |
| D-U1-capability-both-ways | standing | the owner's term walled the same way as every other term: one row per term, a `_has_capability!` raw check | `read`: vocab.cue shape |
| D-U1-infra-readme | standing, with a note | a named carve-out path must exist for `test_guide` to accept it; the README is created here. Note for reviewers: `env/docker-lane` (PR #82) brings `.dev/infra/` with its own layout — reconcile at merge, whichever lands second | `measured`: `.dev/infra/` absent on this lineage |
| D-U1-parent-binding | standing | same bootstrapping as U0: prose digest until `plan extract` exists | `measured`: no `.plan.json` at this ref |

## Closure 2026-08-30 (conductor)
U1 is done at `05f5390`: three Codex fix cycles on two review rounds and two further executing reviews (`fce178`, `02d142`): 34 + 9 tests green, ruff clean, the wall quiet on both passes over 662 files; compound and hyphenated compose names caught; the two-pass partition of named surfaces (not the tree) stands by D-U1-two-passes. Reviewer note for the merge: `.dev/infra/README.md` created here will meet `env/docker-lane`'s `.dev/infra/` at the group PR.
