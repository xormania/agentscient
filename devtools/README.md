# MCP tools for live work

This directory provides role-bound MCP tools for shared work, backed by live
communication, telemetry, work orders/jobs, artifacts, and GitHub PR/CI services.
Normal sessions expose `work_context`, `work_report`, and `guidance_request`
directly, with command tools added for CO and XO. Services supply context and
handle routing, work records, configured collaborators, startup, and storage.
Python 3.11+ and SQLite from its standard library are sufficient on Linux/macOS.
Native launchers require the selected locally
installed, authenticated harness. Background Claude sessions also require tmux.

This implements shared work, command outcomes, managed workspaces, installed
Symfony development tools and validation from the
[control-plane design](../docs/control-plane-roles-and-tools.md). Serena v2 REPL is
a separate workspace-bound provider; final review/acceptance is being added. There is no dispatcher, task engine,
grant system, audit ladder, source editor or general shell capability.

## Agent-facing tools

| Tool | Outcome |
| --- | --- |
| `work_context` | Read the supplied brief, scoped activity, incoming messages, or evidence. |
| `work_report` | Retain and route progress, findings, blockers, recommendations, results, or responses, with optional evidence. |
| `guidance_request` | Retain and route a question or request for assistance through the reporting relationship. |

All eight initial profiles (`co`, `xo`, `coder`, `audit`, `docs`, `research`,
`test_writer`, `architect`) share these three core tools once bound to work.

| Role | Additional tools |
| --- | --- |
| CO | `direct`, `monitor` |
| XO | `orchestrate`, `monitor`, `steer` |
| Specialists | Managed workspace inspection; editing roles also get checkpoints, recovery, refresh and PR submission. |

An unbound member can only call `work_context`, unless explicitly appointed as CO
in trusted team configuration. That user-facing session also gets `direct` and
`monitor` before a work order exists. Member names do not confer authority.
No normal connection can access the operator catalog.

The initialization response includes the current brief. Managed Codex and Claude
also receive it in their startup instructions; Grok receives MCP instructions and
context with its first live delivery. Changed briefs are included with the next
live delivery; unchanged briefs are not repeated in every peer message. Command
tools proactively queue the affected current briefs through the same live transport.

Examples of direct tool arguments:

```json
{"name":"work_context","arguments":{}}
{"name":"work_report","arguments":{"kind":"finding","text":"The existing service already supports this contract."}}
{"name":"guidance_request","arguments":{"text":"Should this behavior apply to existing records?"}}
{"name":"work_report","arguments":{"text":"Here is the evidence","evidence":{"name":"observations.md","content":"Measured results..."}}}
```

Optional `section` values for `work_context` are `brief`, `activity`, `messages`,
and `evidence`. Listings are bounded; use returned `next_after` as `after` for
another page. A returned `reference` retrieves a complete update/message or a
bounded artifact read. Pass an artifact's `next_offset` as `offset` to continue.
References are information handles, never permission to change the active work.

`responding_to` on a report or guidance request accepts an update/message reference.
The service routes the response to its author with the original work association.
Responding to a shared work-order item from a job retains the caller's narrower
job scope. An answer to an incoming message also records its acknowledgement;
agents do not need an acknowledgement tool. A submitted live message alone is not
proof that the agent read or acted on it.

Reports and their outbound messages commit together. Identical report contents,
evidence, response reference, and binding reuse the same record on retry, including
after restart. Evidence uses the existing managed artifact service; a failure after
saving evidence can leave a private, unlinked artifact, reused on retry. The visible
evidence association commits with its report and audience. Delivery is reported
as observed (`queued`, `submitted`, or `uncertain`), not as inferred completion.
CO reports without a recipient are saved and returned as `recorded_for_user`.

A job binding can read that job and shared work-order material. A work-order binding
can read material across its jobs. CO/XO reports at work-order level and their
attached evidence are visible to the relevant command scope and their participants;
they do not automatically appear in specialist context. References, context listings, and live delivery
enforce that scope. Artifact reads omit other work associations and provider
metadata from the backing catalog. Agents cannot supply a work-order/job/recipient
override or invoke raw operations through a guessed name or the former discovery
wrapper. The server checks each call, including calls on already-open connections.
In-flight reports retain the binding under which they started; subsequent calls use
the current binding. Commands recheck authority inside their write transaction and
reject a stale call before changing work. These are service boundaries, not a claim of OS isolation.

## CO and XO command outcomes

