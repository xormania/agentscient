# Finding admission — which findings earn correction

Standing: owner-scoped contract, 2026-09-09; implementation is present in the
task, dispatch, jobs, ledger and ladder owners. Independent acceptance remains
pending: the supplied ledger/routing gates have unresolved fixture/contract
contradictions. Owner: "does it solve an issue or expand
scope - has to solve - and its can't be theoretical - it has to something
that can actually happen". Structural enforcement does not establish the
truth of an evaluation or independent acceptance. The implementation handoff
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
| `source` | Null for the original review; for adjudication, closed object `{key, sha256}` binding the original raw finding. `key` is the existing `<record>#<n>`, with one-based positive decimal `n`; `sha256` is 64 lowercase hex digits. |
| `ruling` | Null for original review; `UPHELD`, `PARTIAL` or `REJECTED` for adjudication. |

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
Only a semantically valid `status=ok` adjudication can supply a ruling;
invalid/tripped adjudications retain partial evidence without resolving disputes.

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

## Verification boundaries and implementation handoff

Implementation reading, 2026-09-10, against base
`8a6a51fff0925fd006aa3a3987cc4b3f969c940e` plus the working diff:
`git diff --stat` names `envelope.py`, `run.py`, `launch.py`, `jobs.json`,
`findings.py` and `ladder.py`. The public additions remain the optional finding
evaluation and the two ledger verbs. The ledger imports legacy history without
semantic repair; it requires the shared task validator for correction reads.
Original JSON bytes and retained input/report bytes live separately from the
derived rows in SQLite. Corrections use a read-only connection. Migration
records the disposition that is actually present; earlier overwritten
disposition events are unavailable, not reconstructed.

Adjudication uses existing retained inputs: original dispatch JSON files
verbatim, artifact-producing dispatch records, prior adjudication records and
the exact scope file. A supplied subset/dispute batch is existing ledger export
JSONL, one row per supplied key; its disputes identify precisely which events
the ruling may resolve. Without subset rows the original reports define the
whole supplied finding batch. No new dispatch flag or output grant is added.
The launcher retains its exact review scope in the existing input set when no
identical input is already present. Missing old scope inputs require evidence,
never a digest copied from the worker's evaluation.

The ladder records and revalidates correction receipts before correction work;
CHANGES with empty admission remains resolved-without-correction and cannot
provide missing approval. Audit mint metadata commits are deferred until both
audits start, with durable partial records kept throughout. A worker closure
or another actor can still move the ref during that interval: differing full
review refs stop admission, rather than being treated as equivalent trees.
Resume cannot silently rebind a previously consumed projection.

Local measurements: `python3 -m unittest discover -s ops/devlane/task/tests -v`
ran 329 tests successfully; the dispatch `test_launch_envelope*.py` discovery
ran 58 successfully; conductor `test_findings*.py` discovery ran 16 successfully.
The three supplied file-path gates are not green as a group. Test bytes were
not changed. Their independent author must address missing staged task
dependencies/scope/provenance, unbound routing mock keys, and the expectation
that empty admission supplies a legacy CHANGES review's missing approval.
The older ladder test that requires raw SKEPTIC input also contradicts the
admitted-only correction requirement. Full-suite and independent acceptance
remain outstanding; these local measurements are not their substitute.

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

The independent-test duty is retained here from the original handoff. Tests
were supplied before this implementation; their corrections remain the
independent test producer's work. Cover real defect, unsupported premise/scope expansion,
mixed findings, complete no-defect, incomplete review, missing evidence, static
path evidence, documentation/test defects, legacy read versus fresh correction,
binding mismatch, disputes and partial rulings. Pair every rejection with a
nearby valid case. A different producer checks those tests before implementation;
the implementation author neither writes nor approves them.

Keep a small independently classified sample of actual agy findings alongside
synthetic cases. The original historical sampling citation was:
`d7bf77f9cbf34398961dcde3add4530d25b83fd3:ops/conductor/findings/findings.jsonl`,
blob `5e996b21fb03769a365155d752e811a66deb4016`, measured by
`git rev-parse d7bf77f9cbf34398961dcde3add4530d25b83fd3:ops/conductor/findings/findings.jsonl`.
The originally named keys `20260903T232447Z-review-codex-9c696a#1` and
`20260904T040646Z-review-codex-7fbe5c#1` are effort/security history, not agy
sample pointers (`rg` against the tracked export, 2026-09-10). The supplied
independent sample is now
`ops/conductor/tests/fixtures/finding_admission/agy-sample-classifications.json`,
SHA-256 `b363c5f8c12ab3756e7b71dba429fad35d016cdc79f3457de129223503d59a83`,
measured by `sha256sum` at the implementation base above. It cites, among others,
`8630ccf0e72a11596ed1a5cb7e2efa2f931f6d29:.dev/records/dispatches/20260908T063559Z-review-claude-6eb510.json`
and
`317a12035fb2b18d92a39d43b023d0326be514ee:.dev/records/dispatches/20260908T083005Z-review-codex-f022fd.json`.
These are the independent producer's immutable citations, not newly verified
captures: `git rev-parse` of the first cited path refused because that path is
absent in this checkout's cited tree. No historical reproduction was executed.
The fixture and its labels are unchanged. The independent test producer must cite original requirement,
supported scope and pinned evidence, justify each expected classification and
state unavailable evidence. Existing severity/disposition is not a truth label;
if this source cannot support a needed class, declare that limit and source
another immutable public/repository finding. No private transcripts/auth, raw
harness captures or automatic execution of historical reproduction strings.

The implementation belongs in the existing envelope/schema and extraction, review job
prompts (self-evaluation), adjudicate prompt (supplied batch only), ledger and
ladder seams above. Preserve existing C1/C2 validation/output custody. The
original first deliverable was contract-only. Run focused independent
behavior tests and `ops/bin/suites.sh` as the full suite gate; retain results and
limits. Batch independent acceptance after implementation, then open the later
draft PR into dev under the owner's scope. Every commit retains `Source:` and
actual-model `Co-Authored-By:` trailers. No disposable plan carries this design.
