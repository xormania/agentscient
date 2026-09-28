"""A process document nobody points at is one nobody reads.

`ops/docs/` already refuses an unindexed document. `ops/process/` did
not, and the cost was measured: `cue-sys.md` recorded the full pipeline
on 2026-08-23 and the next session read `cross-review.md`, found three
roles where there are six, ran a truncated version and had to be
corrected twice. The complete answer was two directories away,
referenced by nothing but its own companion.

So both directions are held here, as the shelf holds them: every
document under `ops/process/` is named by the operating contract every
harness reads, and every process path that contract names exists.
"""

import re
import unittest

import support

REPO = support.WF_DIR.parent.parent.parent
PROCESS = REPO / "ops" / "process"
AGENTS = REPO / "AGENTS.md"

#: A path mentioned anywhere in AGENTS.md, backticked or not.
MENTION = re.compile(r"ops/process/[\w./-]*[\w/-]")


def process_docs():
    return sorted(p for p in PROCESS.rglob("*.md"))


class TheProcessIsIndexed(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PROCESS.is_dir(), f"{PROCESS} is missing")
        self.assertTrue(AGENTS.is_file(), f"{AGENTS} is missing")
        self.docs = process_docs()
        self.assertGreaterEqual(len(self.docs), 4,
                                "INVALID: too few process docs to be testing this")
        self.named = set(MENTION.findall(AGENTS.read_text(encoding="utf-8")))

    def test_every_process_document_is_named_by_the_operating_contract(self):
        for doc in self.docs:
            rel = doc.relative_to(REPO).as_posix()
            with self.subTest(doc=rel):
                self.assertIn(
                    rel, self.named,
                    f"{rel} is not named in AGENTS.md — a process document "
                    f"nobody points at is one nobody reads")

    def test_every_process_path_named_exists(self):
        for rel in sorted(self.named):
            with self.subTest(path=rel):
                self.assertTrue(
                    (REPO / rel).exists(),
                    f"AGENTS.md names {rel}, which does not exist")

    def test_the_sequence_document_is_among_them(self):
        """The one that was missing, pinned by name.

        Six stages exist and cross-review.md describes three. Without
        this, removing the sequence document would pass silently and the
        next session would rebuild it from a transcript again."""
        self.assertIn("ops/process/pipeline.md", self.named)
        self.assertTrue((PROCESS / "pipeline.md").is_file())


class TheWalkRecurses(unittest.TestCase):
    """process_docs() must recurse, or the nested documents are unindexed.

    Replacing rglob with glob drops everything under roles/ and every
    assertion above stays green: the top-level documents already satisfy
    them. The nested files are discovered here by a one-level glob, not
    by rglob, so the oracle does not share the walk under test.
    """

    def test_nested_process_documents_are_listed(self):
        nested = sorted(PROCESS.glob("*/*.md"))
        self.assertTrue(
            nested,
            "INVALID: no nested process documents — this is not testing recursion")
        listed = process_docs()
        missing = [p for p in nested if p not in listed]
        self.assertFalse(
            missing,
            "process_docs() dropped nested documents: "
            + ", ".join(p.relative_to(REPO).as_posix() for p in missing))


if __name__ == "__main__":
    unittest.main(verbosity=2)