With `project` configured, a bound specialist also receives `work_inspect`.
Editing roles receive `work_save`, `work_refresh`, `work_recover`, and `work_submit`.
Their brief includes the role's editable paths. Repository, branch, worktree and
target selection remain service responsibilities.

CO calls `direct` with the authorized `title`, `objective`, `done_when`, and
`constraints`. The first call creates the work order, binds CO and an available XO,
queues direction, and records a pending managed startup. Later calls revise that
same work order. A work-order change reaches XO and affected collaborators; private
CO discussion is not copied into those briefs. Responses follow each collaborator's
reporting relationship. CO remains the session used by the person, without spawning
another CO model.

XO calls `orchestrate` with up to four named responsibilities in `work`. Each has
`name`, specialist `role`, `objective`, `done_when`, and `constraints`. The service
creates or updates the job, claims an available configured member, binds its scope
and reporting relationship, queues its brief, and records pending startup. Repeating
a name updates the same job and collaborator. Names are stable, case-insensitive
within the XO's work order. A failed batch rolls back its job, binding, and message
changes, including when there are too few matching slots.

Both tools accept optional `selection` filters (`harness`, `model`, `reasoning`);
for `orchestrate`, selection belongs to each responsibility. These select configured
slots, without accepting binaries, paths, shell commands, or arbitrary launch options.
An existing collaborator keeps its session settings. Changing the local configuration
applies on a later restart; active settings are taken from the recorded session start.
Absent settings on older sessions remain unknown.

`monitor` returns ten collaborators per page, current work, latest reports, observed
session state, pending startup/errors, latest bounded usage observations, and available
configured capacity. Continue with returned `next_offset` as `offset`. XO sees its
own descendants; CO sees its work-order team. Missing usage is unknown, and raw
observations are not added together as if they were independent totals. Session
activity and reports do not establish that an objective is complete.

XO calls `steer` with `action` (`guide`, `pause`, `resume`, `stop`), an optional work
name, and optional `direction`. Omitting the name addresses its team. For one named
responsibility, it can also revise `objective`, `done_when`, or `constraints`.
These change that job's brief, never CO's work-order objective or boundaries.

- `guide` retains direction and delivers the updated brief.
- `pause` retains the live conversation and marks work paused. Reports and guidance
  remain available. Paused command roles cannot expand or restart work. This asks
  the current model turn to pause; it is not a native mid-turn interrupt.
- `resume` clears the pause and starts a stopped managed session if necessary.
- `stop` pauses work and requests an orderly managed-session shutdown. Work,
  bindings, messages and evidence remain. Restarting after stop creates a new native
  conversation; pause/resume of a running session preserves its conversation.

Examples of normal MCP calls:

```json
{"name":"direct","arguments":{"title":"Prepare the Symfony starting point","objective":"Make local product development usable","done_when":"The bounded local workflow has evidence","constraints":"Do not implement the product"}}
{"name":"orchestrate","arguments":{"work":[{"name":"Maker access","role":"coder","objective":"Expose the basic installed Makers through the prepared development tools","done_when":"Generation is demonstrated in the correct workspace","constraints":"Use installed Symfony capabilities; no custom project patterns"}]}}
{"name":"steer","arguments":{"action":"guide","work":"Maker access","direction":"Inspect the installed command metadata before adding infrastructure"}}
{"name":"monitor","arguments":{}}
```

Managed startup is asynchronous. Pending intent survives MCP restart and is serviced
while a team MCP server remains connected. Launches are serialized per member and
check the binding again before starting a native session. Startup failures are
reported to the supervising role and retained for monitoring; retry with `direct`
for XO or `steer`/`resume` for a collaborator. External slots connect their own MCP
clients and are not reported as managed launches. Queued direction is not proof
that a model received or followed it. Superseded queued directions remain in history
without being delivered; a delayed live direction renders the current brief.

This slice supports one current work order per CO and one collaborator per named
job. Completed-job turnover and further specialist
delivery outcomes are still to be integrated. Stopping a collaborator does not
release its binding or mark its job done.

## Managed job workspaces and delivery

Add trusted project configuration to the team's `team.json` before starting product
work. `checkout` is an existing local Git checkout; `target` is its integration branch.
Authentication for the Git remote and GitHub is supplied by the operator's installed
Git/GitHub configuration, never by agent arguments.

```json
{
  "project": {
    "checkout": "/absolute/path/to/agentscient",
    "repository": "uscient/agentscient",
    "target": "dev",
    "remote": "origin"
  }
}
```

