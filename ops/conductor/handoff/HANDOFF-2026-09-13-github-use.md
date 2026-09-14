# Handoff — 2026-09-13, GitHub use: the first slice of the pitfall review

Record by Claude Opus 5 (1M context) on `lane/session-20260913-n`, cut
from dev `cccc810b` (#201). The board, PRs and grants are re-measured by
`onboard.py`, not taken from here. The [AAR](../AAR-2026-09-13-github-use.md)
carries the readings.

## Next thread: options 1 and 2

Owner, 2026-09-13: "i'll do options 1 and 2 on next session - make sure
to have that in the handoff when we're done here".

Why: every hook in `.claude/settings.json` runs from the main checkout
through `$CLAUDE_PROJECT_DIR`, and nothing moves that checkout's dev when
a PR lands on GitHub. No session may move it: the engine's trunk-commit
row refuses a fast-forward there and no grant lifts it (LD-38). At
2026-09-14T00:47Z it was 44 commits behind origin/dev
(`git rev-list --count HEAD..origin/dev`), and the owner ran the
fast-forward by hand ("Updating 3014cb22..cccc810b", 61 files). At 01:42Z
it was 5 behind `d21dfce6` again, with no file under
`.claude/settings.json` or `ops/devlane/hooks` changed between the two
(`git diff --stat cccc810b origin/dev` over those paths: empty).

- **Option 1: fast-forward at every session start.** A script on the
  SessionStart event (SessionStart `*` already runs `engine.py`) fetches
  and fast-forwards the main checkout's dev only when it is clean, on
  dev, and git calls the merge a fast-forward; otherwise it prints one
  line saying why not. It prints the old and new sha, because the hooks
  then change under any session already running. Not measured: whether
  a new hook entry in `settings.json` takes effect without a session
  restart.
- **Option 2: LD-38's repair.** The trunk-commit row allows a merge on
  the trunk that git reports as a fast-forward and refuses one that
  would create a commit; a red test in the engine suite is the first
  commit.
- Both are wall paths (the hook registry and engine, `settings.json`):
  one session, a wall grant, nothing else written.
- Offered at this session and not chosen: LD-32's backtick half and
  LD-35 (pr-proof and deliverable read a verb inside backticks or `$( )`
  in a quoted heredoc as a command; pitfall 35) and LD-27 (the wall list
  names no test path) in the same wall session; a GitHub ruleset
  requiring lane and app on dev (the three rulesets read
  `"enforcement":"disabled"` in `gh api repos/uscient/agentscient/rulesets`
  at 2026-09-14T00:47Z).

## Where things stand

- #202 merged into dev at `d21dfce6` (2026-09-14T01:40:11Z), carrying
  `12642609`, `63699e5e`, `a48edd92` and `6505f786`. The dev push runs on
  `d21dfce6`: CodeQL 34796668858 success at 01:41:29Z, ci 34796668765
  success at 01:43:07Z.
- The close records (this file, the AAR, five corpus rows) are one commit
  on the branch after `d21dfce6`; its PR number and checks are in
  `gh pr list`, not here.
- Grant 221 is settled with that commit's sha once the commit is on the
  branch (pitfall 32). It waited for agentscient-5e's suites run to end
  (LD-9); that session's message: suites.sh exit 0 on `acc18b17`.
- The lock names `lane/session-20260913-m` and `lane/session-20260913-n`;
  this session's entry is removed with `deliverable.py remove lane/session-20260913-n`
  once the close PR is on dev.
- Worktrees: `../wt/ag-session-20260913-n`, and `../wt/ag-session-20260913-k`
  from this conversation's first branch (#201, `cccc810b`); both read 0
  uncommitted and 0 unpushed at 01:40:45Z.
- Dispatches: none run (`subs.py`: no dispatch snapshots). Ladders: none.
  Findings: none produced; the open rows of the day are 7 on
  `20260913T023636Z-review-codex-bdbe55`, from before this session.
- The other session: agentscient-5e on `lane/session-20260913-m`, #203
  open at head `420affd9`, merge state UNSTABLE at 01:44:14Z while its
  checks ran; it re-ran its suites on a merge with `d21dfce6`, as agreed
  by message.

## Left as found

- CodeQL run 34748624693 (refs/pull/196/head, `2a0b7e0a`) has read
  `queued` since 2026-09-13T08:52Z. Cancel and force-cancel refused with
  HTTP 409 ("has not been queued yet"); delete, at the owner's word, refused with
  HTTP 403 at 2026-09-14T01:40:15Z. Only GitHub can clear it.
- #200 (actions/checkout 4.4.0 to 7.0.1) is left for a wall session
  (owner, 2026-09-13: "Leave it for a wall session"). Dependabot's body
  has no Proof section and its commit no trailers.
- The close skill's line 40 still says `gh pr checks <number>`; the file
  was lane/session-20260913-m's this session. Whoever next edits it
  swaps in `python3 ops/conductor/tools/watch.py pr <number>`.
- A pitfall to add once #203 is on dev (ids 36 and 37 are held there, and
  `ledger.py` mints from origin/dev): `gh run list --commit` given a
  40-character sha typed out past a short one printed `[]` with exit 0,
  read at first as no run on #202's head; the sha from `git rev-parse HEAD`
  listed ci 34795348058 and CodeQL 34795347239. Do instead: pass the sha
  from `git rev-parse` or from `gh pr view --json headRefOid`, never a
  typed one; an empty list keyed on a value nobody read is could-not-look.
- I-024 (the owner's ideas on git and GitHub work) and I-029 (the PR
  process as MCP tools) stay the owner's, unscheduled.
- CI checks no trailers (`grep -c -i trailer .github/workflows/ci.yml`:
  0 at `cccc810b`); only the local commit-msg hook does.

## Retrieval

```sh
git show dev:ops/conductor/handoff/HANDOFF-2026-09-13-github-use.md
gh pr view 202 --json state,mergeCommit
python3 ops/conductor/tools/defects.py show LD-38
python3 ops/conductor/tools/ledger.py show pitfalls 35
python3 -m unittest discover -s ops/conductor/tests -p test_watch_lever.py -k NoChecksReported -v
python3 ops/conductor/tools/probes.py run
```

Left behind on purpose: the session transcript and the scratchpad,
including the three scripts that fed the hooks their readings; pitfall 35
describes the method.
