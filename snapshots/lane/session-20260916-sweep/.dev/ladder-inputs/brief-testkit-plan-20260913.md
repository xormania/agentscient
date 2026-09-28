# Work order — the test kit plan

Owner, 2026-09-12: "i'm more concerned with reuse of testing patterns - a
framework going forward that avoids one-off tests in favor of a testing
framework"; "we need consolidate the existing system in such a way where we
can avoid duplication - then we'll wire in a formal path for adding tests and
CI". Owner, 2026-09-13: "The first step there is the plan job at xhigh effort
with the census and the three documents as its inputs."

This is a plan job. It changes nothing. Its deliverable is `out/PLAN.md`:
the sliced order of work that consolidates the test system by extraction,
migrates the ladder family on evidence, then enforces the formal path. The
settled order is in `ops/conductor/handoff/HANDOFF-2026-09-13-test-census.md`
§The thread this record hands over; the plan states *how*, and does not
move that order's boundaries.

## Contract

1. **Three primitives, domain free, by extraction.** A world (HOME, XDG
   roots, temp root, cwd, environment, planted tools, owned processes,
   before/after snapshots of declared paths; hermetic by default, ambient
   by explicit opt-in), one command runner with one result shape and one
   timeout policy, and one fake tool registry driven by data with an
   append-only call log. Promoted from the five places the census names
   (`ops/devlane/dispatch/tests/launch_support.py`,
   `ops/devlane/hooks/tests/support.py` and `gh_stub.py`,
   `ops/conductor/tests/live_store_guard.py`, the `_LaneMcpFixture` in
   `ops/conductor/tests/test_lane_mcp.py`, the embedded programs in
   `ops/conductor/tests/test_ladder_lever.py`), not rewritten. No lane,
   ladder, finding, dispatch or telemetry concept inside the kit; the plan
   names the test that proves it (an import or name scan the kit's own
   suite runs).
2. **Where it lives and how every suite reaches it.** The plan names the
   kit's path and how each of the nine suite directories `ops/bin/suites.sh`
   runs imports it under `python3 -m unittest discover -s <dir>`, stdlib
   only, without a per-suite path trick. For each of the 21 helpers in the
   census `helpers` list it says which primitive absorbs it, by name, or
   why it stays where it is.
3. **The ladder family first, on evidence.** 17 files, 254,957 bytes at
   cc91f00d and at 8b863cf4 (`git ls-files 'ops/conductor/tests/test_ladder*.py'
   | xargs cat | wc -c`). The refusal invariant is the first case table; its
   rows are defined by `docs/wire.md` and
   `ops/conductor/instrument-conventions.md` (exit 2, one non-empty stderr
   line, class token, expected–found–needed, empty stdout). No file is
   deleted in any slice until its replacement rows catch the same planted
   faults side by side; the plan names the planted faults per file, the
   command that runs old and new against them, and where the result is
   recorded.
4. **The regression files become rows.** The ladder files whose docstring
   names a ledger row or PR (`LD-15` ×2, `LD-17`, `LD-19` ×3, `LD-23`/PR 133
   in the census `origin` field) each become a case in a table with the row
   id as its `origin`, not a file; the same for the 14 modules in finding 6
   as they are reached.
5. **Then the enforced path, as its own slices.** A short test contract
   under `docs/`; a hook row in `ops/devlane/hooks/claude/` that a new file
   under any `tests/` directory imports the kit or declares its exemption,
   and that ratchets the census counts (HOME by hand, embedded fakes,
   `subprocess.run` without timeout) so they cannot rise on a PR; the
   tests job's prompt and the what-exists brief in
   `ops/devlane/task/jobs.json` naming the kit's invariants and `reused:`
   naming the invariant joined; check-tests running case rows against
   planted faults. A CI workflow change carries a corpus row.
6. **No dependency.** No pytest, Hypothesis, mutmut or any package until two
   families share the primitives and the leverage is measured; the plan
   names that measurement and the slice where it is taken. The Symfony
   half (Infection, Foundry) is the prod lane's and is not planned here.
7. **Every slice carries its grant class and its producers.** The kit, its
   hook row, the jobs prompt and the CI workflow are wall: written under a
   grant of class `wall` in a session whose deliverable is the wall and
   which writes nothing else. A wall file's test needs its own grant (LD-27:
   red test under an ordinary grant, wall file under a wall grant, same
   branch, said in the commit). The kit's tests are written by a producer
   other than the kit's author. Each slice says `wall` or `other`.
8. **Acceptance is numbers, before and after, each with its command.**
   Before, at 8b863cf4: 204 files, 189 tests and 15 support
   (`git ls-files 'ops/**/tests/*.py' '.claude/skills/*/tests/*.py' | wc -l`);
   49 test modules and 52 modules set HOME by hand (finding 1's command);
   76 fake programs, 53 with no call log, 7 rewriting one (census `fakes`);
   14 gh fakes in 10 files (finding 2's command); 171 `subprocess.run` calls
   in 58 files with no timeout (finding 3's command); 31 cardinality pins
   (finding 5's command); 14 regression-per-file modules (finding 6's
   command). After: HOME by hand to zero in every migrated family, embedded
   fakes to zero in every migrated family, conductor suite time not up from
   the reading in `ops/bin/suites.sh`'s log at this ref, tests protected not
   down, each of the rows in item 4 a case in a table. The plan repeats
   these with the command that will re-measure each.
9. **The seven findings each land in a slice or are deferred with a
   reason**, including the unreaped child on the breaker stall test's
   failure path (finding 4, `ops/devlane/telemetry/tests/test_breaker.py`
   143–155).
10. **The three documents are research, not authority** (owner, 2026-09-11:
    "the doc is not authoritative - it was Astra the created - that being
    said, Astra is smart, so don't dismiss it out of hand"). A claim from
    them enters the plan only re-measured at the ref by a command; a claim
    that cannot be re-measured is quoted as theirs.
11. **Read only.** No file outside `out/` is written. The machine lines,
    calibration rows and walkthrough follow the job template; the class of
    every slice is `lane` unless the slice is contract-only.

## Inputs (read whole, in this order)

- `in/brief-testkit-plan-20260913.md` — this work order.
- `in/tests-20260913-cc91f00d.json` — the census, measured at cc91f00d by
  record `20260913T023636Z-review-codex-bdbe55` (Codex, exit 0): `files`,
  `helpers`, `fakes`, `families`.
- `in/census-findings-20260913-cc91f00d.json` — the seven findings from that
  record's envelope, each with its reproduce command.
- `in/I-022-ci-review-handoff-2026-09-11.md` — the CI review.
- `in/I-022-test-framework-research-2026-09-11.md` — the research and the
  testkit proposal.
- `in/I-023-test-framework-reference-survey-2026-09-11.md` — the reference
  survey, vocabulary and phases.

In the snapshot: the handoff named above, `ops/conductor/handoff/lane-defects.md`
(LD-15 to LD-28), `ops/process/pipeline.md`, `ops/process/tdd.md`,
`docs/wire.md`, `docs/probes.md`, `docs/concerns.md`, `AGENTS.md`.

## Reuse

Read the lane MCP's `lane_brief`, `lane_changes` and `lane_findings` before
working, and say in the envelope's `note` what you reused (`reused: <what>`
or `reused: nothing applied`).
