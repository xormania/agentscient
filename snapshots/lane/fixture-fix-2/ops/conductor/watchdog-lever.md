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
  (the harness pid), the `exit` file, and the `exit` file's mtime.
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
- `heartbeat: running=<id m/wall, ...>; settling=<n>; launchers=<L|unreachable>; open PRs into dev=<n|unreachable|not watched>`
  — every `--heartbeat-every` ticks (default 6); a pull request whose
  checks could not be read is named inside the count as unreachable.
- `watchdog error: <type>: <message> (tick <t>; the loop continues)` —
  any exception in a tick; the loop never dies quietly.
- `watchdog armed: store <path>, <n> closed records ignored, tick <s>s`
  — the first line, always.

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

It judges nothing: bucket drift against the plan, a stage whose
findings have gone flat, a recurring failure class, and "closed ok but
landed nothing" as a verdict belong to the reporting model of idea
I-017, which reads these lines and the records. The `closed` line's
`env=` and `changed=` are that model's hook, not this loop's judgment.
