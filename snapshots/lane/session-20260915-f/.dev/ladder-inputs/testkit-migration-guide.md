# Moving a test family onto the kit — the worker's guide

The contract is docs/tests.md; the kit is ops/testkit (read its four
modules and its own tests under ops/testkit/tests before you start).
Your job: rewrite the modules the scope names so that each one builds
its world, its commands and its fakes through the kit, with the tests
themselves unchanged in what they assert. This is a migration, not new
tests: the same test names, the same number of tests, the same subjects.

## What every migrated module must satisfy

1. It imports the kit: `from ops.testkit import World, run, ...` (no
   sys.path insert, no PYTHONPATH, no symlink; suites run from the repo
   root as ops/bin/suites.sh does).
2. No HOME, XDG_*, TMPDIR set by hand: a `World()` owns them.
   `world.env(extra)` is the hermetic environment; `world.home`,
   `world.cwd`, `world.tmp`, `world.bin` are its roots; `hermetic_env(home,
   ...)` is the same as a function for a fixture that keeps its own home.
   Ambient host values are named: `World(ambient=("GH_TOKEN",))`.
3. Every subprocess goes through `run(argv, cwd=..., env=..., timeout=N)`;
   `run` returns a `Result` (argv, exit, stdout, stderr, duration, cwd)
   and `Result.refusal()` parses the wire. `expect=0` turns an unexpected
   exit into INVALID (PlantFailed), never a verdict. No bare
   `subprocess.run` / `subprocess.Popen` remains in the module; a fixture
   that must hold a long-lived child registers it with `world.own(child)`.
4. No program embedded in a string literal (a `#!/usr/bin/env python3`
   text written to disk at test time). A fake tool is
   `world.tools.plant("gh", stdout="...", exit=0, responses=[...])`
   (its calls: `world.tools.calls("gh")`, one JSON line per call); a real
   tool logged the same way is `world.tools.wrap("git")`; a program that
   must be a file is a fixture file under the family's `tests/fixtures/`
   (or an existing `tests/fakes/`) planted by path, never a string.
5. Files are planted with `world.plant_text(path, content)` /
   `plant_bytes`, which prove the plant landed; a required ambient tool is
   `world.require("git")`.
6. A world is closed: `with World() as world:` or `self.addCleanup(world.close)`.
7. Nothing else changes: not the subject under test, not ops/testkit,
   not ops/devlane/workflow/checks/testkit-ratchet.json, not modules the
   scope does not name. If the kit lacks something the family needs, do
   not extend the kit: keep the module's own minimal code for that one
   thing, and name it in your note as a kit gap.

## The proof you carry in the envelope

- For each module: the discover command
  `python3 -m unittest discover -s <its tests dir> -p <module>.py` with
  `Ran N tests ... OK` before and after, N unchanged (a finding per
  module, reproduce = the command).
- The family's whole suite green: `python3 -m unittest discover -s <tests dir>`.
- `ruff check <the files you touched>` clean.
- `python3 ops/devlane/workflow/checks/testkit_ratchet.py` exits 0 and
  prints the counts that fell (it prints "the new floor" lines); paste its
  output. Do not write the baseline.
- Your note starts with `reused: testkit.world, testkit.run, testkit.fakes`
  (the invariants the modules now join) and lists any kit gap.

Commit each module as soon as it is green, with the trailers AGENTS.md
requires (Source: original; Co-Authored-By: your model, vendor noreply).
A run killed at the wall then leaves finished modules, not residue.
