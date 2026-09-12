---
name: refused
description: What each hook and guard refusal means and the accepted spelling - hand-write, graft-first, clipped-sweep, deliverable, pr-proof, direct-launch, dispatch-by-hand, override, scope-cap, stale-base, test-form, prune, and the CI walls. Use the moment a refusal appears; do the needed half, never rephrase around a row.
---

# refused — the needed half, not a workaround

Why it exists, measured: twelve of the twenty-one pitfalls recorded on
2026-09-11 are command shapes the guards reject; the consolidation
session of 2026-09-10 lost time to three refusal classes; the close-out
session of 2026-09-11 met ten refusals; 115 of 137 hand grants are
filed under "other", the class with no lever. None of these was a lane
defect. Each refusal states its remedy; this page is that remedy per
class, so the second refusal of a class never happens.

## Hook rows (`ops/devlane/hooks/claude/matrix.py`)

| class | it means | do this |
|---|---|---|
| `hand-write` | a write to a code root outside the ladder | declare a grant: `python3 ops/conductor/tools/hand.py declare --scope '<paths>' --ttl <min> '<action>' '<why>' other`; then the write goes through Bash with `HAND_GRANT=<id>` as the very first token of the command (pitfall 15). The Write and Edit tools cannot carry a grant. Scope paths are relative to the repository root and match worktree paths (pitfall 16). |
| `graft-first` | a grep, rg or git grep over a code root | a count (`grep -c`) or a file list (`grep -l`) is allowed; to read code, `sed -n`, `python3`, or `graft.py query`; `graft-stale` means the context needs `graft.py refresh --context FILE` by the conductor. |
| `clipped-sweep` | a multi-alternation grep piped to head | one pattern per grep, `-c` first for the verdict, then a bounded view; or `ops/devlane/hooks/claude/evgrep.sh PATTERN FILE` (pitfall 8). |
| `pr-proof` | `gh pr ready` or `gh pr merge` without proof the system verifies | put the change's corpus rows under `ops/conductor/handoff/probes/` on the branch, name their ids under a `## Proof` heading in the PR body, push, and wait for the ci run on that head; the hook reads the PR, the corpus at the head and the run list itself. No grant lifts this row (owner, 2026-09-12: "it has to be impossible to not do the work"). |
| `deliverable` | new work aimed at a branch the lock does not name | finish the deliverable, or `python3 ops/conductor/tools/deliverable.py set <branches> --why '<text>'` if the owner has named new work. A finding on the way is a ledger row. No grant lifts this row. |
| `direct-launch` | `launch.py` run without the dispatcher | `ops/bin/dispatch.sh`; `launch.py --help` reads with `HAND_GRANT=<id>` leading (pitfall 7); the `wait` and `status` verbs refuse from a session (LD-1). |
| `dispatch-by-hand` | a driver job (`author-tests`, `implement`) sent straight to `dispatch.sh` | the ladder runs driver jobs. By the owner's word only: an unscoped open grant, run from the branch's own worktree, no `--model` or `--effort`, every path spelled out (pitfall 18). |
| `override` | `--model` or `--effort` on a dispatcher call | remove it; models come from `MODEL_*` in `ops/lane.conf` (pitfall 4). |
| `scope-cap` | a scope file over the cap | `wc -c` the scope, trim it; detail goes in a brief passed as `--input` (pitfall 2). |
| `input-absent` | a `--scope-file` or `--input` missing or empty | spell the path from the worktree and check it exists before the call. |
| `stale-base` | the worktree is behind dev | `git merge origin/dev` in the worktree, resolve, push, then dispatch. |
| `test-form` | unittest given a path | `python3 -m unittest discover -s <dir> -p '<file>'`. |
| `prune` | `rm -r` of records, state, worktrees or `.git` | never. Branches are never deleted; worktrees are listed in the handoff. |
| `bucket-command`, `walkthrough`, `contract-vet`, `dispatch-env` | the scope names the whole suite; a write job carries no walkthrough; harness contracts do not vet; a launch without the launcher pin | read the row's needed half in the refusal; each names the exact file or token to change. |

## Command-shape and delegation hooks (`unsafe-command.py`, `no-subagents.py`)

| class | do this |
|---|---|
| `clipped-runner` | a test or build runner piped to a short tail: run it whole into a file, then read the failure count first. |
| `unguarded-replace` | a `.replace` whose result is written with nothing asserting the anchor matched: count the anchor first and refuse on zero, as the close-out scripts of 2026-09-11 do. |
| `shell-expanded-prose`, `stale-check-rollup`, `partial-feedback-poll` | the refusal names the shape; read its needed half. |
| `amend-published`, `amend-sweep` | never amend a pushed commit; a new commit, and `git diff --cached --name-only` before any amend. |
| `no-subagents` | in-session sub-agents are off; a stage goes through `ops/bin/dispatch.sh` or `go.sh`. |

Every refusal above, and every matrix row, logs one miss against this
page (or against `deliverable` for its row) in the skills registry, so
`skills.py report` measures which pages are followed.

## Launcher and lever refusals

| refusal | do this |
|---|---|
| `--stage fix-tests` unknown | stages are plan, tests, check-tests, code, review, adjudicate; the fix halves use `tests` and `code` (pitfall 1). |
| `findings.py disposition ... observation` | the vocabulary is open, fixed, addressed, deferred, ruled, fix-round, opinion; an observation is `deferred` with the reason (pitfall 5). |
| `correction: ... no --answers key named` | the write job follows a review; dispose each finding it answers with a contract citation, then pass `--answers <record>#<n>` per key. |
| `identity` | `export WF_AGENT='Name <address>'` before a writing verb. |
| the harness classifier blocks a push or a declare text | never rewrite a pushed branch; cut a new branch and leave the old one (pitfall 10). |

## CI walls

| check | do this |
|---|---|
| term wall | names the tree does not carry, machine users in paths outside a home path: scrub the evidence file; the pattern is configuration, never tree content. |
| `laneconf.py literals` | the lane name is spelled from `LANE_NAME` in `ops/lane.conf`, never as a string in code (pitfall 17). |
| ruff | `ruff check <file>` before pushing any hand-landed worker file (pitfall 21). |
| commit trailers | `Source:` and `Co-Authored-By:` on every commit; the orphan `deprecated-work` tree cannot run the check (pitfall 9). |

## The rule

A refusal is the wire. Do its needed half. A refusal that is wrong is a
lane defect: a row in `ops/conductor/handoff/lane-defects.md`, never a
rephrasing that gets past the row. The same class refusing twice in one
session is a miss on this page: `skills.py log-miss refused "<class>"`.

Record the use: `python3 ops/conductor/tools/skills.py log-use refused "<class>"`
with `WF_AGENT` set.
