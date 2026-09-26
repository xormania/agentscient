# CI

`ci.yml` runs the focused live MCP tests and the Symfony application's checks.
The `lane` result succeeds only when both jobs succeed. It retains that check name
for branch protection compatibility; there is no development workflow engine.

The Symfony job validates and installs locked Composer dependencies, checks the
PHP platform, lints PHP/YAML/container configuration, and runs PHPUnit.
`CI_RUNNER_MODE=local` selects the registered self-hosted runner; `hosted` or an
empty value selects Ubuntu. The legacy scope selector, receipts, and policy
checks have been removed.
