#!/bin/sh
set -e
cargo metadata --offline --format-version 1 >/dev/null || exit 127
exec cargo test --offline --locked --quiet --test rc02