Each job gets an owned worktree and branch outside the source checkout and private
control-plane state. Managed harnesses start in that worktree; artifact file sources
use it as well. Creation is retryable and serialized. Git changes, checkpoints,
refresh, recovery and submission share a per-job lock, which provider calls also
need to use. This is coordination between managed services, not OS isolation.

| Tool | Outcome |
| --- | --- |
| `work_inspect` | Read changed-file summaries, bounded diffs, checkpoint history and editable scope. |
| `work_save` | Commit allowed changes as a checkpoint and retain diff evidence. |
| `work_refresh` | Preserve changes, fetch the configured target, and merge it; abort conflicts while retaining the checkpoint. |
| `work_recover` | Restore a checkpoint belonging to this job as a new commit, preserving current work first. |
| `work_submit` | Checkpoint, push without force, create/reuse the job's PR, start CI observation, and report the result. |

`work_inspect(section="changes", path="src/Example.php")` reads a bounded diff.
Use `next_offset` for more. `work_save` takes a `note`; `work_submit` takes a
`summary`. Recovery takes a returned `checkpoint` reference and a `reason`.
These references identify retained evidence, not arbitrary Git revisions.

Default coder paths cover the Symfony product (`src`, `config`, `packages`, `tests`,
`templates`, `assets`, `translations`, `public`, `migrations`, Composer/Symfony lock
files and PHPUnit configuration). Test writers own tests; docs and architect profiles
own documentation. `devtools` and control-plane configuration are outside those
defaults. The operator can explicitly set `project.paths` by role. Unexpected
changes are preserved and reported for guidance; they are not silently discarded.
Optional `project.identity` has `name` and `email` when a dedicated commit identity
is needed; otherwise Git uses its configured identity. Git hooks and external diff
programs are disabled in managed operations.

Submission does not merge a PR or mark the objective done. CI observation is retained
by the existing GitHub service. A failed remote step preserves completed checkpoints
and publication; retry reuses the branch and PR. With `project.development`
configured, submission runs the configured checks before publication. Failed checks
or files changed by checks return `needs_attention` with evidence and the preserved
checkpoint. Source authoring is a separate Serena integration.

## Installed Makers, Mate and validation

Add `"development": {}` inside trusted `project` configuration to enable the
installed Symfony tools. Local PHP and Composer must satisfy `composer.lock`.
Optional `php` and `composer` settings select installed binaries; an absolute PHP
path also supplies its directory to PATH so `vendor/bin/mate` uses that runtime.
Each worktree gets its own locked Composer install. Dependencies are refreshed when
Composer metadata changes; another checkout's vendor directory is never symlinked.

| Tool | Outcome |
| --- | --- |
| `framework_inspect` | Discover installed Makers and their real inputs, or inspect/call installed Mate diagnostics. |
| `framework_generate` | Run an installed basic Maker with structured arguments/options; available to coders and test writers. |
| `work_check` | Run named configured checks or the complete configured suite, retaining measured results. |

Examples:

```json
{"name":"framework_inspect","arguments":{"kind":"makers","name":"make:command"}}
{"name":"framework_generate","arguments":{"maker":"make:command","arguments":{"name":"app:example"}}}
{"name":"framework_inspect","arguments":{"kind":"mate","name":"server-info","parameters":{}}}
{"name":"work_check","arguments":{}}
```

Omit `name` to list available Makers or Mate capabilities. A named Mate tool with
no `parameters` returns its schema; supply an object (including `{}`) to call it.
Maker inputs come from installed Console metadata, including repeated options.
The generator stays Symfony's own implementation, including its current PHP
attributes and autoconfiguration conventions. Global console/runtime options are
service-managed. Test writers can generate with `make:test` only. A Maker that
needs an uninstalled bundle or interactive answers reports its actual failure;
partial changes are preserved and listed, including changes outside role paths.
Workspace checkpoint/submission refuses those out-of-scope changes.

Default checks are Symfony container and YAML validation plus PHPUnit. The operator
can replace `development.checks` with a map of names to fixed argv arrays and set
`check_timeout` (default 600 seconds per check). Agents supply only a check name.
These installed application commands run as the local service user. This is a
restricted tool interface, not OS isolation from application code or Composer plugins.

Installation, inspection, generation, checks and configured submission return a
retained operation receipt promptly. Completion is automatically delivered to the
original worker and its supervisor, while their bindings still include that work.
Results and artifacts retain the original job. Use
`work_inspect(section="operations")` to inspect recent progress after reconnecting.
An identical active call reuses its operation; another concurrent operation for
the job is rejected. Workers survive MCP disconnect, and a lost worker becomes
`uncertain` rather than silently repeating external effects. This executes fixed
service actions behind tools; it does not dispatch agent tasks or replace live
conversations. Pause prevents a new process starting; an already-running process
finishes or reaches its timeout, with the observed result retained.

