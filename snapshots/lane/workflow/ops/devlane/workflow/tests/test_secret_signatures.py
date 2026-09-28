"""Prove every declared secret signature fires and empty filesets are invalid."""

import ast
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

SCANNER = support.WF_DIR / "checks" / "secret_scan.py"

# EVERY branch of every declared class gets a firing sample: a
# corpus that undersamples its alternations lets a one-line regex
# narrowing go dark (Grok, PR #32 rounds one and two — first the
# missing variants, then the still-missing ones; hand-curating a
# subset invites the next round, so the branches are enumerated in
# full and the count is asserted against the source classes).
SAMPLES = {
    "private key block": [
        "-----BEGIN " + "PRIVATE KEY-----",
        "-----BEGIN " + "RSA PRIVATE KEY-----",
        "-----BEGIN " + "EC PRIVATE KEY-----",
        "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
        "-----BEGIN " + "PGP PRIVATE KEY-----",
    ],
    "AWS access key id": ["AKIA" + "ABCDEFGHIJKLMNOP",
                          "ASIA" + "ABCDEFGHIJKLMNOP"],
    "GitHub token": [prefix + ("A" * 36)
                     for prefix in ("ghp_", "gho_", "ghu_", "ghs_",
                                    "ghr_")],
    "Slack token": [prefix + ("A" * 10)
                    for prefix in ("xoxa-", "xoxb-", "xoxp-", "xoxs-",
                                   "xoxr-")],
    "Google API key": ["AIza" + ("A" * 35),
                       "AIza" + ("a9_-" * 8) + "aaa"],
    "PEM certificate key": ["-----BEGIN " + "ENCRYPTED PRIVATE KEY-----"],
}

# one mixed-charset payload per token class: a scanner that quietly
# drops lowercase or digits from a payload class keeps the all-A
# witnesses green while real credentials go dark (Grok, round three)
SAMPLES["AWS access key id"].append("AKIA" + "0123456789ABCDEF")
# 40 chars after the prefix: the class is {36,}, and an all-36
# corpus lets a {36} tightening ship (Grok, PR #32 round four)
SAMPLES["GitHub token"].append("ghp_" + ("a1B2" * 10))
SAMPLES["Slack token"].append("xoxb-" + "12-ab34cd56")


