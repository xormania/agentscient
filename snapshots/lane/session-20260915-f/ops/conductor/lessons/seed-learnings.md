# Learnings for the framework — the conducted days, 2026-08-28 → 31

Standing: RECORD. Seed material for Agentscient, distilled from what the
conducting sessions measured and paid for, in the format
`learnings-since-loopstrap.md` proved: statement — why it matters for
the framework — source. Written now because these learnings are
session-held until written down, and compaction has already eaten one
tool this week.

---

**1. The four outcome classes survive contact everywhere they're
applied.** Rejection | Denial | Abort | Finding flowed looplaw →
`outcome.cue` → the doctor's output contract → the writ schema's
`on_fail` with zero friction, and tonight's timeout diagnosis sorted
cleanly into them (wall-kill = Abort; unmeasured = Finding).
Why: the framework's envelope `status` should BE these four, replacing
ok | invalid | tripped — already recommended, now practice-backed.
Source: looplaw-findings §1; permission-surface.md; work-orders.md §4.

**2. Runtime is a property of the job, never of the session.** The
author-tests wall-kills happened because a prior session's
`DISPATCH_TIMEOUT` compensation died with the session; the fix was caps
in `jobs.json` with a named resolution order and source.
Why: the framework rule generalizes — **no operating parameter may be
session-resident**; every knob lives in job/contract data with its
source recorded. The writ schema's `caps: {…, source}` says this;
tonight proved why.
Source: PR #98; the seven wall-kills across ~280 dispatch records.

**3. A kill must leave commits, not residue.** grok's timed-out
test-author left near-finished work recoverable only because the
launcher snapshots residuals; the brief clause "commit each file the
moment its red is proven" makes salvage unnecessary.
Why: framework job cards for write roles carry commit-early as contract
text, not as conductor folklore.
Source: record 20260901T004909Z-tests-grok-3a7479; jobs.json prompt
amendment in PR #98.

**4. The two-producer firewall works as a pipeline shape, not just a
review ideal.** Three times in one night (co_doc, job caps, the
decisions register): contract written first, implementation and tests
authored in parallel by different harnesses from the contract alone,
expected reds proven against the pre-implementation tree, all flipping
green at reconciliation with zero edits to either side.
Why: this is the framework's default pipeline for tool-sized units —
and the law design's §4.1 generalizes it with proven-blind staging.
Source: records 20260901T{004028,015943,020002}Z; tonight's register
dispatches.

**5. Operational instruments must be repo citizens.** hand.py (the
declare-before-do ledger) lived in a session scratchpad and died with
it; its database survived but the lens is gone. Same class as lesson 2:
session-scoped homes lose what process depends on.
Why: every framework instrument — ledgers, registers, doctors — lands
in-tree with a contract, or it does not exist.
Source: this session's scratchpad purge; grant 19 left unsettleable.

**6. Refusals carrying expected / found / needed as data held up under
every use.** The launcher's identity refusal named its remedy verbatim
and the relaunch was mechanical; the register contract now demands the
same shape; looplaw states the doctrine (refusals are protocol, with
the remedy part of the contract).
Why: the framework's refusal wire is a struct, not prose — class, check,
subject, reason, remedy.
Source: looplaw-findings §2; tonight's WF_AGENT refusal round-trip.

**7. There is no global lexicon — vocabulary is governed per scope, and
collisions are judged per surface.** Four traditions converge (law's
scoped Definitions, DDD bounded contexts, ISO 704 concept/term,
looplaw's two tested-disjoint lexicons); the writ/write near-miss and
the "lexicon is loaded" catch were both instances the machinery would
have gated.
Why: the framework ships scoped Definitions with per-entry `collision`,
tested disjointness between scopes, and no-coin/no-borrow lists — the
law design's Lexicon leg.
Source: defined-terms.md with its sources; I-002/I-003.

**8. Namespacing substitutes for physical separation, and a
deletability test keeps it honest.** looplaw's product provably stands
with `dev/` deleted; the same test per namespace makes the framework
permanently extraction-ready without a repo split.
Why: the framework forms in place (I-004/I-005) and its boundary
manifest + deletability check are framework artifacts, not project
chores.
Source: looplaw dev/README; I-004.

**9. Ratification is non-delegable, and recording-on-behalf requires
the principal's words.** The register's guard: a harness identity
deciding without `--evidence` refuses as self-conferred standing;
`decided_by` comes from the evidence, never the recorder.
Why: the framework's authority model in one rule — delegation is an
authority binding carried as data, not assumed by the agent signing its
own work.
Source: looplaw-findings §4; decisions-register.md.

**10. Instruments get misread under pressure — pin the reading.** "No
checks reported" was read as settled (it means *not yet reported*);
`echo rc=$?` after a pipe reports the tail's exit; a lineage worktree
left behind origin made a dispatch build on stale law.
Why: framework watchers and land levers carry their reading as code:
settled ⇔ rows>0 ∧ pending=0; exits captured un-piped; land
fast-forwards the lane or dispatches ref origin.
Source: the #91 watcher defect; the exit-swallowing handwork entries;
the stale-ref dispatch of 2026-08-31.

**11. Telemetry of absence finds the next lever.** The skills registry
tracks misses (failed potential uses) and wishes; the handwork ledger
flagged its third 'other'-class declaration as "a lever demanding to be
built" — and it was right (the caps PR).
Why: the framework treats recurring absence as a first-class demand
signal, queryable, not anecdotal.
Source: skills.py telemetry design; hand.py's recurrence note before
grant 19.

**12. Scale is bounded by the longest job, and deliberate no-cache is a
position, not a gap.** Twelve runners drained the 23-check wave in two
waves; the remaining floor is codeql; the lane's no-cache stance is
correct for stdlib suites because a cached oracle is the stale-cache
failure class inside CI.
Why: framework CI doctrine — parallelize to the longest job, cache
tools by digest, never cache oracles.
Source: the runner scale-up and caching audit, 2026-08-31/09-01.
