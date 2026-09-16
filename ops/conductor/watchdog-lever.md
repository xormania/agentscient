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
  `in/plan.md` (falling back to `brief.scope`), and held `raw.out`,
  `stdout`, `stderr`, and `launcher.log` text. Per-job targets are opened without
  following the job directory, intermediate directories, or file symlinks;
  each must be a regular file no larger than 64 MiB. A held file is scanned
  only through the extent measured when it was opened.
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
| a watched input that cannot be read safely (including a directory, device, symlink, permission failure, or oversized file) | error: `deviation unavailable` and a sanitized watchdog error line, once per record; the scan goes on |
| `record.json` status `closed` or `died` | closed |
| an `exit` file and a record not yet closed | settling: the harness exited, the launcher has not collected |
| otherwise, with no usable worker PID | unobservable: cannot establish worker liveness |
| otherwise | running candidate, subject to the live-worker check below |

The `exit` file alone is never read as closed: the launcher writes it
before it settles the record.

## The lines

Each line is printed once per record (or per key) for the life of the
process. Whatever the process can already see when it starts is backlog:
a record already closed, a job directory with no record copy, and a job
directory whose inputs cannot be read. Nothing about backlog is
reported — not the `closed` line, not a `deviation` line, not
`no record copy`, not `drift`, not the `watchdog error` line for its
unreadable inputs. `--report-existing` asks for backlog and reports
every one of those lines once. Only what changes after start speaks: a
record that closes, a directory that appears, inputs that become
unreadable while the process runs are live and are reported without the
flag (owner, 2026-09-16, through the Lead: "a watcher reports nothing
about a record that was already closed when it started, in every
condition family"; and, the same day, "anything the watcher can see when
it starts, closed, no-copy, unreadable, is silent without
--report-existing"; LD-68).

- `closed <id> status=<s> env=<envelope status> changed=<n> after <m> min`
  — `m` from `at.launched` to `at.closed`; `changed` is the count of
  `result.changed_paths`, or `unknown`.
- `drift <id>: branch <b> outside the deliverable (<branches>)` — while
  `<state>/<lane>/deliverable.json` names branches (`deliverable.py set`),
  a record launched after the lock whose lineage branch is not named;
  `drift PR #<n>: head <b> outside the deliverable (...)` for an open PR
  into the trunk from an unnamed branch. Counted as a deviation.
- `stall <b>: no dispatch running, <m> min since <id|the lock>` — a named
  branch with nothing running and its newest record closed STALL_MIN (45)
  minutes ago or more; `stall <b>: ladder <id> stopped <reason> at <stage>`
  for a stopped ladder on a named branch. Counted as a deviation. Owner,
  2026-09-11: the watchdog watches the conductor, not only the workers.
- `harness gone <id> after <m> min: pid <p> dead, no exit written` —
  `state.json`'s pid is not a live process whose command line carries
  the harness name (a reused pid is not the worker; EPERM is alive).
  The record is then never counted as running.
- An `unobservable <id>` line reports missing or unusable worker identity.
  That job is excluded from running counts and long-running warnings. Later
  ticks reread worker state and may establish a live worker; missing state is
  not a permanently cached judgment.
- `exit written, not collected <id>: <k> min since exit, record still <status>`
  — after the record has been settling for two ticks.
- `long <id>: <m> min running, wall <w> min` — at the warn fraction of
  the wall (`--warn-fraction`, default two thirds); `wall unknown` and
  a fixed 40 minutes when no cap is known.
- `no record copy <id>: cannot judge (...)`.
- `launchers fewer than running records: <L> launch.py processes, <R> running (heuristic: ...)`
  — once per (L, R) pair; a heuristic, and named as one, because the
  record does not carry its launcher's pid (fix scope item 32).
  The census accepts a Python 3 executable named directly or by an absolute
  executable path, including versioned python3.N; its pgrep expression is
  POSIX ERE, not Python-only regular-expression syntax.
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

A closed record is compared unless it was already closed when the watcher
started: backlog says nothing in this family either, and
`--report-existing` is what asks for it (§The lines; LD-68). Each
matching comparison prints once per record:

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
- `deviation unavailable <id>` — a per-job input is unreadable, symlinked,
  non-regular, over 64 MiB, or changes to such a target while being opened.
  The file path, contents, and operating-system detail are not printed; later
  records and the heartbeat are still read.
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

## Proposed efficiency update — dev-lane first

Owner request, 2026-09-04: optimize watchdog and minimize conductor
context/GitHub usage; dev-lane machinery comes before framework work.
This is a declared draft coupling for the current instrument, not owner
ratification and not a new conductor or automatic-remediation service.

- Add `--forge-every N` (default 1), a positive integer, refused as
  `arguments` otherwise. The forge is read on tick 1 and every N ticks
  thereafter; local worker classification still runs each tick. Between
  forge readings the heartbeat explicitly labels the retained count as
  cached, with the tick it was measured on; cached/unreachable/not-watched
  are distinct. No model call is involved.
- Bound the entire forge reading, including the list and all per-PR checks,
  to one 10-second monotonic deadline; each command receives only the time
  remaining. Bound each subprocess's combined captured stdout and stderr to
  1 MiB, and never forward either transcript. List with an explicit limit
  of 200; exactly 200 rows means `200+ (page full, total unmeasured)`,
  not an exact total. Unavailable or malformed forge output stays
  unavailable, never an empty successful listing. Once the deadline is
  exhausted, every unvisited PR is explicitly checks-unreachable. Head ids
  must be 40- or 64-digit hexadecimal SHAs; check buckets are the known
  pass/fail/pending/skipping/cancel set; check names are limited to 512 UTF-8
  bytes and control characters are escaped before printing. Existing CI
  notification identity and once-per-head/check behavior remain unchanged.
- Avoid repeated closed-record JSON/log/deviation reads when their
  inputs have not changed. Invalidate on replacement, size/mtime change,
  deletion, late output, resume or collection. A closed record is not
  immutable. Read errors must be retried, never cached as success. The
  watched inputs include record, state, exit, copied plan and held logs.
  Startup must not parse every record twice just to make the first tick.
  Parsed closed readings are retained in an insertion-ordered LRU capped at
  16 MiB by a conservative upper bound on the complete cache object graph,
  based on Python object sizes rather than source-file bytes. Each new or
  replaced entry is walked individually; its size is added to a maintained
  aggregate along with current container and accounting-metadata overhead.
  Objects shared between entries may be counted more than once, so the bound
  is never presented as an exact retained-size measurement. Unchanged hits
  only refresh LRU order: they do not rebuild or re-account the projection.
  After deviation scanning, only the
  compact fields needed for unchanged closed classification and its line are
  retained. An entry that cannot fit is left uncached and is re-read on the
  next tick; it is never classified unavailable for exceeding the cache
  budget. Per-entry accounting walks object graphs iteratively, deduplicates
  shared or cyclic references within that entry, and therefore does not
  recurse on deeply nested data or traverse the whole cache on update.
  Enumeration and parsing are per job rather than accumulated as one list.
  Eviction never clears notification keys or the last-scanned fingerprint:
  re-read preserves once-per-condition behavior, while an amended fingerprint
  is scanned again and can report a newly introduced deviation.
- Treat `raw.out` as the launcher's actual held stdout, alongside a
  legacy `stdout` file. Search held output without loading whole growing
  transcripts into memory or printing them; an append after open is deferred
  to the next mutation-sensitive scan, while a file above the declared bound
  is explicitly unavailable rather than silently truncated. Preserve
  the existing lexical deviation definitions, not inferred model intent.
- A store-directory enumeration failure reaches the existing watchdog
  error line and tick guard; it is not a successful zero-job reading.

Unchanged: the current period is work plus sleep, missing PID is not
declared dead, launcher counting remains a labeled heuristic, and this
instrument writes no state. Those separate semantic changes are not
smuggled into an efficiency fix. Historical deviations were still
reported when this efficiency fix landed; that carve-out was withdrawn
on 2026-09-16 (LD-68) and backlog is now silent in every condition
family — see the rule in §The lines, which governs.

The cache, notification-key set, and last-scanned fingerprints live only for
the watchdog process. The 16 MiB ceiling covers the cache; notification and
fingerprint metadata remain O(number of jobs and emitted conditions), because
forgetting them would break once and mutation semantics. During a tick, the
running-job list retains the parsed record and state for every active job until
launcher and heartbeat reporting, so this transient payload is O(active jobs),
with each source bounded at 64 MiB. Copied-plan parsing and accounting work are
transient for one entry at a time. None is inside the retained-cache ceiling.

Verification boundary: existing `test_watchdog.py` behavior stays covered;
focused additional probes must distinguish unchanged versus amended
closed records, unreadable store versus empty store, cached versus fresh
forge readings, a full page, and errors spanning an output-read boundary.
