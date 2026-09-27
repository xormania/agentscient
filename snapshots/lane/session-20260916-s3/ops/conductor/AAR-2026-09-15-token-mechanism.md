# AAR 2026-09-15: the token-spend mechanism, after the levers

Written by the support session (Claude Sonnet 5, agentscient-4c; later on
lane/session-20260915-i for the Grok dispatch), committed by Fable,
readings dispatched to Fable (agentscient-11, lane/session-20260915-e)
and Opus (agentscient-1c, lane/session-20260915-f) across T-62. Owner's
words, carried in the lock (`deliverable.py show` at bbdcc651): "Let's
start with the token optimization and efficiency efforts - can we make
this system more token efficient?" Every number names its command and
sha; absence says so.

## The readings, in order

1. **T-56 vs. after-b95aac46 window comparison.** `worth.py waste --repo .
   --since <S> --until <U> --format json` at bbdcc651: mean context/
   session 378,439 (3 sessions) → 203,806 (5), lever 1 met later.
   Dispatches (codex+grok) 89→0, so requests-per-PR's fall 4.24→0 is not
   a clean comparison (no author-tests/review ran later). `worth.py
   report`: 21 PRs landed first window, 4 the second.
2. **LD-45.** The same call's `stamp.sessions.claude` read 8 while
   `sessions` listed 5. Filed via `ledger.py add defects` (e9fa003e).
3. **Top 10 author-tests dispatches by cached tokens**, T-56 window
   (`.dev/records/dispatches/<id>.json` `.brief` + `waste` rows): 9 codex
   (gpt-5.6-sol) + 1 grok, cached 7.37M–12.57M, scope text 423–627B each
   — scope size does not track spend. `jobs.json`'s template sha256 at
   launch (26aae8b0bef2…) no longer matches disk (9f235d55…) — template
   byte size at launch is UNREACHABLE.
4. **LD-46.** `jobs.json` `.caps` at bbdcc651: author-tests
   `{"timeout":1800,"turns":200}`, adversarial-review
   `{"timeout":1800,"turns":150}`, adjudicate has no `caps` key.
   `messages` on the 87 author-tests dispatches: min 200, median 351,
   mean 382.1, max 786 — at face value, 60/87 exceed 200. Filed via
   `ledger.py add defects` (098e2540). `git log`: the cap was untouched
   by the last edit to the author-tests entry (abf766b5, which only
   trimmed a dated figure from the prompt).
5. **Correction: `messages` is not `turns`.** From `usage.py`/`worth.py`:
   claude's `messages`/`turns` are both unique assistant-message ids
   carrying `usage` (1:1, confirmed). Codex's `codex_sessions` counts
   every raw JSONL line, no type filter — several fire per completion,
   overstating turns. Grok's `grok_sessions` takes `num_messages` from
   the harness's own opaque `summary.json`. LD-46's 60/87 is an
   overstatement; LD-46 is append-only and uncorrected — this AAR
   carries the correction.
6. **Per-harness baseline, same 87:** codex n=44, median messages 398.5,
   cached 4,627,584, 43/44 over 200 raw; grok n=43, median messages 313,
   cached 3,206,528, 43/43 over 200; claude n=0.
7. **True turns, top 10.** codex: `event_msg`/`token_count` entries per
   rollout (one per completion) — range 71–98, all under cap. grok
   (c14b8c): no rollout file; `updates.jsonl`'s `turn_completed` count = 1
   for the whole dispatch (159 `tool_call` + 318 `tool_call_update` + 71
   `agent_thought_chunk` sit inside that one harness-native "turn") — a
   structural mismatch with codex's per-step counting. **No dispatch in
   the top 10 exceeds 200 true turns.**
8. **Context-growth breakdown, 34dc59 and 0353f2** (heaviest codex runs):
   joined each `custom_tool_call` to its `custom_tool_call_output` by
   `call_id`, grouped bytes by first shell word/`mcp:<tool>`. 34dc59:
   context 21,158→12,757,814 (cached 11,136→12,573,184) over 97 calls /
   481,259 bytes; top groups `sed` 349,370B/14, `git` 37,945B/8,
   `python3 -m` 25,824B/18; largest a `sed -n` full-file dump, 40,156B.
   0353f2: context 20,698→8,910,551 (cached 11,136→8,718,464) over 79
   calls / 399,500 bytes; top groups `cat` 169,825B/9, `sed` 81,247B/6,
   `rg` 61,461B/6; largest a `cat` of the law docs under docs/, 40,157B — both
   spend most bytes re-reading whole files, not the MCP tools.
