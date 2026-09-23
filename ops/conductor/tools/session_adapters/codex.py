"""The codex adapter: one Codex app-server conversation, spoken to by the
member's bridge over `app-server --listen stdio://`.

Contract: ops/conductor/sessions-lever.md, "The adapter boundary,
extended". Slice 1's five methods come from the shared module; this file
adds the channel argv, the handshake, the submission and the
classification of what the app-server sends. The method names and frame
shapes are the installed Codex's (0.155.1), read from its generated
schema: `initialize`, `initialized`, `thread/start`, `turn/start` with
`toolOutput`, `thread/read` with `includeTurns`. Codex frames carry no
`jsonrpc` field.

Stdlib only.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _common():
    path = Path(__file__).with_name("__init__.py")
    spec = importlib.util.spec_from_file_location("session_adapters_common", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _common()

CLIENT = {"name": "agentscient-sessions", "title": "agentscient sessions bridge", "version": "2"}
# What the bridge answers to each request the app-server may send: every
# approval declined, every question left unanswered, nothing granted.
DECLINE = {
    "item/commandExecution/requestApproval": {"decision": "decline"},
    "item/fileChange/requestApproval": {"decision": "decline"},
    "item/permissions/requestApproval": {"permissions": {}},
    "mcpServer/elicitation/request": {"action": "decline"},
    "item/tool/requestUserInput": {"answers": {}},
    "applyPatchApproval": {"decision": "denied"},
    "execCommandApproval": {"decision": "denied"},
}
UNKNOWN = {"code": -32601, "message": "not handled by the agentscient sessions bridge"}


def thread_of(params) -> str | None:
    if not isinstance(params, dict):
        return None
    named = params.get("threadId")
    if named is None and isinstance(params.get("thread"), dict):
        named = params["thread"].get("id")
    return named if isinstance(named, str) else None


class Adapter(common.ProtocolAdapter):
    """Codex's app-server, launched through the profile by the bridge."""

    harness = "codex"
    jsonrpc = False

    def channel(self, member, binding):
        return ["app-server", "--listen", "stdio://"]

    def handshake(self, rpc):
        """`initialize`, `initialized`, `thread/start`; the thread id."""
        method = "initialize"
        try:
            rpc.request(method, {"clientInfo": CLIENT, "capabilities": {"experimentalApi": True}},
                        timeout=common.SUBMIT_TIMEOUT)
            rpc.notify("initialized")
            method = "thread/start"
            started = rpc.request(method, {}, timeout=common.SUBMIT_TIMEOUT)
        except common.channel.ChannelError as error:
            self.refuse_channel(method, error)
        thread = started.get("thread") if isinstance(started, dict) else None
        native = thread.get("id") if isinstance(thread, dict) else None
        if not isinstance(native, str) or not native:
            common.refuse("channel", "the codex handshake answering thread/start with thread.id",
                          f"thread/start: {json.dumps(started)[:200]}",
                          "read the member's channel.log; the harness did not speak its protocol")
        self.native = native
        return native

    def submit(self, rpc, text, *, busy):
        """A new turn when idle; into the active turn as `toolOutput` when busy."""
        params = {"threadId": self.native, "input": [{"type": "text", "text": text}]}
        if busy:
            params = {"threadId": self.native, "input": [],
                      "toolOutput": {"name": common.SERVER, "namespace": "agentscient",
                                     "output": text}}
        try:
            result = rpc.request("turn/start", params, timeout=common.SUBMIT_TIMEOUT)
        except common.channel.ChannelError as error:
            return self.settled("turn/start", error)
        turn = result.get("turn") if isinstance(result, dict) else None
        ident = turn.get("id") if isinstance(turn, dict) else None
        if not isinstance(ident, str) or not ident:
            return f"uncertain turn/start: answered without turn.id: {json.dumps(result)[:200]}"
        return f"accepted turn {ident}"

    def reconcile(self, rpc, message: str) -> str:
        """`seen M-n` when the thread's history carries the message's marker."""
        try:
            read = rpc.request("thread/read", {"threadId": self.native, "includeTurns": True},
                               timeout=common.SUBMIT_TIMEOUT)
        except common.channel.ChannelError as error:
            return f"unseen {message}: thread/read {error.reading}"
        if common.marker(message) in json.dumps(read, ensure_ascii=False):
            return f"seen {message}"
        return f"unseen {message}: not in thread/read"

    def observe(self, rpc, frame):
        """One received frame, classified; a request is answered here."""
        if "reconcile" in frame:
            return self.reconcile(rpc, str(frame["reconcile"]))
        method = frame.get("method")
        params = frame.get("params") if isinstance(frame.get("params"), dict) else {}
        if "id" in frame and method is not None:
            return self.answer(rpc, frame, method, params)
        other = self.other_native(thread_of(params))
        if other is not None:
            return other
        if method == "turn/started":
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            self.turn = turn.get("id") or self.turn
            return "activity active"
        if method == "turn/completed":
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            done, self.turn = turn.get("id") or self.turn, None
            return f"done {done}"
        if method == "item/agentMessage/delta":
            return f"output {params.get('delta', '')}"
        if method == "mcpServer/startupStatus/updated":
            if params.get("name") == common.SERVER and params.get("status") == "ready":
                return f"tool {common.SERVER} ready"
            return f"activity {params.get('name')} {params.get('status')}"
        if method in ("item/started", "item/completed"):
            item = params.get("item") if isinstance(params.get("item"), dict) else {}
            if item.get("type") == "mcpToolCall":
                return f"tool {item.get('server')}/{item.get('tool')}"
            return "activity active"
        named = thread_of(params)
        return f"native {named}" if named else f"other {method}"

    def answer(self, rpc, frame, method, params):
        """Decline what the app-server asks; the prompt is printed, not kept."""
        other = self.other_native(thread_of(params))
        if method in DECLINE:
            rpc.answer(frame, result=DECLINE[method])
            title = (params.get("reason") or params.get("command") or params.get("message")
                     or method)
            if isinstance(title, list):
                title = " ".join(str(part) for part in title)
            return other or f"permission {title}"
        rpc.answer(frame, error=UNKNOWN)
        return other or f"permission {method} declined"
