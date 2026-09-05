# worth.md — costs and results, joined

Two questions the dev lane must answer from data, not memory: *was the
recent work worth what it cost?* and *where are tokens being wasted?*
Both are answered by `ops/devlane/telemetry/worth.py`, which reads the
same stores as `usage.py` and the same repo history as everything
else. Every figure it prints is produced at run time and stamped with
the window and the repo state it was measured against. No figure from
this tool is ever USD: the only native dollar wire (grok
`costUsdTicks`) has an unverified scale, and it is reported raw as
ticks or `unrecorded`, exactly as `usage.py` does.

## worth report — cost x results

    python3 ops/devlane/telemetry/worth.py report --repo PATH \
        [--since ISO] [--until ISO] [--now ISO] [--format plain|json]

The cost block: per harness (claude, codex, grok), the sessions and
messages inside the window, and in / cached / out / total token sums.
The results block, from the repo's history alone (no network): merge
commits landed on the current branch in the window with their PR
numbers parsed from the subject, non-merge commits, and the
test-definition count at each window edge with its delta.

## worth waste — where the spend concentrates

    python3 ops/devlane/telemetry/worth.py waste --repo PATH \
        [--since ISO] [--until ISO] [--now ISO] [--top N] [--format plain|json]

`--claude-dir` has no command-line default. When omitted it is read from
`CLAUDE_DIR` in the lane configuration; a relative value is resolved against
the user's home directory, and a missing key refuses as `conf-key`.

Ranks sessions by total tokens and names, for each: the harness, the
session id, messages (or runs), out, and cached tokens. Claude rows also carry
turns after last-write-per-message-id dedup, mean context tokens over that
same retained population, and tool-result deny refusals (both `is_error=true`
and the deny marker are required). A retained usage row with malformed token
types, negative values, or non-finite values is an explicit gap rather than
a partial measurement. Boolean values are not token currencies. An unreadable
candidate found under Claude's slash-and-dot encoded repository directory is
appended outside the measured `--top` ranking as `kind=gap`: its session id
stays discoverable, but its repo, window, turns, mean context, and refusals are
`unrecorded`, and it does not count as a known session. Signals are
numbers with provenance, never verdicts: `cache-churn` carries the
cached-read and output figures whose ratio breached, and
`heavy-turn` names the single heaviest message (for codex, the
largest step between its cumulative counts) or run. A human or an
agent decides what to change; the tool only points.

## Behavior contract (tests are authored from this section alone)

1. **Time is an input.** `--now ISO` is accepted by both subcommands;
   when absent the current time is read once. The default window is
   the 24 hours ending at now; `--since`/`--until` (ISO 8601,
   inclusive lower, exclusive upper) override either edge. No test
   may depend on the wall clock: fixtures pass `--now`.
2. **Windowing is per message for claude and codex**: a usage event
   counts iff its own timestamp is inside the window. **Windowing is
   per run for grok**: a run (as split by `usage.py`'s shrink rule)
   counts iff its last report's timestamp is inside the window; runs
   are never subdivided, because grok reports cumulatively and a
   partial run has no honest per-message delta. The report says
   `runs=` for grok, not `messages=`.
3. **Cost figures reuse the usage.py accounting** — same stores, same
   session discovery, same cwd filter for `--repo`, same last-wins
   dedup for claude ids, same grok run-splitting, cost ticks, and
   incompleteness discipline. A harness whose stores are absent or
   unparseable prints `unrecorded`, never 0. `counted=N/M` and
   `(incomplete)` propagate to every output format. When `--claude-dir`
   is omitted, `CLAUDE_DIR` comes from lane configuration and relative
   values resolve against the user's home directory.
4. **Results come from git only.** Merge commits on HEAD's
   first-parent line in the window; PR numbers parsed from `Merge
   pull request #N` subjects; commits with no PR number are listed as
   commits, not dropped. The test-definition count is measured from
   the two window-edge trees (`git rev-list -1 --before` at each
   edge), never from the working tree; if an edge has no commit the
   report says `unrecorded` for the delta.
5. **The join is stamped**: repo HEAD short sha, branch, window
   [since, until), and generation `--now` appear in both formats.
6. **waste ranks by window-scoped totals**: `--top N` (default 5)
   sessions ordered by total tokens inside the window, ties broken by
   session id for determinism. `cache-churn` fires for a session iff
   cached reads exceed 20x its output tokens AND output is nonzero;
   `heavy-turn` names the single largest out-token message (claude /
   codex) or run (grok) in each listed session. Signals carry the
   session id and harness so the transcript can be opened. Every ranked
   Claude row carries `turns` from the retained, id-bearing assistant-usage
   population after last-write-per-message-id dedup, mean `avg_context`
   (input plus both caches) over that population, and tool-result deny
   `refusals`. A refusal requires `is_error=true` as well as the deny marker.
   Malformed retained usage values, including negative and non-finite values,
   produce an explicit unrecorded gap. Zero and valid nonnegative numeric
   values retain their existing meaning. An
   unreadable Claude candidate is discovered using the store's encoding
   (every `/` and `.` in the repo path replaced by `-`) and appended after the
   `--top` measured sessions with `kind=gap`, its file-stem session id, and
   repo/window/turns/avg_context/refusals all `unrecorded`; it is not counted
   as a known session.
7. **JSON is the same truth**: `--format json` emits one object with
   `stamp`, `cost`, `results` (report) or `stamp`, `sessions`,
   `signals` (waste); every plain-format figure appears in it, and
   nothing appears in JSON that plain omits.
8. **Exit codes**: 0 on success including empty windows (an empty
   window prints zeros for results and `sessions=0` per harness); 2
   on unusable arguments (malformed ISO, until <= since, unknown
   format) or missing configured `CLAUDE_DIR`; stderr carries the reason,
   with the missing key using the `conf-key` refusal class.

## Reading it

- A PR that took three review rounds and a fraction of a session's
  tokens, and landed with its findings pinned, was cheap. A refuted
  finding that consumed a round is the trigger to inspect, not a
  number to hide. Marginal cost against marginal utility, per
  decision — not totals against feelings.
- `waste` output feeds the token-thrift checklist
  (`ops/process/token-thrift.md`): each signal names the transcript
  to open and the discipline that would have prevented it.
