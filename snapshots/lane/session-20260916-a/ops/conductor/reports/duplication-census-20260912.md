# Duplication census of the lane's tools, 2026-09-12

Measured on `dev` at `729f50a9` with
`python3 ops/conductor/reports/duplication-census.py ops`, the script
tracked beside this record. Scope: `ops/`, excluding tests, fixtures,
the archive and vendored copies. The owner asked for thoughts on
consolidating code duplication in the system itself while a second
session consolidates tests and CI; the thoughts rest on this reading,
and the owner agreed the four steps below (owner, 2026-09-12: "agreed -
hand grant ok'd for #1, #2, #3, and #4"; grant 176).

## What the reading says

The duplication is concentrated in a few helpers, and the ones copied
most are the ones that implement the wire itself.

| helper | copies | what differs between the copies |
|---|---|---|
| `refuse()` in Python | 18 | four behaviours: print and exit 2; raise a string exception; raise a structured exception; whitespace collapsed or a 500-character clip in some |
| refuse, die or fail helper in shell | 8 | counted, not compared |
| literal wire lines outside any helper | 24 in `ops/conductor/tools/dispatch.sh` alone | |
| `identity()` | 12 | four regexes; `graft.py` accepts any non-empty value; `ci.py`, `decisions.py`, `monitor.py` accept an address without `@` |
| `lane_name()` and `conf_value()` | 8 | four byte-identical `lane_name` bodies, each with a hand-rolled fallback parser for when `laneconf.py` cannot be imported |
| `now`, `stamp`, `parse_stamp` | 11 | `skills.py` uses `time.strftime`, the rest `datetime`; `watchdog.py` tolerates a naive stamp, `hand.py` does not |
| sqlite `connect()` | 4 | two policies: create on read (`findings.py`, `hand.py`), refuse on absent (`ci.py`, `decisions.py`); `decisions.py` ignores `XDG_STATE_HOME` |
| `git()` and `run()` | 12 | timeouts of 5 s, 90 s, a constant, or none |

The root cause is structural: nothing under the lane is an importable
package, every tool is a standalone script, and sharing means sys.path
surgery or an `importlib` loader. The fallback parsers inside
`lane_name()` exist only because `import laneconf` may fail when a test
stages a copy of the tool elsewhere; 31 of the conductor suites do
that, which is measured in `ops/conductor/tests/` by the
`copy-tool-bytes` stand-in each carries.

## Findings outside this deliverable, declared

Two readings are not duplication and are recorded here so nobody
infers them absent. Neither is repaired on this branch.

- **The vendored isolation copy.** `ops/devlane/dispatch/levers/codex/vendor/isolation.py`
  differs from `ops/devlane/harness/isolation.py` by 163 added or
  removed lines and lacks the `agy` entry and the credential-age rule.
  A real dependency with no declared edge and no drift check: a dark
  coupling in the sense of `docs/verified-couplings.md`.
- **A second wire.** `ops/devlane/harness/receipt/errors.py` gives a
  refusal exit 1 and an integrity failure exit 2, with the sentence
  shape `refused: … expected … actual`. `docs/wire.md` says a refusal
  is exit 2 and reads `class: expected; found; needed`. The receipt
  engine predates the wire (PLAN §4); its adoption is a change of its
  own.

## The four steps agreed

1. This record, committed on the session branch before any change.
2. One shared module, `ops/conductor/tools/instrument.py`, additive:
   the wire, identity, the UTC clock, the state root, the lane-conf
   read and one bounded subprocess call, with its own tests and a
   registry row. No caller changes in that commit.
3. One tool per commit, each migrated with the gate in
   `test_instrument.py` red before (the tool named in `MIGRATED` while
   still carrying its copies) and green after, with that tool's own
   suite green with the same command.
4. The runners' policies stay at the callers: `onboard.py` returning an
   absence reason and `watchdog.py`'s bounded capture are deliberate.
   The shared call is bounded; what a caller does with a timeout is
   the caller's.

Out of scope on this branch, by the wall ruling (owner, 2026-09-12):
`probes.py`, `laneconf.py`, the hook engine and matrix, the suite lever
and the CI workflow. Their copies are counted above and stay until a
wall session.

## What was not measured

- The bodies of the eight shell helpers; only their presence.
- Which of the 31 staging suites run the copied tool from a scratch
  directory rather than the repository, per tool; that is measured
  when each tool migrates.
- One failure in the first full `ops/bin/suites.sh` run of the day on
  the conductor suite (1022 tests) that did not reproduce on the rerun
  (1022 OK); the failing test's name was not captured.

## The reading, verbatim

```
== top-level function names defined in 3+ files ==
 18 refuse         ops/conductor/tools/branches.py ops/conductor/tools/ci.py ops/conductor/tools/correction.py ops/conductor/tools/decisions.py ops/conductor/tools/deliverable.py ops/conductor/tools/findings.py ops/conductor/tools/hand.py ops/conductor/tools/ladder.py ops/conductor/tools/land.py ops/conductor/tools/lane_read.py ops/conductor/tools/monitor.py ops/conductor/tools/onboard.py ops/conductor/tools/probes.py ops/conductor/tools/watch.py ops/conductor/tools/watchdog.py ops/devlane/harness/graft.py ops/devlane/harness/receipt.py ops/devlane/workflow/checks/term_wall.py
 12 identity       ops/conductor/tools/branches.py ops/conductor/tools/ci.py ops/conductor/tools/co_doc.py ops/conductor/tools/control.py ops/conductor/tools/decisions.py ops/conductor/tools/deliverable.py ops/conductor/tools/findings.py ops/conductor/tools/hand.py ops/conductor/tools/land.py ops/conductor/tools/lane_refs.py ops/devlane/harness/graft.py ops/devlane/harness/receipt.py
  6 git            ops/conductor/tools/branches.py ops/conductor/tools/control.py ops/conductor/tools/ladder.py ops/conductor/tools/land.py ops/devlane/harness/graft.py ops/devlane/harness/receipt/gitio.py
  6 run            ops/conductor/tools/branches.py ops/conductor/tools/ladder.py ops/conductor/tools/onboard.py ops/conductor/tools/watchdog.py ops/devlane/harness/receipt/receipts.py ops/devlane/task/run.py
  5 digest         ops/conductor/tools/control.py ops/conductor/tools/ladder.py ops/conductor/tools/lane_read.py ops/conductor/tools/monitor.py ops/devlane/harness/receipt/canonical.py
  5 lane_name      ops/conductor/tools/decisions.py ops/conductor/tools/deliverable.py ops/conductor/tools/findings.py ops/conductor/tools/hand.py ops/conductor/tools/onboard.py
  5 now            ops/conductor/tools/hand.py ops/conductor/tools/skills.py ops/conductor/tools/watchdog.py ops/devlane/harness/graft.py ops/devlane/harness/receipt/canonical.py
  5 parser         ops/conductor/tools/branches.py ops/conductor/tools/ci.py ops/conductor/tools/decisions.py ops/conductor/tools/hand.py ops/devlane/harness/receipt.py
  5 report         ops/conductor/tools/decisions.py ops/conductor/tools/hand.py ops/conductor/tools/probes.py ops/conductor/tools/skills.py ops/devlane/harness/isolation.py
  4 _parser        ops/devlane/dispatch/launch.py ops/devlane/task/fileset.py ops/devlane/task/run.py ops/devlane/task/verify.py
  4 connect        ops/conductor/tools/ci.py ops/conductor/tools/decisions.py ops/conductor/tools/findings.py ops/conductor/tools/hand.py
  4 decide         ops/conductor/tools/decisions.py ops/devlane/hooks/claude/engine.py ops/devlane/hooks/claude/matrix.py ops/devlane/hooks/claude/no-subagents.py
  3 _inside        ops/conductor/tools/monitor.py ops/devlane/dispatch/launch.py ops/devlane/task/fileset.py
  3 _now           ops/devlane/dispatch/launch.py ops/devlane/task/run.py ops/devlane/task/verify.py
  3 _stamp         ops/conductor/tools/monitor.py ops/devlane/task/envelope.py ops/devlane/task/run.py
  3 _text          ops/conductor/tools/lane_read.py ops/conductor/tools/probes.py ops/devlane/task/envelope.py
  3 build          ops/devlane/dispatch/record.py ops/devlane/harness/controls/build.py ops/devlane/task/envelope.py
  3 check          ops/conductor/tools/correction.py ops/devlane/hooks/claude/unsafe-command.py ops/devlane/task/verify.py
  3 conf_value     ops/conductor/tools/ladder.py ops/conductor/tools/land.py ops/conductor/tools/watchdog.py
  3 parse_args     ops/conductor/tools/land.py ops/conductor/tools/watch.py ops/conductor/tools/watchdog.py
  3 parse_stamp    ops/conductor/tools/hand.py ops/conductor/tools/watchdog.py ops/devlane/telemetry/worth.py
  3 query          ops/conductor/tools/lane_mcp.py ops/conductor/tools/lane_read.py ops/devlane/harness/graft.py
  3 repo_root      ops/conductor/tools/probes.py ops/devlane/harness/receipt.py ops/devlane/hooks/claude/matrix.py
  3 stamp          ops/conductor/tools/ci.py ops/conductor/tools/decisions.py ops/conductor/tools/hand.py

== function bodies identical across files (3+ statements) ==
2209cfc759 ops/conductor/tools/deliverable.py:identity | ops/conductor/tools/findings.py:identity | ops/conductor/tools/hand.py:identity
8d066d37a2 ops/devlane/harness/controls/build.py:at | ops/devlane/harness/vet_context.py:_at
9afda46336 ops/conductor/tools/decisions.py:lane_name | ops/conductor/tools/findings.py:lane_name | ops/conductor/tools/hand.py:lane_name | ops/conductor/tools/onboard.py:lane_name

== files spelling the refusal wire literally (count, file) ==
  1 ops/conductor/tools/branches.py
  1 ops/conductor/tools/ci.py
  3 ops/conductor/tools/control.py
  1 ops/conductor/tools/decisions.py
  1 ops/conductor/tools/deliverable.py
  1 ops/conductor/tools/findings.py
  1 ops/conductor/tools/hand.py
  1 ops/conductor/tools/land.py
  1 ops/conductor/tools/onboard.py
  1 ops/conductor/tools/probes.py
  1 ops/conductor/tools/watch.py
  1 ops/conductor/tools/watchdog.py
  3 ops/devlane/harness/graft.py
  1 ops/devlane/harness/receipt.py
  3 ops/devlane/hooks/claude/engine.py
  3 ops/devlane/hooks/claude/matrix.py
  1 ops/devlane/hooks/conductor-control.py
  3 ops/devlane/task/write_path.py
  1 ops/devlane/workflow/checks/term_wall.py
  4 ops/bin/fixture.sh
 24 ops/conductor/tools/dispatch.sh

== shell files defining their own refuse/die/fail helper ==
    ops/bin/go.sh
    ops/conductor/tools/dispatch.sh
    ops/conductor/tools/gate.sh
    ops/devlane/dispatch/levers/apply-push.sh
    ops/devlane/dispatch/levers/claude/fable-dispatch.sh
    ops/devlane/dispatch/levers/codex/codex-dispatch.sh
    ops/devlane/dispatch/levers/grok-dispatch.sh
    ops/devlane/dispatch/levers/selftest.sh

== the vendored isolation copy against the harness module ==
    lines added or removed: 163

== the receipt engine's refusal exit code (the wire says 2) ==
    EXIT_REFUSED = 1
```
