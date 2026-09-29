# Control-plane roles and tools

This is the reference for the implemented normal MCP interface in this repository.
[Setup](local-agent-readiness.md) configures the local services;
[operator documentation](../devtools/OPERATIONS.md) covers their backing APIs.
Each line in a tool example is a separate MCP call.

## Responsibilities and context

**CO is the session the person works with directly.** It holds the broader intent,
sets the authorized objective and boundaries, and assesses the overall outcome.
**XO reports to CO** and organizes, monitors and steers live collaborators.
Specialists receive the context and capabilities needed for their responsibility.

| Concept | Meaning |
| --- | --- |
| Work order | The numbered overall effort and integrated result: objective, completion criteria, boundaries, decisions and evidence. |
| Job | A bounded contribution to a work order; its source changes are delivered through one PR into that work order. |
| Role | The tools and default editable paths available to a participant. |
| Work binding | The work to which that role's calls and context apply. |
| Reporting relationship | Where findings, questions, results and guidance go. |

The services supply repository, workspace, branch, target, PR and artifact context.
Agents name responsibilities and request outcomes. Returned evidence/checkpoint
references identify information; they do not retarget the caller's work.

CO resolves questions requiring broader intent. XO handles coordination and
execution decisions within the brief. Specialists investigate and act within their
responsibilities, asking for guidance when needed. A message does not grant new
role or work authority.

## Role catalog

Every bound role gets **`onboard`, `skill_read`, `work_context`, `work_report`, `guidance_request`**.
Read the [role onboarding reference](role-onboarding.md) for customized responsibilities
and skill catalogs shared across all supported harnesses.
With a project configured, specialists also get **`work_inspect`**. Enabling
`project.development` adds **`framework_inspect` and `work_check`** for specialists.
The **editing tools** below are `work_save`, `work_refresh`, `work_recover`,
`work_submit` and `review_respond`.

| Role | Additional control-plane tools | Default Serena source access |
| --- | --- | --- |
| CO | `direct`, `monitor`, `conclude`, `restart_xo` | None |
| XO | `orchestrate`, `monitor`, `steer`; with a project: `work_inspect`, `work_refresh`, `work_submit`, `review_respond`; with development enabled: `work_check` | None |
| Coder (`coder`) | Editing tools; `framework_generate` | Product paths |
| Audit (`audit`) | `review_record` | Read-only review snapshot |
| Docs (`docs`) | Editing tools | `docs/` and `README.md`; other source read-only |
| Research (`research`) | Shared and specialist inspection/reporting tools | Read-only source |
| Test Writer (`test_writer`) | Editing tools; `framework_generate` for `make:test` | `tests/` and PHPUnit configuration |
| Architect (`architect`) | Editing tools | `docs/`; other source read-only |

Serena is a separate provider, enabled by `project.serena.image`. It exposes
`serena_repl` to configured specialist jobs. The operator can customize editing
paths. The current research profile covers repository material, supplied sources
and retained evidence; a general external web-search provider is not configured.

An unbound member gets only `work_context`. The external member explicitly
appointed as CO also gets `onboard`, `skill_read`, `direct` and `monitor` before its first work order.
Member names alone confer no role. Normal connections cannot invoke the operator
catalog, even by guessing a backing capability's name.

## Shared context, reports and guidance

| Tool | Use |
| --- | --- |
| `work_context` | Read the supplied brief, scoped activity, incoming messages or evidence. |
| `work_report` | Retain and route progress, findings, blockers, recommendations or results, optionally with evidence. |
| `guidance_request` | Route a question or request for assistance through the reporting relationship. |

The MCP initialization includes the current brief. Managed Codex and Claude also
receive it in startup instructions; Grok receives MCP instructions and context with
its first live delivery. Changed briefs accompany subsequent live delivery.
Unchanged briefs and the CO's whole conversation are not copied into every message.

```json
{"name":"work_context","arguments":{}}
{"name":"work_report","arguments":{"kind":"finding","text":"The installed service already supports this behavior."}}
{"name":"guidance_request","arguments":{"text":"Should this behavior also apply to existing records?"}}
{"name":"work_report","arguments":{"kind":"result","text":"Validation evidence","evidence":{"name":"observations.md","content":"Measured results..."}}}
```

`work_context.section` accepts `brief`, `activity`, `messages` or `evidence`.
Continue listings with the returned `next_after` as `after`. A returned `reference`
retrieves an update/message or a bounded artifact read; continue artifact reads
with `next_offset` as `offset`.

