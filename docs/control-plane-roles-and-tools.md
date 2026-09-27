# Control plane: roles, context, and MCP tools

Status: delivery scope and discussion baseline for the next catalog revision.
Recorded: 2026-09-26.
Local-agent readiness target: Monday, 2026-09-28.

This document captures the direction discussed with xor. It separates that
direction from candidate tool names and from capabilities implemented today.
It is not a frozen API, a detailed implementation plan, or evidence that the
proposed tools already exist. The owner's subsequent direction can change it.

Implementation progress: the first shared-work slice now provides direct
`work_context`, `work_report`, and `guidance_request` tools, trusted role/work
bindings, scoped context and live delivery, routed reports, and retained evidence.
All eight role names receive this common core. The command slice now adds CO
`direct`/`monitor` and XO `orchestrate`/`monitor`/`steer`, with automatic job/member
binding, configured harness selection/startup, scoped monitoring, and live brief
updates. Pause retains the running conversation; stop requests session shutdown
while preserving work and evidence. Managed Git workspaces, checkpoints, publication,
installed Makers/Mate, and configured checks now have direct scoped tools. Serena,
review/acceptance and completed-work turnover remain to be integrated. The older low-level catalog is
available only through an explicit operator connection for setup/diagnostics.
See [`devtools/README.md`](../devtools/README.md) for the current callable interface.
The catalog sections below retain the discussion baseline for continuing revision.

## Delivery scope and deadline

The entire dev-lane is being built in these chats. It must be ready for local
agents to use on Monday, September 28, 2026, to begin developing the Symfony
prod-lane. The local agents are consumers of the prepared development environment;
they should not have to finish building it before they can do product work.

Here, **dev-lane** means the complete development support environment: the
control-plane MCP, live harness coordination, work and artifact services,
telemetry, Git/GitHub delivery, role/context provisioning, and the configured
development capabilities that make MCP-only work possible. **Prod-lane** means
the Symfony application those local agents will develop.

Completion includes configuring Serena v2 beta with REPL for product development,
providing MCP access to basic Symfony Maker and Mate capabilities, configured
validation, and preparing the Symfony foundation so local agents can start work.
Use the current PHP/Symfony versions and native framework facilities, including
attributes, autowiring, and autoconfiguration where appropriate; verify versions
and installed capabilities during implementation. Basic Maker support does not
depend on project-specific patterns already existing.

The current deliverable is the prepared dev-lane and Symfony starting foundation.
The subsequent local-agent work develops the Symfony product. These chats may
implement and repair the dev-lane directly; the MCP-only/no-shell constraint
describes the working environment being provided to those local agents.

The catalog revision is part of this delivery effort. It must cover the complete
working setup needed for that start date, followed by implementation and actual
local acceptance. A merged document or passing protocol fixtures alone does not
establish that the environment is ready.

## Purpose

Provide live agent coordination, telemetry, work tracking, artifacts, and delivery
through simple services behind MCP. Agents should spend their context and effort
on their assigned work. The services should handle operational state, routing,
storage, workspace lifecycle, Git, and GitHub associations.

Participating local agents work through MCP, without a general shell surface.
An agent requests a useful outcome; it should not have to assemble that outcome
from a sequence of provider calls or manage internal identifiers.

Keep the implementation small. This work does not restore the removed development
system's dispatcher, grant machinery, review ladders, or workflow engine. Live
communication between persistent harness sessions is the normal mechanism.
Dispatch may be available separately, but is used only when explicitly requested.

## Boundaries

| Component | Responsibility |
| --- | --- |
| Control plane | Work context and state, live coordination, workspace lifecycle, local Git/GitHub delivery, artifacts, and telemetry. |
| Serena | Code discovery, navigation, edits, refactoring, and the intended Serena v2 beta REPL capability for developing the Symfony application. It remains a separate MCP service. |
| Development capabilities | Framework generation, application diagnostics, and configured validation. Basic Maker and Mate access are required for Monday readiness; their invocation contracts must be resolved in the tool revision. |
| Symfony application | The product being developed. Its foundation and dependencies are distinct from the independent development support in `devtools/`. |

The `dev` branch contains both the Symfony application and development support;
the branch name does not define a component's responsibility. The delivery scope
above covers the entire dev-lane and the Symfony starting foundation; product
implementation follows through the prepared local environment.

