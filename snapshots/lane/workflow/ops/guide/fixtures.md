---
name: guide-fixtures
description: The fixtures mini app — measured harness store shapes, so telemetry tests assert against reality rather than a guess.
covers:
  - ops/devlane/fixtures/
---

# The fixtures app

`ops/devlane/fixtures/stores.py` builds fake-but-faithful harness session
stores for the telemetry tests. It exists because the alternative —
inventing a plausible JSON shape — produces tests that agree with the
reader's assumptions instead of with the harnesses.

```python
import stores

stores.build_claude_store(root, slug, base_timestamp=..., cwd=repo,
                          session_id="s1", model="claude-fable-5",
                          effort="high", marker="probe")
stores.build_codex_store(root, base_timestamp=..., cwd=repo, ...)
stores.build_grok_store(root, cwd=repo, base_timestamp=...,
                        session_id="g1", model="grok-4.6",
                        marker="probe", usage_runs=[[{...}]])
```

## What "measured" means here

Every shape in this module was read off a real session store, and the
differences between harnesses are the point:

- **Claude** writes one JSONL file per session under a slug directory;
  usage rides `message.usage`, and a message id can be re-emitted with
  grown usage, which is why readers take last-wins by id.
- **Codex** splits its metadata: `session_meta` carries the id, cwd
  and the long prompt; model and effort live only on `turn_context`.
  Token counts are **cumulative**, so the last one is the spend.
- **Grok** uses epoch-integer timestamps in `updates.jsonl` and ISO
  timestamps in `events.jsonl` — and only `updates.jsonl` carries
  usage, on `turn_completed` events. `summary.json` never does.

The docstrings record which of these were verified and when. When a
harness changes, fix the fixture first: a reader updated without its
fixture is a rule with nothing to contradict it.

## The rule the fixtures follow

Usage is emitted **verbatim** from what the caller passes
(`usage_runs`), never invented or normalised. A fixture that quietly
fills in a missing currency would hide exactly the gap the readers are
supposed to report as `unrecorded`.

## Working on this app

```sh
python3 -m unittest discover -s ops/devlane/fixtures/tests
```

Fixture changes ripple into the telemetry suites, so run both. There
is a pin on the module's own bytes in the telemetry tests: it catches
a fixture edited to match a reader rather than a harness.
