"""Planted faults for deliverable.py's show --unmeasured (LD-146).

Each mutant is a literal edit to a copy of the subject, never the tree;
the kit's Mutant applies the anchor in an archive copy. Every row of
test_deliverable.py must stay green on the clean subject, and the rows
named in each note must go red on its mutant:

    python3 ops/testkit/cases.py calibrate --subject ops/conductor/tools/deliverable.py \\
        --mutants ops/conductor/tests/deliverable_faults.py \\
        --command "python3 -m unittest discover -s ops/conductor/tests -p test_deliverable.py"

Anchored on the subject at 243a17d8 (LD-146). An anchor that no longer
matches once refuses class anchor; re-measure it against the subject.
"""

from ops.testkit import Mutant

SUBJECT = "ops/conductor/tools/deliverable.py"

MUTANTS = [
    Mutant(
        "M-unmeasured-measures",
        SUBJECT,
        "    measured = not args\n",
        "    measured = True\n",
        "show --unmeasured runs every measure (deliverable-show-unmeasured)",
    ),
    Mutant(
        "M-any-option-admitted",
        SUBJECT,
        '    if args not in ([], ["--unmeasured"]):\n',
        "    if False:\n",
        "an unknown option to show is admitted, never refused "
        "(deliverable-show-bogus-refuses)",
    ),
    Mutant(
        "M-show-never-measures",
        SUBJECT,
        "    measured = not args\n",
        "    measured = False\n",
        "a plain show stops measuring (deliverable-show-still-measures)",
    ),
]