## Serena v2 REPL as a separate provider

Build the pinned external provider once on the local Docker engine:

```sh
docker build --tag agentscient-serena:v2-beta devtools/serena
```

Add `"serena": {"image": "agentscient-serena:v2-beta"}` inside `project` in
`team.json`. The source is Serena's `dev-v2` commit
`b79e2a55f9d4072084977dd35bd07d31146d88b9`, with its PHPactor version and checksum
preinstalled for operation without runtime network. The image retains upstream
source and its GPL-3.0-or-later license. This repository only integrates the
separate MCP process. `serena.docker` optionally selects an installed Docker binary;
`serena.memory` sets its container memory limit (default `2g`).

Managed Codex, Claude and Grok attach the separate `serena` MCP server automatically
for configured specialist jobs. CO and XO do not receive it. External specialist
clients can attach the same gateway with `python3 devtools/run.py serena --state
/absolute/private/state --member configured-member`. They still attach the normal
control-plane server separately.

The provider exposes one tool, `serena_repl`, accepting only `code`. The gateway
supplies the job workspace and persistent session. Start with `s.info()` or
`s.info("lsp", "edit")`; use Serena's facade documentation progressively. Variables,
functions and classes persist for that provider session. Large output is retained
as job evidence. A process restart loses Python variables while preserving source
files and managed evidence; the gateway reports timeout/restart failures explicitly.

The v2 REPL executes unrestricted Python. Hiding its shell facade would not provide
a workspace boundary. The supplied container has no runtime network, host home,
credentials, Docker socket or control-plane database mount. The project is mounted
read-only, with only the current editing role's configured paths writable. Audit
and research source mounts stay read-only. Provider configuration/cache/memories
have a separate private mount. Writable directory aliases/symlinks are rejected.
This protects host paths exposed through this provider; application checks and
Composer still execute locally as described above.

Each REPL call holds the same job lock as Git, Makers and validation. Its container
is paused before releasing that lock and resumed for the next call, retaining REPL
state while preventing background Python from racing another managed operation.
Work pause rejects new REPL calls. Role, job, supervisor or provider configuration
changes invalidate an existing gateway, requiring a fresh connection. Removing a
gateway stops its container; forcibly killing it or the Docker engine can require
the operator to remove a leftover `agentscient-serena-*` container.

CI builds this image and exercises real stdio MCP, persistent REPL variables,
PHPactor symbol navigation, the Serena edit facade, denied writes to protected
source, pause/resume and a control-plane checkpoint. This does not claim a live
authenticated vendor-model run.

## Set up a team

An operator runs this once from the repository checkout. State must be outside
the source worktree. The `external` member represents the MCP client from which
you manage the team; it does not spawn another model.

```sh
python3 devtools/run.py init \
  --state "$HOME/.local/state/agentscient-live" \
  --workspace "$PWD" \
  --co owner \
  --member owner:external --member codex:codex --member claude:claude --member grok:grok
```

Select only the harnesses you use. Edit that state directory's `team.json` to set
each member's `binary`, optional `model` and `reasoning`, and workspace. Different
members can use separate worktrees. Existing member identities cannot silently
move to a different harness or workspace; use a new member name for that change.
No model is selected by this repository.

Connect the user-facing CO through the normal MCP server, replacing these paths
with absolute local paths:

```json
{
  "mcpServers": {
    "agentscient_dev": {
      "command": "/absolute/path/to/python3",
      "args": ["/absolute/path/to/agentscient/devtools/run.py", "mcp",
               "--state", "/absolute/path/to/state", "--member", "owner"]
    }
  }
}
```

CO can now use `direct`; XO receives its tools and brief automatically. No operator
calls are required to construct that initial work/team. For an existing team, the
equivalent trusted appointment is top-level `"co":"owner"` in `team.json`; it must
name an external member. Removing a binding does not revoke that bootstrap
appointment: remove `co` from configuration as well to remove CO's bootstrap tools.

## Trusted setup and diagnostics

For trusted setup and diagnostics, add this temporary operator connection,
replacing the paths with absolute paths on your machine. The command must be your
Python executable. Managed agent profiles never include `--operator`; remove this
connection from any client used as an agent role after setup.

