# Tests — the kit, the path, the rules

Standing: proposed, slice 1 of the test kit plan (record
`20260913T034513Z-plan-claude-892490`), under the order the owner settled
on 2026-09-12: "reuse of testing patterns - a framework going forward
that avoids one-off tests in favor of a testing framework". Inherits
`docs/wire.md` for the refusal shape and `docs/concerns.md` for fixture
sets. Scope: the dev lane's Python suites under `ops/` and
`.claude/skills/*/tests/`; the prod application's PHPUnit suites are the
prod lane's.

## The kit

`ops/testkit/` is the one place test machinery lives. It is stdlib only
and free of every lane concept: no lane, ladder, finding, dispatch or
telemetry name appears in it, and its own suite proves that by scanning
its sources. Three primitives and one pattern on them:

- **World** (`world.py`): a temporary root that owns HOME, the XDG roots,
  TMPDIR, the working directory, a hermetic environment, planted files
  and tools, owned child processes, and before/after snapshots of
  declared paths. Hermetic by default: nothing from the host reaches a
  subject unless it is named — values in `ambient=`, tools in
  `ambient_tools=`. Under `host_path=False` a subject's PATH is the
  world's own bin and nothing else, so a tool the case neither planted nor
  named is absent, and `run` says so on the wire instead of falling
  through to the operator's copy of it (LD-72). That is the shape this
  contract asks for and the default it will carry; it is not the default
  on 2026-09-16, because it turns 1,339 rows red across 95 modules, listed
  at `d8219578` in
  `ops/conductor/handoff/HANDOFF-2026-09-16-hermetic-path-sweep.md`. Until
  that sweep lands, `host_path` defaults to True and the host's PATH
  follows the world's bin; the kit's own rows run strict and pin both
  values. Owned children are reaped at close. A plant proves it landed.
- **Daemons** (`world.py`, reached as `world.daemon`): a process that
  outlives the command that started it is started through
  `world.daemon(name, start, stop, match=, socket=, timeout=)` and
  recorded, as malloc records a block for free (owner, 2026-09-23,
  relayed by the Lead: "daemons are managed in the kit - something like a
  malloc"). A daemon is its pids in the process table, each with its start
  time, and the children it starts after; never the files it leaves
  (measured at `a93368b5`: 1 run in 20 leaked 18 tmux servers, because the
  teardown skipped when the socket file was missing). `close` stops the
  recorded daemons in reverse order, escalating within each timeout: the
  stop, then SIGTERM, then SIGKILL. It proves each gone: pids dead, socket
  not accepting. Then it sweeps for any process still carrying the
  world's HOME, which is a daemon started around the kit. `close`
  finishes its cleanup either way and then raises `DaemonRefused`, one
  line per daemon in the wire's shape, class `daemon`, when a daemon's
  own stop did not bring it down or a process of the world was left
  unrecorded. A daemon a case starts around the kit is a finding of the
  kind rule 5 names. A daemon the subject starts is recorded after the
  subject returns, with `world.adopt(name, stop, match=, socket=,
  timeout=)`: the processes holding the unix socket bound at `socket`,
  read from the kernel's socket table and narrowed by `match` when both
  are given, or those `match` names. The case starts nothing, so the
  subject's own path is the one under test, and `close` stops an adopted
  daemon as it stops a started one.
- **run** (`command.py`): one call, one result shape (argv, exit, stdout,
  stderr, duration, cwd), one timeout policy: expiry kills and reaps the
  child and raises, naming the argv. A result reads its own refusal line
  into class, expected, found and needed.
- **Tools** (`fakes.py`, `fake_program.py`): one fake registry driven by
  data. A planted tool answers by argv from its spec, injects failure by
  data, and appends one JSON line per call to an append-only log. A
  wrapped real tool is logged the same way.
- **cases** (`cases.py`): a case table addresses rows by id, never by
  count. `refusal_wire` asserts the wire on one row; `calibrate` runs a
  table against its planted faults and reports caught and quiet per
  fault; `sidebyside` runs an old command and a new one over one fault
  set and writes the record. Nothing is retired until that record shows
  the rows catch every fault the old file caught.

## Reaching it

Every suite runs from the repository root, as `ops/bin/suites.sh` and CI
do, and imports the kit in one line: `from ops.testkit import World,
run, refusal_wire`. There is no other way in: no symlink, no `sys.path`
insert, no `PYTHONPATH`. A test run from another directory fails at
import with `ModuleNotFoundError: ops.testkit`; that failure is the
refusal, and the kit's own suite proves it from a temporary directory.

## Rules for a test

1. A new test module under any `tests/` directory imports the kit, or
   carries `# testkit: exempt <reason>` within its first ten lines.
2. A regression is a row in a case table with its `origin` (a ledger row,
   a PR), never a file named after one.
3. A table carries a fixture set, planted faults it catches and clean
   neighbours it passes, or it is a declared gap. A pin on a count the
   contract does not own is a finding.
4. A world is hermetic by default; ambient is explicit and named.
5. Every subprocess goes through `run`; a call without a timeout is a
   finding.
6. A fake is planted through the registry and logs every call; a program
   embedded in a test module is a finding.
7. No test package (pytest, Hypothesis, a mutation tool) until two
   families share the primitives and the leverage is measured and
   recorded. The owner decides on that record; nothing installs before it.
8. The kit is wall (D-TESTKIT-1): written under a grant of class `wall`,
   in a session whose deliverable is the wall and which writes nothing
   else. Its tests are written by a producer other than its author.
9. A case executes the subject's behaviour and asserts what it did. A
   case that pins a schema word, a mock's shape, a name, or an assertion
   that cannot fail is a declared gap wearing a pass; it is rewritten to
   run the subject against a planted fault, or dropped.

## Invariants

The names a tests job's note joins with `reused:`:

- `testkit.world` — hermetic by default, ambient by name, PATH the
  world's own bin under `host_path=False`, children reaped.
- `testkit.daemon` — every daemon recorded by `world.daemon` or
  `world.adopt`, stopped in
  reverse at close with the stop, SIGTERM and SIGKILL, proven gone by pid
  and socket; a stop that fails, or a process of the world left
  unrecorded, refuses class `daemon`.
- `testkit.run` — one result shape, one timeout policy, the wire parsed.
- `testkit.fakes` — fakes driven by data, an append-only call log.
- `testkit.refusal-wire` — exit as declared, stdout empty, one stderr
  line, the class token first, then expected, found, needed.
- `testkit.rows` — rows by id with an origin, a fixture set or a declared gap.
