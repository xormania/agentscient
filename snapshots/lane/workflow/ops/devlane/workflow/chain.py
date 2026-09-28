"""The append-only event chain: append, verify, project (PLAN §3.1).

The chain is the authority.  ``wo_state`` is a derived read view, and a read
that finds the two disagreeing refuses with an integrity error rather than
reporting either.

Two properties make that enforceable:

* the stored payload is the **exact canonical bytes** of the complete event,
  its own ``hash`` field included, and ``hash`` is taken over the same object
  without that field.  Verification re-parses from the payload, so a row that
  was rewritten is a rewritten record even when it decodes to the same value;
* the state each event produced is hashed into that event as ``state_sha256``,
  so the projection is covered by the same chain of hashes as the events.

The reducer here is deliberately **spec-free**.  Every event carries what it
did — the stage entered, the frozen set sealed, the effect an outcome had —
so state replays from the chain alone.  A gate-kind spec decides what a verb
is *allowed* to record; once recorded, the record is the whole story.  That
is what lets ``init --rebuild`` reconstruct the projection from the export,
and what lets ``verify`` re-derive it independently of the stored row.

A type the reducer does not know is inert, not an error: PLAN §6 requires a
new event type to cost zero engine changes.  Tampering with a type name is
still caught, because the type is inside the hashed payload.
"""

from __future__ import annotations

import canonical
from errors import Integrity, Refusal

# Event types this reducer understands.  Others are recorded and hashed like
# any event; they simply do not move the projection.
WO_OPENED = "wo.opened"
STAGE_ENTERED = "stage.entered"
RECEIPT_RED = "receipt.red"
RECEIPT_GREEN = "receipt.green"
RECEIPT_CHECK = "receipt.check"
OUTCOME = "outcome"
MARKER_OPEN = "marker.open"
MARKER_CLOSE = "marker.close"
COMMIT_LANDED = "commit.landed"
ARTIFACT_RECORDED = "artifact.recorded"

RECEIPT_PREFIX = "receipt."

#: The type vocabulary, so a filter can tell a typo from an empty result.
#: A `receipt.<anything>` is always known — §6 requires a new check class to
#: cost zero engine changes, and a new receipt type is the same promise.
KNOWN_TYPES = (
    WO_OPENED, STAGE_ENTERED, RECEIPT_RED, RECEIPT_GREEN, RECEIPT_CHECK,
    OUTCOME, MARKER_OPEN, MARKER_CLOSE, COMMIT_LANDED, ARTIFACT_RECORDED,
)


def is_known_type(etype: str) -> bool:
    return etype in KNOWN_TYPES or (
        isinstance(etype, str) and etype.startswith(RECEIPT_PREFIX)
        and len(etype) > len(RECEIPT_PREFIX)
    )

# Fields the chain owns.  A caller may supply them, which is a compare-and-
# swap; it may not invent different ones.
DERIVED_FIELDS = ("seq", "prev", "time", "state_sha256", "hash")


class Projection:
    """A work order's state, only ever returned when the chain verifies."""

    def __init__(self, wo_id, state, state_sha256, last_seq, last_hash, events):
        self.wo_id = wo_id
        self.state = state
        self.state_sha256 = state_sha256
        self.last_seq = last_seq
        self.last_hash = last_hash
        self.events = events

    def __repr__(self):
        return f"<Projection {self.wo_id} seq={self.last_seq} stage={self.state.get('stage')}>"


def initial_state(wo_id: str) -> dict:
    return {
        "wo": wo_id,
        "kind": None,
        "kind_version": None,
        "spec_sha256": None,
        "objective": None,
        "stage": None,
        "stage_seq": 0,
        "satisfied": [],
        "outcomes": [],
        "frozen": None,
        "open_markers": [],
        "status": "open",
        "last_commit": None,
    }


