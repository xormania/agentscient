#!/usr/bin/env bash
# suites.sh — run every lane suite the way CI runs it, so "is it green?"
# has one answer here, in a hook, and in the workflow. Every suite runs
# with the repository root as cwd (the hooks under test ask git about
# the tree they are in) and its own tests directory as the discovery
# start, which unittest also puts on sys.path so `import support`
# resolves. The suites run concurrently, each to its own log, and the
# logs are printed in the fixed order below once all have finished, so
# the output reads the same as a serial run; SUITES_SERIAL=1 runs them
# one after another. One summary per suite; exit 1 if any suite is not
# OK, and a suite that left no exit status counts as not OK.
# Stdlib only: no pip step, no cached oracle.
# Lint runs first in the output and beside the suites in time: the CI
# lane job runs `ruff check .` and two reds on 2026-09-12 were lint on a
# locally green tree (owner, 2026-09-13, ruling 4). A host without ruff
# reads ABSENT and not OK; a lint it could not run is not a green lint.
set -u
here=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(CDPATH='' cd -- "$here/../.." && pwd)
cd "$root" || exit 2
suites=(ops/devlane/{dispatch,harness,task,telemetry,hooks,fixtures,workflow}/tests ops/testkit/tests ops/conductor/tests .claude/skills/pr-overview/tests)
logs=$(mktemp -d "${TMPDIR:-/tmp}/suites.XXXXXX") || exit 2
trap 'rm -rf "$logs"' EXIT
run_one() {  # run_one <tests dir> <log key>
    python3 -m unittest discover -s "$1" -p 'test_*.py' > "$logs/$2" 2>&1
    echo $? > "$logs/$2.rc"
}
lint() {  # the lane job's ruff step, verbatim: the version, then the check
    if command -v ruff > /dev/null 2>&1; then
        { ruff --version && ruff check .; } > "$logs/ruff" 2>&1
        echo $? > "$logs/ruff.rc"
    else
        echo 'ruff: expected ruff on PATH, the CI lane job runs it; found ABSENT; needed install ruff' > "$logs/ruff"
        echo 2 > "$logs/ruff.rc"
    fi
}
if [[ ${SUITES_SERIAL:-0} == 1 ]]; then lint; else lint & fi
for d in "${suites[@]}"; do
    [[ -d $d ]] || continue
    key=${d//\//_}
    if [[ ${SUITES_SERIAL:-0} == 1 ]]; then
        run_one "$d" "$key"
    else
        run_one "$d" "$key" &
    fi
done
wait
rc=0
printf '== ruff\n'
cat "$logs/ruff"
[[ $(cat "$logs/ruff.rc" 2>/dev/null || echo none) == 0 ]] || rc=1
for d in "${suites[@]}"; do
    app=${d%/tests}; app=${app#ops/}; app=${app#.claude/skills/}
    [[ -d $d ]] || { printf '== %-18s ABSENT (no tests directory)\n' "$app"; continue; }
    key=${d//\//_}
    printf '== %s\n' "$app"
    cat "$logs/$key"
    status=$(cat "$logs/$key.rc" 2>/dev/null || echo none)
    [[ $status == 0 ]] || rc=1
done
exit "$rc"