The control plane and Serena need a shared workspace binding. Refresh, restore,
and cleanup operations must coordinate with active editing. Git serialization
alone cannot prevent two agents from changing the same working files.

Roles can expose tools from multiple services. Access restrictions must apply at
the service and workspace boundaries, including Serena's REPL access. Hiding a
tool from discovery is not sufficient enforcement. The intended integration is
not a claim about restrictions already implemented by the current harness setup.

## CO, XO, and live collaborators

**CO is the session xor works with directly.** It holds the broader intent,
discusses choices with xor, and translates authorized direction into work for XO.
Discussion and exploration do not automatically authorize execution.

**XO reports to CO.** XO carries out the objective by orchestrating, monitoring,
and steering persistent collaborators. It chooses suitable harnesses, models,
reasoning settings, and role profiles for the work within its authority.

The intended XO surface has three operations:

| Candidate tool | Outcome |
| --- | --- |
| `orchestrate` | Organize collaborators around an objective, responsibilities, completion criteria, boundaries, and dependencies. |
| `monitor` | Inspect progress, blockers, results, and measured usage. Significant developments also arrive automatically. |
| `steer` | Clarify direction, change priorities or responsibilities, answer questions, and pause or stop work within scope. |

These outcomes now have an initial callable implementation, documented in
`devtools/README.md`. Small tool counts must not conceal a large command language
that agents still have to learn and sequence manually.

A work order needs only enough command information to know who is participating,
what each participant is responsible for, and where decisions and reports go.
XO now establishes the initial structure with named responsibilities through
`orchestrate`; the service creates jobs and binds configured collaborators.
Specialist roles do not automatically introduce additional command levels.

Decisions should be made where the relevant context and responsibility reside.
An agent retrieves missing facts or consults a relevant specialist when possible.
XO resolves coordination and execution questions within the brief. CO is involved
when the decision needs broader intent or materially changes scope or priorities.

The control plane routes findings, questions, reviews, and authoritative direction
through the established relationships. Agents should not need to select recipient
IDs, forward context packets, poll inboxes, or manage acknowledgements. Routine
exchanges can reach the relevant collaborator without XO manually relaying them.

Tool calls enforce who may change direction or scope. A message carrying a
suggestion does not itself confer that authority. Delivery and acknowledgements
remain observable without claiming that transport can guarantee model compliance.

## Work orders, jobs, and evidence

- A work-order number binds the overall effort: objective, completion criteria,
  boundaries, decisions, and evidence.
- Jobs are sub-units of a work order, normally delivered through PRs.
- Services bind repositories, workspaces, branches, target branches, PRs, checks,
  and artifacts to the appropriate work.
- Agents receive relevant context automatically. Internal IDs are not required
  inputs to the normal work loop; useful references remain available for inspection.
- Submitting or merging a PR does not establish that the work-order objective is
  complete. Completion is assessed against the stated outcome.
- Artifact metadata and associations belong in a database. Managed storage holds
  the payloads; agents request evidence or deliverables without managing paths.
- Material decisions and their rationale are retained and reflected in the briefs
  of affected collaborators.

Retries, partial completion, concurrent operations, and uncertain provider outcomes
are handled by the services. They should preserve completed work, report actual
state, and avoid duplicate effects. Conflicts needing a decision return a focused
problem with relevant evidence rather than a Git repair procedure for the agent.

Long operations continue in the background, retain their original work binding,
persist their results, and deliver meaningful developments through live channels.

## Context and role binding

A role profile defines tool capabilities and default context needs. A work binding
determines which work those capabilities apply to. A reporting relationship
determines where findings, questions, and decisions go.

Each active brief provides the objective, completion criteria, boundaries,
relevant dependencies and decisions, and current problems. Include the reason for
the work where it helps judgment. The brief also identifies decisions the agent
can make and the questions requiring guidance.

Supply that brief at startup or resume, and update affected context when meaningful
events occur. Additional relevant detail remains retrievable; compact context must
not leave an agent unable to obtain the facts needed to do its work.

CO can retain broad context without copying its entire conversation to XO or every
specialist. XO receives what it needs to carry out the work; specialists receive
the context needed for their responsibilities. Automatic updates should deliver
changes and actionable information rather than repeatedly sending the full history.

