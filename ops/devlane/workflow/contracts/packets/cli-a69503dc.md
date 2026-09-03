# packet cli-a69503dc

observation: `cli`  definition: `#Cli`
id: `<name>-<sha256(error path)[:8]>` = `cli` + `a69503dc`

## the disagreement

error path: `explicit error (_|_ literal) in source:`

```
explicit error (_|_ literal) in source:
    ./cue/cli.cue:77:10
```

## what the extractor observed

The error path could not be resolved inside `obs/cli.json`: no value at explicit error (_|_ literal) in source:.

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/cli.cue:77`

```
   75 | #PositionalArgument: {
   76 | 	// PLAN.md SS4 lines 243-259 (positional observations are distinct from flags).
   77 | 	flags?: _|_
   78 | 	// PLAN.md SS4 lines 243-259
   79 | 	positional!: string
```

## verdict required

Write `verdicts/cli-a69503dc.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

