"""Repoint test_ci_codeql's two reaches into the implementation.

The suite touches the implementation only through the module globals
CODEQL_YML and EVAL_SARIF. Pointing them at a directory under out/
runs the whole suite against a stand-in without ever writing the
working tree.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE.parent / "snapshot"
TESTS = SNAPSHOT / "ops" / "devlane" / "workflow" / "tests"

if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


def load(standin_dir):
    """Import test_ci_codeql with its two globals repointed at ``standin_dir``."""
    import test_ci_codeql as mod

    root = Path(standin_dir).resolve()
    mod.CODEQL_YML = root / "codeql.yml"
    mod.EVAL_SARIF = root / "eval_sarif.py"
    return mod


def variant(name, *, yml=None, eval_py=None, base="honest"):
    """Materialise out/_standin/<name>/ from the honest stand-in, one edit."""
    src = HERE / "_standin" / base
    dest = HERE / "_standin" / name
    dest.mkdir(parents=True, exist_ok=True)
    text = (src / "codeql.yml").read_text(encoding="utf-8")
    script = (src / "eval_sarif.py").read_text(encoding="utf-8")
    if yml is not None:
        text = yml(text)
    if eval_py is not None:
        script = eval_py(script)
    (dest / "codeql.yml").write_text(text, encoding="utf-8")
    (dest / "eval_sarif.py").write_text(script, encoding="utf-8")
    os.chmod(dest / "eval_sarif.py", 0o755)
    return dest
