# packet cli-1b6f359c

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `1b6f359c`

## the disagreement

error path: `facts.commands.11.arguments.5._id`

```
facts.commands.11.arguments.5._id: 7 errors in empty disjunction::
    ./cue/cli.cue:54:5
```

## what the extractor observed

The error path could not be resolved inside `obs/cli.json`: no value at facts.commands.11.arguments.5._id.

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/cli.cue:54`

```
   52 | 
   53 | 	// PLAN.md SS4 lines 246-251 -- CLI-S02 (stated)
   54 | 	if _id == "--kind" || _id == "--objective" || _id == "--by" {
   55 | 		// PLAN.md SS4 lines 246-251 -- CLI-S02 (stated)
   56 | 		required: true | null
```

## verdict required

Write `verdicts/cli-1b6f359c.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

