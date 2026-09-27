# Scope — one lane configuration file, everything named in one place

Formed in chat with the owner, 2026-09-04. The owner's words are
verbatim. Every fact was measured by the session on the day, on dev at
`77f7c1a`; the command is named. Nothing here says how. Queued behind
lane fix batch 1 (items 1 to 12); planned as the first unit of batch 2
so the remaining fixes read the conf from the start.

## What the owner said

> i was thinking that having a config file that names everything, would
> be better then spreading shit all over - after the C batch - we should
> do that, as much as possible

> is the dev machinery able to be copied into another project if needed
> and not be too configured for this one?

## What is spread today

Measured with `grep -l` and `grep -c` over the lane's code (`launch.py`,
`record.py`, `worth.py`, the conductor tools, `dispatch.sh`, `ops/bin`,
the PR overview, the Claude hooks, `jobs.json`):

| constant | written today |
|---|---|
| the lane's name, as the state directory `~/.local/state/agentscient/` | 14 files, 18 places (`launch.py` line 144 and nine conductor tools among them) |
| the trunk branch name `dev` | 3 files, 12 places |
| the repository slug `uscient/agentscient` | 3 files (`pr_overview.py` `--repo` default among them) |
| the required check name `ci` | the PR overview |
| the scope-file cap, 1024 bytes | 3 files |
| the default wall (900) and the per-job caps (1800) | `launch.py` and `jobs.json` |
| the worktree root `../wt` | 1 file |
| this machine's absolute launcher pin | `dispatch.conf` (batch 1 item 11 makes the default relative) |
| fallback binary paths from the House's machine, `/home/work/…` | the Grok and Codex levers, 2 places |
| models, efforts, the default agent identity | `dispatch.conf` — already in one place |

Not spread, and not in scope: the term wall pattern (a CI variable and a
gitignored conf, per project by design); the founding documents and
records that mention the project by name (content, not configuration).

## What the owner wants

- One tracked file names everything the lane is configured by: the
  lane's name, the trunk and release branch names, the repository slug
  (or the rule that derives it from the remote), the state root, the
  worktree root, the required check name, the default agent identity,
  the models and efforts per harness and per job, the default wall, the
  scope cap, the launcher pin's default. `dispatch.conf` is the seed and
  is absorbed, not duplicated.
- Every reader of such a value reads it from that file. Bash sources it;
  Python reads it with a stdlib reader. No reader carries its own copy.
- Precedence is the dispatcher's existing rule, unchanged: the
  environment beats the conf, the conf beats the built-in default. A
  reader that needs a key the conf lacks refuses on the wire, naming the
  key and the file.
- Per-machine values live beside it in a gitignored local file sourced
  after it, never in the tracked file.
- Per-job caps stay in the job catalogue (a table per job is not a
  scattered constant); the conf holds the default wall.
- The per-language parts of the lane (the lint, the test runner, the
  named command, the CI steps) are a toolchain profile in the conf, one
  per language, named by each fixture app it proves and chosen when the
  product installs into a target project (owner, 2026-09-04: the Rust
  target "shouldn't be the only one"; and: "Agenscient should be able
  to work with any language - python, go, rust, php, C, WASM - right?").
  Profiles are data, not code paths: Python first (the lane runs on
  it), PHP second (the product), Rust third (the targets), then Go, C
  and WASM each when a target needs it, each proved by its fixture app
  the day it arrives. The core (the wire, the records, the loop, the
  ledgers, the audits) names no language.
- Retention is a conf line, and the default keeps everything (owner,
  2026-09-04: "data, data, data - i can't say it enough - its training
  data-sets waiting to be derived"). A job directory under the state
  root (the rendered prompt, the input files, the worker's full output
  and transcript, the diff, the envelope) is never pruned; the meter
  reports the store's size; and an export bundles, per run, prompt,
  inputs, output, diff, envelope and the finding dispositions that
  followed into one dataset row, so every run is a row that can be
  derived later rather than reconstructed.
- It does not spread again: a check refuses a literal lane name, branch
  name or repository slug in lane code outside the conf and its reader,
  and a check holds the closure both ways — every key the code reads is
  declared, every declared key has a reader (the couplings contract's
  first obligation).
- Copying the lane into another project then means: copy `ops/`,
  `.claude/`, `CONTRIB.md` and the lane half of the workflow, write that
  project's AGENTS.md and CLAUDE.md, set its term-wall variable, and edit
  one file.

## Boundaries the owner set

- After batch 1 lands (owner: "after the C batch"); the files overlap.
- "as much as possible": where a value cannot move without changing a
  wire contract, the scope says so and the plan names the residue.
- The lane is bounded: no new instruments beyond the reader and the two
  checks; no new kernel responsibilities (AGENTS.md §The lane).
- The wire holds: every new refusal names expected, found, needed.

## Acceptance, measurable

- `grep` for the lane's name, `dev`, `master`, the slug and the check
  name over lane code finds them only in the conf, its reader, the two
  checks and their tests.
- `bash ops/conductor/tools/dispatch.sh --dry-run …` and `python3
  ops/devlane/dispatch/launch.py …` resolve models, efforts, wall and
  pin from the same file, shown in the record's `caps` and `model`.
- A conf missing a required key makes each reader refuse on the wire in
  one line naming the key and the file.
- A copy of the lane into a scratch repository with a one-file edit runs
  `bash ops/bin/suites.sh` green and a `--dry-run` dispatch there.
- Every lane suite green on the merged tree; `ruff check .` clean.
