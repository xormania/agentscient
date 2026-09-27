# Handoff — 2026-09-11, after the close-out and the six skills

Record by Claude Fable 5.1 on `records/closeout-skills-20260911`, cut
from dev `d410fb2`. See the
[AAR](../AAR-2026-09-11-closeout-skills.md). Re-measure before acting on
anything below.

## Where things stand

- dev `d410fb2` contains master. Merged this session, in order: #131,
  #132, #133, #130, #134, #135, #136. Zero open PRs.
- Six skill pages under `.claude/skills/`: `tdd`, `close`, `measure`,
  `refused`, `dead-dispatch`, `deliverable`. Registry synced: 22
  skills on disk, 22 rows. Every hook refusal now logs a miss against
  the page it names; the registry holds one (deliberate) miss against
  `refused` and one use of `close`.
- The deliverable lock is cleared when this record lands. Set it before
  any new work: `python3 ops/conductor/tools/deliverable.py set
  BRANCH... --why TEXT`.
- No open grants once 142 settles. Grants 138 to 142 are this
  session's, all by hand at the owner's word.
- The watchdog still runs from `../wt/ag-deliverable-lock-20260911`
  (pid 379354, 13 h at hand-off); restart it from the main checkout
  when convenient, since #126 has been on dev all day.
- Ladders fd103b and 307788 read `stopped withheld` on dev, complete;
  no record on dev reads `launched`; no finding on a 2026-09-11 record
  is open.
- Worktrees this session created, all clean and pushed:
  `../wt/ag-gate-closeout-20260911`, `ag-aar-20260911`,
  `ag-skills-20260911`, `ag-hook-miss-log-20260911`,
  `ag-hook-test-isolation-20260911`, `ag-closeout-skills-20260911`.
  The main checkout is on dev, level with origin.

## Corrections to retain

- **The registry gate runs each row from an empty directory**, so a
  refusal class that needs a readable record (`correction`) cannot be
  a registry row; contract item 10 is met by the module's hermetic
  rows. Read the gate before calling an item unmet.
- **A `..` spelling under the jobs root is refused** (class `input`)
  and the correction classifier collapses the path lexically (#133).
- **A test that runs a refusing hook must isolate HOME** (LD-22): since
  #135 a refusal writes to the registry under HOME. `test_matrix.py`
  and `test_miss_log.py` do; `test_no_subagents.py` now does.
- **The Write and Edit tools cannot carry a grant.** A granted hand
  change goes through Bash with `HAND_GRANT=<id>` as the first token.
- **Check a new telemetry's first live reading against the expected
  count.** Thirteen where one was expected was the whole finding.
- **The owner's word on the process outranks the process page for that
  work.** When told the process is broken, do the work by hand and say
  in the record that the second producer is absent.

## Open, in the ledger, not started

- LD-21: `test_worth_claude_usage_currency.py` matches a planted number
  against the serialized report with its timestamps; flakes once a
  minute at the matching second. Repair pending.
- LD-20 candidate: the ladder's `pr` stage cannot adopt a PR already
  open for its branch.
- The ladder's leak heuristic (`withheld`) stops on audit envelopes
  that name the implementation record; both slice ladders ended there.
- 567 of 765 findings open; 86 grants settled unverified. Standing debt,
  not this session's.
- The skills' effect: unmeasured until sessions have run under them.

## Next thread

Owner, earlier on 2026-09-11 (previous handoff): "we'll probably tackle
e2e next session - i just need to trust this enough first." The
fixture (I-020) and the monitor work order (I-021) follow, then item
31's ladder. Start by naming the deliverable and setting the lock; the
`deliverable` page is the checklist. Every refusal met on the way is
now counted; `skills.py report` after that session is the first
reading of whether the pages are followed.

## Retrieval

```sh
git show records/closeout-skills-20260911:ops/conductor/AAR-2026-09-11-closeout-skills.md
git show records/closeout-skills-20260911:ops/conductor/handoff/HANDOFF-2026-09-11-closeout-skills.md
```

Left behind on purpose: the session transcript and the scratchpad
(the edit scripts for grants 138 to 142, the dot-dot fixture).
