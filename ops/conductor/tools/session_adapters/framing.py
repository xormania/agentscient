"""JSON-lines framing and request correlation for a native harness's
protocol channel.

Contract: ops/conductor/sessions-lever.md, "The adapter boundary". Adapted
from the proof's asyncio RPC reader (`RPC.read`) and its id book-keeping,
made synchronous: this module reads no process and owns no transport, it
only classifies one already-received line at a time.

Source: /home/scientdb/projects/poc/multi-harness-proof@a944f31
(mhproof/rpc.py: RPCError, RPC.read)

Stdlib only.
"""
from __future__ import annotations

import json


class Refused(Exception):
    """A frame the parser cannot correlate. `reading` names the line."""

    def __init__(self, reading: str):
        self.reading = reading
        super().__init__(reading)


class Parser:
    """Feeds one native-protocol line at a time.

    Tracks the ids of requests seen so a response can be matched to one;
    a line this parser cannot place is refused, naming the line itself,
    never a summary of it.
    """

    def __init__(self):
        self._pending: set = set()

    def feed(self, line: str) -> dict:
        try:
            packet = json.loads(line)
        except ValueError:
            raise Refused(f"non-JSON line on the native protocol channel: {line}") from None
        if not isinstance(packet, dict):
            raise Refused(f"non-object frame on the native protocol channel: {line}")
        if "method" in packet:
            ident = packet.get("id")
            if ident is not None:
                if ident in self._pending:
                    raise Refused(f"a second request with id {ident!r} already pending: {line}")
                self._pending.add(ident)
            return packet
        ident = packet.get("id")
        if ident is None:
            raise Refused(f"a result with no id to correlate it: {line}")
        if ident not in self._pending:
            raise Refused(f"a response whose id {ident!r} matches no pending request: {line}")
        self._pending.discard(ident)
        return packet