```json
{
  "mcpServers": {
    "agentscient_operator": {
      "command": "/absolute/path/to/python3",
      "args": ["/absolute/path/to/agentscient/devtools/run.py", "mcp",
               "--state", "/absolute/path/to/state", "--member", "owner", "--operator"]
    }
  }
}
```

On this operator connection, `tools/list` exposes `capability_search`, `capability_describe`, and
`capability_invoke`. Search returns five capabilities per page; describe supplies
the input schema. Invoke takes `{"capability":"name","arguments":{...}}`.

For importing existing work or repairing setup, the operator can create work and
bind roles from the top down. For example, with work order 1 and job 2:

```json
{"capability":"member_bind","arguments":{"member":"owner","role":"co","work_order":1,"brief":"Represent the user's intent."}}
{"capability":"member_bind","arguments":{"member":"codex","role":"xo","work_order":1,"reports_to":"owner","brief":"Coordinate the work within the stated boundaries."}}
{"capability":"member_bind","arguments":{"member":"claude","role":"coder","job":2,"reports_to":"codex","brief":"Implement the job using existing framework capabilities."}}
```

The reporting member must cover the child's work scope. XO reports to CO; CO
reports to the user. Cycles and mismatched work-order/job bindings are rejected.
Rebinding identical values is a no-op. `member_unbind` with `member` removes the
active binding; existing connections immediately lose report/guidance access.
MCP clients receive a tool-list-change notification when the advertised list changes.
Changing a supervisor's scope can require updating its collaborators' reporting
bindings; a stale route reports an error instead of delivering into unrelated work.

Normal external clients use the same server configuration **without `--operator`**,
under the name `agentscient_dev`. Managed sessions are launched only after their
role/work binding exists. The CO/XO tools perform this setup behind their outcomes.

## Operator and backing-service capabilities

The remainder of this guide describes the operator surface and underlying services.
These capabilities are not advertised or invocable on normal agent connections.

| Capability | Purpose |
| --- | --- |
| `member_bind`, `member_unbind` | Configure or remove a trusted role/work/reporting binding |
| `peers` | Configured members, observed state, and actual native conversation IDs |
| `session_start`, `session_stop` | Start a configured member or request that it stops |
| `message_send` | Send a durable message with an idempotency key |
| `message_inbox`, `message_wait` | Read or briefly wait for incoming messages |
| `message_ack`, `message_retry` | Acknowledge reception or explicitly retry uncertain delivery |
| `telemetry_events`, `telemetry_usage` | Read paginated measured events and available native usage |
| `work_order_create`, `work_order_select` | Open a numbered work order or select existing work |
| `work_order_get`, `work_order_list`, `work_order_update` | Recover purpose, boundaries, progress, jobs and evidence |
| `job_create`, `job_select` | Open or select a bounded piece of a work order |
| `job_get`, `job_list`, `job_update` | Track a job's progress, branch and resulting PR |
| `work_link`, `work_unlink` | Associate references or existing artifacts with the work |
| `artifact_save`, `artifact_list`, `artifact_read` | Save a managed snapshot, find evidence, or read its contents |
| `pr_list`, `pr_get`, `pr_diff` | Find a PR, understand its current state, and inspect changes |
| `pr_open`, `pr_update` | Open/adopt the job's PR and maintain its description or draft/ready state |
| `pr_comments`, `pr_comment`, `pr_review`, `pr_threads` | Read feedback, post progress, review a revision, and handle discussions |
| `pr_merge` | Merge the inspected revision using the repository's allowed methods and rules |
| `ci_status`, `ci_failures` | Inspect observed CI and get failed steps, annotations and log excerpts |
| `ci_workflows`, `ci_run`, `ci_rerun`, `ci_cancel` | Discover workflows, explicitly start one, retry or cancel a run |
| `ci_watch`, `ci_watch_stop` | Receive CI changes through durable live messages |
| `ci_artifacts`, `ci_artifact_save` | Find CI outputs and retain an archive or report as managed evidence |

For example, invoke `session_start` with `{"member":"codex"}`, then `message_send`
with `{"to":"codex","body":"Your message","key":"unique-key-for-this-message"}`.
Starting a session reports observed startup state, not proof that the model has
received or processed anything. A recipient's explicit acknowledgement is separate.

## Work orders, jobs, and evidence

The **work-order number** is the enduring binding for an overall effort. It holds
the objective, completion criteria, boundaries, progress, and shared evidence.
**Jobs** are bounded pieces beneath it, normally delivered through individual PRs.
Each job belongs to one work order and records its repository, branch and resulting
PR. Several jobs and live members can contribute to the same work order.

