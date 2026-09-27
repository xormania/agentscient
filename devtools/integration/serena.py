#!/usr/bin/env python3
"""Real Serena v2 container acceptance over stdio MCP; no model credentials are needed."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "devtools/tests"))

from support import Client  # noqa: E402

from devtools.api import API  # noqa: E402
from devtools.launch import initialize  # noqa: E402
from devtools.workspaces import git  # noqa: E402


def repl(client, code):
    ident = client.begin("tools/call", {"name": "serena_repl", "arguments": {"code": code}})
    value = client.finish(ident, timeout=115)
    assert not value.get("isError"), value
    return "\n".join(row["text"] for row in value["content"] if row["type"] == "text")


def main():
    image = os.environ.get("AGENTSCIENT_SERENA_IMAGE", "agentscient-serena:v2-beta")
    with tempfile.TemporaryDirectory(prefix="agentscient-serena-") as temporary:
        root = Path(temporary)
        checkout = root / "checkout"
        (checkout / "src").mkdir(parents=True)
        (checkout / "devtools").mkdir()
        (checkout / "src/Example.php").write_text(
            "<?php\nnamespace App;\nclass Example { public function greeting(): string { return 'hello'; } }\n"
        )
        (checkout / "devtools/protected.txt").write_text("unchanged")
        subprocess.run(["git", "init", "-b", "dev", str(checkout)], check=True, capture_output=True)
        git(checkout, "config", "user.name", "Fixture")
        git(checkout, "config", "user.email", "fixture@example.invalid")
        git(checkout, "add", ".")
        git(checkout, "commit", "-m", "Initial")
        state = root / "state"
        initialize(state, checkout, ["owner:external", "xo:external", "coder:external"], co="owner")
        config = json.loads((state / "team.json").read_text())
        config["project"] = {
            "checkout": str(checkout),
            "target": "dev",
            "repository": "example/fixture",
            "serena": {"image": image},
        }
        (state / "team.json").write_text(json.dumps(config))
        API(state, "owner").call(
            "direct",
            {
                "title": "Serena acceptance",
                "objective": "Use v2 REPL",
                "done_when": "Symbol discovery, persistent variables and bounded edits work",
                "constraints": "Disposable job",
            },
        )
        xo = API(state, "xo")
        xo.call(
            "orchestrate",
            {
                "work": [
                    {
                        "name": "Serena example",
                        "role": "coder",
                        "objective": "Inspect and edit",
                        "done_when": "Evidence",
                        "constraints": "Source only",
                    }
                ]
            },
        )
        client = Client(state, "coder", provider="serena")
        try:
            assert {r["name"] for r in client.call("tools/list")["tools"]} == {"serena_repl"}
            assert "42" in repl(client, "answer = 42; answer")
            assert "42" in repl(client, "answer")
            documentation = repl(client, "s.info('lsp.get_symbols_overview', 'edit.replace_content')")
            assert "get_symbols_overview" in documentation, documentation
            symbols = repl(client, "s.lsp.get_symbols_overview('src/Example.php', depth=1)")
            assert "Example" in symbols and "greeting" in symbols, symbols
            edited = repl(client, "s.edit.replace_content('src/Example.php', 'hello', 'welcome', 'literal')")
            assert "Error" not in edited, edited
            workspace = Path(API(state, "coder").workspaces.ensure()["root"])
            assert "welcome" in (workspace / "src/Example.php").read_text(), edited
            blocked = repl(
                client,
                "from pathlib import Path\ntry:\n Path('/workspace/devtools/protected.txt').write_text('wrong')\nexcept OSError:\n print('protected')",
            )
            assert "protected" in blocked, blocked
            assert (workspace / "devtools/protected.txt").read_text() == "unchanged"
            assert "False" in repl(client, "Path('/var/run/docker.sock').exists()")
            xo.call("steer", {"action": "pause", "work": "Serena example"})
            response = client.call("tools/call", {"name": "serena_repl", "arguments": {"code": "answer"}})
            assert response.get("isError") and "paused" in json.dumps(response), response
            xo.call("steer", {"action": "resume", "work": "Serena example"})
            assert "42" in repl(client, "answer")
            API(state, "coder").call("work_save", {"note": "Serena-generated change"})
            print(
                json.dumps(
                    {
                        "accepted": [
                            "Serena v2 REPL",
                            "persistent variables",
                            "PHPactor symbol navigation",
                            "Serena edit facade",
                            "protected source mount",
                            "no Docker socket",
                            "live pause/resume",
                            "control-plane checkpoint",
                        ],
                        "symbols": symbols,
                    }
                )
            )
        except Exception:
            path = state / "telemetry/coder-serena.log"
            if path.exists():
                print(path.read_text()[-18000:], file=sys.stderr)
            raise
        finally:
            client.close()


if __name__ == "__main__":
    main()
