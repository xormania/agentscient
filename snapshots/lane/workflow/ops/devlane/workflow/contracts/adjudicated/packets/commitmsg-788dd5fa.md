# packet commitmsg-788dd5fa

observation: `commitmsg`  definition: `#CommitMsg`
id: `<name>-<sha256(error path)[:8]>` = `commitmsg` + `788dd5fa`

## the disagreement

error path: `facts._has_subject_format`

```
facts._has_subject_format: field is required but not present:
    ./cue/commitmsg.cue:66:2
```

## what the extractor observed

The error path could not be resolved inside `obs/commitmsg.json`: no value at facts._has_subject_format.

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/commitmsg.cue:66`

```
   64 | 
   65 | 	// PLAN.md SS5 lines 305-315 -- MSG-S06 (stated)
   66 | 	_has_subject_format!: true
   67 | 
   68 | 	// PLAN.md SS5 lines 289-315 -- MSG-S07 (stated)
```

## verdict required

Write `verdicts/commitmsg-788dd5fa.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

