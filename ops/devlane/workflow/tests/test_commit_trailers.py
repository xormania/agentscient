"""A trailer git will not parse must be reported, and nothing else.

The corpus is real: measured on 2026-08-24 across `dev`,
`task/runner-slice-1` and `contracts/lift-and-enforce`, 50 of 243
commits carry a `Source:` line that `git log --format='%(trailers…)'`
cannot see. The checker was tuned against that corpus until it flagged
exactly those 50 -- 0 missed, 0 extra -- and the shapes it had to stop
flagging on the way have cases of their own below.

The first version keyed on trailer SHAPE alone. This repo's commit
subjects are `workflow: ...`, `docs: ...`, `telemetry: ...`, so a body
that quotes one is a line indistinguishable from a trailer: it flagged
187 of 243 commits, 137 of them subject prefixes. A checker that fires
on three quarters of history is one nobody reads, so precision came
before coverage and the key list became data.
"""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

CHECK = support.WF_DIR / "checks" / "commit_trailers.py"

SPLIT = """subject line

Body paragraph explaining the change.

Source: original

Co-Authored-By: A <a@x>
"""

JOINED = """subject line

Body paragraph explaining the change.

Source: original
Co-Authored-By: A <a@x>
"""


def run(*args):
    proc = subprocess.run([sys.executable, str(CHECK), *args],
                          capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout + proc.stderr


def on_message(text):
    """Write a message to a temp file and check it; prove it landed first."""
    with tempfile.NamedTemporaryFile("w", suffix=".msg", delete=False) as handle:
        handle.write(text)
        path = Path(handle.name)
    landed = path.read_text(encoding="utf-8")
    if landed != text or not landed.strip():
        raise AssertionError("INVALID fixture: the message did not land intact")
    try:
        return run("--message-file", str(path))
    finally:
        path.unlink()


def on_range(text):
    """Commit `text` in a throwaway repo and check it over a range.

    Source and Co-Authored-By are enforced only when `sha` names an
    existing commit. A one-commit repo makes `HEAD^` unresolvable, so a
    well-formed base sits underneath and the range is exactly the commit
    under test. The message is read back before the checker is asked.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        def git(*a):
            return subprocess.run(["git", *a], cwd=root, check=True,
                                  capture_output=True, text=True)
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@x")
        git("config", "user.name", "T")
        git("config", "commit.gpgsign", "false")
        (root / "f").write_text("base\n")
        git("add", "-A")
        git("commit", "-q", "--no-verify", "-m",
            "base\n\nSource: original\nCo-Authored-By: A <a@x>")
        base = git("rev-parse", "HEAD").stdout.strip()
        (root / "f").write_text("work\n")
        git("add", "-A")
        git("commit", "-q", "--no-verify", "-m", text)
        head = git("rev-parse", "HEAD").stdout.strip()
        landed = git("log", "-1", "--format=%B", head).stdout
        if landed.strip() != text.strip() or not landed.strip():
            raise AssertionError(
                "INVALID fixture: the commit message did not land intact")
        listed = git("rev-list", f"{base}..{head}").stdout.split()
        if listed != [head]:
            raise AssertionError(
                f"INVALID fixture: range must be exactly the test commit, got {listed}")
        proc = subprocess.run(
            [sys.executable, str(CHECK), "--range", f"{base}..{head}"],
            cwd=root, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr


class ItFires(unittest.TestCase):
    def test_a_split_trailer_block_is_reported(self):
        code, out = on_message(SPLIT)
        self.assertEqual(code, 1, out)
        self.assertIn("Source: original", out)

    def test_it_names_the_line(self):
        code, out = on_message(SPLIT)
        self.assertEqual(code, 1, out)
        self.assertIn("line 5", out)

    def test_every_orphaned_known_key_is_reported(self):
        message = ("subject\n\nbody\n\nSource: original\n"
                   "Reviewed-by: B <b@x>\n\nCo-Authored-By: A <a@x>\n")
        code, out = on_message(message)
        self.assertEqual(code, 1, out)
        self.assertIn("Source:", out)
        self.assertIn("Reviewed-by:", out)


class ItStaysQuiet(unittest.TestCase):
    def test_a_joined_block_passes(self):
        code, out = on_message(JOINED)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)

    def test_the_two_fixtures_differ_only_by_the_blank_line(self):
        """The positive control's own control: if these ever converge the
        pair proves nothing, and both cases would pass for free."""
        self.assertEqual(SPLIT.replace("\n\nCo-Authored-By", "\nCo-Authored-By"),
                         JOINED)

    def test_a_real_merge_needs_no_source(self):
        """Merges carry no Source — every merge on dev is a generated
        "Merge pull request #N" with no trailers at all — so they must be
        exempt or every PR merge fails. Exemption is read from PARENTAGE,
        so this builds an actual merge rather than a message. The same
        exemption covers Co-Authored-By; non-merge commits in the range
        carry both trailers so a failure is about the merge."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*a):
                return subprocess.run(["git", *a], cwd=root, check=True,
                                      capture_output=True, text=True)
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@x")
            git("config", "user.name", "T")
            (root / "f").write_text("a\n")
            git("add", "-A")
            git("commit", "-q", "--no-verify", "-m", "base\n\nSource: original\nCo-Authored-By: A <a@x>")
            git("checkout", "-q", "-b", "side")
            (root / "g").write_text("b\n")
            git("add", "-A")
            git("commit", "-q", "--no-verify", "-m", "side\n\nSource: original\nCo-Authored-By: A <a@x>")
            git("checkout", "-q", "main")
            (root / "h").write_text("c\n")
            git("add", "-A")
            git("commit", "-q", "--no-verify", "-m", "main\n\nSource: original\nCo-Authored-By: A <a@x>")
            # a real merge, with a generated message carrying no trailers
            git("merge", "--no-ff", "--no-verify", "-m", "Merge branch 'side'", "side")
            head = git("rev-parse", "HEAD").stdout.strip()
            parents = git("rev-list", "--parents", "-n", "1", head).stdout.split()
            self.assertEqual(len(parents), 3, "INVALID fixture: not a merge")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--range", f"{head}^..{head}"],
                cwd=root, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_merge_SUBJECT_on_an_ordinary_commit_does_not_exempt_it(self):
        """The bypass: exemption was read off the subject, so titling any
        commit `Merge branch ...` skipped the mandatory attribution
        entirely (Codex, PR #51). Parentage is a fact; a subject is a
        claim.

        Aimed at a range: the hook no longer asks, because parentage is
        not a fact until the commit exists.
        """
        code, out = on_range("Merge branch not-really\n\nbody, no Source.\n")
        self.assertEqual(code, 1, out)
        self.assertIn("Source", out)

    def test_an_orphaned_trailer_identical_to_a_valid_one_is_reported(self):
        """Two `Source: original` lines in different blocks: the pair was
        in the parsed set, so the orphan was suppressed and a declared
        origin git cannot see reported clean (Codex, PR #51)."""
        message = ("subject\n\nbody.\n\nSource: original\n\n"
                   "Source: original\nCo-Authored-By: A <a@x>\n")
        code, out = on_message(message)
        self.assertEqual(code, 1, out)
        self.assertIn("line 5", out)

    def test_a_subject_prefix_quoted_in_the_body_is_not_a_trailer(self):
        """The 137 false positives. `workflow: ...` is trailer-shaped."""
        message = ("subject\n\nThese landed earlier:\n\n"
                   "workflow: add the export\n"
                   "telemetry: close the disable class\n"
                   "docs: rewrite the guide\n\n"
                   "Source: original\nCo-Authored-By: A <a@x>\n")
        code, out = on_message(message)
        self.assertEqual(code, 0, out)

    def test_prose_mentioning_a_trailer_is_not_a_trailer(self):
        """A commit explaining the rule must not trip the rule."""
        message = ("subject\n\n"
                   "The message carried `Source: original` one paragraph\n"
                   "too early, which is why nothing parsed it.\n\n"
                   "Source: original\nCo-Authored-By: A <a@x>\n")
        code, out = on_message(message)
        self.assertEqual(code, 0, out)

    def test_an_unknown_key_is_not_policed(self):
        """Documented trade: the list is data, so a new key is unchecked
        until added. Pinned so the trade is deliberate, not forgotten."""
        message = ("subject\n\nbody\n\nWhatever: value\n\nSource: original\n"
                   "Co-Authored-By: A <a@x>\n")
        code, out = on_message(message)
        self.assertEqual(code, 0, out)


class ItRefuses(unittest.TestCase):
    """A run that could not look must never render as a pass."""

    def test_an_empty_message_is_invalid(self):
        with tempfile.NamedTemporaryFile("w", suffix=".msg", delete=False) as handle:
            path = Path(handle.name)
        try:
            code, out = run("--message-file", str(path))
            self.assertEqual(code, 1, out)
            self.assertIn("INVALID", out)
        finally:
            path.unlink()

    def test_a_missing_message_file_is_invalid(self):
        code, out = run("--message-file", "/nonexistent/commit.msg")
        self.assertEqual(code, 1, out)
        self.assertIn("INVALID", out)

    def test_a_range_naming_no_commit_is_invalid(self):
        code, out = run("--range", "HEAD..HEAD")
        self.assertEqual(code, 1, out)
        self.assertIn("INVALID", out)

    def test_an_unresolvable_base_is_invalid(self):
        code, out = run("--since-base", "--base-ref", "refs/heads/no-such-ref")
        self.assertEqual(code, 1, out)
        self.assertIn("INVALID", out)


class TheKeyListIsTheContract(unittest.TestCase):
    @staticmethod
    def _module():
        spec = importlib.util.spec_from_file_location("commit_trailers", CHECK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_keys_the_repo_documents_are_policed(self):
        module = self._module()
        for key in ("Source", "Co-Authored-By", "Reviewed-by"):
            self.assertIn(key, module.KNOWN_KEYS,
                          f"{key} is named by CONTRIB.md but not policed")

    def test_git_is_the_oracle_not_a_parser_written_here(self):
        """The rules for a trailer are git's. A second implementation
        would drift from the first the day either changed."""
        source = CHECK.read_text(encoding="utf-8")
        self.assertIn("interpret-trailers", source)


class ShapesCodexFoundOnTheCheckerItself(unittest.TestCase):
    """Three ways this gate reported clean over a real defect.

    All verified against the checker as it stood when PR #51 opened:
    each fixture below exited 0.
    """

    def test_a_message_with_no_source_at_all_is_reported(self):
        """The check compared a raw scan against git's parse, which by
        construction can only see trailers that are THERE — so an
        ABSENT one was invisible, though CONTRIB.md requires it.

        Range mode: the hook cannot know parentage, so it does not
        enforce this. That half is pinned in TheHookDoesNotGuessParentage.
        """
        code, out = on_range("subject\n\njust a body, no trailers here.\n")
        self.assertEqual(code, 1, out)
        self.assertIn("Source", out)

    def test_an_orphaned_trailer_is_not_excused_by_a_later_valid_one(self):
        """Set membership lost the occurrence: `Source: lost-source`
        orphaned above a valid `Source: original` put the KEY in the
        parsed set and suppressed the orphan, so a declared origin git
        cannot see reported clean."""
        message = ("subject\n\nbody.\n\nSource: lost-source\n\n"
                   "Source: original\nCo-Authored-By: A <a@x>\n")
        code, out = on_message(message)
        self.assertEqual(code, 1, out)
        self.assertIn("lost-source", out)

    def test_the_range_comes_from_the_ci_event_when_there_is_one(self):
        """Hard-coding origin/dev broke on the branch it named: a push
        run for dev checks out the pushed commit AND sets origin/dev to
        it, so merge-base is HEAD, the range is empty, and the gate
        reported INVALID on every push to dev."""
        import json as _json
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*a):
                return subprocess.run(["git", *a], cwd=root, check=True,
                                      capture_output=True, text=True)
            git("init", "-q", "-b", "dev")
            git("config", "user.email", "t@x")
            git("config", "user.name", "T")
            (root / "f").write_text("a\n")
            git("add", "-A")
            git("commit", "-q", "--no-verify", "-m", "one\n\nSource: original\nCo-Authored-By: A <a@x>")
            before = git("rev-parse", "HEAD").stdout.strip()
            (root / "f").write_text("b\n")
            git("add", "-A")
            git("commit", "-q", "--no-verify", "-m", "two\n\nSource: original\nCo-Authored-By: A <a@x>")
            after = git("rev-parse", "HEAD").stdout.strip()
            git("update-ref", "refs/remotes/origin/dev", "HEAD")   # what checkout does
            self.assertEqual(git("rev-parse", "origin/dev").stdout.strip(), after,
                             "INVALID fixture: origin/dev must equal HEAD")

            proc = subprocess.run([sys.executable, str(CHECK), "--since-base"],
                                  cwd=root, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1,
                             "the fixture must reproduce the old failure")
            self.assertIn("INVALID", proc.stdout + proc.stderr)

            event = root / "event.json"
            event.write_text(_json.dumps({"before": before, "after": after}))
            env = dict(_os.environ, GITHUB_EVENT_PATH=str(event))
            ok = subprocess.run([sys.executable, str(CHECK), "--since-base"],
                                cwd=root, capture_output=True, text=True, env=env)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertIn("checked 1 message", ok.stdout)

    def test_a_new_branch_falls_back_rather_than_inventing_a_base(self):
        """An all-zero `before` means there is no prior state to diff."""
        module = TheKeyListIsTheContract._module()
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "e.json"
            event.write_text('{"before":"' + "0" * 40 + '","after":"abc"}')
            old = _os.environ.get("GITHUB_EVENT_PATH")
            _os.environ["GITHUB_EVENT_PATH"] = str(event)
            try:
                self.assertIsNone(module.range_from_event())
            finally:
                if old is None:
                    del _os.environ["GITHUB_EVENT_PATH"]
                else:
                    _os.environ["GITHUB_EVENT_PATH"] = old


class TheEventBelongsToOneRepository(unittest.TestCase):
    """An event range must not leak into a repo it does not describe.

    GITHUB_EVENT_PATH is set for every step of a CI job, including steps
    that run this checker inside a throwaway fixture repo — which is
    exactly what test_gate_binding does. That repo has none of the
    event's commits, so the derived range asked about commits that do
    not exist and refused, failing the gate binding's CLEAN arm.

    It passed locally and failed in CI, because locally the variable is
    unset. Found by CI, not by me, which is the reason this case exists.
    """

    def test_an_event_naming_foreign_commits_falls_back(self):
        import json as _json
        import os as _os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*a):
                return subprocess.run(["git", *a], cwd=root, check=True,
                                      capture_output=True, text=True)
            git("init", "-q", "-b", "dev")
            git("config", "user.email", "t@x")
            git("config", "user.name", "T")
            (root / "f").write_text("a\n")
            git("add", "-A")
            git("commit", "-q", "--no-verify", "-m", "base\n\nSource: original\nCo-Authored-By: A <a@x>")
            git("update-ref", "refs/remotes/origin/dev", "HEAD")
            (root / "f").write_text("b\n")
            git("add", "-A")
            git("commit", "-q", "--no-verify", "-m", "work\n\nSource: original\nCo-Authored-By: A <a@x>")

            # an event from some OTHER repository
            event = root / "e.json"
            event.write_text(_json.dumps({"before": "a" * 40, "after": "b" * 40}))
            self.assertNotEqual(
                git("rev-parse", "HEAD").stdout.strip(), "b" * 40,
                "INVALID fixture: the event must name commits this repo lacks")

            env = dict(_os.environ, GITHUB_EVENT_PATH=str(event))
            proc = subprocess.run([sys.executable, str(CHECK), "--since-base"],
                                  cwd=root, capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("checked 1 message", proc.stdout)


class TheHookDoesNotGuessParentage(unittest.TestCase):
    """Source and Co-Authored-By are range-only.

    At hook time the commit does not exist, so parentage is not a fact
    (Codex, PR #51 round four). The hook still catches an orphaned
    trailer, which needs only the message — that is pinned in ItFires.
    """

    def test_the_hook_does_not_require_source(self):
        code, out = on_message("subject\n\njust a body, no trailers here.\n")
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)

    def test_the_hook_does_not_require_co_authored_by(self):
        code, out = on_message("subject\n\nbody\n\nSource: original\n")
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)

    def test_the_hook_does_not_police_co_authored_by_form(self):
        """Parseability is not the requirement — but the hook is not
        the place that asks. `arbitrary` parses; a range would refuse."""
        code, out = on_message(
            "subject\n\nbody\n\nSource: original\nCo-Authored-By: arbitrary\n")
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)


