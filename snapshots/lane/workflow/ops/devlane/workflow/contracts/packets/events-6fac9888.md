# packet events-6fac9888

observation: `events`  definition: `#Events`
id: `<name>-<sha256(error path)[:8]>` = `events` + `6fac9888`

## the disagreement

error path: `facts.shapes.24.type`

```
facts.shapes.24.type: conflicting values {unresolved:"the \"type\" value does not resolve to a string: etype is not a string constant or a name for one; etype is a local of cmd_marker assigned 2 different values (chainmod.MARKER_CLOSE = 'marker.close' at wf.py:1798; chainmod.MARKER_OPEN = 'marker.open' at wf.py:1788), so there is no one string to report; the site stays because it IS an event constructor — wf.py:1806 appends event to the chain"} and string (mismatched types struct and string):
    ./cue/events.cue:17:9
    ./cue/events.cue:182:15
    ./cue/events.cue:271:10
    ./obs/events.json:278:17
```

## what the extractor observed

```json
{
  "unresolved": "the \"type\" value does not resolve to a string: etype is not a string constant or a name for one; etype is a local of cmd_marker assigned 2 different values (chainmod.MARKER_CLOSE = 'marker.close' at wf.py:1798; chainmod.MARKER_OPEN = 'marker.open' at wf.py:1788), so there is no one string to report; the site stays because it IS an event constructor — wf.py:1806 appends event to the chain"
}
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/events.cue:17`

```
   15 | #EventShapeObservation: {
   16 | 	// PLAN.md SS3.2 lines 110-121
   17 | 	type!: string
   18 | 	// PLAN.md SS3.1 lines 73-83
   19 | 	keys!: [...string]
```

### `./cue/events.cue:182`

```
  180 | 	types!: [...#EventTypeObservation]
  181 | 	// PLAN.md SS3.1 lines 73-83
  182 | 	shapes?: [...#EventShapeObservation]
  183 | 
  184 | 	// PLAN.md SS3.2 lines 110-121 -- EVT-S01 (stated)
```

### `./cue/events.cue:271`

```
  269 | #Events: {
  270 | 	// PLAN.md SS3.1 lines 71-89
  271 | 	facts!: #EventFacts
  272 | 	// PLAN.md SS3.1 lines 71-89
  273 | 	provenance!: _
```

### `./obs/events.json:278`

```
  276 |         ],
  277 |         "line": 1800,
  278 |         "type": {
  279 |           "unresolved": "the \"type\" value does not resolve to a string: etype is not a string constant or a name for one; etype is a local of cmd_marker assigned 2 different values (chainmod.MARKER_CLOSE = 'marker.close' at wf.py:1798; chainmod.MARKER_OPEN = 'marker.open' at wf.py:1788), so there is no one string to report; the site stays because it IS an event constructor \u2014 wf.py:1806 appends event to the chain"
  280 |         }
```

## verdict required

Write `verdicts/events-6fac9888.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

