# Developing this Symfony application

Check installed PHP/Symfony packages and native component capabilities before
adding infrastructure. Use attributes, autowiring, autoconfiguration, and PHP's
supported language features where they express the behavior directly.

For an MCP tool, `Mcp\Capability\Attribute\McpTool` on a suitable public service
method participates in the application's existing MCP discovery. A separate
wrapper or custom Maker is needed only when the actual operation requires one.
The basic Maker commands are already installed for application development.

Mate reports measured application facts through its documented tools. Discover
them with `vendor/bin/mate tools:list` and inspect inputs with `tools:inspect`.
Local agents use `framework_inspect` for installed Maker metadata and Mate diagnostics,
`framework_generate` for basic Makers, and `work_check` for configured validation.
The control plane supplies the job workspace, retains evidence, and routes results.
Serena is the separate source-editing provider.