A message about different work must not silently retarget the agent's next action.
In-flight operations keep their originating binding even if the session later
changes work. Context reads and tool calls enforce the established scope on the
server; supplying an arbitrary work ID is not authority to access it.

## Initial role profiles

These are starting profiles for revision, not a mandatory sequence of agents.
XO selects the collaborators the work needs. Profiles reuse shared capabilities;
they do not each require a separate implementation of reporting or storage.

| Profile | Capabilities and responsibilities | Default context |
| --- | --- | --- |
| CO | `direct`, `monitor`, shared reporting/guidance tools. Resolve intent questions, change priorities, assess outcomes. | xor's broader intent, constraints, consequential decisions, and relevant XO reports. |
| XO | `orchestrate`, `monitor`, `steer`. | Work order, responsibilities, dependencies, progress, exceptions, and measured usage. |
| Coder | Inspect and edit through Serena, validate changes, submit work. | Assigned objective, relevant code and contracts, boundaries, and completion criteria. |
| Audit | Inspect implementation and evidence, investigate concerns, record findings and review conclusions. | Changes under review, requirements, applicable standards, and supporting evidence. |
| Docs | Inspect source material, write and maintain documentation, check consistency. | Audience, established behavior, relevant decisions, and source material. |
| Research | Search sources, investigate options, preserve evidence, report conclusions and uncertainty. | The question, constraints, and decision the research supports. |
| Test Writer | Inspect behavior and contracts, create tests, run checks, report coverage gaps. | Expected behavior, edge cases, boundaries, and existing test conventions. |
| Architect | Explore system structure, define contracts, assess dependencies, record design decisions. | Relevant system context, requirements, existing capabilities, and technical constraints. |

The role identifies the responsibility; the tool profile makes it usable. For
example, Coder can receive the control-plane work tools and Serena together.
Research may need a research provider. These provider capabilities should be
selected for the role without becoming duplicate control-plane implementations.

Audit normally needs inspection and validation plus a way to publish findings.
Test Writer needs editing and execution capabilities as well. Specialization such
as security audit can be expressed through the brief and appropriate capabilities
without automatically creating another fundamental rank or role.

Role and scope changes should follow changes in responsibility. The next catalog
revision must settle the initial tool sets, any needed combinations, and how scope
changes are applied to a running session. It must not assume every role needs every
tool, or that a command role automatically needs all specialist capabilities.

## Candidate control-plane catalog

The names below preserve the discussion baseline. The shared and command tools
identified in the implementation-progress note are now callable; the remaining
names are proposals. Revise those together with the role list before defining schemas.

### Shared context and coordination

| Candidate tool | Agent-facing outcome |
| --- | --- |
| `work_context` | Retrieve the relevant brief, decisions, discussions, documents, or evidence when more detail is needed. The normal brief is supplied automatically. |
| `work_inspect` | Understand changes, progress, checks, feedback, and outstanding problems within the current responsibility. |
| `work_report` | Report a finding, blocker, or recommendation that the service cannot infer. Route it with the relevant work context and evidence. |
| `guidance_request` | Ask for clarification, a decision, or help. Route the question to the appropriate responsibility without manual recipient selection. |

### Producing, validating, and reviewing work

Expose the operations a profile needs; these are not a universal permission set.

| Candidate tool | Agent-facing outcome |
| --- | --- |
| `work_save` | Preserve a deliberate checkpoint with notes or deliverables. Services manage storage and association. |
| `work_check` | Run configured validation and return actionable results with retained evidence. The agent does not provide a shell command. |
| `work_submit` | Deliver the result: preserve changes, commit/publish and create or update a PR when applicable, attach evidence, follow checks, and route the review packet. |
| `review_record` | Record findings and a review conclusion against the inspected revision, then route them to the relevant participants. |
| `review_respond` | Respond to findings with explanation, changed work, or supporting evidence in the original review context. |

Research and design outputs may be reports or decisions rather than code PRs.
The next revision should settle how submission represents those outcomes while
retaining their work-order/job associations.

### Exceptions and recovery

