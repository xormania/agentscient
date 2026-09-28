# packet exitcodes-18549552

observation: `exitcodes`  definition: `#ExitCodes`
id: `<name>-<sha256(error path)[:8]>` = `exitcodes` + `18549552`

## the disagreement

error path: `facts.all_codes`

```
facts.all_codes: incompatible list lengths (5 and 6):
    ./cue/exitcodes.cue:24:15
```

## what the extractor observed

```json
[
  0,
  1,
  2,
  3,
  64,
  70
]
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/exitcodes.cue:24`

```
   22 | 		exit_literals!: [...(0 | 1 | 2 | 3 | 64)]
   23 | 		// PLAN.md SS4 lines 271-274 (stated: the map is exact).
   24 | 		all_codes!: [0, 1, 2, 3, 64]
   25 | 	})
   26 | 	// PLAN.md SS1 lines 21-24 (inferred; evidence provenance is deliberately unconstrained).
```

## verdict required

Write `verdicts/exitcodes-18549552.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

