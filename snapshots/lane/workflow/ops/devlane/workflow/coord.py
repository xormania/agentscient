"""Claims and sessions — coordination, deliberately not evidence.

Neither touches the chain. PLAN §8 keeps both out of the export because they
are transient: losing them on rebuild is correct, and a claim that outlived
the agent holding it is worse than no claim at all.

The claim discipline is loopflow's, unchanged:

* **TTL.** A claim expires. Nothing has to clean up after an agent that
  died, and no agent has to decide whether another agent is really gone.
* **Re-claim is the heartbeat.** An agent that is still working re-claims,
  which extends the expiry. There is no separate keep-alive verb to forget.
* **Expiry frees; nobody overrides.** A live claim held by someone else is
  exit 3 and stays that way — the answer is to wait for it to expire or to
  ask, never to take it (AGENTS.md §Teamwork).
"""

from __future__ import annotations

import re

import canonical
from errors import Claimed, Refusal, Usage

DURATION = re.compile(r"^(\d+)([smhd])$")
SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
DEFAULT_TTL = "30m"
SESSION_TTL_SECONDS = 3600


def parse_duration(raw: str) -> int:
    """``30m`` → 1800. One spelling, so a typo refuses rather than surprises."""
    if (raw or "").strip().startswith("-"):
        # Python 3.14's argparse hands `-5m` through as a value where 3.12
        # rejected it as a flag; the usage answer (64) must not depend on
        # which interpreter parsed the command line, so it lives here too.
        raise Usage(
            f"--ttl {raw} reads as a flag — a duration cannot be negative"
        )
    match = DURATION.match(raw or "")
    if not match:
        raise Refusal(
            "the ttl is a duration",
            actual=repr(raw),
            needed="a count and a unit, one of s/m/h/d — for example 30m",
        )
    count = int(match.group(1))
    if count <= 0:
        raise Refusal(
            "the ttl is positive", actual=raw, needed="a duration greater than zero"
        )
    return count * SECONDS[match.group(2)]


def shift(stamp: str, seconds: int) -> str:
    """``stamp`` moved forward, in the chain's one canonical time spelling."""
    import datetime as dt

    return canonical.format_time(
        canonical.parse_time(stamp) + dt.timedelta(seconds=seconds)
    )


def held_by_other(store, wo_id: str, agent: str, now: str):
    """The live claim blocking ``agent``, or None.

    An expired claim is not a block: it is simply over. That is the whole
    point of the TTL, and it is why no verb needs to decide whether another
    agent is still alive.
    """
    row = store.one("SELECT * FROM claims WHERE wo_id = ?", (wo_id,))
    if row is None:
        return None
    if row["agent"] == agent:
        return None
    if row["expires_at"] <= now:
        return None
    return row


def require_not_claimed(store, wo_id: str, agent: str, now: str) -> None:
    row = held_by_other(store, wo_id, agent, now)
    if row is not None:
        raise Claimed(
            f"{wo_id} is claimed by {row['agent']} until {row['expires_at']}"
            f"{(' — ' + row['note']) if row['note'] else ''}"
        )