9. **Clip estimate, same two runs.** Model: each call's output bytes ride
   into every later turn's resent context (codex's `token_count` is
   cumulative); triangular estimate = Σ(bytes_i/4 × turns-remaining),
   calibrated against measured growth for a residual (non-tool-output
   growth) clipping cannot touch. 34dc59: residual 3,851,575 of 12,736,656
   growth; est. final input N=8,192→7,459,598, 16,384→9,803,872,
   32,768→12,152,040. 0353f2: residual 2,912,502 of 8,889,853; est.
   8,192→5,819,652, 16,384→7,928,776, 32,768→8,777,549. Calls over
   16,384B: 11 in 34dc59 (all `sed`/`git`); 13 in 0353f2, including
   `git diff` (17,604B), `git log -8` (23,180B), `mcp:lane_jobs`
   (17,024B) — a blanket clip also cuts git and MCP output.
10. **Session-side, two heaviest Claude sessions** (44f9de58, 836a47fd,
    `~/.claude/projects/.../<id>.jsonl`), same triangular model,
    calibrated against the sum of every turn's context (worth.py's
    `total`). Tool-result bytes 1,050,433/529,651 against measured totals
    270,540,483/138,786,384 — under 0.4% raw; full resend explains only
    34.3%/19.1% of growth, residual 65.7%/80.9%. Fixed prefix (first-turn
    context): 48,697 and 48,540 — within 157 tokens. Est. total N=8,192:
    262,951,973 (2.8% saved)/136,739,800 (1.5%); N=16,384: 0.7%/0.2%.
11. **LD-47**, found by Opus under grant 248, not measured by this
    session: the wall-write guard judges command text (refuses a `git
    checkout` under the grant) but let a `python3` script rewrite
    `jobs.json` with `Path.write_text` a minute earlier under the same
    grant — file left modified, unstaged, no authority behind it.

12. **Lever 2, closed on the launcher side** (Opus, agentscient-1c, at
    bbdcc651): codex exec runs its shell inside its own sandbox;
    launch.py plants nothing on PATH (`custom_tool_call`/`exec_command`/
    `shell_call` grep-count 0 in launch.py); only backstop is `wires.py`
    `CAP_OUT = 500_000` total; codex-cli 0.154.0 has no limit/truncate
    flag. A planted shell shim is dead: `strings -a` on the static-pie
    binary shows `/bin/sh`/`/bin/bash` compiled in by absolute path next
    to `exec_policy.rs`, with `bash -lc`/`sh -c`/`SHELL`/`default_shell`
    all 0. `caps.output_bytes` is dropped outright, not a dead field —
    what's left of lever 2 is the tests-job prompt (wall work): law
    loaded once, scope files read in ranges, a test run's tail only.

13. **PR #231 merged at 18ee9849** (worth compare, `worth.md` item 9 first):
    12 red then 12 green, 242 in the zone, two corpus rows earned
    (P-TOKENS-20260916-compare-row, P-TOKENS-20260916-baseline-nearmiss),
    310 rows passing. Both baseline pairs from Opus (1c), sent to Fable:
    corrected baseline [2026-09-15T00:00Z,2026-09-16T00:25Z) against
    [2026-09-16T02:00Z,03:00Z) — context met 426,037 (n=3) → 168,048
    (n=5); refusals met 10.0 → 4.0; landed met 5.235 (n=17) → 0.0 (n=1),
    **not a win** (LD-54: the numerator is empty); dispatch-cached
    UNREACHABLE, n=0. A second pair from 23:00Z: context 295,986 (n=4) →
    166,248 (n=5) — already under threshold before anything changed,
    because the 431k/573k sessions (readings 1, 10) sat outside that
    window. Window choice alone can make lever 1 look met.

## The mechanism

Codex's per-run spend is not a turns problem (all ten heaviest runs stay
under the 200 cap) — it is per-turn context: a ~21k fixed prefix, then
whole-file rereads (`sed`, `cat`, `git log`/`diff`) compound across
71–98 turns since codex's token accounting is cumulative, carrying every
prior turn's tool output into every later turn. Claude sessions run the
opposite shape: tool-result bytes are under 0.4% of billed total; the
66–81% residual a byte clip cannot touch, plus a ~48.6k shared fixed
prefix, points at the system prompt/conversation text as the driver.
**Per-harness cap mechanism** (Opus, agentscient-1c, at bbdcc651, launch.py):

| harness | how the cap travels | proof |
|---|---|---|
| claude | `--max-turns N` on the command line | `_turns_argv`, launch.py:844-851 |
| grok | `--max-turns N` on the command line | same; the live argv of 20260915T053520Z-tests-grok-c14b8c ends `--prompt-file … --max-turns 200` |
| codex | nowhere: argv `[]`, a note recorded instead | `_turns_argv` returns `[]`; every 20260915T06* record carries `turns=200 argv=[] note="codex offers no turn-cap flag (measured 2026-09-12)"` |
| agy | nowhere: same `[]` branch, unexercised | `_turns_argv`, same lines |

