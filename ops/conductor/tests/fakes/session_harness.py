# testkit: exempt fixture program planted as the native harness
"""Fake native harness for managed-sessions slice 1.

The kit plants this file through Tools.plant(..., script=...). The spec
beside the registry (fakes/<name>.spec.json) says which session id to
bind: null or absent uses the launch id from --session-id; a string is
that native id (the native-mismatch variant); empty skips the bind (the
timeout-with-no-bind variant). It runs the profile's guard.sh
SessionStart and then holds until the supervisor stops it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def spec_path() -> Path | None:
    named = os.environ.get("TESTKIT_FAKE_SPEC", "")
    if named:
        path = Path(named)
        if path.is_file():
            return path
    exe = Path(sys.argv[0]).resolve()
    candidate = exe.parent.parent / "fakes" / f"{exe.name}.spec.json"
    return candidate if candidate.is_file() else None


def load_spec() -> dict:
    path = spec_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def log_call(spec: Path | None, argv: list[str]) -> None:
    if spec is None:
        return
    log = spec.with_name(spec.name.replace(".spec.json", ".calls.jsonl"))
    line = json.dumps({"pid": os.getpid(), "argv": argv, "cwd": os.getcwd()}) + "\n"
    fd = os.open(str(log), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def flag(argv: list[str], name: str) -> str | None:
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    prefix = name + "="
    for item in argv:
        if item.startswith(prefix):
            return item[len(prefix):]
    return None


def profile_dir(argv: list[str]) -> Path | None:
    settings = flag(argv, "--settings")
    if settings:
        return Path(settings).resolve().parent
    binding = os.environ.get("AGENTSCIENT_HOOK_PROFILE", "")
    if binding:
        return Path(binding).resolve().parent
    return None


def native_id(argv: list[str], spec: dict) -> str | None:
    if "session_id" in spec:
        value = spec["session_id"]
        if value is None:
            return flag(argv, "--session-id")
        return str(value)
    return flag(argv, "--session-id")


def kit_run():
    """ops.testkit.run, after the plant substitutes the repository root.

    origin: 20260922T215604Z-review-codex-f6777b#20
    """
    repo = "@@REPO@@"
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from ops.testkit import run
    return run


def run_session_start(profile: Path, bind_id: str) -> int:
    guard = profile / "guard.sh"
    if not guard.is_file() or not bind_id:
        return 0
    payload = json.dumps({
        "session_id": bind_id,
        "hook_event_name": "SessionStart",
        "source": "startup",
        "cwd": os.getcwd(),
    })
    env = os.environ.copy()
    env.pop("COORDINATION_CAPABILITY", None)
    result = kit_run()(
        [str(guard), "SessionStart"],
        cwd=os.getcwd(),
        env=env,
        stdin=payload,
        timeout=30,
    )
    if result.exit != 0:
        sys.stderr.write(result.stderr or result.stdout)
        return result.exit
    return 0


def hold() -> None:
    try:
        stream = sys.stdin
        if stream is not None and not stream.closed and not stream.isatty():
            stream.read()
    except (OSError, ValueError):
        pass
    while True:
        time.sleep(3600)


def main() -> int:
    argv = sys.argv[1:]
    spec_file = spec_path()
    log_call(spec_file, argv)
    spec = load_spec()
    bind_id = native_id(argv, spec)
    profile = profile_dir(argv)
    if profile is not None and bind_id:
        code = run_session_start(profile, bind_id)
        if code:
            return code
    hold()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
