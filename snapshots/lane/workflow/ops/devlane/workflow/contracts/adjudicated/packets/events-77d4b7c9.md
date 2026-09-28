# packet events-77d4b7c9

observation: `events`  definition: `#Events`
id: `<name>-<sha256(error path)[:8]>` = `events` + `77d4b7c9`

## the disagreement

error path: `facts.shapes.27.type`

```
facts.shapes.27.type: conflicting values {unresolved:"the \"type\" value does not resolve to a string: etype is not a string constant or a name for one"} and string (mismatched types struct and string):
    ./cue/events.cue:14:9
    ./cue/events.cue:180:15
    ./cue/events.cue:267:10
    ./obs/events.json:318:17
```

## what the extractor observed

```json
{
  "unresolved": "the \"type\" value does not resolve to a string: etype is not a string constant or a name for one"
}
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/events.cue:14`

```
   12 | #EventShapeObservation: {
   13 | 	// PLAN.md SS3.2 lines 110-121
   14 | 	type!: string
   15 | 	// PLAN.md SS3.1 lines 73-83
   16 | 	keys!: [...string]
```

### `./cue/events.cue:180`

```
  178 | 	types!: [...#EventTypeObservation]
  179 | 	// PLAN.md SS3.1 lines 73-83
  180 | 	shapes!: [...#EventShapeObservation]
  181 | 
  182 | 	// PLAN.md SS3.2 lines 110-121 -- EVT-S01 (stated)
```

### `./cue/events.cue:267`

```
  265 | #Events: {
  266 | 	// PLAN.md SS3.1 lines 71-89
  267 | 	facts!: #EventFacts
  268 | 	// PLAN.md SS3.1 lines 71-89
  269 | 	provenance!: _
```

### `./obs/events.json:318`

```
  316 |         ],
  317 |         "line": 1800,
  318 |         "type": {
  319 |           "unresolved": "the \"type\" value does not resolve to a string: etype is not a string constant or a name for one"
  320 |         }
```

## verdict required

Write `verdicts/events-77d4b7c9.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