Reports and guidance accept `responding_to` with an update/message reference.
The service routes the response in its original work context. Responding to an
incoming message also acknowledges it. Agents do not choose recipient IDs or
perform a separate acknowledgement step.

Reports, evidence associations and outbound messages commit together. Identical
contents and binding reuse the report on retry. A failed evidence publication can
leave an unlinked blob for reuse; it does not expose a partially published report.
CO reports without a recipient are retained as `recorded_for_user`.

A specialist reads its job and shared work-order material. Command-level private
reports and evidence stay with the relevant participants. Scope checks apply to
references, listings and live delivery. In-flight reports retain the binding under
which they started; subsequent calls use the current binding.

## CO and XO tools

| Role / tool | Outcome |
| --- | --- |
| CO — `direct` | Establish or revise the current objective, completion criteria and boundaries; bind XO and deliver its brief. |
| CO/XO — `monitor` | Read scoped progress, capacity and cleanup status; inspect named work or the combined delivery. |
| CO — `conclude` | Deliver the inspected, passing integrated result, retain the assessment and release the team. |
| CO — `restart_xo` | Replace XO's conversation using current runtime policy while retaining its work and team. |
| XO — `orchestrate` | Create/update named responsibilities, bind suitable configured collaborators and start their live sessions. |
| XO — `steer` | Guide, pause, resume, stop or replace collaborators; revise a named brief or accept/cancel a named job. |

`direct` requires `title`, `objective`, `done_when` and `constraints`. Its first call
creates the work order and claims an available XO slot. Later calls revise that
work order and deliver the affected briefs. CO remains the person's existing session.

`orchestrate.work` contains up to four responsibilities per call, each with `name`,
`role`, `objective`, `done_when` and `constraints`. Repeating a name and role updates
the same job/collaborator. Names are case-insensitive within the work order.
One producer and an optional auditor can share the job name with distinct briefs.
The auditor's brief does not overwrite the producer's completion criteria.

Runtime choices belong to the operator's [role and vendor policy](shared-runtime-config.md).
Neither tool takes harness/model/reasoning selectors. The service allocates role
instances and starts [owned tmux terminals](tmux-control.md). Existing collaborators
keep their launch settings. Failed allocation batches roll back jobs, bindings and messages.

The following illustrates an authorized product job, not a request to implement it:

```json
{"name":"direct","arguments":{"title":"Project summary","objective":"Provide a basic project summary command","done_when":"The command and tests meet the agreed behavior","constraints":"Use native Symfony capabilities; keep devtools unchanged"}}
{"name":"orchestrate","arguments":{"work":[{"name":"Summary command","role":"coder","objective":"Implement the agreed summary command","done_when":"Generated command, behavior tests and checks pass","constraints":"Use installed Makers and attributes; product paths only"}]}}
{"name":"steer","arguments":{"action":"guide","work":"Summary command","direction":"Inspect installed services before adding another one"}}
{"name":"monitor","arguments":{}}
```

`monitor` returns bounded collaborator and job listings. Continue with the returned
`next_offset` or `next_job_offset` as `offset`. CO sees its work-order team; XO sees
its descendants and jobs. Usage is the latest raw observation, not an invented cost
or an additive total. Missing usage stays unknown.
The default `section="overview"` shows progress. With a named `work`, the default
shows its review packet. Omit `work` and select `section="review"`, `"ci"` or
`"feedback"` to inspect the integrated work-order delivery.

For live steering, omit `work` to address the team or name a responsibility. An
optional `role` filter selects its producer or auditor. `guide` retains direction;
`pause` retains the conversation and prevents new work actions; `resume` clears the
pause and starts a stopped session if needed. `stop` requests orderly shutdown and
preserves the unfinished job and binding. Pause is not a native mid-token interrupt.
Stopping/restarting creates a new native conversation.
`replace` requests shutdown and a fresh conversation using current vendor policy;
include a reason in `direction`. CO can do the same for XO using `restart_xo`.
See [session handover](session-handover.md) for switching the user-facing CO and
the retained context and generation boundaries.

A named producer brief can revise `objective`, `done_when` or `constraints`; it does
not rewrite CO's work-order objective. Commands recheck scope when committing.
Pending startup survives MCP restart and is serviced while a team MCP server is
connected. Startup failures are retained and sent to the supervisor; `direct`
retries XO startup, and `steer(action="resume")` retries a collaborator.

## Workspaces and Git

