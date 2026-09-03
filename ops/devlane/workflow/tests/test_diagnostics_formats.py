"""SARIF and JUnit: whole documents, where the reader expected lines.

`diagnostics.py` reads one JSON record per line, which is what rustc
and cargo emit. The two formats Rust adds are not line-oriented at
all — SARIF is a single JSON document (clippy, and every scanner that
speaks GitHub code-scanning) and JUnit is XML (what `cargo nextest`
writes). Fed to a line walker, a SARIF file full of errors is N
unparsed lines and zero findings, which is the silent pass this whole
check exists to refuse.

Each format carries a "nobody looked" case that is NOT the same as
"looked and found nothing", and those are the load-bearing tests:

  * SARIF — `runs: []` means no tool ran. A run whose `results` are
    empty means one ran and found nothing. Only the second is clean.
  * JUnit — zero test cases is the "NO TESTS RAN" state that
    `ops/process/tdd.md` says is not a red. It must not be a pass
    either.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

CHECK = support.WF_DIR / "checks" / "diagnostics.py"

SARIF_SCHEMA = ("https://raw.githubusercontent.com/oasis-tcs/sarif-spec"
                "/master/Schemata/sarif-schema-2.1.0.json")


def sarif(results=None, runs=None, rules=None):
    """A SARIF 2.1.0 log. `runs=[]` is a tool that never ran."""
    import json
    if runs is None:
        run = {"tool": {"driver": {"name": "clippy", "rules": rules or []}},
               "results": results or []}
        runs = [run]
    return json.dumps({"$schema": SARIF_SCHEMA, "version": "2.1.0",
                       "runs": runs})


def result(level=None, rule="clippy::needless_range_loop", text="m"):
    out = {"ruleId": rule, "message": {"text": text},
           "locations": [{"physicalLocation": {
               "artifactLocation": {"uri": "src/lib.rs"},
               "region": {"startLine": 4}}}]}
    if level is not None:
        out["level"] = level
    return out


def junit(cases="", suite_attrs="", wrap=True):
    inner = f'<testsuite name="s" {suite_attrs}>{cases}</testsuite>'
    body = f"<testsuites>{inner}</testsuites>" if wrap else inner
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def case(name="t", inner=""):
    return f'<testcase name="{name}" classname="c">{inner}</testcase>'


class FormatCase(unittest.TestCase):
    def emit(self, payload):
        """A producer that writes `payload` verbatim and exits 0."""
        root = Path(tempfile.mkdtemp(prefix="diag-fmt-"))
        self.addCleanup(shutil.rmtree, root, True)
        path = root / "payload.txt"
        path.write_text(payload)
        return ["python3", "-c",
                f"import sys;sys.stdout.write(open({str(path)!r}).read())"]

    def emit_both(self, payload, noise):
        """stdout carries the document, stderr carries progress chatter.

        This is what a real producer does — `cargo clippy
        --message-format=sarif` writes the log to stdout while cargo
        writes "Compiling foo v0.1" to stderr. Every fixture in the
        first version of this file wrote stdout ONLY, so the check
        concatenating the two streams before parsing was invisible to
        all 14 planted mutants (Codex, PR review of 3453dc1).
        """
        root = Path(tempfile.mkdtemp(prefix="diag-fmt-"))
        self.addCleanup(shutil.rmtree, root, True)
        out, err = root / "out.txt", root / "err.txt"
        out.write_text(payload)
        err.write_text(noise)
        return ["python3", "-c",
                (f"import sys;sys.stdout.write(open({str(out)!r}).read());"
                 f"sys.stderr.write(open({str(err)!r}).read())")]

    def run_it(self, payload, *args, noise=None):
        producer = (self.emit(payload) if noise is None
                    else self.emit_both(payload, noise))
        return subprocess.run(
            [sys.executable, str(CHECK), *args, "--", *producer],
            capture_output=True, text=True)


class SarifIsReadAsADocument(FormatCase):
    def test_an_error_result_fires(self):
        proc = self.run_it(sarif([result("error")]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_a_document_is_never_counted_as_unparsed_lines(self):
        # The regression this whole file exists for: pretty-printed
        # SARIF read line-by-line is every line unparsed and no
        # findings at all.
        import json
        pretty = json.dumps(json.loads(sarif([result("error")])), indent=2)
        self.assertGreater(len(pretty.splitlines()), 5)
        proc = self.run_it(pretty)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertNotIn("unparsed", proc.stdout)

    def test_a_run_that_found_nothing_is_clean(self):
        proc = self.run_it(sarif(
            runs=[{"tool": {"driver": {"name": "c"}}, "results": []}]))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        # Exit 0 alone does not prove the document was READ: the line
        # walk returns 0 for a document it never claimed, counting it
        # as unparsed. The absence of "unparsed" is the discriminator
        # (Grok, PR review of 3453dc1).
        self.assertNotIn("unparsed", proc.stdout)

    def test_no_runs_at_all_is_not_clean(self):
        # "The tool never ran" and "the tool found nothing" must not
        # produce the same verdict.
        proc = self.run_it(sarif(runs=[]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no runs", (proc.stdout + proc.stderr).lower())

    def test_a_level_less_result_takes_the_rules_default(self):
        # SARIF 2.1.0 §3.27.10: absent `level` resolves through the
        # rule's defaultConfiguration before any global default.
        rules = [{"id": "R1", "defaultConfiguration": {"level": "error"}}]
        proc = self.run_it(sarif([result(None, rule="R1")], rules=rules))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_a_level_less_result_with_no_rule_is_a_warning(self):
        # The spec's fallback is `warning` — NOT unparsed, which would
        # read as "we could not tell" for a perfectly valid document.
        proc = self.run_it(sarif([result(None, rule="unknown")]))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warning=1", proc.stdout)

    def test_a_non_failing_kind_is_not_a_finding(self):
        # SARIF 2.1.0 §3.27.9: a result whose `kind` is anything but
        # "fail" is not a finding, so an absent level means "none"
        # rather than the global `warning` default. Scoring a passing
        # rule evaluation as a warning is a false positive the gate
        # would have to be taught to ignore.
        passing = result(None, rule="unknown")
        passing["kind"] = "pass"
        proc = self.run_it(sarif([passing]))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        # Not `assertIn("none", ...)`: the empty-counts summary prints
        # the word "none" itself, so that assertion is satisfied by a
        # spurious `none=1` count as readily as by no count at all.
        # The summary always carries ">= error", so the discriminating
        # form is the exact opening — `none (` and not `none=1 (`.
        self.assertTrue(
            proc.stdout.startswith("diagnostics: none ("), proc.stdout)

    def test_a_non_failing_kind_beats_its_rules_default(self):
        # §3.27.9 resolves `kind != "fail"` to "none" BEFORE the
        # fail-path defaulting. Without a rule default in the fixture,
        # kind-first and kind-last are indistinguishable — so this
        # gives the rule a default of `error` and requires the kind to
        # win (Grok, PR review of 3453dc1).
        passing = result(None, rule="R1")
        passing["kind"] = "pass"
        proc = self.run_it(sarif(
            [passing],
            rules=[{"id": "R1", "defaultConfiguration": {"level": "error"}}]))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(
            proc.stdout.startswith("diagnostics: none ("), proc.stdout)

    def test_a_note_does_not_fail_but_is_counted(self):
        proc = self.run_it(sarif([result("note")]))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("note=1", proc.stdout)

    def test_every_run_is_counted_not_only_the_first(self):
        two = [{"tool": {"driver": {"name": "a"}},
                "results": [result("error")]},
               {"tool": {"driver": {"name": "b"}},
                "results": [result("error")]}]
        proc = self.run_it(sarif(runs=two))
        self.assertIn("error=2", proc.stdout)

    def test_fail_on_warning_reaches_sarif_too(self):
        proc = self.run_it(sarif([result("warning")]), "--fail-on", "warning")
        self.assertEqual(proc.returncode, 1, proc.stdout)


class JunitIsReadAsADocument(FormatCase):
    def test_a_failure_fires(self):
        proc = self.run_it(junit(case(inner='<failure message="assert"/>')))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_an_error_fires(self):
        proc = self.run_it(junit(case(inner='<error message="panic"/>')))
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_the_two_are_distinguished_in_the_summary(self):
        # A failed assertion and a test that never got to assert are
        # different facts. Both fail the gate; collapsing them in the
        # report throws away the distinction ops/process/tdd.md is
        # built on — an honest red versus a collection error.
        proc = self.run_it(junit(
            case("a", '<failure message="assert"/>')
            + case("b", '<error message="panic"/>')))
        self.assertIn("1 failure", proc.stdout)
        self.assertIn("1 error", proc.stdout)

    def test_passing_cases_are_clean(self):
        proc = self.run_it(junit(case("a") + case("b")))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("unparsed", proc.stdout)
        self.assertIn("2 test(s)", proc.stdout)

    def test_a_skip_is_a_note_not_a_failure(self):
        proc = self.run_it(junit(case("a", "<skipped/>")))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("note=1", proc.stdout)

    def test_zero_test_cases_is_not_clean(self):
        # "NO TESTS RAN" is not a red (ops/process/tdd.md) — and it is
        # not a pass either. A -k pattern matching nothing, a filter
        # that excluded everything, a binary that built no tests.
        proc = self.run_it(junit(""))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no test", (proc.stdout + proc.stderr).lower())

    def test_a_bare_testsuite_root_reads_too(self):
        proc = self.run_it(
            junit(case(inner='<failure message="a"/>'), wrap=False))
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_a_foreign_root_is_not_read_as_junit(self):
        # The substring gate lets in any XML that merely MENTIONS a
        # testsuite. Only a document actually rooted at one is a
        # report; anything else falls through to the line walk and is
        # reported unparsed, rather than being scored as a clean run.
        foreign = ('<?xml version="1.0"?><coverage><testsuite name="s">'
                   '<testcase name="t"/></testsuite></coverage>')
        proc = self.run_it(foreign)
        self.assertIn("unparsed", proc.stdout)
        self.assertNotIn("test(s)", proc.stdout)

    def test_entity_expansion_is_refused_rather_than_parsed(self):
        # ElementTree is not hardened against entity expansion and
        # defusedxml is not available in a stdlib-only lane, so a
        # document declaring entities is refused before it is parsed.
        bomb = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
                '<testsuites><testsuite name="s">'
                '<testcase name="t"/></testsuite></testsuites>')
        proc = self.run_it(bomb)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        # NOT the combined output: the check echoes the producer's
        # first lines, so the bomb's own "<!ENTITY" would satisfy a
        # loose assertion whether or not the guard ever fired.
        self.assertIn("refusing", proc.stderr.lower())
        self.assertIn("entities", proc.stderr.lower())


class ARealProducerAlsoWritesToStderr(FormatCase):
    """The document is on stdout; the build chatter is on stderr."""

    def test_sarif_survives_progress_chatter_on_stderr(self):
        proc = self.run_it(sarif([result("error")]),
                           noise="Compiling foo v0.1.0\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_junit_survives_progress_chatter_on_stderr(self):
        proc = self.run_it(junit(case(inner='<failure message="a"/>')),
                           noise="Compiling foo v0.1.0\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_a_refusal_survives_chatter_too(self):
        proc = self.run_it(junit(""), noise="Compiling foo v0.1.0\n")
        self.assertEqual(proc.returncode, 1, proc.stdout)


class SarifIdentityAndEmptyStates(FormatCase):
    """What counts as a SARIF log, and which of its shapes are clean."""

    def test_a_line_record_carrying_a_runs_list_is_not_sarif(self):
        # The recognition guard was "a dict with a list-valued runs".
        # An ordinary producer record can satisfy that and was being
        # swallowed silently (Codex P1).
        proc = self.run_it('{"severity":"error","message":"m","runs":[{}]}')
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_runs_null_is_refused_not_ignored(self):
        proc = self.run_it('{"version":"2.1.0","runs":null}')
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_results_null_is_refused(self):
        # SARIF §3.14.23: absent/null `results` means the tool failed
        # to populate the log, which is not "found nothing".
        proc = self.run_it(sarif(runs=[{"tool": {"driver": {"name": "c"}},
                                        "results": None}]))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        # Exit 1 alone is satisfied by a TypeError traceback just as
        # well as by the refusal, so the message is the assertion.
        self.assertIn("results", proc.stderr.lower())
        self.assertNotIn("traceback", proc.stderr.lower())

    def test_an_unsuccessful_invocation_is_refused(self):
        # The spec has a field for "did the tool actually run", and
        # ignoring it while inferring the same thing from empty runs
        # was reading the wrong signal.
        proc = self.run_it(sarif(
            runs=[{"tool": {"driver": {"name": "c"}},
                   "invocations": [{"executionSuccessful": False}],
                   "results": []}]))
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_a_successful_invocation_with_no_results_stays_clean(self):
        proc = self.run_it(sarif(
            runs=[{"tool": {"driver": {"name": "c"}},
                   "invocations": [{"executionSuccessful": True}],
                   "results": []}]))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class SarifRuleReferences(FormatCase):
    """A result may name its rule three ways; all resolve the default."""

    RULES = [{"id": "R1", "defaultConfiguration": {"level": "error"}}]

    def run_with(self, ref):
        return self.run_it(sarif(runs=[{
            "tool": {"driver": {"name": "c", "rules": self.RULES}},
            "results": [{**ref, "message": {"text": "m"}}]}]))

    def test_by_rule_index(self):
        proc = self.run_with({"ruleIndex": 0})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_by_rule_descriptor_reference(self):
        proc = self.run_with({"rule": {"id": "R1"}})
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_by_rule_descriptor_index(self):
        proc = self.run_with({"rule": {"index": 0}})
        self.assertEqual(proc.returncode, 1, proc.stdout)


class TheProlognWalkIsNotFooledByAComment(FormatCase):
    """A regex boundary read a comment as the document root.

    `<!-- <A -->` before a DOCTYPE made the guard scan an empty prolog,
    admit the document, and expand the entity — while the SAME document
    without the comment was refused. That defeated the mitigation the
    S314 exemption in ruff.toml is justified by (Codex, PR #38).
    """

    SUITE = ('<testsuites><testsuite name="s">'
             '<testcase name="t"/></testsuite></testsuites>')
    DECL = '<!DOCTYPE testsuites [<!ENTITY lol "lol">]>'

    def test_a_comment_holding_an_angle_bracket_does_not_hide_a_doctype(self):
        proc = self.run_it("<!-- <A -->" + self.DECL + self.SUITE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("refusing", proc.stderr.lower())

    def test_a_processing_instruction_does_not_hide_one_either(self):
        proc = self.run_it('<?xml version="1.0"?><?style href="<A"?>'
                           + self.DECL + self.SUITE)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("refusing", proc.stderr.lower())

    def test_a_comment_before_a_clean_report_is_not_a_refusal(self):
        # The guard must not simply refuse anything with a comment in
        # it — that would trade a silent pass for a false failure.
        proc = self.run_it("<!-- <A -->" + self.SUITE.replace(
            '<testcase name="t"/>',
            '<testcase name="t"><failure message="a"/></testcase>'))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)
        self.assertNotIn("refusing", proc.stderr.lower())


class SarifRulesResolveThroughTheirToolComponent(FormatCase):
    """A rule may live in an extension, not the driver.

    §3.52: a rule reference may carry a toolComponent index into
    `run.tool.extensions`. Reading only the driver's rules gave an
    extension rule configured `error` the global `warning` fallback, so
    a document declaring a failure passed the gate (Codex, PR #38).
    """

    RULE = {"id": "R1", "defaultConfiguration": {"level": "error"}}

    def doc(self, reference, *, in_extension=True):
        tool = {"driver": {"name": "clippy"}}
        if in_extension:
            tool["extensions"] = [{"name": "ext", "rules": [self.RULE]}]
        else:
            tool["driver"]["rules"] = [self.RULE]
        return sarif(runs=[{"tool": tool, "results": [
            {**reference, "message": {"text": "m"}}]}])

    def test_an_extension_rule_keeps_its_configured_level(self):
        proc = self.run_it(self.doc(
            {"rule": {"id": "R1", "toolComponent": {"index": 0}}}))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_a_driver_rule_is_unaffected_by_the_change(self):
        proc = self.run_it(self.doc({"ruleId": "R1"}, in_extension=False))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_an_unresolvable_component_falls_back_to_the_driver(self):
        # An index past the end is a malformed document, not a reason
        # to crash or to invent a level.
        proc = self.run_it(self.doc(
            {"rule": {"id": "R1", "toolComponent": {"index": 9}}},
            in_extension=False))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)


class JunitIsReadRegardlessOfNamespace(FormatCase):
    """A default xmlns made a report full of failures exit 0.

    ElementTree reports namespaced tags as "{uri}testsuites", so every
    tag comparison silently stopped matching, the reader declined the
    document, and the failures went out as unparsed lines with a clean
    exit — the silent-pass shape this whole check exists to refuse
    (Grok, PR review of 3453dc1). The fix was verified by hand at the
    time and NOT pinned by a test; a mutation run caught that.
    """

    NS = 'xmlns="http://example.com/junit"'

    def namespaced(self, inner):
        return ('<?xml version="1.0"?>'
                f'<testsuites {self.NS}><testsuite name="s">'
                f'{inner}</testsuite></testsuites>')

    def test_a_namespaced_failure_still_fires(self):
        proc = self.run_it(self.namespaced(
            '<testcase name="t"><failure message="assert"/></testcase>'))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)
        self.assertNotIn("unparsed", proc.stdout)

    def test_a_namespaced_error_is_told_from_a_failure(self):
        proc = self.run_it(self.namespaced(
            '<testcase name="a"><failure message="x"/></testcase>'
            '<testcase name="b"><error message="y"/></testcase>'))
        self.assertIn("1 failure", proc.stdout)
        self.assertIn("1 error", proc.stdout)

    def test_a_namespaced_report_with_no_cases_still_refuses(self):
        proc = self.run_it(self.namespaced(""))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("no test cases", proc.stderr.lower())


class TheEntityGuardOnlyReadsTheProlog(FormatCase):
    def test_a_doctype_inside_cdata_is_not_a_declaration(self):
        # Maven Surefire writes captured stdout as CDATA, so a test
        # that prints HTML made the whole report a refusal (Codex P2).
        proc = self.run_it(junit(case("t", "<system-out><![CDATA["
                                      "<!DOCTYPE html>]]></system-out>")))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_each_declaration_keyword_is_refused_on_its_own(self):
        # One fixture carrying BOTH keywords lets either half of the
        # guard be deleted undetected — the conjunction is never
        # exercised alone (Grok, PR review of 3453dc1).
        suite = ('<testsuites><testsuite name="s">'
                 '<testcase name="t"/></testsuite></testsuites>')
        only_doctype = ('<?xml version="1.0"?>'
                        '<!DOCTYPE testsuites SYSTEM "j.dtd">' + suite)
        only_entity = ('<?xml version="1.0"?>'
                       '<!ENTITY lol "lol">' + suite)
        for label, doc in (("DOCTYPE", only_doctype),
                           ("ENTITY", only_entity)):
            with self.subTest(keyword=label):
                proc = self.run_it(doc)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn("refusing", proc.stderr.lower())


class TheLineFormatStillWorks(FormatCase):
    """Neither reader may swallow what the check already handled."""

    def test_a_cargo_nested_record_still_fires(self):
        proc = self.run_it(
            '{"reason":"compiler-message","message":'
            '{"level":"error","rendered":"E0308"}}')
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)

    def test_prose_is_still_unparsed_not_a_crash(self):
        proc = self.run_it("not json at all\n")
        self.assertIn("unparsed=1", proc.stdout)

    def test_malformed_xml_falls_through_rather_than_crashing(self):
        proc = self.run_it("<testsuites><unclosed>")
        self.assertIn("unparsed", proc.stdout)

    def test_a_json_document_that_is_not_sarif_is_left_alone(self):
        # A single-line JSON object with no `runs` is an ordinary
        # record, and the line reader owns it.
        proc = self.run_it('{"severity":"error","message":"boom"}')
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("error=1", proc.stdout)


if __name__ == "__main__":
    unittest.main()
