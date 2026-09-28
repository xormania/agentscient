"""Exercise the real cache installer with a local archive and offline downloader."""

import hashlib
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / "actions/php-runtime/install-php.sh"


class PHPCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("bin", "temp", "tools"):
            (self.root / name).mkdir()
        php = self.root / "php"
        php.write_text("#!/bin/sh\nprintf 'fixture PHP\\n'\n")
        php.chmod(0o755)
        self.archive = self.root / "php.tar.gz"
        with tarfile.open(self.archive, "w:gz") as archive:
            archive.add(php, arcname="php")
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        curl = self.root / "bin/curl"
        curl.write_text('#!/bin/bash\nset -eu\necho download >> "$FIXTURE_DOWNLOADS"\ncp "$FIXTURE_ARCHIVE" "${@: -1}"\n')
        curl.chmod(0o755)
        self.downloads = self.root / "downloads"
        self.path_file = self.root / "github-path"
        self.env = {
            **os.environ,
            "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"],
            "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "RUNNER_TEMP": str(self.root / "temp"), "RUNNER_TOOL_CACHE": str(self.root / "tools"),
            "GITHUB_PATH": str(self.path_file),
            "FIXTURE_ARCHIVE": str(self.archive), "FIXTURE_DOWNLOADS": str(self.downloads),
        }
        self.cached = self.root / "tools/agentscient-php" / (self.digest + ".tar.gz")

    def install(self):
        return subprocess.run(["bash", str(INSTALLER), "https://fixture.invalid/php.tar.gz", self.digest],
                              env=self.env, capture_output=True, text=True)

    def test_cold_warm_and_corrupt_downloads_keep_runtime_extraction_isolated(self):
        for state in ("cold", "warm", "corrupt"):
            with self.subTest(state=state):
                if state == "corrupt":
                    self.cached.write_bytes(b"broken cache")
                result = self.install()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("cache hit" if state == "warm" else "cache miss", result.stdout)
                self.assertEqual(hashlib.sha256(self.cached.read_bytes()).hexdigest(), self.digest)
        self.assertEqual(self.downloads.read_text().splitlines(), ["download", "download"])
        runtimes = self.path_file.read_text().splitlines()
        self.assertEqual(len(set(runtimes)), 3)
        self.assertTrue(all((Path(path) / "php").is_file() for path in runtimes))

    def test_invalid_download_is_never_published_or_executed(self):
        self.archive.write_bytes(b"not the pinned archive")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum mismatch", result.stdout)
        self.assertFalse(self.cached.exists())
        self.assertFalse(self.path_file.exists())
        self.assertEqual(list(self.cached.parent.glob(".download.*")), [])


if __name__ == "__main__":
    unittest.main()
