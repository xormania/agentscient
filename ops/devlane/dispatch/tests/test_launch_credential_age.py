"""LD-18 (2026-09-11): an aged grok credential is refused at the launcher,
on the wire, before any child starts. The isolation module raises
NotIsolated; the launcher must turn that into a refusal, not a traceback
(NotIsolated subclasses Exception, and the launcher's catch listed only
the standard classes)."""

import datetime
import json

import launch_support as ls


def _stamp(hours_ago):
    at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    return at.strftime("%Y-%m-%dT%H:%M:%S.%f") + "000Z"


class AnAgedGrokCredentialIsRefusedBeforeTheMint(ls._TempLaunch):
    def plant_credential(self, hours_ago):
        auth = self.home / ".grok" / "auth.json"
        self.assertTrue(auth.is_file(), "plant: the fixture's credential is present")
        auth.write_text(json.dumps({"https://auth.x.ai::client": {
            "key": "k", "refresh_token": "r", "create_time": _stamp(hours_ago)}}) + "\n",
            encoding="utf-8")
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
