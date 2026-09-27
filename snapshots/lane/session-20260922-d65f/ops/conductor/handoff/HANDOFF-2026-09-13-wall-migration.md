# Handoff — 2026-09-13, the wall migration, the explain skill, the skills against the friction, closed

Record by Claude Fable 5.1 on `lane/session-20260913-i`. §Close is the
board as measured after #194 merged (owner, 2026-09-13: "194 merged -");
the thread sections after it are the records as written. The next
session onboards fresh and re-measures before acting.

## Close, measured at `268065a3`

| what | reading |
|---|---|
| worktree `../wt/ag-session-20260913-i` | branch `lane/session-20260913-i`, fast-forwarded to dev at `268065a3`; 0 uncommitted; the close records commit is pushed with this file |
| PRs from this branch | #192 MERGED `eaf73b98` (laneconf.py and probes.py onto instrument.py, the fixture copy lists, the explain skill); #194 MERGED `268065a3` (search, handwrite, claim, the skill-use hook) — `gh pr list --state all --head lane/session-20260913-i` |
| open PRs in the repository | none (`gh pr list --state open`) at write time; the close records PR from this branch follows this commit |
| grants | 201, 202 settled unverified (prose evidence, pitfall 32); 204, 205, 208, 209 settled verified; 212 (this close) settled with this commit's sha after it exists; 211 is session -k's, open (`hand.py open`) |
| the lock | names `lane/session-20260913-i` and `lane/session-20260913-k`; this session's entry is removed with `deliverable.py remove` once this commit is pushed |
| findings | none produced by this session; `findings.py export --write` re-run at close, 807 rows, tree unchanged |
| dispatches | none run or running (`subs.py`: no dispatch snapshots) |
| ladders | none run or resumed |
| the gate | 19 migrated, 1 no-wire, 3 pending: `skills.py`, `co_doc.py`, `control.py` (placement files at `268065a3`) |
| corpus | `probes.py run` at `d413f0b5`: pass 156, fail 0, unreachable 0 |
| the registry | `skills.py report` after the merge: explain 4 uses; search, handwrite, claim 0 uses, 0 misses (new); refused 166 misses (10 this session after the reading of 156); the main checkout on dev is 16 commits behind `origin/dev` and does not carry the Skill settings row, so no hook-written use exists yet |

### Next thread

1. **The first live reading of the hook.** A session run from a checkout
   at or past `268065a3` makes one Skill call and reads
   `skills.py report`: a use whose event was written by the hook, not by
   hand, is the reading that closes "built, not consumed". The main
   checkout needs `git pull --ff-only` on dev first, by the owner or by
   whoever owns it; this session did not write there.
2. **The owner's ruling** on `skills.py`, `co_doc.py`, `control.py`
   adopting the wire; the decision brief is in the explain thread of
   this session (skills.py first, control.py second, co_doc.py's
   argument refusal along, the report format a separate decision).
3. **The measure of the three pages**: the next window's daily miss
   count against 21, 55, 94.
4. Session ids on registry events read `unknown`; per-session rates
   need `CLAUDE_SESSION_ID` in the hook's environment.


## First thread, as written at `2e7dec62`

The [AAR](../AAR-2026-09-13-wall-migration.md) carries the readings.

## Where things stand

