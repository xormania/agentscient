"""The grok adapter: one Grok ACP session, spoken to by the member's bridge
over `agent stdio`.

Contract: ops/conductor/sessions-lever.md, "The adapter boundary,
extended". Slice 1's five methods come from the shared module; this file
adds the channel argv, the handshake, the submission and the
classification of what the agent sends. The ACP shapes are the proof's
(Source: /home/scientdb/projects/poc/multi-harness-proof@a944f31,
mhproof/adapters.py:273-408, the Grok adapter's `start`, `request`,
`notification`, `prompt` and `deliver`: `initialize` with protocolVersion 1, `authenticate`
when methods are advertised, `session/new`, `session/prompt`,
`_x.ai/interject`, `session/update`, `_x.ai/session/prompt_complete`,
`session/request_permission` never approved: the proof asked the terminal,
the bridge answers the offered reject option, else cancelled).

Stdlib only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import uuid
from pathlib import Path


def _common():
    path = Path(__file__).with_name("__init__.py")
    spec = importlib.util.spec_from_file_location("session_adapters_common", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _common()

# `session/prompt` stays open until the turn ends; a submission reads
# `written` when no refusal came back within this grace.
PROMPT_GRACE = 2.0
UNKNOWN = {"code": -32601, "message": "declined: not handled by the sessions bridge"}


def channel_error(error) -> bool:
    """A ChannelError from any load of channel.py. Modules here are loaded by
    path, so one file can yield two classes and `except` on one misses the
    other (a caller's own RPC, as the adapter rows build)."""
    return type(error).__name__ == "ChannelError" and hasattr(error, "reading")


def tool_name(update: dict) -> str | None:
    meta = update.get("_meta") if isinstance(update.get("_meta"), dict) else {}
    tool = meta.get("x.ai/tool") if isinstance(meta.get("x.ai/tool"), dict) else None
    if tool is not None and tool.get("name"):
        namespace = tool.get("namespace")
        return f"{namespace}/{tool['name']}" if namespace else str(tool["name"])
    title = update.get("title")
    return str(title) if title else None


def acp_servers(binding) -> list:
    """The binding's native MCP servers as ACP `session/new` entries.

    Measured 2026-09-23 on grok 1.0.40 over `agent stdio`: with
    `mcpServers: []` and no servers in its config, `_x.ai/mcp_initialized`
    reads mcpToolCount 0; with a stdio entry named `coordination`, grok
    starts it (initialize, tools/list), reads mcpToolCount 1 and sends
    `_x.ai/mcp/server_status` {name: coordination, status: ready}. An entry
    with a `url` is passed as http; one with neither command nor url is
    left out."""
    settings = binding.get("native_settings") if isinstance(binding, dict) else None
    servers = settings.get("mcp_servers") if isinstance(settings, dict) else None
    entries = []
    for name, spec in (servers or {}).items() if isinstance(servers, dict) else ():
        if not isinstance(spec, dict):
            continue
        env = spec.get("env") if isinstance(spec.get("env"), dict) else {}
        if spec.get("command"):
            entries.append({"name": str(name), "command": str(spec["command"]),
                            "args": [str(arg) for arg in spec.get("args") or []],
                            "env": [{"name": str(key), "value": str(value)}
                                    for key, value in env.items()]})
        elif spec.get("url"):
            headers = spec.get("headers") if isinstance(spec.get("headers"), dict) else {}
            entries.append({"type": "http", "name": str(name), "url": str(spec["url"]),
                            "headers": [{"name": str(key), "value": str(value)}
                                        for key, value in headers.items()]})
    return entries


class Adapter(common.ProtocolAdapter):
    """Grok's ACP agent, launched through the profile by the bridge."""

    harness = "grok"
    jsonrpc = True
    # The directory the harness was spawned in, kept from `connect`.
    cwd = None
    # The MCP servers `session/new` names, kept from `channel`.
    servers = ()

    def channel(self, member, binding):
        self.servers = acp_servers(binding)
        return ["--no-auto-update", "agent", "stdio"]

    def connect(self, argv, *, env=None, cwd=None, stderr=None):
        """The channel, and the directory it runs in kept for `session/new`."""
        self.cwd = cwd
        return super().connect(argv, env=env, cwd=cwd, stderr=stderr)

    def workdir(self, rpc) -> str:
        """The directory the session works in: the one the harness was
        spawned in (the channel's, else `connect`'s), and the bridge's own
        only when neither was given. ACP asks for an absolute path."""
        named = getattr(rpc, "cwd", None) or self.cwd
        return str(Path(named).absolute()) if named else os.getcwd()

    def handshake(self, rpc):
        """`initialize`, `authenticate` when advertised, `session/new`; the session id."""
        method = "initialize"
        try:
            init = rpc.request(method, {"protocolVersion": 1, "clientCapabilities": {}},
                               timeout=common.SUBMIT_TIMEOUT)
            methods = [entry.get("id") for entry in init.get("authMethods") or []
                       if isinstance(entry, dict) and entry.get("id")]
            if methods:
                # The proof's choice: the API key when one is in the
                # environment and advertised, the cached login otherwise.
                chosen = ("xai.api_key" if os.environ.get("XAI_API_KEY") and "xai.api_key" in methods
                          else "cached_token")
                method = "authenticate"
                rpc.request(method, {"methodId": chosen, "_meta": {"headless": True}},
                            timeout=common.SUBMIT_TIMEOUT)
            method = "session/new"
            opened = rpc.request(method, {"cwd": self.workdir(rpc), "mcpServers": self.servers},
                                 timeout=common.SUBMIT_TIMEOUT)
        except Exception as error:
            if not channel_error(error):
                raise
            self.refuse_channel(method, error)
        native = opened.get("sessionId") if isinstance(opened, dict) else None
        if not isinstance(native, str) or not native:
            common.refuse("channel", "the grok handshake answering session/new with sessionId",
                          f"session/new: {json.dumps(opened)[:200]}",
                          "read the member's channel.log; the harness did not speak its protocol")
        self.native = native
        return native

    def submit(self, rpc, text, *, busy):
        """`_x.ai/interject` into the running prompt when busy; a new
        `session/prompt` when idle, `written` once it left without a refusal."""
        if busy:
            try:
                rpc.request("_x.ai/interject",
                            {"sessionId": self.native, "text": text,
                             "interjectionId": str(uuid.uuid4())},
                            timeout=common.SUBMIT_TIMEOUT)
            except Exception as error:
                if not channel_error(error):
                    raise
                return self.settled("_x.ai/interject", error)
            return "written"
        try:
            pending = rpc.send("session/prompt", {"sessionId": self.native,
                                                  "prompt": [{"type": "text", "text": text}]})
        except Exception as error:
            if not channel_error(error):
                raise
            return self.settled("session/prompt", error)
        try:
            pending.wait(PROMPT_GRACE)
        except Exception as error:
            if not channel_error(error):
                raise
            if not error.reading.startswith("no answer within"):
                return self.settled("session/prompt", error)
        return "written"

    def reconcile(self, rpc, message: str) -> str:
        """Grok offers no read of a session's history on this channel, so a
        crashed submission is never read as seen."""
        return f"unseen {message}: no history read on the grok channel"

    def observe(self, rpc, frame):
        if "reconcile" in frame:
            return self.reconcile(rpc, str(frame["reconcile"]))
        method = frame.get("method")
        params = frame.get("params") if isinstance(frame.get("params"), dict) else {}
        other = self.other_native(params.get("sessionId"))
        if "id" in frame and method is not None:
            return self.answer(rpc, frame, method, params, other)
        if other is not None:
            return other
        if method == "session/update":
            update = params.get("update") if isinstance(params.get("update"), dict) else {}
            kind = update.get("sessionUpdate")
            if kind == "agent_message_chunk":
                content = update.get("content") if isinstance(update.get("content"), dict) else {}
                return f"output {content.get('text', '')}"
            if kind in ("tool_call", "tool_call_update"):
                name = tool_name(update)
                return f"tool {name}" if name else "activity active"
            return "activity active"
        if method == "_x.ai/mcp/server_status":
            if params.get("name") == common.SERVER and params.get("status") == "ready":
                return f"tool {common.SERVER} ready"
            return f"activity {params.get('name')} {params.get('status')}"
        if method == "_x.ai/session/prompt_complete":
            done = params.get("promptId") or params.get("turn") or params.get("stopReason")
            return f"done {done or 'prompt'}"
        named = params.get("sessionId")
        return f"native {named}" if named else f"other {method}"

    def answer(self, rpc, frame, method, params, other):
        """Decline what the agent asks: the offered reject option, else
        cancelled; the prompt is printed to the pane, not kept."""
        if method == "session/request_permission":
            call = params.get("toolCall") if isinstance(params.get("toolCall"), dict) else {}
            title = call.get("title") or params.get("title") or method
            options = [entry for entry in params.get("options") or [] if isinstance(entry, dict)]
            reject = next((entry.get("optionId") for entry in options
                           if str(entry.get("kind", "")).startswith("reject")), None)
            outcome = ({"outcome": "selected", "optionId": reject} if reject
                       else {"outcome": "cancelled"})
            rpc.answer(frame, result={"outcome": outcome})
            offered = ", ".join(str(entry.get("optionId")) for entry in options) or "none"
            print(f"permission asked: {title}; offered {offered}; answered "
                  f"{reject or 'cancelled'}", flush=True)
            return other or f"permission {title}"
        rpc.answer(frame, error=UNKNOWN)
        print(f"permission asked: {method}; answered declined, not handled", flush=True)
        return other or f"permission {method}"
