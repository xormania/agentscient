"""verify — recompute every hash and link; --deep re-checks the evidence.

CI is a verifier, never a decider (PLAN §7): this re-checks recorded
evidence and fails on mismatch. It originates no state and writes nothing.

The shallow pass covers what the database claims about itself. ``--deep``
adds the three things that need the repository:

* **red receipts are genuine** — the frozen-set manifest is re-hashed from
  the blobs in the tree at the commit the receipt recorded, and must equal
  the recorded digest; **green is verified against the frozen set** the same
  way. A receipt recorded with ``tree_dirty`` is verifiable only against its
  own output hashes, which is D3's trade-off, reported rather than hidden.
* **commit cross-binds** — every ``commit.landed`` names a commit that
  exists, is an ancestor of HEAD, and whose tree holds a chain file ending
  at exactly the recorded head.
* **the append-only prefix walk** — each historical version of a chain
  file, walked through the ancestors that touched it, is a byte-prefix of
  its successor. Dropped or rewritten rows are caught even when the rows
  naming them are gone.

What none of this survives is a coordinated rewrite of both git history and
the chain: the walk would be walking the rewritten ancestors. What survives
that is only what the forge retains outside the tree — protected refs that
cannot be force-pushed, PR records, and check runs pinned to observed SHAs.
A local-only clone has none of those, and this says so rather than claiming
otherwise.
"""

from __future__ import annotations

from pathlib import Path

import canonical
import chain as chainmod
import gitio
import receipts
from errors import Integrity, Refusal


def check_export_matches_database(ctx, wo_id: str) -> None:
    """The export is the evidence, so it must equal the payload bytes."""
    expected = gitio.chain_bytes(ctx.store, wo_id)
    path = ctx.chains_dir / f"{wo_id}.jsonl"
    actual = path.read_bytes() if path.exists() else b""
    if actual == expected:
        return
    if expected.startswith(actual):
        # A pure append: the database is ahead of the file, which is what a
        # deferred --no-commit leaves behind. Recoverable, so a refusal.
        missing = expected[len(actual):].count(b"\n")
        raise Refusal(
            "the export is current",
            actual=f"{wo_id}.jsonl is behind the chain by {missing} event(s)",
            needed="wf export, or wf commit to flush and bind",
            wo=wo_id,
        )
    raise Integrity(
        "the exported chain diverges from the recorded payload bytes",
        wo=wo_id,
        detail=f"{len(actual)} bytes on disk, {len(expected)} recorded",
    )


def check_export_is_complete(ctx) -> None:
    """Every exported chain is present in the database.

    Without this, a rebuild that failed part-way leaves an empty database
    that verifies perfectly — "0 work orders, ok" — over an export full of
    evidence it never read. A verifier that reports success because it found
    nothing to check is the exact failure this system exists to prevent.
    """
    if not ctx.chains_dir.exists():
        return
    known = {row["wo_id"] for row in ctx.store.list_work_orders()}
    for path in sorted(ctx.chains_dir.glob("*.jsonl")):
        wo_id = path.name[: -len(".jsonl")]
        if wo_id not in known:
            lines = len([ln for ln in path.read_bytes().split(b"\n") if ln.strip()])
            raise Integrity(
                "the database is missing a work order the export records",
                wo=wo_id,
                detail=(
                    f"{path.name} holds {lines} event(s) that were never"
                    " imported — did wf init --rebuild fail?"
                ),
            )


def check_registry_agrees_with_database(ctx) -> None:
    for spec in ctx.specs.values():
        row = ctx.store.get_gate_kind(spec.kind, spec.version)
        if row is None:
            raise Refusal(
                "every registered gate kind is synced into the database",
                actual=f"{spec.kind}@{spec.version} is not in gate_kinds",
                needed="wf init",
            )
        if row["spec_sha256"] != spec.sha256:
            raise Refusal(
                "the database mirrors the registry files",
                expected=spec.sha256,
                actual=row["spec_sha256"],
                needed="wf init to re-sync the registry",
            )