def claim(store, wo_id: str, agent: str, ttl: str, note: str, now: str) -> dict:
    """Acquire or extend a claim. Re-claiming is the heartbeat.

    The UPSERT *is* the authorization. Checking first and writing second left
    a window in which two agents both read "free" and both wrote — measured
    at 16 of 25 contested acquisitions — and the unguarded
    ``DO UPDATE SET agent=excluded.agent`` meant the loser silently took the
    winner's claim. The ``WHERE`` clause makes the database refuse that in
    one statement: the row updates only when the claimant already holds it or
    the existing claim has expired, and a ``rowcount`` of zero is somebody
    else holding it.
    """
    # Not `ttl or DEFAULT_TTL`: argparse already supplies the default when the
    # flag is absent, so falling back here would turn an explicitly blank
    # --ttl into a silent 30 minutes instead of a refusal.
    seconds = parse_duration(ttl)
    expires = shift(now, seconds)
    existing = store.one("SELECT * FROM claims WHERE wo_id = ?", (wo_id,))

    cursor = store.q(
        "INSERT INTO claims (wo_id, agent, note, acquired_at, expires_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(wo_id) DO UPDATE SET"
        "   agent=excluded.agent,"
        "   note=excluded.note,"
        "   expires_at=excluded.expires_at,"
        "   acquired_at=CASE WHEN claims.agent = excluded.agent"
        "                 AND claims.expires_at > excluded.acquired_at"
        "               THEN claims.acquired_at ELSE excluded.acquired_at END"
        " WHERE claims.agent = excluded.agent"
        "    OR claims.expires_at <= excluded.acquired_at",
        (wo_id, agent, note or "", now, expires),
    )
    if cursor.rowcount == 0:
        holder = store.one("SELECT * FROM claims WHERE wo_id = ?", (wo_id,))
        raise Claimed(
            f"{wo_id} is claimed by {holder['agent']} until {holder['expires_at']}"
            f"{(' — ' + holder['note']) if holder['note'] else ''}"
        )

    row = store.one("SELECT * FROM claims WHERE wo_id = ?", (wo_id,))
    # Expiry ended the old claim, whoever held it: reacquiring after the TTL
    # is a retake with a fresh acquired_at, not a continuous heartbeat.
    renewed = (existing is not None and existing["agent"] == agent
               and existing["expires_at"] > now)
    return {
        "wo": wo_id, "agent": agent, "note": note or "",
        "acquired_at": row["acquired_at"],
        "expires_at": expires, "ttl_seconds": seconds, "renewed": renewed,
    }


def release(store, wo_id: str, agent: str, now: str) -> dict:
    """Give a claim up. Only the holder may; an expired one is already free."""
    row = store.one("SELECT * FROM claims WHERE wo_id = ?", (wo_id,))
    if row is None:
        return {"wo": wo_id, "released": False, "note": "no claim was held"}
    if row["agent"] != agent and row["expires_at"] > now:
        raise Claimed(
            f"{wo_id} is claimed by {row['agent']} until {row['expires_at']} —"
            " a claim is released by its holder, or it expires"
        )
    store.q("DELETE FROM claims WHERE wo_id = ?", (wo_id,))
    return {
        "wo": wo_id, "released": True, "was_held_by": row["agent"],
        "was_expired": row["expires_at"] <= now,
    }


def current(store, wo_id: str, now: str):
    """The claim a reader should be told about, or None if it has expired."""
    row = store.one("SELECT * FROM claims WHERE wo_id = ?", (wo_id,))
    if row is None or row["expires_at"] <= now:
        return None
    return {
        "agent": row["agent"], "note": row["note"],
        "acquired_at": row["acquired_at"], "expires_at": row["expires_at"],
    }


def touch_session(store, agent: str, wo_id: str, now: str) -> None:
    """Record that this agent is active. Presence, not permission.

    One row per agent rather than one per invocation: PLAN §2 drops
    loopflow's session history and its role/task/cycle key, and what is
    actually wanted is the answer to "who else is working right now".
    """
    if not agent:
        return
    session_id = canonical.sha256_hex(agent.encode("utf-8"))[:16]
    store.q(
        "INSERT INTO sessions (session_id, agent, wo_id, status, started_at,"
        " last_seen, ttl_seconds) VALUES (?, ?, ?, 'active', ?, ?, ?)"
        " ON CONFLICT(session_id) DO UPDATE SET last_seen=excluded.last_seen,"
        " wo_id=excluded.wo_id, status='active'",
        (session_id, agent, wo_id or "", now, now, SESSION_TTL_SECONDS),
    )


def active_sessions(store, now: str) -> list:
    out = []
    for row in store.all("SELECT * FROM sessions ORDER BY agent"):
        if shift(row["last_seen"], row["ttl_seconds"]) > now:
            out.append({
                "agent": row["agent"], "wo": row["wo_id"] or None,
                "last_seen": row["last_seen"],
            })
    return out
