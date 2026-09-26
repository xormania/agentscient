# Agentscient

Agentscient is a Symfony application. Its foundation includes the Symfony MCP
Bundle, Maker Bundle, and Symfony AI Mate. Runtime versions and dependencies are
defined in `composer.json` and `composer.lock`.

The development support in [`devtools/`](devtools/README.md) contains only an MCP
server, local telemetry, and live communication between persistent native
harnesses. It runs independently of PHP and the application.

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
session management, messages, and telemetry. The MCP surface has no shell or
project editing/execution capabilities.

The previous development system was removed. Its full pre-removal snapshot is
preserved on [`shit`](https://github.com/uscient/agentscient/tree/shit) at
`456457b9a0a9eb1ff285ee2d3e40535b6f722cdb`.