def check_registry_against_pins(ctx) -> None:
    """A registered version whose content moved away from a chain pin.

    PLAN §6: new versions are new entries and old ones are never edited, so
    an in-place edit of a registered version must be detectable. The pin is
    the authority; this is the detection.
    """
    for row in ctx.store.list_work_orders():
        key = (row["kind"], row["kind_version"])
        spec = ctx.specs.get(key)
        if spec is None:
            raise Refusal(
                "every pinned gate kind is still registered",
                actual=f"{row['kind']}@{row['kind_version']} has no file",
                needed="restore the registry file, or leave the version registered",
                wo=row["wo_id"],
            )
        if spec.sha256 != row["spec_sha256"]:
            raise Integrity(
                "a registered gate-kind version was edited in place",
                wo=row["wo_id"],
                detail=(
                    f"{row['kind']}@{row['kind_version']}: pinned"
                    f" {row['spec_sha256'][:12]}, registry {spec.sha256[:12]}"
                    " — register a new version instead of editing this one"
                ),
            )


def check_objects(ctx, events_by_wo: dict) -> int:
    """Every digest the chain references resolves and re-hashes."""
    from wf import referenced_digests

    seen = set()
    for wo_id, events in events_by_wo.items():
        for event in events:
            for digest, _media, _class in referenced_digests(event):
                if digest in seen:
                    continue
                seen.add(digest)
                try:
                    ctx.cas.get(digest)
                except Integrity as exc:
                    raise Integrity(
                        exc.problem, wo=wo_id, detail=exc.detail or digest
                    ) from None
    return len(seen)


def check_receipts(ctx, wo_row, events) -> dict:
    """Re-hash each receipt's manifest from the tree it recorded."""
    spec = ctx.spec_for(wo_row)
    scope = receipts.Scope(spec.test_scope + spec.harness_scope)
    wo_id = wo_row["wo_id"]
    checked, skipped = 0, 0
    sealed = None

    for event in events:
        etype = event.get("type")
        if etype == chainmod.STAGE_ENTERED:
            # The seal that governs this stage, taken from the chain rather
            # than from whatever a green receipt claims about itself.
            sealed = (event.get("frozen") or {}).get("manifest_sha256")
            continue
        if etype not in (chainmod.RECEIPT_RED, chainmod.RECEIPT_GREEN,
                         chainmod.RECEIPT_CHECK):
            continue
        if etype == chainmod.RECEIPT_GREEN and \
                event.get("frozen_manifest_sha256") != sealed:
            raise Integrity(
                "a green receipt names a frozen set that was never sealed for its stage",
                wo=wo_id, seq=event["seq"],
                detail=(
                    f"receipt claims {str(event.get('frozen_manifest_sha256'))[:12]},"
                    f" stage.entered sealed {str(sealed)[:12]}"
                ),
            )
        if event.get("tree_dirty"):
            skipped += 1
            continue
        commit = event.get("head_sha")
        if not commit or not gitio.commit_exists(ctx.repo, commit):
            raise Integrity(
                "a receipt names a commit this repository no longer has",
                wo=wo_id, seq=event["seq"], detail=str(commit),
            )
        manifest = receipts.manifest_from_commit(ctx.repo, commit, scope)
        digest = receipts.manifest_digest(manifest)
        if digest != event.get("test_manifest_sha256"):
            raise Integrity(
                "a receipt's test manifest does not re-hash from the tree it names",
                wo=wo_id, seq=event["seq"],
                detail=(
                    f"recorded {str(event.get('test_manifest_sha256'))[:12]},"
                    f" recomputed {digest[:12]} at {commit[:8]}"
                ),
            )
        if etype == chainmod.RECEIPT_GREEN:
            frozen = sealed
            if digest != frozen:
                raise Integrity(
                    "a green receipt was not verified against its frozen set",
                    wo=wo_id, seq=event["seq"],
                    detail=f"frozen {str(frozen)[:12]}, tree {digest[:12]}",
                )
        checked += 1
    return {"checked": checked, "skipped_dirty": skipped}


