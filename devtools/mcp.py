"""Stdio MCP with concurrent calls and Claude's proved live channel transport."""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from . import VERSION
from .api import API, SERVER, render
from .sessions import Lease
from .telemetry import Trace, context

MAX_FRAME = 131072


def serve(directory, member, channel=False, operator=False, generation=None):
    api = API(directory, member, operator=operator)
    lease = Lease(api.store, member, generation, operator=operator)
    output_lock = threading.Lock()
    initialized = threading.Event()
    stopped = threading.Event()
    tool_names = [row["name"] for row in api.tools()]
    trace = Trace(
        directory,
        member,
        component="mcp",
        context=lambda: {
            **context(api.store, member),
            "connection_generation": lease.generation,
        },
    )

    def write(packet):
        trace.record("mcp_out", packet)
        encoded = json.dumps({"jsonrpc": "2.0", **packet}, ensure_ascii=False)
        with output_lock:
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()

    def channels():
        initialized.wait()
        while not stopped.wait(0.1):
            try:
                with lease.hold():
                    deliver_channel()
            except ValueError:
                stopped.set()

    def deliver_channel():
        session = api.store.member(member)
        if session["desired"] != "running" or session["state"] not in {"idle", "active"}:
            return
        message = api.store.take_delivery(member, scoped=not operator)
        if message is None:
            return
        try:
            write(
                {
                    "method": "notifications/claude/channel",
                    "params": {
                        "content": render(message) if operator else api.control.render(message),
                        "meta": {"message_id": str(message["id"]), "sender_id": message["sender"]},
                    },
                }
            )
            api.store.delivered(member, message["id"], message["attempt"], transport="claude/channel")
        except Exception as error:
            api.store.delivered(member, message["id"], message["attempt"], error=str(error)[:1000])
            stopped.set()

    def handle(packet):
        try:
            with lease.hold():
                handle_current(packet)
        except ValueError as error:
            if packet.get("id") is not None:
                write({"id": packet["id"], "error": {"code": -32602, "message": str(error)}})

    def handle_current(packet):
        ident, method = packet.get("id"), packet.get("method")
        if method == "notifications/initialized":
            initialized.set()
            api.store.event(member, "mcp_ready", channel=channel)
            return
        if ident is None:
            return
        try:
            if method == "initialize":
                api.store.event(
                    member,
                    "mcp_client",
                    client=packet.get("params", {}).get("clientInfo", {}),
                    connection=trace.connection,
                    channel=channel,
                    operator=operator,
                )
                caps = {"tools": {"listChanged": not operator}}
                if channel:
                    caps["experimental"] = {"claude/channel": {}}
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": caps,
                    "serverInfo": {"name": SERVER, "version": VERSION},
                    "instructions": api.instructions(),
                }
            elif method == "ping":
                result = {}
            elif not initialized.is_set():
                raise ValueError("Initialize this MCP session first")
            elif method == "tools/list":
                result = {"tools": api.tools()}
            elif method == "tools/call":
                params = packet.get("params", {})
                try:
                    value = api.call(params["name"], params.get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
                except Exception as error:
                    result = {"isError": True, "content": [{"type": "text", "text": str(error)[:2000]}]}
            else:
                write({"id": ident, "error": {"code": -32601, "message": "Unknown MCP method"}})
                return
            write({"id": ident, "result": result})
        except Exception as error:
            write({"id": ident, "error": {"code": -32602, "message": str(error)[:2000]}})

    def watches():
        initialized.wait()
        while not stopped.wait(1):
            try:
                with lease.hold():
                    watch_current()
            except ValueError:
                stopped.set()

    def watch_current():
        nonlocal tool_names
        try:
            current = [row["name"] for row in api.tools()]
            if current != tool_names:
                write({"method": "notifications/tools/list_changed"})
                tool_names = current
            api.github.tick()
        except Exception as error:
            api.store.event(member, "github_watch_error", error=api.github.http.clean(str(error))[:1000])
        try:
            api.commands.tick()
            api.operations.tick()
        except Exception as error:
            api.store.event(member, "command_watch_error", error=str(error)[:1000])

    def cleanup():
        from .retirement import Retirement

        initialized.wait()
        while not stopped.wait(2):
            try:
                with lease.hold():
                    Retirement(api.store, member).tick()
            except ValueError:
                stopped.set()
            except Exception as error:
                api.store.event(member, "cleanup_watch_error", error=str(error)[:1000])

    if channel:
        threading.Thread(target=channels, daemon=True).start()
    threading.Thread(target=watches, daemon=True).start()
    threading.Thread(target=cleanup, daemon=True).start()
    with ThreadPoolExecutor(max_workers=4) as pool:
        try:
            while line := sys.stdin.buffer.readline(MAX_FRAME + 1):
                try:
                    if len(line) > MAX_FRAME:
                        raise ValueError("MCP frame exceeds 128 KiB")
                    packet = json.loads(line)
                    if not isinstance(packet, dict) or not isinstance(packet.get("method"), str):
                        raise ValueError("Expected a JSON-RPC request object")
                except ValueError as error:
                    write({"id": None, "error": {"code": -32700, "message": str(error)}})
                    if len(line) > MAX_FRAME:
                        break
                    continue
                if packet["method"] == "tools/call":
                    trace.record("mcp_in", packet)
                    pool.submit(handle, packet)
                else:
                    trace.record("mcp_in", packet)
                    handle(packet)
        finally:
            stopped.set()
            initialized.set()
    trace.record("mcp_closed", {})
    trace.close()
