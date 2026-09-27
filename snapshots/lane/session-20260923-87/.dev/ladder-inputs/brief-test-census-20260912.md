# Work order — the test-system census

Owner, 2026-09-12: "we need consolidate the existing system in such a way
where we can avoid duplication - then we'll wire in a formal path for
adding tests and CI"; "go - hand grant given - dispatch the census".

This is a read job. It changes nothing. Its deliverable is data: a
machine-readable census of the test tree, and findings over the six
categories in the scope, each with a reproduce command. It chooses no
framework and recommends no dependency; that is a later work order's.

## Contract

1. `out/census.json` exists and parses. It carries `{"commit": "<sha>",
   "files": [...], "helpers": [...], "fakes": [...], "families": [...]}`.
2. `files` has one row per test or support module under `ops/**/tests/`
   and `.claude/skills/*/tests/` (189 test files and 15 support modules
   were counted on 2026-09-12 at dev 729f50a9; reproduce with
   `git ls-files 'ops/**/tests/*.py' '.claude/skills/*/tests/*.py'`).
   Each row: `path`, `bytes`, `kind` (`test` or `support`), `family`
   (the production module or component it exercises, by path), `world`
   (`hand`, `helper:<name>`, or `none`), `fakes` (list of embedded or
   planted programs, by the constant or file name), `subprocess`
   (`true`/`false`), `pins` (list of `{"line": n, "what": "..."}` for
   representation pins as the scope defines them), `origin` (ledger rows
   `LD-n` or PR numbers named in the file's docstring, else `[]`),
   `helpers_used` (support functions imported or called).
3. `helpers` has one row per support function or class used by two or
   more families: `name`, `path`, `families` (list), `what` (one line:
   world, command runner, fake registry, snapshot, guard, other).
4. `fakes` has one row per embedded or planted fake program: `path`,
   `constant_or_file`, `pretends_to_be` (git, gh, claude, codex, grok,
   launcher, other), `call_log` (`append`, `rewrite`, `none`),
   `failure_injection` (`true`/`false`).
5. `families` has one row per production component with tests:
   `component` (path), `production_bytes`, `test_bytes`, `test_files`,
   `ratio` (test bytes over production bytes, two decimals).
6. Every finding in the envelope names one category from the scope, lists
   the files it covers, and carries a `reproduce` command that re-derives
   the count or the list from the tree (`rg -l`, `rg -c`, `git ls-files`,
   `wc -c`, `python3 -c`). A finding without one is not a finding.
7. Baseline numbers to check yourself against, measured on 2026-09-12 at
   dev 729f50a9 with `rg -l`: 52 files set HOME by hand
   (`\["HOME"\] *=` or `"HOME": `), 29 through `isolated_env(` or
   `git_env(`, 86 build a `TemporaryDirectory` or `mkdtemp`, 86 call
   `subprocess.run` or `Popen`, 7 use `live_store_guard`, 28 files hold
   36 `#!/usr/bin/env python3` shebangs inside strings. Where your count
   differs, say which method differs and why; do not adjust the number to
   match.
8. Read only. No file outside `out/` is written. No opinion on Hypothesis,
   pytest, mutmut or any dependency; no proposal of a kit shape. A
   category you could not cover is said in `note` with status `invalid`.

## Where the generic halves already sit (read these first)

- `ops/devlane/dispatch/tests/launch_support.py` (the launch world, fake
  harness CLI, witness).
- `ops/devlane/hooks/tests/support.py` (`isolated_env`, `plant_executable`)
  and `ops/devlane/hooks/tests/gh_stub.py`.
- `ops/conductor/tests/live_store_guard.py`.
- `ops/conductor/tests/test_lane_mcp.py` (`_LaneMcpFixture`, reused by
  `test_lane_mcp_context.py` and `test_lane_mcp_review.py`).
- `ops/conductor/tests/test_ladder_lever.py` (embedded `DISPATCH_PY`,
  `LAUNCH_PY`, `GH_PY`).

## Reuse

Read the lane MCP's `lane_brief`, `lane_changes` and `lane_findings`
before working, and say in the envelope's `note` what you reused
(`reused: <what>` or `reused: nothing applied`).