def apply_event(state: dict, event: dict, seq: int) -> dict:
    """Fold one event into the state.  Pure: the input is not mutated."""
    new = dict(state)
    new["satisfied"] = list(state.get("satisfied", []))
    new["outcomes"] = list(state.get("outcomes", []))
    new["open_markers"] = list(state.get("open_markers", []))

    etype = event.get("type")

    if etype == WO_OPENED:
        new["kind"] = event.get("kind")
        new["kind_version"] = event.get("kind_version")
        new["spec_sha256"] = event.get("spec_sha256")
        new["objective"] = event.get("objective")
    elif etype == STAGE_ENTERED:
        new["stage"] = event.get("stage")
        new["stage_seq"] = seq
        # Entering a stage clears the evidence gathered in the one before it,
        # and reseals — or voids — the frozen set.  The latest entry governs,
        # which is how re-entering an earlier stage has an exit (PLAN §3.3).
        new["satisfied"] = []
        new["outcomes"] = []
        new["frozen"] = event.get("frozen")
    elif etype == OUTCOME:
        new["outcomes"] = sorted(set(new["outcomes"] + [event.get("value")]))
        if event.get("effect") == "terminal":
            new["status"] = "terminal"
    elif etype == MARKER_OPEN:
        new["open_markers"] = sorted(set(new["open_markers"] + [event.get("id")]))
    elif etype == MARKER_CLOSE:
        new["open_markers"] = [m for m in new["open_markers"] if m != event.get("id")]
    elif etype == COMMIT_LANDED:
        new["last_commit"] = event.get("sha")

    if isinstance(etype, str) and etype.startswith(RECEIPT_PREFIX):  # noqa: SIM102 — the nested test
        # below carries its own long rationale; collapsing them
        # would strand that comment from its condition
        # A receipt that did not pass is still recorded — records are
        # evidence — but it does not satisfy anything. `satisfies` defaults
        # to true so an event type this reducer has never heard of still
        # counts, per §6's zero-engine-change requirement.
        if event.get("satisfies", True):
            entries = [etype]
            klass = event.get("class")
            if isinstance(klass, str) and klass:
                # Recorded in both forms so a stage can require either
                # `receipt.check` or `receipt.check:security` without the
                # engine ever knowing what "security" means.
                entries.append(f"{etype}:{klass}")
            new["satisfied"] = sorted(set(new["satisfied"] + entries))

    return new


def replay(wo_id: str, events) -> dict:
    """Derive state from a chain.  ``events`` is an ordered list of payload dicts."""
    state = initial_state(wo_id)
    for index, event in enumerate(events):
        state = apply_event(state, event, index + 1)
    return state


def event_hash(event: dict) -> str:
    """sha256 over the canonical JSON of the event without its own hash field."""
    return canonical.digest({k: v for k, v in event.items() if k != "hash"})


