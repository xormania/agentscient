# packet cli-17b697ea

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `17b697ea`

## the disagreement

error path: `facts.global_arguments.0.flags.0`

```
facts.global_arguments.0.flags.0: conflicting values "--json" and "--agent":
    ./cue/cli.cue:22:10
    ./cue/cli.cue:601:27
    ./cue/cli.cue:693:10
    ./obs/cli.json:1293:11
```

## what the extractor observed

```json
"--agent"
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/cli.cue:22`

```
   20 | #GlobalJsonArgument: #GlobalArgument & {
   21 | 	// PLAN.md SS4 lines 264-265 -- CLI-S03 (stated)
   22 | 	flags: ["--json"]
   23 | }
   24 | 
```

### `./cue/cli.cue:601`

```
  599 | #CliFacts: {
  600 | 	// PLAN.md SS4 lines 261-265
  601 | 	global_arguments!: [] | [#GlobalJsonArgument]
  602 | 	// PLAN.md SS4 lines 238-259 -- CLI-S01 (stated)
  603 | 	commands!: [
```

### `./cue/cli.cue:693`

```
  691 | #Cli: {
  692 | 	// PLAN.md SS4 lines 236-283
  693 | 	facts!: #CliFacts
  694 | 	// PLAN.md SS4 lines 236-283
  695 | 	provenance!: _
```

### `./obs/cli.json:1293`

```
 1291 |         "dest": null,
 1292 |         "flags": [
 1293 |           "--agent"
 1294 |         ],
 1295 |         "nargs": null
```

## verdict required

Write `verdicts/cli-17b697ea.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

