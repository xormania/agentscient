"""The vocabulary wall bites, and cannot pass over nothing.

The wall had one test — that it was registered and runnable — while
the design tree it polices is nearly empty: at the time of writing it
scans a single file, and every allowed prefix or file shrinks that
further. So the two properties worth pinning are that it still
catches a reserved term in a real design artifact, and that it
refuses rather than reports clean when it scanned nothing.

U1 adds a second pass over the surfaces pass 1 exempts: the compose
term lives under `ops/devlane/infra/` (plus the stated homes);
`capability` joins the reserved set so the design tree cannot borrow
the framework's word. Fixtures under fixtures/vocab/ plant those words
at test time; the committed copies keep a token so the real tree is
not itself a hit.
"""

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

CHECK = support.WF_DIR / "checks" / "vocabulary_wall.py"
REPO = support.WF_DIR.parent.parent.parent
CONTRACTS = support.WF_DIR / "contracts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vocab"
VET = CONTRACTS / "vet.py"

# Assembled so this pass-2 surface does not itself carry the word.
_COMPOSE = "serv" + "ice"
_COMPOSE_PL = "serv" + "ices"
_COMPOSE_TITLE = "Serv" + "ice"

SERVICE_HOMES = (
    "ops/devlane/infra/",
    "ops/docs/scratch/",
    ".dev/handoffs/",
    ".dev/records/",
    "ops/conductor/",
    ".git/",
)
SERVICE_TERMS = (_COMPOSE, _COMPOSE_PL)
CODE_SUFFIXES = (".py", ".json")
HOME_REASONS = (
    ("ops/devlane/infra/", "compose"),
    ("ops/docs/scratch/", "research"),
    (".dev/handoffs/", "systemd"),
    (".dev/records/", "evidence"),
    ("ops/conductor/", "conductor records quote evidence"),
    (".git/", "not a tree surface"),
)

# Longer tokens first: __VOCAB_SERVICE__ is a prefix of __VOCAB_SERVICES__.
PLANT_TOKENS = (
    ("__VOCAB_SERVICES__", _COMPOSE_PL),
    ("__VOCAB_SERVICE_TITLE__", _COMPOSE_TITLE),
    ("__VOCAB_SERVICE__", _COMPOSE),
)
SERVICE_WORD = re.compile(
    rf"(?<![\w-]){_COMPOSE}s?(?![\w-])", re.IGNORECASE)
# One grammar: pass 1 keeps the pre-existing "design file" wording;
# pass 2 reports "file". The "design" token is optional so both match.
CLEAN_N = re.compile(r"clean [—-] ([1-9]\d*)(?: design)? file")
SERVICE_REFUSAL = re.compile(
    rf"vocab\.{re.escape(_COMPOSE)}-outside-infra: "
    rf".+:[0-9]+: '{re.escape(_COMPOSE)}' in: .+",
)


def wall_const(name):
    tree = ast.parse(CHECK.read_text())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == name
                        for t in node.targets)):
            return ast.literal_eval(node.value)
    return None


def run_wall(root):
    return subprocess.run(
        [sys.executable, str(CHECK), "--root", str(root)],
        capture_output=True, text=True, check=False,
    )


def pass_slice(stdout, n):
    """The report section for pass n, or the whole report if unlabelled."""
    lower = stdout.lower()
    marker = f"pass {n}"
    if marker not in lower:
        return stdout
    start = lower.index(marker)
    rest = lower[start + len(marker):]
    nxt = re.search(r"pass\s+\d+", rest)
    if nxt:
        return stdout[start:start + len(marker) + nxt.start()]
    return stdout[start:]


def file_map(root):
    mapping = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            mapping[path.relative_to(root).as_posix()] = path.read_bytes()
    return mapping


def materialize(src, dst):
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token, word in PLANT_TOKENS:
            text = text.replace(token, word)
        leftover = re.findall(r"__VOCAB_[A-Z0-9_]+__", text)
        if leftover:
            raise AssertionError(
                f"{path}: unreplaced tokens {leftover}")
        target = dst / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


