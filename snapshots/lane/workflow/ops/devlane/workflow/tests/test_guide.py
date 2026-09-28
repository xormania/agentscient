"""The guide covers every app, and says only checkable things.

Teaching material rots faster than anything else in a repo, because
nothing runs it. These are the parts a test CAN hold: that each mini
app has a page, that the index and the pages agree both ways, that
every repo path a page names exists — in prose AND in the shell
blocks, since a command naming a moved script is the way these pages
go stale first — and that every relative link resolves.

The invariant AGENTS.md states about itself is checked here too — its
sentence naming the dev-lane surfaces and the vocabulary wall's
allowlist must name the same set, because the wall is what turns that
sentence into a rule.
"""

import ast
import re
import unittest

import support

REPO = support.WF_DIR.parent.parent.parent
GUIDE = REPO / "ops" / "guide"
INDEX = GUIDE / "README.md"
APPS = REPO / "ops" / "devlane"
WALL = support.WF_DIR / "checks" / "vocabulary_wall.py"

#: Any markdown link destination, fragment/query/title stripped —
#: not only .md, because a link to a directory or a script rots the
#: same way.
LINK = re.compile(r'\]\(([^)\s]+)(?:\s+"[^"]*")?\)')

#: A repo path in prose, backticked. `.git/` is included because the
#: pages talk about it; the trailing char class refuses a prefix
#: match, so `wf.py.gone` cannot pass as `wf.py`.
REPO_PATH = re.compile(r"`((?:\.dev|\.github|\.git|\.claude|\.serena)"
                       r"/[\w./-]+)`")

#: The same, unquoted inside shell blocks. It matches the WHOLE
#: token rather than a known extension: keying on `.py` let
#: `acceptance.py.gone` slip by, first as an existing prefix and
#: then — once the extension was anchored — by not matching at all,
#: which is the same silence (Codex, PR #37 audit).
COMMAND_PATH = re.compile(
    r"(?<![\w/`.])((?:\.dev|\.github|\.git|\.claude|\.serena)"
    r"/[^\s\x22\x27`)\]]+)")

#: Created at run time, so naming one is correct and asserting its
#: existence would be wrong.
RUNTIME_PATHS = frozenset({".git/claude-context-stream.jsonl"})


def pages():
    return sorted(p for p in GUIDE.glob("*.md") if p.name != "README.md")


class TheGuideCoversTheLane(unittest.TestCase):
    def test_every_mini_app_has_a_page(self):
        apps = sorted(p.name for p in APPS.iterdir()
                      if p.is_dir() and not p.name.startswith("."))
        self.assertGreaterEqual(len(apps), 4, apps)
        covered = {p.stem for p in pages()}
        for app in apps:
            with self.subTest(app=app):
                self.assertIn(
                    app, covered,
                    f"the {app} app has no page in the guide")

    def test_the_index_and_the_pages_agree_both_ways(self):
        linked = {t for t in LINK.findall(INDEX.read_text())
                  if "/" not in t}
        present = {p.name for p in pages()}
        self.assertEqual(present - linked, set(),
                         "pages the index never mentions")
        self.assertEqual(linked - present, set(),
                         "the index links pages that do not exist")

    def test_every_repo_path_a_page_names_exists(self):
        for page in [INDEX, *pages()]:
            for quoted in REPO_PATH.findall(page.read_text()):
                if quoted in RUNTIME_PATHS:
                    continue
                with self.subTest(page=page.name, path=quoted):
                    target = REPO / quoted.rstrip("/")
                    self.assertTrue(
                        target.exists(),
                        f"{page.name} names {quoted}, which does not exist")

    def test_every_path_in_a_shell_block_exists(self):
        for page in [INDEX, *pages()]:
            text = page.read_text()
            blocks = re.findall(r"```(?:sh|bash|python)?\n(.*?)```",
                                text, re.DOTALL)
            if page is not INDEX:
                # The index points; the pages teach, and a page that
                # shows nothing to run is not teaching.
                self.assertTrue(
                    blocks, f"{page.name} shows no commands at all")
            for block in blocks:
                for match in COMMAND_PATH.findall(block):
                    quoted = match.rstrip(".,;:")
                    if quoted in RUNTIME_PATHS:
                        continue
                    with self.subTest(page=page.name, path=quoted):
                        self.assertTrue(
                            (REPO / quoted).exists(),
                            f"{page.name} runs {quoted}, which does not"
                            " exist")

    def test_every_relative_link_resolves(self):
        for page in [INDEX, *pages()]:
            for raw in LINK.findall(page.read_text()):
                if raw.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target = raw.split("#")[0].split("?")[0]
                if not target:
                    continue
                with self.subTest(page=page.name, link=raw):
                    self.assertTrue(
                        (page.parent / target).resolve().exists(),
                        f"{page.name} links to missing {target}")


