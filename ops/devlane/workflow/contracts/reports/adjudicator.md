I'll start by reading SCOPE.md, ADJUDICATION.md, PLAN.md, and the packets so each verdict rests only on that evidence.Next I’ll read every packet so each verdict is based only on the disagreement evidence, not on outside context.Several packets look incomplete, so I’ll read the rest of them and check whether contracts, observations, or notes exist in this snapshot.I have the packets and PLAN.md. Next I’ll write each verdict, then mechanically check that every quote appears verbatim.I’ll write all 25 verdict files, then check that every quote appears verbatim in the packet or PLAN.md.Settled all 25 packets against PLAN.md and the packet evidence only.

The two calibration cases are **code-wrong**: `wf.py` adds an `agents` verb on top of the sixteen §4 commands, and `errors.py` defines `EXIT_INTERNAL = 70` outside `{0,1,2,3,64}`. Extra `--root` is the same kind of undocumented CLI surface. Documented flags placed on the root parser (`--agent`, `--json`, `--no-commit`, `--source`) are a contract that is stricter than PLAN.md. Extra `artifacts.created_at` and `gate_kinds.{spec_sha256,synced_at}` columns depart from the §3.2 code-font lists. `advance_to` and `blocked_by_open_markers` encode behavior PLAN.md requires but never names as spec fields. Event `shapes[*].type: {unresolved:…}` entries are extractor false positives, not PLAN.md event types. `_has_subject_format` is a contract-only field the observation never produces.

RESULT: DONE
WROTE: 25
TALLY: code-wrong 11, contract-wrong 7, extraction-wrong 5, doc-wrong 2, ambiguous 0
NEEDS-MORE-CONTEXT: none
DISAGREEMENTS-WITH-THE-PACKET:
- Packets' "verdict required" section allows only doc-wrong|code-wrong|ambiguous and a `citations` list; ADJUDICATION.md §9 (followed here) uses five verdicts, `because[]`, and `action`.
- Packets omit the whole contract, quoted PLAN.md lines, CONTRACT-NOTES, and EXTRACTION-NOTES that ADJUDICATION.md §9 said they would contain. Many CLI/events/exitcodes/commitmsg packets have no provenance.
- `cue/cli.cue` cites PLAN.md §4 lines 264–265 for `global_arguments!: [] | [#GlobalJsonArgument]`; those lines say `--json` everywhere, not that `--json` is the only legal global flag.
- schema/db contracts label the closed column counts "inferred"; the packets still treat that inference as stated PLAN.md.
- gatekinds packets never include `cue/gatekinds.cue`; closedness is visible only as `field not allowed` on the observation.
- `cli-f9688ea2` cites the `--kind`/`--objective`/`--by` required-flag rule for `commands.0.arguments.4._id` (advance's fifth argument). That is not what PLAN.md says about `advance`, and this packet omits the argument value (`--root` in `cli-f8b3b9e0`).
- `schema-8a10347f` truncates provenance after `attempts` and never shows `tables.4` (`gate_kinds`); the 5-vs-3 count is only in the cue error.
