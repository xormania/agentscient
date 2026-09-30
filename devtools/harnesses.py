"""Installed native harness adapters selected through the shared operator manifest.

Manifest harness entries name zero-argument factories. Instances declare vendor
and supports_provider and implement prepare(directory, member), permitted(tool,
arguments, catalogue=...), hook(directory, member, payload), run(directory,
member, config, generation), command(directory, member, config, private, server),
channel(private), retain_login(directory, member, generation), and
readiness(binary, probe). prepare returns (private_path, environment, MCP_config);
command returns (argv, native_session_id). run owns one persistent session;
the common launcher retains generation, work binding and cleanup ownership.
"""

from __future__ import annotations

import asyncio

from .adapters import factory


def get(name):
    adapter = factory("harness", name)()
    methods = ("prepare", "permitted", "hook", "run", "command", "channel", "retain_login", "readiness")
    if (any(not callable(getattr(adapter, method, None)) for method in methods)
            or not isinstance(getattr(adapter, "vendor", None), str) or not adapter.vendor
            or type(getattr(adapter, "supports_provider", None)) is not bool):
        raise ValueError("Harness adapters must implement profile, permission, hook, session and console capabilities.")
    # The configured name is identity; its adapter owns the underlying protocol.
    adapter.name = name
    return adapter


class BuiltinHarness:
    protocol = None
    supports_provider = False

    def prepare(self, directory, member):
        from .profiles import _prepare_builtin

        return _prepare_builtin(directory, member, self.protocol, adapter_name=self.name)

    def permitted(self, tool, arguments, *, catalogue=None):
        from .profiles import _permitted_builtin

        return _permitted_builtin(self.protocol, tool, arguments, catalogue=catalogue)

    def hook(self, directory, member, payload):
        from .profiles import _hook_builtin

        return _hook_builtin(directory, member, self.name, payload, protocol=self.protocol)

    def retain_login(self, directory, member, generation):
        from .profiles import _retain_login_builtin

        return _retain_login_builtin(directory, member, self.protocol, generation)

    def command(self, directory, member, config, private, server):
        from .console import _command_builtin

        return _command_builtin(directory, member, config, private, server, protocol=self.protocol)

    def channel(self, private):
        return None

    def readiness(self, binary, probe):
        return {"protocol": self.readiness_message}

    def run(self, directory, member, config, generation):
        from .native import Native

        return asyncio.run(Native(directory, member, config, generation).run())


class CodexHarness(BuiltinHarness):
    protocol = "codex"
    vendor = "openai"
    supports_provider = True

    def readiness(self, binary, probe):
        from .compat import codex_capability

        capability = codex_capability(binary)
        if capability["status"] != "supported":
            raise ValueError("Installed Codex must support TurnStartParams.toolOutput; update before launch.")
        return {"protocol": capability}


class GrokHarness(BuiltinHarness):
    protocol = "grok"
    vendor = "xai"
    readiness_message = "ACP authentication and session creation are checked on actual startup."


class ClaudeHarness(BuiltinHarness):
    protocol = "claude"
    vendor = "anthropic"
    readiness_message = "Channel registration is checked on actual startup."

    def channel(self, private):
        from .compat import ClaudeChannelLog

        return ClaudeChannelLog(private / "native-debug.log")

    def run(self, directory, member, config, generation):
        from .native import claude

        return claude(directory, member, config, generation)