class TheWallBites(unittest.TestCase):
    def run_wall(self, root):
        return run_wall(root)

    def test_a_planted_design_artifact_is_caught(self):
        with tempfile.TemporaryDirectory(prefix="wall-") as raw:
            root = Path(raw)
            artifact = root / "design" / "spec.md"
            artifact.parent.mkdir(parents=True)
            planted = "The engine records a receipt for each write.\n"
            artifact.write_text(planted)
            self.assertEqual(artifact.read_text(), planted)
            self.assertIn("receipt", artifact.read_text())

            proc = self.run_wall(root)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("receipt", proc.stdout)
            self.assertIn("spec.md", proc.stdout)

    def test_a_clean_design_artifact_passes(self):
        with tempfile.TemporaryDirectory(prefix="wall-") as raw:
            root = Path(raw)
            artifact = root / "design" / "spec.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("Observations are stored and reproduced.\n")

            proc = self.run_wall(root)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("clean", proc.stdout)

    def test_a_zero_file_scan_says_so_instead_of_claiming_clean(self):
        # Vacuously true, and sandboxes depend on it passing — but the
        # report must not be indistinguishable from a real clean scan.
        # Scope to pass 1: the same fixture is a pass-2 target, and
        # pass 2 may honestly report clean.
        with tempfile.TemporaryDirectory(prefix="wall-empty-") as raw:
            root = Path(raw)
            (root / "ops").mkdir()
            (root / ".dev" / "note.md").write_text("gate receipt claim\n")

            proc = self.run_wall(root)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = pass_slice(proc.stdout, 1)
            self.assertIn("nothing to scan", report)
            self.assertNotIn("clean —", report)

    def test_the_repo_wall_still_covers_at_least_one_design_file(self):
        # This is where the danger lives: every allowed prefix or file
        # shrinks the design surface, and at zero the wall would pass
        # forever without looking at anything.
        proc = self.run_wall(REPO)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("nothing to scan", proc.stdout)
        self.assertRegex(proc.stdout, r"clean — [1-9]\d* design file")

    def test_the_allowed_root_files_are_the_documented_set(self):
        # ruff.toml is allowed because a lint config cannot name the
        # dev-lane paths it configures without using the vocabulary;
        # widening this set is how the wall stops measuring anything,
        # so the set itself is pinned.
        allowed = wall_const("ALLOWED_FILES")
        self.assertEqual(
            allowed,
            ("AGENTS.md", "CONTRIB.md", "README.md", "ruff.toml"))