class ARangeRequiresTheDocumentedAgent(unittest.TestCase):
    """AGENTS.md SS1: a specific model name and a vendor address.

    An absent Co-Authored-By was accepted, and so was
    `Co-Authored-By: arbitrary`, because only parseability was asked
    (Codex, PR #51 round five). Parseability is not the requirement.
    """

    def test_a_message_with_no_co_authored_by_is_reported(self):
        code, out = on_range("subject\n\nbody\n\nSource: original\n")
        self.assertEqual(code, 1, out)
        self.assertIn("Co-Authored-By", out)
        self.assertNotIn("not the documented form", out)

    def test_a_malformed_co_authored_by_is_reported(self):
        """`arbitrary` is a trailer git will parse. Presence is not form."""
        code, out = on_range(
            "subject\n\nbody\n\nSource: original\nCo-Authored-By: arbitrary\n")
        self.assertEqual(code, 1, out)
        self.assertIn("not the documented form", out)
        self.assertIn("arbitrary", out)

    def test_a_name_without_an_address_is_reported(self):
        code, out = on_range(
            "subject\n\nbody\n\nSource: original\n"
            "Co-Authored-By: Claude Fable 5\n")
        self.assertEqual(code, 1, out)
        self.assertIn("not the documented form", out)

    def test_a_well_formed_co_authored_by_passes(self):
        code, out = on_range(
            "subject\n\nbody\n\nSource: original\nCo-Authored-By: A <a@x>\n")
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)

    def test_one_well_formed_value_is_enough(self):
        """`any()` over the values: a malformed first line must not hide
        a well-formed second. AGENTS.md asks for a specific agent, not
        that every Co-Authored-By line be one."""
        code, out = on_range(
            "subject\n\nbody\n\nSource: original\n"
            "Co-Authored-By: arbitrary\n"
            "Co-Authored-By: A <a@x>\n")
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)

    def test_a_merge_SUBJECT_does_not_exempt_co_authored_by(self):
        """The Source bypass's twin: a merge-shaped subject with Source
        present still needs the documented agent."""
        code, out = on_range(
            "Merge branch not-really\n\nbody\n\nSource: original\n")
        self.assertEqual(code, 1, out)
        self.assertIn("Co-Authored-By", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
