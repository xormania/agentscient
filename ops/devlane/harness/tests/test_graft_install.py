"""Install identity, pin/digest mismatch, and partial trees.

Written from graft/CONTRACT.md installation. Ordinary cases never
download; they plant a fake completed tree or refuse before fetch.
"""

from __future__ import annotations

import json
import unittest

import support  # noqa: F401
import graft_support as gs


class InstallRefusesBeforeOverwrite(gs.GraftCase, unittest.TestCase):
    def test_relative_destination_refuses_arguments(self):
        code, out, err = self.cli(["install", "--destination", "rel-install"])
        gs.assert_refusal(
            self, code, out, err, "arguments",
            phrases=["absolute"],
        )
        self.assertFalse((self.home / "rel-install").exists())

    def test_nonempty_destination_is_refused_not_overwritten(self):
        dest = self.home / "occupied"
        dest.mkdir()
        marker = dest / "keep-me"
        marker.write_text("original\n", encoding="utf-8")
        code, out, err = self.cli(["install", "--destination", str(dest)])
        gs.assert_refusal(
            self, code, out, err, "graft-install",
            phrases=["nonempty"],
        )
        self.assertEqual(marker.read_text(encoding="utf-8"), "original\n")

    def test_install_is_the_only_cli_verb_that_would_fetch(self):
        dest = self.home / "fresh"
        self.drain_spawns()
        status = self.cli(["status"])
        gs.assert_no_spawns(self, self.drain_spawns())
        self.assertFalse(dest.exists())
        self.assertNotEqual(status[0], None)
        probe = self.cli(["probe", "--root", str(self.home), "--cache", str(self.home / "c")])
        gs.assert_no_fetch(self, self.drain_spawns())
        self.assertFalse(dest.exists())
        self.assertNotEqual(probe[0], 0)
        self.assertFalse(dest.exists())


class ReceiptAndPinAreTheInstallIdentity(gs.GraftCase, unittest.TestCase):
    def test_wrong_pin_version_in_the_receipt_is_not_ready(self):
        dest = self.plant_fake_install()
        before_code, before_out, _before_err = self.cli(["status"])
        receipt_path = dest / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        planted = receipt_path.read_bytes()
        receipt["pin"]["graft"]["version"] = "0.0.0"
        self.assertNotEqual(receipt["pin"]["graft"]["version"], self.pin["graft"]["version"])
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        self.assertNotEqual(receipt_path.read_bytes(), planted)
        code, out, err = self.cli(["status"])
        self.assertNotEqual(
            (before_code, before_out), (code, out),
            "a wrong pin must not status the same as the matching receipt",
        )
        if code == 0:
            self.assertEqual(json.loads(out).get("state"), "unavailable")
        else:
            gs.assert_refusal(self, code, out, err, "graft-install")

    def test_wrong_file_digest_in_the_receipt_is_not_ready(self):
        dest = self.plant_fake_install()
        before_code, before_out, _before_err = self.cli(["status"])
        receipt_path = dest / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        bogus = "0" * 64
        key = "graft/package.json"
        self.assertIn(key, receipt["files"])
        self.assertNotEqual(receipt["files"][key], bogus)
        receipt["files"][key] = bogus
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        code, out, err = self.cli(["status"])
        self.assertNotEqual(
            (before_code, before_out), (code, out),
            "a wrong file digest must not status the same as the matching receipt",
        )
        if code == 0:
            self.assertEqual(json.loads(out).get("state"), "unavailable")
        else:
            gs.assert_refusal(self, code, out, err, "graft-install")

    def test_partial_install_missing_node_is_not_ready(self):
        dest = self.plant_fake_install()
        before_code, before_out, _before_err = self.cli(["status"])
        node = dest / "node" / "bin" / "node"
        self.assertTrue(node.is_file())
        node.unlink()
        self.assertFalse(node.exists())
        code, out, err = self.cli(["status"])
        self.assertNotEqual(
            (before_code, before_out), (code, out),
            "a partial tree must not status the same as a complete one",
        )
        if code == 0:
            self.assertEqual(json.loads(out).get("state"), "unavailable")
        else:
            gs.assert_refusal(self, code, out, err, "graft-install")

    def test_prepare_refuses_a_partial_install(self):
        dest = self.plant_fake_install()
        (dest / "graft" / "package-lock.json").unlink()
        root = self.plant_root()
        cache = self.home / "cache"
        code, out, err = self.cli(
            ["prepare", "--root", str(root), "--cache", str(cache)],
        )
        gs.assert_refusal(self, code, out, err, "graft-install")
        self.assertFalse(cache.exists())

    def test_escaping_symlink_in_the_install_tree_is_rejected(self):
        dest = self.plant_fake_install()
        before_code, before_out, _before_err = self.cli(["status"])
        outside = self.home / "outside.js"
        outside.write_text("not-in-install\n", encoding="utf-8")
        link = dest / "graft" / "dist" / "escape.js"
        link.symlink_to(outside)
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), outside.resolve())
        code, out, err = self.cli(["status"])
        self.assertNotEqual(
            (before_code, before_out), (code, out),
            "an escaping symlink must not status the same as a clean tree",
        )
        if code == 0:
            self.assertEqual(json.loads(out).get("state"), "unavailable")
        else:
            gs.assert_refusal(self, code, out, err, "graft-install")


class ProbeIsUnavailableNotSilentlyGreen(gs.GraftCase, unittest.TestCase):
    def test_disabled_probe_refuses_graft_disabled_and_is_never_green(self):
        self.set_install("")
        root = self.plant_root()
        cache = self.home / "probe-cache"
        self.drain_spawns()
        code, out, err = self.cli(
            ["probe", "--root", str(root), "--cache", str(cache)],
        )
        gs.assert_refusal(self, code, out, err, "graft-disabled")
        gs.assert_no_fetch(self, self.drain_spawns())
        self.assertFalse(cache.exists())

    def test_enabled_unreachable_provider_probe_is_not_silently_green(self):
        dest = self.plant_fake_install()
        node = dest / "node" / "bin" / "node"
        node.write_bytes(b"#!/no/such/graft-provider\n")
        node.chmod(node.stat().st_mode | 0o111)
        receipt_path = dest / "receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["files"]["node/bin/node"] = gs.sha256_file(node)
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8",
        )
        status_code, status_out, status_err = self.cli(["status"])
        self.assertEqual(status_code, 0, status_err)
        self.assertEqual(json.loads(status_out).get("state"), "ready")
        root = self.plant_root()
        cache = self.home / "probe-cache"
        code, out, err = self.cli(
            ["probe", "--root", str(root), "--cache", str(cache)],
        )
        self.assertNotEqual(code, 0)
        if (out or "").strip():
            try:
                body = json.loads(out)
            except json.JSONDecodeError:
                body = None
            if isinstance(body, dict):
                self.assertNotEqual(body.get("state"), "ready")
        gs.assert_no_fetch(self, self.read_spawns())


if __name__ == "__main__":
    unittest.main()
