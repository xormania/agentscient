"""Run the whole test_ci_codeql suite against one stand-in directory.

    python3 run_standin.py _standin/honest
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import standin  # noqa: E402


def run(standin_dir, verbose=False):
    mod = standin.load(standin_dir)
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1, stream=sys.stdout)
    return runner.run(suite)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "_standin/honest"
    result = run(target, verbose="-v" in sys.argv)
    print(f"ran {result.testsRun}, failures {len(result.failures)}, "
          f"errors {len(result.errors)}")
    sys.exit(0 if result.wasSuccessful() else 1)
