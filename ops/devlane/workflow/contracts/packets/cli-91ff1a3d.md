# packet cli-91ff1a3d

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `91ff1a3d`

## the disagreement

error path: `facts.commands.7.arguments.0`

```
facts.commands.7.arguments.0: 4 errors in empty disjunction::
    ./cue/cli.cue:290:34
```

## what the extractor observed

```json
{
  "action": null,
  "choices": null,
  "flags": [
    "--agent"
  ],
  "nargs": null,
  "required": null
}
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/cli.cue:290`

```
  288 | 
  289 | 	// PLAN.md SS4 lines 243-259
  290 | 	for _, argument in arguments if argument._is_positional {
  291 | 		// PLAN.md SS4 lines 246-257 -- CLI-S02 (stated)
  292 | 		if argument._id == "wo" {
```

## verdict required

Write `verdicts/cli-91ff1a3d.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

