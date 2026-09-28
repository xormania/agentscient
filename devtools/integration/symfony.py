#!/usr/bin/env python3
"""Exercise actual installed Makers/Mate through normal MCP, in a disposable job worktree."""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "devtools/tests"))

from support import Client  # noqa: E402

from devtools.api import API  # noqa: E402
from devtools.launch import initialize  # noqa: E402
from devtools.readiness import platform  # noqa: E402
from devtools.workspaces import git  # noqa: E402


def completed(client, tool, arguments):
    value = client.tool(tool, arguments)
    reference = value["reference"]
    deadline = time.monotonic() + 700
    while value["state"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.2)
        value = next(
            row
            for row in client.tool("work_inspect", {"section": "operations"})["operations"]
            if row["reference"] == reference
        )
    assert value["state"] == "completed", value
    return value["result"]


def main():
    platform_result = platform(REPO, {})
    with tempfile.TemporaryDirectory(prefix="agentscient-symfony-") as temporary:
        root = Path(temporary)
        checkout = root / "checkout"
        subprocess.run(["git", "clone", "--no-hardlinks", str(REPO), str(checkout)], check=True, capture_output=True)
        git(checkout, "branch", "fixture-base", "HEAD")
        git(checkout, "config", "user.name", "Integration fixture")
        git(checkout, "config", "user.email", "fixture@example.invalid")
        state = root / "state"
        initialize(state, checkout, ["owner:external", "xo:external", "coder:external"], co="owner")
        config = json.loads((state / "team.json").read_text())
        config["project"] = {
            "checkout": str(checkout),
            "target": "fixture-base",
            "repository": "example/fixture",
            "fetch": False,
            "development": {},
        }
        (state / "team.json").write_text(json.dumps(config))
        co, xo, coder = [Client(state, member) for member in ("owner", "xo", "coder")]
        try:
            co.tool(
                "direct",
                {
                    "title": "Development provider acceptance",
                    "objective": "Use installed framework conventions",
                    "done_when": "Generation, diagnostics and checks have evidence",
                    "constraints": "Disposable workspace only",
                },
            )
            xo.tool(
                "orchestrate",
                {
                    "work": [
                        {
                            "name": "Exercise Symfony",
                            "role": "coder",
                            "objective": "Generate with native Makers",
                            "done_when": "Attributes and autoconfiguration work",
                            "constraints": "No handwritten replacement generator",
                        }
                    ]
                },
            )
            makers = completed(coder, "framework_inspect", {"kind": "makers"})["result"]["makers"]
            assert "make:command" in {row["name"] for row in makers}, makers
            metadata = completed(coder, "framework_inspect", {"kind": "makers", "name": "make:command"})["result"]
            assert "name" in metadata["definition"]["arguments"], metadata
            generated = completed(
                coder, "framework_generate", {"maker": "make:command", "arguments": {"name": "app:fixture-command"}}
            )["result"]
            assert generated["exit_code"] == 0, generated
            workspace = Path(API(state, "coder").workspaces.ensure()["root"])
            command = next((workspace / "src/Command").glob("*.php")).read_text()
            assert "#[AsCommand" in command and "#[Argument" in command and "#[Option" in command, command
            actual = subprocess.run(
                ["php", "bin/console", "app:fixture-command", "--no-interaction"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            assert actual.returncode == 0, actual.stderr
            mate = completed(coder, "framework_inspect", {"kind": "mate", "name": "server-info", "parameters": {}})
            assert mate["result"], mate
            onboarding = coder.tool("onboard", {})
            assert onboarding["role"] == "coder" and len(onboarding["skills"]) == 8, onboarding
            coder.tool("skill_read", {"name": "mate-system-information"})
            package = completed(coder, "framework_inspect", {"kind": "packages", "package": "symfony/console"})
            assert package["result"]["name"] == "symfony/console", package
            tests = completed(
                coder,
                "framework_generate",
                {"maker": "make:test", "arguments": {"type": "TestCase", "name": "FixtureGeneratedTest"}},
            )["result"]
            assert tests["exit_code"] == 0, tests
            validation = completed(coder, "work_check", {})
            assert validation["passed"], validation
            print(
                json.dumps(
                    {
                        "accepted": [
                            "isolated dependency install",
                            "installed Maker metadata",
                            "attribute command generation",
                            "autoconfigured command execution",
                            "Mate server-info",
                            "test generation",
                            "configured checks",
                        ],
                        "mate": mate["result"],
                        "platform": platform_result,
                        "validation": validation,
                    },
                    indent=2,
                )
            )
        finally:
            for client in (coder, xo, co):
                client.close()


if __name__ == "__main__":
    main()
