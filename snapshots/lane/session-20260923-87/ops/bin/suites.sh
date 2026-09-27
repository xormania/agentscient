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
# A family too slow to run in one process is discovered as disjoint
# slices, each its own process and its own summary, so the family costs
# its slowest slice rather than its sum. Measured 2026-09-16 at
# d919c982, one discover per file over all 69 files of
# ops/conductor/tests: 1478 tests, 334s summed, and one file,
# test_coordination.py, is 60s of that. In one process the family cost
# ~300s of a ~330s lane job while every other suite finished inside
# 100s, so the whole lever waited on it (owner, 2026-09-16: "CI is
# starting to take a lot of time - can we get it faster? Delegate").
# Stdlib only: no pip step, no cached oracle.
# Lint runs first in the output and beside the suites in time: the CI
# lane job runs `ruff check .` and two reds on 2026-09-12 were lint on a
# locally green tree (owner, 2026-09-13, ruling 4). A host without ruff
# reads ABSENT and not OK; a lint it could not run is not a green lint.
set -u
here=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(CDPATH='' cd -- "$here/../.." && pwd)
cd "$root" || exit 2
# A suite entry is <tests dir>, or <tests dir>:<discovery pattern> for
# one slice of a sharded family. The slices below are cut by measured
# cost and not by file count: c is 93s, l is 97s, o and w together 79s,
# everything else 65s. The last pattern is the complement of the others,
# so a file added later always lands in a slice. Going finer buys
# nothing: test_coordination.py alone is 60s, and devlane/hooks at ~100s
# is the lever's pole once this family is split.
conductor_shards=('test_[c]*.py' 'test_[l]*.py' 'test_[ow]*.py' 'test_[!clow]*.py')
suites=(ops/devlane/{dispatch,harness,task,telemetry,hooks,fixtures,workflow}/tests ops/testkit/tests)
for pat in "${conductor_shards[@]}"; do suites+=("ops/conductor/tests:$pat"); done
suites+=(.claude/skills/pr-overview/tests)
# The partition is proved on every run, never trusted: a file that falls
# out of every slice is a suite that shrank in silence, and that failure
# reads green. Refused before anything runs, on docs/wire.md: exit 2, one
# stderr line, stdout empty.
missed=()
for d in $(for e in "${suites[@]}"; do [[ $e == *:* ]] && printf '%s\n' "${e%%:*}"; done | sort -u); do
    pats=()
    for e in "${suites[@]}"; do [[ $e == "$d":* ]] && pats+=("${e#*:}"); done
    for f in "$d"/test_*.py; do
        [[ -e $f ]] || continue
        b=${f##*/}
        hits=0
        for p in "${pats[@]}"; do [[ $b == $p ]] && hits=$((hits + 1)); done
        [[ $hits == 1 ]] || missed+=("$b in $hits of ${#pats[@]}")
    done
done
if [[ ${#missed[@]} -gt 0 ]]; then
    printf 'shard: expected every test file of a sharded family in exactly one shard; found %s; needed a shard set that takes each file once, the last pattern being the complement of the others\n' "${missed[*]}" >&2
    exit 2
fi
logs=$(mktemp -d "${TMPDIR:-/tmp}/suites.XXXXXX") || exit 2
trap 'rm -rf "$logs"' EXIT
run_one() {  # run_one <tests dir> <discovery pattern> <log key>
    python3 -m unittest discover -s "$1" -p "$2" > "$logs/$3" 2>&1
    echo $? > "$logs/$3.rc"
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
for e in "${suites[@]}"; do
    d=${e%%:*}
    [[ -d $d ]] || continue
    pat='test_*.py'; [[ $e == *:* ]] && pat=${e#*:}
    key=${e//[^A-Za-z0-9]/_}
    if [[ ${SUITES_SERIAL:-0} == 1 ]]; then
        run_one "$d" "$pat" "$key"
    else
        run_one "$d" "$pat" "$key" &
    fi
done
wait
rc=0
printf '== ruff\n'
cat "$logs/ruff"
[[ $(cat "$logs/ruff.rc" 2>/dev/null || echo none) == 0 ]] || rc=1
for e in "${suites[@]}"; do
    d=${e%%:*}
    app=${d%/tests}; app=${app#ops/}; app=${app#.claude/skills/}
    [[ $e == *:* ]] && app="$app ${e#*:}"
    [[ -d $d ]] || { printf '== %-18s ABSENT (no tests directory)\n' "$app"; continue; }
    key=${e//[^A-Za-z0-9]/_}
    printf '== %s\n' "$app"
    cat "$logs/$key"
    status=$(cat "$logs/$key.rc" 2>/dev/null || echo none)
    [[ $status == 0 ]] || rc=1
done
exit "$rc"
