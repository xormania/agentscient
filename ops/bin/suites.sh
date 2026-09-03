#!/usr/bin/env bash
# suites.sh — run every lane suite the way CI runs it, so "is it green?"
# has one answer here, in a hook, and in the workflow. Every suite runs
# with the repository root as cwd (the hooks under test ask git about
# the tree they are in) and its own tests directory as the discovery
# start, which unittest also puts on sys.path so `import support`
# resolves. One summary per suite; exit 1 if any suite is not OK.
# Stdlib only: no pip step, no cached oracle.
set -u
here=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(CDPATH='' cd -- "$here/../.." && pwd)
cd "$root" || exit 2
rc=0
for app in dispatch harness task telemetry hooks fixtures workflow; do
    d="ops/devlane/$app/tests"
    [[ -d $d ]] || { printf '== %-10s ABSENT (no tests directory)\n' "$app"; continue; }
    printf '== %s\n' "$app"
    python3 -m unittest discover -s "$d" -p 'test_*.py' || rc=1
done
exit "$rc"
