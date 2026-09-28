#!/usr/bin/env bash
# php-suite.sh — the Symfony project's own suite, the way CI runs it: the
# manifest and lock agree, install from the lock, lint, the kernel boots,
# PHPUnit over the project and every package, and Mate answering from the
# compiled container. The host toolchain lives in ~/.local/bin on the
# runners; put it on PATH first. Any failure stops the run.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
composer validate --strict
composer install --prefer-dist --no-progress --no-interaction
find src packages -name '*.php' -print0 | xargs -0 -r -n50 php -l
php bin/console about
vendor/bin/phpunit
vendor/bin/mate tools:call symfony-services --query=router --limit=10 --format=json | jq -e '.untrusted_data.services["router.default"]' >/dev/null
vendor/bin/mate tools:list
