"""The owner's doc shelf (ops/docs/) cannot rot silently.

This file holds the map rules: every doc appears in the README index,
the index lists nothing that does not exist, and ghost links resolve.
Header rules — name, description, and every covers: path — live in the
registered doc-covers checker. Tests here import its helpers and drive
the live shelf; they are not the check.
"""

import re
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import support

CHECKS = support.WF_DIR / "checks"
if str(CHECKS) not in sys.path:
    sys.path.insert(0, str(CHECKS))
from doc_covers import (  # noqa: E402
    covers_path_errors,
    covers_paths,
    frontmatter_errors,
)

DOCS = support.WF_DIR.parents[1] / "docs"
REPO = support.WF_DIR.parents[2]
#: A fixed instant, so an age never depends on when the suite ran.
NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
README = DOCS / "README.md"


class TheShelfExists(unittest.TestCase):
    def test_the_shelf_and_its_index_exist(self):
        self.assertTrue(DOCS.is_dir(), f"{DOCS} is missing")
        self.assertTrue(README.is_file(), f"{README} is missing")
        self.assertTrue((DOCS / "TODO.md").is_file(),
                        "the to-do list is part of the shelf")
        self.assertTrue((DOCS / "tomorrow.md").is_file(),
                        "the resume point is part of the shelf")
        self.assertTrue((DOCS / "scratch").is_dir(),
                        "the informal working space is part of the shelf")

    def test_the_status_page_is_untracked_and_generated(self):
        # STATUS.md is generated on demand and never committed: a
        # committed copy is stale the moment anything moves, and a
        # tracked page invites hand-edits no banner check can catch
        # (Grok, PR #30 review). When one exists locally its FIRST
        # line must be the generator's banner — containing the word
        # "generated" somewhere is a proxy, not a check.
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "STATUS.md"],
            cwd=DOCS, capture_output=True, text=True, check=False)
        self.assertNotEqual(tracked.returncode, 0,
                            "STATUS.md must not be tracked")
        status = DOCS / "STATUS.md"
        if status.is_file():
            head = status.read_text().splitlines()[0]
            self.assertTrue(
                head.startswith("<!-- generated"),
                "a local STATUS.md must open with the generator banner")

    def test_no_doc_links_to_a_missing_file(self):
        # Every relative .md link in every shelf doc must resolve.
        # STATUS.md is the one exemption: generated on demand, its
        # absence is the normal state in a fresh checkout.
        errors = ghost_link_errors(DOCS)
        self.assertFalse(errors, "; ".join(errors))


MD_LINK = (r"\]\(([\w./-]+\.md)(?:[#?][^\s)]*)?"
           r"(?:\s+\"[^\"]*\")?\)")


def ghost_link_errors(root):
    """The production ghost-link walk — driven on the live shelf by
    the class test and on a planted shelf by the self-test, so a
    call site cannot quietly swap MD_LINK for a narrower copy
    (Grok, PR #30 round four)."""
    errors = []
    for doc in sorted(root.rglob("*.md")):
        for target in re.findall(MD_LINK, doc.read_text()):
            if Path(target).name == "STATUS.md":
                continue
            if not (doc.parent / target).is_file():
                errors.append(f"{doc.name} links to missing {target}")
    return errors


def index_errors(readme_text, present):
    """Both directions of the index agreement, from the Index section
    ALONE — a doc linked only in prose is unindexed."""
    if "## Index" not in readme_text:
        return ["the README lost its Index"]
    section = readme_text.split("## Index", 1)[1].split("\n## ", 1)[0]
    linked = set(re.findall(MD_LINK, section))
    linked -= EveryDocIsIndexedAndFrontmattered.INFORMAL
    errors = []
    if present - linked:
        errors.append(f"unindexed docs: {sorted(present - linked)}")
    if linked - present:
        errors.append(f"the index lists ghosts: {sorted(linked - present)}")
    return errors


def shelf_docs(root, informal):
    # TODO.md and scratch/ are deliberately rule-free: the shelf's
    # discipline is for reference docs, not for thinking out loud.
    # Recursive on purpose, and the informal exemption applies at the
    # TOP LEVEL only — guides/README.md is a doc, not a free pass
    # (Grok, PR #30 rounds one and two).
    return sorted(
        p for p in root.rglob("*.md")
        if "scratch" not in p.relative_to(root).parts[:-1]
        and not (p.parent == root and p.name in informal))


