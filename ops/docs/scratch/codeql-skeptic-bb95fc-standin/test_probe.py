"""Probes that say, per surviving row, exactly what the suite looked at.

Each probe is an assertion about the mutant, not about the suite: it
proves the defect is really in the file the suite read green.

    python3 -m unittest discover -s <out> -t <out> -p 'test_probe.py'
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import standin  # noqa: E402

MOD = standin.load(HERE / "_standin" / "honest")


def load(name):
    path = HERE / "_standin" / name / "codeql.yml"
    if not path.is_file():
        raise unittest.SkipTest(f"{name} not materialised; run test_variants first")
    return MOD.load_gha(path.read_text(encoding="utf-8")), path


class InitWithBlockIsUnpinned(unittest.TestCase):
    def test_languages_is_hardcoded_and_the_suite_read_it_green(self):
        doc, _ = load("init_languages_pinned")
        init = MOD.step_uses(doc, MOD.INIT_ACTION)
        self.assertEqual(init["with"]["languages"], "actions")
        # every helper that reads init's with: is quiet
        self.assertEqual(MOD.bundle_pin_problems(_text("init_languages_pinned")), [])

    def test_a_paths_ignore_config_excludes_the_plant(self):
        doc, _ = load("init_ignores_the_plant")
        init = MOD.step_uses(doc, MOD.INIT_ACTION)
        self.assertIn("paths-ignore", init["with"]["config"])
        self.assertIn("codeql-proof", init["with"]["config"])
        # and the plant still lands in codeql-proof/
        plant = MOD.copy_step(doc)
        self.assertIn("codeql-proof/findable.py", plant["run"])


class GuardOutputKeyIsHandBound(unittest.TestCase):
    def test_no_step_carries_the_id_the_ifs_read(self):
        doc, _ = load("guard_has_no_id")
        ids = [step.get("id") for step in MOD.steps_of(doc)]
        self.assertNotIn("default-setup", ids)
        init = MOD.step_uses(doc, MOD.INIT_ACTION)
        self.assertIn("steps.default-setup.outputs.state", init["if"])
        # GitHub binds an absent step output to the empty string:
        real = {"steps.default-setup.outputs.state": "", "env.PROOF": "0"}
        self.assertFalse(MOD.github_if(init.get("if"), real))
        skip = MOD.skip_step(doc)
        self.assertTrue(MOD.github_if(skip.get("if"), real))

    def test_the_endpoint_is_never_pinned_to_this_repository(self):
        doc, _ = load("guard_reads_another_repo")
        guard = MOD._default_setup_step(self, _text("guard_reads_another_repo"))
        self.assertIn("repos/github/codeql-action", guard["run"])
        self.assertNotIn("GITHUB_REPOSITORY", guard["run"])
        problems, observed = MOD.observe_guard_states(
            self, _text("guard_reads_another_repo")
        )
        self.assertEqual(problems, [], "the stub answers any URL identically")
        self.assertEqual(observed["configured"], "configured")


class PlantSourceIsManufacturedByTheHarness(unittest.TestCase):
    def test_execute_copy_creates_whatever_path_the_run_names(self):
        text = _text("plant_source_is_another_fixture")
        doc = MOD.load_gha(text)
        step = MOD.copy_step(doc)
        named = ".dev/ci/findable.py.fixture"
        self.assertIn(named, step["run"])
        self.assertFalse(
            (MOD.REPO / named).exists(),
            "the path the plant names does not exist in the repository",
        )
        cwd, proc = MOD.execute_copy(self, step)
        self.assertEqual(proc.returncode, 0, "the harness made the cp succeed anyway")
        self.assertTrue((cwd / named).is_file())
        self.assertEqual(MOD.plant_execution_problems(self, text), [])


class SecondPlantIsNeverLookedAt(unittest.TestCase):
    def test_copy_step_returns_only_the_first_match(self):
        text = _text("second_unconditional_plant")
        doc = MOD.load_gha(text)
        planting = [
            step for step in MOD.steps_of(doc)
            if "findable.py.fixture" in str(step.get("run") or "")
        ]
        self.assertEqual(len(planting), 2)
        self.assertIs(MOD.copy_step(doc), planting[0])
        self.assertEqual(planting[0].get("if"), "env.PROOF == '1'")
        self.assertIsNone(planting[1].get("if"), "the second plant is unguarded")
        self.assertTrue(
            MOD.github_if(planting[1].get("if"), MOD.proof_ctx(False, "not-configured"))
        )
        self.assertEqual(MOD.fixture_exclusion_problems(text), [])


class JobLevelContinueOnErrorIsNotLookedAt(unittest.TestCase):
    def test_only_step_level_is_scanned(self):
        doc, _ = load("job_continue_on_error")
        self.assertEqual(MOD.analyze_job(doc).get("continue-on-error"), True)
        self.assertEqual(MOD.continue_on_error_steps(doc), [])


def _text(name):
    return (HERE / "_standin" / name / "codeql.yml").read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
