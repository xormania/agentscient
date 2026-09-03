# packet exitcodes-10a89bb7

observation: `exitcodes`  definition: `#ExitCodes`
id: `<name>-<sha256(error path)[:8]>` = `exitcodes` + `10a89bb7`

## the disagreement

error path: `facts.constants.3.value`

```
facts.constants.3.value: conflicting values 64 and 70:
    ./cue/exitcodes.cue:9:26
    ./cue/exitcodes.cue:20:19
    ./obs/exitcodes.json:30:18
```

## what the extractor observed

```json
70
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/exitcodes.cue:9`

```
    7 | 	name!: string
    8 | 	// PLAN.md SS4 lines 271-274 (stated).
    9 | 	value!: 0 | 1 | 2 | 3 | 64
   10 | 	// PLAN.md SS4 lines 271-274 (inferred; source file is observation metadata).
   11 | 	file!: string
```

### `./cue/exitcodes.cue:20`

```
   18 | 	facts!: close({
   19 | 		// PLAN.md SS4 lines 271-274 (stated: any surfaced code must be in the documented map).
   20 | 		constants!: [...#ExitCodeConstant]
   21 | 		// PLAN.md SS4 lines 271-274 (stated: any surfaced literal must be in the documented map).
   22 | 		exit_literals!: [...(0 | 1 | 2 | 3 | 64)]
```

### `./obs/exitcodes.json:30`

```
   28 |         "file": "errors.py",
   29 |         "name": "EXIT_INTERNAL",
   30 |         "value": 70
   31 |       },
   32 |       {
```

## verdict required

Write `verdicts/exitcodes-10a89bb7.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

