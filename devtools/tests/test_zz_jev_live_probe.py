"""Temporary runner proof for PR #353; deliberately fails and must not be merged."""

import unittest


class JevLiveProbe(unittest.TestCase):
    def test_incorrect_fixture_expectation(self):
        fixture = ["alpha", "beta"]
        self.assertEqual(
            3,
            len(fixture),
            "JEV_CI_LIVE_PROBE_353: this temporary fixture contains two entries, "
            "but the test expectation incorrectly requires three.",
        )


if __name__ == "__main__":
    unittest.main()
