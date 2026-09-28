# Conductor control — mandatory execution boundary

Owner, 2026-09-09: manually repair the lane before using it; runaway
conductors and failure to follow TDD require enforcement, not suggestions.
This repair consumes the existing lane through a bounded execution boundary.
It does not adopt the unfinished policy/discovery designs as prerequisites.

This instrument inherits [instrument-conventions.md](instrument-conventions.md)
and the shared [wire](../../docs/wire.md). Writing verbs (`init`, `run`, `seat`)
require `WF_AGENT` in `Name <address>` form and retain that invocation identity.
It identifies the caller; action producer identities remain frozen in the
owner plan. Status reads need no identity. Refusal classes are `identity`,
`control`, `plan`, `binding`, `admission`, and `tool`.

## Authority and scope

`ops/conductor/tools/control.py` owns a local control directory. The owner
initializes it outside a conductor session using `init PLAN --state DIR`.
The conductor cannot initialize, extend, reset, approve or rewrite it through
its tools. Initialization refuses an existing directory. A plan is strict
JSON (duplicate/unknown keys refused), retained byte-for-byte. There is no
environment-variable bypass. Existing work remains readable without a plan.

The plan has exactly `version` (1), `repo` (absolute existing Git worktree),
`branch`, `scope` (repository-relative file), `scope_sha256`, `expires_at`
(UTC ISO timestamp), `max_seconds` (positive integer), and `actions`.
Actions are a nonempty array of closed objects:
`{id, kind, argv, timeout, requires, tests, producer}`. IDs are unique safe
tokens, argv is a nonempty string array (no shell interpretation), timeout
is a positive integer bounded by max_seconds, requires is an explicit array
of preceding action IDs, tests is an explicit array of unique normalized
repository-relative test/helper/fixture paths, and producer is a nonblank
specific harness/model identity. kind is one of `tests`, `fixture`, `red`,
`test-review`, `code`, `green`, `review`, `check`.
`scope` is the immutable owner task declaration, not an implementation file.
Implementation may change other worktree files as directed by the exact
owner-declared command; this control does not add a general filesystem policy.

The owner declares exact commands and dependencies; a conductor chooses only
an existing action ID. It cannot supply new argv, scope, model, criteria or
allowances. A fresh ID, changed declaration, concurrent request or resume
cannot replenish actions. The plan's absolute repo and branch are checked
on every action. Scope bytes and plan bytes must still match initialization.
Actions, terminal outcomes and cumulative elapsed execution time are stored
outside the worker worktree using atomic writes and an exclusive lock.

`status --state DIR` returns JSON with `plan`, `actions_state`, and
`cumulative_time`. Each attempted action entry includes `status`
(`running`, `completed`, `failed`, or `aborted`), `exit_code`, retained
`stdout_path`, `stdout_sha256`, `stderr_path`, `stderr_sha256`, and, when
tests are selected, `tests` and `tests_sha256`. `tests` is sorted by path,
with rows exactly `{path, sha256}`. Its hash is SHA-256 of UTF-8 JSON with
sorted keys, separators `(',', ':')`, ensure_ascii=False, and no trailing
newline. A missing action has no entry; it has not run. Reviewer processes
read these paths and hashes through `status`; argv need not change. The
controller supplies `CONTROL_STATE` with the absolute state directory to
each child for this read. This variable confers no action/initialization grant.
Tests may not exist at initialization or before the test-author action;
after successful test production they must exist, be tracked and be sealed.

`run ID --state DIR` reserves once, then executes that exact argv in the
bound repo. An action with unmet prerequisites, an expired plan, exhausted
time, changed bindings, completed/failed/running reservation or unknown ID
refuses before spawning. Failure consumes the action and stops that path;
there is no automatic retry. A crash leaves a running reservation that
refuses reuse. The child gets a new process group; the controller terminates
that owned group on the smaller of its timeout, remaining cumulative budget
and plan expiry. On timeout or interruption it retains stdout/stderr and an
aborted result. A process that closes its own stdout does not end supervision.
No other process group may be signalled. Retained logs are bounded (8 MiB
combined); overflow aborts the group. Reads (`status`) need no identity.

