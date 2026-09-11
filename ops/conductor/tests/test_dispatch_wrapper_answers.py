"""Dispatcher pass-through of --follows and --answers.

Written from scope-gate-20260910.md items 1, 2 and 9, and the landed
Dispatch §Verbs line `[--follows ID]... [--answers KEY]...`. The wrapper
is the subject and is not read here. Callee flag names and order come
from ops/devlane/dispatch/CONTRACT.md §Verbs, not from launch.py.

Item 2: a correction names finding keys through the declared dispatch
field --answers KEY, repeatable. Item 1: the shape is read from
--follows (repeatable) and --input, never from prose. Item 9: fix-tests
and fix-code dispatch with --follows previous, security, adversarial and
one --answers KEY per finding.

Argv assertions compare exact lists. The fixture is the existing
wrapper harness; this module does not restyle it.
"""

from __future__ import annotations

import json
import re
import unittest

import test_dispatch_wrapper as wrap

# CONTRACT.md §Verbs: key shape accepted on the declared field.
# The wrapper is pass-through; tests plant keys of that shape.
RECORD_ID = re.compile(
    r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}$"
)
ANSWER_KEY = re.compile(
    r"^\d{8}T\d{6}Z-[a-z-]+-[a-z]+-[0-9a-f]{6}#[1-9][0-9]*$"
)

PREVIOUS = "20260901T000000Z-code-codex-aaaaaa"
SECURITY = "20260901T010000Z-review-codex-bbbbbb"
ADVERSARIAL = "20260901T020000Z-review-grok-cccccc"
KEY_SEC = f"{SECURITY}#1"
KEY_ADV = f"{ADVERSARIAL}#2"
UNKNOWN = "--not-a-real-flag"


def flag_values(argv: list[str], flag: str) -> list[str]:
    values: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == flag:
            if i + 1 >= len(argv):
                raise AssertionError(f"{flag} is last with no value: {argv!r}")
            values.append(argv[i + 1])
            i += 2
            continue
        i += 1
    return values


def last_index(argv: list[str], token: str) -> int:
    try:
        return len(argv) - 1 - argv[::-1].index(token)
    except ValueError as exc:
        raise AssertionError(f"{token!r} missing from {argv!r}") from exc


