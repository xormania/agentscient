# Handoff — 2026-09-13, after the test-system census

Record by Claude Fable 5.1 on `lane/session-20260912-m`, cut from dev
`edb398a4`. See the [AAR](../AAR-2026-09-13-test-census.md). Written for
the session that plans the test framework; re-measure before acting.

## Where things stand

- dev `edb398a4` carries #159 to #168 and #171; master `2fed5317` is
  release #158, merged by the owner, and master was merged back into
  dev at `729f50a9`. Nothing on dev is unreleased except #171.
- Open PRs at write time: #169 and #170, dependabot bumps in the python
  fixture app, not this session's. No session PR open.
- Grants: 176 is the other session's (consolidating duplicated lane
  helpers on `lane/session-20260912-l`); 177 is this record's and
  settles against its merge. 171 to 175 settled against merge shas.
- The deliverable lock names `lane/session-20260912-l` (the other
  session) and `-m` (this record); `-m` leaves it by `set` naming `-l`
  alone when this lands, because the lever has no `remove` verb (LD-28).
- Worktrees this session created, all clean and pushed:
  `../wt/ag-session-20260912-h`, `-i`, `-j`, `-k`, `-m`.
- The census: dispatch record `20260913T023636Z-review-codex-bdbe55`
  (Codex, one attempt, exit 0, four lane MCP calls proven), artifact
  `ops/conductor/handoff/census/tests-20260913-cc91f00d.json`, seven
  findings open in the ledger on that record, each with a reproduce
  command; two re-run by the conductor with the same result.
- 11 findings stay open on `20260912T042714Z-review-codex-063615` (the
  conductor contract's references to a missing board lever).

## The thread this record hands over

Owner, 2026-09-12: "i'm more concerned with reuse of testing patterns -
a framework going forward that avoids one-off tests in favor of a
testing framework"; "we need consolidate the existing system in such a
way where we can avoid duplication - then we'll wire in a formal path
for adding tests and CI"; "go - hand grant given - dispatch the census";
and, asked whether to start a new session for what follows: yes.

Settled in session, in this order:

1. **Consolidate by extraction, not rewrite.** The generic halves sit in
   five places the census names: the launch support module, the hooks
   tests' support and gh stub, the live-store guard, the lane MCP
   fixture, the ladder lever test's embedded programs. Promote a world
   (HOME, XDG, temp, cwd, environment, planted tools, owned processes,
   snapshots of declared paths; hermetic by default, ambient by explicit
   opt-in), one command runner with one result shape, and one fake tool
   registry driven by data with an append-only call log. Domain free: no
   lane, ladder, finding or dispatch inside the kit.
2. **Migrate on evidence, never by deletion.** The 49 modules setting
   HOME directly move onto the world; the 76 fakes onto the registry. An
   old test stays until its replacement rows catch the same planted
   faults side by side. Pilot on the ladder family (17 test files, 254 KB
   around 90 KB of driver, eight of them this week's regression files);
   the refusal invariant is the first table, because the wire contract
   defines it exactly.
3. **Then the formal path, enforced:** a short test contract under
   `docs/`; a hook row that a new file under any `tests/` directory
   imports the kit or declares its exemption, and that ratchets the
   census counts so they cannot rise on a PR; the tests job's prompt and
   the what-exists brief naming the kit's invariants; `reused:` naming
   the invariant joined; check-tests running case rows against planted
   faults. CI changes take the same path: the workflow is wall and a
   change carries a corpus row.
4. **No dependency yet.** No pytest, Hypothesis or mutation tool until
   two families share the primitives and leverage is measured. The
   Symfony half (Infection, Foundry) is the prod lane's.

Acceptance is numbers, before and after: HOME by hand to zero, embedded
fakes to zero, conductor suite time not up (131.5 s at be7c0e06), tests
protected not down, each of this week's ledger rows represented as a
case in a table rather than a file.

How it runs: the kit is test machinery, so it is wall; built under wall
grants in sessions that write nothing else, its own tests by a producer
other than its author. Start with the plan job at xhigh effort on a
snapshot carrying the census artifact, the three supplied documents in
the ideas folder (the CI review, the research, the survey; author Astra,
not authoritative) and the seven findings. The work-order form to copy
is `.dev/ladder-inputs/brief-test-census-20260912.md` with its scope
file beside it: a scope under 1024 bytes, the contract as numbered items,
baselines with their commands and sha.

## The census, measured at cc91f00d

- 204 files: 189 tests, 15 support modules; world `hand` 79, `helper`
  60, `none` 65.
- 21 helpers already used by two or more families; 76 fake programs, 14
  of them gh, 53 with no call log, 7 rewriting one.
- 69 families; the highest byte ratios: the hooks installer 14.05, the
  lane MCP 9.25, the instrument conventions 8.29, the live-store guard
  7.76, the CI workflow 7.49, jobs.json 7.43, the boundary engine 6.7.
- Findings: 49 modules assign HOME directly; 10 files hold 14 gh fakes;
  171 `subprocess.run` calls in 58 files carry no timeout; the breaker
  stall test leaves its child unreaped on the failure path; 31 assertions
  pin cardinalities the contracts do not own; 14 modules named for one
  ledger row or PR rebuild a world or a fake; 21 support functions are
  cross-family infrastructure.

## Corrections to retain

- **An ask only where it is critical** (#168). `force-push` and `prune`
  ask; `trunk-commit`, `claim-unmeasured` and `pr-proof` deny. A
  published sentence carries its reading or the row refuses it.
- **Count rows go stale the day the count moves.** Three did today
  (`P-WMC-20260912-grok`, `P-ASK-20260912-rows`, `P-ASK-20260912-forge`).
  Serve a presence or a sentence; pin a count only when the count is
  the ruling.
- **A wall file's test needs a second grant** (LD-27): the wall row
  names no test path. Until repaired, write the red test under an
  ordinary grant and the wall file under a wall grant on the same
  branch, and say so in the commit.
- **The lock has no remove verb** (LD-28): with two sessions in it, a
  landed branch leaves by `set` naming the other session's branch with
  its own words.
- **A compound command is judged before it runs.** `deliverable.py add
  X && git worktree add -b X` is refused because the lock is read at
  PreToolUse; add first, cut second.
- **Measure in a pinned tree.** A reading is "N at <sha>"; a later one
  is a second measurement, not a correction. Cut `git worktree add
  ../wt/ref-<sha> <sha>` when the main checkout would move under you.
- **Edit scripts are not idempotent.** One ran twice and inserted its
  tests twice; guard the anchor or split the steps.

## Retrieval

```sh
git show dev:ops/conductor/handoff/HANDOFF-2026-09-13-test-census.md
git show dev:ops/conductor/handoff/census/tests-20260913-cc91f00d.json | python3 -m json.tool | head -40
python3 ops/conductor/tools/findings.py summary 2>/dev/null | head
```

Left behind on purpose: the session transcript and the scratchpad (edit
scripts, PR bodies, reply texts).