The owner starts the conductor itself with `seat --state DIR -- ARGV...`.
This reserves a single conductor session and supervises its whole process
group, including thinking and read-only loops, for at most max_seconds and
the remaining plan lifetime. A second seat or a changed/replayed state
refuses. Interruption/expiry terminates the seat and every still-owned action
group using recorded PID plus process-start identity, never stale PID alone.
The conductor hook denies `seat` just as it denies `init`; it cannot launch
another seat or extend its own wall. A started seat's terminal state is
durable. Owner shell diagnosis/status remains available after it stops.

## TDD admission

No `code` action may run until its transitive prerequisite set contains
successful `tests`, `fixture`, `red`, and `test-review` actions for exactly
the same nonempty test path set. The test author, test reviewer and code
producer must be three distinct specific harness/model identities. Producer
names come from the owner plan, never an envelope or an action argument.
The same exact test bytes must survive fixture, RED, review, code and GREEN.
A missing, untracked, symlinked, changed or out-of-repository test file
refuses. Directory shorthand is not accepted: enumerate the complete set
including helpers and fixtures. The independent reviewer checks that set's
completeness and the test oracle against the declared behavior.

`fixture` and `test-review` require exit 0. `red` requires exit 1 plus a
machine-readable result produced by the controller's unittest runner:
testsRun > 0, failures > 0, errors = 0, unexpectedSuccesses = 0, and skipped
= 0. The owner-declared RED argv is exactly `unittest discover` followed by
normal unittest discovery flags; the controller invokes the Python runner,
not an arbitrary shell or a worker-written JSON report. Runner output names
the actual failed test IDs and traceback text. No collection/import error,
zero tests, arbitrary nonzero command or self-reported RED earns admission.
`green` uses the same discovery arguments as RED and requires all tests pass.

The independent `test-review` process receives the retained RED/fixture logs
and test manifest and must write its verdict to stdout as a strict JSON
object `{verdict: "approve", tests_sha256: SHA256, red_sha256: SHA256}`.
Its action argv is fixed at initialization. A plain exit 0, missing verdict,
CHANGES, stale digest or malformed output refuses code. This is an attestation
from a separately configured producer, not proof of semantic perfection.
Tests that prove defective require a new independently authored and reviewed
cycle; the conductor cannot quietly edit sealed tests or bless its own tests.
`red_sha256` is the retained RED action's `stdout_sha256`; the runner writes
its JSON result to stdout. The attested test manifest must match that RED
receipt and the actual test bytes at review and code admission.

`code` and `green` recheck test bytes after execution; mutation invalidates
the action with an Abort result (exit 3), even when the worker reports success.
A malformed or non-approving review result is an execution finding (exit 1);
an identity/prerequisite mismatch found before spawn is a refusal (exit 2).
Code success alone cannot
satisfy GREEN or reviews. Fixture checks execute before RED and may exercise
established consumers; the test reviewer must reject fixtures that hide
their invalid downstream assumptions behind a missing API.

## Native tool boundary

`ops/devlane/hooks/conductor-control.py --state DIR` reads native
PreToolUse input from Claude, Codex and Grok. Grok's camelCase aliases are
normalized; disagreeing aliases and truncated input refuse. It permits read tools and a
small parsed set of shell reads (`pwd`, `cat`, `rg`, `git status/diff/show/log/
rev-parse/ls-files/ls-tree`) with executable-capable options refused. No
shell substitutions, redirections, separators, environment assignments or
interactive stdin/TTY are admitted. The only action command it permits is
the exact absolute Python/controller invocation `run ID --state DIR` for
its own state. All direct edits, raw harness launches, alternate lane
entrypoints, git mutations, native subagents, unknown tools and configuration
edits refuse. A string merely mentioning a permitted command grants nothing.
Code-mode nested tool calls retain this native interception; `write_stdin`
may poll but nonempty interactive input is not part of the allowed interface.