The service prepares an integration workspace for each work order and a separate
workspace for each job. Managed harnesses and file-backed evidence use the bound
workspace automatically. Jobs incorporate accepted contributions through their
parent work order. Git operations, Makers, checks and Serena calls coordinate
through scoped locks. Branch routing and local paths are service responsibilities.

| Tool | Outcome / input |
| --- | --- |
| `work_inspect` | Read changes, checkpoints, scope, retained operations or delivery evidence. |
| `work_save` | Checkpoint allowed changes and retain a diff; takes `note`. |
| `work_refresh` | For a job, checkpoint and incorporate accepted contributions plus current development changes. Resolve any listed conflicts with the editing tools, then `work_save` and refresh again. For XO, synchronize the integrated result. |
| `work_recover` | Restore a returned `checkpoint` as a new commit; takes `reason` and preserves current work first. |
| `work_submit` | Submit a checked contribution, or let XO submit the combined result once jobs are finished; takes `summary`. Publication and CI observation are automatic. |

For review fixes before acceptance, keep working in the same job and call
`work_submit` again. It updates the existing PR and starts observation of the new
CI result. XO inspects the changed revision again before accepting it; GitHub's
required checks still apply. Branch names and PR targets remain service-managed.

`work_inspect` defaults to `overview`. Use `section="changes"` with optional `path`
and `offset` for bounded local diffs. `section="operations"` reads retained long
operation status. Delivery sections are described below.

Default coder paths cover `src`, `config`, `packages`, `tests`, `templates`,
`assets`, `translations`, `public`, `migrations`, Composer/Symfony lockfiles and
PHPUnit configuration. Other editing roles have the narrower paths in the role
table. The brief includes the editable scope. Unexpected changes remain available
for guidance; checkpoint/submission refuses changes outside the role's paths.
Git hooks and external diff programs are disabled in managed operations.

Submission retains completed checkpoints and publication across retry. With
`project.development` enabled, failed checks or files changed by checks return
`needs_attention` with evidence. Submission does not accept the job or merge its PR.

## Symfony Makers, Mate and checks

These tools use the installed application in the job worktree. `project.development`
enables them; each worktree owns its locked Composer installation.

| Tool | Outcome |
| --- | --- |
| `framework_inspect` | Discover installed Maker metadata, or inspect/call an installed Mate diagnostic. |
| `framework_generate` | Run an installed basic Maker with structured arguments and options. |
| `work_check` | Run a named configured check or the full configured suite, with retained evidence. |

```json
{"name":"framework_inspect","arguments":{"kind":"makers","name":"make:command"}}
{"name":"framework_generate","arguments":{"maker":"make:command","arguments":{"name":"app:example"}}}
{"name":"framework_inspect","arguments":{"kind":"mate","name":"server-info","parameters":{}}}
{"name":"work_check","arguments":{}}
```

Omit `name` to list Makers or Mate tools. For a named Mate tool, omit `parameters`
to inspect its schema; supply an object, including `{}`, to call it. Maker inputs
come from installed Console metadata. Symfony performs the generation using its
current attributes and conventions. Test writers can generate through `make:test`.
A Maker needing an additional bundle or interactive answers reports its actual
failure and preserves partial changes for inspection.

Default validation is container lint, YAML lint and PHPUnit. Operators can configure
named fixed commands; agents provide a name, never a shell command. These application
commands and Composer plugins run as the local service user. The tool interface does
not provide OS containment for application code.

Framework inspection, generation, checks and configured submission return retained
operation receipts promptly. Compact completion notices (including failed-check
counts) and evidence references are delivered to the original worker and supervisor
while their scope still covers that work. Full results remain available through
`work_inspect(section="operations")`. Workers survive
an MCP disconnect. An identical active call reuses its receipt; a lost worker becomes
`uncertain` without automatically replaying external effects. Pausing prevents new
processes; an already-running command finishes or reaches its timeout.

## Serena v2 REPL