| Candidate tool | Agent-facing outcome |
| --- | --- |
| `work_refresh` | Incorporate relevant upstream changes while preserving current work and coordinating with active editors. |
| `work_recover` | Restore an appropriate checkpoint or undo a specified change within scope. |
| `work_control` | Pause, resume, retry, or cancel an ongoing operation within the caller's responsibility. |

The service should handle routine recovery automatically. Whether these require
separate visible tools, appear only when relevant, or overlap with XO's `steer`
remains open for the next revision.

### Discovery and command tools

Common tools should be immediately callable. Where further discovery is useful,
the candidate `capability_find` should return a relevant description and callable
schema together. Agents should not repeatedly search, describe, and invoke just
to perform routine work. Discovery and invocation must respect the role and scope.

XO's implemented command tools are `orchestrate`, `monitor`, and `steer`.
CO uses `direct` and `monitor`. This baseline does not restore the
earlier, larger list of separate session and work-management tools for XO.

## Current implementation and the intended revision

At the recording baseline, `dev` is commit
`730df2a9d8b14b3c7eaee3fd8e8dbf5105c3ee5d`. The supported interface is documented in
[`devtools/README.md`](../devtools/README.md).

At that baseline, implemented development support included persistent live harness transports,
messages, telemetry, numbered work orders, child jobs, managed artifacts, and
GitHub PR/CI services. MCP then exposed `capability_search`,
`capability_describe`, and `capability_invoke` over those capabilities.

[PR #309](https://github.com/uscient/agentscient/pull/309) added work and artifact
services. [PR #310](https://github.com/uscient/agentscient/pull/310) added GitHub
capabilities including `pr_*` and `ci_*`. That implementation is reusable backing
functionality; its current public surface is not the intended final agent catalog.

The next revision should put coherent work outcomes above those backing services,
handle context and state internally, and expose only the operations appropriate
to the caller's profile. Existing operational documentation continues to describe
what can actually be called until implementation changes it.

The shared role-bound surface, command tools, initial and updated briefs, and
report/guidance routing are now implemented as described above. The initial command
implementation keeps one current work order per CO and one collaborator per named
job. Further specialist tools and the integrated Serena/Maker/Mate workspace
contract remain part of the delivery work.
Configured jobs now have isolated Git worktrees and task-facing inspection,
checkpoint, recovery, upstream refresh and PR submission. The service binds the
repository, branch and target automatically, preserves conflicts/checkpoints, and
retains diff and CI evidence. Installed Maker generation, Mate diagnostics and
configured validation now execute behind role-bound MCP, with retained asynchronous
results and automatic worker/supervisor delivery. Serena editing and completed-job turnover
are the remaining integration work. Protocol fixtures exercise the command flow and live pause/resume; authenticated
local model acceptance remains outstanding. This document does not mark the complete
dev-lane ready.

## What done means

The completed dev-lane should demonstrate that:

1. CO can give XO an objective and boundaries; XO can organize, monitor, and steer
   live collaborators and return outcomes or focused intent questions.
2. Each agent receives the necessary profile, working context, and tools without
   supplying operational repository, workspace, branch, PR, or storage identifiers.
3. Tool access and context retrieval enforce the established role and scope at
   the service boundary, including calls attempted outside the advertised catalog.
4. Findings, guidance, and reviews reach the right responsibility through live
   communication, with durable records and without agent delivery bookkeeping.
5. Submission, checks, evidence, and delivery handle their underlying Git/GitHub
   steps, concurrency, and retries without silently changing work or losing edits.
6. Serena operates on the intended workspace and coordinates with lifecycle
   operations; the control plane retains its separate responsibility.
7. Measured progress and usage are visible. Unknown usage remains unknown, and
   queued, delivered, reviewed, and complete are distinguishable states.
8. The working system remains small enough to understand and use. Roles reuse
   services, and an agent can carry out ordinary work without a management ritual.
9. A real local harness can receive a bounded Symfony job, use Serena's configured
   REPL, invoke the basic Makers and Mate capabilities it needs, run validation,
   and deliver evidence and a PR through MCP without a general shell surface.
10. Live guidance and review work during that task; the result is visible to XO
    and CO. Record the actual local run and distinguish it from fixture-only checks.

The next discussion should revise the tool/role matrix, resolve overlaps and
missing outcomes, and order the remaining implementation toward Monday readiness.
It should not turn this baseline into a detailed workflow that every work order
must follow.
