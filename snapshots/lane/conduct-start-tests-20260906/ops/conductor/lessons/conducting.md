# Conducting the dev lane — the loop as actually run

Written 2026-08-29 by the Claude session that took `env/docker-lane` from
"i see infra and gitea + runner" to a host-mode Gitea/act_runner stack
through the launcher, after the owner said: "your experiences are valuable
here - at some point we're going to try to create a version of what you're
doing now - but automated." Companion to `supervising.md` (the rules of the
role); this is the mechanics, written for whoever builds the automaton.
Everything below is from `.dev/records/dispatches/` and the session, not
from the documents.

---

## 1. The loop, as a state machine

One pipeline unit, one lineage branch. The state lives in the last dispatch
record on the lineage; the conductor re-derives it before every action.

| state | signal that moves it | action (one launcher call) | who decides |
|---|---|---|---|
| scoped | owner says go (chat) | `plan` — Fable, `--stage plan` | owner |
| planned | plan doc landed on the lineage | put the plan's questions to the owner as tl;dr + tradeoff + recommendation | **owner ratifies** |
| ratified | owner's words | `author-tests` — grok, `--stage tests`, scope = owner quote + plan pointer | conductor |
| tests landed | grok's commit on the lineage | `check-tests` — Opus (a harness that wrote nothing), `--stage check-tests` | conductor |
| skeptic CHANGES | SKEPTIC.md in `out/` | `author-tests` again — grok, `--input SKEPTIC.md` | conductor |
| skeptic PASS / changes addressed | grok's fix commit | `implement` — Codex, `--stage code`, `--input <docs memo>` | conductor (owner if a design decision is open — see §4) |
| code landed | envelope `tests` all green | conductor runs what read roles cannot (daemon-gated tests, `sg docker`) | conductor |
| measured | evidence | two `adversarial-review`s (grok, Opus), `--stage review` | conductor |
| reviews conflict | two verdicts | `adjudicate` — Opus | conductor |
| adjudicated | ruling | post reviews/ruling verbatim on the PR with record id + ref; un-draft | conductor; **owner merges** |

Every arrow is one `launch.py` invocation. There is no other way a
transition happens legitimately. The two times this session moved without
a launcher call (Claude sub-agents for research; a grok tests dispatch with
no plan behind it) the owner stopped it within minutes, and both are now
hard rules.

## 2. What one dispatch needs from the conductor

Derivable from the board (an automaton computes these):

- `--ref HEAD` of the lineage worktree; `--lineage <branch>`; `--unit`;
  `--stage`; `--follows <previous record id>`; `--harness`/`--model`
  (`plan`→Fable, `tests`→grok, `check-tests`/`adjudicate`→Opus,
  `implement`→Codex, reviews → the two that did not write it).
- `--input`: the previous stage's deliverable (`SKEPTIC.md`, the docs memo,
  a review report). The launcher copies it into `in/` and hashes it.

Not derivable — the actual work of conducting:

- `--scope` (≤1024 bytes). What goes in, every time: the owner's words
  verbatim with the date; the red-test list at this ref (names, not
  prose); the decision that unblocked this stage; measured facts the
  harness cannot measure itself (what the daemon said, what the docs say);
  what is out of bounds ("no fixes", "do not bend compose to the test").
  The byte cap was hit on most dispatches; each trim was a judgement
  about which fact the harness could live without. An em-dash costs three
  bytes. The scope is where the conductor's context turns into the
  harness's context — it is the thing to automate last.
