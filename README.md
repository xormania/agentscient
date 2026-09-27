# Agentscient

Agentscient is a Symfony application. Its foundation includes the Symfony MCP
Bundle, Maker Bundle, and Symfony AI Mate. Runtime versions and dependencies are
defined in `composer.json` and `composer.lock`.

The development support in [`devtools/`](devtools/README.md) exposes shared work
tools and CO/XO command tools through role-bound MCP sessions. CO uses `direct`
and `monitor`; XO uses `orchestrate`, `monitor`, and `steer`. Services bind work,
start configured collaborators, supply briefs, route live messages, and retain evidence. Live harness transport,
telemetry, work orders/jobs, artifacts, and GitHub PR/CI services back this surface;
their lower-level tools remain on an explicit operator connection during setup.
It runs independently of PHP and the application.

## Symfony application

```sh
composer install
php bin/console about
php bin/console list make
vendor/bin/mate tools:list
vendor/bin/phpunit
```

Application code belongs in `src/`, with configuration in `config/` and tests in
`tests/`. The application is a foundation, not a completed product.

## Live development support

See [`devtools/README.md`](devtools/README.md) for setup, MCP configuration,
session management, work tracking, GitHub PR/CI work, artifact storage, messages,
and telemetry.
Configured jobs now get managed Git workspaces, checkpoints, recovery, upstream
refresh, and PR submission through outcome tools. There is no general shell tool.
Installed Makers, Mate diagnostics and configured validation now have scoped MCP
tools and retained asynchronous results. Serena and final review/acceptance are
being integrated toward the documented Monday readiness target.

The proposed control-plane direction, CO/XO relationship, role profiles, and draft
tool catalog are recorded in
[`docs/control-plane-roles-and-tools.md`](docs/control-plane-roles-and-tools.md).
That document separates the intended design from the capabilities available today.

The previous development system was removed. Its full pre-removal snapshot is
preserved on [`shit`](https://github.com/uscient/agentscient/tree/shit) at
`456457b9a0a9eb1ff285ee2d3e40535b6f722cdb`.
