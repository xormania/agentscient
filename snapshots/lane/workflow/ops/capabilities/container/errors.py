class Refusal(Exception):
    OUTCOMES = frozenset({"rejection", "denial", "abort", "finding"})

    def __init__(self, claim, *, expected, actual, needed, outcome):
        if outcome not in self.OUTCOMES:
            raise ValueError(f"unknown refusal outcome: {outcome!r}")
        self.claim = claim
        self.expected = expected
        self.actual = actual
        self.needed = needed
        self.outcome = outcome
        super().__init__(claim)

    def __str__(self):
        expected = str(self.expected).replace("plan.cue", "plan contract")
        actual = str(self.actual).replace("plan.cue", "plan contract")
        needed = str(self.needed).replace("plan.cue", "plan contract")
        rendered = (
            f"refused: {self.claim}\n"
            f"expected: {expected}\n"
            f"actual: {actual}\n"
            f"outcome: {self.outcome}\n"
            f"needed: {needed}"
        )
        return rendered
