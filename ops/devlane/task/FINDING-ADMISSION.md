# Finding admission — which findings earn correction

Standing: owner-scoped contract, 2026-09-09; implementation and independent
acceptance are later deliverables. Owner: "does it solve an issue or expand
scope - has to solve - and its can't be theoretical - it has to something
that can actually happen". This contract implements that scope's design,
not a claim that the runtime already enforces it. The implementation handoff
is part of this contract.

This is the dev lane, under [the lane boundary](../../../AGENTS.md#lane-boundary-and-precedence).
Use the existing [task envelope](CONTRACT.md#the-envelope), review jobs,
[findings ledger](../../conductor/findings/README.md),
[ladder](../../conductor/ladder-lever.md) and
[independent adjudicator](../../process/cross-review.md#acting-on-findings).
No new framework, workflow engine, model table or Symfony dependency follows.
Reviewer counts, approval freshness, retry limits, safety, custody, release
and merge authority remain owned by their existing contracts.

## Admission rule

An actionable correction solves a demonstrated issue within the agreed scope:
an existing requirement, a reachable trigger under supported conditions, an
actual failure of that requirement, and a reproduction or evidenced execution
path. Production occurrence is unnecessary. A reviewer checks realism and
attempts to refute its own finding before returning an evaluation.

Every evaluated finding has exactly one classification:

| classification | decision |
|---|---|
| `demonstrated-defect` | All four evidence duties hold inside agreed scope; eligible for correction, subject to bindings and dispute resolution below. |
| `scope-expansion` | The requested change needs a new requirement, capability, guarantee, supported condition or work outside agreed scope. Preserve it for an owner scope decision. |
| `unproven` | Available evidence cannot establish the requirement, reachability or failure, or the attempted refutation defeats the claim. State the missing evidence or counterexample. |

An existing defect outside the agreed work is a scope expansion **for this
correction**, not a denial that the defect exists. Missing coverage alone,
style and best-practice assertions, hypothetical capabilities and unsupported
premises do not earn correction. A documentation contradiction or a test that
misstates an existing requirement can earn it with the same evidence as code.
Priority ranks admitted defects; it cannot admit one. No serious concrete
defect may be hidden merely to shorten review. Preserve all raw findings,
verdicts, counts, evaluations, disputes and disposition history.

Code validates shape, source bindings and route consistency. Filled text
fields do not prove truth, reachability, execution or scope membership. Those
are the reviewer's judgment, independently adjudicated when disputed. Never
execute a `reproduce` string automatically on the host or network. Reproductions
remain evidence; execution requires the existing trusted dispatch and custody
boundary. A static execution path must cite the entry, supported inputs,
relevant branches and failing operation, with expected versus actual behavior.

## Minimal task interface

Keep the envelope's top-level keys and the four existing finding fields.
Add one optional finding member, `evaluation`; absent means legacy/unevaluated,
never demonstrated. Explicit null is invalid. The object is closed: all fields
below are required, and extra keys refuse. Strings must be nonblank; nullable
strings use null to declare missing evidence. JSON duplicate keys refuse before
dictionary construction, including inside an evaluation.

| field | exact type and meaning |
|---|---|
| `classification` | One of the three literal values above. |
| `scope_sha256` | 64 lowercase hex digits; SHA-256 of the exact owner scope bytes retained in the dispatch inputs. A worker cannot choose a substitute scope. |
| `requirement` | String or null; quote the existing requirement and name its immutable source path/ref or supplied scope location. |
| `trigger` | String or null; supported conditions and reachable entry/input. |
| `failure` | String or null; expected versus actual behavior and consequence. For a partial ruling this is the exact admitted subclaim. |
| `evidence` | Null or closed object `{kind, details}`. `kind` is `reproduction` or `execution-path`; `details` is a nonblank string recording command and observed result, or the cited execution path, measured against the envelope's full `stamp.ref`. |
| `refutation` | Nonblank string; attempted counterargument/check, result and remaining limits. For unproven/expansion, state the missing evidence, defeated premise or extra scope. |
| `source` | Null for the original review; for adjudication or a requested followup closure, closed object `{key, sha256}` binding the original raw finding. `key` is the existing `<record>#<n>`, with one-based positive decimal `n`; `sha256` is 64 lowercase hex digits. |
| `ruling` | Null for original review; `UPHELD`, `PARTIAL` or `REJECTED` for adjudication or requested followup closure. |

`demonstrated-defect` requires non-null requirement, trigger, failure and
evidence. `reproduction` also requires the existing nonblank `reproduce`
field; evidence details record its observed outcome. `execution-path` permits
`reproduce=null`. Other classifications may carry partial or counter-evidence;
their nullable fields must not be filled with invented facts. Concern reviewers
still supply the [required quotation pair](../../../docs/concerns.md).

The source hash is SHA-256 of the original finding encoded as UTF-8 JSON with
sorted keys, `ensure_ascii=False`, separators `(',', ':')`, no trailing LF and
no non-finite numbers. Include the original evaluation if present. The source
key, hash, full reviewed ref and retained scope digest must all match. Never
bind by claim similarity, an abbreviated ledger ref, current branch name or
array position in a merged report. The original review's evaluator is its
dispatch's recorded producer; worker-supplied attribution confers no authority.

Extend existing `envelope.finding(severity, where, claim, reproduce=None)` with
keyword-only `evaluation` (default omitted, distinguish explicit null).
`build`, `validate` and `ENVELOPE_SCHEMA` preserve and check this member;
they must not drop it while normalizing a finding or repair invalid evidence.
Existing arguments/returns and `EnvelopeError` remain. Strict response decoding
belongs in the existing task/dispatch extraction paths, not a second parser.
Dispatch consumes the same semantic validator as task replay. No new task
execution path, top-level protocol version, output file or grant is needed.

Counts remain a tally of **raw** findings and raw null reproductions. The
historical `opinions` counter is not an admission decision: an evidenced path
can qualify with a null reproduction; a command-bearing assertion can fail.
New completed reviews use `changes` when any evaluated demonstrated defect
exists and `approve` only when the review is complete and none exists, subject
to existing approval rules. Non-defects remain visible even alongside approve.
An incomplete review is `invalid`/null with a reason or `tripped`/non-approve
under the existing wire. Its partial findings are retained, never approval.

## Ledger and correction interface

Extend existing `findings.py import` to retain evaluations from review records
and `adjudicate` records. Import is still identity-bearing and idempotent.
Correction source jobs remain `check-tests`, `security-audit` and
`adversarial-review`; other jobs' command-log findings do not acquire review
authority. If another job reports an issue, it needs an explicit review of
that evidence within the agreed scope before this correction route can use it.
Original keys stay `<record>#<n>`. An adjudication adds an evaluation against
`source.key`, not a replacement raw finding or a new correction item. Retain
the exact source records separately from derived columns. A changed source
under an existing record id refuses; do not overwrite the first imported bytes.

Persist append-only evaluation and disposition events in the existing ledger.
Each evaluation event has exactly `{record, n, evaluation}`: the producing
dispatch id, its one-based finding index and the object above. Source records
supply identity, time, ref and input bindings. Existing finding exports retain
all columns and add `evaluations` (ordered event array, empty for legacy) and
`disputes` (ordered array of `{by, at, evidence, resolved_by}`). Dispute `by`
is a full identity, `at` a UTC timestamp, `evidence` nonblank text;
`resolved_by` is null or an adjudication record id. Preserve old disposition
values; add `disposition_history`, an ordered array of
`{disposition, evidence, disposed_at, disposed_by}` using the existing column
types. Do not invent timestamps/actors for missing historical data. Migration
retains the existing disposition as the first history entry when present;
earlier overwritten events are explicitly unavailable, not reconstructed.

Two additions to the existing ledger CLI, no new instrument:

```text
python3 ops/conductor/tools/findings.py dispute KEY EVIDENCE
python3 ops/conductor/tools/findings.py corrections --ref FULL_SHA --scope-sha256 SHA256 RECORD [RECORD ...]
```

`dispute` requires `WF_AGENT` as existing writes do, appends an unresolved
dispute, prints `KEY<TAB>disputed` and exits 0. Correction reads require no
identity and perform no imports/writes. The caller supplies the complete
declared review batch as record ids, not a cherry-picked subset of findings.
The ladder binds that batch to its recorded review stages before calling.
Each record must already be imported with its source available and must bind
to the named full ref and scope. No selection from the newest record by guess.

On success `corrections` prints one JSON object with exactly
`{ref, scope_sha256, admitted, held}` and exits 0, including when admitted is
explicitly empty. Each admitted entry is exactly
`{key, evaluation_record, evaluation_n, evaluation}`. Each held entry is
`{key, reason}`, where reason is `scope-expansion`, `unproven` or `disputed`.
Return each original key exactly once across the two arrays, in supplied record
order then original index. Ruling findings never become additional keys.
Selection uses the original evaluation unless a valid independent ruling
supersedes it; unresolved disputes hold that key. Multiple unresolved rulings
with conflicting classifications hold the key as disputed, never last-writer
wins. A later ruling must explicitly settle those supplied prior rulings.
Only a semantically valid `status=ok` adjudication can resolve a dispute;
invalid/tripped adjudications retain partial evidence without resolving disputes.
Requested followup closure below can settle an undisputed correction claim,
but cannot substitute for independent adjudication of a dispute.

Missing/malformed evaluations, duplicate batch records, unknown keys/records,
missing source evidence, source/ref/scope mismatch, or any incomplete review in
the batch refuse the entire read with exit 2, empty stdout and one
expected–found–needed stderr line. Classes respectively are
`admission-evidence`, `admission-binding` (duplicates, unknown or mismatched
sources included), and `admission-incomplete`. Unknown CLI arguments retain
`arguments`; writes without identity retain `identity`. No partial correction
brief may escape a refused read. A structurally invalid original record remains
visible as invalid evidence; importing history does not make it acceptable.

The existing ladder consumes this projection before `tests-fix`, `fix-tests`
or `fix-code`, including resume. Correction inputs contain only admitted
evaluations and their stable source keys, scope and required test command.
Use the evaluated failure/requirement as the correction demand, especially for
PARTIAL; do not append raw mixed audit envelopes or SKEPTIC prose as correction
instructions. Raw reports remain available in the ledger to reviewers and the
adjudicator. Existing test-author withholding applies to the projection too:
if admitted evidence leaks withheld implementation, refuse custody and require
a sufficient permitted specification projection; never silently strip it.

Nonempty admitted selects the existing correction stage; empty admitted skips
correction without creating another dispatch. Preserve the original verdict:
empty selection is not a rewritten approval or permission to advance an
incomplete/otherwise blocked review. A legacy `changes` batch adjudicated down
to no defects remains visibly resolved-without-correction; existing approval
requirements still govern advancement. Ladder records retain the consumed
batch ids, ref, scope digest and exact projection with its SHA-256, using the
same JSON encoding above. Resume revalidates those bindings before fresh work.
Existing stop/exit handling maps a refused read to an admission stop, not retry
or a dispatched repair of the evidence. No retry or freshness rule changes.

## Disputes and legacy records

The reviewer self-evaluates first. A disputed finding goes to the existing
adjudicator, which produced neither the artifact nor the finding. The artifact
producer may submit counter-evidence or a dispute, never dismiss it unilaterally.
Supply the pinned artifact, owner scope, original reports, disputed keys and
prior rulings verbatim; producer identities are checked from retained dispatch
provenance, not persuasive prose. If provenance cannot establish independence,
hold as disputed. No role/model table is introduced.
The adjudication inputs must include the artifact-producing dispatch records
and original finding-producing records; compare their recorded harness and
actual model against the adjudicator's, requiring a different harness from
each producer under the existing cross-review rule. Unknown actual model or
missing production provenance is unavailable evidence, not independence.

The adjudicator settles every supplied key exactly once and no other key,
returning evaluation-bearing findings plus the existing `RULING.md` artifact.
Missing/extra/duplicate source keys or disagreement between structured ruling
and the report refuses acceptance as `admission-binding`; structural checks
require exactly one line `## <key> — <ruling>` per supplied key, with literal
key and ruling matching the structured evaluation. Other prose is unrestricted
and judged independently. UPHELD/PARTIAL require a demonstrated in-scope defect;
REJECTED requires unproven or scope-expansion with reasons. A ruling resolves
only the disputes/prior rulings included in its retained input batch. Do not
ask the adjudicator to hunt for additional findings. An incidentally noticed
serious issue stays a visible follow-up in the report, never a new ruling or
an automatic correction/dispatch in this batch.

Legacy envelopes with no evaluation keep their historical parsing, counts and
verdicts; do not rewrite old dispatch records, add inferred evaluations or
retroactively invalidate completed work. Import/export must round-trip their
raw findings even if an old row cannot meet today's admission shape. A fresh
correction or resumed correction using them requires explicit evaluation in a
new `adjudicate` record bound to the original keys and hashes. Historical
dispositions such as fixed, ruled or opinion and a raw CHANGES verdict cannot
substitute. Missing old scope, source, full ref or independence evidence blocks
new admission with a named reason; never guess from a twelve-character ref.

## Mandatory prevention amendment

Authority: owner, 2026-09-09, supplied `owner-enforcement-addendum.md`:
"what the fuck is the point if its not enforced?" The fixture-proof,
additional-review and terminal boundaries below are requirements of this
deliverable. They supersede advisory prevention in the
[review-churn AAR](../../conductor/AAR-2026-09-09-review-churn.md), without
rewriting its measurements. Standing: declared design; implementation and
independent RED → GREEN acceptance are pending. The original five corrections
in `20260910T005819Z-code-codex-5b0115` remain a separate active source job.
This amendment changes no source, tests, onboarding, lane_policy or Git monitor.

### Frozen work-order declaration

Extend canonical dispatch/wrapper with `--work-order FILE`, retained with the
existing hashed inputs. It is required for fresh test-authoring, implementation,
review and adjudication work under this admission contract, including manual
dispatch. Ladder takes the same option and forwards it; resume reads the
retained declaration, never a replacement file. No optional bypass is defined.
Planning and historical read/export operations do not require one.

FILE is strict UTF-8 JSON with duplicate keys refused. Its closed object has
exactly the following required fields. All strings are nonblank, all hashes
are lowercase SHA-256, all refs are full commit object ids. File paths are
unique normalized repository-relative paths or names of retained input files;
absolute paths, traversal and symlinks outside admitted roots refuse. Arrays
are ordered and nonempty unless explicitly stated otherwise.

| field | exact shape and binding |
|---|---|
| `id` | String, matching `[A-Za-z0-9][A-Za-z0-9._-]*`; stable work-order key, not a new dispatch id. |
| `branch`, `base_ref` | Strings; owning lineage and its initial full ref. Later candidates must descend from this ref. |
| `scope` | `{path, sha256}`; exact retained owner scope bytes used by finding evaluations. |
| `authority` | Array of `{path, sha256}`; retained owner scope/addendum inputs establishing this work and its terminal action. These are evidence, not a new grant or authority inference from reviewer text. |
| `test_scope` | Array of repository-relative directory or file paths; frozen selection boundary for tests, helpers and fixture data. Directory entries end in `/` and include every tracked descendant. |
| `fixture`, `acceptance`, `final` | Arrays of command rows defined below. Fixture checks must execute without the new API; acceptance runs the intended behavioral tests; final includes `ops/bin/suites.sh` and every already-required final check. |
| `reviews` | Array of `{slot, job}`; the existing required review slots and jobs for this work order, in their existing order. No new reviewer count, model selection, closure stage or retry allowance. Launcher validates against the retained existing ladder stage table, or the supplied existing owner work-order sequence for manual work. |
| `terminal` | Exactly `{action: "draft-pr", base: "dev"}`. No ready, merge, release or branch deletion. |

A command row is exactly `{id, command, inputs}`. `id` is unique across all
three phases; `command` is the exact nonblank shell command executed by the
existing trusted verification subprocess; `inputs` is an explicit array
(possibly empty) of `{path, sha256}` for external retained inputs. Tracked
command scripts and their dependencies bind to each candidate's full ref.
Commands are owner-scoped inputs, never copied from finding `reproduce`, an
envelope or reviewer suggestions. Freeze complete test-file commands before
the first test dispatch; absent future files do not authorize derived defaults.
The existing ladder's artifact-derived command is only a consistency check
against this declaration for bound work, not a second source of criteria.

The ledger retains the original FILE bytes and digest, scoped to its existing
lane/repository and branch. Only one active declaration per branch is allowed;
a new id, `--unit`, scope spelling or fresh dispatch id cannot reset its review
history. Registration records the invoking `WF_AGENT` and authority input
digests, not a fabricated owner signature. Changed criteria or authority bytes
refuse; an actual owner scope revision is a separate work order requiring
explicit owner evidence and closure/supersession of the prior binding, never an
automatic retry. This interface offers no reset or override operation.

Dispatch `brief.admission` is exactly
`{work_order, declaration_sha256, scope_sha256, review}`; `review` is null
outside review jobs, otherwise the request below. `record.py` validates this
extension; `work_order` is the declaration id string and `review` contains the
exact decoded request, whose original bytes/digest are retained as an input.
The ledger retains registration and reservations append-only;
the ladder retains the same declaration digest and dispatch references.
Hash declaration bytes without reformatting. Hash derived objects using the
canonical JSON encoding already specified for evaluations.

### Executed fixture and acceptance evidence

The execution owner is `launch.py`, reusing the verification subprocess and
sanitized child environment of `_collect`, the admitted snapshot/custody
boundary and recorded wall. Add `launch.py verify ID --phase PHASE`, where
PHASE is `fixture`, `acceptance` or `final`; it executes only that record's
declared commands, requires existing write identity, and spawns no model.
This is evidence production in the existing launcher, not a task vendor path
or revival of the unbuilt `wf` writing verbs. `collect --verify` remains a
recovery check and cannot replace these phase receipts with an arbitrary CMD.

Before any paid `check-tests` attempt, canonical launch stages the candidate
test bytes under its existing allowed custody, runs every fixture command and
validates the resulting receipt before `_run_attempt`. Test-result acceptance
also invokes this same path after the test author's result is available and
before publishing an accepted test result. A worker may return raw candidate
output without proof; it cannot thereby supply accepted test evidence.
Other paid reviews require current fixture proof for the tests they rely on.
Unchanged receipts may be reused only on an exact binding match. Missing,
stale or failed proof blocks advancement until a fresh successful execution;
no paid review repairs a proof failure. Retry/limit rules remain unchanged.

The verifier executes in a disposable copy of the bound candidate snapshot,
with only its already-admitted inputs and a dedicated verification home.
It records hashes before and after execution, including all tracked files in
`test_scope`; changed tests, scripts or inputs invalidate that run. Fixture
mutation happens only in declared scratch copies. Test authors may inspect
established public consumers needed by fixtures; new implementation remains
withheld. If current snapshot staging cannot prove both permitted access and
withholding, it refuses custody; this amendment grants no new source access.

Fixture commands must assert actual planted values and exercise established
consumer assumptions directly, before any missing-new-API call: explicit empty
lists must stay empty; event names, fields and formatting must match the
established consumer; dependencies, provenance and batch keys must exist as
declared. Independently authored focused checks establish these assumptions.
The existing `test-guard.py` may also run where applicable, but its narrow
regex result cannot satisfy this executable fixture duty. Missing-API red is
recorded as such; it is neither fixture proof nor proof of downstream asserts.
The independent test reviewer still judges whether the chosen checks cover
the assumptions. Code proves execution and bindings, not semantic completeness.

Launcher-owned `verification` is an append-only array beside existing attempt
evidence, outside worker-writable snapshot/in/out. Every entry is the closed
object below; its hash is retained by the ledger and acceptance consumers.

| fields | exact types and meaning |
|---|---|
| `dispatch`, `attempt`, `phase` | Dispatch id string, positive integer attempt binding, phase enum above. Pre-review proof binds the reserved next attempt; it cannot be reused for a different attempt. |
| `work_order`, `declaration_sha256`, `scope_sha256`, `ref` | Strings matching retained declaration, owner scope and full candidate commit. |
| `tests` | Sorted array of `{path, sha256, producers}`; nonempty complete expansion of `test_scope`; `producers` is a nonempty array of artifact-producing dispatch ids whose retained commit diffs account for the file's current bytes. No identity from worker prose. |
| `tests_sha256` | Hash of canonical `tests`; every selected path/byte and producer is bound. |
| `executor` | `{path, sha256}` for the launcher code actually executing the verification subprocess; resolve once and retain its bytes, never hash one revision and execute another. |
| `by`, `started`, `ended` | Existing full invoking identity and UTC timestamp strings, measured by launcher. |
| `commands` | Ordered rows `{id, command, inputs, exit, timed_out, stdout, stderr}` matching the phase declaration exactly. `exit` is an integer or null for spawn failure/timeout; `timed_out` is boolean; stdout/stderr are `{path, sha256}` handles to retained process bytes, not worker log summaries. |
| `status`, `reason` | `ok` with null reason only if every command completed with exit 0 and all bindings held; otherwise `invalid` with nonblank reason naming failure or unavailable evidence. |

Run phase commands in order and retain all results; on infrastructure abort,
mark the receipt invalid and name unexecuted command ids in `reason`. An empty
command result array never passes. Raw red behavioral runs remain separate
failed execution evidence, bound to the same test manifest; only the independent
review determines whether their failures are the intended red. Test producer
provenance must establish independence from implementation under the existing
cross-review rule. Test-byte changes require an admitted test correction and
new proof; unchanged tests at a new candidate ref still require fresh execution.

Receipt admission reads the launcher's retained process result and bound
record, verifies files/digests and provenance, and compares the actual executed
command list. A worker-authored `verification`, `status=ok`, output handle or
copied historical receipt has no execution authority. Close, resume, collect,
ledger review import and ladder/land acceptance use the same predicate, not
merely `record.py`'s shape check. Legacy results remain readable but cannot
authorize new bound advancement without current executed evidence. This is
mechanical enforcement through canonical entrypoints under the trusted-host
boundary, not protection against an owner using raw shell or same-UID tampering.

### Review eligibility through manual dispatch and ladder

For review jobs, add `--review-request FILE` to wrapper and launch; ladder
generates the identical request. The closed object is
`{slot, kind, prior, projection_sha256, changes}`. `slot` names a declared
review slot; `kind` is `initial` or `followup`. Initial has `prior=[]`,
`projection_sha256=null`, `changes=[]`. Followup has the complete nonempty
prior review batch, its canonical correction-projection digest and nonempty
`changes`, each exactly `{key, correction_record, before_ref, after_ref,
paths, behavior}`. Paths are a nonempty sorted array of changed tracked paths;
behavior is nonblank text naming the admitted failure and changed behavior.
Refs and correction commit paths must match retained correction dispatch
provenance and the candidate. This structural check cannot prove the text true.

The ledger's existing `corrections` projection is the eligibility source.
Every followup key must still be admitted, unresolved in this work order and
included in that correction's retained input projection. A producer's `fixed`
disposition or successful implementation is only a closure claim until the
independent followup accepts it; it does not erase unresolved review duty.
Reject held, unrelated, unknown, already independently closed or unevaluated
keys; reject missing source batches, unchanged behavior with no matching code
or test diff, and unbound correction refs. Affected paths constrain the review
demand, not permission to hide serious incidental issues. Reuse the existing
custody-safe admitted specification projection; raw mixed reports never become
test-author instructions.

Canonical launch consults and atomically reserves the ledger slot before
model spawn, for both manual and ladder calls. The reservation records exactly
`{work_order, slot, dispatch, attempt, request_sha256, state}`, with state
`reserved`, `completed` or `failed`, appended as events. One completed initial
review consumes its slot. Concurrent duplicates, renamed-unit duplicates and
a new initial review after fixture fixes refuse. A retry refers to the same
reservation and recorded failed attempt under existing retry limits; a
completed review is never a retry. A followup additionally needs a remaining
followup slot in the existing sequence: unresolved findings alone do not add
one. In particular, the ladder's no-second-skeptic and single security re-audit
limits hold. Pre-spawn proof failures leave diagnostic evidence and release
the unstarted reservation without consuming a paid attempt. Crash recovery
reconciles its named record; it never guesses that an active reservation died.

The followup returns evaluation-bearing findings bound through `source` to
each requested key exactly once. Reuse adjudication source/ruling semantics
for closure: `UPHELD`/`PARTIAL` means an admitted failure remains; `REJECTED`
with counter-evidence means the requested claim no longer holds at the new
ref. Bind source hash/ref to its original record and review stamp to the
candidate ref; the two refs need not be equal. Task validates structure;
ledger validates the complete request binding and review independence.
No extra key may become a closure ruling. Incidental findings without a source
remain verbatim visible follow-ups with their evaluations; they cannot change
this request's correction projection or terminal criteria. A new demonstrated
in-scope issue still needs explicit admission to a permitted unresolved batch;
there is no automatic new dispatch or dismissal. Disputes use the existing
independent adjudicator. Incomplete followup never closes a key or approves.
For this bounded followup only, the verdict reflects the supplied closure batch:
`changes` if any requested failure remains, `approve` only if every requested
claim is completely resolved. Incidental findings retain their raw counts and
classifications without changing that verdict or erasing existing review gates.
The slot's initial/followup kind must match the existing sequence, so an initial
request cannot occupy a reserved re-audit slot. Extend task validation with
keyword-only `admission=None`: the default preserves legacy validation;
canonical acceptance supplies launcher-bound context, never a worker-selected
mode. A source-bearing review closure without its retained followup request
cannot authorize closure. Dispatch extraction and replay must use this same
context-aware validator; standalone legacy parsing confers no advancement.

### Refusals, completion and independent acceptance

| class | expected / found / needed boundary |
|---|---|
| `admission-criteria` | Frozen complete declaration / absent, malformed or changed criteria, unknown slot or reset id / supply original retained owner-scoped declaration; an owner scope change requires separate authority. |
| `admission-fixture` | Current successful executed fixture proof / absent, failed, stale, forged or mutated evidence / run declared checks successfully on the actual bound tests. |
| `admission-review` | An eligible unconsumed slot and admitted changed unresolved batch / duplicate, exhausted slot or unsupported followup / complete the existing authorized path or resolve its named evidence deficiency. |
| `admission-binding` | Exact source, producer, ref, scope, request and receipt bindings / missing or mismatched evidence / restore the correct retained records, never infer identities. |
| `admission-incomplete` | Complete accepted review and declared final evidence / incomplete review or missing/failed acceptance/final command / finish the named existing checks. |

All are non-overridable. Ledger/verify CLI preconditions use exit 2, empty
stdout and one expected–found–needed stderr line. Canonical launch/wrapper
preserve their existing dispatch-refusal exit 3; pre-spawn refusal creates no
model process. After execution, retain invalid/null-verdict evidence and named
cause; ladder uses its existing stopped-stage exit 3. Do not relabel a failed
execution as a pre-effect rejection. Existing identity/custody refusals stand.

Completion requires the exact declared fixture, acceptance and final commands
to pass against the final candidate, current test/producer bindings, complete
required reviews under their existing freshness rules, and no admitted
unresolved correction/dispute in the required batch. Compare declarations on
every fresh dispatch, resume, result acceptance and before the terminal action.
No artifact-derived replacement command or reviewer condition may enter here.
If freshness requires review but the existing slots are exhausted, stop with
the named unsatisfied criterion; do not invent a stage or claim completion.
Once satisfied, ladder takes its existing push/draft-PR path into dev. Add
`ops/bin/ladder.sh finish WORK_ORDER` for manual work: resolve the registered
owning worktree and accepted records, apply that identical terminal predicate,
then invoke the existing driver's push/draft-PR operation without launching
review stages. This is the canonical manual terminal entrypoint, not a new
closure review. It refuses absent work-order/evidence bindings before push.
Retain `{work_order, declaration_sha256, ref, receipts, reviews, pr}` in the
existing ladder record (manual terminal evidence in the ledger): receipts are
receipt hashes, reviews accepted record ids, pr the returned draft URL. A
failed terminal operation remains stopped and resumable without fresh reviews
if bindings are unchanged. No release/merge authority follows.

Independent tests are authored once from this amendment after the original
five corrections finish, then implemented by a different producer. Extend
existing dispatch/task/ledger/ladder test homes, using synthetic process and
dispatch records. No new review dispatch or executable test is part of this
docs-only amendment. This bounded matrix supplements the original admission
matrix; source cases are the dated AAR and supplied owner addendum, not newly
inspected private dispatch captures.

| case | required paired behavioral observation |
|---|---|
| Empty-list substitution | Actual fixture checks reject default substitution for `[]`; the helper preserving `[]` passes. |
| Nineteen absent-adapter reds, guessed event consumer | Missing API alone cannot pass fixture gate; established event/format checks execute before API access, catch the wrong assumption and pass the corrected one. No new monitor implementation here. |
| Admission fixture omissions | Missing dependency/provenance, key outside batch or forbidden raw report refuses at its owning binding/custody gate; complete permitted projection passes. |
| Executed proof versus assertion | Invoke real launch preflight with a spy model boundary: populated worker receipt with no child run, failed/omitted fixture command and stale test/ref/scope hashes yield zero model starts; real successful process evidence permits one. |
| Manual review churn and concurrency | Real wrapper → launch path rejects a second whole `check-tests`, including renamed unit/new id and simultaneous duplicate; first eligible slot starts once. |
| Earned followup | Admitted unresolved key plus bound changed behavior and an existing followup slot passes; held/closed/unchanged/unrelated key, exhausted slot and altered request refuse. Resume preserves attempts rather than buying another round. |
| Followup scope and completeness | Complete supplied-key closure is accepted; missing/duplicate ruling refuses; incidental expansion/unproven findings remain visible without becoming new closure conditions or dispatches. |
| Criteria and terminal | Changed command/input/required check or missing declaration refuses through fresh/resume/collect/acceptance; all frozen checks and required reviews green trigger only the draft-dev terminal path. Failure retains stop; unchanged terminal retry adds no review. |
| Custody, producer and legacy | Same/unknown producer and leaked withheld source refuse; permitted established interfaces and independent producer pass. Old records still read unchanged but cannot seed unbound new advancement. |

Use real entrypoints and a controlled verification subprocess; mock paid model,
GitHub and landing boundaries only where needed. Assert process invocation,
retained stdout/stderr bytes, exact bindings, refusal wire and no forbidden
dispatch/terminal effect. Shape tests and prompt substring assertions alone
cannot certify these outcomes. Acceptance records retain RED and GREEN with
identical independent test hashes plus focused and `ops/bin/suites.sh` results.
Until those receipts exist, machine enforcement remains pending.

## Verification boundaries and implementation handoff

Amendment source reading, 2026-09-10, against
`9399f228a71d2a245a14cb06bcf4a8c123142ae6`:
`sed -n '1304,1531p' ops/devlane/dispatch/launch.py` locates preflight,
snapshot/input retention and `_run_attempt`;
`sed -n '2168,2266p' ops/devlane/dispatch/launch.py` locates the existing
verification subprocess; `sed -n '1091,1121p' ops/conductor/tools/ladder.py`
locates artifact-derived commands. These are extension seams, not executed
proof of the amendment. Earlier source measurements below retain their dates.

Measured source baseline: `d7bf77f9cbf34398961dcde3add4530d25b83fd3`,
2026-09-09. `sed -n '35,120p' ops/devlane/task/envelope.py` shows the closed
four-field finding; `sed -n '1349,1415p' ops/conductor/tools/ladder.py` shows
verdict-driven correction; `cat ops/conductor/tools/findings.py` shows the
existing keys and disposition store. These are source observations, not live
acceptance or semantic classification of old findings.

The [six coupling obligations](../../../docs/verified-couplings.md) apply to
these exact edges; each needs a faulty/valid fixture pair and version/date
stamps at implementation acceptance. Until then behavior verification is absent.

| owner → consumer | declared gate and permitted mock |
|---|---|
| Task finding shape → dispatch extraction, replay, ledger | Round-trip legacy and evaluated envelopes; reject malformed evidence, duplicates and tally mismatch through real entrypoints. Synthetic harness responses implement the same envelope; no vendor call. |
| Retained dispatch scope/ref/source/provenance → ledger evaluation | Detect changed bytes, wrong scope/ref/key/hash, unavailable identity and same-producer adjudication. Fixture records and scoped files carry explicit synthetic identities; no operator store/transcripts. |
| Ledger → ladder correction input and resume | Exercise actual CLI/import/export and driver selection with synthetic records; mixed batch yields only admitted demands, empty yields no dispatch, missing/incomplete refuses, dispute holds and independent ruling resolves. Mock the existing dispatch/land boundary, not the selector being tested. |
| Projection → test-author/implementation custody | Assert both sufficient given specification and absent withheld implementation; no raw mixed report smuggled in. Omitted evidence refuses rather than granting correction. |

Reverify the consumers of any changed edge; task shape changes cover extraction
and ledger, ledger changes cover export and routing, routing changes cover
brief generation, resume and custody. Tests must assert real outcomes and
refusal class/reason, not merely prompt substrings. Pure schema success is not
proof that a reviewer correctly classified a finding.

The next producer writes independent tests from this contract and owner scope,
without implementation. Cover real defect, unsupported premise/scope expansion,
mixed findings, complete no-defect, incomplete review, missing evidence, static
path evidence, documentation/test defects, legacy read versus fresh correction,
binding mismatch, disputes and partial rulings. Pair every rejection with a
nearby valid case. A different producer checks those tests before implementation;
the implementation author neither writes nor approves them.

Add a small independently classified sample of actual agy findings alongside
synthetic cases. Immutable starting source:
`d7bf77f9cbf34398961dcde3add4530d25b83fd3:ops/conductor/findings/findings.jsonl`,
blob `5e996b21fb03769a365155d752e811a66deb4016`, measured by
`git rev-parse d7bf77f9cbf34398961dcde3add4530d25b83fd3:ops/conductor/findings/findings.jsonl`.
Candidate keys include `20260903T232447Z-review-codex-9c696a#1` and
`20260904T040646Z-review-codex-7fbe5c#1`; these are sampling pointers, not supplied
truth labels. The independent test producer must cite original requirement,
supported scope and pinned evidence, justify each expected classification and
state unavailable evidence. Existing severity/disposition is not a truth label;
if this source cannot support a needed class, declare that limit and source
another immutable public/repository finding. No private transcripts/auth, raw
harness captures or automatic execution of historical reproduction strings.

Then implement in the existing envelope/schema and extraction, review job
prompts (self-evaluation), adjudicate prompt (supplied batch only), ledger and
ladder seams above. Preserve existing C1/C2 validation/output custody. No source,
prompt or test change belongs in this first deliverable. Run focused independent
behavior tests and `ops/bin/suites.sh` as the full suite gate; retain results and
limits. Batch independent acceptance after implementation, then open the later
draft PR into dev under the owner's scope. Every commit retains `Source:` and
actual-model `Co-Authored-By:` trailers. No disposable plan carries this design.
