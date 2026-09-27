# Grok's cost ticks are nanodollars (meter unit B, verified against list prices)

Measured 2026-09-04 from the owner's Grok session report
(`.xor/tmp/grok-usage.md`, 12 counted grok dispatches, 82,978,431,400
ticks) against a list-price estimate per run (input $3/M, cached input
$0.75/M, output $15/M, the grok-4 family's published rates as
remembered; grok-4.6's own sheet not consulted):

- nine of twelve runs: ticks / 1e9 is 5 to 9 percent above the estimate
  (ratio 1.05 to 1.09), the shape of a small price difference, not a
  different unit;
- three runs, the largest contexts (8.8M, 11.6M and 3.3M tokens with
  long single turns), sit at 1.29 to 1.49, the shape of long-context
  pricing above a threshold, which the estimate did not model;
- total: $82.98 by ticks against $69.91 by the flat estimate.

Reading: ticks are USD times a billion. The meter may print
`cost_usd≈ticks/1e9` for Grok with the stamp "scale verified against
list prices within 9 percent on nine of twelve runs; long-context rates
not modelled". A console figure from the owner would make it exact.
