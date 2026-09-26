# Private Serena provider for prod-lane development

The dev-lane MCP owns workflow, live communication, identity and source receipts.
Serena v2 beta supplies discovery and edits of the Symfony **prod-lane**. This
provider is not intended for developing `ops/` or `.dev/`. Mate, Makers, checks,
dependencies and Git belong to their named project operations, not Python cells.
Those operations remain readiness stages 4–6; this provider does not implement them.

## Install and select

Create an isolated installation outside the project. Do not replace an operator's
existing Serena environment. From the repository root, for example:

```sh
uv venv --python 3.13 /absolute/serena-v2
uv pip install --python /absolute/serena-v2/bin/python \
  -r ops/devlane/providers/serena-v2.txt
python3 -B ops/conductor/tools/sessions.py start --member NAME --mcp-only \
  --serena-python /absolute/serena-v2/bin/python
```

Git, Node and npm are backend dependencies. The core dev-lane stays stdlib-only
and requires no Symfony kernel, Composer vendor directory or Serena package.
The provider checks Serena's distribution version and installed VCS commit
against the manifest before starting. Keep the virtualenv's `bin/python` path;
resolving its symlink would select the base interpreter without the installation.

`profiles.py prepare-interactive` accepts the same provider option. The private
profile continues to register one MCP entry, named `coordination`. Serena is a
child of that entry. A missing provider is reported during discovery without
disabling live coordination. Select the option again for a replacement member.

Intelephense 1.14.4 is the selected PHP backend. Serena installs it into its
private home on first use; allow time for installation and indexing. The provider
sets `SERENA_USAGE_REPORTING=false` and disables Intelephense's bundled
Application Insights 2.7.3 telemetry and Statsbeat through
`APPLICATIONINSIGHTS_CONFIGURATION_CONTENT`. npm audit, funding and update
notifications are disabled. These are upstream configuration switches, not
upstream code edits. Normal package downloads still use the configured registry.
Operators can supply `NPM_CONFIG_CACHE` and `NPM_CONFIG_OFFLINE=true` to use a
populated cache without registry access.

## Work through the broker

Discover `code_status`, `code_repl` and `code_restart` with `capability_search`,
then load their schemas with `capability_describe`. Invoke them using
`capability_invoke`. Initial discovery remains three tools / 1,154 compact JSON bytes.

1. Invoke `code_status` with empty arguments to obtain the trusted worktree,
   participant, optional assignment binding, source fingerprint and provider epoch.
2. Invoke `code_repl` with `code`, `expected_source_fingerprint` and
   `expected_epoch` from that status. Start with `s.info('lsp.find_symbol')` or
   other selected API documentation. Retain objects in REPL variables and return
   small selected results.
3. Inspect the outcome, changed paths and source-event identifier. Use the
   returned fingerprint and epoch for the next cell, or refresh `code_status`.
   A source change by a peer requires inspection before another edit.
4. Use `code_restart` with the current epoch when needed. It reports loss of
   variables; assignments and messages remain in the lane store.

Caller arguments cannot select a participant, workspace, executable or Serena
session. A trusted `dev_mcp.py --binding FILE` can attach an existing assignment;
an ordinary interactive profile has no assignment-specific binding and reports
`assignment: null`. Direct work requires no new permission ceremony. A changed
binding requires a new entry process so temporary state cannot cross assignments.

## Source records and failures

Every cell invalidates current-source check receipts **before** execution, even
discovery cells: arbitrary Python cannot be assumed read-only. The existing lane
SQLite store records participant, optional assignment, epoch, fingerprints,
changed paths and outcome. A short worktree lock serializes source operations
without holding the coordination database during the cell.

Fingerprints include HEAD, tracked files, nonignored untracked files, deletions,
modes and symlink targets; ignored runtime data is excluded. Historical CI records
stay historical. The receipt API does not yet wire stage 4 project checks.

At this beta pin, Python exceptions can be ordinary MCP text. The adapter
recognizes their location format and records partial edits. Failed transport
never causes automatic replay. A failed final source scan retains the event as
`source_unknown`, leaves verification stale and returns no invented fingerprint.
Inspect and repair the worktree. Namespace eviction reports lost variables before
the next requested cell runs. Bounded replies retain the source-event identifier;
the complete changed-path list remains in `source_events`.

Private logs, configuration and indexes live outside the product worktree under
the lane's state directory. Ending the entry stops its owned provider/LSP process
group. Serena's configuration ignores dev-lane directories and disables its shell
tool. Arbitrary Python still has provider-process permissions: this is **not a
filesystem, credential or network sandbox**. Environment filtering omits harness
identity, lane configuration, publication credentials and SSH agents; it cannot
prevent the same OS user from reading other accessible files. An observed edit
outside the intended lane is reported, not silently rolled back.

## Evidence and remaining acceptance

`test_code_work.py` exercises real pipes with a synthetic provider: isolated
namespaces, bindings, stale source, partial failures, lost state, bounded output
and source accounting. `test_mcp_only.py` checks provider selection across profile
projections while keeping one entry. Neither is native-harness evidence.

The optional real-provider check uses disposable PHP service files:

```sh
python3 -B ops/devlane/providers/serena_php_smoke.py \
  --serena-python /absolute/serena-v2/bin/python
```

On 2026-09-26 it passed with Serena commit
`b79e2a55f9d4072084977dd35bd07d31146d88b9`, Python 3.13.15 and Intelephense 1.14.4.
The real dev-lane → Serena MCP route demonstrated PHP class/reference discovery,
an edit/read, persistent variables, edit-then-error accounting, stale-check
invalidation and restart with an unchanged assignment. It recorded eight source
events, using npm offline and both usage-reporting paths disabled. No PHP runtime
test was performed.

Stage 3 still requires these operations from an installed native participant.
The complete workflow also needs native restrictions/live communication acceptance,
project actions, Mate, Makers and a useful prod-lane task. See the
[readiness stages](../../../docs/dev-lane-mcp-readiness.md).
