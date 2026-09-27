"""LD-18 (2026-09-11): an aged grok credential is refused at the launcher,
on the wire, before any child starts. The isolation module raises
NotIsolated; the launcher must turn that into a refusal, not a traceback
(NotIsolated subclasses Exception, and the launcher's catch listed only
the standard classes)."""

import datetime
import json
import os

import launch_support as ls

from ops.testkit import World  # noqa: F401 - _TempLaunch owns the world


def _stamp(hours_ago):
    at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    return at.strftime("%Y-%m-%dT%H:%M:%S.%f") + "000Z"


class AnAgedGrokCredentialIsRefusedBeforeTheMint(ls._TempLaunch):
    def plant_credential(self, hours_ago):
        auth = self.home / ".grok" / "auth.json"
        self.assertTrue(auth.is_file(), "plant: the fixture's credential is present")
        self.world.plant_text(auth, json.dumps({"https://auth.x.ai::client": {
            "key": "k", "refresh_token": "r", "create_time": _stamp(hours_ago)}}) + "\n")
        self.assertIn("create_time", auth.read_text(encoding="utf-8"), "plant: stamp written")

    def test_a_credential_past_its_lifetime_refuses_naming_the_login(self):
        self.plant_credential(31)
        code, out, err = self.dispatch(self.argv_for(job="plan", harness="grok", stage="plan"))
        self.assertEqual(code, ls.REFUSAL_EXIT, self.combined(out, err))
        text = self.combined(out, err)
        self.assertIn("isolation", text)
        self.assertIn("grok login --device-code", text)
        self.assertNotIn("Traceback", text)
        self.assert_not_started()
        self.assertEqual(self.job_dirs(), [])

    def test_a_fresh_credential_launches(self):
        self.plant_credential(1)
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        self.assertEqual(rec["harness"]["name"], "grok")

    def test_a_renewal_by_the_worker_reaches_the_host_copy(self):
        # LD-41 (2026-09-15): the CLI renews by renaming a new file over the
        # link in the job home; the host copy kept the login's token and
        # aged out while every renewal sat in a job home.
        self.plant_credential(20)
        renewed = json.dumps({"https://auth.x.ai::client": {
            "key": "k2", "refresh_token": "renewed", "create_time": _stamp(0)}}) + "\n"
        os.environ["TASK_LAUNCH_RENEW_AUTH"] = renewed
        rec, *_ = self.launch_ok(job="plan", harness="grok", stage="plan")
        host = self.home / ".grok" / "auth.json"
        self.assertIn('"renewed"', host.read_text(encoding="utf-8"),
                      "the host copy carries the worker's renewal")
        self.assertEqual(rec["attempts"][-1].get("credential"),
                         [{"file": "auth.json", "outcome": "carried"}])
        job_auth = self.jobs_root / rec["id"] / "home" / "grok" / "auth.json"
        self.assertTrue(job_auth.is_symlink(), "the job home holds the link again")
