"""Helpers for Graft adapter tests. Import ``support`` first in callers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
GRAFT_PY = HARNESS / "graft.py"
PIN_PATH = HARNESS / "graft" / "pin.json"
FAKE_PY = Path(__file__).resolve().parent / "fakes" / "graft_bridge.py"
AGENT = "Graft Test <noreply@example.invalid>"
REFUSAL_EXIT = 2
ABORT_EXIT = 3

CONF_DEFAULTS = {
    "LANE_NAME": "agentscient",
    "TRUNK_BRANCH": "dev",
    "RELEASE_BRANCH": "master",
    "REPO_SLUG": "uscient/agentscient",
    "CHECK_NAMES": "lane app",
    "WF_AGENT_DEFAULT": AGENT,
    "LANE_AUTHOR": "Lane Owner <lane-owner@example.invalid>",
    "MODEL_GROK": "model-grok",
    "MODEL_CODEX": "model-codex",
    "MODEL_CLAUDE_READ": "model-claude-read",
    "MODEL_CLAUDE_PLAN": "model-claude-plan",
    "EFFORT_GROK": "high",
    "EFFORT_CODEX": "high",
    "EFFORT_CLAUDE": "high",
    "WALL_DEFAULT": "900",
    "SCOPE_CAP": "1024",
    "GRAFT_INSTALL": "",
}


def load_fake():
    spec = importlib.util.spec_from_file_location("graft_bridge_fake", FAKE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_graft():
    spec = importlib.util.spec_from_file_location("graft_adapter", GRAFT_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pin() -> dict:
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_conf(path: Path, **overrides: object) -> Path:
    keys = dict(CONF_DEFAULTS)
    omit = tuple(overrides.pop("omit", ()) or ())
    for name, value in overrides.items():
        keys[name] = str(value)
    for name in omit:
        keys.pop(name, None)
    lines = ["# scratch lane conf\n"]
    for name, value in keys.items():
        lines.append(f"{name}='{value}'\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")
    return path


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({
        "GIT_AUTHOR_NAME": "graft-test",
        "GIT_AUTHOR_EMAIL": "graft-test@example.invalid",
        "GIT_COMMITTER_NAME": "graft-test",
        "GIT_COMMITTER_EMAIL": "graft-test@example.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    })
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {args} failed: {proc.stderr}")
    return proc


FETCH_NAMES = frozenset({"npm", "npx", "curl", "wget", "yarn", "pnpm"})
OBSERVER_SITE = '''\
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path


def _log_path():
    raw = os.environ.get("GRAFT_SPAWN_LOG")
    return Path(raw) if raw else None


def _record(kind, argv):
    path = _log_path()
    if path is None:
        return
    if isinstance(argv, (list, tuple)):
        argv = [str(x) for x in argv]
    else:
        argv = [str(argv)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": kind, "argv": argv}, sort_keys=True) + "\\n")


def _argv(popenargs, kwargs):
    if popenargs:
        args = popenargs[0]
    else:
        args = kwargs.get("args")
    if args is None:
        return []
    if isinstance(args, (list, tuple)):
        return [str(x) for x in args]
    return [str(args)]


_orig_run = subprocess.run
_orig_call = subprocess.call
_orig_check_call = subprocess.check_call
_orig_check_output = subprocess.check_output
_orig_popen = subprocess.Popen


def run(*a, **k):
    _record("run", _argv(a, k))
    return _orig_run(*a, **k)


def call(*a, **k):
    _record("call", _argv(a, k))
    return _orig_call(*a, **k)


def check_call(*a, **k):
    _record("check_call", _argv(a, k))
    return _orig_check_call(*a, **k)


def check_output(*a, **k):
    _record("check_output", _argv(a, k))
    return _orig_check_output(*a, **k)


class Popen(_orig_popen):
    def __init__(self, *a, **k):
        _record("popen", _argv(a, k))
        super().__init__(*a, **k)


subprocess.run = run
subprocess.call = call
subprocess.check_call = check_call
subprocess.check_output = check_output
subprocess.Popen = Popen

_orig_urlopen = urllib.request.urlopen


def urlopen(url, *a, **k):
    _record("urlopen", [str(url)])
    return _orig_urlopen(url, *a, **k)


urllib.request.urlopen = urlopen

if hasattr(urllib.request, "urlretrieve"):
    _orig_urlretrieve = urllib.request.urlretrieve

    def urlretrieve(url, *a, **k):
        _record("urlretrieve", [str(url)])
        return _orig_urlretrieve(url, *a, **k)

    urllib.request.urlretrieve = urlretrieve
'''

FETCH_STUB = '''\
#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

path = os.environ.get("GRAFT_SPAWN_LOG")
if path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "path-stub", "argv": sys.argv}, sort_keys=True) + "\\n")
raise SystemExit(1)
'''


def spawn_log_path(home: Path) -> Path:
    return Path(home) / "spawn-log.jsonl"


def install_spawn_observer(home: Path) -> Path:
    home = Path(home)
    observer = home / "spawn-observer"
    observer.mkdir(parents=True, exist_ok=True)
    (observer / "sitecustomize.py").write_text(OBSERVER_SITE, encoding="utf-8")
    bindir = home / "fetch-stubs"
    bindir.mkdir(parents=True, exist_ok=True)
    stub = bindir / "_fetch_stub"
    stub.write_text(FETCH_STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    for name in sorted(FETCH_NAMES):
        dest = bindir / name
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        dest.symlink_to(stub)
    return observer


def observer_env(home: Path) -> dict[str, str]:
    home = Path(home)
    observer = home / "spawn-observer"
    bindir = home / "fetch-stubs"
    pypath = str(observer)
    existing = os.environ.get("PYTHONPATH")
    if existing:
        pypath = pypath + os.pathsep + existing
    return {
        "PYTHONPATH": pypath,
        "GRAFT_SPAWN_LOG": str(spawn_log_path(home)),
        "PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
    }


def read_spawns(home: Path) -> list[dict]:
    path = spawn_log_path(home)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def drain_spawns(home: Path) -> list[dict]:
    rows = read_spawns(home)
    path = spawn_log_path(home)
    if path.is_file():
        path.write_text("", encoding="utf-8")
    return rows


def _argv_name(row: dict) -> str:
    argv = row.get("argv") or []
    if not argv:
        return ""
    return Path(str(argv[0])).name.lower()


def is_git_spawn(row: dict) -> bool:
    name = _argv_name(row)
    return name in {"git", "git.exe"}


def is_fetch_spawn(row: dict) -> bool:
    if row.get("kind") in {"urlopen", "urlretrieve", "path-stub"}:
        return True
    return _argv_name(row) in FETCH_NAMES


def assert_no_spawns(test, rows) -> None:
    test.assertEqual(list(rows), [], f"must not spawn or fetch: {rows!r}")


def assert_no_fetch(test, rows) -> None:
    bad = [row for row in rows if is_fetch_spawn(row)]
    test.assertEqual(bad, [], f"must not download or invoke npm: {bad!r}")


def assert_only_declared_bridge(test, rows, install: Path) -> None:
    assert_no_fetch(test, rows)
    install = Path(install)
    node = (install / "node" / "bin" / "node").resolve()
    bridge = (install / "graft" / "bridge.mjs").resolve()
    graft_dir = (install / "graft").resolve()
    others = [row for row in rows if not is_git_spawn(row)]
    test.assertTrue(others, "prepare/query must invoke the declared node bridge")
    for row in others:
        argv = [str(x) for x in (row.get("argv") or [])]
        test.assertGreaterEqual(len(argv), 3, argv)
        test.assertEqual(Path(argv[0]).resolve(), node, argv)
        test.assertEqual(Path(argv[1]).resolve(), bridge, argv)
        test.assertEqual(Path(argv[2]).resolve(), graft_dir, argv)


def published_descriptors(root: Path) -> list[Path]:
    root = Path(root)
    found = []
    if not root.exists():
        return found
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("schema") == "graft-context/1":
            found.append(path)
    return found


def assert_no_published_prepare(test, cache: Path, extra_roots=()) -> None:
    cache = Path(cache)
    test.assertFalse(
        (cache / "binding.json").exists(),
        "failed first prepare publishes no binding",
    )
    test.assertFalse(
        (cache / ".graph" / "wiring.json").exists(),
        "failed first prepare publishes no graph",
    )
    found = []
    for root in (cache, *extra_roots):
        found.extend(published_descriptors(root))
    test.assertEqual(found, [], f"failed first prepare publishes no descriptor: {found}")


def git_common_dir(repo: Path) -> Path:
    raw = git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(repo) / path
    return path.resolve()


def plant_linked_worktrees(home: Path) -> tuple[Path, Path]:
    main = Path(home) / "wt-main"
    plant_ops_root(main, {"ops/main.md": "main worktree\n"})
    git(main, "branch", "linked")
    linked = Path(home) / "wt-linked"
    git(main, "worktree", "add", str(linked), "linked")
    (linked / "ops" / "linked.md").write_text("linked worktree\n", encoding="utf-8")
    git(linked, "add", "-A")
    git(linked, "commit", "-m", "linked-ops")
    return main, linked


def plant_ops_root(path: Path, files: dict[str, str] | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    files = files or {"ops/lane.md": "ops source\n"}
    git(path, "init", "-b", "work")
    git(path, "config", "user.name", "graft-test")
    git(path, "config", "user.email", "graft-test@example.invalid")
    git(path, "config", "commit.gpgsign", "false")
    for rel, body in files.items():
        dest = path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-m", "ops")
    return path


def run_cli(argv, *, env=None, cwd=None) -> tuple[int, str, str]:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    proc = subprocess.run(
        [sys.executable, str(GRAFT_PY), *list(argv)],
        cwd=cwd,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def call_public(test, name, *args, **kwargs):
    graft = load_graft()
    test.assertTrue(
        hasattr(graft, name),
        f"{name} is a public seam on ops/devlane/harness/graft.py",
    )
    fn = getattr(graft, name)
    test.assertTrue(callable(fn), f"{name} is callable")
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        test.fail(f"{name}() raised {type(exc).__name__}: {exc}")


def assert_refusal(test, code, out, err, ident, *, phrases=(), named=()):
    test.assertEqual(
        code, REFUSAL_EXIT,
        f"{ident} refuses with exit {REFUSAL_EXIT}, got {code}: {(out or '') + (err or '')!r}",
    )
    test.assertEqual(
        (out or "").strip(), "",
        f"{ident} refusal text belongs on stderr, not stdout: {out!r}",
    )
    lines = [ln for ln in (err or "").splitlines() if ln.strip()]
    test.assertEqual(
        len(lines), 1,
        f"{ident} refusal must be one stderr line: {err!r}",
    )
    line = lines[0]
    lower = line.lower()
    token = ident.lower().replace("_", "-")
    test.assertIn(token, lower, f"{ident} class token missing: {line!r}")
    for word in ("expected", "found", "needed"):
        test.assertIn(word, lower, f"{ident} names {word}: {line!r}")
    test.assertLess(lower.index("expected"), lower.index("found"), line)
    test.assertLess(lower.index("found"), lower.index("needed"), line)
    test.assertRegex(
        line,
        rf"{re.escape(token)}:\s*expected",
        f"{ident}: expected is the refusal class token: {line!r}",
    )
    for item in named:
        test.assertIn(str(item), line, f"{ident} names {item!r}: {line!r}")
    for phrase in phrases:
        test.assertIn(
            phrase.lower(), lower,
            f"{ident} names {phrase!r}: {line!r}",
        )
    return line


class GraftCase:
    """Temp HOME, scratch lane conf, optional fake install and ops root."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = Path(self._td.name)
        self._saved = {
            k: os.environ.get(k)
            for k in (
                "HOME", "WF_AGENT", "LANE_CONF", "GRAFT_INSTALL",
                "XDG_STATE_HOME", "PATH",
            )
        }
        os.environ["HOME"] = str(self.home)
        os.environ["XDG_STATE_HOME"] = str(self.home / "state")
        os.environ["WF_AGENT"] = AGENT
        self.conf = write_conf(self.home / "lane.conf")
        os.environ["LANE_CONF"] = str(self.conf)
        os.environ["GRAFT_INSTALL"] = ""
        self.fake = load_fake()
        self.pin = load_pin()
        install_spawn_observer(self.home)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._td.cleanup()

    def set_install(self, value: str) -> None:
        os.environ["GRAFT_INSTALL"] = value
        write_conf(self.conf, GRAFT_INSTALL=value)

    def plant_fake_install(self, *, mode: str = "ok") -> Path:
        dest = self.home / "graft-install"
        self.fake.plant_install(dest, pin=self.pin, mode=mode)
        self.set_install(str(dest))
        return dest

    def plant_root(self, files=None) -> Path:
        return plant_ops_root(self.home / "src", files)

    def cli(self, argv, *, identity=True):
        env = dict(os.environ)
        env.update(observer_env(self.home))
        if not identity:
            env.pop("WF_AGENT", None)
        return run_cli(argv, env=env, cwd=self.home)

    def drain_spawns(self) -> list[dict]:
        return drain_spawns(self.home)

    def read_spawns(self) -> list[dict]:
        return read_spawns(self.home)