Resolution order (`_resolve_turns`, launch.py:863): `DISPATCH_TURNS` env,
else `caps.turns`, else none — recorded via `turns_source` whether or
not a flag carries it, so codex reads capped when nothing capped it.
Four jobs declare no `caps` key: verify, sweep, plan, adjudicate.

## Decisions (by Fable, on these numbers) and defects filed

8,192 bytes as the lane's clip default (reading 9). Caps 150/150/150/200
and a 900s timeout as wall work (per-job detail is Fable's/Opus's to
cite). No session-side clip hook: reading 10 shows at most 2.8% savings
at 8,192 — not enough to justify wall work. `caps.output_bytes` is
dropped outright (reading 12), not queued. Wall slice (caps on the four
uncapped jobs, the brief line, LD-47) to the wall session, agentscient [48b89b], session -h.
LD-45 (session-count stamp disagrees with its list, e9fa003e). LD-46
(turn cap does not bind — filed as 60/87 raw `messages`; corrected
above: true turns stay under cap at 71–98; LD-46 unedited, append-only).
LD-47 (reading 11, f59c418f). Owner, 2026-09-15, on T-68's connectors:
"Decision 2 - disconnect them - they're stupid and shoudn't be there" —
the five claude.ai connectors (Gmail, Google Calendar, Google Drive,
Docusign, Hugging Face; 56 tool names in every request, none ever
called, per Opus's reading in AAR-2026-09-15-token-levers.md) were
disconnected by the owner's hand in claude.ai. After reading (harness
notice in session agentscient-11, 2026-09-16T02:42Z): 54 deferred tools
withdrawn — Gmail 29, Google Calendar 9, Google Drive 11, Hugging Face
5. Docusign's 2 tools remain connected, staying until the owner
disconnects it too. Owner, 2026-09-15, after that disconnect: "i also
disabled dumb tools via mcp" — which servers/tools is not measured from
this session; no harness notice reached agentscient-11 for it by
02:50Z. The reading is the deferred tool list at the next session's
start against tonight's 94, minus the 54 already withdrawn.

## Where it stands now (Fable, at close of the first read)

