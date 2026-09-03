RESULT: DONE

TIGHTENED:

- `layout.3`: a hidden witness now requires ignore evidence naming `wf.db` whenever that file is observed. PLAN.md SS8 lines 453-479 and SS12 lines 538-539 require `wf.db` to be gitignored.
- `layout.5`: the layout must contain `gate-kinds/tdd.json`; the symmetric `artifact.json` seed is also required. PLAN.md SS6 lines 328-330 and SS11 lines 513-519.
- `mcp.1`: observed server imports must include `query`. PLAN.md SS9 lines 485-488 says the server “imports the query layer.”
- `mcp.4`: observed server imports reject `gitio` and `chain`, the append-layer modules identified by PLAN.md SS9 lines 485-488 and SS13 lines 565-570.
- `meta.3`: `raw` must be JSON and cannot be the exact `"unresolved"` sentinel; at least one version carrier must be reported. PLAN.md SS6 lines 361-364 says the export carries a format version in `meta.json`.
- `meta.4`: `bytes` must be an integer greater than zero. PLAN.md SS6 lines 361-364 and SS8 lines 468-479 identify `meta.json` as JSON carrying the export format version.

LOOSENED:

- `cli`: `global_arguments` is optional/open, and cross-cutting requirements are checked across root and subcommand arguments. Command observation order is no longer prescribed. PLAN.md SS4 lines 261-265 says chain-appending verbs require `--agent` and “Every command: `--json` output mode”; SS5 lines 289-300 specifies `--no-commit` and repeatable `--source` without prescribing parser placement.
- `events`: extractor-only `files`, `file`, `line`, and shape carriers are optional/unconstrained. PLAN.md SS3 lines 73-83 specifies the event object and its fields, not a provenance-observation format. Whenever a shape is supplied, all common event keys are still required, including for future event types under SS6 lines 366-367.
- `mcp`: import, launch, and URI observation carriers are optional; when server imports are supplied, the query/append boundary is enforced. PLAN.md SS9 lines 485-488 specifies behavior—`status`/`next`/`log` resources and query-layer isolation—but no carrier structure, URI spelling, or import normalization.

EXAMPLES:

- `db`: added a PLAN-only example using the nine SS3.2 tables, documented column names, `present: true`, and the seeded `tdd`/`artifact` kinds. Unsupported SQL metadata, counts, digests, and migration values were omitted.
- `schema`: added a PLAN-only example using the nine SS3.2 tables and `0001_foundation.sql` from SS13 line 576. Unsupported SQL types, nullability, PK metadata, and undocumented columns were omitted.
- `gatekinds`: no honest complete example is possible. PLAN supplies a full illustrative `tdd` spec but not the seeded `artifact` kind’s version, scopes, checks, or outcome-to-stage/effect mapping.
- `meta`: no honest concrete example is possible. PLAN names a format version but supplies no JSON key, value/type, raw content, or byte count.
- All ten available examples pass `cue vet -c`; the two definitions lacking examples also pass CUE evaluation.

DISAGREE:

- `commitmsg-788dd5fa`: `_has_subject_format` is a derived CUE witness, not a required observation field. PLAN.md SS5 lines 305-315 explicitly labels and illustrates the message format, and the packet supplied no PLAN-valid subject rejected by the regex. The subject constraint was retained. No other adjudicated verdict is disputed.

UNRESOLVED:

- PLAN requires the effect “`wf.db` gitignored” but does not define gitignore syntax or an observation carrier. Literal, wildcard, negation, and comment semantics therefore cannot be resolved reliably.
- PLAN defines a query-layer/append-layer boundary but not normalized module names, qualified imports, or MCP URI forms.
- PLAN does not provide the concrete `meta.json` representation or the complete seeded `artifact` gate specification.
- SQL types, nullability, most `wo_state`/`schema_migrations` columns, raw-versus-canonical gate-kind digest forms, and several attempts-table carrier forms are unspecified and remain unconstrained.
- PLAN does not define parser-observation fields such as `global_arguments`, flag aliases, or `--root`; only their documented effective CLI behavior is constrained.
