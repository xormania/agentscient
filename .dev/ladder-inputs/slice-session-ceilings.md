# Slice session-ceilings (S)

Tests-only amendment on lane/session-budget. Implementation of the row is not this slice.

## Why these integers (measured, not hoped)

Fable session c1b9ce7c, 2026-09-03 19:00Z–2026-09-04 17:12Z: 1377 turns, average context 448k, ~70 hook refusals (clipped-sweep 25). Churn doc "the test" was 100 / 200000 / 10. That set kills good work: this repository's law prefix already exceeds 200k, so every tool call would refuse; 10 refusals is below one false-positive class.

Planted production integers for the session-budget row:

- `SESSION_TURNS_CEILING=500` — a driver day of several slices stays under; 1377-turn 22h session is past it.
- `SESSION_AVG_CONTEXT_CEILING=400000` — compact-or-close-at-300k still has headroom; Fable's 448k average (never compacted until the end) is past it.
- `SESSION_REFUSALS_CEILING=25` — equal to the clipped-sweep false-positive count; after false-positive-rows lands this has headroom; 70-refusal runaway is past it.

Change only the three constants and the planted conf strings in `ops/devlane/hooks/tests/test_matrix.py`. Keep "past ceiling refuses" relative to those constants. Do not implement matrix.py in this slice.

slice	session-ceilings	S
bucket	session-ceilings	S	ops/devlane/hooks/tests/test_matrix.py
