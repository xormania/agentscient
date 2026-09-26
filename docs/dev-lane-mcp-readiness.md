# Agentscient dev-lane: MCP readiness stages

Date: 2026-09-25  
Owner: xor  
Status: Implementation handoff; stage requirements and acceptance criteria, not a detailed implementation plan. The first implementation slice adds the progressive MCP entry; native harness restrictions and stages 2–7 still require implementation and acceptance.

## Objective and overall done

Make the existing dev-lane usable locally to develop the Agentscient Symfony application through MCP, with persistent Codex, Claude Code, and Grok sessions communicating live.

The dev-lane manages assignments, live peer communication, project execution, source state, and results. Persistent harnesses communicate directly while work is in progress. Dispatch remains available only when the owner explicitly requests it; agents must not choose it as the default workflow or a fallback. Serena v2 beta with REPL enabled provides code discovery and editing. Symfony AI Mate provides Symfony inspection. Custom Makers generate selected repeatable structures. Named project actions provide the remaining capabilities needed to finish the work.

**Done means a useful prod-lane change has been developed, communicated about, checked, and handed off through this arrangement on the actual local harnesses.** Starting servers, passing mocks, exchanging a greeting, or generating an empty scaffold is insufficient.

This handoff does not ask for another general dev-lane redesign. Models implementing a stage choose its internal design and reuse existing components. xor's later direction can change the stages or their boundaries.

## Starting point: verified facts

