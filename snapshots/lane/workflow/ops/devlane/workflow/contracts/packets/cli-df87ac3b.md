# packet cli-df87ac3b

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `df87ac3b`

## the disagreement

error path: `facts.commands.0.arguments.4.flags`

```
facts.commands.0.arguments.4.flags: field not allowed:
    ./cue/cli.cue:223:34
    ./obs/cli.json:45:14
```

## what the extractor observed

```json
[
  "--root"
]
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/cli.cue:223`

```
  221 | 
  222 | 	// PLAN.md SS4 lines 243-259
  223 | 	for _, argument in arguments if argument._is_positional {
  224 | 		// PLAN.md SS4 lines 246-257 -- CLI-S02 (stated)
  225 | 		if argument._id == "wo" {
```

### `./obs/cli.json:45`

```
   43 |             "action": null,
   44 |             "choices": null,
   45 |             "flags": [
   46 |               "--root"
   47 |             ],
```

## verdict required

Write `verdicts/cli-df87ac3b.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

