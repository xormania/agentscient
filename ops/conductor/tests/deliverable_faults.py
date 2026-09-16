"""The deliverable lock's planted faults, as data (docs/tests.md rule 3).

Each mutant is a literal edit to a copy of ops/conductor/tools/deliverable.py,
never the tree; the kit's Mutant applies the anchor in an archive copy.
The S3 rows in test_deliverable.py must go red on the mutant named here,
and stay green on the clean lever:

    python3 ops/testkit/cases.py calibrate --subject ops/conductor/tools/deliverable.py \\
        --mutants ops/conductor/tests/deliverable_faults.py \\
        --command "python3 -m unittest discover -s ops/conductor/tests -p 'test_deliverable.py' -k MeasureAsArgv"
"""

from ops.testkit import Mutant

SUBJECT = "ops/conductor/tools/deliverable.py"

MUTANTS = [
    Mutant(
        "M-string-tokenizer",
        SUBJECT,
        "        argv = [str(part) for part in measure]\n"
        "        return argv, False\n",
        "        argv = [str(part) for part in measure]\n"
        '        return shlex.split(" ".join(argv)), False\n',
        "a list measure joined and re-split before running; "
        "measure-is-argv goes red on a quoted \"$X\" (S3, issue 3)",
    ),
    Mutant(
        "M-show-runs-all",
        SUBJECT,
        "            print(target_line(branch, target, run_measure=False))\n",
        "            print(target_line(branch, target, run_measure=True))\n",
        "bare show runs every measure; show-runs-nothing goes red "
        "on a sleeping measure (S3, issue 3)",
    ),
    Mutant(
        "M-string-accepted",
        SUBJECT,
        "    if not argv_shape:\n",
        "    if False:\n",
        "a string measure accepted on add; string-refuses goes red (S3, issue 3)",
    ),
]
