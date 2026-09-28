"""Reserved terms come from vocab.cue; the wall refuses each on its surfaces.

D-VOCAB-1/2/3: the prod-lane term is refused in dev-lane surfaces; the
dev-lane part is named container; plan files have no compose-term
carve-out. Coverage is a plant per term parsed from vocab.cue, on
every suffix class the wall's rule walks, not a list in this file —
a term or suffix added there next month is then covered without
editing this test.

The three ratified instances must fall out of that property. The
discriminating mutants are named below and planted, not described.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from test_vocabulary_wall import (
    REPO,
    SERVICE_HOMES,
    SERVICE_REFUSAL,
    run_wall,
    wall_const,
)

VOCAB_CUE = support.WF_DIR / "contracts" / "cue" / "vocab.cue"

# Assembled so this pass-2 surface does not itself carry the words.
_PROD = "ker" + "nel"
_COMPOSE = "serv" + "ice"

PROD_WORD = re.compile(
    rf"(?<![\w-]){re.escape(_PROD)}(?![\w-])", re.IGNORECASE)

# vocab.cue encodings this suite accepts. Neither is present at the
# ratification commit; the empty parse is the red, not a skip.
_RULE_FIELD = re.compile(r'"vocab\.([^"]+)":\s*true')
_TERM_RULE = re.compile(
    r'term:\s*"([^"]+)"\s*(?:[^{}]*?)rule:\s*"(vocab\.[^"]+)"',
    re.DOTALL,
)

HOMES = tuple(h.rstrip("/") for h in SERVICE_HOMES)

# One representative per wall suffix class. Membership is asserted at
# use, so a class that dropped the representative fails rather than
# skipping the plant. .md/.py are the two surfaces D-VOCAB-1 names
# (prose, and the file D-VOCAB-2 says still carries the word).
_SUFFIX_CLASSES = (
    ("text", "TEXT_SUFFIXES", ".md"),
    ("code", "CODE_SUFFIXES", ".py"),
)


def suffix_classes_or_fail(test):
    """Wall suffix classes plus a representative each class actually owns.

    Empty or missing classes would make a per-class loop assert nothing.
    A representative not in the class would plant a file the wall never
    walks, and the assertion afterwards would answer a question about
    nothing.
    """
    found = []
    for name, const, representative in _SUFFIX_CLASSES:
        suffixes = wall_const(const)
        test.assertIsNotNone(
            suffixes, f"{const} is missing from the wall")
        test.assertTrue(
            suffixes, f"{const} is empty; a loop would assert nothing")
        test.assertIn(
            representative, set(suffixes),
            f"{representative} is not in the wall's {const}")
        found.append((name, suffixes, representative))
    test.assertEqual(len(found), len(_SUFFIX_CLASSES))
    return found


def reserved_from_vocab_cue(text=None):
    """Wall-reserved terms and their rule ids, derived from vocab.cue.

    A ``vocab.<body>: true`` field whose body does not end in
    ``absent`` is a wall rule; the term is the first hyphen-separated
    token. A ``term: "…"`` / ``rule: "vocab.…"`` pair is the other
    accepted encoding. CUE ``-absent`` fields are observation checks,
    not wall refusals, and are skipped.
    """
    if text is None:
        text = VOCAB_CUE.read_text(encoding="utf-8")
    found = []
    seen = set()
    for match in _RULE_FIELD.finditer(text):
        body = match.group(1)
        if body.endswith("absent"):
            continue
        rec = {"term": body.split("-", 1)[0], "rule": f"vocab.{body}"}
        if rec["rule"] not in seen:
            seen.add(rec["rule"])
            found.append(rec)
    for match in _TERM_RULE.finditer(text):
        rec = {"term": match.group(1), "rule": match.group(2)}
        if rec["rule"] not in seen:
            seen.add(rec["rule"])
            found.append(rec)
    return found


def under_home(rel):
    return any(rel == home or rel.startswith(home + "/") for home in HOMES)


def plant_file(root, rel, content, word):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    landed = path.read_text(encoding="utf-8")
    if landed != content:
        raise AssertionError(f"{rel}: plant did not reach disk")
    if not re.search(
            rf"(?<![\w-]){re.escape(word)}(?![\w-])", landed, re.IGNORECASE):
        raise AssertionError(f"{rel}: plant does not carry {word!r}")
    return path


def sandbox_with_design():
    tmp = Path(tempfile.mkdtemp(prefix="wall-reserved-"))
    spec = tmp / "design" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("Observations are stored and reproduced.\n")
    return tmp


def wall_lines_for_rule(stdout, rule):
    return [line for line in stdout.splitlines() if rule in line]


class ReservedTermsAreDerivedFromVocabCue(unittest.TestCase):
    def test_every_reserved_term_from_vocab_cue_is_planted_and_caught(self):
        # Mutant 1: a term present in vocab.cue with no plant exercising
        # it fails here, because the plant list is the parse.
        self.assertTrue(VOCAB_CUE.is_file(), "vocab.cue is missing")
        terms = reserved_from_vocab_cue()
        self.assertTrue(
            terms,
            "vocab.cue named no wall-reserved terms; "
            "a loop over an empty list would assert nothing",
        )
        names = {item["term"] for item in terms}
        self.assertIn(_PROD, names)
        self.assertIn(_COMPOSE, names)

        classes = suffix_classes_or_fail(self)
        exercised = set()
        for item in terms:
            term, rule = item["term"], item["rule"]
            for cls_name, _suffixes, representative in classes:
                with self.subTest(
                        term=term, rule=rule, suffix_class=cls_name):
                    root = sandbox_with_design()
                    self.addCleanup(shutil.rmtree, root, ignore_errors=True)
                    rel = (
                        Path("ops") / "app" / "vocab_derived"
                        / f"{term}{representative}")
                    plant_file(
                        root, rel, f"The {term} is named here.\n", term)
                    proc = run_wall(root)
                    self.assertEqual(proc.returncode, 1, proc.stdout)
                    self.assertIn(rule, proc.stdout)
                    self.assertTrue(
                        any(rel.as_posix() in line
                            for line in wall_lines_for_rule(
                                proc.stdout, rule)),
                        proc.stdout,
                    )
            exercised.add(term)
        self.assertEqual(exercised, names)


class TheProdLaneTermIsRefusedInDevLane(unittest.TestCase):
    def test_the_prod_lane_term_in_an_unheard_of_dev_lane_file_is_caught(self):
        # Mutant 2: a hit in a file this suite never named.
        root = sandbox_with_design()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        rel = Path("ops") / "app" / "vocab_unheard_plant.md"
        plant_file(
            root, rel, f"The {_PROD} boots and dispatches.\n", _PROD)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertRegex(proc.stdout, rf"vocab\.{re.escape(_PROD)}-")
        self.assertTrue(
            any(rel.as_posix() in line for line in proc.stdout.splitlines()
                if _PROD in line.lower()),
            proc.stdout,
        )

    def test_directory_rename_alone_still_reds_on_plan_and_vet(self):
        # Mutant 3: the directory is container, the word remains in
        # plan_vet.py and a plan sentence.
        root = sandbox_with_design()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        errors = (
            Path("ops") / "agentscient" / "container" / "errors.py")
        vet = Path("ops") / "agentscient" / "checks" / "plan_vet.py"
        plan = Path("ops") / "agentscient" / "plans" / "U0.plan.md"
        errors_src = "class InjectError(Exception):\n    pass\n"
        (root / errors).parent.mkdir(parents=True, exist_ok=True)
        (root / errors).write_text(errors_src, encoding="utf-8")
        self.assertEqual(
            (root / errors).read_text(encoding="utf-8"), errors_src)
        self.assertIsNone(
            PROD_WORD.search((root / errors).read_text(encoding="utf-8")))
        plant_file(
            root, vet,
            f"the {_PROD} boots the registry\n", _PROD)
        plant_file(
            root, plan,
            f"the {_PROD} holds capabilities\n", _PROD)
        old = root / "ops" / "capabilities" / _PROD
        self.assertFalse(old.exists(), f"{old} must not exist in this mutant")
        self.assertTrue(
            (root / errors).is_file(), "container/errors.py missing")
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertRegex(proc.stdout, rf"vocab\.{re.escape(_PROD)}-")
        hits = [line for line in proc.stdout.splitlines()
                if _PROD in line.lower()]
        self.assertTrue(hits, proc.stdout)
        joined = "\n".join(hits)
        self.assertIn("plan_vet.py", joined, proc.stdout)
        self.assertIn("U0.plan.md", joined, proc.stdout)

    def test_the_prod_lane_term_fires_outside_homes_and_not_on_kernelled(self):
        root = sandbox_with_design()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        app = Path("ops") / "app" / "x" / "note.md"
        infra = Path("ops") / "infra" / "note.md"
        scratch = Path("ops") / "docs" / "scratch" / "note.md"
        cousin = Path("ops") / "app" / "x" / "cousin.py"
        plant_file(
            root, app, f"The {_PROD} is a prod-lane name.\n", _PROD)
        plant_file(
            root, infra, f"infra may mention {_PROD} as compose does.\n",
            _PROD)
        plant_file(
            root, scratch, f"research may mention {_PROD}.\n", _PROD)
        planted = root / cousin
        planted.parent.mkdir(parents=True, exist_ok=True)
        cousin_src = f"def {_PROD}led():\n    return 1\n"
        planted.write_text(cousin_src, encoding="utf-8")
        self.assertEqual(planted.read_text(encoding="utf-8"), cousin_src)
        self.assertIn(f"{_PROD}led", planted.read_text(encoding="utf-8"))
        self.assertIsNone(PROD_WORD.search(planted.read_text(encoding="utf-8")))
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertRegex(proc.stdout, rf"vocab\.{re.escape(_PROD)}-")
        hits = [line for line in proc.stdout.splitlines()
                if re.search(rf"vocab\.{re.escape(_PROD)}-", line)]
        self.assertTrue(hits, proc.stdout)
        for line in hits:
            self.assertIn("note.md", line)
            self.assertNotIn("infra/note.md", line)
            self.assertNotIn("scratch/note.md", line)
            self.assertNotIn("cousin.py", line)

    def test_the_prod_lane_term_under_conductor_is_quiet(self):
        root = sandbox_with_design()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        rel = Path("ops") / "conductor" / "quote.md"
        plant_file(
            root, rel, f"The {_PROD} is quoted as evidence.\n", _PROD)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotRegex(proc.stdout, rf"vocab\.{re.escape(_PROD)}-")

    def test_the_prod_lane_term_is_refused_on_every_suffix_class(self):
        # Mutant 5: a wall that registers the prod-lane rule against
        # TEXT_SUFFIXES only, never CODE_SUFFIXES. Each class is its
        # own plant, so an or between surfaces cannot hide the hole.
        classes = suffix_classes_or_fail(self)
        for cls_name, _suffixes, representative in classes:
            with self.subTest(suffix_class=cls_name, suffix=representative):
                root = sandbox_with_design()
                self.addCleanup(shutil.rmtree, root, ignore_errors=True)
                rel = (
                    Path("ops") / "app" / "vocab_class"
                    / f"{cls_name}{representative}")
                plant_file(
                    root, rel, f"The {_PROD} is named here.\n", _PROD)
                proc = run_wall(root)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertRegex(
                    proc.stdout, rf"vocab\.{re.escape(_PROD)}-")
                hits = [
                    line for line in proc.stdout.splitlines()
                    if re.search(rf"vocab\.{re.escape(_PROD)}-", line)]
                self.assertTrue(hits, proc.stdout)
                self.assertTrue(
                    any(rel.as_posix() in line for line in hits),
                    proc.stdout,
                )


class PlanFilesHaveNoComposeCarveOut(unittest.TestCase):
    def test_service_in_a_plan_json_is_caught_with_no_carve_out(self):
        # Mutant 4: a *.plan.json carve-out must still red on the U0 line.
        root = sandbox_with_design()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        rel = Path("ops") / "agentscient" / "agentscient.plan.json"
        payload = {
            "id": "D-launcher-after",
            "sentence": (
                "Moving the launcher and levers under the framework "
                f"so a {_COMPOSE} is a capability."
            ),
        }
        content = json.dumps(payload) + "\n"
        plant_file(root, rel, content, _COMPOSE)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertTrue(SERVICE_REFUSAL.search(proc.stdout), proc.stdout)
        self.assertTrue(
            any("agentscient.plan.json" in line
                for line in proc.stdout.splitlines()
                if SERVICE_REFUSAL.search(line)),
            proc.stdout,
        )


class TheDevLanePartIsContainer(unittest.TestCase):
    def test_the_agentscient_prod_lane_named_directory_does_not_exist(self):
        old = REPO / "ops" / "capabilities" / _PROD
        new = REPO / "ops" / "capabilities" / "container"
        self.assertFalse(
            old.exists(),
            f"{old.relative_to(REPO).as_posix()} still exists",
        )
        self.assertTrue(
            new.is_dir(),
            "container/ is the dev-lane part and is missing",
        )
        self.assertTrue(
            (new / "errors.py").is_file(),
            "container/errors.py is missing",
        )

    def test_no_dev_lane_surface_outside_homes_names_the_prod_lane_term(self):
        prefixes = wall_const("ALLOWED_PREFIXES")
        files = wall_const("ALLOWED_FILES")
        text_suffixes = wall_const("TEXT_SUFFIXES")
        code_suffixes = wall_const("CODE_SUFFIXES")
        self.assertIsNotNone(prefixes)
        self.assertIsNotNone(files)
        self.assertIsNotNone(text_suffixes)
        self.assertIsNotNone(code_suffixes)
        suffixes = set(text_suffixes) | set(code_suffixes)
        self.assertTrue(
            suffixes, "wall named no suffixes; a scan would assert nothing")

        offenders = []
        candidates = []
        for name in files:
            path = REPO / name
            if path.is_file():
                candidates.append(path)
        for prefix in prefixes:
            root = REPO / str(prefix).rstrip("/")
            if not root.exists():
                continue
            if root.is_file():
                candidates.append(root)
                continue
            candidates.extend(p for p in root.rglob("*") if p.is_file())
        for path in candidates:
            try:
                rel = path.relative_to(REPO).as_posix()
            except ValueError:
                continue
            if under_home(rel):
                continue
            parts = Path(rel).parts
            if any(part.lower() == _PROD for part in parts):
                offenders.append(f"{rel}:path")
            if path.suffix not in suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            hits = [
                i for i, line in enumerate(text.splitlines(), 1)
                if PROD_WORD.search(line)]
            if hits:
                offenders.append(f"{rel}:{hits}")
        self.assertEqual(
            offenders, [],
            "dev-lane surfaces still name the prod-lane term",
        )


class ConductorIsAHomeForBothReservedTerms(unittest.TestCase):
    def test_both_reserved_terms_under_conductor_are_accepted(self):
        # Amendment 2026-08-31: a quoting surface, same class as records.
        # One file per rule so a wall that reports only the first hit
        # on a line cannot hide a missing exemption.
        root = sandbox_with_design()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        compose_rel = Path("ops") / "conductor" / "quote-compose.md"
        prod_rel = Path("ops") / "conductor" / "quote-prod.md"
        plant_file(
            root, compose_rel,
            f"quoted {_COMPOSE} as evidence.\n", _COMPOSE)
        plant_file(
            root, prod_rel,
            f"quoted {_PROD} as evidence.\n", _PROD)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assertNotRegex(proc.stdout, rf"vocab\.{re.escape(_PROD)}-")

    def test_both_reserved_terms_outside_every_home_are_refused(self):
        root = sandbox_with_design()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        compose_rel = Path("ops") / "app" / "vocab_outside_compose.md"
        prod_rel = Path("ops") / "app" / "vocab_outside_prod.md"
        plant_file(
            root, compose_rel,
            f"quoted {_COMPOSE} as evidence.\n", _COMPOSE)
        plant_file(
            root, prod_rel,
            f"quoted {_PROD} as evidence.\n", _PROD)
        self.assertFalse(under_home(compose_rel.as_posix()))
        self.assertFalse(under_home(prod_rel.as_posix()))
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertTrue(SERVICE_REFUSAL.search(proc.stdout), proc.stdout)
        self.assertRegex(proc.stdout, rf"vocab\.{re.escape(_PROD)}-")
        service_hits = [
            line for line in proc.stdout.splitlines()
            if SERVICE_REFUSAL.search(line)]
        prod_hits = [
            line for line in proc.stdout.splitlines()
            if re.search(rf"vocab\.{re.escape(_PROD)}-", line)]
        self.assertTrue(service_hits, proc.stdout)
        self.assertTrue(prod_hits, proc.stdout)
        self.assertTrue(
            any(compose_rel.as_posix() in line for line in service_hits),
            proc.stdout,
        )
        self.assertTrue(
            any(prod_rel.as_posix() in line for line in prod_hits),
            proc.stdout,
        )


class TheMergedTreeIsQuiet(unittest.TestCase):
    def test_the_real_tree_is_quiet_on_both_reserved_terms_and_scans(self):
        proc = run_wall(REPO)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assertNotRegex(proc.stdout, rf"vocab\.{re.escape(_PROD)}-")
        self.assertNotIn("nothing to scan", proc.stdout)
        self.assertIn("pass 1", proc.stdout)
        self.assertIn("pass 2", proc.stdout)
        self.assertRegex(
            proc.stdout, r"clean [—-] [1-9]\d*(?: design)? file")


if __name__ == "__main__":
    unittest.main()
