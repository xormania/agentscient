# MCP tools for live work

This directory provides task-facing MCP tools for live communication, measured
telemetry, work orders, jobs, artifacts, and GitHub PR/CI work. Agents ask to track
work, inspect a PR, diagnose CI, save evidence, or retrieve context; services handle
provider calls, database records and storage internally.
Python 3.11+ and SQLite from its standard library are sufficient on Linux/macOS.
Native launchers require the selected locally
installed, authenticated harness. Background Claude sessions also require tmux.

There is no dispatcher, task engine, assignment registry, grant system, audit
ladder, source editor, shell capability, or project command runner.

## Set up a team

An operator runs this once from the repository checkout. State must be outside
the source worktree. The `external` member represents the MCP client from which
you manage the team; it does not spawn another model.

```sh
python3 devtools/run.py init \
  --state "$HOME/.local/state/agentscient-live" \
  --workspace "$PWD" \
  --member owner:external --member codex:codex --member claude:claude --member grok:grok
```

Select only the harnesses you use. Edit that state directory's `team.json` to set
each member's `binary`, optional `model` and `reasoning`, and workspace. Different
members can use separate worktrees. Existing member identities cannot silently
move to a different harness or workspace; use a new member name for that change.
No model is selected by this repository.

Add this server to the managing client's MCP configuration, replacing the paths
with absolute paths on your machine (the command must be your Python executable):

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

`tools/list` exposes only `capability_search`, `capability_describe`, and
`capability_invoke`. Search returns five capabilities per page; describe supplies
the input schema. Invoke takes `{"capability":"name","arguments":{...}}`.

| Capability | Purpose |
| --- | --- |
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
tools retrieve current provider state. Local Git operations are not implemented.
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

Work orders, jobs, associations, GitHub watches, artifact sources and metadata share the existing
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