Create a work order with `work_order_create`:

```json
{"title":"Artifact support","objective":"Keep evidence with the work",
 "done_when":"Agents can save and recover evidence through MCP",
 "constraints":"Do not change Symfony application code","key":"artifact-support"}
```

The result includes its stable numeric `work_order.id`, used as the `work_order`
argument throughout the tools. Creation selects it for this member. Then create a
job with `job_create`, supplying its own `title`, `objective`, and `done_when`, plus
optional `repository` and `branch`. That selects the job and its parent work order.
`pr_open` records the PR automatically. For a PR opened elsewhere, it can adopt the
existing PR by number; alternatively record its URL with `job_update`:

```json
{"pull_request":"https://github.com/owner/repository/pull/123",
 "status":"in_progress","next_action":"Review the storage checks"}
```

`job_get` returns the job together with its parent's purpose and boundaries.
`work_order_get` returns overall progress, a small page of job/PR summaries, and
linked evidence. Use `job_list` with the work-order number and `after` set to
`next_job` to continue the job list; use `after` set to `next_after` to continue
references. Discovery and listings stay bounded, and artifact contents are read
only when requested.

Messages, artifacts, tool events, and native observations inherit the member's
selection. A job ID implies its work-order number; mismatched pairs are rejected.
Supplying a work-order number alone associates activity at the overall level.
Replies inherit the original message's binding unless explicitly overridden.
Acknowledgement and delivery events retain that binding even when another member
has selected different work. Native observations carry the selection at observation
time; aggregate vendor usage is not a precise allocation of cost to individual jobs.
An in-flight MCP call keeps its original context if another call changes selection.

`job_select` without an ID clears only the job; `work_order_select` without a number
clears both. Selection persists across MCP process restarts. Records remain after
branches disappear and PRs merge. Work-tracking tools store references; GitHub
tools retrieve current provider state. Managed Git operations are described above.
Status (`open`, `in_progress`, `blocked`, `done`, `cancelled`) is freely editable.
Closing jobs does not automatically close their work order. Optional creation
`key` values let a caller retry without creating duplicate records.

Save a small report with `artifact_save`:

```json
{"name":"results.md","content":"# Verification\nThe storage checks passed."}
```

Or save an existing deliverable with `{"name":"report.pdf","source":"var/report.pdf"}`.
The tool attaches it to the selected work order and job and returns an artifact ID.
`source` is relative to that member's configured workspace and is streamed into a
managed snapshot. Changes or deletion of the original file do not change the saved
artifact. Absolute paths, escapes outside the workspace, and non-regular files are
rejected. The tool never writes into the workspace.

Inline content is limited to 8,000 characters to fit the MCP request frame. Use
`encoding:"base64"` for inline binary content, or `source` for larger existing files.
`media_type` is optional; the service infers it from the name. Repeating the same
name, content, media type and member reuses the artifact; changed content produces
a new ID and retains the earlier snapshot. `work_link` with `kind:"artifact"` and
the artifact ID as `reference` can reuse evidence in another work order or job.
`work_unlink` removes only that association.

`artifact_read` accepts the artifact ID and returns bounded UTF-8 or base64 content.
For more content, pass its `next_offset` back as `offset`; reads default to 16 KiB
and are limited to 32 KiB. `artifact_list`, `message_inbox`, and telemetry tools can
filter by `work_order` and `job`; without filters their existing whole-team/member
listing behavior is preserved. Work selection is convenient context, not a gate
required before communication or artifact storage.

## GitHub work through MCP

GitHub capabilities are discovered and invoked through the same three MCP entry
points. There is no raw API, arbitrary GraphQL, credential input, or command tool.
Repository/PR inputs normally come from the selected job. An explicit `job` uses
that job for the call without changing selection. Without a job, supply
`repository:"owner/name"` and `pr` where needed, or configure a default repository.

A typical sequence of capability arguments is:

```json
{"capability":"pr_open","arguments":{"base":"dev","summary":"What changed and why"}}
{"capability":"pr_get","arguments":{}}
{"capability":"pr_diff","arguments":{"path":"src/Example.php","revision":"<head SHA from pr_get>"}}
{"capability":"ci_failures","arguments":{"run":123456}}
{"capability":"ci_watch","arguments":{}}
{"capability":"ci_artifacts","arguments":{"run":123456}}
{"capability":"ci_artifact_save","arguments":{"artifact":789,"entry":"test-results.xml"}}
```

