# CI tracking with thresholds

Owner, 2026-09-04, in session: "one of the services I plan is for
constant CI tracking with thresholds to optimize".

What happened the same hour: the suites step of one CI run took 4 min
27 s where the runs before it took 46 to 50 s (run 33842564639 on
lane/wait-loop, the one-second tick slowing the dispatch tests), and
nothing said so until the owner looked at the run list. The step
timings were there; no reader compared them to anything.

The shape, in the lane's pattern: a reader of each run's step timings
(`gh run view --json jobs`) into a SQLite store beside the handwork,
findings and skills stores, with a tracked export; thresholds as data
in the lane conf, per step, with a tolerance; a finding on the wire
(exit 1, never 2) when a step crosses its threshold, so a slow runner
is never silent and never blocks a merge by itself; the thresholds
recalibrated from the store's history, which is the living-system loop
(I-012) applied to CI. The same store answers the meter's question for
CI: seconds per step per run, runner, and branch. In the product, a
service with the four projections. Not ruled.
