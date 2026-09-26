# Developing this Symfony application

Use the selected PHP and Symfony capabilities before adding infrastructure.
The four questions are different: what the framework provides, what Composer
installed, what the selected environment wires, and what the project implements.
An empty service search does not establish that Symfony lacks the feature.

Before a product change, load `project_context` through the dev-lane MCP. Use
`mate_skills` and `mate_skill` for the relevant installed Mate guidance,
`mate_services`/`mate_service` for actual wiring, and Serena for existing source.
The installed versions and source references in the response select the APIs to
use. Check their official documentation or installed source when uncertain.

For MCP tools, put `Mcp\Capability\Attribute\McpTool` on a suitable service's
public method. The application's existing autoconfiguration discovers it and
autowiring injects its dependencies. MCP Bundle supplies schema discovery and
invocation. A new wrapper or Maker is unnecessary for that case. Introduce an
adapter only when its actual inputs, output or boundary need to differ.

For other work, check the relevant Symfony component and its supported attributes
and configuration first. Examples include Console commands, Messenger handlers,
event listeners, validation, serialization and service selection. Use supported
PHP types, enums, promoted properties, readonly state and other language features
when they directly express the required behavior. Do not invent substitutes or
add features merely to demonstrate newer syntax.

Give the next live participant a compact task-specific handoff: applicable native
facility and documentation/source, reusable project service, observed wiring,
remaining design gap, allowed changes and meaningful completion check. Reading a
skill is not proof of a good design. Review the resulting diff for unnecessary
custom infrastructure and exercise the chosen native connection.

When upstream Mate instructions show CLI commands, use the corresponding named
dev-lane capabilities in an MCP-only session. Serena edits prod-lane source;
Mate inspects it; named actions refresh and check it. A custom Maker is appropriate
only for a demonstrated recurring structure not covered by existing facilities.

This guidance follows KNOW-1 and KNOW-2 in the 2026-09-09 Symfony capability
specification and the owner's 2026-09-26 correction. It supplies working context,
not a new permission gate or a guarantee of model judgment.
