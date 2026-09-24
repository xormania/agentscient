# PR02: bounded CI execution and verified reuse

Owner direction, 2026-09-24: "now PR02 - get CI un-fucked and optimized".
Current direction keeps self-hosted execution. This supersedes the planning
document's earlier hosted-default proposal. Base: `828e7b63440fb05ed24d2d487880dfd7b72ff756`.
Work is performed directly in chat, with no dispatcher, live grant/session
workflow, or second producer. Independent second reviewer absent.

## Measured problem

PR01's final [run 35948478889](https://github.com/uscient/agentscient/actions/runs/35948478889)
passed both required jobs. Its lane job ran on `agentscient-wsl-10` for 8m32s.
One conductor shard ran 832 tests in 484.376s; dispatch finished in 167.297s.
The preceding sessions work in #285 grew the alphabetical remainder: before
that work, [run 35928421194](https://github.com/uscient/agentscient/actions/runs/35928421194)
ran that shard's 697 tests in 113.984s and finished lane in 2m56s.

The scheduler started expensive suites alongside cheap guards and waited for
them even after a guard failed. Every event repeated both jobs. That combination
made documentation/fixture failures expensive and post-merge work redundant.

## Changes

- Keep `lane` and `app` on `self-hosted`; preserve PR/push/merge-group coverage.
- Use the existing testkit's strict discovery and execution primitives. Run
  conductor modules independently in a bounded pool, with larger modules
  queued first. Every newly discovered module remains required.
- Preflight the entire plan, then run cheap guards before expensive suites.
  A guard failure leaves the full result red and prevents expensive starts.
- Use a private World home, XDG roots and temporary directory. Declare and
  fingerprint required tools. Drop operator configuration, session variables
  and API credentials from children; retain the existing watch/cleanup checks.
- Keep only dependency downloads in the explicit shared Composer cache.
  Reinstall dependencies when a fresh app check needs them; a prior install
  receipt does not stand in for files in a new workspace.
- Materialize the tracked decision-register export in the private job store
  using the existing domain schema and storage primitive, and initialize the
  private skills register with its existing sync command. Four historical PR
  probes read their recorded merge commits, including the original titles,
  rather than depending on an operator's authenticated gh session. Their
  questions remain and the full corpus still runs.
- Publish original executed results as bounded, immutable GitHub artifacts.
  Validate artifact integrity, repository/workflow/job/attempt, source Git
  objects, input digest and complete check plan before reusing any success.
  Preserve valid successful checks from a failed companion or earlier attempt.
  Never derive an original pass from a reused marker.
- Canonicalize verification commit metadata while retaining the exact tree
  and ordered parents. A temporary PR merge and its published merge can use
  the same tested Git object. Bind record refs, tool identities, checks and
  relevant configuration. Live probes always read the actual event checkout.
- Conservative lane inputs include the full tracked tree. Application inputs
  omit independent dev-lane code but include CI/kit definitions. A dirty source
  checkout refuses before reuse; changed or unknown inputs require execution.
- Evidence lookup has a ten-second overall budget. Missing/expired evidence
  or unavailable GitHub APIs cause real checks, never a guessed pass.

## Direct validation

The existing workflow and testkit families cover the new behavior. Added
cases first reproduced missing automatic partitioning and expensive starts
after a failed cheap guard. Both passed with the same commands after repair.
The reuse table rejects wrong workflow/source/tree/history, fork provenance,
cancelled/incomplete jobs, expired or partial evidence, malformed outcomes,
duplicate rows and reused-only markers. A real fixture execution is skipped
on a valid second presentation and executes again after its tree changes.

The canonical-commit case proves that publication message changes preserve
the tested object while changed parents invalidate it. A real child captures
its private HOME/XDG/temp values and proves that GITHUB_TOKEN and WF_AGENT are
absent; its private home is removed on completion. An app case proves that a
fresh dependent check still causes dependency installation after partial reuse.

Repository-wide Ruff and the testkit ratchet pass in this chat. Final commands,
counts and native run links are maintained in the PR body after the candidate
is published; local results do not replace required native CI.

The chat environment lacks tmux and CUE. An exploratory module profile there
therefore skipped native cases and had dependency failures; its 26-second time
is not a full pass or a speedup claim. The acceptance timing must come from
the existing WSL runners. Target: return toward the previous roughly three-minute
full gate, then demonstrate that presenting the same passing inputs reuses
original evidence. Hosted execution and any hosted-minute saving are unclaimed.

## Boundaries and rollback

No existing behavioral cases, required families or guard checks are removed.
The JSON artifact is CI execution evidence, not a second work/assignment store.
No operator worktrees, active sessions or runtime databases are used or changed.
Private state roots do not claim an OS sandbox for hostile contributor code.

A rollback can restore unconditional execution through the same full lane
plan while retaining private state roots and bounded module scheduling.
Invalidating or losing receipts costs fresh verification; it cannot authorize
completion. The original native run/job links remain the source of a reused pass.
