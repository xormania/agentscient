---
name: guide-hooks
description: The hooks mini app — git-native recording of branch switches and commits for every actor rather than only cooperating ones, and the Claude-side hooks and CLI tools beside them.
covers:
  - ops/devlane/hooks/
---

# The hooks app

Several actors work this clone at once: harness sessions, background
reviewers, the owner. Session transcripts only record the actors that
cooperate. Git hooks record everybody.

```sh
sh ops/devlane/hooks/install.sh          # install into the shared hooks dir
WF_AGENT='Your Name <you@example>'    # so the record names you
```

`install.sh` writes `post-checkout`, `post-commit` and `commit-msg`
into the clone's shared hooks directory, so every worktree of the clone
is covered by one installation.

Two of those three are recorders and one is a gate, and the difference
matters. `post-checkout` and `post-commit` swallow every failure and
always exit 0 — a broken recorder must never stop work. `commit-msg` is
the only hook here that can fail a commit: it runs
`ops/devlane/workflow/checks/commit_trailers.py` over the message and
rejects a trailer git will not parse, because a blank line above the
final block silently demotes everything above it to body text.

It refuses for the one thing it judges — the message — and warns rather
than blocks when it cannot run at all, in a worktree without the checker
or on a machine without python3. That is not the gate going soft: the
gate is `dev: gates (commit-trailers)` in CI, which runs the same checker
over every commit the branch adds and cannot be dodged. Stopping every
commit in a clone for an environment problem would cost work without
catching a bad message. `git commit --no-verify` is the deliberate way
past the local hook.

## What gets recorded

One JSONL line per crossing, appended to the clone-shared context
stream (`.git/claude-context-stream.jsonl` — per-clone, and impossible
to commit by accident):

```json
{"at": "...Z", "kind": "branch", "what": "switched to dev",
 "detail": "", "agent": "...", "worktree": "agentscient", "via": "git-hook"}
```

- **Branch checkouts only.** Git passes a flag distinguishing a branch
  checkout from a file checkout; a file checkout is not a crossing and
  is ignored.
- **Commits**, with the worktree that made them.
- **`WF_AGENT`, then `$USER`, then `unknown`** — the record always
  names someone.

## Two properties worth knowing

**A hook must never break git.** Every failure path is swallowed and
the exit status is always 0. If the stream cannot be written, the
record is lost and your checkout still succeeds. Losing a record is
bad; losing a commit because a logger failed is worse.

**Control characters are stripped before quoting.** A branch or agent
name containing a newline would otherwise split one JSON object into
two lines and corrupt everything downstream that reads the file.

`install.sh` refuses rather than guessing when the clone already has a
`core.hooksPath` pointing somewhere else — including when it is set to
an empty value, which is a configuration that exists and would
otherwise be read as "unset".

## The Claude-side scripts

`ops/devlane/hooks/claude/` holds twelve scripts that are not git hooks.
Four are wired as Claude Code hooks by `.claude/settings.json`, five are
the deciders behind them, and three are command-line tools. They are
one directory because they share one subject — the moments a session's
picture of the repo stops being true — and because every one of them can
be read without running a session.

**The four the harness runs.** A hook fires on every matching tool call
in every session, so each one is built to be worth that: precise enough
not to be read as noise, and unable to take the session down with it.

| hook | event | does |
|:--|:--|:--|
| `ops/devlane/hooks/claude/context-precheck.sh` | PreToolUse(Bash) | refuses two silent-failure command shapes, then asks whether the repo about to publish is up to date |
| `ops/devlane/hooks/claude/context-boundary.sh` | PostToolUse(Bash) | says so when the ground moved, and records the crossing |
| `ops/devlane/hooks/claude/test-guard-hook.sh` | PostToolUse(Write/Edit) | reports a test that plants a fault without proving it landed |
| `ops/devlane/hooks/claude/ruff-after-edit.sh` | PostToolUse(Write/Edit) | nags on `ruff check` for the file just edited |

Only the first can refuse anything, and only the two rules in
`ops/devlane/hooks/claude/unsafe-command.py` plus a moved-ref denial. The
other three are advisory and exit 0 on every path — junk input, a missing
file, a missing interpreter, their own errors. Work arrives
half-finished; a hook that interrupts that gets switched off, and then it
protects nothing.

**The five deciders.** Each answers one question and prints the answer,
so it can be run by hand on a payload and read like any other program.
The wrappers above call four of them; `command_shape.py` is called by
those four in turn.

| script | question |
|:--|:--|
| `ops/devlane/hooks/claude/command_shape.py` | what commands does this shell text run, and where does each start? |
| `ops/devlane/hooks/claude/unsafe-command.py` | is this one of the two shapes that fails silently? |
| `ops/devlane/hooks/claude/context-precheck.py` | did the refs of the repository this command names move? |
| `ops/devlane/hooks/claude/boundary-match.py` | did that command cross a context boundary? |
| `ops/devlane/hooks/claude/test-guard.py` | does this test plant a fault it never proves landed? |

`command_shape.py` is the one to know about. Three of these each split a
Bash payload into pieces and looked for the program name in each piece,
in three copies that disagreed — and every disagreement was a defect in
whichever copy lost. It owns the split now and has no opinion about what
any command means: no list of dangerous programs, no notion of
consequence. The rules stay with the script that has the reason for them.

**The three CLI tools**, which are here for a stated reason rather than
by drift: a refusal or a report names them, so the tool and the rule that
recommends it have to move together.

| tool | run when |
|:--|:--|
| `ops/devlane/hooks/claude/pr-feedback.sh` | reading or waiting on a PR's feedback — `unsafe-command.py` names it as the remedy for a poll that watches a subset of surfaces |
| `ops/devlane/hooks/claude/evgrep.sh` | a completeness question — the count comes from the full search and truncation announces itself |
| `ops/devlane/hooks/claude/context-stream.sh` | reading or writing the context stream the git hooks above already write |

```sh
bash ops/devlane/hooks/claude/pr-feedback.sh 55 uscient/agentscient --watch
bash ops/devlane/hooks/claude/evgrep.sh -E 'push|fetch' AGENTS.md
bash ops/devlane/hooks/claude/context-stream.sh tail 15
python3 ops/devlane/hooks/claude/test-guard.py ops/devlane/hooks/tests
```

`pr-feedback.sh` reads five surfaces, because feedback on a pull request
lives in five different API objects and checking four of them and
reporting "nothing" answers the question wrongly rather than not
answering it. Two things it will not do: print `(none)` for a surface it
could not read — a failed call prints `UNREADABLE` with the exit status
and exits 3, distinct from `--watch`'s 1 for a quiet timeout — and stop
at the first page of unresolved threads.

`context-stream.sh` writes the same file the git hooks do, resolved
through `--git-common-dir`, so one clone has one stream however many
worktrees are reading it. Its `record` is what
`ops/devlane/hooks/claude/context-boundary.sh` calls; its `tail` and `since`
are what a session reads at the start, and both print each record
verbatim under its rendering, because a rendering that drops the year,
the agent and the worktree cannot answer whether two worktrees are
reading the same file.

## Working on this app

```sh
python3 -m unittest discover -s ops/devlane/hooks/tests
```

One suite covers both halves. It drives real git repositories rather
than mocking git, which is the only way to test a hook's actual
contract with it — including the case where the stream file is
unwritable and git must still succeed — and it puts stub `gh` and
`ruff` binaries on `PATH` so a tool's exit status is an input rather
than a thing the fixture cannot reach. The Claude-side scripts each
used to carry their own `--test` corpus, which CI never ran; `--test`
is now a pointer to this directory and exits 2.