PR #230 (lane/session-20260915-f) merged into dev 2026-09-16T02:47:09Z,
merge commit f9e48c35, origin/dev bbdcc651..f9e48c35: `caps.turns_applied`
beside `turns_argv` in the dispatch record (true for claude/grok, false
for codex/agy), the turn budget in every worker's brief, two corpus rows
(a serve on `turns_applied`, a nearmiss on "turns 200 so codex was
capped"), 308 rows passing at 420025b2. Before: every codex record in
the T-56 window said `turns=200` with an empty argv. After: the record
now says `applied` false for codex, proven by the corpus rows, not yet
by a live dispatch — a reporting fix, not a spend lever, per the PR body.
Small fixes on lane/session-20260915-g (Opus, agentscient-61): LD-45 at
c04bd730 (`waste` prints `listed=N` beside the window count; equalising
the two counts was the wrong repair). LD-44/T-63 at 7c8c16a6 (`usage.py
--repo .` from the main checkout printed nothing and that silence read
as an answer; not touched by abf766b5, which only fixed `worth.py`).
Queued: T-71, LD-48, identity precedence, cwd-under-repo comparison.
New defects: LD-48 at 8bfd7706 (the onboard brief reads lock contention
under five sessions as an unavailable lock, the wall session, agentscient [48b89b]). LD-49 at
6fd0ba3b on lane/session-20260915-e (agentscient-1c): the lock records
`by` only at the lock level, and `add` overwrites it, so `show` cannot
say who added a given branch target.
Provenance in flight: `settings.local.json` binds `WF_AGENT` to Fable's
name for every session; two of agentscient-61's writes went out under it
before an explicit override — commit trailers were always the writer's
own. Owner, 2026-09-15: "WF_AGENT - i don't like static binding - it
needs to be something that can be overrided." Design: explicit
`WF_AGENT` wins, else a per-session identity in state.db, else refuse;
the SessionStart hook that writes it is wall work. Grant 248 ran at a
default ttl of 30 minutes, succeeded by grant 249 at 12 hours. This
session's own shape — Fable at low context, four support sessions
measuring — is offered as lever 2's first live session-side test.

## Wall branch (#232) and defects/ideas since the last fold

PR #232, draft: caps at 131ff893, brief lines at c6c01085; item 1 green
uncommitted behind a harness denial; items 4 and 5 wait on the owner's
words in that terminal; item 6 is the laneconf line. Small fixes: fix 3
at 06cff0dc (`set` dropped unnamed branches; per-target `by`/`at`), fix
4 at 96025d77 (the lock line's `TIMED_OUT`/`UNREACHABLE`), fix 5's first
commit (the session reader, `CLAUDE_CODE_SESSION_ID`).

New defects: LD-51 (`worth.py`'s `landed` walks the main checkout's
HEAD, 549499a6). LD-52 (the wall row's isolation half is blind to a
script naming its target inside the file, 1cd03905). LD-53 (two ideas
share I-029, 3ca84d0b). LD-54 (fc15d528: an empty numerator reads
`met` — reading 13 above). LD-55 (fc15d528: laneconf's scanner misses
an indirect read). LD-56 (8e468654: a session in a worktree is
invisible to the spend report — Opus (61) at f9e48c35 measured 33
sessions matching the repo path, 0 under it, 2 worktrees dropped, 208
elsewhere; the compare window's n=5 above undercounts by the worktree
sessions and the after figures carry that caveat until fix 9 lands).
New ideas, both in the owner's own words: I-030 (9b92f8b1, Fable issues
grants on the owner's ok in the master session); I-031 (824549b7, the
cheap session as dispatcher).

## Grok keepalive decision

Record `20260916T030018Z-review-grok-df544a` (sweep, grok-4.6) running
since 2026-09-16T03:00:18Z on lane/session-20260915-i; the first launch
attempt refused pre-mint at 24.3h credential age (reading above: 24h
guard, ~30.1h measured death, 6h access-token `expires_at`, implicit
renewal on use, no CLI refresh subcommand). Owner, 2026-09-15: "grok
done - but this is third day in a row - do i have to do this every
day?" Decision: a keepalive lever running every 12h, Opus (1c) job 3.

## What is not measured

Whether grok honours the `--max-turns` flag on its argv (reading 7: its
"turn" concept doesn't decompose like codex's). The composition of the
66–81% Claude-session residual — system prompt vs. reasoning vs.
cache-miss resend. Whether `autoCompactWindow` is honoured live — open
from the prior AAR (token-levers.md), not re-measured here.

## After readings
T-62 lever thresholds, filled in against the next comparison window:

| lever | threshold | before | after | met/short |
|---|---|---|---|---|
| 1 mean context/session | under 300k | 426,037.58 (n=3) | 168,048 (n=5) | met |
| 2a refusals/session | falling | 10.0 | 4.0 | met |
| 2b requests/landed-PR | falling | 5.235 (n=17) | 0.0 (n=1) | **not a win** — LD-54, empty numerator |
| 3 cached/author-tests dispatch | under 3M | — | UNREACHABLE (n=0) | no dispatch ran in-window |

The lock's `lane/session-20260915-e` target runs this same compare
(`worth.py` against the main checkout) and read, at 2026-09-16T03:06Z:
context `baseline=426037.58 n=3 window=182839.43 n=5` — met, the first
half of the deliverable's `until`; this AAR landing on dev is the second
half, per the lock's own text.
The live dispatch that would measure lever 3 against a bound cap waits
on the wall session's brief change (reading 12: the tests-job prompt),
so one dispatch measures both `turns_applied` live and cached-per-run
together, rather than two separate runs.

## The Grok sweep on WF_AGENT (added by Fable after the record closed)

Owner, 2026-09-16: "WF_AGENT is a derilect - can you dispatch grok 4.6
to investigate history of it, and potential side-effects of fucking
with it?" Dispatch 20260916T030018Z-review-grok-df544a (sweep, grok-4.6,
launched by Claude Sonnet 5 from lane/session-20260915-i at f9e48c35,
after one refusal at 24.3h credential age): status ok, verdict changes,
p1=0 p2=4 p3=1; the report is the record's `.result.envelope.findings`.

What it read, at f9e48c35: `git log -S WF_AGENT` is 173 commits; the
read path is five places (launch.py `_identity`, the post-commit and
post-checkout hooks, dispatch.sh, instrument.identity()), and the
2026-09-12 commit 780b7b1b that claimed one identity check migrated
none of the other readers. WF_AGENT's visible use is the trailer, but it
gates writes directly: launch.py refuses before mint and collect,
identity() gates ledger add, hand declare and settle, handoff writes,
deliverable add, set, remove and clear, and skills events; matrix.py
refuses a hand dispatch whose command lacks it. Not derelict: dropping
it outright stops every write in the lane. Two readers diverge from the
contract (dispatch.sh falls a malformed value through to a default; the
hooks stamp USER and never refuse): LD-58. Two tests pin the current
dispatch.sh behaviour by name and invert if the static binding is
dropped or an override is put ahead of it in dispatch.sh; the state.db
row is additive; SessionStart carries no identity today. Grok could not
read the gitignored settings file (correct: it is not in the snapshot)
and reported it absent rather than assumed. Decision (Fable): WF_AGENT
stays as the ambient identity; the override and the session row (fix 5
on lane/session-20260915-g) go ahead of it; the five readers converge on
instrument.identity() as a later fix; deleting the static binding from
the owner's settings file breaks nothing in the tree.