These are separate `capability_invoke` calls. The branch must already exist on
GitHub. `pr_open` defaults to a draft, includes the job's purpose/completion criteria
and work-order number, reuses an existing PR for that branch/base, and binds its URL
to the job. Use `pr_update` with `draft:false` when ready. Merging does not mark the
job or work order done; their completion criteria can include further work.

`pr_get` returns compact reviews, CI and observed blockers; `description_offset`
continues a long PR description using `next_description_offset`. `pr_diff` lists files
first; supplying a path returns a bounded patch and `next_offset`. GitHub may omit
or truncate large/binary patches. `pr_comments` lists conversation comments,
`kind:"review"` reviews, or `kind:"inline"` inline findings. Previews include IDs;
use `comment` and `offset` for full text. `pr_threads` pages review threads, supports
replies and resolution, and checks that a selected thread belongs to this PR.

`pr_review` and `pr_merge` require the inspected 40-character `revision`. Reviews
are attached to that commit; merge passes it as GitHub's expected head. Refresh
after a revision-change error. GitHub enforces repository rules and the caller's
permissions. The tools do not bypass reviews or enable administrative merges.
Writes are not automatically retried after uncertain network outcomes: inspect
PR comments/reviews or CI status before repeating them.

`ci_status` distinguishes head and test-merge revisions, inspects all check pages
before summarizing, and reports observed results rather than claiming merge
eligibility. `page` continues checks and runs using `next_page`/`next_run_page`.
Select an explicit `run` for CI diagnosis/control. In CI output, `check` denotes
an Actions job inside a run; the MCP `job` remains the work-order child.
`ci_failures` defaults to the latest attempt and returns five failed checks per
page. Supply `attempt` for an earlier attempt, `check` plus `log_offset:0` for
consecutive log pages, or `annotation_page` to continue annotations. Missing or
expired logs remain an explicit `log_error` alongside the available step evidence.

`ci_rerun` retries failed checks and their dependents by default, at the run's
original revision. `failed_only:false` reruns the whole workflow. `ci_run` explicitly
requests an existing manually runnable workflow, with a published `ref` (default:
job branch) and optional string `inputs`. It reports acceptance, not a fabricated
run ID or completion. Find the actual run in `ci_status` after it appears.

`ci_watch` records a fixed PR head or explicit run and sends changes through the
existing message service. It retains the original work binding across selection
changes and MCP restarts. A changed PR head produces `superseded`; completion or
timeout ends the watch. Repeating the call renews the watch. `ci_watch_stop` stops
this member's watch without cancelling CI. Polling resumes while this member's MCP
server is connected; stored notifications remain readable in `message_inbox`.

`ci_artifact_save` retains the downloaded ZIP by default or a named `entry` as a
report. It verifies GitHub's digest when available and uses the existing managed
store, with repository, PR, run, revision, source ID, and archive digest provenance.
`observed_attempt` is the run's current attempt: GitHub's artifact metadata does
not identify the producing attempt. ZIP entries are streamed, never extracted into
workspace paths. The result lists 50 entry names; `entry_offset` continues the list
and reuses the saved archive. `artifact_read` subsequently returns contents and
source provenance. Default download and expanded-entry limits are 256 MiB; CI log
downloads are limited to 16 MiB, with bounded text returned to the agent.

### GitHub connection for operators

Reuse an authenticated GitHub CLI OAuth session, or provide a refreshed GitHub App
installation/OAuth credential through a private file. Add this optional object to
the state directory's existing `team.json`:

```json
{"github":{"repository":"uscient/agentscient","base":"dev",
           "poll_seconds":30,"max_download_bytes":268435456}}
```

For a managed credential file, add `token_file:"/absolute/path/to/refreshed-token"`
inside `github`; it is read on each request. Otherwise the service uses
`AGENTSCIENT_GITHUB_TOKEN` if present, then the fixed internal
`gh auth token --hostname github.com` credential lookup. Authentication must permit
the requested repository operations. Credential refresh and initial OAuth login
belong to the operator; credentials are never MCP arguments or tool results.
Private Grok profiles preserve the operator's `GH_CONFIG_DIR` for this lookup.

No GitHub server installation or new Python dependency is required. The small
transport calls GitHub's REST/GraphQL APIs behind the task service. Redirected
artifact/log downloads do not forward credentials. Rate-limit retry times are
honored by CI watches; other rejected requests report GitHub's error to the caller.
Optional `merge_method` chooses `merge`, `squash`, or `rebase` if the repository
allows it; otherwise the service selects an allowed method from repository settings.

