"""Planted faults for dispatch_actions.py (sessions-lever.md, slice 3).

Each mutant is a literal edit to a copy of the subject, never the tree;
the kit's Mutant applies the anchor in an archive copy. The rows named in
each note must go red on its mutant and stay green on the clean subject:

    python3 ops/testkit/cases.py calibrate --subject ops/conductor/tools/dispatch_actions.py \\
        --mutants ops/conductor/tests/dispatch_actions_faults.py \\
        --command "python3 -m unittest discover -s ops/conductor/tests -p test_dispatch_actions.py -k role -k holder -k unwritable"

Anchored on agentscient-10's subject at bfa82f5b. An anchor that no longer
matches once refuses class anchor; re-measure it against the subject.
"""

from ops.testkit import Mutant

SUBJECT = "ops/conductor/tools/dispatch_actions.py"

MUTANTS = [
    Mutant(
        "M-role-unchecked",
        SUBJECT,
        '    coordination.require_role(part, ("dispatcher",))\n',
        "    pass\n",
        "the role check dropped: a worker reaches the holder check and "
        "refuses holder, not role (worker-role)",
    ),
    Mutant(
        "M-holder-unchecked",
        SUBJECT,
        "    if not held or held != mine:\n",
        "    if False:\n",
        "any dispatcher acts without holding the machine (not-holder)",
    ),
    Mutant(
        "M-refusal-swallowed",
        SUBJECT,
        "    except Refusal as refusal:\n        return emit(refusal)\n",
        "    except Refusal as refusal:\n        return 0\n",
        "a refusal from the core is swallowed and the verb exits 0; "
        "the core refuses an unwritable store before the subject acts "
        "(store-unwritable; the contract's store is the core's store)",
    ),
]
