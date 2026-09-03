"""One-fault stand-ins run through the whole test_ci_codeql suite.

Each row is the honest stand-in with exactly one defect. A row FIRES
when the suite goes red on it and SURVIVES when the suite stays green —
a surviving row is a hole in the tests.

    python3 -m unittest discover -s <out> -t <out> -p 'test_variants.py'
"""

import io
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import standin  # noqa: E402

MOD = standin.load(HERE / "_standin" / "honest")


def one_fault(text, old, new):
    if old not in text:
        raise AssertionError(f"anchor missing: {old!r}")
    if text.count(old) != 1:
        raise AssertionError(f"anchor not unique ({text.count(old)}): {old!r}")
    out = text.replace(old, new, 1)
    if out == text:
        raise AssertionError("one-fault was a no-op")
    if "jobs:" not in out or "CodeQL" not in out:
        raise AssertionError("one-fault left the workflow unrecognisable")
    return out


def sub(old, new):
    return lambda text: one_fault(text, old, new)


def sub_py(old, new):
    """One-fault edit to eval_sarif.py; recognisable = still a python script."""

    def mutate(text):
        if text.count(old) != 1:
            raise AssertionError(f"anchor not unique ({text.count(old)}): {old!r}")
        out = text.replace(old, new, 1)
        if out == text or "def main(" not in out:
            raise AssertionError("eval one-fault did not land")
        compile(out, "eval_sarif.py", "exec")
        return out

    return mutate


PLANT_RUN = (
    "          install -D -m 0644 ops/devlane/workflow/tests/fixtures/"
    "codeql_proof/findable.py.fixture codeql-proof/findable.py\n"
)
PLANT_STEP = (
    "      - name: Stage the deliberately vulnerable file\n"
    "        if: env.PROOF == '1'\n"
    "        run: |\n" + PLANT_RUN + "\n"
)
CLEANUP_STEP = (
    "      - name: Unstage the vulnerable file\n"
    "        if: always() && env.PROOF == '1'\n"
    "        run: rm -rf codeql-proof/findable.py\n\n"
)
INIT_HEAD = "      - uses: github/codeql-action/init@v3\n"
ANALYZE_HEAD = "      - uses: github/codeql-action/analyze@v3\n"
GUARD_TAIL = (
    "          observed=$(printf '%s\\n' \"$body\" | python3 -c "
    "'import json,sys; print(json.load(sys.stdin)[\"state\"])')\n"
    "          printf 'state=%s\\n' \"$observed\" >> \"$GITHUB_OUTPUT\"\n"
)
GUARD_UNREACHABLE = (
    "          if ! body=$(curl -sSf -H \"Authorization: Bearer ${GH_TOKEN}\" "
    "\"$endpoint\"); then\n"
    "            echo \"UNREACHABLE: could not establish default-setup state\" >&2\n"
    "            exit 1\n"
    "          fi\n"
)
OUTSIDE = "/tmp/ci-codeql-escape-hatch"


def plant_after_init(text):
    """Move the plant below init: the database is built without it."""
    without = one_fault(text, PLANT_STEP, "")
    out = one_fault(without, ANALYZE_HEAD, PLANT_STEP + ANALYZE_HEAD)
    if out.index("Stage the deliberately") < out.index(INIT_HEAD):
        raise AssertionError("plant_after_init did not move the plant below init")
    return out


def cleanup_early(text):
    without = one_fault(text, CLEANUP_STEP, "")
    return one_fault(without, INIT_HEAD, CLEANUP_STEP + INIT_HEAD)