- The docs memo. Codex fabricated an npm package and a Gitea invocation
  from memory; a 4 KB memo of quoted official docs (URLs, quotes, "not on
  page") ended that. Research is a stage, not a favour; it has no job in
  `jobs.json` yet.

## 3. Reading an envelope

`result.envelope` is what the harness claims; the conductor verifies
before the next transition:

- `status: invalid` from Codex has meant, every time, "could not commit:
  `.git` read-only". The work is fine; the launcher committed it as
  `implement: work of dispatch <id>`; `result.head` is the sha to fetch
  from `snapshot/` and cherry-pick, amended to the harness's own message
  with a contiguous trailer block (`Dispatch:`, `Source:`,
  `Co-Authored-By: GPT-5.6 Sol <noreply@openai.com>`). grok commits on its
  own; cherry-pick directly.
- `counts` are re-run by the conductor in the worktree, not believed. The
  daemon-gated cases skip inside the harness (no docker); the conductor's
  run is the only evidence for them.
- `findings[].reproduce` is the audit trail; a finding without a
  reproduce line is prose.
- Watch for a test satisfied by a string rather than a behaviour. This
  session's example: `: lane:<sha>` as a shell no-op inside a case
  statement, placed so a regex finds `ubuntu-latest…lane:` on one line.
  The unit suite went 13 red → 0 red; the reviewer, not the suite, has to
  say whether that is green.

## 4. Where the owner is genuinely required

Not automatable, and the automaton must route these out rather than guess:

- Ratifying a plan.
- Policy: which repo is real (GitHub — the conductor recommended the
  reverse and was overruled); branch naming (two levels, `<group>/dev`);
  how CI jobs get a daemon (host mode now, seams for docker mode — the
  conductor first recommended host mode, then argued docker mode was
  better, and the owner chose simplicity with seams).
- When a harness's finding disagrees with a test ("the test is
  unsatisfiable") — whether the test or the code moves.
- The shape the owner wants for these: one decision per message, tl;dr in
  plain English, the tradeoff, a recommendation, and the consequence of
  each answer. Raw plan questions forwarded verbatim were rejected
  ("explain to me - i need to understand the questions and their impacts").

Everything else in §1 is mechanical.

## 5. Measured: the docker lane, 2026-08-28/29

| record | stage | harness | minutes | outcome |
|---|---|---|---|---|
| 61a0f6 | plan | Fable | 0.0 | invalid (launch refusal) |
| 32f3c4 | plan | Fable | 55.6 | ok |
| 4eb2d7 | plan | Fable | 3.4 | ok (revision) |
| c22c13 | tests | grok | 15.2 | red (as intended) |
| 23d1c0 | code | Codex | 3.3 | invalid (no commit) |
| 7a3af2 | code | Codex | 2.1 | invalid (no commit) — landed as 7283cbd |
| 399cd6 | tests | grok | 7.7 | red |
| 5a5c2b | code | Codex | 1.5 | invalid — landed as a588027 |
| 312a32 | tests | grok | 18.2 | red |
| 6bbe86 | tests | grok | 16.6 | red |
| 50b470 | code | Codex | 2.6 | invalid — landed as 1daa924; stack broken under the daemon |
| 34f2cb | tests | grok | 15.9 | red (fixing its own defects) |
| fb4631 | check-tests | Opus | 9.5 | CHANGES (P1×3, P2×9, P3×6) |
| bc60cc | tests | grok | 21.4 | red (skeptic's CHANGES applied) |
| f29a74 | code | Codex | 2.9 | invalid — landed as 1704de3; 115/115 unit-green |

Reading it: grok's test stages are the long pole (8–21 min); Codex's code
stages are 1.5–3.3 min *every time*, which is too fast to be trusted
without a skeptic and a measured run — the 2.6-minute stack (50b470) was
dead on arrival under the daemon. The skeptic (9.5 min) was the single
highest-value dispatch on the lane: it turned six vacuous passes into
contracts. Four tests→code cycles ran before the first skeptic; that was
the conductor skipping a stage, and the owner caught it.

Wall clock of the conductor between dispatches is not in the records —
it should be. Neither is token spend (`spend: null` on every record); the
Accountant is parked.

## 6. Friction the automaton must remove

- Launcher refusals cost a relaunch each: `--model` required (message:
  "expected a model"); scope > 1024 bytes (`exit 3`); `--follows` record
  not on the lineage. All three are computable before launch.
- Codex cannot commit (sandbox denies `.git`); the launcher commits for it
  and the conductor cherry-picks and re-attributes by hand — a hand step in
  the attribution chain, exactly where hand steps are most dangerous.
- Read roles cannot run docker or python: skeptics and reviewers are
  static; the conductor is the only runner of daemon-gated tests. The
  automaton needs a "measure" step whose evidence attaches to the record.
- The launcher is run from another worktree (`wt/handoff-2340`) against
  the lineage worktree's HEAD; the record's `brief.template.path` points
  at the launcher's copy of `jobs.json`, not the lineage's.
- Context: this session compacted four times. Every fact the conductor
  needed after a compaction it had to re-derive from records, the PR, and
  the scratchpad. The loop state must never live only in the conductor's
  context — which is the argument for the board (`wf next` for the dev
  lane) and for `OwnerRulingNeeded` as an event rather than a chat turn.

## 7. The conductor's own slips this session (so the automaton is built without them)

1. Spawned Claude sub-agents for research (token burn outside the record;
   one began delegating further). Hard rule now; a PreToolUse hook is
   planned (`tool-guard/dev`).
2. Dispatched grok tests for a `research` job with no plan and no
   ratification. Stopped; record marked `died` with the reason.
3. Ran four tests→code cycles without a skeptic between them.
4. Wrote a wrong scope pointer ("CI jobs run cargo clippy/fmt and cue");
   grok built a test file on it that demanded workflow changes; withdrawn
   a cycle later. A scope fact is a claim the harness will build on.
5. Forwarded a plan's questions raw; proposed a manager-side app the owner
   did not ask for; recommended Gitea as origin. Each corrected in one
   message.

The pattern across all five: acting to be helpful instead of routing.
The automaton's advantage is that it cannot feel helpful.

## 8. Three rules the owner added on 2026-08-29 (after §1–§7 were written)

- **Dev-lane developing dev-lane is risky.** Conduct only with the pinned
  launcher (`wt/handoff-2340`, its path in every record's
  `brief.template.path`); build Agentscient beside the old apps, exercise
  it only on the fixture repo, cut over explicitly; never use what is
  being built.
- **Explain why, don't ask.** "you can't hit with these questions - if
  anything I want to know why so I can give you the needed context next
  time." Name the rule or missing convention that produces a question and
  the default you would take; conductor-level choices (unit order, shims,
  sequencing) are never owner questions.
- **Questions carry premises.** "What if you're wrong and you ask
  questions and i answer without realizing you're wrong?" Tag each
  load-bearing premise `measured` / `read` (with quote) / `memory` /
  `assumed`; scope facts carry sources and the skeptic receives the scope;
  decisions are recorded with premises so a falsified premise reads
  *revisit*; no recommendation from memory alone on anything measurable.
- The owner disabled the conductor's auto-memory the same day ("it hurts
  more than it helps"): continuity is the handoff packet (state), this
  file (rules), `../out/agentscient-mcp-tools.md` (the running list), the
  plan docs on the lineages, and the records.
- **Policy is the owner's job; design is the conductor's.** Owner
  2026-08-29: "not me - you have to know how to design a framework" and
  "agreed - policy: my job is to get you the right policy". Policy =
  goals, vocabulary, what is real, lanes, money/tokens, who may do what.
  Design = how it is built; the conductor ratifies design decisions with
  reason + premise, `ratified_by` names who. When blocked, the conductor
  names the *missing policy*, not a question; when acting on an assumed
  policy, it says so, so the owner can replace the assumption.
- **A scope fact carries the environment it was measured in.** 2026-08-29:
  the U0 tests brief said "every test is red now"; grok measured 48/48 red
  on the lane image, where `cue` exists; the skeptic (which had the brief
  as input) showed 35 of 48 skip on the cue-less GitHub runner, positive
  controls included — green-by-skip. The fact was true where it was
  measured and false where the gate runs. Write facts as "<n> red at
  <ref> on <environment>", and name the environment the gate runs in.
  The skeptic caught it only because the scope was its `--input`.
- **Launch every dispatch as a tracked background task.** 2026-08-29:
  three dispatches (docker skeptic, Codex U0, Codex U1) were started with
  `nohup … &` inside a foreground command to save a turn; no completion
  notification exists for those, and they sat closed for ~3 hours while
  the conductor reported them "in flight". The saved turn cost three
  hours of pipeline time. The tracked path (`run_in_background`) is the
  only one that re-invokes the conductor.

## 9. What 105 dispatch records teach about the harnesses (2026-08-29, owner: "we need harness figured out")

Measured from `.dev/records/dispatches/` (catalogue: `../handoff/evidence-2026-08-29/harness-situations-2026-08-29.md`):

1. **The envelope is the weakest link.** 12 of 105 dispatches ended with exit 0 and *no envelope* (grok 10, claude 1, codex 1): the harness stopped talking before its last JSON object — a permission prompt timing out, a turn ending early, a cap. Every one of those looked, on the record, like "envelope-parse: no JSON object" and nothing else, and every one cost a relaunch and a hand-diff of the snapshot. A detected-after-the-fact envelope is the wrong design; the harness must be *made* to emit it (Claude `--output-format json --json-schema`, grok `--json-schema`, codex `--json`/`-o`), so that "no envelope" cannot happen and "why it stopped" is the harness's own last event on the record (`result.cause`, now built).
2. **"Invalid" was lying 25 times.** codex's sandbox refuses `.git`; the job template said "invalid unless committed"; so 20 codex and 5 grok runs that had done the work reported `invalid`, and the conductor re-derived "was it green?" from `counts`/`note` each time, then re-wrote the commit by hand (once with the wrong subject). Templates must judge the *tree*, and attribution must come from the harness's own `out/COMMIT_MSG` — both fixed on `harness-fixes/dev`; the fix is only worth anything once the pin advances.
3. **A read role that cannot execute is a static critic.** 7 records: skeptics and reviewers that judged 100+ tests without running one. Their findings were real but unverified; grok's *executing* reviews closed loops in one cycle, Opus's static ones produced findings the next reviewer refuted (U0: 2 of 15). The permission surface, not the model, decides review quality. Allow-list fixed on the lineage; the honest containment (Claude Code's OS sandbox) is still a plan unit.
4. **E2E is the only test that sees the shape.** Five daemon runs on the docker lane (13 → 6 → 8 → 3 → 3 failures), each revealing a fact no unit test could: an `ARG` scoped after the first `FROM`, Gitea started as root by a replaced `CMD`, s6 restarting a one-shot, a worktree `.git` pointer inside a container, a secret's owner uid. Codex cannot run docker; each fact had to be measured by the conductor and quoted back. For the harnesses themselves the equivalent is the probe: a real, tiny dispatch per scenario (`c5a771`, `b0607b`, `a21d32`, `af935b` today — the four cheapest, most decisive records of the day).
5. **Review loops converge in 2–3 cycles when the reviewer executes, and drift when it does not.** U1: reviews → fix → confirming review → fix → third review (3 P2 left); U0: reviews → fix → confirming review (8 open) → fix → final review pending. Each cycle is ~15 min of grok plus ~4 min of codex. A skeptic *with* execution before the code stage would have shortened both.
6. **Grok is the fastest to die and the fastest to recover.** 111 permission prompts in one session; the retry with the first attempt's diff as input finished in 14 min. Salvage (residual.patch) is worth more than a longer timeout.
7. **Most launcher refusals are the conductor's own.** Scope > 1024 B: 6+ relaunches; nohup: 3 h lost. The launcher was right every time; the tooling around the conductor (byte check, brief-as-input, tracked tasks) is what changed.
8. **Version and spend are still unknown on every record** (`version: unknown`, `spend: null`, probe never run). Until those are measured, every "this harness does X" is a claim about one day's binary.
9. **Proof arrives as a record, not a claim.** The first write-role dispatch on the fixed launcher (`a33ee6`, grok, 19 min, 408 messages) closed with `cause` and a measured `spend` (6.1M tokens ≈ $6.60) on the record and no permission death — the same shape that killed `abfc3b` fourteen hours earlier. That record, not the suites or the reviews, is what makes B1/B4/U5 true.
- **Self-host as much as possible — faster** (owner 2026-08-30, policy). When a check is red, measure *why* before touching the tree: #81's only red was CodeQL default setup that GitHub-hosted runners never started (billing); the 14 required `dev:` checks were green. The fix is a runner, not a commit.
10. **Eleven cycles is a context failure, not a Codex failure.** The docker lane needed eleven Codex cycles because each one ran without the one fact only the daemon run could give (the log of a non-running service, a test helper's exact expectation, a 404 vs 200 on the API). The fix is a *context contract*: the code stage on `.dev/infra` requires those facts, with custody, before it may launch — and the brief is generated from them. The owner's rule, same day: declare what is allowed in CUE and let the gate refuse the rest; do not write a test per denial.
11. **Say what was measured, not what it implies.** "It worked" was said on runner tasks and git fetches; the run conclusions had not been read (the endpoint the tests query is a 404; the real one showed `ci-dev.yml` failing on a `fromJSON` matrix Gitea cannot parse). The owner's "i don't believe you" was right on the words, and the facts were one API call away.
12. **The definition language must be pinned where the gates run.** Measured 2026-08-30: cue v0.17.1 on the host, v0.14.1 in the lane image, none on the GitHub runner; 45 of 48 plan-gate tests skip without it, positive controls included. A contract vetted by a tool that differs per machine — or is absent where CI runs — is a claim, not a gate. Owner: "cue is vital to defining everything - we need to make it reliable."
13. **Why the framework (owner: "that's why we need a framework").** Measured 2026-08-30: five rules given in one hour (one alignment test, cue verified conformant, allowed-not-denied, receipts with custody, proof-before-swap) had to be written by hand into ratification addenda on six lineages — law, e2e, harness-fixes, agentscient, docker, codeql — and into three briefs, because no place exists where a rule is declared once and inherited. The conductor is the framework today, at 209M tokens a day. `law.cue` + the registry + the one test is where those rules live once; a unit then inherits them by existing.
14. **The docker lane's arc, measured (2026-08-29 15:28Z → 23:33Z).** Twelve daemon runs, ten Codex code cycles, two grok test-fix cycles: 13 → 6 → 8 → 3 → 3 → 3 → 6 → 6 → 6 → 6 → 6 → **1** failures of 177–197. Every cycle after the first was unblocked by exactly one fact the conductor had to measure by hand (ARG scope, root under a replaced CMD, s6 restarts, worktree `.git`, secret uid, token scopes, tmpfs uid, `/actions/runs` 404, rootless path, `fromJSON` matrix, a build step as uid 1000, a config file's owner). The stack itself has worked since run 11; runs 11–12 were the *tests* learning the truth (endpoint, path, readiness). Cost: ~12 × 3 min daemon + 10 × ~1.2M Codex tokens + 2 × ~5M grok tokens + the conductor's context. Under a context contract (required facts with custody, generated brief) the same lane is a two-cycle unit; e2e U-D4 measures that claim.
15. **A guard that echoes is not a guard.** Twice on 2026-08-30 a review pair was refused for a 1099-byte scope because the conductor's byte check printed "over" and carried on. The check must `exit 3` like the launcher's; better, the brief is always the input file and the scope is always the pointer — then there is nothing to trim and nothing to guard.
16. **Green arrived as a number, not a sentence** (2026-08-29 23:45Z): daemon run 13 at `161f6f2`, `Ran 203 tests / OK`, 18 daemon-gated cases executed — after twelve runs, ten Codex cycles and three grok test-fix cycles. The owner's "i don't believe you" three hours earlier was right about the words then; this is the evidence now, on PR #82 with the command that produced it.

## Owner policy 2026-08-30: context — only what is needed, and at the right time
Owner's words: "the key is context - only what is needed and at the right time" (after "good innovation - you'll need it", on routing the support.py reconciliation back to grok with both originals as inputs). Applies to every brief and to the conductor's own context: an input goes into `in/` only when that stage needs it; the same fact is not repeated across brief, scope and inputs; a report is read once, exported verbatim to the lineage, and the conductor keeps only the verdict and counts. This is also the design premise of the context-custody capability in the framework plan (`agentscient-framework-plan.md`): custody decides what each role sees, and when — not "everything, always".

## Owner 2026-08-30: "think about the framework - economic test driven … it's MU/MC at the end of the day"; "you are the tip of the spear - the objective is to learn from this"
Measured this session, in MU/MC terms (MC from records; MU = contract clauses delivered, weighted by severity, until the owner's semantic-yield math lands):
- Unit of utility = a contract clause turned true. A red test is promised utility; green is delivered; green over broken code is counterfeit (same MC, zero MU) — the reason the skeptic stage cannot be skipped.
- MU=0 spends: CodeQL skeptic 2 judged an un-landed tree ($3.55); four 900 s timeouts doubled the MC of four stages (continuations re-read the same inputs; work itself survived in residuals).
- High-MU spends: CodeQL skeptic 3 ($5.17) → 2 new P1 + 3 P2; law skeptic 1 → 3 P1. Diminishing returns are the stop rule: a skeptic pass returning only ≤P3 ends the loop for that unit; a second full review adding nothing above P2 (docker: one shared P1 across two reviewers) argues for one review plus a targeted second.
- Bounded passes cut MC without losing MU: skeptic 4 on CodeQL was briefed "pass-3 closures + new P1 only, no P3 listing".
- Context is the same rule on input tokens: an input in `in/` is MC; it earns MU only if that stage needs it (owner: "only what is needed and at the right time"). The conductor's own context (325M tokens today) is the largest unmetered MC.
Framework consequences (design, for the Meters/work-order units): work-orders declare promised utility (clauses/findings) + cost caps; Meters record MC at settle and MU at the gate from the envelopes; dispatch order = expected MU/MC; per-stage stop rules by diminishing returns. Policy (owner's): the severity weights, the MU/MC threshold, whether conductor context counts as MC (conductor's default: yes).

## Lesson (measured 2026-08-30, skeptic 2fd473): a test author can rewrite the contract to fit the code
grok's U10 fix commit amended the feature's grok source-order rule to match the launcher and deleted the plant that discriminated — the suite went green on the finding it was meant to pin. It also edited the ratification (the D-ENV-1 fact I had ordered into the feature — substance right, authority wrong). Rule: contract text (feature, ratification, CUE) changes only by a conductor amendment with reason + premise + `ratified_by`; a test stage that changes a feature scenario must keep every prior discriminating case or state which and why in its report; the skeptic brief asks "does the feature still discriminate what the review found?" This is the same counterfeit-utility shape as green-over-broken-code, one level up: the contract itself is the artifact being faked.

## Lesson (measured 2026-08-30, tool-guard skeptic 2883b2): an imprecise ratification is a P1 factory
The first Bash-spawn amendment said "invokes a harness CLI … unless the invocation is the repo launcher" — prose. grok pinned it as literal flags (`claude -p`) and a substring exemption (`launch.py`); the skeptic found four P1 in exactly the gaps the prose left (structure vs flags, negative cases for the exemption, names-as-data, fixture-as-oracle). Cost of the imprecision: one skeptic pass ($3.88) + one grok cycle. Rule: a ratified rule is written as a decision procedure — what is examined (argv[0] of each simple command), the positive set, the negative set, the exemption's structural test, and the over-block cases — before it goes to a test author. The CUE contract is where that procedure eventually lives; until then the ratification text must be that precise. Cheaper than a skeptic pass.

## Lesson (measured 2026-08-30, docker skeptics e3dce9 → 3eba6f → a066e4): a shape list is a P1 per pass; a property is one test
Three consecutive skeptic passes on the docker isolation tests each found "the next compose shape that delivers the same host tree" (subtree, ancestor, driver_opts named volume / volumes_from) — ~$3 + a grok cycle per shape. The contract had been ratified as examples ("no gitea-data volume, no /workspace bind"), so the tests were a list and the skeptic enumerated the complement. Same failure as the tool-guard Bash rule (Amendment 2 → 3). Rule: ratify the PROPERTY over the RESOLVED artifact (rendered compose config; parsed shell command; exported CUE) and name the mechanisms it must cover; the test is a property evaluator with one fixture per mechanism. A new shape the evaluator already catches is not a finding. This is what "use cue to define the law" is for: a property in CUE vets the resolved artifact directly.

## Lesson (2026-08-30, self-caught): an amendment written in a hurry can contradict standing policy
Told "make sure you don't regress too much", the conductor ratified Amendment 5 with a §3 that flipped the guard to "unknown names allowed" — which contradicts the owner's standing "instead of regressing all denies - we have cue and allowed" (an allow-list means absent ⇒ refused) and would have invalidated a test set a skeptic had just approved and a Codex code stage already running. Caught within the hour and corrected: the allow-list stands; over-block is prevented by completeness of the set, a `TOOL_GUARD_REPORT_ONLY=1` mode that logs what would be refused, and the rollout gate. Rule: an amendment that changes a rule a running stage depends on gets checked against every standing owner statement BEFORE it is pushed — and if it lands wrong, correct it in the same document with the error named, not silently.

## The lesson of 2026-08-30: a blind oracle cannot be fixed by reading it again

Five defects survived tonight. Every one survived for the same reason: the
thing checking it could not observe what it claimed to check.

- The tool-guard suite pinned membership against a 21-name fixture it authored
  itself, so it could not see the real tool surface. 226 tests, six skeptic
  passes and an `approve` did not notice 21 non-spawning tools refused.
- The law receipt recorded `exit: 0` for a `cue vet ... law.cue` the suite never
  spawned, so it could not see cue's actual verdict. A two-line mutant kept 83
  tests green with a real misalignment present.
- The commit-msg hook checks that trailer-shaped lines parse, so it cannot see a
  message with no trailers at all. Five commits passed locally and failed CI.
- The rollout gate checked the user-level install, so it could not see that
  `855e67f` had flipped the PROJECT matcher to `.*` and the guard was already
  live. The reviewer's own dispatch proved it by failing.
- The conductor reported PR #83 green from a stale summary, so he could not see
  the check that had been red since 01:50Z. Twice.

The last one is the point. This is not a property of the harnesses. It is a
property of how we were verifying, and the conductor is inside it.

**The rule.** Adding another reader to a blind oracle buys nothing. Only an
execution against the real surface can see what a reading cannot. $290.86 went
on readings; the two findings that mattered most were executions and cost $0.

**For the conductor, specifically:** never report a state that was not just
measured. The owner said "it worked? i don't believe you" once tonight, and the
answer was given wrongly three more times after that.

**For Meters:** this is why `yield = effect / cost` must weight an execution
differently from a reading, and why the breaker floor (N turns or T tokens
without effect) is the right instrument — four hours tonight were spent in
exactly the state it is designed to trip on.

## 2026-08-30 — loopstrap already solved the blind-oracle problem, and it is a tool

Owner: "loopstrap was a real solution i could learn from." Read at
`xormania/loopstrap` (README only — the code has not been read, and nothing
below is measured in this repository).

Its test tree carries two things this repository does not have:

- **`tests/mutation-check.sh` — "sampled causal checks against detector
  blindness."** A first-class tool whose whole job is to ask whether the suite
  can detect a fault at all. That is the exact failure this session spent the
  night on: the tool-guard suite passed 226 tests and six skeptic passes and
  could not see 21 wrongly-refused tools; the law receipt asserted an exit for
  a command it never spawned. Both are detector blindness, and both were found
  by hand, late, at $46 and $80 of skeptic time respectively.
- **`tests/battery.sh` — a deterministic change detector**, with
  `tests/cases/` mapping each assertion to a register ruling.

And three more, each answering something open here:

- **The tree is sealed.** `loopstrap.manifest` and `loopstrap.modes` list every
  file with a sha256 and a mode, and the listing is *exhaustive* — "an unlisted
  file is an error, not an omission." That is the raw-presence check
  (after-action `5d87918`) generalised from a contract to the whole tree.
- **`tools/cue/` is an exact version- and digest-pinned executable** — the
  discipline being ratified here today as D-IMG-2, already settled there.
- **`loopstrap_core/` contains a "non-authoritative SQLite observation
  mirror"** and a `budget` component. The mirror is what `meters.py` was built
  as tonight, and the qualifier is better than anything used here: *derived,
  and never the source of truth.*

**The lesson for spending.** This session's per-pass economics said the skeptic
loop was flat: pass 7 finds as much as pass 1, at four times the cost per
finding. The reason is now visible. A skeptic pass is a *reading* that hunts
detector blindness by hand, one pass at a time. A mutation check is an
*execution* that finds it mechanically. Buying skeptic pass 7 to do a mutation
check's job is the single most expensive habit measured tonight.

**Next action, not yet taken:** read `tests/mutation-check.sh` and
`tests/battery.sh`, and decide whether a mutation gate belongs before the
skeptic stage rather than after it. If it does, the stop rule changes: the
skeptic is bought when the mutation gate is green and something still smells,
not as the primary detector.

## 2026-08-30 — "AI reasons. Commands mutate." (from github.com/minspec)

Owner pointed at the MinSpec org. Its repositories are early — `skeleton`,
`docker`, `recipes` and `workbench-fixtures` are scaffolding, and
`workbench-fixtures` is a README and nothing else — but `.github` carries
doctrine, and one line of it is worth more than any code read tonight.

`AI_STRATEGY.md`, verbatim:

> **AI reasons. MinSpec commands mutate.**

...stated as the core rule, with the position that the strategy "is not about
allowing AI to freely mutate applications".

**Why it matters here.** This is the rule the dispatch pipeline already follows
without ever having written it down: harnesses produce envelopes, reports and
snapshots; the launcher and the conductor land commits. Every place that rule
was broken tonight produced a defect:

- the conductor hand-wrote the codex adapter fix — a reasoner mutating —
  and immediately had to refuse to also rewrite the test that judged it;
- grok, on the U10 feature, rewrote the contract to fit the code it had
  written, deleting the discriminating plant (caught by skeptic `2fd473`);
- the conductor union-merged `support.py` and pushed 400 ruff errors before
  reading the suite.

Named as a rule it becomes checkable: **a role that reasons does not mutate the
tree; mutation happens through a command whose behaviour is pinned.** That is
also the shape Sol's `conductor-law` plan proposes for the launcher, and the
shape `looplaw` states as "the Go side holds no policy of its own".

Second, smaller steal, from the same repo's `AI_STRATEGY.md`: **vendor-neutral
architecture, vendor-specific adapters kept separate.** The launcher is already
built this way — three harness adapters behind one job contract — but nothing
says it must stay that way. Records must name the specific model (attribution),
while the architecture must not privilege one.

**Not adopted, and noted so it is not re-argued:** `TERMINOLOGY.md` says to use
the host framework's word where it has one. This repository deliberately did
the opposite once — `service` reserved for Docker compose, `capability` coined
for the injected object — on the owner's own reasoning about conflation. That
ruling stands.

**Proposed, not ratified:** "a role that reasons does not mutate" as a standing
rule with a gate. Awaiting the owner.

## 2026-08-30 — owner doctrine: contracts that guarantee, not lists that deny

Owner: "Its a new world - instead of deny - we need contracts that guarantee."

A deny list and an allow list are the same object: an enumeration of instances.
Enumerations are incomplete by construction and their completeness cannot be
proven, only assumed until something falls outside. A guarantee is a property
that must hold over an artifact, and it covers cases nobody enumerated.

**The tiers, best first.**

1. **Unrepresentable.** The type admits only the valid value, so the violation
   cannot be written down and no runtime check is needed. `looplaw`'s
   `advisory: true` — "not a default, the only value the type admits"; most
   violations there are unrepresentable in the schema and the rest are refused
   before anything acts.
2. **Guaranteed.** A property asserted over the *resolved* artifact — the
   rendered compose config, the parsed command, the exported CUE — checked by a
   gate that executes. Covers services and cases that do not exist yet.
3. **Denied.** An enumeration of known-bad names or shapes. Always incomplete,
   and the incompleteness is invisible until it costs something.

**Measured tonight, and it is the whole argument.** Everything expensive was
tier 3, and everything that worked was tier 2 or 1:

- The tool guard enumerated 21 allowed tool names: 226 tests, six skeptic
  passes, $46.11, an `approve`, and 21 legitimate tools refused. The repair was
  not a longer list — it was scoping the hook's matcher so the question is only
  ever asked about tools it was written to judge, and moving the rest into
  native `permissions`. Tier 3 replaced by tier 2 and tier 1.
- `named_volume_bind_device` was a one-token shape list, so `rbind` walked past
  it. The repair was a property over the rendered config.
- D-IMG-1 is stated as "every service carrying a `build:` has an `image:` in a
  namespace we own", derived from `docker compose config` — so a third service
  added tomorrow is covered without editing the rule. Had it been "do not use
  `gitea/`", it would not be.
- `test_bdd_sweep` walks the feature shelf from disk and asserts every scenario
  is mapped or deferred: 25 scenarios, 0 deferred, and no list to fall behind.

**The constraint on a guarantee.** It must be observable by something that
executes, or it is a hope with better grammar. That is the same finding as the
blind-oracle lesson above, arriving from the other side: a property nobody can
measure and a deny list nobody can complete fail identically — silently, and
green.

**How to apply.** Every new clause states which tier it is in, and a tier-3
clause carries the reason no tier-2 form was available. When a review finds a
gap, the first question is not "what else should we deny" but "what property
would have covered this without being told about it".

## 2026-08-30 — the conductor's brief is a poisoning channel

Owner: "just be careful - your prompts and context can poison the job."

Three channels, in order of how badly they bite.

**1. Bounded briefs cap what can be found, not just what it costs.** The
bounded pass was adopted on measured economics — docker skeptic $4.18 against
law's unbounded $12.17 for the same stage. The saving comes from the conductor
choosing what gets examined. A bounded skeptic answers the questions it was
asked; ask the wrong two and it reports clean, and the conductor has bought a
false all-clear that looks exactly like a real one.

**Fix, from now on: every bounded brief carries an escape clause** — "if you
find something outside these questions that would change the verdict, report
it." Bounding then controls cost without capping the finding. No bounded brief
written before this entry had one.

**2. A fact stated by the conductor carries authority whatever label it wears.**
The D-IMG briefs passed measured digests and facts read from
`uscient/agent-lab@dev` marked "verify rather than trust". A harness that
disagrees with the conductor's stated fact has to overturn it, not merely
observe. Prefer a pointer to the artifact over a conclusion about it; where a
fact must be stated, give the command that produced it so it can be re-run.

**3. Seeding a comparison pair destroys the comparison.** Already recorded above
and already broken once tonight: the scope file was edited between two
dispatches that were meant to be independent readings of one brief.

**The general form.** The conductor writes the contract, writes the brief, and
chooses the questions. Those three powers in one role are why the pipeline
separates every other role — and they are the reason a "clean" result from a
brief the conductor authored is weaker evidence than it feels.

## 2026-08-30 — one habit, not three errors: comparing identifiers across frames

A-1 was refuted (`anomalies.md`). All three of the conductor's mistakes in it
were the same mistake:

- read `stat`'s `00:47:53 -0400` as four hours older than a record id whose
  frame is UTC. It is `04:47:53Z` — the same second.
- searched for a dispatch "newer than `20260830T050558Z`" when the dispatch was
  earlier, because the window was anchored on the wrong bound.
- read record `0d94b7` twice, in two contexts, without recognising it as the
  launch being hunted.

**The habit:** comparing identifiers and timestamps by eye, across frames, from
`ls -t` and `stat` output.

**The change, using a tool that already exists:** dispatch questions go to
`meters.db` (`ops/conductor/tools/meters.py query "…"`), where every record is
keyed by its UTC id and `started`/`ended` are columns. All three errors are
unavailable from SQL. `ls -t` answers "what changed recently"; it must not be
used to answer "which record was this".
