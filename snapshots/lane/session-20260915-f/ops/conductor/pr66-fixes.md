# PR 66 — bounded release corrections

Owner, 2026-09-05: resolve the release review findings. Measured baseline:
dev c0ce300. No data rewriting, path cleanup, Symfony work, or P3 sweep.

## Couplings to correct

1. Watchdog launcher census must recognize a Python 3 interpreter spelled
   as a basename or as an absolute executable path, including versioned
   python3.N. Keep the count explicitly heuristic; do not count unrelated
   commands. The pattern passed to pgrep must be valid POSIX ERE.
2. A nonterminal job with no usable worker PID is unobservable, not running.
   Report that condition explicitly, exclude it from running/long warnings,
   and reconsider it on later ticks when usable worker state appears.
   Keep closed, settling, confirmed-gone and live-worker behavior intact.
3. Retained Claude usage currencies must be numeric, nonnegative and finite;
   bool is not a currency. Invalid retained usage yields the existing
   malformed-usage gap, not a measured row or partial totals. Preserve zero,
   valid positive numbers, missing-field behavior and last-write dedup.
4. The CI two-job oracle must run with Python's standard library alone.
   Remove its undeclared YAML dependency without weakening the existing
   trigger, branch, runner, filter, and distinct-step-order assertions.
   A bounded parser for the workflow's used YAML surface must refuse syntax
   outside that surface rather than silently ignore structural content.
   Do not add a dependency installer or alter the live workflow to fit tests.
5. Land's author override documentation must describe the existing tested
   behavior: preserve LANE_AUTHOR and requested-author commits; reauthor only
   other authors. No production authorship behavior change is requested.

The unittest wrapper diagnostic for a broken Python stdlib installation is
P3 polish and deferred under the owner's priority ruling.

Production producer does not write or approve tests. An independent producer
adds only focused regression coverage and repairs the CI oracle dependency.
Root adjudicates that oracle. One integrated suites floor; no unrelated test
expansion. Grok quality and Daybreak security reviews before landing to dev;
PR 66 remains draft and its master merge belongs to the owner.