class DispatcherAnswers(wrap._WrapperFixture):
    """Item 2 field on the wrapper; item 1/9 repeatable follows."""

    maxDiff = None

    def setUp(self):
        super().setUp()
        for rec in (PREVIOUS, SECURITY, ADVERSARIAL):
            self.assertRegex(rec, RECORD_ID, rec)
        for key in (KEY_SEC, KEY_ADV):
            self.assertRegex(key, ANSWER_KEY, key)
        self.assertNotEqual(KEY_SEC, KEY_ADV)
        self.assertNotEqual(SECURITY, ADVERSARIAL)
        self.assertNotEqual(PREVIOUS, SECURITY)

    def correction_flags(
        self,
        follows: list[str],
        answers: list[str],
        *extra: str,
        **kw,
    ) -> list[str]:
        flags: list[str] = []
        for rec in follows:
            flags.extend(["--follows", rec])
        for key in answers:
            flags.extend(["--answers", key])
        flags.extend(extra)
        return self.full_flags(*flags, omit=("follows",), **kw)

    def expected_correction_argv(
        self,
        follows: list[str],
        answers: list[str],
        **kw,
    ) -> list[str]:
        argv = self.expected_argv(follows="", **kw)
        self.assertNotIn("--follows", argv)
        self.assertNotIn("--answers", argv)
        for rec in follows:
            argv.extend(["--follows", rec])
        for key in answers:
            argv.extend(["--answers", key])
        return argv

    def assert_follows_then_answers(
        self,
        argv: list[str],
        follows: list[str],
        answers: list[str],
    ) -> None:
        self.assertTrue(follows, "plant: follows must be non-empty")
        got_follows = flag_values(argv, "--follows")
        self.assertEqual(len(got_follows), len(follows), argv)
        self.assertEqual(got_follows, follows)
        got_answers = flag_values(argv, "--answers")
        self.assertEqual(len(got_answers), len(answers), argv)
        self.assertEqual(got_answers, answers)
        input_at = last_index(argv, "--input")
        follows_at = [i for i, tok in enumerate(argv) if tok == "--follows"]
        self.assertEqual(len(follows_at), len(follows), argv)
        self.assertLess(input_at, follows_at[0], argv)
        if answers:
            answers_at = [i for i, tok in enumerate(argv) if tok == "--answers"]
            self.assertEqual(len(answers_at), len(answers), argv)
            self.assertLess(follows_at[-1], answers_at[0], argv)
        else:
            self.assertNotIn("--answers", argv)

    def test_two_follows_reach_dry_run_argv_in_given_order(self):
        """Item 1: --follows is repeatable; last-wins drops a review."""
        follows = [SECURITY, ADVERSARIAL]
        proc = self.invoke(self.correction_flags(follows, answers=[]))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv, _env = self.parse_dry_run(proc)
        self.assert_follows_then_answers(argv, follows, [])
        self.assertEqual(argv, self.expected_correction_argv(follows, []))
        self.assert_no_launch()

    def test_two_answers_reach_dry_run_argv_after_the_follows(self):
        """Item 2: --answers KEY is a documented, repeatable field."""
        follows = [SECURITY, ADVERSARIAL]
        answers = [KEY_SEC, KEY_ADV]
        proc = self.invoke(self.correction_flags(follows, answers))
        text = self.combined(proc)
        self.assertNotIn("unknown flag", text.lower(), text)
        self.assertEqual(proc.returncode, 0, text)
        argv, _env = self.parse_dry_run(proc)
        self.assert_follows_then_answers(argv, follows, answers)
        self.assertEqual(
            argv,
            self.expected_correction_argv(follows, answers),
        )
        payload = self.parse_dry_run_object(proc)
        self.assertEqual(payload["argv"], argv)
        self.assert_no_launch()

    def test_three_follows_reach_dry_run_argv_in_given_order(self):
        """Item 9: previous, security, adversarial all reach argv."""
        follows = [PREVIOUS, SECURITY, ADVERSARIAL]
        proc = self.invoke(self.correction_flags(follows, answers=[]))
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv, _env = self.parse_dry_run(proc)
        self.assert_follows_then_answers(argv, follows, [])
        self.assertEqual(argv, self.expected_correction_argv(follows, []))
        self.assert_no_launch()

    def test_fix_stage_three_follows_and_one_answers_per_key(self):
        """Item 9: --follows previous, security, adversarial, then keys."""
        follows = [PREVIOUS, SECURITY, ADVERSARIAL]
        answers = [KEY_SEC, KEY_ADV]
        proc = self.invoke(self.correction_flags(follows, answers))
        text = self.combined(proc)
        self.assertNotIn("unknown flag", text.lower(), text)
        self.assertEqual(proc.returncode, 0, text)
        argv, _env = self.parse_dry_run(proc)
        self.assert_follows_then_answers(argv, follows, answers)
        self.assertEqual(
            argv,
            self.expected_correction_argv(follows, answers),
        )
        self.assert_no_launch()

    def test_two_answers_reach_the_foreground_launcher_after_follows(self):
        """Item 2: the exec path carries the same flags as dry-run."""
        follows = [SECURITY, ADVERSARIAL]
        answers = [KEY_SEC, KEY_ADV]
        argv_log = self.scratch / "launcher-argv.json"
        self.assertFalse(argv_log.exists(), "plant: argv log must not pre-exist")
        self._plant_python_sentinel(
            self.pin,
            "import json, pathlib, sys\n"
            f"pathlib.Path({str(argv_log)!r}).write_text("
            "json.dumps(sys.argv))\n"
            f"pathlib.Path({str(self.marker)!r}).write_text('launched')\n",
        )
        proc = self.invoke(
            self.correction_flags(follows, answers, dry_run=False),
            timeout=8,
        )
        text = self.combined(proc)
        self.assertNotIn("unknown flag", text.lower(), text)
        self.assertEqual(proc.returncode, 0, text)
        self.assertTrue(self.marker.exists(), "foreground path must launch")
        self.assertTrue(argv_log.is_file(), "sentinel recorded argv")
        launched = json.loads(argv_log.read_text(encoding="utf-8"))
        self.assertIsInstance(launched, list, launched)
        self.assertTrue(
            all(isinstance(item, str) for item in launched),
            launched,
        )
        self.assert_follows_then_answers(launched, follows, answers)

    def test_a_dispatch_without_answers_does_not_emit_answers(self):
        """Item 7: the wrapper does not invent keys on a non-correction."""
        proc = self.invoke(self.full_flags())
        self.assertEqual(proc.returncode, 0, self.combined(proc))
        argv, _env = self.parse_dry_run(proc)
        self.assertNotIn("--answers", argv)
        self.assertEqual(flag_values(argv, "--answers"), [])
        self.assertEqual(argv, self.expected_argv())
        self.assert_no_launch()

    def test_unknown_flag_is_still_a_refusal(self):
        """Accepting --answers must not accept an undocumented flag."""
        proc = self.invoke(self.full_flags(UNKNOWN, dry_run=False))
        text = self.combined(proc)
        self.assertIn(UNKNOWN, text)
        self.assertNotEqual(proc.returncode, 0, text)
        self.assert_no_launch()


if __name__ == "__main__":
    unittest.main()