- Commits on the branch over dev `c7245c6c` (#190): `dee2b4c9`, the two
  wall files onto `instrument.py` (grant 201, class wall); `15bea6a3`,
  their placement files to `migrated` (grant 202); `a9b79257`, the four
  fixture copy lists naming `instrument.py` beside `laneconf.py`;
  `2e7dec62`, the merge of `origin/dev` at `3014cb22` (#191); then the
  records commit carrying this file, the AAR and six corpus rows.
- PR: opened as a draft from this branch after the records commit; its
  number, head and checks are in the ready note and in `gh pr list`,
  not here. Ready waits on the full check set green on the final head,
  merge state clean, and `## Proof` naming the `P-WALL-20260913-*` rows.
- The consolidation gate at `15bea6a3`: 19 migrated, 1 no-wire
  (`lane_refs.py`), 3 pending (`skills.py`, `co_doc.py`, `control.py`).
  Nothing pending is a copy removal.
- Grants 201 and 202: settled after `cabb9d25`, but as "claimed;
  unverified": the evidence was prose with the sha inside it, and the
  lever verifies a bare object id only; a settled grant cannot be
  settled again. Pitfall 32. Grant 204 (this row and this line) is
  settled with a bare sha.
- The lock names `lane/session-20260913-i`; removed with
  `deliverable.py remove` once the PR has landed on dev, per the
  deliverable skill.
- Worktree `../wt/ag-session-20260913-i`.
- Dispatches: none run. Ladders: none. Findings: none produced.

## Second thread: search, handwrite, claim, and the skill-use hook

Owner, 2026-09-13: "hand grant ok'd for new skills #1-4 - do them in
one PR". Grants 208 and 209. Commits on the branch over `eaf73b98`
(#192): `21d50dc8`, the hook's test (wall); `85dfe597`, the three
pages, the hook, its settings row, the skills page sentence, six
corpus rows; then the records commit carrying this section.

- PR: opened as a draft after the records commit; number, head and
  checks in the ready note. Ready waits on the check set green, merge
  state clean, and `## Proof` naming the `P-SKILLS-20260913-*` rows.
- **What the next session must read first**: after the merge, the
  first Skill call in a session run from a checkout carrying the
  settings row writes an `invoked` row with agent `Claude ...` or
  `skill-use hook <skill-use@agentscient>`; `skills.py report` then
  measures uses. Until that row exists the hook is built and tested,
  not consumed (the close page's rule); name the row id when it
  appears.
- The measure of the three pages is the next window of misses:
  `sqlite3 ~/.local/state/agentscient/skills.db "select substr(ts,1,10),
  count(*) from skill_events where event='miss' group by 1"`; the
  baseline is 21, 55, 94 for the 11th, 12th, 13th.
- Session ids on events read `unknown` on all 170 rows;
  `CLAUDE_SESSION_ID` is not in the hook's environment. Per-session
  rates need it; not this thread's, named here.
- Grants 208 and 209: settled with bare shas after the records commit.

## The explain skill

Owner, 2026-09-13, after the three-tool summary: "the way you explain
something - sucks. What I need is a brief summary of the overall -
background info - then the specifics named in such a way that I can
both understand and have enough info to make a decision (you're
suggestions are welcome) - ending in something that proves you actually
verified everything"; then "its not a wish - hand grant ok'd to write
the skill `explain`". Grant 205. `.claude/skills/explain/SKILL.md`
carries the shape: background, one block per item (what it is, who
depends on it, what changes, cost, recommendation), then the proof. The
registry row `explain` is active (`skills.py sync`); the session's own
wish row `decision-brief` is retired with the reason. Every explaining
reply from here loads it first.

## Corrections to retain

- **A wall grant writes wall paths only.** The placement files and the
  records went under a second grant of class `other`, declared at the
  same word; the code and its placement flip are two commits so the
  gate is never red between them.
- **`ConfigError` is a `Refusal`.** A consumer may catch either name;
  `line(kind)` still projects under a caller's token. New consumers
  should catch `instrument.Refusal` through `conf()` and not import
  `laneconf` for its class.
- **A copied `laneconf.py` needs `instrument.py` beside it.** The
  fixture copy lists in the four app tests are copiers too; a change to
  a tool's siblings reads every list that names the tool, not only the
  suites that stage it (`suites.sh` at `15bea6a3`, four reds).
- **The handoff directory.** Records named `HANDOFF-*` live under
  `ops/conductor/handoff/`; AARs beside `ops/conductor/`.

## Next thread

The consolidation's copy removals are complete. What remains is the
owner's ruling on the three older tools, summarized for the owner this
session:

- `skills.py`, the skills registry and its telemetry: on a bad call it
  prints a usage sentence and exits 1, the Finding class (measured:
  `skills.py nonsense`), where the wire says exit 2 with
  `class: expected; found; needed`. Adopting the wire changes what
  every caller of a bad verb sees.
- `co_doc.py`, the read-only permission doctor: on a bad argument it
  prints a usage line and exits 2 without the wire line (measured:
  `co_doc.py --bad`); otherwise it collects probe lines into a report
  object and exits 0, 1 or 2 from the report's state, and its
  `[Abort] probe: expected / found, remedy` lines are a wire of their
  own, older than the shared one.
- `control.py`, the finite conductor controller: it has its own
  `Refusal` class and a `need()` helper whose defaults fill in expected
  and needed; its lines are on the wire already (measured: no
  arguments exits 2 with a `control:` line), but the class is a private
  copy the gate names, and its defaults would go.

Each is a shape change with callers to read first, not a copy removal;
a session takes one at the owner's word. Two wall items from session
-h's handoff stay open, unassigned, for a wall session: the
corpus-shape rule refusing an `expect` that spans lines (`probes.py`),
and the hook's deliverable remedy that still says `clear` (`matrix.py`,
one line).
