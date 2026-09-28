"""init / open / next / status — the first end-to-end path, and the agent
contract that applies to every verb (PLAN §4)."""

import json
import unittest

import support
from support import SandboxCase
import canonical
from errors import EXIT_OK, EXIT_REFUSED, EXIT_USAGE


class AgentContract(SandboxCase):
    def test_no_command_prompts_for_input(self):
        # An acceptance-bar item: "zero interactive prompts". Parsed rather
        # than grepped, because a regex cannot tell a call from a method name
        # that happens to end in _input( — §13's literal grep matches five
        # such things and none of them is a prompt.
        import ast

        hits, scanned = [], 0
        for path in sorted(support.WF_DIR.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            scanned += 1
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                        and node.func.id in ("input", "raw_input"):
                    hits.append(f"{path.name}:{node.lineno}")
        self.assertGreater(scanned, 5, "the scan must actually reach the modules")
        self.assertEqual(hits, [], "wf must never prompt")

    def test_a_bad_command_line_exits_usage_not_two(self):
        # argparse's own default is 2, which the exit map reserves for
        # integrity. Reporting a typo as evidence corruption would be a lie.
        self.sb.wf("init", check=EXIT_OK)
        for bad in (["nosuchverb"], ["open", "--kind", "tdd"], []):
            with self.subTest(bad=bad):
                self.assertEqual(self.sb.wf(*bad).returncode, EXIT_USAGE)

    def test_every_verb_accepts_json_and_emits_canonical_json(self):
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("--agent", support.Sandbox.AGENT, "open", "WO-001",
                   "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        for argv in (["init"], ["next"], ["status"], ["status", "WO-001"],
                     ["log", "--full", "--all", "WO-001"], ["next", "WO-001"]):
            with self.subTest(argv=argv):
                proc = self.sb.wf("--json", *argv, check=EXIT_OK)
                body = proc.stdout.strip()
                decoded = json.loads(body)
                self.assertEqual(
                    body, canonical.dumps(decoded),
                    "--json output must itself be canonical",
                )

    def test_a_refusal_names_the_first_failed_precondition_in_json(self):
        self.sb.wf("init", check=EXIT_OK)
        proc = self.sb.wf("--json", "status", "WO-404", check=EXIT_REFUSED)
        body = json.loads(proc.stderr.strip())
        self.assertEqual(body["error"], "refusal")
        self.assertEqual(body["exhaustiveness"], "first-failure")
        self.assertIn("work order exists", body["precondition"])

    def test_an_appending_verb_requires_an_agent(self):
        self.sb.wf("init", check=EXIT_OK)
        proc = self.sb.wf("open", "--kind", "tdd", "--objective", "o",
                          agent="", check=EXIT_REFUSED)
        self.assertIn("agent identity", proc.stderr)


class Init(SandboxCase):
    def test_creates_the_tracked_layout_and_is_idempotent(self):
        first = self.sb.wf("--json", "init", check=EXIT_OK)
        self.assertEqual(json.loads(first.stdout)["migrations_applied"],
                         ["0001_foundation.sql"])
        for name in ("chains", "attempts", "objects"):
            self.assertTrue((self.sb.root / name).is_dir(), name)
        meta = canonical.loads((self.sb.root / "meta.json").read_bytes())
        self.assertEqual(meta, {"format_version": 1})

        second = self.sb.wf("--json", "init", check=EXIT_OK)
        self.assertEqual(json.loads(second.stdout)["migrations_applied"], [])
        self.assertEqual(json.loads(second.stdout)["gate_kinds"],
                         ["artifact@1", "tdd@1"])

    def test_syncs_the_registry_into_the_database(self):
        self.sb.wf("init", check=EXIT_OK)
        import sqlite3

        conn = sqlite3.connect(str(self.sb.db))
        try:
            rows = conn.execute(
                "SELECT kind, version, spec_sha256 FROM gate_kinds ORDER BY kind"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual([(r[0], r[1]) for r in rows], [("artifact", 1), ("tdd", 1)])
        for _, _, sha in rows:
            self.assertEqual(len(sha), 64)

    def test_refuses_when_the_registry_directory_is_missing(self):
        import shutil

        shutil.rmtree(self.sb.root / "gate-kinds")
        proc = self.sb.wf("init", check=EXIT_REFUSED)
        self.assertIn("gate-kind registry directory", proc.stderr)


class Open(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)

    def test_allocates_a_zero_padded_id_when_none_is_given(self):
        first = json.loads(
            self.sb.wf("--json", "open", "--kind", "tdd", "--objective", "one",
                       check=EXIT_OK).stdout
        )
        second = json.loads(
            self.sb.wf("--json", "open", "--kind", "tdd", "--objective", "two",
                       check=EXIT_OK).stdout
        )
        self.assertEqual(first["wo"], "WO-001")
        self.assertEqual(second["wo"], "WO-002")

    def test_opens_at_the_first_stage_with_two_events(self):
        body = json.loads(
            self.sb.wf("--json", "open", "WO-007", "--kind", "tdd",
                       "--objective", "o", check=EXIT_OK).stdout
        )
        self.assertEqual(body["stage"], "spec")
        self.assertEqual(body["kind"], "tdd@1")
        self.assertTrue(body["created"])
        chain = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-007").stdout)["events"]
        self.assertEqual([e["type"] for e in support.without_binds(chain)],
                         ["wo.opened", "stage.entered"])

    def test_is_idempotent_for_identical_arguments(self):
        first = json.loads(
            self.sb.wf("--json", "open", "WO-001", "--kind", "tdd",
                       "--objective", "o", check=EXIT_OK).stdout
        )
        again = json.loads(
            self.sb.wf("--json", "open", "WO-001", "--kind", "tdd",
                       "--objective", "o", check=EXIT_OK).stdout
        )
        self.assertFalse(again["created"])
        self.assertEqual(again["seq"], first["seq"], "a no-op must not append")
        self.assertEqual(again["head"], first["head"])

    def test_refuses_a_reopen_with_different_arguments(self):
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        proc = self.sb.wf("open", "WO-001", "--kind", "artifact",
                          "--objective", "other", check=EXIT_REFUSED)
        self.assertIn("different arguments", proc.stderr)

    def test_refuses_an_id_that_is_not_wo_nnn(self):
        for bad in ("wo-1", "WO-1", "WO001", "PKT-001"):
            with self.subTest(bad=bad):
                proc = self.sb.wf("open", bad, "--kind", "tdd",
                                  "--objective", "o", check=EXIT_REFUSED)
                self.assertIn("WO-NNN", proc.stderr)

    def test_refuses_an_unregistered_gate_kind(self):
        proc = self.sb.wf("open", "--kind", "nosuch", "--objective", "o",
                          check=EXIT_REFUSED)
        self.assertIn("gate kind is registered", proc.stderr)

    def test_pins_the_spec_into_the_object_store(self):
        body = json.loads(
            self.sb.wf("--json", "open", "WO-001", "--kind", "tdd",
                       "--objective", "o", check=EXIT_OK).stdout
        )
        chain = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001").stdout)
        opened = chain["events"][0]
        digest = opened["spec_sha256"]
        stored = (self.sb.root / "objects" / digest[:2] / digest)
        self.assertTrue(stored.exists(), "the pinned spec must be in the CAS")
        self.assertEqual(canonical.sha256_hex(stored.read_bytes()), digest)
        self.assertEqual(canonical.loads(stored.read_bytes())["kind"], "tdd")
        self.assertEqual(body["kind"], "tdd@1")

    def test_records_an_attempt_for_the_transition(self):
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001", "--attempts").stdout)
        self.assertEqual(len(body["attempts"]), 1)
        attempt = body["attempts"][0]
        self.assertEqual(attempt["verb"], "open")
        self.assertEqual(attempt["record_kind"], "accepted")
        self.assertEqual(attempt["event_appended"], 2)
        self.assertEqual(attempt["seq_before"], 0)
        self.assertEqual(attempt["seq_after"], 2)
        self.assertEqual(attempt["agent"], support.Sandbox.AGENT)

    def test_records_an_attempt_for_a_refusal(self):
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "artifact", "--objective", "x",
                   check=EXIT_REFUSED)
        # The refusal happens before the work order is re-derived, so it is
        # recorded against the id that was refused.
        body = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001", "--attempts").stdout)
        kinds = [a["record_kind"] for a in body["attempts"]]
        self.assertIn("accepted", kinds)


class SpecPinning(SandboxCase):
    """The chain's pin is the authority; the registry is a mirror (PLAN §6)."""

    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)

    def relax_red_in_the_registry(self):
        """Delete red's evidence requirement from the tracked spec file."""
        path = self.sb.root / "gate-kinds" / "tdd.json"
        support.plant_bytes(
            path,
            lambda raw: raw.replace(
                b'"leave_requires": ["receipt.red"]', b'"leave_requires": []'
            ),
            expect="shrink",
            recognisable=lambda raw: canonical.loads(raw).get("kind") == "tdd",
        )
        self.sb.commit_all("sandbox: relax the registry")
        self.sb.wf("init", check=EXIT_OK)

    def test_editing_the_registry_file_does_not_move_an_open_work_order(self):
        # The discriminating question is not "is the work order still tdd@1"
        # — that holds whatever the file says. It is whether the *pin* still
        # governs: red must go on requiring a red receipt after the file
        # stops asking for one.
        self.sb.wf("advance", "WO-001", check=EXIT_OK)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "next", "WO-001").stdout)["missing"],
            ["receipt.red"],
        )
        self.relax_red_in_the_registry()

        proc = self.sb.wf("advance", "WO-001", check=EXIT_REFUSED)
        self.assertIn("receipt.red", proc.stderr)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "next", "WO-001").stdout)["missing"],
            ["receipt.red"],
            "the pinned spec governs, not the file",
        )

    def test_a_work_order_opened_after_the_edit_uses_the_edited_spec(self):
        # The control for the test above: without this, "still refuses" could
        # just mean the edit never took effect anywhere.
        self.relax_red_in_the_registry()
        self.sb.wf("open", "WO-002", "--kind", "tdd", "--objective", "after",
                   check=EXIT_OK)
        self.sb.wf("advance", "WO-002", check=EXIT_OK)
        self.assertEqual(
            json.loads(self.sb.wf("--json", "next", "WO-002").stdout)["missing"], []
        )
        # The edit is live for WO-002: red no longer demands a red receipt.
        # Entering impl still refuses, but for a different reason — that stage
        # seals a frozen set and there is no red receipt to seal. Two distinct
        # refusals is what proves the pin, not the file, decided the first one.
        proc = self.sb.wf("advance", "WO-002", check=EXIT_REFUSED)
        self.assertIn("a red receipt exists to seal the frozen set", proc.stderr)
        self.assertNotIn("evidence its gate kind requires", proc.stderr)

    def test_a_tampered_pinned_spec_is_an_integrity_failure(self):
        chain = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001").stdout)
        digest = chain["events"][0]["spec_sha256"]
        obj = self.sb.root / "objects" / digest[:2] / digest
        support.plant_bytes(
            obj,
            lambda raw: canonical.dumpb({**canonical.loads(raw), "version": 99}),
            expect="grow",   # version 1 -> 99 is one byte longer
            recognisable=lambda raw: canonical.loads(raw).get("kind") == "tdd",
        )
        proc = self.sb.wf("status", "WO-001")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("does not hash to its own name", proc.stderr)

    def test_a_missing_pinned_spec_is_an_integrity_failure(self):
        chain = json.loads(self.sb.wf("--json", "log", "--full", "--all", "WO-001").stdout)
        digest = chain["events"][0]["spec_sha256"]
        obj = self.sb.root / "objects" / digest[:2] / digest
        self.assertTrue(obj.exists(), "plant: the object must exist first")
        obj.unlink()
        self.assertFalse(obj.exists(), "plant: the object must be gone")
        proc = self.sb.wf("status", "WO-001")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("missing from the object store", proc.stderr)


