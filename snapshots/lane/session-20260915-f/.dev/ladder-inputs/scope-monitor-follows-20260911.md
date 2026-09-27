# Work order: the monitor follows the ladder

Owner, 2026-09-11, in session, after reviewing the watchdog and monitor
instruments: "#1 - agreed, #2 agreed" (start the watchdog long-lived; a
work order in which the driver registers each stage's record id with the
monitor so the queue follows a ladder without hand-written configs), then
"agreed - fold the 3 ideas in #2 WO scope" (the three ideas from the
owner's retired session watch script, now at
`deprecated/session-watch-20260904@0d5bcde`, path `.dev/wip/watch-lane.py`).
The scope-discipline clause beside this file governs.

This file is the scope only: what, and the boundaries. The plan is not
its author's to write. Dispatch after the end-to-end fixture work order
(I-020) lands, so the fixture is where this work order's behaviour is
proven; it adds one scenario there.

## What

Two read-only instruments exist and nothing uses them. The watchdog
prints one line per condition from the dispatch store and the forge; the
monitor turns configured observations into a bounded queue a consumer
pulls. Neither is wired to the ladder driver, so the conductor polls
records by hand with sleep loops and single-id waits, which is what the
instruments were built to replace. After this work order a running
ladder is observed by the monitor from its first stage without a
hand-written config, the conductor reads one bounded three-word answer
per event, a set of records can be waited on as one call, the session's
own configuration drift is probed at session start from tracked values,
and the watchdog's fresh start no longer replays history.

## Contract

1. **The monitor follows the ladder.** When the ladder driver mints a
   stage record it adds that record id to a dispatch monitor for the
   ladder, so a `monitor.py run --loop` started against that ladder
   observes every stage from the first without an operator editing a
   config. The monitor keeps its rule of reloading and validating the
   config each cycle; the driver writes only where the monitor contract
   allows a config to live, never into the monitor's state.
2. **A three-word answer for the conductor.** `monitor.py digest` for
   the conductor consumer summarises each event as exactly one of
   `ACTION_REQUIRED`, `DONE`, or `FAILED`, followed by the record id and
   the condition, within the existing 240-byte summary bound. The
   mapping is declared data in the contract (death, invalid envelope and
   refusal are FAILED; completion and no-op are DONE; long-running,
   settling-uncollected and CI failure are ACTION_REQUIRED), not inferred
   from text.
3. **Wait for a set.** The launcher's `wait` verb accepts more than one
   record id and returns when all are closed or died, printing one line
   per record with its status and envelope state; a death among them is
   a Finding (exit 1), a refusal on arguments is on the wire. The single
   id form is unchanged.
4. **Session probes from tracked values.** The onboard hook that runs at
   session start and after compaction measures the interactive model
   setting and the local conf's default agent and Claude model lines
   against the tracked lane conf, and prints a line per disagreement. No
   model name is hardcoded in the probe; the rule is whatever the
   tracked conf says on the day.
5. **The watchdog starts quiet.** A fresh watchdog reports deviations
   only for records that close after it starts, unless
   `--report-existing`, matching how it already treats `closed` lines.
   The instrument still writes no state.
6. **One fixture scenario.** The end-to-end fixture gains a scenario in
   which a planted ladder runs under a following monitor and the digest
   shows DONE for each stage and FAILED for a planted death; the
   watchdog's lines for the same run are asserted.
7. **Refusals on the wire, registry rows.** Every new refusal is one
   stderr line `class: expected …; found …; needed …`, exit 2, stdout
   empty; each component that gains a refusal adds one hermetic
   invocation to the registry.

## Boundaries — not this work order

- Any remediation chosen by an instrument. The monitor and watchdog name
  conditions; the conductor decides. Unchanged from both contracts.
- Model calls, external delivery adapters, harness hook or idle-wakeup
  integration. The monitor contract leaves them unadmitted; so does this.
- The git-refs freshness adapter's acceptance (owner direction 2026-09-09).
  Separate; its example stays disabled here.
- The watchdog's size and minutes calibration (3 files or 2,000 lines; 4,
  21, 10 minutes). A calibration ruling, not code.
- Archiving the twenty job directories from 2026-09-03 that have no record
  copy. Conductor work in the store, not code.
- Retiring the owner's script. Done: it lives at
  `deprecated/session-watch-20260904@0d5bcde` for the data.

## Measured, 2026-09-11, at dev 5beafd8

- Callers: `grep -c watchdog` over `ops/conductor/tools/ladder.py`,
  `ops/bin/ladder.sh`, `ops/conductor/conductor-start-plan.md`,
  `ops/README.md`: 0, 0, 0, 0; `grep -c monitor.py` over the same: 0.
- A live watchdog tick with `--once --heartbeat-every 1`: 631 closed
  records ignored, 240 deviation lines replayed from history (170
  assumption, 61 envelope, 4 lock, 3 errors, 2 bucket), 20 `no record
  copy` lines, heartbeat naming two running reviews with minutes against
  wall, launchers=4, open PRs into dev=1.
- The watchdog now runs long-lived from this session (tick 300 s, forge
  every third tick), started 2026-09-11 after the owner's "#1 - agreed".
- `monitor.py check` on the example config: valid, 3 monitors (all
  disabled), 2 schedules, 3 conditions, 3 routes. Adapters registered:
  dispatch, codex-usage, github-rate, git-refs.
- Prior monitor runs, each with a hand-written config and explicit state:
  2026-09-04 on seven record ids plus Codex usage and rate limit, 30
  events; 2026-09-10 on four record ids, 29 events, one consumer cursor.
- `launch.py wait` takes exactly one `id` (`--timeout`, `--interval`).
- Onboard hook: `ops/devlane/hooks/claude/onboard-on-compact.sh`, wired
  in `.claude/settings.json`; it measures law, register, ledger, PRs,
  dispatches and branch, not the model setting or the local conf.
- The retired script: hardcoded live record id and repository root, a
  forbidden-model list naming the current session model, one watchdog
  `--once` per 30 s, `sys.exit` inside a probe.
- Registry rows: `watchdog.py` refuses `store` on `--store /dev/null`;
  `monitor.py` refuses `config` on `--config /dev/null check`.

## Tests — proposed coverage, not approval

- `ops/conductor/tests/`: the driver adds each minted id to the ladder's
  monitor config and the monitor's reload picks it up (item 1); digest
  summary mapping for each condition class, both directions (item 2);
  the fresh-start rule with a planted closed record before and after
  start (item 5).
- `ops/devlane/dispatch/tests/`: `wait` with two ids, one closing and one
  dying, exit 1 with both lines; arguments refusal on a malformed id
  (item 3).
- `ops/devlane/hooks/`: the onboard probe against a planted local conf
  that disagrees with the tracked conf (item 4).
- The fixture scenario (item 6) lives in the fixture's own suite.

## Calibration

Declared S in two buckets: the driver's registration with the monitor
and the digest summary; the launcher's set wait and the onboard probe.
Files expected: `ops/conductor/tools/ladder.py`,
`ops/conductor/tools/monitor.py`, `ops/conductor/monitor-lever.md`,
`ops/conductor/tools/watchdog.py`, `ops/conductor/watchdog-lever.md`,
`ops/devlane/dispatch/launch.py`,
`ops/devlane/hooks/claude/onboard-on-compact.sh`, the registry, tests.
The planner buckets; this row is the declaration it is measured against.
