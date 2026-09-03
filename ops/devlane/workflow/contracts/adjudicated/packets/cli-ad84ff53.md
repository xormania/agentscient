# packet cli-ad84ff53

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `ad84ff53`

## the disagreement

error path: `facts.global_arguments`

```
facts.global_arguments: 7 errors in empty disjunction::
    ./cue/cli.cue:650:9
```

## what the extractor observed

```json
[
  {
    "action": null,
    "choices": null,
    "default_env": null,
    "dest": null,
    "flags": [
      "--agent"
    ],
    "nargs": null
  },
  {
    "action": "store_true",
    "choices": null,
    "default_env": null,
    "dest": null,
    "flags": [
      "--json"
    ],
    "nargs": null
  },
  {
    "action": "store_true",
    "choices": null,
    "default_env": null,
    "dest": null,
    "flags": [
      "--no-commit"
    ],
    "nargs": null
  },
  {
    "action": null,
    "choices": null,
    "default_env": null,
    "dest": null,
    "flags": [
      "--root"
    ],
    "nargs": null
  },
  {
    "action": "append",
    "choices": null,
    "default_env": null,
    "dest": null,
    "flags": [
      "--source"
    ],
    "nargs": null
  }
]
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

## verdict required

Write `verdicts/cli-ad84ff53.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

