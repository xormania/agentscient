# Contributions

Use an owned branch based on `dev` and submit a PR into `dev`. A PR should explain
the concrete problem, resulting behavior, verification, and any remaining limits.
Keep commits focused and preserve source/license attribution for reused code.
Use `Source:` and `Co-Authored-By:` trailers where applicable.

Run the relevant checks in `.github/workflows/ci.yml`. The `lane` result aggregates
the live MCP tests and the Symfony application's checks. No additional repository
workflow, record, permission, or review machinery is required.