# name -> (mutate codeql.yml, mutate eval_sarif.py, what ships broken)
ROWS = {
    # --- pass-3 regressions, closed before 08704d ---------------------
    "eval_if": (
        sub(
            "      - name: Judge the proof SARIF\n        if: env.PROOF == '1'\n",
            "      - name: Judge the proof SARIF\n        if: env.PROOF != '1'\n",
        ),
        None,
        "proof mode never evaluates the SARIF",
    ),
    "eval_noif": (
        sub(
            "      - name: Judge the proof SARIF\n        if: env.PROOF == '1'\n"
            "        run:",
            "      - name: Judge the proof SARIF\n        run:",
        ),
        None,
        "evaluation runs on every real PR",
    ),
    "cleanup_early": (cleanup_early, None, "the plant is gone before analyze"),
    "proof_binding": (
        sub("PROOF: ${{ inputs.proof && '1' || '0' }}", "PROOF: ${{ inputs.proof }}"),
        None,
        "env.PROOF is 'true', never '1'",
    ),
    "never_upload": (
        sub(
            "upload: ${{ env.PROOF != '1' && 'always' || 'never' }}",
            "upload: never",
        ),
        None,
        "the Security tab stays empty after the swap",
    ),
    "unreachable_soft": (
        sub(
            GUARD_UNREACHABLE,
            "          body=$(curl -sSf -H \"Authorization: Bearer ${GH_TOKEN}\" "
            "\"$endpoint\") || "
            "echo \"UNREACHABLE: could not establish default-setup state\" >&2\n"
            "          body=${body:-'{\"state\": \"not-configured\"}'}\n",
        ),
        None,
        "unreadable endpoint looks like not-configured",
    ),
    "plant_after_init": (
        plant_after_init,
        None,
        "the plant lands after the database is built",
    ),
    # --- the three 08704d P1 rows -------------------------------------
    "plant_outside": (
        sub(PLANT_RUN, PLANT_RUN.replace("codeql-proof/", f"{OUTSIDE}/")),
        None,
        "proof mode scans a tree with no plant",
    ),
    "plant_runner_temp": (
        sub(PLANT_RUN, PLANT_RUN.replace("codeql-proof/", "${{ runner.temp }}/")),
        None,
        "the plant lands outside $GITHUB_WORKSPACE",
    ),
    "cleanup_wrong_path": (
        sub("run: rm -rf codeql-proof/findable.py", "run: rm -rf findable.py"),
        None,
        "the plant is never removed",
    ),
    # --- the 08704d P1 #2 row -----------------------------------------
    "plant_when_ready": (
        sub(
            "      - name: Stage the deliberately vulnerable file\n"
            "        if: env.PROOF == '1'\n",
            "      - name: Stage the deliberately vulnerable file\n"
            "        if: env.PROOF == '1' || "
            "steps.default-setup.outputs.state == 'not-configured'\n",
        ),
        None,
        "the fixture is planted on every real post-swap scan",
    ),
    # --- the 08704d P2 row --------------------------------------------
    "guard_ignores_state": (
        sub(GUARD_TAIL, "          printf 'state=not-configured\\n' >> \"$GITHUB_OUTPUT\"\n"),
        None,
        "the guard writes not-configured whatever the endpoint says",
    ),
    # --- new hunts -----------------------------------------------------
    "init_languages_pinned": (
        sub("languages: ${{ matrix.language }}", "languages: actions"),
        None,
        "python is never analysed on either matrix leg",
    ),
    "init_ignores_the_plant": (
        sub(
            "          build-mode: none\n",
            "          build-mode: none\n"
            "          config: |\n"
            "            paths-ignore:\n"
            "              - codeql-proof\n",
        ),
        None,
        "the planted file is excluded from the database",
    ),
    "job_continue_on_error": (
        sub(
            "    timeout-minutes: 30\n",
            "    timeout-minutes: 30\n    continue-on-error: true\n",
        ),
        None,
        "the job-level escape hatch makes a refusal green",
    ),
    "artifact_always_uploads": (
        sub(
            "      - name: Retain the proof SARIF\n        if: env.PROOF == '1'\n",
            "      - name: Retain the proof SARIF\n",
        ),
        None,
        "the SARIF artifact is produced on every real scan",
    ),
    "eval_says_nothing": (
        None,
        sub_py(
            "        for line in hits:\n            print(line)\n",
            "",
        ),
        "a red proof run never names the rule that fired",
    ),
    "plant_source_does_not_exist": (
        sub(
            "ops/devlane/workflow/tests/fixtures/codeql_proof/findable.py.fixture",
            "ops/devlane/workflow/fixtures/codeql_proof/findable.py.fixture",
        ),
        None,
        "the cp names a path that is not in the repo",
    ),
    "guard_has_no_id": (
        sub("      - id: default-setup\n", "      - id: setup-state\n"),
        None,
        "every if: on the guard output reads an empty string",
    ),
    "second_unconditional_plant": (
        sub(
            INIT_HEAD,
            "      - name: Seed the sample tree\n"
            "        run: |\n"
            "          install -D -m 0644 ops/devlane/workflow/tests/fixtures/"
            "codeql_proof/findable.py.fixture sample/findable.py\n\n" + INIT_HEAD,
        ),
        None,
        "a second, unguarded plant lands on every real scan",
    ),
    "guard_reads_another_repo": (
        sub(
            'endpoint="https://api.github.com/repos/${GITHUB_REPOSITORY}'
            '/code-scanning/default-setup"',
            'endpoint="https://api.github.com/repos/github/codeql-action'
            '/code-scanning/default-setup"',
        ),
        None,
        "the guard judges a different repository's default setup",
    ),
    "plant_source_is_another_fixture": (
        sub(
            "ops/devlane/workflow/tests/fixtures/codeql_proof/findable.py.fixture",
            ".dev/ci/findable.py.fixture",
        ),
        None,
        "the plant copies a file that is not the reviewed vulnerable fixture",
    ),
}


def run_suite(directory):
    MOD.CODEQL_YML = Path(directory) / "codeql.yml"
    MOD.EVAL_SARIF = Path(directory) / "eval_sarif.py"
    suite = unittest.defaultTestLoader.loadTestsFromModule(MOD)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    failed = sorted(
        str(case).split(" ")[0] for case, _ in result.failures + result.errors
    )
    return result.testsRun, failed


class HonestStandinIsGreen(unittest.TestCase):
    def test_the_control_row_passes_every_test(self):
        ran, failed = run_suite(HERE / "_standin" / "honest")
        self.assertGreater(ran, 70, ran)
        self.assertEqual(failed, [], f"ran {ran}: {failed}")


class OneFaultRowsFire(unittest.TestCase):
    maxDiff = None

    def test_every_row(self):
        table = []
        surviving = []
        for name, (yml, eval_py, ships) in sorted(ROWS.items()):
            directory = standin.variant(name, yml=yml, eval_py=eval_py)
            ran, failed = run_suite(directory)
            verdict = "FIRES" if failed else "SURVIVING MUTANT"
            table.append(
                f"{name:28} ran {ran:3}  {verdict:16} "
                f"{len(failed)} red  — {ships}"
            )
            if not failed:
                surviving.append(f"{name}: {ships}")
        print("\n" + "\n".join(table))
        self.assertEqual(surviving, [], "\n".join(surviving))


if __name__ == "__main__":
    unittest.main()