class TheSecondPassWallsService(unittest.TestCase):
    def prove_plant(self, dirty_name, word, rel):
        with tempfile.TemporaryDirectory(prefix="wall-plant-") as raw:
            tmp = Path(raw)
            clean_root = tmp / "clean"
            dirty_root = tmp / dirty_name
            materialize(FIXTURES / "clean", clean_root)
            materialize(FIXTURES / dirty_name, dirty_root)
            self.assertNotEqual(
                file_map(dirty_root), file_map(clean_root),
                f"{dirty_name} is identical to clean/")
            planted = dirty_root / rel
            self.assertTrue(planted.is_file(), rel)
            self.assertRegex(
                planted.read_text(encoding="utf-8"),
                rf"(?i)(?<![\w-]){re.escape(word)}(?![\w-])")
            return file_map(dirty_root)

    def materialize_into(self, name):
        tmp = Path(tempfile.mkdtemp(prefix=f"wall-{name}-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        materialize(FIXTURES / name, tmp)
        return tmp

    def sandbox_with_design(self, rel, content):
        tmp = Path(tempfile.mkdtemp(prefix="wall-home-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        spec = tmp / "design" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("Observations are stored and reproduced.\n")
        planted = tmp / rel
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(content)
        self.assertEqual(planted.read_text(), content)
        self.assertRegex(planted.read_text(), SERVICE_WORD)
        return tmp

    def assert_compose_refusal(self, stdout, filename):
        self.assertTrue(
            SERVICE_REFUSAL.search(stdout), stdout)
        self.assertTrue(
            any(filename in line
                for line in stdout.splitlines()
                if SERVICE_REFUSAL.search(line)),
            stdout)

    def assert_both_passes_clean(self, stdout):
        self.assertIn("pass 1", stdout)
        self.assertIn("pass 2", stdout)
        for n in (1, 2):
            section = pass_slice(stdout, n)
            found = CLEAN_N.search(section)
            self.assertIsNotNone(found, section)
            self.assertGreaterEqual(int(found.group(1)), 1)

    def test_service_homes_are_the_documented_set(self):
        homes = wall_const("SERVICE_HOMES")
        self.assertEqual(tuple(homes) if homes is not None else None,
                         SERVICE_HOMES)

    def test_code_suffixes_are_py_and_json(self):
        suffixes = wall_const("CODE_SUFFIXES")
        self.assertEqual(
            tuple(suffixes) if suffixes is not None else None,
            CODE_SUFFIXES)

    def test_service_terms_are_singular_and_plural(self):
        terms = wall_const("SERVICE_TERMS")
        self.assertEqual(
            tuple(terms) if terms is not None else None,
            SERVICE_TERMS)

    def test_each_service_home_exists(self):
        homes = wall_const("SERVICE_HOMES")
        self.assertIsNotNone(homes, "SERVICE_HOMES is missing from the wall")
        for home in homes:
            with self.subTest(home=home):
                target = REPO / str(home).rstrip("/")
                self.assertTrue(
                    target.exists(),
                    f"{home} is a named home but does not exist")

    def test_wall_docstring_states_each_home_reason(self):
        doc = ast.get_docstring(ast.parse(CHECK.read_text()))
        self.assertIsNotNone(doc, "the wall has no docstring")
        for home, reason in HOME_REASONS:
            with self.subTest(home=home, reason=reason):
                self.assertIn(home, doc)
                self.assertIn(reason, doc)

    def test_a_clean_fixture_is_quiet_on_both_passes(self):
        # `ops/devlane/infra/` is compose's home — the only place the word
        # is the right word. The app file saying capability must stay
        # quiet too: pass 1 does not reach `.dev/`.
        compose = (
            FIXTURES / "clean" / "ops" / "devlane" / "infra" / "compose.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("__VOCAB_SERVICES__", compose)
        app = (FIXTURES / "clean" / "ops" / "devlane" / "x" / "x.py").read_text(
            encoding="utf-8")
        self.assertRegex(app, r"(?i)\bcapability\b")
        root = self.materialize_into("clean")
        planted = (root / "ops" / "devlane" / "infra" / "compose.yaml").read_text()
        self.assertRegex(
            planted, rf"(?i)(?<![\w-]){_COMPOSE_PL}(?![\w-])")
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(
            f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assert_both_passes_clean(proc.stdout)

    def test_service_in_an_app_module_fires(self):
        self.prove_plant(
            "service-in-app", _COMPOSE, "ops/devlane/x/x.py")
        root = self.materialize_into("service-in-app")
        planted = (root / "ops" / "devlane" / "x" / "x.py").read_text()
        self.assertIn(f"class {_COMPOSE_TITLE}", planted)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assert_compose_refusal(proc.stdout, "x.py")

    def test_service_in_an_app_json_fires(self):
        self.prove_plant(
            "service-in-json", _COMPOSE,
            "ops/devlane/x/capability.json")
        root = self.materialize_into("service-in-json")
        planted = (
            root / "ops" / "devlane" / "x" / "capability.json"
        ).read_text()
        self.assertIn(f'"{_COMPOSE}"', planted)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assert_compose_refusal(proc.stdout, "capability.json")

    def test_service_in_docs_outside_scratch_fires(self):
        with tempfile.TemporaryDirectory(prefix="wall-docs-") as raw:
            root = Path(raw)
            note = root / "ops" / "docs" / "note.md"
            note.parent.mkdir(parents=True)
            planted = f"The docker {_COMPOSE} is a container.\n"
            note.write_text(planted)
            self.assertEqual(note.read_text(), planted)
            self.assertRegex(note.read_text(), SERVICE_WORD)
            spec = root / "design" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("Observations are stored and reproduced.\n")
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assert_compose_refusal(proc.stdout, "note.md")

    def test_service_under_docs_scratch_is_quiet(self):
        # Research that names other frameworks' objects by their names.
        content = (
            f"OSGi names the injected object a {_COMPOSE}.\n")
        root = self.sandbox_with_design(
            "ops/docs/scratch/note.md", content)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(
            f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assert_both_passes_clean(proc.stdout)

    def test_service_under_handoffs_is_quiet(self):
        # Dated session handoffs; systemd's word for the runners.
        content = f"systemd user {_COMPOSE_PL} start the runners.\n"
        root = self.sandbox_with_design(
            ".dev/handoffs/h.md", content)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(
            f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assert_both_passes_clean(proc.stdout)

    def test_service_under_records_is_quiet(self):
        # Dispatch records are committed evidence and are never edited.
        content = '{\n  "note": "' + _COMPOSE + '"\n}\n'
        root = self.sandbox_with_design(
            ".dev/records/dispatches/r.json", content)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(
            f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assert_both_passes_clean(proc.stdout)

    def test_service_under_conductor_is_quiet(self):
        # Conductor records quote evidence; the reserved term there is
        # a citation, not a leak.
        content = f"the quoted {_COMPOSE} in a conductor record.\n"
        root = self.sandbox_with_design(
            "ops/conductor/quote.md", content)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(
            f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assert_both_passes_clean(proc.stdout)

    def test_service_under_conductor_not_as_a_prefix_fires(self):
        with tempfile.TemporaryDirectory(prefix="wall-cond-not-") as raw:
            root = Path(raw)
            planted_path = root / ".dev" / "conductor-not" / "quote.md"
            planted_path.parent.mkdir(parents=True)
            planted = f"the quoted {_COMPOSE} is not under the home.\n"
            planted_path.write_text(planted)
            self.assertEqual(planted_path.read_text(), planted)
            self.assertRegex(planted_path.read_text(), SERVICE_WORD)
            spec = root / "design" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("Observations are stored and reproduced.\n")
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assert_compose_refusal(proc.stdout, "quote.md")
            self.assertIn("conductor-not", proc.stdout)

    def test_service_under_git_is_quiet(self):
        # `.git/` is not a tree surface. `.github/` is a pass-2
        # surface, so a sibling plant there still fires — that is
        # what distinguishes a home from never walking git-like paths.
        with tempfile.TemporaryDirectory(prefix="wall-git-") as raw:
            root = Path(raw)
            spec = root / "design" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("Observations are stored and reproduced.\n")
            git_cfg = root / ".git" / "config"
            git_cfg.parent.mkdir(parents=True)
            git_planted = f"[foo]\nbar = {_COMPOSE}\n"
            git_cfg.write_text(git_planted)
            self.assertEqual(git_cfg.read_text(), git_planted)
            self.assertRegex(git_cfg.read_text(), SERVICE_WORD)
            gh = root / ".github" / "note.md"
            gh.parent.mkdir(parents=True)
            gh_planted = f"the {_COMPOSE} is compose's word.\n"
            gh.write_text(gh_planted)
            self.assertEqual(gh.read_text(), gh_planted)
            self.assertRegex(gh.read_text(), SERVICE_WORD)
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assert_compose_refusal(proc.stdout, "note.md")
            hit_lines = [
                line for line in proc.stdout.splitlines()
                if SERVICE_REFUSAL.search(line)]
            self.assertTrue(hit_lines, proc.stdout)
            for line in hit_lines:
                self.assertNotIn(".git/config", line)

    def test_service_under_infra_not_as_a_prefix_fires(self):
        with tempfile.TemporaryDirectory(prefix="wall-infra-not-") as raw:
            root = Path(raw)
            planted_path = root / ".dev" / "infra-not" / "compose.yaml"
            planted_path.parent.mkdir(parents=True)
            planted = f"{_COMPOSE_PL}:\n  db:\n    image: example\n"
            planted_path.write_text(planted)
            self.assertEqual(planted_path.read_text(), planted)
            self.assertRegex(planted_path.read_text(), SERVICE_WORD)
            spec = root / "design" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("Observations are stored and reproduced.\n")
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assert_compose_refusal(proc.stdout, "compose.yaml")
            self.assertIn("infra-not", proc.stdout)

    def test_serviced_does_not_match_as_service(self):
        with tempfile.TemporaryDirectory(prefix="wall-serviced-") as raw:
            root = Path(raw)
            planted = root / "ops" / "devlane" / "x" / "x.py"
            planted.parent.mkdir(parents=True)
            planted.write_text("def serviced():\n    return 1\n")
            self.assertIn("serviced", planted.read_text())
            self.assertIsNone(SERVICE_WORD.search(planted.read_text()))
            spec = root / "design" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("Observations are stored and reproduced.\n")
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertNotIn(
                f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
            self.assert_both_passes_clean(proc.stdout)

    def test_a_zero_file_pass_2_says_so_instead_of_claiming_clean(self):
        with tempfile.TemporaryDirectory(prefix="wall-p2-empty-") as raw:
            root = Path(raw)
            spec = root / "design" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("Observations are stored and reproduced.\n")
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("pass 2", proc.stdout)
            self.assertIn("nothing to scan", proc.stdout)
            p2 = pass_slice(proc.stdout, 2)
            self.assertNotIn("clean -", p2.replace("—", "-"))

    def test_the_real_tree_is_quiet_on_both_passes_and_scans_files(self):
        proc = run_wall(REPO)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn(
            f"vocab.{_COMPOSE}-outside-infra", proc.stdout)
        self.assertNotIn("nothing to scan", proc.stdout)
        self.assert_both_passes_clean(proc.stdout)

    def test_pass2_surfaces_outside_homes_do_not_carry_the_compose_term(self):
        # D-U1-rename: a hit is a rename. Walk the pass-2 surface
        # (ALLOWED_PREFIXES | ALLOWED_FILES, text + code suffixes)
        # minus SERVICE_HOMES and demand an empty hit list.
        prefixes = wall_const("ALLOWED_PREFIXES")
        files = wall_const("ALLOWED_FILES")
        text_suffixes = wall_const("TEXT_SUFFIXES")
        self.assertIsNotNone(prefixes)
        self.assertIsNotNone(files)
        self.assertIsNotNone(text_suffixes)
        suffixes = set(text_suffixes) | set(CODE_SUFFIXES)
        homes = tuple(h.rstrip("/") for h in SERVICE_HOMES)

        def under_home(rel):
            return any(rel == h or rel.startswith(h + "/") for h in homes)

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
            if path.suffix not in suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            hits = [
                i for i, line in enumerate(text.splitlines(), 1)
                if SERVICE_WORD.search(line)]
            if hits:
                offenders.append(f"{rel}:{hits}")
        self.assertEqual(
            offenders, [],
            "pass-2 surfaces still carry the compose term")

    def test_a_py_in_the_design_tree_is_scanned_by_neither_pass(self):
        # D-U1-two-passes partitions named surfaces, not every suffix.
        # A .py outside ALLOWED_PREFIXES | ALLOWED_FILES is skipped by
        # pass 1 (not a text suffix) and by pass 2 (not a pass-2
        # surface). The compose term there is not a hit.
        with tempfile.TemporaryDirectory(prefix="wall-neither-") as raw:
            root = Path(raw)
            spec = root / "design" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("Observations are stored and reproduced.\n")
            tool = root / "design" / "tool.py"
            planted = f"class {_COMPOSE_TITLE}:\n    pass\n"
            tool.write_text(planted)
            self.assertEqual(tool.read_text(), planted)
            self.assertRegex(tool.read_text(), SERVICE_WORD)
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("pass 1", proc.stdout)
            self.assertIn("pass 2", proc.stdout)
            self.assertNotIn(
                f"vocab.{_COMPOSE}-outside-infra", proc.stdout)


class TheCapabilityTermIsReserved(unittest.TestCase):
    def test_reserved_includes_capability_and_capabilities(self):
        reserved = wall_const("RESERVED")
        self.assertIsNotNone(reserved, "RESERVED is missing from the wall")
        terms = set(reserved)
        self.assertIn("capability", terms)
        self.assertIn("capabilities", terms)

    def test_a_planted_capability_in_design_is_caught(self):
        dirty = file_map(FIXTURES / "capability-in-design")
        clean = file_map(FIXTURES / "clean")
        self.assertNotEqual(dirty, clean)
        spec = (
            FIXTURES / "capability-in-design" / "design" / "spec.md"
        ).read_text(encoding="utf-8")
        self.assertRegex(spec, r"(?i)(?<![\w-])capability(?![\w-])")
        root = Path(tempfile.mkdtemp(prefix="wall-cap-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        materialize(FIXTURES / "capability-in-design", root)
        proc = run_wall(root)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("capability", proc.stdout)
        self.assertIn("spec.md", proc.stdout)
        self.assertNotIn(
            f"vocab.{_COMPOSE}-outside-infra", proc.stdout)

    def test_a_planted_capabilities_in_design_is_caught(self):
        with tempfile.TemporaryDirectory(prefix="wall-caps-") as raw:
            root = Path(raw)
            artifact = root / "design" / "spec.md"
            artifact.parent.mkdir(parents=True)
            planted = "These capabilities are the framework's objects.\n"
            artifact.write_text(planted)
            self.assertEqual(artifact.read_text(), planted)
            self.assertIn("capabilities", artifact.read_text())
            proc = run_wall(root)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("capabilities", proc.stdout)
            self.assertIn("spec.md", proc.stdout)


class TheVocabContractGainsCapability(unittest.TestCase):
    def test_vocab_cue_has_a_raw_has_capability_check(self):
        text = (CONTRACTS / "cue" / "vocab.cue").read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r'for _, literal in literals if strings\.Contains'
            r'\(literal, "capability"\)',
        )
        self.assertRegex(text, r"_has_capability:\s*true")
        self.assertRegex(text, r"_has_capability!:\s*true")

    def test_examples_vocab_json_lists_capability(self):
        data = json.loads(
            (CONTRACTS / "examples" / "vocab.json").read_text(
                encoding="utf-8"))
        literals = data["facts"]["literals"]
        self.assertIn("capability", literals)
        self.assertIn("capability", data["facts"]["joined"])

    def test_obs_vocab_json_lists_capability(self):
        data = json.loads(
            (CONTRACTS / "obs" / "vocab.json").read_text(
                encoding="utf-8"))
        literals = data["facts"]["literals"]
        self.assertIn("capability", literals)
        self.assertIn("capability", data["facts"]["joined"])

    def test_fault_vocab_4_exists_and_names_capability(self):
        fault = CONTRACTS / "faults" / "vocab.4.json"
        meta = CONTRACTS / "faults" / "vocab.4.meta.json"
        self.assertTrue(fault.is_file(), "faults/vocab.4.json is missing")
        self.assertTrue(meta.is_file(), "faults/vocab.4.meta.json is missing")
        data = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual(
            data["reject_path"],
            r"facts\.(joined|literals)\b|capability",
        )
        cited = " ".join(
            str(data.get(k, ""))
            for k in ("violates", "change", "note", "quote"))
        self.assertIn("capability", cited.lower())

    def test_fault_vocab_4_removes_capability_from_literals(self):
        example_path = CONTRACTS / "examples" / "vocab.json"
        fault_path = CONTRACTS / "faults" / "vocab.4.json"
        self.assertTrue(fault_path.is_file(), "faults/vocab.4.json is missing")
        example = json.loads(example_path.read_text(encoding="utf-8"))
        fault = json.loads(fault_path.read_text(encoding="utf-8"))
        self.assertIn("capability", example["facts"]["literals"])
        self.assertNotEqual(example, fault)
        for lit in fault["facts"]["literals"]:
            self.assertNotIn("capability", lit)
        self.assertNotIn("capability", fault["facts"]["joined"])

    @unittest.skipUnless(
        shutil.which("cue"), "cue is absent on this runner")
    def test_cue_vet_draws_capability_absent_on_vocab_4(self):
        fault = CONTRACTS / "faults" / "vocab.4.json"
        self.assertTrue(fault.is_file(), "faults/vocab.4.json is missing")
        proc = subprocess.run(
            ["cue", "vet", "-d", "#Vocab",
             str(CONTRACTS / "cue" / "vocab.cue"), str(fault)],
            cwd=str(CONTRACTS),
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        joined = proc.stdout + proc.stderr
        self.assertTrue(
            "capability-absent" in joined.lower()
            or "vocab.capability-absent" in joined
            or "_has_capability" in joined,
            joined,
        )

    def test_vet_py_draws_capability_absent_on_vocab_4(self):
        # Run against a copy: vet.py writes packets and obs/ in cwd.
        self.assertTrue(VET.is_file(), "contracts/vet.py is missing")
        tmp = Path(tempfile.mkdtemp(prefix="vet-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        dest = tmp / "contracts"
        shutil.copytree(
            CONTRACTS, dest,
            ignore=shutil.ignore_patterns("__pycache__"))
        proc = subprocess.run(
            [sys.executable, str(dest / "vet.py"),
             "--root", str(support.WF_DIR),
             "--no-check-determinism"],
            cwd=str(dest),
            capture_output=True, text=True, check=False,
        )
        joined = proc.stdout + proc.stderr
        self.assertIn("vocab.capability-absent", joined)


if __name__ == "__main__":
    unittest.main()
