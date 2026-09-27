# The watchdog lever — one line per condition, on cadence

`python3 ops/conductor/tools/watchdog.py` reads the dispatch store and
the forge and prints one line per condition worth acting on. It never
writes: no identity is required, and a refusal from it on a read is
itself a finding. The owner asked for it on 2026-09-04 ("Can you
periodically check the workload and watch for issues like that?");
Grok's review of the first cut (record
`20260904T071136Z-review-grok-d7233b`) shaped this contract.

## Where it reads

- The store: `--store`, else `DISPATCH_JOBS`, else
  `$XDG_STATE_HOME/agentscient/dispatch`, else
  `$HOME/.local/state/agentscient/dispatch` — the launcher's own rule.
  A store that is not a directory is refusal class `store`.
- Per job directory: `record.json` (the record copy), `state.json`
  (the harness pid), the `exit` file and its mtime, the copied
  `in/plan.md` (falling back to `brief.scope`), and held `stdout`,
  `stderr`, and `launcher.log` text.
- Ladder records: JSON files in the state root's sibling `ladders/`
  directory.
- The job caps: the record's `caps.timeout`, else the job's
  `caps.timeout` in `ops/devlane/task/jobs.json` (found beside this
  file, or beside the working directory when the file runs as a staged
  copy), else unknown.
- The forge, unless `--no-forge`: `gh pr list --base <TRUNK_BRANCH> --state open`
  and `gh pr checks` per open pull request; the trunk comes from the lane
  conf through its reader (a missing key is refusal class `conf-key`).

## Classification, per job directory

| on disk | kind |
|:--|:--|
| no `record.json`, or one that is not a JSON object | no-copy: cannot judge; said once, never inferred |
| a `record.json` or `state.json` that cannot be read (a directory in its place, a permission) | error: the watchdog error line, once per record and error type; the scan goes on |
| `record.json` status `closed` or `died` | closed |
| an `exit` file and a record not yet closed | settling: the harness exited, the launcher has not collected |
| otherwise | running |

The `exit` file alone is never read as closed: the launcher writes it
before it settles the record.

## The lines

Each line is printed once per record (or per key) for the life of the
process. Records already closed when the process starts are not
reported unless `--report-existing`.

- `closed <id> status=<s> env=<envelope status> changed=<n> after <m> min`
  — `m` from `at.launched` to `at.closed`; `changed` is the count of
  `result.changed_paths`, or `unknown`.
- `harness gone <id> after <m> min: pid <p> dead, no exit written` —
  `state.json`'s pid is not a live process whose command line carries
  the harness name (a reused pid is not the worker; EPERM is alive).
  The record is then never counted as running.
- `exit written, not collected <id>: <k> min since exit, record still <status>`
  — after the record has been settling for two ticks.
- `long <id>: <m> min running, wall <w> min` — at the warn fraction of
  the wall (`--warn-fraction`, default two thirds); `wall unknown` and
  a fixed 40 minutes when no cap is known.
- `no record copy <id>: cannot judge (...)`.
- `launchers fewer than running records: <L> launch.py processes, <R> running (heuristic: ...)`
  — once per (L, R) pair; a heuristic, and named as one, because the
  record does not carry its launcher's pid (fix scope item 32).
- `ci <fail|cancel> #<pr> at <sha>: <check>` — the head's full sha; once
  per pull request head and check name; every failing or cancelled
  check, not the first.
- `heartbeat: running=<id m/wall, ...>; settling=<n>; launchers=<L|unreachable>; open PRs into dev=<n|unreachable|not watched>; deviations=<n>`
  — every `--heartbeat-every` ticks (default 6); a pull request whose
  checks could not be read is named inside the count as unreachable;
  deviations counts deviation lines printed since the process started.
- `watchdog error: <type>: <message> (tick <t>; the loop continues)` —
  any exception in a tick; the loop never dies quietly.
- `watchdog armed: store <path>, <n> closed records ignored, tick <s>s`
  — the first line, always.

## Deviations

Closed records are compared even when their ordinary `closed` line is
suppressed at startup. Each matching comparison prints once per record:

- `deviation assumption <id>` — an envelope note or finding contains
  one of `assumption`, `assume`, `substitute`, `stub`, or
  `hermetic substitute` (case-insensitive).
- `deviation lock <id>` — a changed path named
  `composer.lock`, `Cargo.lock`, `requirements.lock`, or `symfony.lock`
  is absent from the bucket line's paths.
- `deviation bucket <id>` — a changed path is outside the bucket line,
  or the changed count is more than four times its class maximum.
- `deviation size <id>` — an `implement` or `author-tests` record is
  over its class maximum. This S-bucket contract fixes the maximum at
  3 files or 2,000 landed lines; other classes are not inferred.
- `deviation envelope <id>` — a `tripped` or `invalid` envelope carries
  findings or changed paths.
- `deviation errors <id>` — an `author-tests` envelope note or held
  output reports `errored` or an `errors=` count above zero.
- `deviation refused <id>` — held launcher text starts a refusal line
  with `empty-comparison`, `scope-cap`, `conf-key`, or `toolchain`.
- `deviation retry <id>` — a ladder is stopped or has a stage attempt
  above one.
- `deviation minutes <id>` — elapsed minutes are more than four times
  the S calibration maximum for the job: implement 4, author-tests 21,
  check-tests 10 minutes.

The words, filenames, class limits, factors, jobs, and refusal classes
above are the comparison data. Deviation detection reads the local
records and plans only; it makes no forge call and recommends no action.

## Seams

- `--tick` seconds, or `WATCHDOG_TICK` (default 300); not a positive
  number is refusal class `tick`.
- `--once`: one tick, exit 0 — the test seam.
- `--heartbeat-every`, `--warn-fraction`: out of range is refusal class
  `arguments`.
- `--no-forge`: the forge is not asked, and the heartbeat says so.

## Refusals

| class | when |
|:--|:--|
| `store` | the store path is not a directory |
| `tick` | the tick is not a positive number |
| `arguments` | heartbeat-every not above zero, or warn-fraction outside (0, 1] |

One line on stderr, exit 2, stdout empty, expected–found–needed.

## What it is not

It does not choose a remedy. A stage whose findings have gone flat, a
recurring failure class, and "closed ok but landed nothing" remain work
for the reporting model of idea I-017. The watchdog names only the
mechanical deviations and their record ids; the conductor decides what
to do about them.