class NextAndStatus(SandboxCase):
    def setUp(self):
        super().setUp()
        self.sb.wf("init", check=EXIT_OK)
        self.sb.wf("open", "WO-001", "--kind", "tdd", "--objective", "o", check=EXIT_OK)

    def test_next_names_the_exact_argv_that_advances(self):
        body = json.loads(self.sb.wf("--json", "next", "WO-001").stdout)
        support.assert_runnable(self, body["advances"])
        self.assertEqual(body["advances"][-2:], ["advance", "WO-001"])
        self.assertTrue(body["advances_complete"])
        self.assertEqual(body["missing"], [])
        self.assertIn("claim", body, "the Slice 2 shape must not move later")

    def test_next_with_no_argument_picks_an_open_work_order(self):
        body = json.loads(self.sb.wf("--json", "next").stdout)
        self.assertEqual(body["wo"], "WO-001")

    def test_status_without_an_argument_lists_every_work_order(self):
        self.sb.wf("open", "WO-002", "--kind", "artifact", "--objective", "two",
                   check=EXIT_OK)
        body = json.loads(self.sb.wf("--json", "status").stdout)
        self.assertEqual([w["wo"] for w in body["work_orders"]], ["WO-001", "WO-002"])
        self.assertEqual(body["work_orders"][1]["kind"], "artifact@1")

    def test_status_with_an_argument_gives_the_chain_and_attempt_counts(self):
        body = json.loads(self.sb.wf("--json", "status", "WO-001").stdout)
        self.assertEqual(body["attempts"], 1)
        self.assertEqual([e["type"] for e in support.without_binds(body["events"])],
                         ["wo.opened", "stage.entered"])
        self.assertEqual(body["seq"], len(body["events"]))

    def test_status_of_an_unknown_work_order_refuses(self):
        proc = self.sb.wf("status", "WO-404", check=EXIT_REFUSED)
        self.assertIn("work order exists", proc.stderr)


if __name__ == "__main__":
    unittest.main()
