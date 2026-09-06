# The task app — a calling convention for delegated work

This is dev tooling under
[AGENTS.md §Lane boundary and precedence](../../../AGENTS.md#lane-boundary-and-precedence).
Work profile is independent of job role, harness and conductor/worker role.
Shared output contracts do not import the prod application's Symfony
runtime into the runner or imply its replacement. A brief's older framework
recommendation cannot override that boundary. This scope clarification
changes neither the job schema nor executable acceptance behavior.

A **task** is one delegated unit of work that returns one deliverable
in one round. It is not a conversation and not a workflow stage: the
Conductor invokes it with parameters, the task does its own iteration
internally, and it returns a typed envelope.

The point is not correctness — the checks and the cross-review process
already own that. The point is a **standard, token-efficient way to
run delegated work**, so the plumbing is written once and the Conductor
never parses prose.

## Why it exists, measured

On 2026-08-22 one session launched **36 agents** and hand-wrote the
same ~40 lines of plumbing for nearly every one: snapshot a ref,
archive it, write a diff, drop a marker, discover the session stream
the harness just opened, arm the battery, wait, read a verdict by eye.
**15 of those 36 were repeat rounds of a review already run**, each
handed the entire diff again even when the live question had narrowed
to a single test case — because there was no parameter for scope.

Two costs follow from that, and both are what this app removes:

- **Plumbing retyped per launch**, with the mistakes that come with it.
- **The Conductor reading work product.** Verdicts arrived as prose, were
  read in full, and the interesting parts were retyped into the next
  prompt. That is the loop cost: a Conductor's context grows with every
  round until it cannot run another.

## The call

This is the target calling convention, not a claim that every field is
already accepted by either CLI. C1 standing and measured baseline are in
the [dispatch contract](../dispatch/CONTRACT.md#c1--execution-authority-target-not-runtime-completion).
Dev tooling remains permanent and independent of the Symfony application;
`prod` is a work profile, not a tooling implementation or retirement plan.

```
task(
    job,                                   # which pre-made task
    context = {ref, diff_base, include, prior},
    require = {schema, scope, constraints},
    runtime = {harness, model, role, profile, effort, caps},
)
```

**`context` is the token lever.** It states what the task may see:

| field | meaning |
|:--|:--|
| `ref` | the git ref to snapshot — the task works on a detached copy, never the live tree |
| `diff_base` | what the diff is taken against; omitted means no diff is written |
| `include` | explicit path allowlist. Absent means the whole snapshot, which is the expensive default and should be a deliberate choice |
| `prior` | findings from an earlier call. Turns "review this again" into "confirm these are closed", which is a much smaller job |

**`require`** states what must come back: the output `schema`, the
`scope` to aim at, and the `constraints` the task must respect (read
only, plant on copies, never edit the snapshot).

**`runtime`** states who runs it and under what ceiling: `harness`,
`model`, `role`, `profile`, `effort`, and supervision `caps`. Harness,
model, role and work profile are independent configurable dimensions,
constrained by the job and admitted capabilities; a job's declared role
is not permission to guess a model or widen source access for an output.
Profile policy is a later consume-only join owned by the parallel
`lane/lane-boundary-20260905` track, not defined by task or dispatch.
The current task vendor runner uses the telemetry battery; launch has
different inline supervision, as the dispatch baseline records.
A job never names a model — that
is the Conductor's dial, which is what makes "eight cheap ones" and "one
careful one" the same job.

## The envelope

Every task returns the same shape. The Conductor routes on it without
reading the work:

```json
{
  "job": "adversarial-review",
  "status": "ok | invalid | tripped",
  "verdict": "approve | changes | null",
  "counts": {"p1": 0, "p2": 1, "p3": 0, "opinions": 0},
  "findings": [
    {"severity": "p2", "where": "file.py §section", "claim": "...",
     "reproduce": "python3 -m unittest ..."}
  ],
  "artifacts": {"raw": "<path>", "diff": "<path>"},
  "spend": {"harness": "grok", "total": 0, "out": 0, "runs": 0},
  "stamp": {"ref": "<sha>", "started": "...Z", "ended": "...Z"},
  "note": null
}
```

Three fields carry the weight:

- **`reproduce`** — the command that re-derives the claim. A finding
  without one is an opinion, and the envelope says so rather than
  hiding it.
- **`artifacts`** — handles, not contents. The prose stays on disk;
  the Conductor reads it only if it decides to.
- **`spend`** — what the run cost, so `worth.py` can price a job
  instead of guessing. Runs happen in throwaway snapshots today, and
  usage.py's cwd filter therefore attributes **none** of them to the
  repo they served: roughly 118M tokens of review on 2026-08-22 went
  unattributed. The stamp is what closes that.

**One semantic authority:** task's [envelope.py](envelope.py) owns the
shape and acceptance rules; dispatch and all frontends must consume that
authority. Counts are derived from findings, including `opinions` for a
null reproduction; a parsed tally mismatch is refused, not repaired.
Artifacts remain non-empty, single-line handles bounded by `HANDLE_MAX`,
not embedded reports. Workers leave the declared zero spend placeholder;
the launcher resolves measured spend, declaring unavailable evidence
instead of treating that placeholder as a measurement.

**Current acceptance defect (C1 baseline):** `run.py` calls
`envelope.validate`, while launch uses `_schema_valid`, adding only an
invalid-plus-approve check to the schema. Shared JSON shape therefore does
not establish shared counts/status/handle acceptance. The optional write
job `commit` transport also needs later reconciliation with the validator's
fixed fields. C1 changes neither validator, schema nor transport; later
acceptance work must preserve harness response extraction and provenance.
Reproduce with `sed -n '240,310p' ops/devlane/task/envelope.py`,
`sed -n '297,335p' ops/devlane/task/run.py` and
`sed -n '708,745p' ops/devlane/dispatch/launch.py` at the dispatch baseline.

**Named temporary exception — inline planning reassignment.** The owner
brief authorized the immediate read-only architecture review to return
the plan as an artifact string after plan record `976735` could not write
`out/PLAN.md` under Codex read-only containment. That specific reassignment
is temporary transport, not a standing artifact mode or general permission
for read-only jobs to embed reports. Ordinary plan, skeptic and ruling
jobs still require file handles. C1 does not universalize the workaround.

## Statuses, and the refusal rule

`status` is the routing decision, and it is not the same as `verdict`:

| status | means |
|:--|:--|
| `ok` | the task ran and produced its deliverable |
| `invalid` | the task could not do its job — harness missing, ref absent, snapshot failed, output unparseable. **Never reported as an approving verdict.** |
| `tripped` | the battery stopped a runaway; the deliverable is partial and says so |

A task that could not look must not return `approve`. This is the same
rule the registered checks follow, and the reason `status` and
`verdict` are separate fields rather than one.
`invalid` requires a null verdict and a note naming why it could not do
the job; `tripped` may carry partial findings but never `approve`.
For implementation jobs, `ok` requires the named acceptance command to
exit 0 in the final tree; otherwise `invalid` names the failing command.
Process exit zero alone is not accepted-envelope evidence.

## Jobs

A job is data, not code — a JSON entry naming the role, the prompt
template, the output schema, and the default constraints. Adding one
does not change the runner.

| job | deliverable |
|:--|:--|
| `adversarial-review` | findings that survived the task's own attempt to refute them |
| `security-audit` | security findings against the change that survived the auditor's own attempt to refute them |
| `verify` | one claim, executed: a reproduction or a refutation |
| `author-tests` | a test file that has been run and is red for the stated reason |
| `sweep` | structured findings over disjoint categories, merged |
| `plan` | a plan written to the job's `out/PLAN.md`, and an envelope naming it |
| `check-tests` | a skeptic's report at `out/SKEPTIC.md`; verdict `changes` when any test is refuted |
| `implement` | commits in the snapshot that make the named test command pass, trailers per `AGENTS.md` |
| `adjudicate` | a ruling at `out/RULING.md` — UPHELD / PARTIAL / REJECTED per finding, and what the reviewers missed |

`verify` is deliberately callable on its own: it is the primitive the
others lean on, and the one whose answer is mechanical — an exit code
or a diff, not another opinion.

The last four are the dev-lane pipeline's own stages as jobs (dispatched
by the dispatch app; see `ops/devlane/dispatch/CONTRACT.md`). They are data
in `jobs.json` today. Three of them — `plan`,
`check-tests`, `adjudicate` — name `{out}` or `{inputs}`, which `run.py`
does not yet supply, so `render` refuses each by name rather than
launching a brief with a hole in it. `implement` names only `{ref}` and
`{scope}` and renders today; what it still lacks is the launcher's
whole-mode snapshot and collect, without which its commits have nowhere
to land.

## What the runner does, and does not

The target worker execution service is dispatch's `launch.py`: it
snapshots, launches, supervises, collects, parses and records. The separate
`run.py` vendor engine is manual/dormant at the measured baseline, not its
backend; direct verification and stub replay are distinct uses. It does
**not** read the work product, and
it does not decide anything a job could not have decided in
advance.

Two things stay outside it. **Intent** — which of two defensible
designs is right — belongs to the job author or escalates to the
owner; a worker task has no standing to settle it. And **the wiring's
own correctness** cannot be delegated to the tasks it wires, which is
why every job is bound to a planted fault: run it against a fixture
with a known defect and it must surface it; run it clean and it must
stay quiet. A job that cannot catch its own planted fault is a
no-op with good throughput.

## Harnesses

The job is harness-independent; an adapter absorbs the differences
in invocation, in where each harness writes its session stream, and in
how each reports usage (`ops/devlane/telemetry/usage.py` already holds
those three accountings). A `stub` adapter exists so the suite can
test the runner without spending a token or needing a model.

## The property to hold

**Iteration N should cost the Conductor about what iteration 1 cost.**
A loop whose context grows every round has a horizon; one that stays
flat can run as long as the work does. The envelope is what makes that
possible, and `worth waste`'s cache-churn signal is how it is checked.

## Declared job outputs

Target ownership: task owns output requirements in [jobs.json](jobs.json);
launch resolves declared `{out}` paths into grants and records custody.
At the C1 baseline, prompt prose requests `{out}/PLAN.md` for `plan`,
`{out}/SKEPTIC.md` for `check-tests`, and `{out}/RULING.md` for `adjudicate` (reproduce:
`rg -n 'PLAN.md|SKEPTIC.md|RULING.md' ops/devlane/task/jobs.json`). These are
job outputs outside the source snapshot, not source-write roles.

A later runtime slice adopts the C2 `outputs` declaration below in `jobs.json`.
No such machine-readable declaration exists today; prompt prose
records demand and must not be parsed to authorize filesystem grants.
Missing declarations mean no extra grant. The named temporary inline
planning reassignment above remains limited to that specific reassignment.

**Target:** grants follow declared artifact needs, not arbitrary job-name
branches. A read role retains source isolation and unchanged-source
settlement while writing its declared outputs. Neither an output handle
nor a profile can confer broad source/host permission. Each harness must
prove the required capability or explicitly refuse it; dispatch owns that
[capability evidence](../dispatch/CONTRACT.md#isolation-per-harness).
Output declarations and grants are owned here and in launch, with no wait
on or duplicate of the parallel lane-policy contract.

**Measured transport gap:** launch renders `{out}` and `{inputs}`, but
`writable_out` is selected by `job == "check-tests"` on launch and resume.
Other Codex read jobs remain read-only; there is no generic output grant.
The owner brief records `976735` invalid because its required plan write
was rejected. Task run does not automatically supply document-job output
or input paths either. Rendering a path and declaring a capability do not
prove that a worker can deliver it. Reproduce the name branch with
`rg -n 'writable_out=' ops/devlane/dispatch/launch.py`. C1 documents this
defect; independent runtime/test work follows.

### C2 standing and declaration schema

**Contract only:** this is the two-file bucket from GPT-6 plan
`20260906T024750Z-plan-codex-93f60d`, Claude review
`20260906T025522Z-review-claude-cfc890`, and the supplied
`launch-c2-contract-ruling.md`, incorporating F1–F5. Task owns declaration
vocabulary, validation and deliverable rendering;
[launch](../dispatch/CONTRACT.md#c2--output-admission-contract-only) resolves
paths, admits grants and checks filesystem custody. No executable code,
catalogue, prompts or capabilities change here. Historical evidence and the
narrow inline planning exception above retain their standing; C2 does not
retroactively reject old records or generalize that exception.

Source checked on 2026-09-06 at `19f938e339cc519d66eb65989915decfa00439df`:
`cat ops/devlane/task/jobs.json` shows no `outputs` declarations and native
prompts request their document paths without fixed artifact keys;
`rg -n 'ENVELOPE\.|\.validate\(|writable_out=|TMPDIR|COMMIT_MSG|last-message.json'
ops/devlane/dispatch/launch.py` shows the job-name grant branches and the
semantic-validator gap described above. This is source evidence, not live
containment proof. Runtime adoption remains later independent work.

An optional `outputs` member on a harness job has exactly this standalone
JSON Schema. Omission is defined as `[]`, with no additional worker output
grant. Explicit `null` is invalid. Each `file` is a required, non-empty
document; `scratch` authorizes temporary work and requires no artifact.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "array",
  "uniqueItems": true,
  "items": {
    "oneOf": [
      {
        "type": "object",
        "properties": {
          "kind": {"const": "file"},
          "path": {"$ref": "#/$defs/path"},
          "artifact": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9_-]*$",
            "maxLength": 64
          }
        },
        "required": ["kind", "path", "artifact"],
        "additionalProperties": false
      },
      {
        "type": "object",
        "properties": {
          "kind": {"const": "scratch"},
          "path": {"$ref": "#/$defs/path"}
        },
        "required": ["kind", "path"],
        "additionalProperties": false
      }
    ]
  },
  "$defs": {
    "path": {
      "type": "string",
      "maxLength": 240,
      "pattern": "^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*$"
    }
  }
}
```

Task's semantic declaration validation additionally rejects duplicate
JSON object members, duplicate paths even across different kinds, repeated
artifact keys, ancestor/descendant overlaps and more than one scratch
entry. Paths and keys must match their grammar over the entire string
(including rejecting a trailing newline). Paths are case-sensitive POSIX
relative names beneath the job's canonical `out/`, never templates or
shell expressions: absolute paths, dot segments, backslashes, whitespace,
globs and substitutions refuse. No case folding or path normalization may
turn invalid input into a different grant. Normalized declarations mean
validated values with omission expanded to `[]`, preserving array order.

Launch supplies adapter/launcher transport reservations to validation;
equal, ancestor or descendant collisions refuse. Reserved leaves include
`last-message.json` and `COMMIT_MSG` beneath `out/`; neither is a report or
scratch declaration. The list must include any further transport paths an
adapter needs. At adoption, declared and admitted scratch owns its temporary
subtree and `TMPDIR` mapping, replacing any legacy launcher-created temporary
output directory for that purpose; it is not also reserved as transport.
Thus the declared `tmp` below is scratch, while genuine transport leaves
remain reserved and file/scratch collisions still refuse. Existing path
types, links and unsupported filesystem alias behavior are checked by
dispatch, not inferred from the schema. A regular
document must not be multiply linked; no output or ancestor may be a
symlink. Lexical and real-path checks alone do not prove race-proof
containment.

### Native declarations and rendered deliverables

The following is catalogue data for later adoption, not a catalogue edit
in this bucket. Each value is the named job's `outputs` array:

```json
{
  "plan": [{"kind": "file", "path": "PLAN.md", "artifact": "plan"}],
  "check-tests": [
    {"kind": "file", "path": "SKEPTIC.md", "artifact": "skeptic"},
    {"kind": "scratch", "path": "tmp"}
  ],
  "adjudicate": [
    {"kind": "file", "path": "RULING.md", "artifact": "ruling"},
    {"kind": "scratch", "path": "tmp"}
  ]
}
```

Preserve native document demands, destinations and `role=read`. Skeptic
mutation and adjudication reproductions use disposable copies in declared
scratch. A renamed job with identical declarations gets identical output
treatment; plain reviews with omission or `[]` gain no writes. Runtime
authorization never searches prompt prose or branches on these names.

Task owns a deterministic deliverable section, consumed by launch on every
initial and resumed worker brief regardless of harness schema transport.
After removing trailing CR/LF from the rendered native prompt, before any
appended envelope schema, append two LFs and `Declared job outputs:` followed
by LF. Visit entries in declaration order. Substitute the canonical absolute path
and declared key into these exact line templates; each substitution is a
JSON string literal (double-quoted, ASCII-escaped with lowercase hex for
non-ASCII characters, no optional slash escaping or shell expansion), and
each line ends in LF:

```text
Required file: <path>. Write a non-empty document; set artifacts[<artifact>] to <path>.
Scratch subtree: <path>. Temporary work only; no artifact is required; TMPDIR is <path>.
```

For omission or `[]`, the only following line is
`None. No additional worker output write grant.` plus LF. No key is chosen
from prose or inferred from the filename. For canonical `out/` at
`/jobs/example/out`, check-tests renders exactly:

```text
Declared job outputs:
Required file: "/jobs/example/out/SKEPTIC.md". Write a non-empty document; set artifacts["skeptic"] to "/jobs/example/out/SKEPTIC.md".
Scratch subtree: "/jobs/example/out/tmp". Temporary work only; no artifact is required; TMPDIR is "/jobs/example/out/tmp".
```

Rendering communicates an admitted declaration; it cannot authorize a
grant. Later catalogue/prompt alignment must remove contradictory output
instructions while retaining native work requirements, and test the exact
key/path pair for each job and a renamed equivalent. No current prompt is
silently changed here. Permission failures cannot fall back to inline
prose. The specific inline planning reassignment persists until its
transition is independently defined and tested, without becoming a new
`outputs` kind or standing report mode.

### Output acceptance

For every `file`, `artifacts[artifact]` must equal the canonical absolute
path rendered to the worker and resolve to that declared regular file,
non-empty in bytes, under the bound job `out/`. Equality is exact string
equality of the decoded handle and the rendered absolute path value;
a different spelling that resolves to the same file does not satisfy it.
This deliberately tightens the plan's resolving-handle language for newly
declared outputs. It neither retroactively invalidates historical records
nor removes the existing narrow inline planning transport exception.
Task's [envelope.py](envelope.py)
remains the single authority for bounded, non-empty, single-line handles,
counts and status/verdict semantics. Launch consumes that validation and
adds filesystem/attempt custody checks; it must not copy those semantic
rules into another validator. If a bound path cannot be represented as a
valid handle, admission refuses `outputs-path` before child execution.

Missing files, a missing/wrong key or handle, unreadable evidence, unsafe
types/links or unverifiable custody prevent `status=ok`. Dispatch records
each accepted file's digest and current-attempt custody. Other evidence
handles remain references and confer no write authority. Scratch is not a
substitute report and is never automatically published. Prior attempt
reports remain prior evidence; current completion needs new production or
explicit verified reuse as specified by dispatch. Changed read-role HEAD
or snapshot residue still invalidates even when every output is present.

The [runtime adoption checklist](../dispatch/CONTRACT.md#c2-runtime-adoption-dependencies)
requires task semantic-validator integration into launch, including optional
write-job commit transport and the narrow inline exception, catalogue/prompt
alignment, independently authored tests and fresh capability proof. These
are later dependencies, not effects of this two-file contract.

## Dispatch ownership

Target: [dispatch](../dispatch/CONTRACT.md) consumes task's jobs and envelope
semantics plus harness isolation/budget wiring. The declared edges are
`dispatch → task` and `dispatch → harness`; task must not depend on
dispatch, harness or lane-policy implementation. The historical
`ops/contracts/imports.json` is absent at the measured baseline, so this
is a declared boundary, not a claim of an installed import gate.

`jobs.json` stays here — it is data the dispatch app reads by path,
not an import — and so do `run.py`, `envelope.py`, `fileset.py`, and
`verify.py`.
The manual/dormant task vendor path awaits a later explicit tested refusal
or owner-admitted retirement with supported behavior accounted for.
Fileset/staging parity is not required for dispatch/go/ladder convergence;
dispatch's existing tested `mode-unavailable` refusal remains in force.