Serena is the separate source-navigation/editing provider. Managed Codex, Claude
and Grok sessions attach it automatically for configured specialist jobs. CO and
XO do not receive it. External specialist clients can attach the gateway described
in [operator setup](../devtools/OPERATIONS.md#external-specialist-connections).

```json
{"name":"serena_repl","arguments":{"code":"s.info()"}}
```

The gateway supplies the workspace and persistent session. `s.info()` and targeted
facade documentation support progressive discovery. Python variables, functions and
classes persist within the provider session; large output becomes job evidence.
A restart loses Python variables while preserving source files and managed evidence.
The beta source revision and PHPactor dependency are pinned in the
[Dockerfile](../devtools/serena/Dockerfile); the image retains upstream source/license.

The REPL executes unrestricted Python inside its container. The container has no
runtime network, host home/credentials, control-plane database or Docker socket.
Source is mounted read-only with only the editing role's paths writable; audit and
research source stay read-only. Provider configuration/cache/memories have a separate
private mount. Writable aliases/symlinks are rejected.

Each call holds the job lock. The container pauses before releasing it and resumes
on the next call, preserving REPL state while preventing background Python from
racing Git, Makers or checks. Work pause rejects new REPL calls. Role, job,
supervisor or provider-configuration changes invalidate an existing gateway.
Refreshing an auditor's source snapshot also resets its provider before further use.
Force-killed providers can require operator cleanup of a leftover container.

## Review, CI and external feedback

XO can add `role="audit"` to the producer's named job. Audit uses a detached snapshot
of the submitted revision, or the current checkpoint before submission. Producer
edits cannot silently change that view. `work_inspect(section="review")` refreshes
the snapshot and returns the PR, CI, findings and changed files.

| Inspection | Details |
| --- | --- |
| `section="review"` | Changed-file `page`; optional `path`/`offset` for a provider patch. GitHub may omit large/binary patches. |
| `section="ci"` | Failed steps, annotations and log excerpts for the bound PR. `page` continues two failed checks at a time; `offset=0` begins consecutive log reads. |
| `section="feedback"` | GitHub conversation, review and inline comments, with file/line/revision context. Continue with `page`. |

Diagnostics retain a full packet as scoped evidence and return a small preview.
Read its reference through `work_context`. Missing or expired logs are explicit.
CO/XO use the same sections through `monitor(work="Job name", section="ci")`
or `section="feedback"`. Neither diagnostic section replaces review inspection
before acceptance. CI changes are delivered to the worker and its current supervisor.

| Tool | Outcome |
| --- | --- |
| `review_record` | Audit records `ready`, `changes_requested` or `comment` with a `summary`, against its inspected revision. |
| `review_respond` | Producer responds with `text`; optional `review` selects a returned review reference. XO supplies a work-order thread reference from `monitor(section="feedback")` and can set `resolve:true` after addressing the finding. |

The service retains and routes findings/responses to the job participants and XO.
GitHub receives a COMMENT review; a local `ready` conclusion does not fabricate a
formal approval from an independent GitHub account. Repository review rules apply.
Stable markers reconcile successful publications after lost responses; unknown
write outcomes are not silently repeated.

## Acceptance and turnover

XO inspects the current delivery with `monitor(work="Job name")`, then uses
`steer(action="accept", work="Job name", direction="Assessment")`. Acceptance
requires the same inspected PR revision, passing CI, the managed branch/target and
a clean producer workspace at that revision. The service merges into the work order through normal
GitHub rules, retains the assessment/evidence and marks the job done.

For report-only work, a retained `work_report(kind="result")` and no unsubmitted
source changes are required. XO can assign an auditor when the responsibility
needs review.

`steer(action="cancel", work="Job name", direction="Reason")` preserves the
worktree, PR and evidence and marks the job cancelled. An existing PR remains open
for the owner to decide its disposition. Acceptance/cancellation releases bindings
and requests shutdown; slots become reusable after the native processes stop.

Completed jobs stay visible in `monitor`. New responsibilities use new names and
start from the integrated work. Merged job worktrees and audit snapshots are
retired after their processes and providers stop. Unexpected changes remain for
inspection; cleanup reports its status without blocking other work. Messages,
checkpoints, assessments, PR references and artifacts remain available.

When every job is done or cancelled, XO uses `work_submit(summary)` to validate
and submit the combined result. Both Codex Code Review and Security Review are
requested for that commit. Review and CI changes arrive as scoped notifications.
XO inspects findings with `monitor(section="feedback")`, coordinates fixes through
jobs, and uses `review_respond(text, review, resolve=true)` to explain and resolve
addressed threads. After integrating fixes, XO submits again for reviews of the new
commit. Missing or stale reviews remain pending; a clean CI result alone is not
review completion. Job PRs do not request these additional reviews.

CO inspects the combined outcome with `monitor(section="review")`, then calls
`conclude(assessment)` after CI and both current reviews pass and findings are
addressed. Delivery verifies the current result and releases the
remaining team. The integration workspace retires after this final merge and
shutdown. Report-only work with no source changes can conclude without a PR.
The next authorized `direct` creates a new work order. Submission, contribution
acceptance and delivery of the overall outcome remain distinct observations.
