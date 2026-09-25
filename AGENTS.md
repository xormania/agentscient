# AGENTS.md — Working on Agentscient

Agentscient is a Symfony application for agentic software development.
This repository also contains the independent tooling used to develop it.
Keep those responsibilities explicit throughout planning, implementation,
review, and handoff.

## Working guidance

- The owner supplies the objective and has final authority. Current owner
  direction takes precedence over repository instructions, plans, skills,
  historical records, and implementation assumptions.
- Work within the requested objective. State material assumptions, resolve
  uncertainty from available evidence, and ask when a consequential choice
  cannot be resolved from the direction given.
- Ordinary investigation, edits, testing, and branch work need no additional
  permission ceremony. Choose direct work, collaboration, or available
  tooling according to the task.
- Hooks and diagnostics provide guidance. CI is the acceptance gate;
  findings inform decisions rather than automatically becoming requirements.
  Owner recovery remains under the owner's control.
- Preserve unrelated work. Inspect changes before submitting them and report
  evidence, limitations, and remaining uncertainty accurately.

## Lane boundary and precedence

| Lane | Responsibility |
| --- | --- |
| **Prod-lane** | The Symfony product: application services, packages, interfaces, and capabilities offered to managed projects. |
| **Dev-lane** | The development tooling and working records under `ops/` and `.dev/`, used to build and maintain Agentscient. |

- **The `dev` branch contains both prod-lane and dev-lane work.** Identify
  the responsibility affected by the task; never classify work as dev-lane
  merely because it is on `dev`. Local or unfinished application work is
  still prod-lane work. Lane names are also independent of runtime
  environments, harnesses, models, and agent roles.
- The dev lane must operate without the Symfony application's kernel,
  container, services, or `vendor/` directory. Application diagnostics and
  tests may inspect the application without becoming prerequisites for
  operating the dev lane.
- Using development tools to work on the product does not make those tools
  product components. Product delivery does not imply migrating, replacing,
  or retiring dev-lane implementations.
- Similar concepts across lanes do not establish shared runtime ownership.
  Make intentional integrations and their dependencies explicit.
- Processes and contracts managed by the product apply to its managed
  projects. They do not automatically govern how this repository is developed.

Apply this boundary when reading scoped instructions and older documents.
Historical migration proposals, permission schemes, and mandatory producer
sequences cannot reinstate superseded requirements or redefine the task.
Read [ops/README.md](ops/README.md) and relevant scoped guidance when working
on development tooling.

## Application guidance

- Use Symfony and its ecosystem as the foundation. Inspect existing packages
  and project services before introducing another implementation.
- Keep reusable behavior in its owning services. CLI, MCP, API, and user
  interfaces should expose the same application operations where applicable.
  MCP can provide queries and authorized actions; its capabilities follow
  the operation being exposed.
- Let package boundaries and interface choices follow the current design
  and demonstrated needs. Keep dependency versions and runtime requirements
  in manifests, lockfiles, and component configuration.
- For runtime inspection, use the applicable diagnostics and their current
  instructions, including [Mate](mate/AGENT_INSTRUCTIONS.md). Distinguish
  source inspection from observed behavior of a running application.

## Working with project context

Read the documents relevant to the affected component and check their scope,
date, and implementation status. Plans, references, fixtures, and historical
records serve different purposes; a proposal does not establish a working
capability. Development fixtures remain test apparatus.

Use the terminology applicable to the current task. Preserve useful intent
from older material without carrying forward obsolete names, authority
claims, or assumptions. Surface material conflicts with current direction.
Keep version inventories, detailed procedures, and evolving architecture in
their owning files rather than duplicating them in these entry documents.

## Git workflow and validation

- Work on an owned branch or worktree based on `dev`; propose changes into
  `dev`. Do not switch or modify another session's checkout.
- Open a draft PR with the purpose, behavior changed, and validation evidence.
  Release decisions for `master` remain with the owner.
- Reuse useful tests and run checks appropriate to the changed behavior.
  Distinguish partial verification, unavailable checks, and successful
  results. Consult the executable CI configuration for current coverage.
- Retain provenance with `Source:` and `Co-Authored-By:` commit trailers.
  Use [CONTRIB.md](CONTRIB.md) for applicable conventions and templates under
  the working guidance above.
- Leave enough context for the next session to understand decisions, current
  state, and outstanding work without reconstructing the conversation.