def check_cross_binds(ctx, wo_id: str, events) -> dict:
    """Every bound commit exists, is an ancestor, and carried what it claims."""
    head = gitio.head_sha(ctx.repo)
    rel = (ctx.chains_dir / f"{wo_id}.jsonl").resolve().relative_to(
        Path(ctx.repo).resolve()
    ).as_posix()
    bound = 0
    for event in events:
        if event.get("type") != chainmod.COMMIT_LANDED:
            continue
        sha = event.get("sha")
        if not sha or not gitio.commit_exists(ctx.repo, sha):
            raise Integrity(
                "a commit.landed names a commit that is not in this repository",
                wo=wo_id, seq=event["seq"], detail=str(sha),
            )
        if not gitio.is_ancestor(ctx.repo, sha, head):
            raise Integrity(
                "a bound commit is not an ancestor of HEAD",
                wo=wo_id, seq=event["seq"],
                detail=f"{sha[:8]} is not reachable from {str(head)[:8]}",
            )
        try:
            blob = gitio.git(ctx.repo, "show", f"{sha}:{rel}", binary=True)
        except Refusal:
            raise Integrity(
                "a bound commit's tree has no chain file for this work order",
                wo=wo_id, seq=event["seq"], detail=f"{sha[:8]}:{rel}",
            ) from None
        lines = [line for line in blob.split(b"\n") if line.strip()]
        if len(lines) != event.get("chain_seq"):
            raise Integrity(
                "a bound commit's chain file does not end at the recorded head",
                wo=wo_id, seq=event["seq"],
                detail=(
                    f"{sha[:8]} holds {len(lines)} event(s),"
                    f" the bind records {event.get('chain_seq')}"
                ),
            )
        recorded = canonical.loads(lines[-1])
        if recorded.get("hash") != event.get("chain_hash"):
            raise Integrity(
                "a bound commit's chain file ends at a different event",
                wo=wo_id, seq=event["seq"],
                detail=(
                    f"tree {str(recorded.get('hash'))[:12]},"
                    f" bind {str(event.get('chain_hash'))[:12]}"
                ),
            )
        bound += 1
    return {"bound": bound}


def require_full_history(ctx) -> None:
    """A shallow clone cannot answer the question the prefix walk asks.

    With history truncated, the walk sees one version of each chain file and
    happily calls a rewritten file append-only. Refusing is the only honest
    answer: the check did not run, so it must not report a pass.
    """
    shallow = gitio.git(
        ctx.repo, "rev-parse", "--is-shallow-repository", check=False
    ).strip()
    if shallow == "true":
        raise Refusal(
            "the repository has full history",
            actual="a shallow clone",
            needed="fetch-depth: 0 — the prefix walk cannot see truncated history",
        )


def chain_paths_in_history(ctx) -> list:
    """Every chain file that has ever existed, repo-relative.

    Driving the walk from the database would let deletion erase the record
    *and* the check that would have noticed: with the file gone, nothing
    imports, no work order exists, and verify reports "0 work orders — ok".
    Git remembers the file was there, so git is what the walk is driven from.
    """
    rel_root = Path(ctx.chains_dir).resolve().relative_to(
        Path(ctx.repo).resolve()
    ).as_posix()
    raw = gitio.git(
        ctx.repo, "log", "--format=", "--name-only", "--diff-filter=AMR",
        "--", rel_root,
    )
    seen = {
        line.strip() for line in raw.split("\n")
        if line.strip().startswith(rel_root + "/") and line.strip().endswith(".jsonl")
    }
    return sorted(seen)


def check_nothing_was_deleted(ctx) -> int:
    """A chain file that history records must still be there."""
    missing = []
    for rel in chain_paths_in_history(ctx):
        if not (Path(ctx.repo) / rel).exists():
            missing.append(rel)
    if missing:
        raise Integrity(
            "a chain file recorded in history is gone",
            detail=(
                f"{', '.join(missing)} — deleting the record is a rewrite of it,"
                " not an absence of one"
            ),
        )
    return len(chain_paths_in_history(ctx))


