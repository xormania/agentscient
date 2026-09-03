# packet cli-e834efa2

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `e834efa2`

## the disagreement

error path: `facts.global_arguments.1`

```
facts.global_arguments.1: field not allowed:
    ./cue/cli.cue:650:9
    ./obs/cli.json:1297:7
```

## what the extractor observed

```json
{
  "action": "store_true",
  "choices": null,
  "default_env": null,
  "dest": null,
  "flags": [
    "--json"
  ],
  "nargs": null
}
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/cli.cue:650`

```
  648 | 
  649 | 	// PLAN.md SS4 lines 264-265 -- CLI-S03 (stated)
  650 | 	if len(global_arguments) == 0 {
  651 | 		// PLAN.md SS4 lines 264-265 -- CLI-S03 (stated)
  652 | 		commands: [
```

### `./obs/cli.json:1297`

```
 1295 |         "nargs": null
 1296 |       },
 1297 |       {
 1298 |         "action": "store_true",
 1299 |         "choices": null,
```

## verdict required

Write `verdicts/cli-e834efa2.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

