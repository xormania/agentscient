# packet cli-f8b3b9e0

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `f8b3b9e0`

## the disagreement

error path: `facts.commands.0.arguments.4`

```
facts.commands.0.arguments.4: 9 errors in empty disjunction::
    ./cue/cli.cue:223:34
```

## what the extractor observed

```json
{
  "action": null,
  "choices": null,
  "flags": [
    "--root"
  ],
  "nargs": null,
  "required": null
}
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

## verdict required

Write `verdicts/cli-f8b3b9e0.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

