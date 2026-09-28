RESULT: DONE

WROTE (all under `ops/devlane/workflow/contracts/`, no existing file touched):
- `extract/cli.py` — 678 lines
- `extract/exitcodes.py` — 245 lines
- `extract/canonical.py` — 208 lines
- `extract/events.py` — 284 lines
- `extract/commitmsg.py` — 173 lines
- `extract/mcp.py` — 216 lines
- `extract/vocab.py` — 135 lines
- `EXTRACTION-NOTES.md` — 422 lines

Each exposes `NAME` and `extract(app_dir=None) -> {"facts", "provenance"}`, and runs standalone as `python3 extract/<name>.py [app_dir]`. Stdlib only, `ast` only, nothing imported or executed from the app.

GUESSES (SPEC §5.6–§5.12)
- §5.6 "argparse with literal strings" — **CONFIRMED**. Wrinkle handled: the root parser is `Parser`, a subclass at `wf.py:1831`; the root is identified by which parser gets `add_subparsers`.
- §5.6 "common flags added by a helper; follow one level" — **ADAPTED**. `common_options` (`wf.py:1836-1858`) is never called on a sub-parser; it is called on a `parents=` parent (`wf.py:1864-1865`). Following only direct helper calls would make every command's `arguments` unresolved, so `parents=[…]` is resolved too. The guess's flag list is wrong twice: `--root` is helper-added and unlisted; `--allow-dirty` is *not* helper-added (declared per-command on `red`/`green`/`check` only).
- §5.6 `next_json_keys` "dict literals inside the dispatch target" — **ADAPTED**. Literally applied it yields `["note","wo"]`, a confident wrong answer: the payload comes from `summarise()` + `.update(next_action())`, both one-line delegates into `query.py`. Adapted to resolve every `ctx.emit(payload,…)` through dict literals, the bound name, `.update`, subscripts, and one call hop at a time into sibling modules. 18 keys, zero unfollowed hops.
- §5.7 "names containing EXIT or CODE" — **ADAPTED**. Case-insensitive (otherwise the "and class attributes" half is dead), and class attributes whose value is a bare name resolved against module-level ints. Adds 5 `Class.exit_code` entries, adds no new code value.
- §5.8 — **no GUESS in this section**; recorded as such, no adaptation needed.
- §5.9 `types` "dotted literals; regex catches filenames" — **CONFIRMED**, noise realised (`meta.json`, `wf.db`, `wf.py`), plus one miss the guess does not predict: `chain.py:40` `OUTCOME = "outcome"` has no dot and is invisible to the regex while appearing in `shapes`.
- §5.9 `shapes` "type value is a string constant" — **ADAPTED**. Unadapted it sees 17 MCP plumbing fragments and not one event. Names/attributes are resolved against module-level string constants (own file or an imported sibling); unresolvable types are kept with `{"unresolved"}` rather than dropped.
- §5.10 `trailer_keys` — **ADAPTED**. Only `"Source: generated: wf"` is a plain constant; the other five trailers are f-strings. Population extended to f-string literal segments, else the answer would be `["Source"]`.
- §5.10 `subject_literals` "contains wf(" — **CONFIRMED, and thin**: the only such literal is the segment `"wf("`. The template is in provenance, not in facts.
- §5.11 — **no GUESS in this section**; recorded as such.
- §5.12 "terms may be encoded as a regex" — **CONFIRMED as not happening**: `RESERVED` is 19 plain constants and `re.escape` is applied around each at line 50.

UNRESOLVED (everything the extractors emit against this tree — five values, all in `events.shapes[].type`)
- `wf.py:837` receipt body (20 keys) — type is the `etype` parameter of `receipt_event`; no AST-local rule can name it.
- `wf.py:1800` marker body — same, `etype` parameter.
- `wf.py:501` and `query.py:308` — `"type": e.get("type")` projections, not event constructors.
- `mcp_server.py:263` — a JSON-Schema property literally *named* `type`, whose value is a dict.

Three facts are legitimately `[]`, each evidenced in provenance rather than defaulted: `exitcodes.exit_literals` (the one exit-like site is `sys.exit(main())`, argument quoted), `mcp.launch_imports` (all nine import statements quoted, none local), and — not triggered here — `cli.commands[].arguments`. The unresolved branches that do *not* fire were exercised against a synthetic tree and an empty tree; all seven modules return per-fact `{"unresolved"}` when their target is absent.

DETERMINISM
- `PYTHONHASHSEED=0` vs `PYTHONHASHSEED=random` (run from a different cwd) vs `PYTHONHASHSEED=12345` with an explicit app-dir argument, three output dirs, `diff -rq` → identical.
- Three back-to-back runs of all seven piped to `sha256sum` → single stable digest.
- `python3 -m py_compile` on all seven → ok; unused-import scan → none; import-and-call check → all seven return `{"facts","provenance"}` with `NAME` matching the filename; no absolute path, timestamp, or `/tmp`/`/home` string in any output.

SURPRISES (nine, detailed in EXTRACTION-NOTES; the load-bearing ones)
1. `wf.py` declares **17 verbs**; §5.11's fixed §4 list has 16. The extra is `agents` (`wf.py:1979`). §5.6 says the §4 verb set is exact, not a subset.
2. `all_codes` is `[0,1,2,3,64,**70**]`. `EXIT_INTERNAL = 70` (`errors.py:22`) is declared with a comment saying it sits outside the documented map on purpose. §5.7 says the set is exactly `{0,1,2,3,64}`.
3. `outcome` is an event type with no dot — §5.9's regex structurally cannot see it, so `types` and `shapes` disagree with each other within one observation.
4. 18 of 28 `shapes` come from `mcp_server.py` (tool schemas, JSON-RPC content blocks). They match the rule exactly and are not events.
5. `--json` is declared twice — once global, once on the `parents=` parent with `argparse.SUPPRESS` — and the §5.6 shape has no `default` field, so the difference is invisible in `facts` and visible only in provenance `text`.
6. The §5.6 argument shape has no `type`, so `type=int` on `-n/--number` is unobservable; likewise `metavar`, and `dest` on per-command arguments (`--recorded-by`).
7. `canonical.py:35` passes `allow_nan=False`, a keyword absent from the canonical-form definition §5.8 quotes. Reported as present; whether it breaks byte-identity is the contract author's call.
8. `mcp_server.py` imports `chain` and `store` — relevant to §5.11's own note that "append layer" is ambiguous. The extractor lists the eight local imports and takes no position.
9. `arguments` is sorted rather than in declaration order (§5.6 grants no declaration-order exemption where §5.1 does); source order and line numbers are preserved in provenance.
