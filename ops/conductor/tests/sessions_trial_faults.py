"""Planted faults for sessions.py's slice 4 rows (sessions-lever.md, slice 4).

Each mutant is a literal edit to a copy of the subject, never the tree.
The rows named in each note must go red on its mutant and stay green on
the clean subject:

    python3 ops/testkit/cases.py calibrate --subject ops/conductor/tools/sessions.py \\
        --mutants ops/conductor/tests/sessions_trial_faults.py \\
        --command "python3 -m unittest discover -s ops/conductor/tests -p test_sessions_trial.py"

Anchored on agentscient-10's sessions.py at c4dd8f12, each anchor counted
once: step 8's acknowledgment and export's pre-check (`if missing:`;
`if failures:` now guards only read errors). Calibrated at 2d374e5e,
with 10's LIVE rename merged (846744f3), over the rows the notes name,
`-k Stop -k missing_a_pane` added to the command above: clean green,
both mutants caught. The whole module's clean run waits on
started_participant (export-complete and the export-window rows).
The owner's-terminal rows have no mutant here: their subject is the bind minting in instrument.py, a
wall path, and the fault is planted in the wall session's change.
"""

from ops.testkit import Mutant

SUBJECT = "ops/conductor/tools/sessions.py"

MUTANTS = [
    Mutant(
        "M-hold-counted-by-default",
        SUBJECT,
        "    return f\"acknowledged {reply['queued_at']}\" if reply else \"unacknowledged\"\n",
        "    return f\"acknowledged {reply['queued_at']}\" if reply else \"acknowledged 1970-01-01T00:00:00Z\"\n",
        "a joined member's hold is counted before anyone acknowledged it, "
        "the 2026-09-19 debrief's F6 (stop-unacknowledged)",
    ),
    Mutant(
        "M-export-past-a-missing-log",
        SUBJECT,
        '    if missing:\n        refuse("export",',
        '    if False:\n        refuse("export",',
        "the pre-check passes a missing pane log or record, and the export "
        "is written anyway "
        "(export-missing-pane-log)",
    ),
]