The inspected source is [uscient/agentscient, dev at 4303bfd](https://github.com/uscient/agentscient/tree/4303bfd8f38a50c5c9e092b7840ca57f4b5c00be). Recheck the branch before implementation because other work may have landed.

| Existing piece | Location / observed state |
| --- | --- |
| Writable coordination | ops/conductor/tools/coordination_mcp.py: assignments, send, inbox, acknowledgment, resolution, and observations |
| Optional dispatch (explicit owner request only) | ops/conductor/tools/dispatch_mcp.py: coord_launch, coord_status, coord_wait, coord_collect |
| Persistent native communication | ops/conductor/tools/sessions.py, courier.py, and session_adapters/ |
| Harness startup and configuration | ops/devlane/hooks/profiles.py; currently projects existing MCP settings into profiles |
| Symfony application | Root application; Symfony FrameworkBundle locked at 8.1.6 |
| Mate | symfony/ai-mate and symfony/ai-symfony-mate-extension locked at 0.13.0; mate/ contains configuration and instructions |
| Serena configuration | The repository MCP configuration currently exposes Serena directly using a different upstream pin from the separate v2 PoC |
| Additional dependencies | MakerBundle, the Monolog Mate extension, and the production MCP Bundle are not declared in the inspected root composer.json |

These facts establish reusable parts, not a claim that the complete MCP-only development path already works. For example, the Grok adapter's automatic permission handling currently recognizes coordination calls specifically.

Two reference repositories supply relevant implementations:

- [MCP PoC at 144fdde](https://github.com/xormania/mcp-poc-agentscient/tree/144fdde3be9f4dfee74474672baee028dff2540d): progressive discovery, a private Serena connection, v2 REPL, source accounting, and named verification. Its demonstrated fixture is Python; PHP capability must be demonstrated here.
- [Multi-harness proof](https://github.com/xormania/multi-harness-proof): native delivery and persistent-session reference. Much of this has already been adapted into Agentscient. Inspect that integration before copying anything else.

## Operating boundary

### What MCP-only means here

Model-initiated project operations go through the dev-lane MCP entry point. Native shell, direct filesystem editing/search, and independent project-access tools are disabled for participating agents. The selected profile must apply to every participating persistent harness. If the owner explicitly requests dispatch, it must also apply to those workers.

Backend services may launch PHP, Git, tests, Maker commands, and native harness processes. Native harness APIs also carry incoming messages. Those implementation mechanisms are compatible with MCP-only agent operations.

**Serena REPL remains enabled.** Its Python runs with provider-process permissions; disabling a harness shell does not make the REPL a sandbox. Code-work cells may compose Serena's discovery and editing operations. They must not be used as a shortcut to invoke the dev-lane CLI, operate Git independently, run Mate/Makers/checks, change coordination state, or impersonate workflow completion. Those operations have named dev-lane capabilities.

Keep workflow-state access and publication credentials under their existing dev-lane ownership; do not deliberately pass them into the Serena provider. Document actual access and limitations. Do not claim that session binding or routing makes arbitrary Python technically incapable of bypassing policy, and do not turn this work into a new general sandbox project.

### Ownership

| Component | Owns |
| --- | --- |
| Dev-lane services exposed through MCP | Work identity, assignments, peer messaging, project actions, source lifecycle, and workflow results |
| Serena | Code understanding, search, editing, and temporary REPL working state |
| Mate | Symfony observations and an optional home for custom Symfony development tools |
| Custom Makers | Generation of selected structures from project-owned patterns |
| Existing checks and CI | Verification and the repository's acceptance gate |
| Prod-lane Symfony services | The product behavior being built; its eventual MCP interface exposes those services |

The dev-lane remains independently operable without the Symfony kernel or vendor directory. A missing application dependency may make a Symfony capability unavailable; it must not take down coordination or the rest of the lane.

### Limits applying to every stage

- Work from current dev in an owned branch/worktree. Preserve other sessions' changes, processes, and records. Follow current task authorization for pushes and PRs; release to master remains outside this readiness work.
- Do not rewrite the coordination engine, replace its state store, port the dev-lane to PHP, or build another dispatcher/message bus.
- Do not restore historical hand-grant bureaucracy or add new approval layers. Hooks and diagnostics guide; CI remains the acceptance gate. Owner recovery access is not for agents to configure or use.
- Do not rewrite global harness settings, credentials, model/provider choices, or operator installations. Use project/run configuration and isolated provider dependencies.
- Do not redesign the prod-lane. Application changes are limited to development integration and the selected live acceptance feature.
- Do not edit vendor code, upgrade unrelated packages, add a second code editor, or copy the reference PoCs wholesale.
- A necessary cross-cutting fix is allowed when evidence connects it to a stage requirement. Explain that connection and keep the change focused.
- A missing capability is a gap to implement or explicitly report, never a reason to quietly enable a native shell fallback.

## Stage overview

| Stage | Required result |
| --- | --- |
| 1. MCP entry and discovery | Existing workflow operations accessible through a small, discoverable surface |
| 2. Native sessions and live communication | Restricted persistent participants can exchange messages during work |
| 3. Serena v2 code work | PHP discovery and edits work through the dev-lane with persistent REPL state |
| 4. Project execution and source lifecycle | Agents can build, check, manage dependencies, and hand off changes without shell |
| 5. Mate integration | Agents can inspect the actual Symfony application through MCP |
| 6. Maker integration | A custom Maker generates a useful project pattern through MCP |
| 7. Live development and handoff | The assembled system completes a real prod-lane task locally |

The stages describe outcomes, not mandatory PR counts or separate management processes. Combine compatible work and checks. Exercise live communication early, then reuse those sessions and checks as development capabilities become available.

## Stage 1 — Existing workflow behind one discoverable MCP entry

**Outcome:** Agents can find and use the existing dev-lane operations with little initial context.

**Requirements**

- Reuse the current coordination, live-session/courier, and evidence-reading services. Preserve their durable identities and behavior. Keep dispatch outside the default surface and workflow; it may be enabled and used only for an explicit owner request.
- Provide one logical agent-facing entry with progressive capability discovery, schema inspection, and validated invocation. Existing internal servers may remain separate processes.
- Bind calls to the actual participant, assignment, and workspace using trusted session context. A model-supplied identity must not substitute for that binding.
- Return bounded summaries, actionable errors, and references/pages for larger results. Discovery must say when a capability is unavailable and why.
- Use the PoC's discovery/broker work where appropriate. A schema returned as data is invoked through the broker; do not assume a host automatically installs it as a native tool.

**Done when**

- A real MCP client discovers and invokes both a read and a writable existing workflow operation.
- The results appear in the existing state/evidence records with the correct caller.
- The actual initial tool surface and a representative response size are recorded; full catalogs and transcripts are not injected by default.
- An unknown capability and invalid arguments produce useful diagnostics.

**May change:** MCP adapters, registry/discovery glue, focused serialization and binding code, related tests and guidance.  
**Do not touch:** Workflow semantics, role definitions, state ownership, or unrelated CLI contracts merely to simplify the adapter.

## Stage 2 — Persistent native sessions with MCP-only operations

**Outcome:** Codex, Claude Code, and Grok participate through the selected profile and retain live communication.

**Requirements**

- Reuse sessions, courier, and existing native adapters; retain each participant's native session across messages. Live peer communication is the main mechanism, without dispatching a job to obtain a response.
- Configure the actual installed harnesses to expose the intended MCP operations and disable native project-access tools. Prompt instructions alone do not establish this.
- Select permitted MCP configuration explicitly instead of inheriting every global/project server. Serena is reached through the dev-lane provider.
- Extend adapter permission handling to the required development capabilities, including Grok's coordination-specific handling.
- Keep queued, native submission, recipient acknowledgment, and resolution distinguishable. Detect delivery failures and preserve pending messages.
- Retain start, inspect, resume/recover, and stop operations. Stop only the run's owned processes.

**Done when**

- All three native harnesses can make an authorized workflow call under the profile.
- Each sends and receives a meaningful peer exchange; at least one message reaches a recipient with unfinished work, with a reply from its existing session.
- Native shell and direct-write canaries fail, while the equivalent permitted MCP operation succeeds once available.
- Detach/reconnect preserves session and message identity; a failed delivery has a visible recovery path.
- Requested settings, observed settings, versions, and remaining limitations are recorded. Busy delivery is not described as mid-token interruption.

**May change:** Run/profile projection, existing adapters, courier integration, and focused lifecycle diagnostics.  
**Do not touch:** Global harness configuration, account authentication, unrelated tmux sessions, or the proven native transport architecture without a demonstrated incompatibility.

## Stage 3 — Serena v2 beta REPL for PHP code work

**Outcome:** Agents understand and modify the Symfony source through Serena while the dev-lane retains the work record.

**Requirements**

- Use a pinned Serena v2 beta with REPL enabled in an isolated installation. The reference pin is b79e2a55f9d4072084977dd35bd07d31146d88b9; any replacement pin needs its own recorded verification.
- Reuse the private MCP-to-MCP provider connection and persistent session pattern. Bind sessions to the intended assignment/worktree and separate participants' temporary state.
- Provide semantic and text discovery, references, file reading, and the edits required by the selected task through Serena. Verify the PHP language backend on actual PHP.
- Preserve intermediate REPL state and return selected, bounded results rather than repeatedly sending full objects or files to the model.
- Treat cells as potentially mutating. Record source changes and invalidate affected verification. A cell can modify files and then return an error; inspect Serena's textual error results as well as transport status.
- Report provider restart or lost REPL state clearly. Durable workflow state must survive independently.

**Done when**

- A native participant finds a PHP class and relevant references, makes a meaningful edit, and reads the changed result through this route.
- An intermediate value survives across cells in the same session.
- A controlled edit-then-error remains visible as a partial change and cannot leave a stale successful verification attached.
- Restarting the provider preserves the assignment record and clearly reports the loss of temporary REPL state.

**May change:** Provider adapter, isolated dependency pin, workspace/session binding, and relevant PHP fixtures/checks.  
**Do not touch:** Serena upstream, operator-wide Serena installations, or core workflow state through REPL. Do not substitute a new editor for Serena.

## Stage 4 — Complete project actions and source lifecycle

**Outcome:** An agent can finish ordinary local development without escaping through shell or repurposing REPL.

**Requirements**

- Provide named, structured operations for the actual task: dependency installation/refresh, container/cache build, linting, tests, application exercise, diagnostics, and necessary background-process lifecycle.
- Use the selected project's PHP environment and directory. Return status, bounded output, and an actionable failure explanation; support collection/cancellation for long-running work.
- Reuse source adapters for workspace preparation, diff, checkpoint, reconcile/conflict handling, and authorized publication/PR handoff. Keep Git mechanics behind the application contract.
- Cover normal file lifecycle gaps through Serena-backed capabilities rather than forcing agents to invent command equivalents.
- Apply shared source-change accounting to Serena edits, Maker generation, and other mutating project actions. Check results must identify the content actually checked.
- Every operation accepts its own parameters, not a free-form command, executable, or argv escape hatch.

**Done when**

- A participant installs or refreshes required project dependencies, builds the container, observes a failing relevant check, repairs the issue, and reruns it successfully.
- It inspects and records its diff/candidate, handles a controlled stale/conflicting source condition, and reaches the authorized handoff path.
- Failures are diagnosable and retryable through MCP. No undocumented manual shell step is required to finish the representative task.
- Publication behavior is exercised against a disposable target or within explicit task authorization.

**May change:** Existing execution/source adapters, project action definitions, and narrowly relevant project scripts.  
**Do not touch:** Branch protections, CI acceptance policy, owner recovery, production databases, unrelated dependency versions, or unrelated source history.

## Stage 5 — Symfony AI Mate through the same entry

**Outcome:** Agents can use Symfony's own observations to guide reuse and diagnose changes.

**Requirements**

- Start with the installed Mate and Symfony extension. Add extensions only for concrete missing capabilities, such as Monolog inspection.
- Translate MCP calls into named Mate operations with validated parameters and structured results. No model-provided shell command.
- Support tool discovery, schema/parameter inspection, service search/detail, and applicable profiler resources.
- Bind inspection to the assignment's worktree, PHP runtime, and Symfony environment. Distinguish source facts from compiled-container or captured-request facts; refresh artifacts after relevant changes.
- Report missing/stale container, profiler, or log data honestly. Preserve Mate's treatment of application-derived output as data.
- Keep this integration optional to core dev-lane operation.

**Done when**

- An agent finds a registered Symfony service and inspects useful dependency/wiring information through MCP.
- After a source/configuration change and rebuild, inspection reflects the new state.
- It diagnoses an exercised application behavior using captured request/profiler or log data where that capability is configured.
- Missing vendor/cache data yields a useful capability error while coordination remains usable.

**May change:** Mate integration, project-local Mate configuration/extensions, and minimal diagnostic setup.  
**Do not touch:** Mate vendor code, unrelated application configuration, or the dev-lane's runtime independence. Do not install the whole Symfony AI stack as a prerequisite.

## Stage 6 — Custom Makers for repeatable project patterns

**Outcome:** A useful custom generator is available as a named MCP development capability.

**Requirements**

- Add MakerBundle as a development dependency and implement one concrete recurring pattern required by the selected development work.
- A relevant example is generating a thin MCP adapter around an existing application service. The generator should encode existing design decisions and reuse, not invent new application architecture.
- Expose it through a custom Mate tool or the existing Symfony action adapter; choose the smaller integration. Supply all required parameters without interactive prompts.
- Validate names, targets, dependencies, and collisions before writing. Do not overwrite unrelated existing implementation; return generated/changed paths and useful diagnostics.
- Register generation as a source mutation in the same assignment. Serena performs the subsequent implementation and edits.
- Keep generator logic/templates project-owned and dependency versions pinned. Verify generated output against this project's Symfony version.

**Done when**

- A native participant discovers the custom generation capability and invokes it through MCP.
- Generated code loads and follows the selected pattern; Serena can complete or modify it.
- A meaningful integration check exercises the generated connection. A skeleton test alone is not behavioral evidence.
- Repeating generation against an existing target or providing an invalid target produces the documented result without clobbering work.

**May change:** Development dependency/configuration, custom Maker/template files, the exposing tool, and focused generator fixtures.  
**Do not touch:** Vendor templates, unrelated application services, or a broad generation framework. Generated code does not become a runtime dependency on MakerBundle.

## Stage 7 — Real local development and operational handoff

**Outcome:** The assembled system earns its place by completing useful prod-lane work.

**Requirements**

- Select one small, useful feature from the current prod-lane objectives and state its observable result before running the task. Feature selection must not silently decide a new product architecture.
- Use the real local harnesses with the selected profile. Keep persistent participants active for coordination and review.
- Complete the assignment through discovery, Serena editing, relevant Mate inspection, named project actions, source handoff, and normal CI. Include the custom Maker where the selected pattern applies; retain Stage 6 evidence otherwise.
- Include a substantive peer question and reply during unfinished work. Record at least one diagnosed development failure and its correction.
- Demonstrate a thin prod-lane MCP interface to an application service, using the Symfony MCP Bundle, within the selected feature or a focused integration fixture. Distinguish this from the dev-lane MCP used to build it.
- Retain concise evidence and provide local start, inspect, resume/recover, stop, and disable instructions. Disabling this integration preserves existing records and unrelated sessions.

**Done when**

- The useful feature's acceptance behavior passes on the resulting candidate.
- Actual calls show project work went through the dev-lane MCP, with Serena REPL and Maker generation accounted for.
- Live peer exchanges occur in retained native sessions; there is no hidden manual shell rescue.
- The product MCP interface calls the intended application service and has its own integration evidence.
- Another session can follow the runbook without reconstructing this conversation.
- The implementation handoff identifies the revision, versions, tested harnesses, evidence, remaining gaps, and how to recover.

**May change:** Final integration fixes, run configuration/runbook, and the bounded product feature or fixture.  
**Do not touch:** Unrelated product architecture, separate prod-lane CI, broad dev-lane cleanup, or global/operator settings.

## Validation and handoff discipline

Reuse existing tests and fixtures. Add checks for changed boundaries and concrete failure risks; do not create a new test framework or multiply tests merely to mirror implementation.

An implementer's stage handoff needs only:

- Revision and behavior delivered.
- Relevant checks and a short acceptance trace.
- Files/areas changed and why any cross-cutting change was necessary.
- Remaining gaps and the next usable entry point.

Mocks establish adapter behavior, not live vendor compatibility. Server schema size establishes surface size, not measured model-token savings. Record actual outcomes without requiring a separate benchmark campaign.

Overall readiness remains incomplete while a required capability or selected harness path is missing. Diagnose and close the gap; do not weaken the stated goal or substitute a simulated pass. Once the integrated acceptance and handoff are complete, stop expanding readiness scope and use the dev-lane to build the product.

## Source references and version notes

Repository facts above were inspected on 2026-09-25. These links are implementation references; current owner direction takes precedence over historical prescriptions within them.

- [Current repository guidance](https://github.com/uscient/agentscient/blob/4303bfd8f38a50c5c9e092b7840ca57f4b5c00be/AGENTS.md)
- [Coordination MCP implementation](https://github.com/uscient/agentscient/blob/4303bfd8f38a50c5c9e092b7840ca57f4b5c00be/ops/conductor/tools/coordination_mcp.py)
- [Dispatch MCP implementation](https://github.com/uscient/agentscient/blob/4303bfd8f38a50c5c9e092b7840ca57f4b5c00be/ops/conductor/tools/dispatch_mcp.py)
- [Native session adapters](https://github.com/uscient/agentscient/tree/4303bfd8f38a50c5c9e092b7840ca57f4b5c00be/ops/conductor/tools/session_adapters)
- [Harness profiles](https://github.com/uscient/agentscient/blob/4303bfd8f38a50c5c9e092b7840ca57f4b5c00be/ops/devlane/hooks/profiles.py)
- [Application dependencies](https://github.com/uscient/agentscient/blob/4303bfd8f38a50c5c9e092b7840ca57f4b5c00be/composer.json)
- [Serena integration reference](https://github.com/xormania/mcp-poc-agentscient/blob/144fdde3be9f4dfee74474672baee028dff2540d/docs/serena-integration.md)
- [Symfony AI Mate](https://symfony.com/doc/current/ai/components/mate.html) and [extensions](https://symfony.com/doc/current/ai/components/mate/extensions.html)
- [MakerBundle custom Makers](https://symfony.com/bundles/SymfonyMakerBundle/current/index.html#creating-your-own-makers)
- [MakerBundle scope and compatibility notes](https://github.com/symfony/maker-bundle#scope): documentation describes custom Makers, while the README limits broad upstream customization. Command options and generated output can change between minor versions.
- [Symfony MCP Bundle](https://symfony.com/doc/current/ai/bundles/mcp-bundle.html)

Use documentation matching the selected dependency versions. A live documentation page or old generated instruction file is not evidence that a capability is installed and working in this checkout.