## Storage for operators

Role/work bindings, routed updates, work orders, jobs, associations, GitHub watches, artifact sources and metadata share the existing
`live.sqlite3`. Payloads live under `artifacts/` in the private state directory.
Services manage paths, hashes, publication and integrity checks; agents receive
IDs, useful summaries, and requested content. Opening existing state adds the new
tables and nullable associations without deleting messages or telemetry.

Saving publishes complete bytes before committing the catalogue and association
in one database transaction. A retry can reuse a complete blob left by an
interrupted commit. Failed calls clean up temporary files; a killed process can
leave temporary or unreferenced files. This initial component keeps them rather
than deleting evidence automatically. Back up the database and artifact directory
together while the team is stopped. Missing or damaged payloads produce explicit
read errors.

## Native conversations

Codex keeps one app-server thread and receives peer messages through
`turn/start.toolOutput`. Its dynamic tools proxy the actual stdio MCP server.
Startup checks that the installed binary advertises the required tool-output API.
Grok keeps one ACP session, using `session/prompt` when idle and `_x.ai/interject`
while busy. Claude keeps its native interactive session and receives MCP channel
notifications. Delivery waits for the native channel registration log entry;
initial MCP handshake alone does not establish a ready channel.

Claude may need its native development-channel approval. Attach to the tmux
terminal returned by `session_start`. The approval remains in the native UI;
there is no replacement repository permission process.

Private profiles expose this team's MCP surface and deny native shell/filesystem
tools. Codex and Grok reuse only selected local login/configuration information;
Claude retains its native account login. These settings do not form an OS sandbox.
Global harness settings are not rewritten. Vendor protocol changes can require an
adapter update; startup failures and delivery errors remain visible in telemetry.

Operator equivalents are available for bootstrap and troubleshooting:

```sh
python3 devtools/run.py start --state /absolute/path/to/state --member codex
python3 devtools/run.py agent --state /absolute/path/to/state --member claude
python3 devtools/run.py status --state /absolute/path/to/state
python3 devtools/run.py stop --state /absolute/path/to/state --member codex
```

`agent` runs in the current terminal. MCP participants use the named capabilities,
not these CLI commands. A stopped session's records survive; restarting creates
a new native conversation. This does not claim transcript/context recovery.

## Telemetry and delivery

The state directory contains `live.sqlite3`, private native profiles, process
logs, and redacted JSONL transport traces under `telemetry/`. Events record MCP
operation timing/results, native identity/activity, message submission and
acknowledgement, and usage observations when the native protocol supplies them.
Missing usage is unknown, not zero; no estimated cost is fabricated.

Queued, submitted, and acknowledged are distinct. A crash during delivery becomes
`uncertain` on restart, not an automatic duplicate. Only the sender can explicitly
retry that message; the ID stays the same. Traces and message history stay local.

## Verification and source

```sh
python3 -m unittest discover -s devtools/tests -v
ruff check devtools
```

Tests launch real stdio MCP servers and native protocol fixtures to exercise
concurrent delivery during unfinished work, persistent identities, acknowledgements,
restart behavior, channel registration, telemetry, and the native-tool boundary.
Command tests cover CO bootstrap, role-scoped tools, automatic CO→XO→collaborator
startup through MCP, atomic allocation, retries, changed authority, private context,
live steering, persistent pause/resume, startup failures, and version-three upgrades.
Workspace tests use real local Git repositories and a bare remote for isolation,
publication, retry, checkpoint recovery and merge-conflict preservation; GitHub PR
behavior is tested separately with the provider fixtures.
Work/storage tests cover the work-order/job hierarchy, PR and artifact associations,
legacy database upgrades, restart recovery, concurrent selection, file snapshots,
publication failure/retry, integrity failures, and binary/UTF-8 reads through MCP.
GitHub HTTP fixtures exercise PR context/revision handling, conversations/review
threads, CI pagination and failure diagnosis, control requests, signed downloads,
credential redaction, managed evidence, and watch restart/revision behavior.
They do not claim an authenticated end-to-end run against a live GitHub account.
Fixtures are not new evidence of authenticated vendor-model acceptance. The native
transports are adapted from the previously accepted
[`multi-harness-proof`](https://github.com/xormania/multi-harness-proof/tree/a944f31b7527807d000da985c546e8b5bc9ff476).
Its MIT notice is retained in `PROVENANCE-LICENSE`. No old development-system
runtime or records are imported.
