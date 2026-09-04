# ops — the Agentscient conductor lane

The operating apparatus for building Agentscient: the owner directs, a
conductor session coordinates, workers are dispatched harness CLIs on
the wire, and everything binds to the law in `AGENTS.md` and `docs/`.

This lane is carried over from the House dev lane, through the scrubbed
copy in the `minspec/workbench` repository (provenance only; MinSpec is
not used here), de-instanced, and lands here as the **bounded Python
incumbent**: every instrument under `ops/devlane/` is the functional
specification for a Symfony Console twin, and retires only when its
twin passes the same conformance row (the strangler, per the migration
doctrine). It is not rewritten for sport and it earns no new kernel
responsibilities; it is the thing the twins are measured against.

## Layout

| path | holds |
|---|---|
| `ops/devlane/dispatch/` | the launcher: mint a snapshot, launch a harness, supervise, collect, record; the levers under `levers/` |
| `ops/devlane/harness/` | the firewall: manifest-staged snapshots proved in both directions, isolation law, probes |
| `ops/devlane/task/` | the job registry (`jobs.json`), envelopes, filesets, the parity runner |
| `ops/devlane/telemetry/` | usage readers, the breaker, pulse, worth |
| `ops/devlane/hooks/` | git hooks (crossing recorder, trailer gate) and the Claude hooks wired by `.claude/settings.json` |
| `ops/devlane/workflow/checks/` | deterministic guards: trailers, secrets, CI shape, the vocabulary wall, the term wall |
| `ops/devlane/fixtures/` | synthetic harness envelopes and store builders — never raw captures |
| `ops/devlane/fixtures/apps/` | whole-project calibration fixtures with planted faults — apparatus, never product code |
| `ops/devlane/infra/` | the local CI muscle: Gitea, act_runner, the lane image (inert until composed up) |
| `ops/conductor/` | the conductor lane: the instruments (register, ledger, watch, land, onboard, CI store, census, skills, the doctor), their contracts and suites, the ideas and hand-off records, the AARs — `ops/conductor/README.md` |
| `ops/process/` | the pipeline law: who produces what, what each is denied, review, tdd, bdd, worth |
| `ops/docs/` | the shelf: the four lesson pages the process law cites, carried from the House; records, not law |
| `ops/design/features/` | the BDD feature shelf: Given/When/Then scenarios per area |
| `ops/capabilities/contracts/` | the seed's four CUE contracts — the anatomy of a capability, the refusal shape, the read/write tags — input to the module maker; the seed's vets, plans and tests did not cross |
| `ops/archive/` | House-era records about this framework, behind a standing banner: reference for the twins' authors, never authority |
| `ops/bin/` | the levers a session pulls by hand |

## The levers

| run | does |
|---|---|
| `ops/bin/suites.sh` | runs every lane suite exactly as CI does; the local answer and the CI answer are one command |
| `ops/bin/fixture.sh` | makes isolated fixture repositories, proves their planted faults red or fixed faults green, and grades review records |
| `ops/bin/dispatch.sh` | the shim for `ops/conductor/tools/dispatch.sh`: one job to one harness through the launcher in the same worktree; `--detach` returns the minted record id at once, and `launch.py wait ID` waits for closure |
| `ops/bin/ladder.sh` | runs the declared test, implementation, audit, fix, and draft-PR ladder in a branch's owning worktree; `resume ID` continues its named durable record |
| `ops/bin/go.sh` | the one-word front of `dispatch.sh`: `go.sh <intent> <branch|.> <scope…>`; `DETACH=1` passes the detached-launch mode through |
| `ops/bin/board.sh` | what is open, measured now: PRs and worktrees per repository |
| `ops/bin/link-ops.sh` | makes this lane reachable from sibling package clones as a locally-excluded symlink |

Delegation runs through `dispatch.sh` (or `go.sh`) and nothing else.
In-session sub-agents are refused by hook
(`ops/devlane/hooks/claude/no-subagents.py`): they burn context and
leave no record; a dispatched job leaves a snapshot, a run record, and
a commit.

## The wall, here

`ops/devlane/workflow/checks/term_wall.py` refuses names this
repository does not carry in its **tree**: content and paths. The
pattern is configuration, never tree content — the repository
variable `TERM_WALL` in CI, the gitignored `ops/bin/term-wall.conf`
locally — and an absent pattern is a refusal, never a pass.

Commit messages and pull-request text are **exempt** in this
repository, unlike the organisation this check came from: `AGENTS.md`
requires every adapted commit to cite its origin in a `Source:`
trailer, and origins are named by repository. Provenance lives in the
history; the framework's files stay clean of it. See
`ops/devlane/workflow/checks/CONTRACT-term-wall.md` §In this repository.

## Armed and available

Wired by `.claude/settings.json`: `context-precheck.sh` (fetch before
anything outward; refuse when refs moved), `context-boundary.sh`
(record and warn when the ground moves), `test-guard-hook.sh`
(advisory: a planted fault without its proof), `ruff-after-edit.sh`
(advisory lint at the edit), `no-subagents.py` (refuse in-session
delegation). Present, not armed: `conductor-enforce.py` (a stricter
posture that forbids hand investigation entirely) and `pr-feedback.sh`.
Arming either is a reviewable change to `.claude/settings.json`.

## Declared absences

Named so nobody infers them from silence:

- The state-machine runtime behind `ops/devlane/workflow/wf.py` — the
  narrow `--json status --checks` read projection is present for CI check
  discovery, but every writing verb remains absent. The House runtime
  stays on `lane/workflow` (PR #10,
  closed unmerged at the owner's word, 2026-09-03; I-008, D-PORT-2
  proposed). What crossed is its specification: `PLAN.md`, the twelve
  CUE contracts and their notes under `contracts/`. The runtime arrives
  only as the Symfony twin, behind the genus contract in
  `docs/workflow.md`.
- `ops/devlane/workflow/tests/` beyond `test_term_wall.py`, and the
  engine's fault corpora, observations, packets and verdicts — on
  `lane/workflow`, not crossing: they pin the Python CLI's shape, which
  the twin does not keep. The CUE contracts are the transferable oracle.
- `ops/contracts/imports.json` — the cross-app import declaration the
  dispatch and task contracts cite. On `lane/workflow`, not crossing;
  deptrac holds that boundary for the PHP modules.
- `ops/capabilities/` beyond `contracts/*.cue`, and `ops/guide/` — the
  seed's vets, plans and tests, and the House's per-app guide pages: on
  `lane/workflow`, not crossing.
- `ops/devlane/workflow/gate-kinds/*.json` still name House paths
  (`.dev/app/…`) in their `argv`; nothing on `dev` executes them. A
  finding, recorded here, not fixed in the extraction.

## The rules the lane binds

- One line of work, one worktree (`../wt/ag-<slug>`); the main
  checkout belongs to nobody; branches are never deleted.
- Workers commit with `Source:` and `Co-Authored-By:` trailers naming
  the model that actually ran; a dispatch never names a model on its
  own — the owner supplies one in `dispatch.conf`, and the run records
  it.
- Work arrives as draft PRs; the owner ratifies and merges. A
  dispatch's scope file is copied beside its record, so what was asked
  and what happened are one record.
- Runtime residue — job captures, snapshots, isolated homes — is
  gitignored; the lane's law is tracked, its residue never is.