class Chain:
    """Append, verify and project over one control-plane database."""

    def __init__(self, store, now=None):
        self.store = store
        self._now = now or canonical.now

    # -- append ------------------------------------------------------------

    def append(self, wo_id: str, event: dict) -> dict:
        """Add one event and replace the derived state, in one transaction.

        ``seq``, ``prev``, ``time``, ``state_sha256`` and ``hash`` may be left
        out, in which case they are derived.  Supplying one is a
        compare-and-swap: a value that disagrees with what the chain requires
        is refused rather than overwritten, which is how a writer working from
        a stale read is caught.  The primary key on ``(wo_id, seq)`` is the
        backstop under that check.
        """
        if self.store.get_work_order(wo_id) is None:
            raise Refusal(
                "work order exists",
                actual=wo_id,
                needed="open the work order before appending to its chain",
                wo=wo_id,
            )
        if not isinstance(event.get("type"), str) or not event["type"]:
            raise Refusal(
                "event has a type",
                actual=repr(event.get("type")),
                needed="a non-empty type string",
                wo=wo_id,
            )

        tail = self.store.chain_tail(wo_id)
        expected_seq = 1 if tail is None else tail["seq"] + 1
        expected_prev = canonical.ZERO_DIGEST if tail is None else tail["hash"]

        out = dict(event)

        if "seq" in out and out["seq"] != expected_seq:
            raise Refusal(
                "append is contiguous with the chain tail",
                expected=expected_seq,
                actual=out["seq"],
                needed="re-read the chain tail and retry against the current seq",
                wo=wo_id,
            )
        out["seq"] = expected_seq

        if "prev" in out and out["prev"] != expected_prev:
            raise Refusal(
                "append links to the chain tail",
                expected=expected_prev,
                actual=out["prev"],
                needed="re-read the chain tail and retry against the current hash",
                wo=wo_id,
            )
        out["prev"] = expected_prev

        # Time is normalised to the wire form *before* the monotonicity check,
        # so the value compared is the value hashed.
        supplied_time = "time" in out
        if supplied_time:
            try:
                stamp = canonical.format_time(canonical.parse_time(out["time"]))
            except (ValueError, TypeError) as exc:
                raise Refusal(
                    "time is RFC3339 UTC with six fractional digits and a Z",
                    actual=repr(out.get("time")),
                    needed=str(exc),
                    wo=wo_id,
                ) from None
        else:
            stamp = self._now()

        if tail is not None and stamp < tail["time"]:
            if supplied_time:
                raise Refusal(
                    "time is non-decreasing within the chain",
                    expected=f"at or after {tail['time']}",
                    actual=stamp,
                    needed="an event time no earlier than the chain tail's",
                    wo=wo_id,
                )
            # The wall clock read earlier than the chain tail. Reordering the
            # chain is not an option, and refusing would wedge the work order
            # until the clock caught up — a host clock that steps backwards by
            # a tenth of a second must not be able to stop the recorder. The
            # event is stamped at the tail's time, which keeps the sequence
            # non-decreasing, and the reading that caused it is recorded
            # rather than quietly discarded.
            out["clock_regressed_from"] = stamp
            stamp = tail["time"]
        out["time"] = stamp

        if "supersedes_seq" in out:
            target = out["supersedes_seq"]
            if not isinstance(target, int) or isinstance(target, bool) or not 1 <= target < expected_seq:
                raise Refusal(
                    "supersedes_seq names an earlier event",
                    expected=f"1..{expected_seq - 1}",
                    actual=repr(target),
                    needed="the seq of an event already in this chain",
                    wo=wo_id,
                )
            if self.store.get_event(wo_id, target) is None:
                raise Refusal(
                    "superseded event exists",
                    actual=target,
                    needed="the seq of an event already in this chain",
                    wo=wo_id,
                )

        # State follows from the chain, never from the caller: there is no way
        # to append an event and a state that do not correspond.
        prior = self._replay_stored(wo_id)
        state = apply_event(prior, out, expected_seq)
        try:
            state_sha = canonical.digest(state)
        except (ValueError, TypeError) as exc:
            raise Refusal(
                "state is canonically hashable",
                actual=str(exc),
                needed="event fields that are JSON values",
                wo=wo_id,
            ) from None
        if "state_sha256" in out and out["state_sha256"] != state_sha:
            raise Refusal(
                "state_sha256 matches the state this event produces",
                expected=state_sha,
                actual=out["state_sha256"],
                needed="omit state_sha256, or supply the hash of the state being written",
                wo=wo_id,
            )
        out["state_sha256"] = state_sha

        try:
            digest = event_hash(out)
        except (ValueError, TypeError) as exc:
            raise Refusal(
                "event is canonically hashable",
                actual=str(exc),
                needed="fields that are JSON objects, arrays, strings, integers, booleans or null",
                wo=wo_id,
            ) from None
        if "hash" in event and event["hash"] != digest:
            raise Refusal(
                "supplied hash matches the event content",
                expected=digest,
                actual=event["hash"],
                needed="omit hash, or supply the hash of the event as written",
                wo=wo_id,
            )
        out["hash"] = digest

        payload = canonical.dumps(out)

        self.store.begin()
        try:
            self.store.insert_event(
                wo_id, expected_seq, digest, expected_prev, stamp, payload, state_sha
            )
            self.store.upsert_state(
                wo_id, canonical.dumps(state), state_sha, expected_seq, digest
            )
            self.store.commit()
        except Exception:
            self.store.rollback()
            raise
        return out

    def _replay_stored(self, wo_id: str) -> dict:
        return replay(wo_id, [canonical.loads(r["payload"]) for r in self.store.list_events(wo_id)])

    # -- verify ------------------------------------------------------------

    def verify(self, wo_id: str) -> list:
        """Recompute every hash and link. Returns the decoded payloads.

        Raises :class:`Integrity` naming the first seq at which the chain
        fails.  A work order with no events verifies: nothing is claimed, so
        nothing is broken.
        """
        rows = self.store.list_events(wo_id)
        payloads = []
        prev_hash = canonical.ZERO_DIGEST
        prev_time = None

        for index, row in enumerate(rows):
            want_seq = index + 1
            if row["seq"] != want_seq:
                raise Integrity(
                    "chain is not contiguous",
                    wo=wo_id, seq=row["seq"],
                    detail=f"expected seq {want_seq} at position {index + 1}",
                )

            raw = row["payload"]
            raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
            try:
                event = canonical.loads(raw_bytes)
            except ValueError as exc:
                raise Integrity(
                    "stored payload is not decodable JSON",
                    wo=wo_id, seq=row["seq"], detail=str(exc),
                ) from None
            if not isinstance(event, dict):
                raise Integrity(
                    "stored payload is not a JSON object",
                    wo=wo_id, seq=row["seq"], detail=type(event).__name__,
                )
            if not canonical.is_canonical(raw_bytes):
                raise Integrity(
                    "stored payload is not in canonical form",
                    wo=wo_id, seq=row["seq"],
                    detail="re-encoding the payload does not reproduce its bytes",
                )

            for field, column in (
                ("seq", row["seq"]),
                ("prev", row["prev"]),
                ("time", row["time"]),
                ("state_sha256", row["state_sha256"]),
                ("hash", row["hash"]),
            ):
                if field not in event:
                    raise Integrity(
                        "stored payload is missing a core field",
                        wo=wo_id, seq=row["seq"], detail=field,
                    )
                if event[field] != column:
                    raise Integrity(
                        "stored column disagrees with the hashed payload",
                        wo=wo_id, seq=row["seq"],
                        detail=f"{field}: column {column!r}, payload {event[field]!r}",
                    )

            recomputed = event_hash(event)
            if recomputed != row["hash"]:
                raise Integrity(
                    "recomputed hash does not match the stored hash",
                    wo=wo_id, seq=row["seq"],
                    detail=f"recomputed {recomputed[:12]}, stored {str(row['hash'])[:12]}",
                )

            if row["prev"] != prev_hash:
                raise Integrity(
                    "prev does not link to the preceding event",
                    wo=wo_id, seq=row["seq"],
                    detail=f"prev {str(row['prev'])[:12]}, preceding hash {prev_hash[:12]}",
                )

            try:
                canonical.parse_time(row["time"])
            except ValueError as exc:
                raise Integrity(
                    "stored event time is unreadable",
                    wo=wo_id, seq=row["seq"], detail=str(exc),
                ) from None
            if prev_time is not None and row["time"] < prev_time:
                raise Integrity(
                    "event time decreases",
                    wo=wo_id, seq=row["seq"],
                    detail=f"{row['time']} precedes {prev_time}",
                )

            prev_hash = row["hash"]
            prev_time = row["time"]
            payloads.append(event)

        return payloads

    # -- project -----------------------------------------------------------

    def project(self, wo_id: str) -> Projection:
        """The work order's current state.

        Refuses — with an integrity error and no projection — when the chain
        does not verify, or when the stored state row disagrees with the chain
        it claims to be derived from.  There is no path by which a work order
        in either condition is reported as valid.
        """
        if self.store.get_work_order(wo_id) is None:
            raise Refusal(
                "work order exists",
                actual=wo_id,
                needed="a work order id that has been opened",
                wo=wo_id,
            )

        payloads = self.verify(wo_id)
        derived = replay(wo_id, payloads)
        derived_sha = canonical.digest(derived)

        row = self.store.get_state(wo_id)
        if not payloads:
            if row is not None:
                raise Integrity(
                    "state row exists for a work order with no events",
                    wo=wo_id,
                )
            return Projection(wo_id, derived, derived_sha, 0, canonical.ZERO_DIGEST, [])

        if row is None:
            raise Integrity("work order has events but no state row", wo=wo_id)

        last_seq = len(payloads)
        last_hash = payloads[-1]["hash"]
        chain_state_sha = payloads[-1]["state_sha256"]

        if derived_sha != chain_state_sha:
            raise Integrity(
                "replayed state does not match the state hashed into the chain",
                wo=wo_id, seq=last_seq,
                detail=f"replayed {derived_sha[:12]}, chain {str(chain_state_sha)[:12]}",
            )
        if row["last_seq"] != last_seq or row["last_hash"] != last_hash:
            raise Integrity(
                "state row was derived from a different chain head",
                wo=wo_id, seq=last_seq,
                detail=(
                    f"row at seq {row['last_seq']} {str(row['last_hash'])[:12]}, "
                    f"chain at seq {last_seq} {last_hash[:12]}"
                ),
            )
        if row["state_sha256"] != derived_sha:
            raise Integrity(
                "state row hash does not match the replayed state",
                wo=wo_id, seq=last_seq,
                detail=f"row {str(row['state_sha256'])[:12]}, replayed {derived_sha[:12]}",
            )
        if canonical.digest(canonical.loads(row["state_json"])) != derived_sha:
            raise Integrity(
                "state row body does not match the replayed state",
                wo=wo_id, seq=last_seq,
            )
        if not canonical.is_canonical(row["state_json"]):
            raise Integrity(
                "state row body is not in canonical form", wo=wo_id, seq=last_seq
            )

        return Projection(wo_id, derived, derived_sha, last_seq, last_hash, payloads)
