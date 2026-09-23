# I-035 — the coordinator drafts and offers; the lead orders and receives only the XO's reports

- recorded: 2026-09-22, the slice-1 run of the multi-harness integration
  plan, by the XO (Claude Opus 5.5 (1M context), PT-21 coordinator,
  lane/session-20260922-3227) at the Lead's order (agentscient-d8, PT-20)
- source: owner, verbatim below, relayed by the Lead; this session did not
  hear the words directly
- disposition: open; proposed to the register as D-COMMAND-2; built after
  slice 1, not before

## In the owner's words

> "keep your context limited to big picture - use XO"

> "have XO do it - you just command"

> "you do it then - but we need to change that - You should only be receiving reports from XO and issuing orders"

## What was heard

The XO's reading: the Lead holds the mission and the orders; the XO
holds the board and moves the work, including the assignment rows that
dispatches run under. The Lead should not be a relay for commands the
XO can run. The change the Lead asked for is to let the coordinator
draft and offer assignments in `coordination.py`, leaving grant,
revoke, role recovery and acceptance with the lead.

Measured on writing, the code already permits most of it. The gap is in
the page, the practice and the tests, not in the verbs.

## Standing facts it must reconcile with

Measured 2026-09-22 at dev `f81be8f1`, reading
`ops/conductor/tools/coordination.py` and mapping each role check to its
verb (`awk '/^def /{fn=$2} /require_role\(part/{print NR": "fn}'`):

| verb | line | roles |
|---|---|---|
| grant | 853 | lead |
| revoke | 968 | lead |
| bind-for | 1012, 1021 | dispatcher; lead for roles above worker |
| draft | 1080 | lead, coordinator |
| offer | 1096 | lead, coordinator |
| hand-back (release, reassign) | 1140 | lead, coordinator |
| verify, return | 1226, 1265 | verifier, lead |
| accept | 1332 | lead |
| reopen | 1358 | lead, coordinator |
| supersede | 1386 | lead, coordinator |
| decide | 1658 | lead |

Live readings the same evening: `coordination.py offer A-477 --to PT-25
--generation 1` and `offer A-482 --to PT-26 --generation 1`, run from
PT-21 (worker,coordinator), each exit 0 ("offered A-477 to PT-25",
"offered A-482 to PT-26").

Today's lead-gated commands that went through the Lead: six drafts
(A-477 to A-481, the five slice-1 stages, then A-482, the security audit
of wall PR #268), each drafted by PT-20. None of them needed the lead:
draft admits the coordinator. The XO sent the Lead the A-482 draft
command ready to run, under the order to relay drafts, before this was
measured. One role grant (`grant PT-21 --roles lead`) was attempted by
the Lead and refused by its own session's permission classifier; it
went to the owner and is not part of this proposal.

What does not yet match the code:

- `ops/conductor/command-structure.md` says the Lead drafts assignments
  and the Coordinator offers them ("Assignments (A-n) are drafted by the
  Lead, offered by the Coordinator"), and its chain table gives the Lead
  "assignments (A-n) drafted and accepted from the brief".
- `ops/conductor/tests/test_coordination.py` has
  `test_a_worker_may_not_offer` (line 295) and
  `test_a_worker_may_not_revoke_a_lead` (line 1915). No row proves a
  coordinator may draft or offer, and none proves a worker may not draft.
  A change to the role tuple at line 1080 would pass the suite unseen.

## What is proposed

1. Register row D-COMMAND-2, for the owner to ratify: the coordinator
   drafts, offers, reopens, supersedes and hands back assignments; the
   lead keeps grant, revoke, role recovery, acceptance and decisions;
   the lead issues orders and receives only the XO's board and choices
   between outcomes.
2. `command-structure.md`: the Lead's row loses drafting and the XO's
   row gains it, citing D-COMMAND-2 once ratified.
3. Tests in `ops/conductor/tests/test_coordination.py`, written by a
   producer other than the one who changes the page: a coordinator
   drafts and offers (exit 0, the row's state and holder read back); a
   worker's draft refuses class `role` on the wire; a coordinator's
   grant refuses. Each row carries its origin, this idea, and plants
   the fault of dropping "coordinator" from line 1080's tuple.

No verb changes. If the owner wants acceptance with the coordinator as
well, that is a code change at line 1332 and a separate row.
