Revision complete. Three sites left `shapes`, two stayed unresolved.

RESULT: DONE

RULE: `shapes` still admits every dict literal carrying a literal `"type"` key (§5.9). A site leaves `shapes` **only** on positive proof that it cannot be an event constructor — never on failure to prove that it is one. Two proofs, both in `extract/events.py:not_an_event()`:

- **E1 — the `"type"` value can never be a `str`**: a dict/list/set/tuple display, a comprehension, a lambda, or a non-string constant. `Chain.append` (`ops/devlane/workflow/chain.py:192`, `if not isinstance(event.get("type"), str) or not event["type"]: raise Refusal`) rejects any such dict, so no runtime turns it into an event.
- **E2 — the dict is a pure projection of one other object**: every value in it is a constant-key read (`B["k"]` / `B.get("k")`) of the *same* base `B`, and the `"type"` value is that object's own `"type"`. It re-describes an event it was handed; it never names a type.

Everything else stays, `{"unresolved": ...}` if the type does not resolve. Reaching `chain.append` is recorded as `provenance.shapes[*].constructor_evidence` but is **evidence only** — it neither includes nor excludes, so an event built somewhere the extractor cannot trace is never dropped. Excluded sites are quoted in full under `provenance.excluded` with the test that dropped them, so the narrowing is auditable rather than silent.

EXCLUDED:
- `mcp_server.py:263` (E1) — the `"type"` value is a `Dict` node, `{'type': 'array', 'items': {'type': 'string'}, 'description': 'event types, e.g. receipt.red'}`. This is the `properties` map of `wf_log`'s `inputSchema`; `type` is the name of a filter argument, and its value is a JSON-Schema fragment. `chain.py:192` would refuse it. Verdict `events-0801e281` is right.
- `query.py:308` (E2) — `{"seq": e["seq"], "type": e.get("type"), "time": e["time"]}` in `status_one_body`, every value read from `e`, iterating `projection.events`. It is the compact log line of an event that already exists.
- `wf.py:501` (E2) — the same three-field projection in `cmd_status`. Verdicts `events-1aeacf14` and `events-6fac9888` are right.

STILL-UNRESOLVED:
- `wf.py:837` — `receipt_event`'s body dict, 20 keys, the PLAN §3.3 receipt. It is proven to be a constructor: `wf.py:889`, `wf.py:1067` and `wf.py:1741` each pass `receipt_event(...)` straight into `ctx.chain.append`. `etype` is its second parameter, and those same three callers supply three different values (`chainmod.RECEIPT_RED` = `'receipt.red'`, `chainmod.RECEIPT_GREEN` = `'receipt.green'`, `chainmod.RECEIPT_CHECK` = `'receipt.check'`). Three values, and §5.9's shape `type` is one string — so `unresolved` is the honest answer, and provenance now names all three.
- `wf.py:1800` — `event = {"type": etype, "id": ..., "stage": ..., "agent": ..., "sources": ...}`, appended six lines later at `wf.py:1806`. `etype` is a local assigned in two branches of `cmd_marker`: `chainmod.MARKER_OPEN` = `'marker.open'` (`wf.py:1788`) or `chainmod.MARKER_CLOSE` = `'marker.close'` (`wf.py:1798`). Both values are now named in provenance; the fact stays unresolved because the site has two types, not none.

In both cases the extractor deliberately does **not** promote the named values into `type`: reporting one of several would be a guess, and inventing two records for one `file:line` would invent structure §5.9 does not have.

DISAGREE:
- **`events-88f3d343`** (shapes[26], `wf.py:837`) and **`events-77d4b7c9`** (shapes[27], `wf.py:1800`) are wrong. Both call the `etype` sites non-events; both are unambiguous event constructors, and the proof is three and one line away from the dict respectively (`ctx.chain.append(args.wo, receipt_event(...))`; `ctx.chain.append(args.wo, event)`). Dropping `wf.py:837` would delete the largest and most consequential shape in the app — the receipt, carrying `check`, `argv`, `exit_code`, `stdout_sha256`, `test_manifest_sha256`, `head_sha`, `tree_dirty` and the rest of PLAN §3.3 — and would report its absence as "there is nothing there". Dropping `wf.py:1800` would delete `marker.open`/`marker.close`. The verdicts' shared premise, "`etype` is not a string constant", is true and is exactly why these stay `unresolved`; it is not evidence about whether they are events.
- The three verdicts I accept quote `shapes[23]`, `[25]`, `[24]` by index. Those indices are now stale: `wf.py:837` and `wf.py:1800` are `shapes[23]` and `shapes[24]` in the regenerated file.

One thing I did not change, and flag deliberately: `shapes` remains over-inclusive. It still holds `mcp_server.py`'s JSON-Schema fragments whose `"type"` is a plain string (`"object"`, `"string"`, `"array"`, `"integer"`, `"boolean"`) and the MCP content blocks (`"text"`). Separating those from a genuine bare-word event type would require the known-type vocabulary — and `chain.py`'s own docstring records that PLAN §6 requires a new event type to cost zero engine changes, so a vocabulary filter would silently drop exactly the new type most important to see. Over-inclusion is auditable from the quoted text in provenance; a wrong exclusion is not. This is recorded in `provenance.readings`.

DETERMINISM:
```
python3 extract/events.py ops/devlane/workflow > obs/events.json
python3 extract/events.py ops/devlane/workflow > /tmp/run_a.json
python3 extract/events.py ops/devlane/workflow > /tmp/run_b.json
cmp /tmp/run_a.json /tmp/run_b.json          -> identical
cmp /tmp/run_a.json obs/events.json          -> identical
sha256: 670e220f7ecac2c6c12b0747138dbac0d84d6f87cce4569eaf45aa39e25c60ae  (all three)
PYTHONHASHSEED={0,1,42,12345}                -> same sha256 on all four
python3 -m py_compile extract/events.py      -> compiles
imports: __future__, ast, json, pathlib, re, sys  (stdlib only; no importlib/exec/eval/subprocess)
```
The inspected modules are only ever `read_text()` + `ast.parse()`d. `facts.types` is byte-for-byte unchanged; `facts.shapes` went 28 → 25, and the only other change is the longer, evidence-bearing text of the two surviving `unresolved` messages.