def check_append_only(ctx, wo_id: str) -> dict:
    """Each historical version of a chain file is a prefix of its successor.

    This is what catches a dropped or rewritten row when the rows naming it
    are gone too: no per-row check can see a truncated tail, but a successor
    that is not an extension of its predecessor is visible from outside.
    """
    path = ctx.chains_dir / f"{wo_id}.jsonl"
    rel = path.resolve().relative_to(Path(ctx.repo).resolve()).as_posix()
    raw = gitio.git(ctx.repo, "log", "--format=%H", "--reverse", "--", rel)
    commits = [line for line in raw.split("\n") if line.strip()]

    previous, previous_sha, steps = b"", None, 0
    for sha in commits:
        blob_id = gitio.git(ctx.repo, "rev-parse", f"{sha}:{rel}", check=False).strip()
        if not blob_id:
            continue
        blob = gitio.git(ctx.repo, "show", f"{sha}:{rel}", binary=True)
        if blob == previous:
            continue
        if not blob.startswith(previous):
            raise Integrity(
                "a chain file was rewritten rather than appended to",
                wo=wo_id,
                detail=(
                    f"{sha[:8]} is not an extension of "
                    f"{previous_sha[:8] if previous_sha else 'the empty file'}"
                ),
            )
        previous, previous_sha = blob, sha
        steps += 1

    on_disk = path.read_bytes() if path.exists() else b""
    if not on_disk.startswith(previous):
        raise Integrity(
            "the chain file on disk is not an extension of its last committed version",
            wo=wo_id,
            detail=f"{len(previous)} bytes committed, {len(on_disk)} on disk",
        )
    return {"versions": steps}


def run(ctx, deep: bool = False) -> dict:
    """Verify everything, fail-fast, and report what was checked."""
    ctx.open_store()
    report = {
        "deep": deep,
        "head": gitio.head_sha(ctx.repo),
        "work_orders": [],
        "events": 0,
        "objects": 0,
    }
    if deep:
        # First, before any check that a truncated history would misdiagnose:
        # in a shallow clone the receipts name commits that are simply absent,
        # and reporting that as corrupted evidence accuses the record of a
        # fault in the checkout.
        require_full_history(ctx)
        report["chain_files_in_history"] = check_nothing_was_deleted(ctx)
    check_export_is_complete(ctx)
    check_registry_agrees_with_database(ctx)
    check_registry_against_pins(ctx)

    events_by_wo = {}
    for row in ctx.store.list_work_orders():
        wo_id = row["wo_id"]
        projection = ctx.chain.project(wo_id)      # verifies, or refuses to answer
        events_by_wo[wo_id] = projection.events
        check_export_matches_database(ctx, wo_id)
        entry = {
            "wo": wo_id,
            "events": projection.last_seq,
            "head": projection.last_hash,
            "stage": projection.state.get("stage"),
        }
        if deep:
            entry["receipts"] = check_receipts(ctx, row, projection.events)
            entry["cross_binds"] = check_cross_binds(ctx, wo_id, projection.events)
            entry["append_only"] = check_append_only(ctx, wo_id)
            entry["unbound_tip"] = unbound_tip(projection.events)
        report["work_orders"].append(entry)
        report["events"] += projection.last_seq

    report["objects"] = check_objects(ctx, events_by_wo)
    return report


def unbound_tip(events) -> dict:
    """What the chain has not yet bound into a commit.

    The tip is never bound in-chain — its bind can only land in a successor
    — so this is a statement of fact, not a failure. CI's check run against
    the head SHA is what witnesses it until the next append.
    """
    last_bind = None
    for event in events:
        if event.get("type") == chainmod.COMMIT_LANDED:
            last_bind = event
    if last_bind is None:
        return {"pending_events": len(events), "since_seq": 0}
    # Measured against the head the bind *recorded*, not the bind's own seq:
    # the bind event itself landed after the commit it names, so it is the
    # pending one. In steady state that makes this exactly 1 (PLAN §5).
    return {
        "pending_events": len(events) - last_bind["chain_seq"],
        "since_seq": last_bind["chain_seq"],
        "last_bound_commit": last_bind["sha"],
    }
