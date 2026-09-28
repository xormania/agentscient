#!/usr/bin/env bash
set -euo pipefail

[[ "$RUNNER_OS/$RUNNER_ARCH" == Linux/X64 ]] || { echo 'The pinned PHP runtime requires Linux/X64'; exit 1; }
ci_url=$1
ci_digest=$2
[[ "$ci_digest" =~ ^[0-9a-f]{64}$ ]] || { echo 'Expected a pinned SHA-256 digest'; exit 1; }
ci_cache="$RUNNER_TOOL_CACHE/agentscient-php"
mkdir -p "$ci_cache"
ci_archive="$ci_cache/$ci_digest.tar.gz"

verify_archive() {
    [[ -f "$1" ]] && printf '%s  %s\n' "$ci_digest" "$1" | sha256sum --check --status
}

# Cache only the checksum-verified download. Every job extracts its own runtime;
# concurrent runners cannot publish a partial archive or replace global PHP.
if verify_archive "$ci_archive"; then
    echo 'Pinned PHP download: cache hit'
else
    echo 'Pinned PHP download: cache miss'
    ci_download=$(mktemp "$ci_cache/.download.XXXXXX")
    trap 'rm -f "$ci_download"' EXIT
    curl --fail --silent --show-error --location --retry 3 --connect-timeout 15 --max-time 120 "$ci_url" -o "$ci_download"
    verify_archive "$ci_download" || { echo 'PHP archive checksum mismatch'; exit 1; }
    mv -f "$ci_download" "$ci_archive"
fi

ci_php=$(mktemp -d "$RUNNER_TEMP/prod-php.XXXXXX")
tar --no-same-owner -xzf "$ci_archive" -C "$ci_php" php
"$ci_php/php" --version
printf '%s\n' "$ci_php" >> "$GITHUB_PATH"