class EveryDocIsIndexedAndFrontmattered(unittest.TestCase):
    INFORMAL: frozenset = frozenset(
        {"README.md", "TODO.md", "STATUS.md", "tomorrow.md"})

    def docs(self):
        return shelf_docs(DOCS, self.INFORMAL)

    def test_every_doc_has_name_and_description_frontmatter(self):
        for doc in self.docs():
            with self.subTest(doc=doc.name):
                errors = frontmatter_errors(doc.read_text(), doc.name)
                self.assertFalse(errors, "; ".join(errors))

    def test_the_index_and_the_shelf_agree_both_ways(self):
        present = {str(d.relative_to(DOCS)) for d in self.docs()}
        errors = index_errors(README.read_text(), present)
        self.assertFalse(errors, "; ".join(errors))

    def test_every_covers_path_exists(self):
        # The live-shelf run of the registered argv: exit 0 over
        # ops/docs is the assertion that proves the wiring, not just
        # the helper.
        proc = subprocess.run(
            [sys.executable, str(CHECKS / "doc_covers.py"),
             "--root", str(REPO)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("clean", proc.stdout)


class ShelfListingSelfTests(unittest.TestCase):
    """shelf_docs and the link regex, proven against a planted shelf —
    the live shelf has no nested doc, so without these the recursion
    and top-level-only INFORMAL rules would be dead code (Grok, PR #30
    round two)."""

    def planted_shelf(self):
        import tempfile
        root = Path(tempfile.mkdtemp(prefix="shelf-self-"))
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        (root / "guides").mkdir()
        (root / "scratch").mkdir()
        (root / "README.md").write_text("top informal\n")
        (root / "guides" / "extra.md").write_text("nested doc\n")
        (root / "guides" / "README.md").write_text("nested non-exempt\n")
        (root / "scratch" / "secret.md").write_text("rule-free\n")
        planted = sorted(str(q.relative_to(root))
                         for q in root.rglob("*.md"))
        self.assertEqual(planted, ["README.md", "guides/README.md",
                                   "guides/extra.md",
                                   "scratch/secret.md"])
        return root

    def test_recursion_holds_and_informal_is_top_level_only(self):
        root = self.planted_shelf()
        informal = frozenset({"README.md"})
        found = {str(q.relative_to(root))
                 for q in shelf_docs(root, informal)}
        self.assertEqual(found, {"guides/extra.md", "guides/README.md"})

    def test_link_pattern_sees_fragments_queries_and_titles(self):
        # MD_LINK is the ONE production pattern (ghost-link check and
        # index parsing both use it); this drives that constant, not
        # a copy (Grok, PR #30 round three)
        text = ('[a](plain.md) [b](frag.md#part) '
                '[c](titled.md "the title") [d](query.md?raw=1)')
        self.assertEqual(re.findall(MD_LINK, text),
                         ["plain.md", "frag.md", "titled.md",
                          "query.md"])

    def test_ghost_walk_sees_every_shape_end_to_end(self):
        # drives ghost_link_errors on a planted shelf with a ghost on
        # EVERY axis a weakened walk could drop: fragment, title, and
        # query suffixes; a nested doc; and README itself (all live
        # links sit in README, so a walk that skips it passes empty)
        # — Grok, PR #30 round five
        import tempfile
        root = Path(tempfile.mkdtemp(prefix="shelf-ghost-"))
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        (root / "guides").mkdir()
        (root / "README.md").write_text(
            "readme ghost [r](gone-r.md)\n")
        (root / "a.md").write_text(
            'frag [x](gone-f.md#frag), titled [y](gone-t.md "t"),'
            " query [z](gone-q.md?raw=1)\n")
        (root / "guides" / "n.md").write_text(
            "nested ghost [n](gone-n.md)\n")
        planted = (root / "a.md").read_text()
        for marker in ("#frag", '"t"', "?raw=1"):
            self.assertIn(marker, planted)
        errors = ghost_link_errors(root)
        reported = "\n".join(errors)
        for ghost in ("gone-r.md", "gone-f.md", "gone-t.md",
                      "gone-q.md", "gone-n.md"):
            self.assertIn(ghost, reported,
                          f"the walk missed the {ghost} shape")
        for ghost in ("gone-r", "gone-f", "gone-t", "gone-q"):
            (root / f"{ghost}.md").write_text("now present\n")
        (root / "guides" / "gone-n.md").write_text("now present\n")
        self.assertFalse(ghost_link_errors(root))

    def test_frontmatter_checker_rejects_the_planted_shapes(self):
        # drives frontmatter_errors itself: an unterminated block
        # with name:/description: in the BODY, a missing key, and a
        # clean doc (Codex round two; Grok round three)
        unterminated = "---\nname: x\ndescription: y\nno closing"
        self.assertEqual(unterminated.count("---"), 1)
        self.assertTrue(frontmatter_errors(unterminated, "t.md"))
        keyless = "---\ndescription: only\n---\nbody\n"
        self.assertTrue(frontmatter_errors(keyless, "t.md"))
        nameless = "---\nname: only\n---\nbody\n"
        self.assertTrue(frontmatter_errors(nameless, "t.md"),
                        "the description branch must be pinned too")
        clean = "---\nname: x\ndescription: y\n---\nbody\n"
        self.assertFalse(frontmatter_errors(clean, "t.md"))

    def test_index_checker_refuses_prose_only_links(self):
        # drives index_errors with a README whose doc link sits in
        # prose above the Index — the live README has no such case,
        # so without this the section-scoping is dead code (Grok,
        # PR #30 round three)
        readme = ("Intro prose linking [t](telemetry.md).\n\n"
                  "## Index\n\n- [d](DECISIONS.md) — decisions\n")
        errors = index_errors(readme, {"telemetry.md", "DECISIONS.md"})
        self.assertEqual(len(errors), 1)
        self.assertIn("telemetry.md", errors[0])
        self.assertFalse(
            index_errors(readme, {"DECISIONS.md"}),
            "the indexed doc alone must satisfy the agreement")

    def test_covers_paths_must_exist(self):
        missing = (
            "---\nname: x\ndescription: y\n"
            "covers:\n  - no/such/path.py\n---\nbody\n"
        )
        self.assertIn("no/such/path.py", covers_paths(missing))
        errors = covers_path_errors(missing, "t.md", DOCS)
        self.assertTrue(errors)
        self.assertTrue(any("no/such/path.py" in err for err in errors))
        inline = "---\nname: x\ndescription: y\ncovers: [ops/docs/]\n---\n"
        self.assertEqual(covers_paths(inline), ["ops/docs/"])
        self.assertFalse(covers_path_errors(inline, "t.md", REPO))


class RefreshRunBehaviour(unittest.TestCase):
    def refresh(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "docs_refresh", DOCS / "refresh.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_main_writes_the_banner_and_labels_usage_honestly(self):
        # Executed against a patched module, so the banner and the
        # usage label are pinned even though CI has no local
        # STATUS.md to inspect (Grok, PR #30 round two).
        import tempfile
        module = self.refresh()
        tmp = Path(tempfile.mkdtemp(prefix="refresh-main-"))
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", str(tmp)], check=False))
        calls = []

        def fake_run(*argv, label=None):
            calls.append((argv, label))
            return "canned"

        module.DOCS = tmp
        module.run = fake_run
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)
        status = (tmp / "STATUS.md").read_text()
        self.assertTrue(status.startswith("<!-- generated"),
                        "main() must open STATUS.md with the banner")
        usage_calls = [(argv, label) for argv, label in calls
                       if any("usage.py" in str(part) for part in argv)]
        self.assertEqual(len(usage_calls), 1)
        self.assertEqual(usage_calls[0][1], "usage.py",
                         "the usage invocation must carry its honest label")

    def test_the_repo_filter_is_derived_never_hardcoded(self):
        # replacing str(REPO) with a literal path is the regression
        # Codex caught at fcbc588; patching REPO to a sentinel proves
        # the call site reads the module value (Grok, round three)
        import contextlib
        import io
        import tempfile
        module = self.refresh()
        tmp = Path(tempfile.mkdtemp(prefix="refresh-repo-"))
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", str(tmp)], check=False))
        sentinel = tmp / "sentinel-checkout"
        calls = []

        def fake_run(*argv, label=None):
            calls.append(argv)
            return "canned"

        module.DOCS = tmp
        module.REPO = sentinel
        module.run = fake_run
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)
        usage_calls = [argv for argv in calls
                       if any("usage.py" in str(part) for part in argv)]
        self.assertEqual(len(usage_calls), 1)
        argv = usage_calls[0]
        self.assertIn("--repo", argv)
        self.assertEqual(argv[argv.index("--repo") + 1], str(sentinel))

    def test_a_failing_tool_is_unavailable_not_empty(self):
        # only the OSError path was pinned; deleting the returncode
        # branch made a failing gh render as blank (Grok, round three)
        self.assertEqual(self.refresh().run("false"),
                         "(unavailable: false)")
        self.assertEqual(self.refresh().run("echo", "-n", "hi"), "hi")

    def test_a_missing_binary_is_unavailable_not_a_crash(self):
        # A checkout without gh must still regenerate the rest of the
        # page (Grok, PR #30 review: FileNotFoundError killed the run
        # and left the stale page in place).
        result = self.refresh().run("definitely-missing-billwurtz-xyz")
        self.assertEqual(
            result, "(unavailable: definitely-missing-billwurtz-xyz)")

    def test_the_unavailable_label_names_the_tool_not_the_interpreter(self):
        result = self.refresh().run(
            "definitely-missing-billwurtz-xyz", label="usage.py")
        self.assertEqual(result, "(unavailable: usage.py)")


class ToolAuditBehaviour(unittest.TestCase):
    """The shelf's second generator, whose subject is outside the repo.

    `refresh.py` reports on state a command can re-derive locally.
    This one reports on external registries, so its whole risk is the
    difference between "the registry said no" and "we could not ask" —
    and a run that renders the second as the first would launder a
    network outage into a clean bill of health.
    """

    def load_audit(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "docs_tool_audit", DOCS / "tool-audit.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def audit(self):
        module = self.load_audit()
        module.PACE = 0
        return module

    ROSTER = (("S", (("t", "a-crate", "o/r", "watch", "why"),)),)

    def measure(self, module, reply):
        return module.audit(roster=self.ROSTER, fetch=lambda url: reply,
                            now=NOW, pace=0)

    def test_a_404_is_absent_and_a_transport_failure_is_unreachable(self):
        module = self.audit()
        absent_reply = module.Reply(module.ABSENT)
        absent = self.measure(module, absent_reply)[0][1][0]
        self.assertEqual(absent["crate"]["state"], module.ABSENT)
        self.assertEqual(absent["repo"]["state"], module.ABSENT)
        blind_reply = module.Reply(module.UNREACHABLE)
        blind = self.measure(module, blind_reply)[0][1][0]
        self.assertEqual(blind["crate"]["state"], module.UNREACHABLE)
        self.assertEqual(blind["repo"]["state"], module.UNREACHABLE)

    def test_a_reply_that_is_not_the_expected_shape_is_unreachable(self):
        # A proxy's HTML error page parses as neither. Reporting that
        # as ABSENT would invent a finding about the name.
        module = self.audit()
        reply = module.Reply(module.OK, {"unexpected": True})
        row = self.measure(module, reply)[0][1][0]
        self.assertEqual(row["crate"]["state"], module.UNREACHABLE)

    def test_fetch_tags_registry_404_documents_as_absent(self):
        # Classification fakes do not drive _fetch. Exercise its
        # HTTPError branch with each registry's actual not-found shape.
        import io
        from unittest import mock
        module = self.audit()
        cases = (
            ("https://crates.io/api/v1/crates/missing",
             b'{"errors":[{"detail":"Not Found"}]}'),
            ("https://api.github.com/repos/o/missing",
             b'{"message":"Not Found"}'),
        )
        for url, payload in cases:
            with self.subTest(url=url):
                error = module.urllib.error.HTTPError(
                    url, 404, "Not Found", {}, io.BytesIO(payload))
                with mock.patch.object(
                        module.urllib.request, "urlopen",
                        side_effect=error):
                    reply = module._fetch(url)
                self.assertEqual(reply.state, module.ABSENT)
                self.assertIsInstance(reply.body, dict)

    def test_fetch_treats_an_html_404_as_unreachable(self):
        # A proxy can attach a registry's 404 status to its own HTML.
        # That is an outage, not evidence that the tool name is absent.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://crates.io/api/v1/crates/a-crate"
        error = module.urllib.error.HTTPError(
            url, 404, "Not Found", {},
            io.BytesIO(b"<html>captive portal</html>"))
        with mock.patch.object(
                module.urllib.request, "urlopen", side_effect=error):
            reply = module._fetch(url)
        self.assertEqual(reply, module.Reply(module.UNREACHABLE))

    def test_fetch_treats_an_integer_404_body_as_unreachable(self):
        # A successful HTTP response is not a registry answer unless
        # its JSON body is an object; its Python type cannot be a tag.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://crates.io/api/v1/crates/a-crate"
        with mock.patch.object(
                module.urllib.request, "urlopen",
                return_value=io.BytesIO(b"404")):
            reply = module._fetch(url)
        self.assertEqual(reply, module.Reply(module.UNREACHABLE))

    def test_fetch_treats_non_404_http_errors_as_unreachable(self):
        # Authentication, throttling, and server failures say nothing
        # about whether the requested registry name exists.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://api.github.com/repos/o/r"
        for status in (403, 429, 500, 503):
            with self.subTest(status=status):
                error = module.urllib.error.HTTPError(
                    url, status, "failure", {}, io.BytesIO(b"{}"))
                with mock.patch.object(
                        module.urllib.request, "urlopen",
                        side_effect=error):
                    reply = module._fetch(url)
                self.assertEqual(
                    reply, module.Reply(module.UNREACHABLE))

    def test_a_throttled_403_carrying_a_message_is_still_unreachable(self):
        # GitHub answers a rate limit with 403 and a body that looks
        # exactly like its not-found shape: {"message": "API rate limit
        # exceeded ..."}. The status check is what keeps the two apart,
        # and the 403 fixture above uses an EMPTY object, so deleting
        # that check was a no-op for it — a mutation run found the gap.
        # Rendering a throttle as "this repository does not exist" is
        # the invented-absence failure in its most likely real form.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://api.github.com/repos/o/r"
        body = b'{"message": "API rate limit exceeded for 1.2.3.4."}'
        error = module.urllib.error.HTTPError(
            url, 403, "rate limited", {}, io.BytesIO(body))
        with mock.patch.object(module.urllib.request, "urlopen",
                               side_effect=error):
            reply = module._fetch(url)
        self.assertEqual(reply, module.Reply(module.UNREACHABLE))

    def test_a_proxy_404_shaped_like_the_registrys_is_unreachable(self):
        # Key PRESENCE was the test, so a JSON-speaking proxy answering
        # {"message": "blocked by proxy"} had GitHub's not-found shape
        # and was reported as an absence — recreating the exact false
        # finding this file exists to prevent (Codex, PR #39). The value
        # has to match, not just the key.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://api.github.com/repos/o/r"
        error = module.urllib.error.HTTPError(
            url, 404, "not found", {},
            io.BytesIO(b'{"message":"blocked by proxy"}'))
        with mock.patch.object(module.urllib.request, "urlopen",
                               side_effect=error):
            reply = module._fetch(url)
        self.assertEqual(reply, module.Reply(module.UNREACHABLE))

    def test_a_404_from_a_host_we_do_not_know_is_unreachable(self):
        # Only the two registries have a recognised not-found shape.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://evil.example/repos/o/r"
        error = module.urllib.error.HTTPError(
            url, 404, "not found", {}, io.BytesIO(b'{"message":"Not Found"}'))
        with mock.patch.object(module.urllib.request, "urlopen",
                               side_effect=error):
            reply = module._fetch(url)
        self.assertEqual(reply, module.Reply(module.UNREACHABLE))

    def test_a_crates_404_needs_error_details_not_just_the_key(self):
        import io
        from unittest import mock
        module = self.audit()
        url = "https://crates.io/api/v1/crates/x"
        for body, want in ((b'{"errors":[{"detail":"crate `x` does not exist"}]}',
                            module.ABSENT),
                           (b'{"errors":["nope"]}', module.UNREACHABLE),
                           (b'{"errors":[]}', module.UNREACHABLE)):
            with self.subTest(body=body):
                error = module.urllib.error.HTTPError(
                    url, 404, "not found", {}, io.BytesIO(body))
                with mock.patch.object(module.urllib.request, "urlopen",
                                       side_effect=error):
                    self.assertEqual(module._fetch(url).state, want)

    def test_a_404_detail_the_registry_never_wrote_is_unreachable(self):
        # Checking that `detail` is a STRING stopped one step short:
        # a proxy answering {"detail": "blocked by proxy"} had the
        # registry's shape exactly, and its refusal was reported as a
        # finding about the NAME (Codex, PR #39 round two).
        import io
        from unittest import mock
        module = self.audit()
        url = "https://crates.io/api/v1/crates/x"
        cases = (
            (b'{"errors":[{"detail":"blocked by proxy"}]}', module.UNREACHABLE),
            (b'{"errors":[{"detail":"crate `y` does not exist"}]}',
             module.UNREACHABLE),
            # Both directions: the registry's real answers still read as
            # an absence, or the guard would trade a false finding for a
            # false outage.
            (b'{"errors":[{"detail":"Not Found"}]}', module.ABSENT),
            (b'{"errors":[{"detail":"crate `x` does not exist"}]}',
             module.ABSENT),
        )
        for body, want in cases:
            with self.subTest(body=body):
                error = module.urllib.error.HTTPError(
                    url, 404, "not found", {}, io.BytesIO(body))
                with mock.patch.object(module.urllib.request, "urlopen",
                                       side_effect=error):
                    self.assertEqual(module._fetch(url).state, want)

    def test_a_report_built_from_a_dirty_generator_says_so(self):
        # rev-parse answers the same SHA whether or not the generator
        # has uncommitted edits, so the report named a commit whose
        # tree cannot reproduce it (Codex, PR #39 round two).
        from unittest import mock
        module = self.audit()
        seen = []

        def fake_git(*argv):
            seen.append(argv)
            if "rev-parse" in argv:
                return "abc1234"
            return fake_git.status

        for status, want in ((" M ops/docs/tool-audit.py", "abc1234-dirty"),
                             ("", "abc1234")):
            with self.subTest(status=status):
                seen.clear()
                fake_git.status = status
                with mock.patch.object(module, "git", fake_git):
                    self.assertEqual(module.head_stamp(), want)
                # The scope is the decision, so it is pinned: dirt is
                # asked about THIS file, not the whole worktree, because
                # the roster and the generator are both in it.
                asked = [a for a in seen if "status" in a]
                self.assertEqual(len(asked), 1, seen)
                self.assertEqual(asked[0][-1], "ops/docs/tool-audit.py")

    def test_a_stamp_with_no_git_does_not_become_dirty(self):
        # git() reports its own failure as a string. Concatenating
        # "-dirty" onto it would turn "we could not ask" into a claim.
        from unittest import mock
        module = self.audit()
        with mock.patch.object(module, "git",
                               lambda *a: module.UNAVAILABLE):
            self.assertEqual(module.head_stamp(), module.UNAVAILABLE)

    def test_an_incomplete_success_document_is_unreachable(self):
        # A 200 whose crate object lacks the figure fields was filling
        # the gaps with 0 and None — fabricating measurements a reader
        # is asked to judge (Codex, PR #39).
        module = self.audit()
        row = module.crate_row(
            "x", lambda url: module.Reply(module.OK, {"crate": {}}), NOW)
        self.assertEqual(row["state"], module.UNREACHABLE)
        repo = module.repo_row(
            "o/r", lambda url: module.Reply(module.OK, {"full_name": "o/r"}),
            NOW)
        self.assertEqual(repo["state"], module.UNREACHABLE)

    def test_a_genuinely_zero_download_crate_is_still_ok(self):
        # Presence is the test, not truth: a brand-new crate has 0
        # downloads and must not be mistaken for an incomplete answer.
        module = self.audit()
        body = {"crate": {"max_version": "0.1.0", "downloads": 0,
                          "updated_at": "2026-08-01T00:00:00Z",
                          "repository": ""}}
        row = module.crate_row(
            "x", lambda url: module.Reply(module.OK, body), NOW)
        self.assertEqual(row["state"], module.OK)
        self.assertEqual(row["downloads"], 0)

    def test_a_404_carrying_json_that_is_not_a_registry_error_is_unreachable(
            self):
        # The shape check earns its place only against a 404 whose body
        # PARSES: an HTML 404 never reaches it, because json.load fails
        # first. A JSON body from something that is not the registry
        # says nothing about the name.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://crates.io/api/v1/crates/whatever"
        error = module.urllib.error.HTTPError(
            url, 404, "not found", {}, io.BytesIO(b'{"detail": "blocked"}'))
        with mock.patch.object(module.urllib.request, "urlopen",
                               side_effect=error):
            reply = module._fetch(url)
        self.assertEqual(reply, module.Reply(module.UNREACHABLE))

    #: A complete crate document; each case below breaks exactly ONE
    #: field, so a rejection can only be that field's doing.
    GOOD_CRATE = {"max_version": "1.2.3", "downloads": 7,
                  "updated_at": "2026-08-01T00:00:00Z",
                  "repository": "https://example.test/o/c"}
    GOOD_REPO = {"full_name": "o/r", "stargazers_count": 9,
                 "pushed_at": "2026-08-22T00:00:00+00:00",
                 "archived": False}

    def test_a_present_but_unreadable_value_is_not_a_measurement(self):
        # Round three of the same class on this file: the key is
        # present, its type was checked, and the VALUE was not. An
        # all-null document rendered as `0 downloads, vNone` — figures
        # a reader is asked to judge, invented here (Codex, PR #39).
        module = self.audit()
        broken = {
            "max_version": [None, "", "   ", 7],
            "downloads": [None, "12", -1, True, 1.5],
            "updated_at": [None, "not-a-date", 20260801,
                           "2026-08-01T00:00:00"],   # naive: no offset
            "repository": [7, []],
        }
        for field, values in broken.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    body = {"crate": dict(self.GOOD_CRATE, **{field: value})}
                    row = module.crate_row(
                        "x", lambda url, body=body: module.Reply(module.OK, body), NOW)
                    self.assertEqual(row["state"], module.UNREACHABLE)

    def test_the_repository_side_is_held_to_the_same_standard(self):
        module = self.audit()
        broken = {
            "full_name": [None, "", 7],
            "stargazers_count": [None, "9", -1, True],
            "pushed_at": [None, "not-a-date", "2026-08-22T00:00:00"],
            "archived": [None, "yes", 1],
        }
        for field, values in broken.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    body = dict(self.GOOD_REPO, **{field: value})
                    row = module.repo_row(
                        "o/r", lambda url, body=body: module.Reply(module.OK, body), NOW)
                    self.assertEqual(row["state"], module.UNREACHABLE)

    def test_the_documents_that_must_still_be_measurements(self):
        # The twins. A guard that turns a real answer into an outage
        # trades one false report for another, and this is the whole
        # list of legitimate shapes the guards above must not catch.
        module = self.audit()
        ok = [
            ("zero downloads", {"downloads": 0}),
            ("a 0.x version", {"max_version": "0.0.0"}),
            ("no repository named", {"repository": None}),
            ("an offset spelled +00:00",
             {"updated_at": "2026-08-01T00:00:00+00:00"}),
        ]
        for label, change in ok:
            with self.subTest(crate=label):
                body = {"crate": dict(self.GOOD_CRATE, **change)}
                row = module.crate_row(
                    "x", lambda url, body=body: module.Reply(module.OK, body), NOW)
                self.assertEqual(row["state"], module.OK)
        for label, change in (("no stars", {"stargazers_count": 0}),
                              ("archived absent", {"archived": None})):
            with self.subTest(repo=label):
                body = dict(self.GOOD_REPO, **change)
                if change.get("archived", False) is None:
                    del body["archived"]
                row = module.repo_row(
                    "o/r", lambda url, body=body: module.Reply(module.OK, body), NOW)
                self.assertEqual(row["state"], module.OK)

    def test_no_registry_answer_can_raise_out_of_a_row(self):
        # The blast radius is the point: a raise inside a row builder
        # aborts the WHOLE audit, so a run against one odd crate loses
        # every other row too. `_age` used to parse, and did both.
        module = self.audit()
        for body in ({"crate": {"max_version": "1", "downloads": 1,
                                "updated_at": "2026-13-45T99:99:99"}},
                     {"crate": "not a dict"},
                     {"crate": None},
                     {}):
            with self.subTest(body=body):
                row = module.crate_row(
                    "x", lambda url, body=body: module.Reply(module.OK, body), NOW)
                self.assertEqual(row["state"], module.UNREACHABLE)

    def test_a_404_detail_that_cannot_be_hashed_is_unreachable(self):
        # The value check added in round two tested membership of a
        # SET, so a non-hashable `detail` raised TypeError — and that
        # call sits outside `_fetch`'s except, so it aborted the run.
        import io
        from unittest import mock
        module = self.audit()
        url = "https://crates.io/api/v1/crates/x"
        body = b'{"errors":[{"detail":["blocked","by","proxy"]}]}'
        error = module.urllib.error.HTTPError(
            url, 404, "not found", {}, io.BytesIO(body))
        with mock.patch.object(module.urllib.request, "urlopen",
                               side_effect=error):
            self.assertEqual(module._fetch(url).state, module.UNREACHABLE)

    def test_successful_registry_documents_pin_the_report_fields(self):
        # Without one complete successful document, renaming the
        # registry wrappers or value fields leaves every failure test green.
        module = self.audit()
        crate_document = {
            "crate": {
                "max_version": "9.8.7",
                "updated_at": "2026-08-20T12:00:00+00:00",
                "downloads": 1234567,
                "repository": "https://example.test/owner/crate",
            },
        }
        repo_document = {
            "full_name": "owner/repository",
            "stargazers_count": 4321,
            "pushed_at": "2026-08-21T12:00:00+00:00",
            "archived": True,
        }

        def fetch(url):
            # The HOST, not a substring of the URL. `"crates.io" in url`
            # is true of `https://evil.test/crates.io/x` too, and a fake
            # that dispatches more loosely than `_fetch` does — which
            # keys `NOT_FOUND` on `urlsplit(url).netloc` — is a fake that
            # cannot reproduce the thing it stands in for. Flagged by
            # code scanning as py/incomplete-url-substring-sanitization.
            host = module.urllib.parse.urlsplit(url).netloc
            body = crate_document if host == "crates.io" else repo_document
            return module.Reply(module.OK, body)

        row = module.audit(
            roster=self.ROSTER, fetch=fetch, now=NOW, pace=0)[0][1][0]
        self.assertEqual(row["crate"], {
            "state": module.OK,
            "version": "9.8.7",
            "released": "2d",
            "downloads": 1234567,
            "repository": "https://example.test/owner/crate",
        })
        self.assertEqual(row["repo"], {
            "state": module.OK,
            "stars": 4321,
            "pushed": "1d",
            "archived": True,
        })

    def test_reachable_counts_answers_not_rows(self):
        module = self.audit()
        unreachable = module.Reply(module.UNREACHABLE)
        absent = module.Reply(module.ABSENT)
        self.assertEqual(module.reachable(self.measure(module, unreachable)), 0)
        self.assertEqual(module.reachable(self.measure(module, absent)), 2)

    def test_a_wholly_unreachable_run_prints_no_report(self):
        # The refusal that matters: a page of UNREACHABLE rows still
        # reads as an audit at a glance, so there is no page.
        import contextlib
        import io
        module = self.audit()
        module.ROSTER = self.ROSTER
        module._fetch = lambda url: module.Reply(module.UNREACHABLE)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = module.main([])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("nothing was reachable", err.getvalue())

    def test_a_reachable_run_prints_the_report_to_stdout(self):
        import contextlib
        import io
        module = self.audit()
        module.ROSTER = self.ROSTER
        module._fetch = lambda url: module.Reply(module.ABSENT)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.main([]), 0)
        report = out.getvalue()
        self.assertIn("- crate **ABSENT**", report)
        self.assertIn("- repo **ABSENT**", report)

    def test_the_report_never_writes_a_file_to_the_shelf(self):
        # The decision this generator turns on: a committed page of
        # external version numbers rots. Nothing may land on the shelf.
        import contextlib
        import io
        module = self.audit()
        module.ROSTER = self.ROSTER
        module._fetch = lambda url: module.Reply(module.ABSENT)

        def shelf_snapshot():
            return {
                p.relative_to(DOCS): p.read_bytes() if p.is_file() else None
                for p in DOCS.rglob("*")
            }

        before = shelf_snapshot()
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            module.main([])
        self.assertEqual(shelf_snapshot(), before)

    def test_absent_and_unreachable_render_differently(self):
        module = self.audit()
        absent_reply = module.Reply(module.ABSENT)
        blind_reply = module.Reply(module.UNREACHABLE)
        absent = module.render(
            self.measure(module, absent_reply), "abc", "b", NOW)
        blind = module.render(
            self.measure(module, blind_reply), "abc", "b", NOW)
        # On the ROW, not anywhere in the page: the header explains
        # both words, so a bare assertIn is satisfied by the legend
        # whichever state the row is actually in.
        self.assertIn("- crate **ABSENT**", absent)
        self.assertNotIn("- crate **UNREACHABLE**", absent)
        self.assertIn("- crate **UNREACHABLE**", blind)
        self.assertNotIn("- crate **ABSENT**", blind)

    def test_a_non_https_url_is_refused_rather_than_opened(self):
        # urlopen honours file: and custom schemes; a roster typo must
        # not become a read of the local filesystem.
        module = self.audit()
        with self.assertRaises(ValueError):
            module._fetch("file:///etc/passwd")

    def test_registry_pace_is_at_least_one_second(self):
        # crates.io caps API clients at one request per second; making
        # the audit faster than that is a policy violation.
        module = self.load_audit()
        self.assertGreaterEqual(module.PACE, 1.0)

    def test_the_roster_is_well_formed_and_names_nothing_twice(self):
        module = self.audit()
        names, verdicts = [], set()
        for heading, entries in module.ROSTER:
            self.assertTrue(heading.strip(), "a section needs a heading")
            self.assertTrue(entries, f"section {heading!r} is empty")
            for entry in entries:
                self.assertEqual(len(entry), 5, entry)
                name, crate, repo, verdict, why = entry
                self.assertTrue(name and why, entry)
                self.assertTrue(crate or repo,
                                f"{name} names nothing to measure")
                names.append(name)
                verdicts.add(verdict)
        self.assertEqual(len(names), len(set(names)),
                         "a tool appears in two sections")
        self.assertLessEqual(
            verdicts, {"adopt", "watch", "marginal", "refuted"}, verdicts)

    def test_offline_parses_the_roster_without_reaching_the_network(self):
        import contextlib
        import io
        module = self.audit()

        def refuse(url):
            raise AssertionError("--offline must not fetch")

        module._fetch = refuse
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(module.main(["--offline"]), 0)
        self.assertIn("roster parses", out.getvalue())


if __name__ == "__main__":
    unittest.main()
