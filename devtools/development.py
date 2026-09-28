"""Installed Symfony capabilities and named checks, invoked behind the MCP surface."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import signal
import subprocess
import tempfile
from pathlib import Path

from .artifacts import Artifacts
from .workspaces import Workspaces, git, project_config

DEFAULT_CHECKS = {
    "container": ["php", "bin/console", "lint:container", "--no-interaction"],
    "configuration": ["php", "bin/console", "lint:yaml", "config", "--parse-tags", "--no-interaction"],
    "tests": ["php", "vendor/bin/phpunit"],
}


def configured(store):
    return isinstance(project_config(store).get("development"), dict)


def capabilities(spec):
    name = {"type": "string", "minLength": 1, "maxLength": 160, "pattern": "[A-Za-z][A-Za-z0-9_.:-]*"}
    values = {"type": "object", "maxProperties": 30}
    return [
        spec(
            "framework_inspect",
            "Inspect installed basic Makers or call an installed Mate diagnostic in your job workspace. Results are retained and delivered automatically.",
            {
                "kind": {"type": "string", "enum": ["makers", "mate", "mate_resource", "packages"]},
                "name": name,
                "parameters": values,
                "resource": {"type": "string", "maxLength": 240,
                             "pattern": "^symfony-profiler://profile/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)?$"},
                "package": {"type": "string", "maxLength": 160,
                            "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.*-]+$"},
            },
            ("kind",),
        ),
        spec(
            "framework_generate",
            "Run an installed Symfony Maker with named arguments/options; preserve its native attributes and conventions. Results are retained and delivered automatically.",
            {
                "maker": {**name, "pattern": "make:[A-Za-z0-9_:-]+"},
                "arguments": values,
                "options": values,
            },
            ("maker",),
        ),
        spec(
            "work_check",
            "Run the configured validation for your current work and retain measured results; completion is delivered automatically.",
            {
                "check": {**name, "description": "Optional configured check name; omit for the full configured suite."},
            },
        ),
    ]


class Development:
    def __init__(self, store, member):
        self.store, self.member = store, member
        self.workspaces = Workspaces(store, member)
        self.config = project_config(store).get("development", {})

    def run(self, root, argv, *, timeout=120):
        """Only callers in this module construct commands; the MCP accepts no argv."""
        if self.workspaces.scope()["paused"]:
            raise ValueError("This work is paused; no new development process was started.")
        argv = [self.config.get("php", "php") if x == "php" and i == 0 else x for i, x in enumerate(argv)]
        env = {
            k: v
            for k, v in os.environ.items()
            if k in {"PATH", "HOME", "LANG", "TMPDIR", "COMPOSER_HOME", "COMPOSER_CACHE_DIR"}
        }
        env.update(APP_ENV="dev", APP_DEBUG="1", COMPOSER_NO_INTERACTION="1")
        php = Path(self.config.get("php", "php"))
        if php.is_absolute():
            env["PATH"] = str(php.parent) + os.pathsep + env.get("PATH", "")
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(
                argv,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise ValueError(
                    "Development operation timed out; changes were preserved. Inspect before retrying."
                ) from None
            size = output.tell()
            output.seek(0)
            text = output.read(2 * 1024 * 1024).decode(errors="replace")
        from .github_http import GitHubHTTP

        result = {
            "exit_code": process.returncode,
            "output": GitHubHTTP().clean(text),
            "truncated": size > 2 * 1024 * 1024,
        }
        if process.returncode < 0:
            try:
                result["signal"] = signal.Signals(-process.returncode).name
            except ValueError:
                result["signal"] = f"SIG{-process.returncode}"
        return result

    def prepare(self, root):
        root = Path(root)
        lock = root / "composer.lock"
        if not lock.is_file():
            raise ValueError("The project needs its committed Composer lock before using Symfony development tools.")
        fingerprint = hashlib.sha256(lock.read_bytes() + (root / "composer.json").read_bytes()).hexdigest()
        marker = root / "vendor/.agentscient-dependencies"
        if marker.is_file() and marker.read_text() == fingerprint and (root / "vendor/autoload.php").is_file():
            return
        # A worktree owns its vendor directory: a symlink to another checkout would load the wrong application.
        if (root / "vendor").is_symlink():
            raise ValueError("The job's vendor directory must not be a symlink to another checkout.")
        result = self.run(
            root,
            [self.config.get("composer", "composer"), "install", "--prefer-dist", "--no-interaction", "--no-progress"],
            timeout=600,
        )
        if result["exit_code"]:
            self.evidence("dependencies.txt", result)
            raise ValueError("Locked dependency installation failed: " + result["output"][-1800:])
        marker.write_text(fingerprint)

    def evidence(self, name, result):
        scope = self.workspaces.control.current()
        saved = Artifacts(self.store, self.member).ingest(
            name,
            io.BytesIO(json.dumps(result, ensure_ascii=False).encode()),
            "application/json",
            work_order=scope["work_order"],
            job=scope["job"],
        )
        return "artifact:" + str(saved["artifact"]["id"])

    def _json(self, root, argv):
        result = self.run(root, argv)
        if result["exit_code"]:
            raise ValueError(result["output"][-1800:])
        try:
            return json.loads(result["output"])
        except ValueError:
            raise ValueError(
                "Installed command did not return valid JSON metadata: " + result["output"][:600]
            ) from None

    def inspect(self, kind, name=None, parameters=None, resource=None, package=None):
        if kind == "packages":
            if name or parameters is not None or resource or not package or not re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.*-]+", package
            ):
                raise ValueError("Supply only a package name or vendor/package* filter")
        elif package:
            raise ValueError("package is only available for kind packages")
        if kind == "mate_resource":
            if name or parameters is not None or not resource or not re.fullmatch(
                r"symfony-profiler://profile/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)?", resource
            ):
                raise ValueError("Supply only a profiler resource URI returned by Mate")
        elif resource:
            raise ValueError("resource is only available for kind mate_resource")
        with self.workspaces.use() as (_, workspace):
            root = workspace["root"]
            self.prepare(root)
            if kind == "makers":
                if parameters:
                    raise ValueError("Use framework_generate to run a Maker.")
                if name and not name.startswith("make:"):
                    raise ValueError("Choose an installed make: command.")
                value = self._json(
                    root,
                    [
                        "php",
                        "bin/console",
                        *(["help", name] if name else ["list", "make"]),
                        "--format=json",
                        "--no-interaction",
                    ],
                )
                if not name:
                    value = {
                        "makers": [
                            {"name": r["name"], "description": r["description"]}
                            for r in value["commands"]
                            if r["name"].startswith("make:")
                        ]
                    }
            elif kind == "mate_resource":
                value = self._json(root, ["vendor/bin/mate", "resources:read", resource, "--format=json"])
            elif kind == "packages":
                value = self._json(root, [self.config.get("composer", "composer"), "show", "--format=json", package])
            else:
                tools = self._json(root, ["vendor/bin/mate", "tools:list", "--format=json"])["tools"]
                if name:
                    if name not in tools:
                        raise ValueError("Choose a diagnostic from the installed Mate tools.")
                    value = (
                        tools[name]
                        if parameters is None
                        else self._json(
                            root,
                            [
                                "vendor/bin/mate",
                                "tools:call",
                                name,
                                "--format=json",
                                "--json=" + json.dumps(parameters),
                            ],
                        )
                    )
                else:
                    if parameters:
                        raise ValueError("Name the installed Mate diagnostic to call.")
                    value = {
                        "tools": [
                            {"name": name, "description": row.get("description"), "parameters": row.get("input_schema")}
                            for name, row in tools.items()
                        ]
                    }
            return self.result("framework-inspection.json", value)

    @staticmethod
    def maker_argv(metadata, arguments, options):
        definition = metadata["definition"]
        positional = {k: v for k, v in definition["arguments"].items() if k != "command"}
        if arguments.keys() - positional.keys() or options.keys() - definition["options"].keys():
            raise ValueError("Use argument and option names from this installed Maker's metadata.")
        forbidden = {
            "env",
            "no-debug",
            "help",
            "version",
            "quiet",
            "silent",
            "verbose",
            "ansi",
            "no-ansi",
            "no-interaction",
            "profile",
        }
        if options.keys() & forbidden:
            raise ValueError("Runtime and global console options are managed by the service.")
        argv = ["php", "bin/console", metadata["name"], "--no-interaction", "--no-ansi"]
        for key, value in options.items():
            option = definition["options"][key]
            if not option["accept_value"]:
                if type(value) is not bool:
                    raise ValueError("Flag options must be boolean.")
                if value:
                    argv.append("--" + key)
            else:
                values = value if isinstance(value, list) and option["is_multiple"] else [value]
                for item in values:
                    if not isinstance(item, (str, int, float)) or isinstance(item, bool):
                        raise ValueError("Maker option values must be scalar, or arrays for multiple options.")
                    argv.append("--" + key + "=" + str(item))
        argv.append("--")
        for key, argument in positional.items():
            value = arguments.get(key, argument.get("default"))
            if value is None:
                if argument["is_required"]:
                    raise ValueError("Missing Maker argument: " + key)
                value = ""
            values = value if isinstance(value, list) and argument["is_array"] else [value]
            if any(not isinstance(item, (str, int, float)) or isinstance(item, bool) for item in values):
                raise ValueError("Maker arguments must be scalar, or arrays for variadic arguments.")
            argv.extend(str(item) for item in values)
        return argv

    def generate(self, maker, arguments=None, options=None):
        with self.workspaces.use(write=True) as (scope, workspace):
            if scope["role"] not in {"coder", "test_writer"}:
                raise ValueError("This role cannot generate Symfony code.")
            if scope["role"] == "test_writer" and maker != "make:test":
                raise ValueError("Test writers use the installed make:test Maker.")
            root = workspace["root"]
            self.prepare(root)
            metadata = self._json(root, ["php", "bin/console", "help", maker, "--format=json", "--no-interaction"])
            if metadata["name"] != maker or not maker.startswith("make:"):
                raise ValueError("Choose an installed Symfony Maker.")
            self.workspaces.scope(write=True)
            result = self.run(root, self.maker_argv(metadata, arguments or {}, options or {}))
            result["changes"] = self.workspaces.changes(root)
            result["outside_role_paths"] = [
                r["path"] for r in result["changes"] if not self.workspaces.permitted_path(r["path"], scope["role"])
            ]
            return self.result("maker-result.json", result)

    def result(self, name, value):
        evidence = self.evidence(name, value)
        text = json.dumps(value, ensure_ascii=False)
        return {
            "result": value if len(text) <= 10000 else None,
            "preview": text[:10000] if len(text) > 10000 else None,
            "evidence": evidence,
        }

    def checks(self, root, check=None):
        self.prepare(root)
        checks = self.config.get("checks", DEFAULT_CHECKS)
        if not checks or check is not None and check not in checks:
            raise ValueError("Choose a configured check: " + ", ".join(checks))
        results = []
        for name, argv in checks.items():
            if check is not None and check != name:
                continue
            self.workspaces.scope()
            result = self.run(root, argv, timeout=self.config.get("check_timeout", 600))
            results.append(
                {
                    "check": name,
                    "exit_code": result["exit_code"],
                    **({"signal": result["signal"]} if "signal" in result else {}),
                    "output": result["output"][-2500:],
                    "evidence": self.evidence("check-" + name + ".json", result),
                }
            )
        return {
            "passed": all(row["exit_code"] == 0 for row in results),
            "checks": results,
            "revision": git(root, "rev-parse", "HEAD").stdout.decode().strip(),
            "uncommitted": self.workspaces.changes(root),
        }

    def check(self, check=None):
        with self.workspaces.use() as (_, workspace):
            return self.checks(workspace["root"], check)
