"""Stdio MCP with concurrent calls and Claude's proved live channel transport."""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from . import VERSION
from .api import API, SERVER, render

MAX_FRAME = 131072


def serve(directory, member, channel=False, operator=False):
    api = API(directory, member, operator=operator)
    output_lock = threading.Lock()
    initialized = threading.Event()
    stopped = threading.Event()

    def write(packet):
        encoded = json.dumps({"jsonrpc": "2.0", **packet}, ensure_ascii=False)
        with output_lock:
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()

    def channels():
        initialized.wait()
        while not stopped.wait(0.1):
            session = api.store.member(member)
            if session["desired"] != "running" or session["state"] not in {"idle", "active"}:
                continue
            message = api.store.take_delivery(member, scoped=not operator)
            if message is None:
                continue
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
        ident, method = packet.get("id"), packet.get("method")
        if method == "notifications/initialized":
            initialized.set()
            api.store.event(member, "mcp_ready", channel=channel)
            return
        if ident is None:
            return
        try:
            if method == "initialize":
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
        tool_names = [row["name"] for row in api.tools()]
        initialized.wait()
        while not stopped.wait(1):
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

    if channel:
        threading.Thread(target=channels, daemon=True).start()
    threading.Thread(target=watches, daemon=True).start()
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
                    pool.submit(handle, packet)
                else:
                    handle(packet)
        finally:
            stopped.set()
            initialized.set()
