#!/usr/bin/env python3
"""Read and check the lane's shared, literal-only configuration."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_CONF = Path(__file__).resolve().parents[2] / "lane.conf"
LOCAL_NAME = "lane.local.conf"
NAME_KEYS = {
    "LANE_NAME",
    "TRUNK_BRANCH",
    "RELEASE_BRANCH",
    "REPO_SLUG",
    "CHECK_NAME",
}
REQUIRED_KEYS = {
    "LANE_NAME",
    "TRUNK_BRANCH",
    "RELEASE_BRANCH",
    "REPO_SLUG",
    "CHECK_NAME",
    "WF_AGENT_DEFAULT",
    "LANE_AUTHOR",
    "MODEL_GROK",
    "MODEL_CODEX",
    "MODEL_CLAUDE_READ",
    "MODEL_CLAUDE_PLAN",
    "EFFORT_GROK",
    "EFFORT_CODEX",
    "EFFORT_CLAUDE",
    "WALL_DEFAULT",
    "SCOPE_CAP",
}
DECLARATION = re.compile(r"^([A-Z][A-Z0-9_]*)='([^']*)'\s*$")
SOURCE_SUFFIXES = {".py", ".sh"}
EXTERNAL_ENV_KEYS = {
    "AGENTSCIENT_ORG",
    "AGENTSCIENT_ROOT",
    "AGENTSCIENT_SIBLINGS",
    "BASH_SOURCE",
    "BASH_REMATCH",
    "CLAUDE_PRECHECK_NO_FETCH",
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_SESSION_ID",
    "CODEX_HOME",
    "DETACH",
    "DETACH_WAIT",
    "DISPATCH_CONF",
    "DISPATCH_JOBS",
    "DISPATCH_STREAM_GRACE",
    "DISPATCH_TICK",
    "DISPATCH_TIMEOUT",
    "EFFORT",
    "EVGREP_LIMIT",
    "GATE_LOG_DIR",
    "GATE_TAIL",
    "GITHUB_EVENT_PATH",
    "GROK_HOME",
    "HARNESS",
    "HOME",
    "ISO_ENV",
    "ISO_ENV_CODEX_HOME",
    "ISO_FLAGS",
    "ISO_STORE",
    "LANE_CONF",
    "LAUNCHER_PIN",
    "PATH",
    "REPO",
    "REPOS",
    "SIBLINGS",
    "SUITES_SERIAL",
    "TERM_WALL",
    "THREADS_OUT",
    "TMPDIR",
    "WATCH_TICK_SCALE",
    "WF_AGENT",
    "XDG_STATE_HOME",
}

# Unit 1A deliberately leaves the other consumers for run B. Naming the
# temporary exclusions makes that incomplete frontier visible and prevents a
# blanket directory exemption from hiding new spread.
DEFERRED_LITERAL_PATHS = {
    ".claude/skills/pr-overview/pr_overview.py",
    "ops/bin/board.sh",
    "ops/bin/link-ops.sh",
    "ops/conductor/tools/branches.py",
    "ops/conductor/tools/ci.py",
    "ops/conductor/tools/co_doc.py",
    "ops/conductor/tools/decisions.py",
    "ops/conductor/tools/findings.py",
    "ops/conductor/tools/gate.sh",
    "ops/conductor/tools/hand.py",
    "ops/conductor/tools/land.py",
    "ops/conductor/tools/onboard.py",
    "ops/conductor/tools/skills.py",
    "ops/devlane/dispatch/levers/codex/codex-dispatch.sh",
    "ops/devlane/dispatch/levers/grok-dispatch.sh",
    "ops/devlane/hooks/claude/context-stream.sh",
    "ops/devlane/hooks/claude/unsafe-command.py",
    "ops/devlane/telemetry/worth.py",
    "ops/devlane/workflow/checks/commit_trailers.py",
}


class ConfigError(Exception):
    """A refusal that can be projected onto either CLI wire."""

    def __init__(
        self,
        kind: str,
        expected: str,
        found: str,
        needed: str,
    ) -> None:
        self.kind = kind
        self.expected = expected
        self.found = found
        self.needed = needed
        super().__init__(self.line())

    def line(self, kind: str | None = None) -> str:
        return (
            f"{kind or self.kind}: expected {self.expected}; "
            f"found {self.found}; needed {self.needed}"
        )


def conf_path() -> Path:
    """Return the explicit conf or the tracked file beside the lane."""
    return Path(os.environ.get("LANE_CONF", DEFAULT_CONF)).resolve()


def parse_file(path: Path) -> dict[str, str]:
    """Parse comments, blank lines, and literal single-quoted assignments."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(
            "conf-file",
            f"a readable lane conf at {path}",
            str(exc),
            "restore the file or set LANE_CONF",
        ) from exc
    values: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = DECLARATION.fullmatch(line)
        if match is None:
            raise ConfigError(
                "syntax",
                "a KEY='literal' assignment or comment",
                f"line {number} in {path}",
                "replace the line with a literal single-quoted assignment",
            )
        values[match.group(1)] = match.group(2)
    return values


def values() -> dict[str, str]:
    """Resolve environment, local file, then tracked-file precedence."""
    path = conf_path()
    resolved = parse_file(path)
    local = path.with_name(LOCAL_NAME)
    if local.is_file():
        overrides = parse_file(local)
        forbidden = sorted(NAME_KEYS.intersection(overrides))
        if forbidden:
            key = forbidden[0]
            raise ConfigError(
                "local-key",
                "lane identity keys only in the tracked conf",
                f"{key} in {local}",
                f"remove {key} from {local}",
            )
        resolved.update(overrides)
    for key in tuple(resolved):
        if key in os.environ:
            resolved[key] = os.environ[key]
    return resolved


