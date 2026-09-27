#!/usr/bin/env python3
"""Operator bootstrap and stdio entry point; agents use MCP, not this CLI."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from devtools import launch
from devtools.api import API
from devtools.mcp import serve
from devtools.profiles import hook
from devtools.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "mcp", "agent", "start", "stop", "status", "send", "hook", "operation", "serena"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True, help="Private state directory outside source worktrees")
        if name not in {"init", "status"}:
            command.add_argument("--member", required=True)
        if name == "init":
            command.add_argument("--co", help="Name of the external user-facing CO session")
            command.add_argument("--workspace", required=True)
            command.add_argument("--member", action="append", required=True, help="name:codex|claude|grok|external")
        elif name == "mcp":
            command.add_argument("--channel", action="store_true")
            command.add_argument(
                "--operator", action="store_true", help="Trusted setup/diagnostics; never pass to managed agents"
            )
        elif name == "operation":
            command.add_argument("--operation", required=True, type=int)
        elif name == "agent":
            command.add_argument("--binding-revision", type=int, help=argparse.SUPPRESS)
        elif name == "send":
            command.add_argument("--to", required=True)
            command.add_argument("--body", required=True)
            command.add_argument("--key", required=True)
        elif name == "hook":
            command.add_argument("--harness", required=True, choices=("codex", "claude", "grok"))
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = launch.initialize(args.state, args.workspace, args.member, args.co)
        elif args.command == "mcp":
            serve(args.state, args.member, args.channel, args.operator)
            return 0
        elif args.command == "operation":
            from devtools.operations import execute

            execute(args.state, args.member, args.operation)
            return 0
        elif args.command == "serena":
            from devtools.serena_provider import serve as serena_serve

            serena_serve(args.state, args.member)
            return 0
        elif args.command == "agent":
            launch.agent(args.state, args.member, args.binding_revision)
            return 0
        elif args.command == "start":
            result = launch.start(args.state, args.member)
        elif args.command == "stop":
            Store(args.state).session(args.member, desired="stopped")
            result = {"member": args.member, "requested": "stopped"}
        elif args.command == "status":
            result = {"members": Store(args.state).members()}
        elif args.command == "send":
            result = API(args.state, args.member, operator=True).call(
                "capability_invoke",
                {"capability": "message_send", "arguments": {"to": args.to, "body": args.body, "key": args.key}},
            )
        else:
            payload = sys.stdin.buffer.read(131073)
            if len(payload) > 131072:
                raise ValueError("Hook payload exceeds 128 KiB")
            result = hook(args.state, args.member, args.harness, json.loads(payload))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        if args.command == "hook":
            # Hook errors must not accidentally enable a native tool.
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": "MCP-only hook failed; native tool denied.",
                        }
                    }
                )
            )
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
