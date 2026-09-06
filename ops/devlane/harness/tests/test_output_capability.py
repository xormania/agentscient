"""Independent tests for compile_launch output-capability admission.

Written from ops/devlane/dispatch/CONTRACT.md C2 (G=D, A=D, transport
separation, freshness, worker encoding, evidence custody),
harness-capabilities.md capability identity, task CONTRACT.md C2
outputs, and adoption review unit 4. Corrected from d3ea314b against
review 20260906T125857Z-review-claude-10edd9. Implementation was not
read.

Each test names the contract rule it pins:

  C1  G=D and A=D on an exact file leaf, with a verified synthetic
      mechanism; empty D is empty A; source isolation is mandatory
  C2  a parent-directory grant, chmod-only operations, a sandbox label
      or a clean-diff limit cannot satisfy the leaf
  C3  transport reservations stay distinct from output grants; admitted
      scratch alone supplies TMPDIR; environment is the closed trusted map
  C4  unsupported combinations and unmeasured/stale/failed/unresolved
      evidence refuse as output-capability before execution
  C5  launch evidence does not admit resume; freshness holds time/tuple
      still; independently held evidence refuses replaced candidate bytes
      without grading a self-consistent relabelled neighbour; witness
      missing/unreadable/digest-mismatch refuse, a clean neighbour does not
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
        denials = kwargs.pop("source_write_denials", self.fx.source_write_denials)
        reads = kwargs.pop("source_reads", self.fx.source_reads)
        identity = self.fx.matching_identity(
            selection,
            operation,
            outputs=identity_outputs,
            source_reads=reads,
            source_write_denials=denials,
            grammar=kwargs.get("grammar"),
            mechanism=kwargs.get("mechanism", "fixture-argv"),
            configuration=kwargs.get("configuration"),
            insertion=kwargs.get("insertion"),
            relay=kwargs.get("relay"),
        )
        return self.fx.transport(
            selection,
            operation,
            identity=identity,
            outputs=identity_outputs,
            source_reads=reads,
            source_write_denials=denials,
            **kwargs,
        )

    def test_exact_leaf_with_matching_actual_authority_admits(self):
        result = ats.compile_launch(
            self.selection, self.grants, self.transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        cap = result["capability"]
        self.assertEqual(set(cap), set(ats.WORKER_CAPABILITY_KEYS))
        self.assertEqual(cap["role"], "worker")
        self.assertNotIn("mcp", cap)
        self.assertNotIn("policy", cap)
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
        self.assertEqual(
            cap["scope"]["source_reads"],
            sorted(self.fx.source_reads),
        )
        self.assertEqual(
            cap["scope"]["source_write_denials"],
            sorted(self.fx.source_write_denials),
        )
        self.assertTrue(cap["scope"]["source_write_denials"])

    def test_empty_declarations_require_empty_actual_authority_and_isolation(self):
        selection = ats.selection_conductor()
        grants = ats.grants_for(selection)
        self.assertEqual(grants["outputs"], [])
        transport = self.fx.transport(selection)
        self.assertEqual(
            transport.evidence.identity["scope"]["outputs"],
            [],
        )
        self.assertTrue(
            transport.evidence.identity["scope"]["source_write_denials"],
        )
        self.assertTrue(transport.evidence.identity["scope"]["source_reads"])
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        cap = result["capability"]
        self.assertEqual(set(cap), set(ats.CONDUCT_CAPABILITY_KEYS))
        self.assertEqual(cap["scope"]["outputs"], [])
        self.assertEqual(grants["outputs"], [])
        self.assertTrue(cap["scope"]["source_write_denials"])
        self.assertTrue(cap["scope"]["source_reads"])

    def test_empty_denials_with_empty_outputs_do_not_discharge_isolation(self):
        selection = ats.selection_conductor()
        grants = ats.grants_for(selection)
        transport = self.fx.transport(
            selection,
            source_reads=self.fx.source_reads,
            source_write_denials=[],
        )
        identity = transport.evidence.identity
        identity["scope"]["source_write_denials"] = []
        transport.evidence.identity = identity
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)

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

    def test_conduct_identity_cannot_admit_a_worker_selection(self):
        conduct_transport = self.fx.transport(ats.selection_conductor())
        result = ats.compile_launch(
            self.selection, self.grants, conduct_transport, [], "launch",
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
        isolation_denials = (
            self.fx.source_write_denials if denials is None else denials
        )
        identity = self.fx.matching_identity(
            self.selection,
            "launch",
            outputs=identity_outputs,
            source_reads=self.fx.source_reads,
            source_write_denials=isolation_denials,
            limits=limits or [],
            platform=platform,
        )
        transport = self.fx.transport(
            self.selection,
            identity=identity,
            outputs=identity_outputs,
            source_reads=self.fx.source_reads,
            source_write_denials=isolation_denials,
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
        identity_outputs = [
            ats.capability_output("file", self.leaf_abs, OPS_WRITE),
            ats.capability_output(
                "scratch",
                self.scratch_abs,
                ("create", "write", "delete"),
            ),
        ]
        identity = self.fx.matching_identity(
            self.selection,
            "launch",
            outputs=identity_outputs,
        )
        transport = self.fx.transport(
            self.selection,
            identity=identity,
            outputs=identity_outputs,
        )
        result = ats.compile_launch(
            self.selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        env = result["environment"]
        self.assertEqual(
            env,
            ats.expected_environment(transport, tmpdir=self.scratch_abs),
        )
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
        identity_outputs = [
            ats.capability_output("file", self.leaf_abs, OPS_WRITE),
        ]
        identity = self.fx.matching_identity(
            self.selection,
            "launch",
            outputs=identity_outputs,
        )
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
            outputs=identity_outputs,
        )
        result = ats.compile_launch(
            self.selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        env = result["environment"]
        self.assertEqual(env, ats.expected_environment(transport))
        self.assertNotEqual(env.get("TMPDIR"), inherited)
        self.assertNotIn("TMPDIR", env)

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
        previous = {name: os.environ.get(name) for name in ("PATH", "HOME")}
        os.environ["PATH"] = "/opt/vendor/bin"
        os.environ["HOME"] = "/opt/vendor/home"

        def restore():
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.addCleanup(restore)
        transport = self.fx.transport(selection)
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        env = result["environment"]
        self.assertEqual(env, ats.expected_environment(transport))
        self.assertNotEqual(env.get("PATH"), "/opt/vendor/bin")
        self.assertNotEqual(env.get("HOME"), "/opt/vendor/home")
        self.assertIn("FIXTURE_MARK", env)


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
        identity = self.fx.matching_identity(
            self.selection,
            "launch",
            outputs=[ats.capability_output("file", self.leaf_abs, OPS_WRITE)],
        )
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
        transport = self.fx.resume_transport(
            self.selection, self.grants, [], identity=identity,
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
        identity = self.fx.matching_identity(
            selection,
            "launch",
            outputs=[],
            limits=["unsupported-file-leaf"],
            mechanism="fixture-argv-no-leaf",
        )
        transport = self.fx.transport(
            selection,
            identity=identity,
            mechanism="fixture-argv-no-leaf",
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
        exe = transport.executable["path"]
        before = os.stat(exe)
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        after = os.stat(exe)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)


class FaultyControlsAreDiscriminated(unittest.TestCase):
    """C5 — held evidence stays fixed; candidate bytes cannot rewrite custody."""

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
        identity_outputs = [
            ats.capability_output("file", self.leaf_abs, OPS_WRITE),
        ]
        self.passing_identity = self.fx.matching_identity(
            self.selection,
            "launch",
            outputs=identity_outputs,
        )
        self.identity_outputs = identity_outputs

    def test_replaced_candidate_bytes_differ_from_the_held_verification_handle(self):
        passing_transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
        )
        held_sha = passing_transport.evidence.verification["sha256"]
        held_identity_sha = passing_transport.evidence.identity["mock"]["verification"]["sha256"]
        self.assertEqual(held_sha, self.fx.verification_sha256)
        self.assertEqual(held_identity_sha, held_sha)
        joined = self.fx.held_path(passing_transport.evidence.verification["path"])
        self.assertEqual(joined, self.fx.verification_path.resolve())
        self.assertTrue(joined.is_file())
        before = self.fx.verification_path.read_bytes()
        self.assertIn(b"leaf-write-and-source-deny", before)
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
        candidate_sha = ats.sha256_bytes(after)
        self.assertNotEqual(candidate_sha, held_sha)
        self.assertIn(b"chmod-then-restore-control", after)
        self.assertIn(b"synthetic", after)
        self.assertEqual(
            passing_transport.evidence.verification["sha256"],
            held_sha,
        )
        candidate_identity = deepcopy(self.passing_identity)
        candidate_identity["mock"]["verification"]["sha256"] = candidate_sha
        self.assertNotEqual(
            candidate_identity["mock"]["verification"]["sha256"],
            passing_transport.evidence.identity["mock"]["verification"]["sha256"],
        )
        result = ats.compile_launch(
            self.selection, self.grants, passing_transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)

    def test_relabelled_self_consistent_neighbour_is_not_a_compile_fault(self):
        passing_transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
        )
        passing = ats.compile_launch(
            self.selection, self.grants, passing_transport, [], "launch",
        )
        relabelled = ats.canonical_json({
            "kind": "receipt",
            "claim": "synthetic leaf/scratch admission control",
            "control": "relabelled-leaf-write-and-source-deny",
            "result": "PASS",
        }).encode("utf-8")
        self.assertIn(b'"result":"PASS"', relabelled)
        self.assertNotEqual(relabelled, self.fx.passing_verification)
        relabel_rel = "relabelled-verification.json"
        ats.plant_bytes(
            self.fx.held_path(relabel_rel),
            relabelled,
            recognisable=b"relabelled-leaf-write-and-source-deny",
        )
        neighbour_sha = ats.sha256_bytes(relabelled)
        self.assertNotEqual(neighbour_sha, self.fx.verification_sha256)
        neighbour_verification = {
            "path": relabel_rel,
            "sha256": neighbour_sha,
        }
        neighbour_identity = deepcopy(self.passing_identity)
        neighbour_identity["mock"]["verification"] = dict(neighbour_verification)
        neighbour_transport = self.fx.transport(
            self.selection,
            identity=neighbour_identity,
            outputs=self.identity_outputs,
            verification=neighbour_verification,
        )
        self.assertEqual(
            neighbour_transport.evidence.verification["sha256"],
            neighbour_sha,
        )
        self.assertEqual(
            neighbour_transport.evidence.identity["mock"]["verification"]["sha256"],
            neighbour_sha,
        )
        neighbour = ats.compile_launch(
            self.selection, self.grants, neighbour_transport, [], "launch",
        )
        self.assertTrue(ats.is_success(passing), ats.explain(passing))
        self.assertTrue(ats.is_success(neighbour), ats.explain(neighbour))
        self.assertNotEqual(
            passing_transport.evidence.verification["sha256"],
            neighbour_transport.evidence.verification["sha256"],
        )

    def test_independent_observation_of_a_forbidden_write_is_held_apart(self):
        snapshot_file = self.fx.snapshot / "held-source.txt"
        before = snapshot_file.read_bytes()
        self.assertIn(b"synthetic-source", before)
        planted = ats.plant_mutate(
            snapshot_file,
            lambda body: body + b"FORBIDDEN_WRITE\n",
            recognisable=b"FORBIDDEN_WRITE",
        )
        self.assertEqual(planted, before)
        after = snapshot_file.read_bytes()
        self.assertNotEqual(after, before)
        observation = ats.canonical_json({
            "kind": "independent-observation",
            "control": "source-write-then-restore",
            "path": str(snapshot_file.resolve()),
            "result": "FAIL",
            "bytes_sha256": ats.sha256_bytes(after),
        }).encode("utf-8")
        obs_path = self.fx.evidence / "independent-observation.json"
        ats.plant_bytes(
            obs_path,
            observation,
            recognisable=b"source-write-then-restore",
        )
        transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
        )
        self.assertEqual(
            transport.evidence.verification["sha256"],
            self.fx.verification_sha256,
        )
        self.assertNotEqual(
            ats.sha256_bytes(observation),
            transport.evidence.verification["sha256"],
        )
        self.assertTrue(transport.evidence.identity["scope"]["source_write_denials"])
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        # Compile checks held verification bytes/digests, not this observation
        # file. The observation remains independently held for the launch
        # evidence owner; matching held PASS bytes still compile.
        self.assertTrue(ats.is_success(result), ats.explain(result))
        self.assertIn(b"FORBIDDEN_WRITE", snapshot_file.read_bytes())

    def test_descriptor_adapter_fields_must_equal_capability_identity(self):
        transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
        )
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        cap = result["capability"]["adapter"]
        desc = transport.manifest["adapter"]
        self.assertEqual(set(cap), set(ats.WORKER_ADAPTER_KEYS))
        self.assertEqual(set(desc), set(ats.WORKER_MANIFEST_ADAPTER_KEYS))
        self.assertEqual(cap["revision"], desc["revision"])
        self.assertEqual(cap["mechanism"], desc["mechanism"])
        self.assertEqual(cap["grammar_sha256"], desc["grammar_sha256"])
        self.assertEqual(cap["config_sha256"], desc["config_sha256"])
        self.assertEqual(
            result["capability"]["harness"]["executable"]["sha256"],
            desc["executable_sha256"],
        )
        self.assertNotIn("normalizer_sha256", cap)
        self.assertNotIn("mcp", result["capability"])
        self.assertEqual(
            cap["config_sha256"],
            self.fx.declared_config_sha256(self.selection),
        )
        self.assertNotEqual(cap["config_sha256"], ats.digest_name("config"))

    def test_conduct_descriptor_adapter_fields_must_equal_capability_identity(self):
        selection = ats.selection_conductor()
        grants = ats.grants_for(selection)
        transport = self.fx.transport(selection)
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_success(result), ats.explain(result))
        cap = result["capability"]["adapter"]
        desc = transport.manifest["adapter"]
        self.assertEqual(set(cap), set(ats.CONDUCT_ADAPTER_KEYS))
        self.assertEqual(set(desc), set(ats.CONDUCT_MANIFEST_ADAPTER_KEYS))
        self.assertEqual(cap["revision"], desc["revision"])
        self.assertEqual(cap["mechanism"], desc["mechanism"])
        self.assertEqual(cap["grammar_sha256"], desc["grammar_sha256"])
        self.assertEqual(cap["normalizer_sha256"], desc["normalizer_sha256"])
        self.assertEqual(cap["config_sha256"], desc["config_sha256"])
        self.assertEqual(
            result["capability"]["harness"]["executable"]["sha256"],
            desc["executable_sha256"],
        )

    def test_conduct_normalizer_mismatch_is_stale(self):
        selection = ats.selection_conductor()
        grants = ats.grants_for(selection)
        transport = self.fx.transport(selection)
        identity = deepcopy(transport.evidence.identity)
        identity["adapter"]["normalizer_sha256"] = ats.digest_name(
            "other-normalizer",
        )
        transport.evidence.identity = identity
        self.assertNotEqual(
            transport.evidence.identity["adapter"]["normalizer_sha256"],
            transport.manifest["adapter"]["normalizer_sha256"],
        )
        result = ats.compile_launch(
            selection, grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("stale", line)

    def test_missing_witness_is_unresolved(self):
        missing = {
            "path": "absent-witness.json",
            "sha256": self.fx.witness_sha256,
        }
        transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
            witness=missing,
        )
        self.assertEqual(transport.evidence.witness["path"], missing["path"])
        self.assertEqual(
            transport.evidence.witness["sha256"], missing["sha256"],
        )
        joined = self.fx.held_path(transport.evidence.witness["path"])
        self.assertFalse(joined.exists())
        self.assertTrue(self.fx.witness_path.is_file())
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("unresolved", line)

    def test_unreadable_witness_is_unresolved(self):
        transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
        )
        held = dict(transport.evidence.witness)
        joined = self.fx.held_path(held["path"])
        self.assertTrue(joined.is_file())
        before_mode = joined.stat().st_mode
        os.chmod(joined, 0)

        def restore_mode():
            os.chmod(joined, before_mode)

        self.addCleanup(restore_mode)
        with self.assertRaises(OSError):
            joined.read_bytes()
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)
        self.assertIn("unresolved", line)

    def test_witness_digest_mismatch_refuses_held_bytes(self):
        transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
        )
        held = dict(transport.evidence.witness)
        self.assertEqual(held["path"], self.fx.witness_rel)
        self.assertEqual(held["sha256"], self.fx.witness_sha256)
        before = self.fx.witness_path.read_bytes()
        self.assertIn(b"source-isolation-and-leaf", before)
        planted = ats.plant_mutate(
            self.fx.witness_path,
            lambda body: body.replace(
                b"source-isolation-and-leaf",
                b"source-isolation-and-chmod",
            ),
            recognisable=b"source-isolation-and-chmod",
        )
        self.assertEqual(planted, before)
        after = self.fx.witness_path.read_bytes()
        self.assertNotEqual(after, before)
        candidate_sha = ats.sha256_bytes(after)
        self.assertNotEqual(candidate_sha, held["sha256"])
        self.assertEqual(transport.evidence.witness["sha256"], held["sha256"])
        result = ats.compile_launch(
            self.selection, self.grants, transport, [], "launch",
        )
        self.assertTrue(ats.is_refusal(result), ats.explain(result))
        line = ats.refusal_text(result)
        self.assertTrue(line.startswith(ats.CAPABILITY_REFUSAL_PREFIX), line)

    def test_self_consistent_witness_neighbour_is_not_a_compile_fault(self):
        passing_transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
        )
        passing = ats.compile_launch(
            self.selection, self.grants, passing_transport, [], "launch",
        )
        neighbour_bytes = ats.canonical_json({
            "kind": "witness",
            "claim": "synthetic capability witness",
            "control": "relabelled-source-isolation-and-leaf",
            "result": "PASS",
        }).encode("utf-8")
        self.assertNotEqual(neighbour_bytes, self.fx.passing_witness)
        neighbour_rel = "neighbour-witness.json"
        ats.plant_bytes(
            self.fx.held_path(neighbour_rel),
            neighbour_bytes,
            recognisable=b"relabelled-source-isolation-and-leaf",
        )
        neighbour_sha = ats.sha256_bytes(neighbour_bytes)
        neighbour_handle = {
            "path": neighbour_rel,
            "sha256": neighbour_sha,
        }
        neighbour_transport = self.fx.transport(
            self.selection,
            identity=deepcopy(self.passing_identity),
            outputs=self.identity_outputs,
            witness=neighbour_handle,
        )
        self.assertEqual(
            neighbour_transport.evidence.witness["sha256"],
            neighbour_sha,
        )
        self.assertTrue(self.fx.held_path(neighbour_rel).is_file())
        self.assertTrue(self.fx.witness_path.is_file())
        neighbour = ats.compile_launch(
            self.selection, self.grants, neighbour_transport, [], "launch",
        )
        self.assertTrue(ats.is_success(passing), ats.explain(passing))
        self.assertTrue(ats.is_success(neighbour), ats.explain(neighbour))
        self.assertNotEqual(
            passing_transport.evidence.witness["sha256"],
            neighbour_transport.evidence.witness["sha256"],
        )
