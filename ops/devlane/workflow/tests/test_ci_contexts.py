"""Unit tests for ci_contexts.py, mirroring MatrixTransform."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

SCRIPT = support.WF_DIR / "checks" / "ci_contexts.py"
REPO = support.WF_DIR.parent.parent.parent
DEV_YML = REPO / ".github" / "workflows" / "ci-dev.yml"
APPS_YML = REPO / ".github" / "workflows" / "ci-dev-apps.yml"
WF_PY = support.WF_PY


class ContextsScript(unittest.TestCase):
    SCRIPT = SCRIPT

    def run_it(self, payload, extra=(), script=None, cwd=None):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as handle:
            json.dump(payload, handle)
            path = handle.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        argv = [sys.executable, str(script or self.SCRIPT), path, *extra]
        return subprocess.run(
            argv, capture_output=True, text=True, check=False, cwd=cwd
        )

    def payload(self, checks=None):
        if checks is None:
            body = json.loads(
                subprocess.run(
                    [sys.executable, str(WF_PY), "--json", "status", "--checks"],
                    capture_output=True, text=True, check=True,
                ).stdout
            )
            return body
        return {"ci_matrix": list(checks)}

    def sandbox(self, mut_dev=None, mut_apps=None, drop=None):
        raw = tempfile.mkdtemp(prefix="ci-ctx-")
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", raw], check=False)
        )
        root = Path(raw)
        checks = root / "ops" / "devlane" / "workflow" / "checks"
        workflows = root / ".github" / "workflows"
        checks.mkdir(parents=True)
        workflows.mkdir(parents=True)
        shutil.copy(self.SCRIPT, checks / "ci_contexts.py")
        if drop != "ci-dev.yml":
            text = DEV_YML.read_text(encoding="utf-8")
            if mut_dev is not None:
                text = mut_dev(text)
            (workflows / "ci-dev.yml").write_text(text)
        if drop != "ci-dev-apps.yml":
            text = APPS_YML.read_text(encoding="utf-8")
            if mut_apps is not None:
                text = mut_apps(text)
            (workflows / "ci-dev-apps.yml").write_text(text)
        return root, checks / "ci_contexts.py"

    def assert_refused(self, proc, job_id=None):
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "", f"stdout was {proc.stdout!r}")
        self.assertTrue(proc.stderr.strip(), "refusal wrote nothing on stderr")
        self.assertIn("expected", proc.stderr)
        self.assertIn("found", proc.stderr)
        if job_id is not None:
            self.assertIn(job_id, proc.stderr)

    def test_no_argument_is_a_usage_error(self):
        proc = subprocess.run(
            [sys.executable, str(self.SCRIPT)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 64)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr)

    def test_json_flag_without_a_file_is_a_usage_error(self):
        proc = subprocess.run(
            [sys.executable, str(self.SCRIPT), "--json"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 64)

    def test_an_extra_argument_is_a_usage_error(self):
        proc = self.run_it(self.payload(["lint"]), extra=("--json", "nope"))
        self.assertEqual(proc.returncode, 64)

    def test_a_malformed_payload_fails_loudly(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as handle:
            handle.write("{not json")
            path = handle.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        proc = subprocess.run(
            [sys.executable, str(self.SCRIPT), path],
            capture_output=True, text=True, check=False,
        )
        self.assert_refused(proc, job_id="ci_matrix")

    def test_a_list_payload_is_not_an_object(self):
        proc = self.run_it(["lint"])
        self.assert_refused(proc, job_id="ci_matrix")

    def test_an_empty_ci_matrix_is_a_refusal(self):
        proc = self.run_it({"ci_matrix": []})
        self.assert_refused(proc, job_id="ci_matrix")

    def test_a_missing_ci_matrix_is_a_refusal(self):
        proc = self.run_it({"checks": []})
        self.assert_refused(proc, job_id="ci_matrix")

    def test_output_is_sorted(self):
        proc = self.run_it(self.payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(lines, sorted(lines))
        self.assertTrue(lines)

    def test_json_emits_the_same_list(self):
        text = self.run_it(self.payload())
        dumped = self.run_it(self.payload(), extra=("--json",))
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(dumped.returncode, 0, dumped.stderr)
        self.assertEqual(json.loads(dumped.stdout), text.stdout.splitlines())

    def test_the_real_command_feeds_it(self):
        proc = self.run_it(self.payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertIn("dev: verify", lines)
        self.assertIn("dev: gates (lint)", lines)
        self.assertNotIn("dev: gates", lines)
        self.assertNotIn("dev: workflow", lines)

    def test_a_duplicate_app_is_a_refusal_not_a_dedupe(self):
        def mut(text):
            needle = "          - app: telemetry\n"
            self.assertIn(needle, text)
            return text.replace(
                needle,
                needle + "            cmd: python3 -m unittest discover x -v\n"
                + needle,
                1,
            )

        root, script = self.sandbox(mut_apps=mut)
        planted = (root / ".github" / "workflows" / "ci-dev-apps.yml")
        self.assertGreaterEqual(
            planted.read_text().count("- app: telemetry"), 2
        )
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="app")
        self.assertIn("duplicate", proc.stderr)

    def test_a_missing_workflow_file_is_a_refusal(self):
        _root, script = self.sandbox(drop="ci-dev.yml")
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc)
        self.assertIn("ci-dev.yml", proc.stderr)

    def test_a_missing_job_id_is_a_refusal(self):
        def drop_verify(text):
            self.assertIn("  verify:\n", text)
            return text.replace("  verify:\n", "  # verify:\n", 1)

        _root, script = self.sandbox(mut_dev=drop_verify)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="verify")

    def test_a_missing_name_line_is_a_refusal(self):
        def mut(text):
            needle = '    name: "dev: verify"\n'
            self.assertIn(needle, text)
            return text.replace(needle, "", 1)

        _root, script = self.sandbox(mut_dev=mut)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="verify")

    def test_gates_without_discover_matrix_is_a_refusal(self):
        def mut(text):
            needle = "fromJSON(needs.discover.outputs.matrix)"
            self.assertIn(needle, text)
            return text.replace(needle, "fromJSON('[\"lint\"]')", 1)

        _root, script = self.sandbox(mut_dev=mut)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="gates")

    def test_an_empty_shard_list_is_a_refusal(self):
        def mut(text):
            needle = "shard: [0, 1, 2]"
            self.assertIn(needle, text)
            return text.replace(needle, "shard: []", 1)

        _root, script = self.sandbox(mut_apps=mut)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="workflow")

    def test_a_missing_shard_line_is_a_refusal(self):
        def mut(text):
            needle = "        shard: [0, 1, 2]\n"
            self.assertIn(needle, text)
            return text.replace(needle, "", 1)

        _root, script = self.sandbox(mut_apps=mut)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="workflow")

    def test_an_app_name_without_the_expression_is_a_refusal(self):
        def mut(text):
            needle = '    name: "dev: ${{ matrix.app }}"\n'
            self.assertIn(needle, text)
            return text.replace(needle, '    name: "dev: apps"\n', 1)

        _root, script = self.sandbox(mut_apps=mut)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="app")

    def test_a_sixth_job_is_a_refusal(self):
        def mut(text):
            self.assertIn("\njobs:\n", text)
            return text.replace(
                "\njobs:\n",
                '\njobs:\n  extra:\n    name: "dev: extra"\n',
                1,
            )

        root, script = self.sandbox(mut_dev=mut)
        planted = (root / ".github" / "workflows" / "ci-dev.yml").read_text()
        self.assertIn("  extra:\n", planted)
        self.assertIn("dev: extra", planted)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_refused(proc, job_id="extra")


# GitHub's job_id grammar, from the workflow-syntax docs, not from
# ci_contexts.JOB_ID. A fixture built from the parser under test can
# only contain input that parser already matches — that is why the
# tests above stayed green on extra jobs the regex cannot see.
# Start with a letter or `_`; then alphanumeric, hyphen, or underscore.
GITHUB_JOB_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class UnrecognisedWorkflowInput(unittest.TestCase):
    """A short list is never a valid answer to input this module does
    not understand. Extra jobs GitHub would accept, and include-matrix
    rows it would run, must be refused or named — not dropped."""

    SCRIPT = SCRIPT
    run_it = ContextsScript.run_it
    payload = ContextsScript.payload
    sandbox = ContextsScript.sandbox
    assert_refused = ContextsScript.assert_refused

    def plant_dev_job(self, key_line, marker):
        root, script = self.sandbox()
        path = root / ".github" / "workflows" / "ci-dev.yml"
        insertion = f"{key_line}\n    name: \"dev: extra\"\n".encode()
        support.plant_bytes(
            path,
            lambda raw, ins=insertion: raw.replace(
                b"\njobs:\n", b"\njobs:\n" + ins, 1
            ),
            expect="grow",
            recognisable=lambda raw, m=marker: (
                b"name: CI" in raw and b"  verify:" in raw and m in raw
            ),
        )
        landed = path.read_bytes()
        self.assertIn(marker, landed)
        self.assertIn(b"  verify:", landed)
        self.assertGreater(len(landed), 64)
        return script

    def plant_apps(self, mutate, marker):
        root, script = self.sandbox()
        path = root / ".github" / "workflows" / "ci-dev-apps.yml"
        support.plant_bytes(
            path,
            mutate,
            expect="grow",
            recognisable=lambda raw, m=marker: (
                b"name: CI" in raw and b"  workflow:" in raw and m in raw
            ),
        )
        landed = path.read_bytes()
        self.assertIn(marker, landed)
        self.assertIn(b"  workflow:", landed)
        self.assertGreater(len(landed), 64)
        return script

    def refuse_github_job(self, job_id, key_line):
        self.assertRegex(job_id, GITHUB_JOB_ID)
        marker = key_line.encode()
        script = self.plant_dev_job(key_line, marker)
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assertNotEqual(
            proc.returncode, 0,
            "unrecognised extra job was accepted:\n" + proc.stdout,
        )
        self.assert_refused(proc, job_id=job_id)

    def assert_seen_or_refused(self, proc, context):
        """Do not return a clean list that silently omitted *context*.

        Parsing the form (context appears, exit 0) or refusing the
        unrecognised form are both fail-closed. Exit 0 without the
        name is the defect.
        """
        if proc.returncode == 0:
            self.assertIn(context, proc.stdout.splitlines(), proc.stdout)
            return
        self.assert_refused(proc)

    def test_extra_job_id_with_underscore_is_a_refusal(self):
        # GitHub's own example: my_first_job / my_second_job.
        self.refuse_github_job("my_first_job", "  my_first_job:")

    def test_extra_job_id_starting_with_underscore_is_a_refusal(self):
        self.refuse_github_job("_hidden", "  _hidden:")

    def test_extra_job_id_with_uppercase_is_a_refusal(self):
        self.refuse_github_job("Lint", "  Lint:")

    def test_extra_job_id_with_mixed_case_is_a_refusal(self):
        self.refuse_github_job("CI_Check", "  CI_Check:")

    def test_quoted_extra_job_id_is_a_refusal(self):
        # YAML quoting is a form, not a different id. GitHub's job_id
        # after parse is quoted-job; the quotes are what the regex
        # never sees.
        self.assertRegex("quoted-job", GITHUB_JOB_ID)
        script = self.plant_dev_job('  "quoted-job":', b'  "quoted-job":')
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assertNotEqual(
            proc.returncode, 0,
            "quoted extra job was accepted:\n" + proc.stdout,
        )
        self.assert_refused(proc, job_id="quoted-job")

    def test_single_quoted_extra_job_id_is_a_refusal(self):
        # YAML single quotes are a form, not a different id. A regex
        # widened only for optional double quotes still never sees this
        # key.
        self.assertRegex("quoted-job", GITHUB_JOB_ID)
        script = self.plant_dev_job("  'quoted-job':", b"  'quoted-job':")
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assertNotEqual(
            proc.returncode, 0,
            "single-quoted extra job was accepted:\n" + proc.stdout,
        )
        self.assert_refused(proc, job_id="quoted-job")

    def test_unrecognised_job_must_not_be_swallowed_into_a_known_job(self):
        # job_block's next-job regex is the same character class as
        # JOB_ID. A quoted extra job between a known job's name: and
        # its shard: is absorbed; SHARD_LINE then reads the extra's
        # list and derive succeeds with the wrong contexts.
        needle = b'    name: "dev: workflow"\n'
        stolen = (
            b'    name: "dev: workflow"\n'
            b'  "stolen":\n'
            b"    strategy:\n"
            b"      matrix:\n"
            b"        shard: [9]\n"
        )

        def mutate(raw):
            self.assertIn(needle, raw)
            return raw.replace(needle, stolen, 1)

        script = self.plant_apps(mutate, b'  "stolen":')
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assertNotIn("dev: workflow (9)", proc.stdout)
        self.assertNotEqual(
            proc.returncode, 0,
            "unrecognised job was swallowed into a known job:\n"
            + proc.stdout,
        )
        self.assert_refused(proc, job_id="stolen")

    def test_flow_style_include_app_is_not_silently_dropped(self):
        extra = (
            b"          - {app: extra, "
            b"cmd: python3 -m unittest discover x -v}\n"
        )
        needle = b"          - app: telemetry\n"

        def mutate(raw):
            self.assertIn(needle, raw)
            return raw.replace(needle, extra + needle, 1)

        script = self.plant_apps(mutate, b"{app: extra,")
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_seen_or_refused(proc, "dev: extra")

    def test_flow_style_include_with_quoted_keys_is_not_silently_dropped(self):
        extra = (
            b'          - {"app": extra, '
            b'"cmd": python3 -m unittest discover x -v}\n'
        )
        needle = b"          - app: telemetry\n"

        def mutate(raw):
            self.assertIn(needle, raw)
            return raw.replace(needle, extra + needle, 1)

        script = self.plant_apps(mutate, b'{"app": extra,')
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_seen_or_refused(proc, "dev: extra")

    def test_nested_include_app_is_not_silently_dropped(self):
        extra = (
            b"          -\n"
            b"            app: extra\n"
            b"            cmd: python3 -m unittest discover x -v\n"
        )
        needle = b"          - app: telemetry\n"

        def mutate(raw):
            self.assertIn(needle, raw)
            return raw.replace(needle, extra + needle, 1)

        script = self.plant_apps(mutate, b"            app: extra\n")
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_seen_or_refused(proc, "dev: extra")

    def test_include_app_without_a_cmd_key_is_not_silently_dropped(self):
        extra = (
            b"          - app: extra\n"
            b"            command: python3 -m unittest discover x -v\n"
        )
        needle = b"          - app: telemetry\n"

        def mutate(raw):
            self.assertIn(needle, raw)
            return raw.replace(needle, extra + needle, 1)

        script = self.plant_apps(mutate, b"          - app: extra\n")
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_seen_or_refused(proc, "dev: extra")

    def test_include_app_with_cmd_before_app_is_not_silently_dropped(self):
        extra = (
            b"          - cmd: python3 -m unittest discover x -v\n"
            b"            app: extra\n"
        )
        needle = b"          - app: telemetry\n"

        def mutate(raw):
            self.assertIn(needle, raw)
            return raw.replace(needle, extra + needle, 1)

        script = self.plant_apps(mutate, b"            app: extra\n")
        proc = self.run_it(self.payload(["lint"]), script=script)
        self.assert_seen_or_refused(proc, "dev: extra")


if __name__ == "__main__":
    unittest.main()