class EverySecretSignatureFires(unittest.TestCase):
    def signature_patterns(self):
        source = SCANNER.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(SCANNER))
        value = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                names = [
                    target.id for target in node.targets
                    if isinstance(target, ast.Name)
                ]
                if "SIGNATURES" in names:
                    value = node.value
                    break
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "SIGNATURES"
            ):
                value = node.value
                break

        self.assertIsNotNone(value, "secret_scan.py must declare SIGNATURES")
        self.assertIsInstance(value, (ast.List, ast.Tuple))
        self.assertGreater(len(value.elts), 0, "SIGNATURES must not be empty")

        patterns = []
        for entry in value.elts:
            self.assertIsInstance(entry, (ast.List, ast.Tuple))
            self.assertEqual(len(entry.elts), 2)
            label = ast.literal_eval(entry.elts[0])
            call = entry.elts[1]
            self.assertIsInstance(call, ast.Call)
            self.assertIsInstance(call.func, ast.Attribute)
            self.assertEqual(call.func.attr, "compile")
            self.assertGreaterEqual(len(call.args), 1)
            expression = ast.literal_eval(call.args[0])
            patterns.append((label, re.compile(expression)))
        return patterns

    def initialise_repo(self, root):
        proc = subprocess.run(
            ["git", "init", "-q", "-b", "main"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = subprocess.run(
            ["git", "config", "core.excludesFile", "/dev/null"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def assert_indexed(self, root, relative):
        proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative.as_posix()],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), relative.as_posix())

    def run_scanner(self, root, *paths):
        return subprocess.run(
            [sys.executable, str(SCANNER), "--root", str(root), *paths],
            cwd=root,
            capture_output=True,
            text=True, check=False,
        )

    def test_each_pattern_has_an_indexed_plant_that_fires_it(self):
        patterns = self.signature_patterns()
        labels = [label for label, _ in patterns]
        self.assertEqual(len(labels), len(set(labels)), "signature labels must be unique")
        self.assertEqual(
            set(labels), set(SAMPLES),
            "every source-declared signature needs one explicit firing sample",
        )

        for label, pattern in patterns:
            for sample in SAMPLES[label]:
              with self.subTest(signature=label, sample=sample[:12]):
                self.assertIsNotNone(
                    pattern.search(sample),
                    f"the {label!r} plant no longer matches its source pattern",
                )

                with tempfile.TemporaryDirectory(prefix="wf-secret-signature-") as raw:
                    root = Path(raw)
                    self.initialise_repo(root)
                    relative = Path("candidate.txt")
                    candidate = root / relative
                    candidate.write_bytes(b"recognisable clean fixture\n")
                    encoded = sample.encode("utf-8")
                    support.plant_bytes(
                        candidate,
                        lambda clean, encoded=encoded: (
                            clean + encoded + b"\n"),
                        expect="grow",
                        recognisable=lambda planted, encoded=encoded: (
                            b"recognisable clean fixture" in planted
                            and encoded in planted
                        ),
                    )
                    self.assertIn(encoded, candidate.read_bytes())

                    proc = subprocess.run(
                        ["git", "add", relative.as_posix()],
                        cwd=root, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assert_indexed(root, relative)

                    scan = self.run_scanner(root)
                    message = (
                        f"{label} did not fire\n"
                        f"stdout:\n{scan.stdout}\nstderr:\n{scan.stderr}"
                    )
                    self.assertNotEqual(scan.returncode, 0, message)
                    self.assertIn(label, scan.stdout, message)
                    self.assertIn(relative.as_posix(), scan.stdout, message)

    def test_a_default_scan_of_an_empty_repo_is_refused(self):
        # the refusal must ride the git ls-files path too, or a
        # mutant scoping it to explicit paths revives the eval's
        # zero-file pass (Grok, PR #32 review)
        with tempfile.TemporaryDirectory(prefix="wf-secret-empty-") as raw:
            root = Path(raw)
            self.initialise_repo(root)
            scan = self.run_scanner(root)
            self.assertNotEqual(scan.returncode, 0, scan.stdout)
            self.assertRegex(scan.stdout.lower(), r"(no|zero).*(file|match)")

    def test_a_directory_path_scans_the_tracked_files_beneath_it(self):
        # the documented [PATH ...] form takes directories; silently
        # dropping them made `secret_scan.py .` a scan of nothing
        with tempfile.TemporaryDirectory(prefix="wf-secret-dir-") as raw:
            root = Path(raw)
            self.initialise_repo(root)
            nested = root / "sub" / "leak.txt"
            nested.parent.mkdir()
            secret = ("AKIA" + "ABCDEFGHIJKLMNOP").encode("utf-8")
            nested.write_bytes(b"key=" + secret + b"\n")
            self.assertIn(secret, nested.read_bytes())
            file_leak = root / "toplevel.txt"
            secret2 = ("ASIA" + "ABCDEFGHIJKLMNOP").encode("utf-8")
            file_leak.write_bytes(b"key=" + secret2 + b"\n")
            self.assertIn(secret2, file_leak.read_bytes())
            clean = root / "README.md"
            clean.write_bytes(b"clean file\n")
            untracked = root / "sub" / "scratch.txt"
            untracked.write_bytes(b"key=" + secret2 + b"\n")
            self.assertIn(secret2, untracked.read_bytes())
            proc = subprocess.run(
                ["git", "add", "sub/leak.txt", "toplevel.txt",
                 "README.md"],
                cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # PATH must BE the fileset (Grok, PR #32 round three):
            # a named dir finds the leak beneath it; a file argument
            # is scanned, not dropped; a scope that excludes a leak
            # stays clean (ignoring PATH would find it); directory
            # expansion is tracked-only (rglob would scan scratch)
            for args in ((".",), ("sub", "README.md")):
                with self.subTest(args=args):
                    scan = self.run_scanner(root, *args)
                    self.assertNotEqual(scan.returncode, 0, scan.stdout)
                    self.assertIn("leak.txt", scan.stdout)
                    self.assertNotIn("scratch.txt", scan.stdout)
            with self.subTest(args=("toplevel.txt",)):
                scan = self.run_scanner(root, "toplevel.txt")
                self.assertNotEqual(scan.returncode, 0, scan.stdout)
                self.assertIn("toplevel.txt", scan.stdout)
            with self.subTest(args=("README.md",)):
                scan = self.run_scanner(root, "README.md")
                self.assertEqual(scan.returncode, 0, scan.stdout)
                self.assertIn("1 tracked file", scan.stdout)
            with self.subTest(args=("no-such-path",)):
                scan = self.run_scanner(root, "no-such-path")
                self.assertNotEqual(scan.returncode, 0, scan.stdout)
                self.assertRegex(scan.stdout.lower(),
                                 r"(no|zero).*(file|match)")

    def test_an_explicit_fileset_matching_zero_files_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="wf-secret-empty-set-") as raw:
            root = Path(raw)
            self.initialise_repo(root)
            pattern = "missing-*.txt"
            self.assertEqual(
                list(root.glob(pattern)), [],
                "the invalid-fileset fixture unexpectedly matched a file",
            )

            proc = self.run_scanner(root, pattern)
            combined = proc.stdout + proc.stderr
            self.assertNotEqual(
                proc.returncode, 0,
                f"a requested fileset matching zero files passed:\n{combined}",
            )
            self.assertRegex(
                combined.lower(),
                r"(no|zero).*(file|match)",
                f"the refusal must identify the empty fileset:\n{combined}",
            )


if __name__ == "__main__":
    unittest.main()