class TheSurfaceListsAgree(unittest.TestCase):
    def test_agents_md_names_the_walls_allowlist(self):
        # AGENTS.md says of itself: "its allowlist and this sentence
        # must name the same surfaces". The wall is what makes the
        # sentence enforceable, so a file allowed by one and not the
        # other is a rule with two different texts.
        tree = ast.parse(WALL.read_text())
        allowed = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", "") == "ALLOWED_FILES"
                            for t in node.targets)):
                allowed = tuple(ast.literal_eval(node.value))
        self.assertIsNotNone(allowed)

        sentence = (REPO / "AGENTS.md").read_text()
        self.assertIn("stays on dev-lane surfaces", sentence)
        start = sentence.index("stays on dev-lane surfaces")
        # Paragraph-terminated, not a character window: a later
        # sentence in this section names compose-term homes, and
        # must not leak into the allowlist comparison.
        block = sentence[start:].split("\n\n", 1)[0]
        prefixes = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", "") == "ALLOWED_PREFIXES"
                            for t in node.targets)):
                prefixes = tuple(ast.literal_eval(node.value))
        self.assertIsNotNone(prefixes)

        # A real set comparison, both directions. Substring matching
        # was not one: `.git/` "appeared" in the sentence because
        # `.github/` contains it, and a surface named only in prose
        # was never noticed at all (Codex, PR #37 audit).
        wall = {name.rstrip("/") for name in (*allowed, *prefixes)}
        wall.discard("AGENTS.md")   # the sentence calls it "this file"

        # Backticked tokens in the sentence that are shaped like a
        # file or a directory. The sentence also names dev-lane commit
        # messages, which are not a tree surface and cannot appear in
        # either tuple, so only path-shaped tokens are compared.
        quoted = set(re.findall(r"`([^`]+)`", block))
        named = {tok.rstrip("/") for tok in quoted
                 if tok.startswith(".") or tok.endswith((".md", ".toml"))}

        self.assertEqual(
            wall - named, set(),
            "the wall allows surfaces AGENTS.md does not name")
        self.assertEqual(
            named - wall, set(),
            "AGENTS.md names surfaces the wall does not allow")

    def test_agents_md_names_the_service_homes(self):
        # Second paragraph of the same section: the compose term is
        # compose's word, capability is the framework's, and the
        # carve-outs named in backticks are SERVICE_HOMES, both
        # directions. Delimited by blank lines / the next heading,
        # not a character window.
        agents = (REPO / "AGENTS.md").read_text()
        start_mark = "This file is dev-lane surface"
        self.assertIn(start_mark, agents)
        section = agents.split("## Attribution", 1)[0]
        section = section[section.index(start_mark):]
        paragraphs = [
            p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
        homes_para = None
        for para in paragraphs:
            if ("compose" in para.lower()
                    and "capability" in para.lower()):
                homes_para = para
                break
        self.assertIsNotNone(
            homes_para,
            "AGENTS.md has no paragraph naming compose and capability")
        tree = ast.parse(WALL.read_text())
        homes = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", "") == "SERVICE_HOMES"
                            for t in node.targets)):
                homes = tuple(ast.literal_eval(node.value))
        self.assertIsNotNone(homes)
        quoted = set(re.findall(r"`([^`]+)`", homes_para))
        named = {tok.rstrip("/") for tok in quoted
                 if tok.startswith(".")}
        wall = {name.rstrip("/") for name in homes}
        self.assertEqual(
            wall - named, set(),
            "the wall allows compose-term homes AGENTS.md does not name")
        self.assertEqual(
            named - wall, set(),
            "AGENTS.md names compose-term homes the wall does not allow")

    def test_each_named_service_home_exists(self):
        tree = ast.parse(WALL.read_text())
        homes = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", "") == "SERVICE_HOMES"
                            for t in node.targets)):
                homes = tuple(ast.literal_eval(node.value))
        self.assertIsNotNone(homes, "SERVICE_HOMES is missing from the wall")
        for home in homes:
            with self.subTest(home=home):
                target = REPO / home.rstrip("/")
                self.assertTrue(
                    target.exists(),
                    f"{home} is a named home but does not exist")

    def test_onboarding_names_the_second_direction(self):
        # Plan §3: the lane-rule paragraph names the second direction
        # (compose term lives under `ops/devlane/infra/`; capability is the
        # framework's). Delimited by the next heading, not line numbers.
        text = (REPO / ".dev" / "ONBOARDING.md").read_text()
        start_mark = "The lane rule"
        end_mark = "Don't conflate"
        self.assertIn(start_mark, text)
        self.assertIn(end_mark, text)
        block = text[text.index(start_mark):text.index(end_mark)]
        self.assertIn("vocabulary_wall.py", block)
        self.assertIn("ops/devlane/infra/", block)
        self.assertIn("capability", block.lower())
        self.assertIn("compose", block.lower())


if __name__ == "__main__":
    unittest.main()

