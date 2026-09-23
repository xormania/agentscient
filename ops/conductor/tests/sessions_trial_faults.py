"""Planted faults for sessions.py's slice 4 rows (sessions-lever.md, slice 4).

Each mutant is a literal edit to a copy of the subject, never the tree.
The rows named in each note must go red on its mutant and stay green on
the clean subject:

    python3 ops/testkit/cases.py calibrate --subject ops/conductor/tools/sessions.py \\
        --mutants ops/conductor/tests/sessions_trial_faults.py \\
        --command "python3 -m unittest discover -s ops/conductor/tests -p test_sessions_trial.py"

Anchored on sessions.py at da3e5e06, before slice 4's accounting and
export refusal exist; the anchors move with that change and are re-read
then. Not yet calibrated: every row is red on the subject, so the clean
run is red and calibrate reports ok false. The owner's-terminal rows have
no mutant here: their subject is the bind minting in instrument.py, a
wall path, and the fault is planted in the wall session's change.
"""

from ops.testkit import Mutant

SUBJECT = "ops/conductor/tools/sessions.py"

MUTANTS = [
    Mutant(
        "M-hold-counted-by-default",
        SUBJECT,
        '            outcome = "unresolved unmanaged"\n',
        '            outcome = "acknowledged 1970-01-01T00:00:00Z"\n',
        "a joined member's hold is counted before anyone acknowledged it, "
        "the 2026-09-19 debrief's F6 (stop-unacknowledged)",
    ),
    Mutant(
        "M-export-past-a-missing-log",
        SUBJECT,
        "    if failures:\n",
        "    if False:\n",
        "an export that could not read a member's file exits 0 "
        "(export-missing-pane-log)",
    ),
]
