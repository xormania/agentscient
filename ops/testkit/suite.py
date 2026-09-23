"""Unittest discovery that rejects zero collected cases on every Python version."""

from __future__ import annotations

import sys
import unittest


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("suite: expected DIRECTORY PATTERN; found invalid arguments; needed a discovery pair",
              file=sys.stderr)
        return 2
    tests = unittest.TestLoader().discover(argv[0], pattern=argv[1])
    if not tests.countTestCases():
        print(f"suite: expected collected test cases; found zero in {argv[0]} ({argv[1]}); needed executable tests",
              file=sys.stderr)
        return 2
    result = unittest.TextTestRunner().run(tests)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