def get(name: str) -> str:
    """Read one key, refusing rather than inventing a missing value."""
    resolved = values()
    if name in os.environ:
        return os.environ[name]
    if name not in resolved:
        path = conf_path()
        raise ConfigError(
            "key",
            f"{name} declared in the lane conf",
            f"no {name} in {path}",
            f"define {name} in {path}",
        )
    return resolved[name]


def _repo_root(path: Path) -> Path:
    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git", "-C", str(path.parent), "rev-parse", "--show-toplevel"
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        detail = proc.stderr.strip() or f"git exited {proc.returncode}"
        raise ConfigError(
            "repo",
            f"{path} inside a git worktree",
            detail,
            "run the check against a lane checkout",
        )
    return Path(proc.stdout.strip()).resolve()


def _source_files(root: Path):
    for top in (root / "ops", root / ".claude"):
        if not top.is_dir():
            continue
        for path in sorted(top.rglob("*")):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            rel = path.relative_to(root)
            if any(part in {"tests", "fixtures", "archive", "infra"} for part in rel.parts):
                continue
            yield rel, path


def _reads(text: str) -> set[str]:
    patterns = (
        r"\bget\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]",
        r"\bos\.environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]",
        r"\bos\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]",
        r"\$\{([A-Z][A-Z0-9_]*)",
    )
    return {
        match.group(1)
        for pattern in patterns
        for match in re.finditer(pattern, text)
    }


def closure() -> int:
    """Check declarations, readers, and the required workflow name."""
    path = conf_path()
    declared = parse_file(path)
    root = _repo_root(path)
    readers: dict[str, set[str]] = {}
    laneconf_in_tree = root / "ops/conductor/tools/laneconf.py"
    if laneconf_in_tree.is_file():
        for key in REQUIRED_KEYS:
            readers.setdefault(key, set()).add(
                "ops/conductor/tools/laneconf.py"
            )
    for rel, source in _source_files(root):
        text = source.read_text(encoding="utf-8", errors="replace")
        for key in _reads(text):
            readers.setdefault(key, set()).add(rel.as_posix())
    dispatch = root / "ops/conductor/tools/dispatch.sh"
    if dispatch.is_file() and "model_job" in dispatch.read_text(
        encoding="utf-8", errors="replace"
    ):
        for key in declared:
            if key.startswith(("MODEL_", "EFFORT_")):
                readers.setdefault(key, set()).add(dispatch.relative_to(root).as_posix())

    findings: list[str] = []
    for key in sorted(set(declared).difference(readers)):
        findings.append(f"unread declaration: {key} in {path}")
    for key in sorted(set(readers).difference(declared, EXTERNAL_ENV_KEYS)):
        locations = ", ".join(sorted(readers[key]))
        findings.append(f"undeclared read: {key} in {locations}")

    workflow = root / ".github/workflows/ci.yml"
    if workflow.is_file() and "CHECK_NAME" in declared:
        match = re.search(
            r"(?m)^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$",
            workflow.read_text(encoding="utf-8", errors="replace"),
        )
        if match and match.group(1) != declared["CHECK_NAME"]:
            findings.append(
                "workflow name mismatch: "
                f"CHECK_NAME={declared['CHECK_NAME']} but "
                f"{workflow.relative_to(root)} names {match.group(1)}"
            )
    if findings:
        print("\n".join(findings))
        return 1
    return 0


def _literal_exempt(rel: str, line: str, needle: str) -> bool:
    stripped = line.strip()
    if rel == "ops/devlane/dispatch/record.py" and needle == '"dev"':
        return stripped in {
            'lane = "dev"',
            'source["lane"] = "dev"',
            '_need(rec["lane"] == "dev", "lane", "must be dev")',
        }
    if rel == "ops/devlane/dispatch/launch.py" and needle == '"dev"':
        return '"WF_LANE": "dev"' in line or '"lane": "dev"' in line
    return False


def literals() -> int:
    """Find project and branch literals that escaped the shared conf."""
    path = conf_path()
    configured = parse_file(path)
    root = _repo_root(path)
    tokens = {'"dev"', "origin/dev", "'agentscient'", "uscient/agentscient", "/home/work/"}
    for key in NAME_KEYS:
        value = configured.get(key, "")
        if len(value) >= 4:
            tokens.add(value)

    findings: list[str] = []
    for rel_path, source in _source_files(root):
        rel = rel_path.as_posix()
        if rel in DEFERRED_LITERAL_PATHS or source.resolve() == Path(__file__).resolve():
            continue
        for number, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(),
            1,
        ):
            for token in sorted(tokens, key=lambda value: (-len(value), value)):
                if token in line and not _literal_exempt(rel, line, token):
                    findings.append(f"{rel}:{number}: forbidden literal {token}")
    print("skipped: ops/devlane/infra")
    if findings:
        print("\n".join(findings))
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) == 2 and args[0] == "get":
            print(get(args[1]))
            return 0
        if args == ["closure"]:
            return closure()
        if args == ["literals"]:
            return literals()
        raise ConfigError(
            "arguments",
            "get KEY, closure, or literals",
            " ".join(args) or "no arguments",
            "choose one documented verb",
        )
    except ConfigError as exc:
        print(exc.line(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
