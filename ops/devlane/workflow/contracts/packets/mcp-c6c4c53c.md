# packet mcp-c6c4c53c

observation: `mcp`  definition: `#Mcp`
id: `<name>-<sha256(error path)[:8]>` = `mcp` + `c6c4c53c`

## the disagreement

error path: `facts.server_imports.2`

```
facts.server_imports.2: invalid value "chain" (out of bound !="chain"):
    ./cue/mcp.cue:11:45
    ./cue/mcp.cue:11:24
    ./obs/mcp.json:7:7
```

## what the extractor observed

```json
"chain"
```

## provenance for that fact

No provenance entry matched this error path.
## the contract text cited above

### `./cue/mcp.cue:11`

```
    9 | 	// PLAN.md SS9 lines 485-488 (stated behavior, but no observation form; optional carrier).
   10 | 	// PLAN.md SS13 lines 565-570 (chain appends; gitio exports/commits/cross-binds; neither is the query layer).
   11 | 	server_imports?: [...(string & !="gitio" & !="chain")]
   12 | 	// PLAN.md SS9 lines 485-488 (no launch-import requirement is stated; optional carrier).
   13 | 	launch_imports?: _
```

### `./obs/mcp.json:7`

```
    5 |       "canonical",
    6 |       "cas",
    7 |       "chain",
    8 |       "errors",
    9 |       "gatekinds",
```

## verdict required

Write `verdicts/mcp-c6c4c53c.json`. `vet.py` checks three things, which are the three SPEC section 6 step 4 names verbatim:

- `verdict` is one of `doc-wrong`, `code-wrong`, `contract-wrong`, `extraction-wrong`, `ambiguous`;
- `citations` is a non-empty list;
- every `quote` in `citations` appears verbatim in this packet.

> unresolved: section 9 of the plan is not present in the SPEC excerpt this tooling was written against; only the three properties section 6 step 4 names verbatim (enum, required citations, quote appears verbatim in the packet) are checked

