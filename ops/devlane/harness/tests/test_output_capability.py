"""Independent tests for compile_launch output-capability admission.

Written from ops/devlane/dispatch/CONTRACT.md C2 (G=D, A=D, transport
separation, freshness), harness-capabilities.md capability identity,
task CONTRACT.md C2 outputs, and adoption review unit 4. Implementation
was not read.

Each test names the contract rule it pins:

  C1  G=D and A=D on an exact file leaf, with a verified synthetic
      mechanism; empty D is empty A
  C2  a parent-directory grant, chmod-only operations, a sandbox label
      or a clean-diff limit cannot satisfy the leaf
  C3  transport reservations stay distinct from output grants; admitted
      scratch alone supplies TMPDIR
  C4  unsupported combinations and unmeasured/stale/failed/unresolved
      evidence refuse as output-capability before execution
  C5  launch evidence does not admit resume; freshness holds time/tuple
      still, and discriminates faulty controls from passing neighbours
"""

from __future__ import annotations

import os
import unittest
from copy import deepcopy

import adapter_test_support as ats

LEAF = "REPORT.md"
SCRATCH = "tmp"
OPS_WRITE = ("create", "write")


class OutputCapabilitySeam(unittest.TestCase):
    """C1 — compile_launch admits exact leaf equality, not a missing name."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_worker()
        self.leaf_rel = LEAF
        self.leaf_abs = str((self.fx.out / LEAF).resolve())
        self.outputs = [
            {"kind": "file", "path": LEAF, "artifact": "report"},
        ]
        self.grants = ats.grants_for(
            self.selection,
            outputs=self.outputs,
            role_grants={"repository": [], "outputs": [LEAF]},
            job_grants={"repository": [], "outputs": [LEAF]},
        )
        self.identity_outputs = [
            ats.capability_output("file", self.leaf_abs, OPS_WRITE),
        ]
        self.transport = self._transport(self.identity_outputs)

    def _transport(self, identity_outputs, **kwargs):
        selection = kwargs.pop("selection", self.selection)
        operation = kwargs.pop("operation", "launch")
        adapter = ats.adapter_descriptor()
        exe = self.fx.executables[selection["harness"]]
        adapter["executable_sha256"] = exe["sha256"]
        identity = ats.identity_for(
            selection,
            operation,
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=identity_outputs,
            source_reads=[str(self.fx.root / "snapshot")],
            source_write_denials=[
                str(self.fx.root / "snapshot"),
                str(self.fx.root / "snapshot" / ".git"),
            ],
        )
        identity["mock"]["verification"] = {
            "path": self.fx.verification_rel,
            "sha256": self.fx.verification_sha256,
        }
        return self.fx.transport(
            selection,
            operation,
            identity=identity,
            **kwargs,
        )

    def test_exact_leaf_with_matching_actual_authority_admits(self):
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        cap = result["capability"]
        admitted = cap["scope"]["outputs"]
        self.assertEqual(len(admitted), 1, admitted)
        self.assertEqual(admitted[0]["kind"], "file")
        self.assertEqual(admitted[0]["path"], self.leaf_abs)
        self.assertEqual(admitted[0]["operations"], sorted(OPS_WRITE))
        self.assertNotEqual(
            admitted[0]["path"],
            str(self.fx.out.resolve()),
            "A must be the leaf, not its parent directory",
        )

    def test_empty_declarations_require_empty_actual_authority(self):
        selection = ats.selection_conductor()
        grants = ats.grants_for(selection)
        transport = self.fx.transport(selection)
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        self.assertEqual(result["capability"]["scope"]["outputs"], [])
        self.assertEqual(grants["outputs"], [])

    def test_prompt_prose_does_not_create_a_grant(self):
        selection = ats.selection_worker()
        grants = ats.grants_for(selection, outputs=[])
        transport = self._transport(
            [ats.capability_output("file", self.leaf_abs, OPS_WRITE)],
            selection=selection,
        )
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)


class LeafEqualityRefusesBroaderProofs(unittest.TestCase):
    """C2 — parent directory, chmod, sandbox label, clean diff are not A=D."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_worker()
        self.leaf_abs = str((self.fx.out / LEAF).resolve())
        self.out_abs = str(self.fx.out.resolve())
        self.grants = ats.grants_for(
            self.selection,
            outputs=[{"kind": "file", "path": LEAF, "artifact": "report"}],
            role_grants={"repository": [], "outputs": [LEAF]},
            job_grants={"repository": [], "outputs": [LEAF]},
        )

    def _compile(self, identity_outputs, *, platform=None, limits=None,
                 denials=None):
        exe = self.fx.executables[self.selection["harness"]]
        adapter = ats.adapter_descriptor()
        adapter["executable_sha256"] = exe["sha256"]
        identity = ats.identity_for(
            self.selection,
            "launch",
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=identity_outputs,
            source_write_denials=denials or [],
            limits=limits or [],
            platform=platform,
        )
        identity["mock"]["verification"] = {
            "path": self.fx.verification_rel,
            "sha256": self.fx.verification_sha256,
        }
        transport = self.fx.transport(
            self.selection, identity=identity,
        )
        return ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )

    def test_parent_directory_grant_does_not_satisfy_the_leaf(self):
        result = self._compile([
            ats.capability_output("file", self.out_abs, OPS_WRITE),
        ])
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)

    def test_chmod_only_operations_are_not_write_authority(self):
        result = self._compile([
            ats.capability_output("file", self.leaf_abs, ("chmod",)),
        ])
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        self.assertTrue(
            ats.refusal_text(result).startswith(ats.CAPABILITY_REFUSAL_PREFIX),
            ats.explain(result),
        )

    def test_sandbox_label_is_not_the_security_oracle(self):
        platform = {
            "os": "linux",
            "sandbox": {"name": "workspace-write", "version": "label-only"},
            "filesystem": {"name": "posix", "alias_semantics": "no-follow"},
        }
        result = self._compile(
            [ats.capability_output("file", self.out_abs, OPS_WRITE)],
            platform=platform,
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertNotIn("workspace-write", line)

    def test_clean_diff_limit_without_source_denials_is_not_prevention(self):
        result = self._compile(
            [ats.capability_output("file", self.leaf_abs, OPS_WRITE)],
            limits=["clean-diff"],
            denials=[],
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        self.assertTrue(
            ats.refusal_text(result).startswith(ats.CAPABILITY_REFUSAL_PREFIX),
            ats.explain(result),
        )

    def test_generic_capability_set_containing_d_does_not_prove_a_equals_d(self):
        result = self._compile([
            ats.capability_output("scratch", self.out_abs, ("create", "write", "delete", "rename", "chmod")),
        ])
        self.assertTrue(ats.is_refusal(result), ats.explain(result))


class TransportAndScratchSeparation(unittest.TestCase):
    """C3 — reservations are not output grants; scratch owns TMPDIR."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_worker()
        self.scratch_abs = str((self.fx.out / SCRATCH).resolve())
        self.leaf_abs = str((self.fx.out / LEAF).resolve())

    def test_scratch_sets_tmpdir_to_the_admitted_subtree(self):
        outputs = [
            {"kind": "file", "path": LEAF, "artifact": "report"},
            {"kind": "scratch", "path": SCRATCH},
        ]
        grants = ats.grants_for(
            self.selection,
            outputs=outputs,
            role_grants={"repository": [], "outputs": [LEAF, SCRATCH]},
            job_grants={"repository": [], "outputs": [LEAF, SCRATCH]},
        )
        exe = self.fx.executables[self.selection["harness"]]
        adapter = ats.adapter_descriptor()
        adapter["executable_sha256"] = exe["sha256"]
        identity = ats.identity_for(
            self.selection,
            "launch",
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=[
                ats.capability_output("file", self.leaf_abs, OPS_WRITE),
                ats.capability_output(
                    "scratch",
                    self.scratch_abs,
                    ("create", "write", "delete"),
                ),
            ],
            source_write_denials=[str(self.fx.root / "snapshot")],
        )
        identity["mock"]["verification"] = {
            "path": self.fx.verification_rel,
            "sha256": self.fx.verification_sha256,
        }
        transport = self.fx.transport(self.selection, identity=identity)
        result = ats.compile_launch(
            self.selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        env = result["environment"]
        self.assertEqual(env.get("TMPDIR"), self.scratch_abs)
        reservations = result["reservations"]
        self.assertIn("last-message.json", reservations)
        self.assertIn("COMMIT_MSG", reservations)
        self.assertNotIn(SCRATCH, reservations)
        self.assertNotIn("tmp", reservations)

    def test_without_scratch_tmpdir_is_not_inherited(self):
        outputs = [{"kind": "file", "path": LEAF, "artifact": "report"}]
        grants = ats.grants_for(
            self.selection,
            outputs=outputs,
            role_grants={"repository": [], "outputs": [LEAF]},
            job_grants={"repository": [], "outputs": [LEAF]},
        )
        exe = self.fx.executables[self.selection["harness"]]
        adapter = ats.adapter_descriptor()
        adapter["executable_sha256"] = exe["sha256"]
        identity = ats.identity_for(
            self.selection,
            "launch",
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=[ats.capability_output("file", self.leaf_abs, OPS_WRITE)],
            source_write_denials=[str(self.fx.root / "snapshot")],
        )
        identity["mock"]["verification"] = {
            "path": self.fx.verification_rel,
            "sha256": self.fx.verification_sha256,
        }
        inherited = str(self.fx.root / "inherited-tmp")
        previous = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = inherited

        def restore_tmpdir():
            if previous is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = previous

        self.addCleanup(restore_tmpdir)
        transport = self.fx.transport(
            self.selection,
            identity=identity,
            configuration={"TMPDIR": inherited},
        )
        result = ats.compile_launch(
            self.selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        env = result["environment"]
        self.assertNotEqual(env.get("TMPDIR"), inherited)
        self.assertFalse(
            env.get("TMPDIR") == inherited,
            "no inherited temporary path may add worker write authority",
        )

    def test_transport_leaf_cannot_be_declared_as_an_output(self):
        outputs = [
            {"kind": "file", "path": "last-message.json", "artifact": "message"},
        ]
        grants = ats.grants_for(
            self.selection,
            outputs=outputs,
            reservations=list(ats.TRANSPORT_RESERVED),
        )
        transport = self.fx.transport(self.selection)
        result = ats.compile_launch(
            self.selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))

    def test_environment_does_not_inherit_path_or_config_overlays(self):
        selection = ats.selection_conductor()
        grants = ats.grants_for(selection)
        transport = self.fx.transport(
            selection,
            configuration={"PATH": "/opt/vendor/bin", "HOME": "/opt/vendor/home"},
        )
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        env = result["environment"]
        self.assertNotEqual(env.get("PATH"), "/opt/vendor/bin")
        self.assertNotEqual(env.get("HOME"), "/opt/vendor/home")


class UnsupportedAndUnmeasured(unittest.TestCase):
    """C4 — unsupported, stale, failed, unresolved: refuse, never run."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_worker()
        self.leaf_abs = str((self.fx.out / LEAF).resolve())
        self.grants = ats.grants_for(
            self.selection,
            outputs=[{"kind": "file", "path": LEAF, "artifact": "report"}],
            role_grants={"repository": [], "outputs": [LEAF]},
            job_grants={"repository": [], "outputs": [LEAF]},
        )

    def _identity(self, **overrides):
        exe = self.fx.executables[self.selection["harness"]]
        adapter = ats.adapter_descriptor()
        adapter["executable_sha256"] = exe["sha256"]
        identity = ats.identity_for(
            self.selection,
            "launch",
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=[ats.capability_output("file", self.leaf_abs, OPS_WRITE)],
            source_write_denials=[str(self.fx.root / "snapshot")],
        )
        identity["mock"]["verification"] = {
            "path": self.fx.verification_rel,
            "sha256": self.fx.verification_sha256,
        }
        identity.update(overrides)
        return identity

    def test_null_identity_is_unresolved_and_does_not_admit(self):
        transport = self.fx.transport(
            self.selection, witness_identity="null",
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("unresolved", line)
        self.assertNotIn("UNREACHABLE", line)

    def test_missing_checked_at_is_unresolved(self):
        identity = self._identity()
        transport = self.fx.transport(
            self.selection, identity=identity, checked_at=None,
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("unresolved", line)

    def test_changed_tuple_member_is_stale(self):
        identity = self._identity()
        identity["adapter"]["revision"] = ats.digest_name("other-adapter")
        transport = self.fx.transport(self.selection, identity=identity)
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("stale", line)

    def test_launch_witness_does_not_admit_resume(self):
        identity = self._identity()
        identity["operation"] = "launch"
        transport = self.fx.transport(
            self.selection, "resume", identity=identity,
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "resume",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)

    def test_age_bound_equality_passes_and_crossing_it_expires(self):
        identity = self._identity()
        at_bound = self.fx.transport(
            self.selection,
            identity=identity,
            checked_at="2026-09-06T11:59:30Z",
            max_age_seconds=60,
        )
        # admission_at is 2026-09-06T12:00:30Z; delta 60s equals the bound.
        ok = ats.compile_launch(
            self.selection, self.grants, at_bound, [], "launch",
        )
        self.assertTrue(ats.is_success(ok), ats.explain(ok))
        expired = self.fx.transport(
            self.selection,
            identity=deepcopy(identity),
            checked_at="2026-09-06T11:59:29Z",
            max_age_seconds=60,
        )
        refused = ats.compile_launch(
            self.selection, self.grants, expired, [], "launch",
        )
        self.assertTrue(ats.is_refusal(refused), ats.explain(refused))
        self.assertIn("stale", ats.refusal_text(refused))

    def test_matching_evidence_without_age_policy_does_not_expire_by_age(self):
        identity = self._identity()
        old = self.fx.transport(
            self.selection,
            identity=identity,
            checked_at="2020-01-01T00:00:00Z",
            max_age_seconds=None,
        )
        result = ats.compile_launch(
            self.selection, self.grants, old, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))

    def test_unsupported_harness_operation_output_combination_refuses(self):
        selection = ats.selection_worker(harness="grok")
        grants = ats.grants_for(
            selection,
            outputs=[{"kind": "file", "path": LEAF, "artifact": "report"}],
        )
        transport = self.fx.transport(
            selection, mechanism="fixture-argv-no-leaf",
        )
        # Witness that cannot enforce a file leaf (scratch-only mechanism).
        exe = self.fx.executables["grok"]
        adapter = transport["adapter"]
        identity = ats.identity_for(
            selection,
            "launch",
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=[],
            limits=["unsupported-file-leaf"],
        )
        transport = self.fx.transport(
            selection, identity=identity, mechanism="fixture-argv-no-leaf",
        )
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("unsupported", line)

    def test_compile_launch_does_not_create_the_child_on_refusal(self):
        transport = self.fx.transport(
            self.selection, witness_identity="null",
        )
        exe = transport["executable"]["path"]
        before = os.stat(exe)
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        after = os.stat(exe)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)


class FaultyControlsAreDiscriminated(unittest.TestCase):
    """C5 — planted faulty controls fire; clean neighbours stay distinct."""

    def setUp(self):
        self.fx = ats.FixtureRoot()
        self.addCleanup(self.fx.close)
        self.selection = ats.selection_worker()
        self.leaf_abs = str((self.fx.out / LEAF).resolve())
        self.grants = ats.grants_for(
            self.selection,
            outputs=[{"kind": "file", "path": LEAF, "artifact": "report"}],
            role_grants={"repository": [], "outputs": [LEAF]},
            job_grants={"repository": [], "outputs": [LEAF]},
        )
        exe = self.fx.executables[self.selection["harness"]]
        adapter = ats.adapter_descriptor()
        adapter["executable_sha256"] = exe["sha256"]
        self.passing_identity = ats.identity_for(
            self.selection,
            "launch",
            executable_path=exe["path"],
            executable_sha256=exe["sha256"],
            adapter=adapter,
            outputs=[ats.capability_output("file", self.leaf_abs, OPS_WRITE)],
            source_write_denials=[str(self.fx.root / "snapshot")],
        )
        self.passing_identity["mock"]["verification"] = {
            "path": self.fx.verification_rel,
            "sha256": self.fx.verification_sha256,
        }

    def test_passing_and_faulty_verification_hashes_differ(self):
        before = self.fx.verification_path.read_bytes()
        self.assertIn(b"leaf-write-and-source-deny", before)
        passing_sha = self.fx.verification_sha256
        planted = ats.plant_mutate(
            self.fx.verification_path,
            lambda body: body.replace(
                b"leaf-write-and-source-deny",
                b"chmod-then-restore-control",
            ),
            recognisable=b"chmod-then-restore-control",
        )
        self.assertEqual(planted, before)
        after = self.fx.verification_path.read_bytes()
        self.assertNotEqual(after, before)
        faulty_sha = ats.sha256_bytes(after)
        self.assertNotEqual(faulty_sha, passing_sha)
        self.assertIn(b"chmod-then-restore-control", after)
        self.assertIn(b"synthetic", after)
        faulty_identity = deepcopy(self.passing_identity)
        faulty_identity["mock"]["verification"]["sha256"] = faulty_sha
        result = ats.compile_launch(
            self.selection,
            self.grants,
            self.fx.transport(self.selection, identity=faulty_identity),
            [],
            "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))

    def test_faulty_control_refuses_while_the_passing_neighbour_would_bind(self):
        passing_transport = self.fx.transport(
            self.selection, identity=deepcopy(self.passing_identity),
        )
        passing = ats.compile_launch(
            self.selection, self.grants, passing_transport, [], "launch",
        )
        ats.plant_mutate(
            self.fx.verification_path,
            lambda body: body.replace(
                b'"result":"PASS"',
                b'"result":"FAIL"',
            ),
            recognisable=b'"result":"FAIL"',
        )
        faulty_sha = ats.sha256_bytes(self.fx.verification_path.read_bytes())
        self.assertNotEqual(faulty_sha, self.fx.verification_sha256)
        faulty_identity = deepcopy(self.passing_identity)
        faulty_identity["mock"]["verification"]["sha256"] = faulty_sha
        faulty_transport = self.fx.transport(
            self.selection, identity=faulty_identity,
        )
        faulty = ats.compile_launch(
            self.selection, self.grants, faulty_transport, [], "launch",
        )
        self.assertTrue(ats.is_success(passing), ats.explain(passing))
        self.assertTrue(ats.is_refusal(faulty), ats.explain(faulty))
        self.assertNotEqual(passing, faulty)
        line = ats.refusal_text(faulty)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertNotEqual(
            passing_transport["witness"]["identity"]["mock"]["verification"]["sha256"],
            faulty_transport["witness"]["identity"]["mock"]["verification"]["sha256"],
        )

    def test_descriptor_adapter_fields_must_equal_capability_identity(self):
        transport = self.fx.transport(
            self.selection, identity=deepcopy(self.passing_identity),
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        cap = result["capability"]["adapter"]
        desc = transport["adapter"]
        self.assertEqual(cap["revision"], desc["revision"])
        self.assertEqual(cap["mechanism"], desc["mechanism"])
        self.assertEqual(cap["grammar_sha256"], desc["grammar_sha256"])
        self.assertEqual(cap["normalizer_sha256"], desc["normalizer_sha256"])
        self.assertEqual(cap["config_sha256"], desc["config_sha256"])
        self.assertEqual(
            result["capability"]["harness"]["executable"]["sha256"],
            desc["executable_sha256"],
        )