Malformed input, missing/corrupt state, helper failure, stale controller or
hook bytes and binding mismatch deny actions. Diagnostic reads stay available.
Native hook denial is the standard permissionDecision=deny object; CLI
precondition refusal is exit 2, empty stdout and one
`class: expected ...; found ...; needed ...` stderr line. Execution failure
returns 1, interruption/timeout returns 3. Successful actions/status return 0.
Here `class` denotes a lowercase refusal token, not the literal word `class`.
Native input uses `tool_name`, object `tool_input`, and `cwd`. A recognized
safe read may pass with silent exit 0 or an explicit native allow object.
Tests must distinguish that from a deny object returned with exit 0.

The owner launches a supported host with the integrated seat form:

```sh
python3 ops/conductor/tools/control.py seat --state /absolute/control-state \
  --host codex --model OWNER_SELECTED_MODEL --prompt /absolute/conductor-prompt.md
```

`--host` accepts `codex`, `claude`, or `grok`; the model is supplied by the
owner. This form creates a fresh private native home, installs the mandatory
catch-all PreToolUse gate, and reserves the same once-only seat. It carries
only the host's credential leaf by symlink and explicit provider configuration
(Codex `model_provider`/`model_providers`, Grok `model`). It does not copy user
hooks, skills, permissions or MCP configuration. Claude receives the gate
through explicit settings with other setting sources disabled. Grok receives
a trusted user-scope hook in its private home. Codex uses invocation-scoped
hook trust in its newly generated home; additional project/ancestor Codex
settings or hook files refuse before launch. Codex code mode is disabled so
the verified native tool interception is used. Native homes and retained logs
remain under the external control state. The raw `seat -- ARGV...` form is
an owner diagnostic supervisor; it does not install a native host gate.
Neither form is callable through the conductor's tools. `status` remains
callable after expiry. No persistent operator settings are changed.

This gate applies to conductor tools, not dispatched worker tools. Initialization
retains only the owner's HOME, native-home and XDG configuration/state path
context. A declared action restores those paths before the existing dispatch
isolation builds the worker's normal home or settings flags. `CONTROL_STATE`
continues to identify evidence for worker reads; it does not install a hook.
No project-wide hook setting or worker launcher is changed by this repair.
The native role probes must show the conductor refusing writes while each
host's worker, through the real dispatch isolation adapter, can still edit
and execute its authorized implementation commands.

Host activation requires an actual denied native edit and denied raw command
with no effect, and a permitted read. A configured-but-untrusted hook is not
active. Unsupported/unproven hosts must not run a conductor with write access.
The supported-host tool gate and the command controller enforce this boundary
against model actions; same-UID owner shell access is an explicit remaining
trust boundary. They do not make raw owner sessions or unhooked hosts safe.

## Verification and recovery

Independent tests must exercise real subprocess side effects, concurrent
double starts, process-group timeout, durable exhausted state, intended RED
versus import/fixture errors, wrong/stale/same-producer attestations, exact
test immutability and native hook bypass attempts. Positive controls must
exercise a full small tests → fixture → RED → review → code → GREEN path.
Every assertion must reach its intended condition with the other prerequisites
valid. No implementation begins before independent test acceptance and RED.

The manual repair records actual raw harness commands and their bounded
outcomes separately from canonical dispatch records. No repaired lane is used
for this bootstrap. Run the independent focused tests, the relevant existing
hook tests and `ops/bin/suites.sh` before activation. Register the control's
read-only diagnostic in the permission surface and correct stale TDD guidance
to the executable path in this change. Completed recovery and monitor branches
are preserved separately; this change does not silently accept their source.
