#!/usr/bin/env python3
"""matrix.py -- the check matrix: a PreToolUse hook on Bash and the write tools.

Owner, 2026-09-04: "you need to force yourself - fuck promises - it has to
PAINFUL for you to fuck up" and "i need matrix of checks in a pre-tool call
or something - you have to be forced".

Every row is a killer from the day's ranking made mechanical.  A row is
computed from the command text, the files it names and the tree, never
from what the session believes.  A refusal is the wire, one line,
``class: expected ...; found ...; needed ...``, sent through the deny
channel the pre-check next door uses.  A hook that cannot read its payload
lets the call through (a hook that fails takes the session with it).  A
row that cannot look refuses: "could not look" is not a pass.

    class           trigger                                       computed from
    hand-write      a write to a path under a code root           statement, repo root
    direct-launch   launch.py run without the dispatcher          command word
    override        --model or --effort on a dispatcher call      tokens
    input-absent    a --scope-file or --input missing or empty    the files
    scope-cap       --scope-file over SCOPE_CAP                   size, lane conf
    bucket-command  an implement scope naming the whole suite     scope text
    walkthrough     a write job whose inputs carry no walkthrough input text
    stale-base      --worktree behind the trunk                   git merge-base
    contract-vet    harness contracts do not vet as a package     cue vet
    dispatch-env    a launch without LAUNCHER_PIN in the          command or run-script
                    worktree, DISPATCH_TIMEOUT and WF_AGENT       text
    dispatch-by-hand a driver-owned job run from the session      job name
    test-form       unittest invoked with a path argument          tokens
    prune           rm -r of records, state, worktrees, .git      statement

The only escape is a declared, open grant: ``HAND_GRANT=<id>`` leading the
command, the id an open row of the hand ledger whose scope covers the
path -- and only for hand-write and direct-launch.  The other rows have no
escape: a launch that would refuse at mint refuses here, before the mint.
"""

import json
import os
import re
import shlex
import sqlite3
import string
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from command_shape import commands

CODE_ROOTS = (
    "ops/", ".github/", ".claude/", "docs/", "packages/", "src/", "config/",
    "bin/", "tests/", "templates/", "composer.json", "composer.lock",
    "AGENTS.md", "CLAUDE.md", "CONTRIB.md", "README.md", "pyproject.toml",
    "ruff.toml", "phpunit.dist.xml", "phpunit.xml",
)
# Session records live under ops/ but are not code: the freeze is about code.
RECORD_PREFIXES = (
    "ops/conductor/ideas/", "ops/conductor/handoff/", "ops/conductor/AAR-",
    "ops/conductor/probes/",
)
WRITE_JOBS = ("author-tests", "implement")
DISPATCHERS = ("dispatch.sh", "go.sh")
DRIVER_JOBS = ("author-tests", "check-tests", "implement", "security-audit", "adversarial-review")
ALLOWED_BY_HAND = {
    "plan": "the ladder has no plan verb",
    "adjudicate": "the ladder has no adjudicate verb",
    "sweep": "the ladder has no sweep verb",
    "verify": "the ladder has no verify verb",
}
LAUNCHER = "launch.py"
DRIVER = "ladder.sh"
SCOPE_CAP_DEFAULT = 1024
TRUNK_DEFAULT = "dev"
LANE_DEFAULT = "agentscient"
COPY_WORDS = ("cp", "mv", "install", "rsync", "ln")
GRANT = re.compile(r"^\s*(?:export\s+)?HAND_GRANT=(\d+)\b")
WHOLE_SUITE = re.compile(r"suites\.sh|unittest\s+discover(?![^\n]*\s-p\s)")
WALK_HEADING = re.compile(r"^#{1,6}\s+first-run walkthrough\b", re.IGNORECASE | re.MULTILINE)
WALK_LINE = re.compile(r"^\s*[-*]\s*assumption\b.*\b(measured|refusal)\b", re.IGNORECASE | re.MULTILINE)
PY_WRITE = re.compile(r"open\([^)]*['\"][wa]['\"]|write_text\(|write_bytes\(|\.writelines\(")
PY_PATH = re.compile(r"(?P<quote>['\"])(?P<path>[^'\"\s]+)(?P=quote)")
ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(\S+)", re.MULTILINE)
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PRUNE_TARGETS = (".dev/records", ".git", "ops/conductor/ideas")
STATE_DIR = os.path.expanduser("~/.local/state")


def deny(klass, expected, found, needed):
    line = f"{klass}: expected {expected}; found {found}; needed {needed}"
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"[matrix:{klass}] {line}",
    }}


# --- the tree ---------------------------------------------------------------

def repo_root(path):
    """The repository (or worktree) root holding ``path``, or None."""
    probe = os.path.abspath(path)
    if not os.path.isdir(probe):
        probe = os.path.dirname(probe)
    while True:
        if os.path.exists(os.path.join(probe, ".git")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return None
        probe = parent


def relative(path, cwd):
    """(root, path relative to root) for a command path, or (None, None)."""
    absolute = os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))
    root = repo_root(absolute)
    if root is None:
        return None, None
    return root, os.path.relpath(absolute, root)


def is_code(rel):
    if rel is None or rel.startswith(".."):
        return False
    if rel.startswith(RECORD_PREFIXES):
        return False
    return rel.startswith(CODE_ROOTS) or rel in CODE_ROOTS


def lane_conf(root):
    """The lane conf as a dict; missing keys are the caller's defaults."""
    conf = {}
    path = os.path.join(root or "", "ops", "lane.conf")
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                conf[key.strip()] = value.strip().strip("'\"")
    except OSError:
        pass
    return conf


# --- the grant --------------------------------------------------------------

def open_grant(text, lane):
    """(id, scope) of the open grant the command leads with, else None."""
    match = GRANT.match(text)
    if not match:
        return None
    grant_id = int(match.group(1))
    db = os.path.join(STATE_DIR, lane, "handwork.db")
    try:
        connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        row = connection.execute(
            "SELECT status, scope FROM handwork WHERE id = ?", (grant_id,)
        ).fetchone()
        connection.close()
    except sqlite3.Error:
        return None
    if row is None or row[0] != "open":
        return None
    return grant_id, (row[1] or "")


def grant_covers(grant, rel):
    """A grant with a scope covers only the paths its scope names."""
    if grant is None:
        return False
    scope = [token for token in grant[1].split() if "/" in token or "." in token]
    if not scope:
        return True
    return any(rel == token or rel.startswith(token.rstrip("/") + "/") for token in scope)


# --- statements -------------------------------------------------------------

def tokens_of(statement):
    """Tokens of one command, leading NAME=value assignments peeled."""
    try:
        toks = shlex.split(statement, posix=True)
    except ValueError:
        toks = statement.split()
    while toks and ENV_ASSIGN.match(toks[0]):
        toks = toks[1:]
    if toks and toks[0] == "export":
        return []
    return toks


def base(word):
    return word.rsplit("/", 1)[-1]


def redirect_targets(tokens):
    """stdout redirection targets, whether `> f`, `>f` or `>> f`."""
    targets = []
    pending = False
    for token in tokens:
        if pending:
            targets.append(token)
            pending = False
            continue
        if token in (">", ">>", "1>", "1>>"):
            pending = True
        elif token.startswith((">", "1>")) and not token.startswith(">&"):
            targets.append(token.lstrip("1").lstrip(">"))
    return [t for t in targets if t and not t.startswith(("&", "/dev/"))]


def written_paths(tokens):
    """Paths a statement writes by its own shape (not by redirection)."""
    if not tokens:
        return []
    word = base(tokens[0])
    rest = tokens[1:]
    if word in ("sudo", "env", "nice", "time"):
        return written_paths(rest)
    if word in ("sed", "perl") and any(t.startswith(("-i", "--in-place", "-pi", "-ni")) for t in rest):
        files, script_taken, expect_script = [], False, False
        for token in rest:
            if expect_script:
                expect_script = False
                script_taken = True
                continue
            if token in ("-e", "--expression", "-f", "--file"):
                expect_script = True
                continue
            if token.startswith("-"):
                if token.startswith(("-e", "--expression=")) and len(token) > 2:
                    script_taken = True
                continue
            if not script_taken:
                script_taken = True
                continue
            files.append(token)
        return files
    if word == "tee":
        return [t for t in rest if not t.startswith("-")]
    if word in COPY_WORDS:
        bare = [t for t in rest if not t.startswith("-")]
        return bare[-1:] if len(bare) >= 2 else []
    if word == "truncate":
        return [t for t in rest if not t.startswith("-") and not t.isdigit()]
    if word == "git":
        sub = [t for t in rest if not t.startswith("-")]
        verb = sub[0] if sub else ""
        if verb in ("checkout", "restore") and "--" in rest:
            return rest[rest.index("--") + 1:]
        if verb == "restore" and "--" not in rest:
            return [t for t in sub[1:] if not t.startswith("-")]
        if verb in ("apply", "am") or (verb == "cherry-pick" and ("-n" in rest or "--no-commit" in rest)):
            return ["."]
    if word == "patch":
        return ["."]
    return []


def prune_targets(tokens, cwd, conf):
    if not tokens or base(tokens[0]) != "rm":
        return []
    flags = [t for t in tokens[1:] if t.startswith("-")]
    if not any("r" in f.lower() for f in flags if not f.startswith("--")) and "--recursive" not in flags:
        return []
    hits = []
    wt_root = os.path.normpath(os.path.join(cwd, conf.get("WORKTREE_ROOT", "../wt")))
    state = os.path.join(STATE_DIR, conf.get("LANE_NAME", LANE_DEFAULT))
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        absolute = os.path.normpath(os.path.join(cwd, os.path.expanduser(token)))
        _, rel = relative(token, cwd)
        if absolute.startswith((wt_root, state)) or (rel is not None and any(
                rel == t or rel.startswith(t + "/") for t in PRUNE_TARGETS)):
            hits.append(token)
    return hits


# --- dispatch rows ----------------------------------------------------------

def dispatch_args(tokens):
    """(kind, flags) when the statement dispatches; kind is dispatcher|launcher|driver|None."""
    kind = None
    name = base(tokens[0]) if tokens else ""
    if name in DISPATCHERS:
        kind = "dispatcher"
    elif name == LAUNCHER:
        kind = "launcher"
    elif name == DRIVER:
        kind = "driver"
    elif (re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", name) and len(tokens) > 1
          and base(tokens[1]) == LAUNCHER):
        kind = "launcher"
    if kind is None:
        return None, {}
    flags = {"input": []}
    it = iter(tokens)
    for flag in it:
        if flag in ("--scope-file", "--worktree", "--job", "--model", "--effort", "--harness", "--stage", "--unit"):
            flags[flag[2:]] = next(it, "")
        elif flag == "--input":
            flags["input"].append(next(it, ""))
        elif flag.startswith("--input="):
            flags["input"].append(flag.split("=", 1)[1])
        elif "=" in flag and flag.startswith("--"):
            key, _, value = flag[2:].partition("=")
            flags[key] = value
    return kind, flags


def expand(script_text, cwd):
    """Expand $VAR / ${VAR} from the script's own assignments, then the environment."""
    mapping = dict(os.environ)
    for match in ASSIGN.finditer(script_text):
        mapping[match.group(1)] = string.Template(match.group(2).strip("'\"")).safe_substitute(mapping)
    return string.Template(script_text).safe_substitute(mapping)


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def unittest_path_argument(tokens):
    """The forbidden path argument in a unittest invocation, if any."""
    if (len(tokens) < 3 or not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", base(tokens[0]))
            or tokens[1:3] != ["-m", "unittest"]):
        return None
    args = tokens[3:]
    if args and args[0] == "discover":
        return None
    takes_value = False
    for arg in args:
        if takes_value:
            takes_value = False
            continue
        if arg in ("-k", "--durations"):
            takes_value = True
            continue
        if arg.startswith("-"):
            continue
        if arg.endswith(".py") or "/" in arg:
            return arg
    return None


def check_dispatch(kind, flags, cwd, text, grant):
    if kind == "launcher":
        if grant is None:
            return deny("direct-launch",
                        "every stage launched through ops/bin/dispatch.sh so the lane conf applies",
                        "launch.py run directly",
                        "dispatch.sh --job ... (or HAND_GRANT=<open id> for a lever hole, declared first)")
        return None
    if kind == "driver":
        return None
    if "model" in flags or "effort" in flags:
        return deny("override", "the conf's model and effort", "--model/--effort on the dispatcher call",
                    "drop them; ops/lane.conf decides")
    worktree = flags.get("worktree", "")
    root = os.path.normpath(os.path.join(cwd, worktree)) if worktree else repo_root(cwd)
    conf = lane_conf(root)
    files = [f for f in [flags.get("scope-file", "")] + flags["input"] if f]
    for path in files:
        absolute = os.path.normpath(os.path.join(cwd, path))
        if "$" in path:
            return deny("input-absent", "a literal input path", f"unresolved {path}", "write the path out in the run script")
        contents = read_text(absolute)
        if contents is None or not contents:
            return deny("input-absent", "a readable non-empty input", f"{path} missing or empty", "write it before dispatch")
        if "$" in contents:
            return deny("input-absent", "resolved input content", f"unresolved $ in {path}",
                        "write the resolved content before dispatch")
    scope_file = flags.get("scope-file", "")
    cap = int(conf.get("SCOPE_CAP", SCOPE_CAP_DEFAULT))
    if scope_file:
        size = os.path.getsize(os.path.normpath(os.path.join(cwd, scope_file)))
        if size > cap:
            return deny("scope-cap", f"<= {cap} bytes", f"{size} bytes in {scope_file}",
                        "cut the scope before dispatch, not after the mint")
    job = flags.get("job", "")
    scope_text = read_text(os.path.normpath(os.path.join(cwd, scope_file))) or "" if scope_file else ""
    if job == "implement":
        hit = WHOLE_SUITE.search(scope_text)
        path_arg = next((arg for statement in commands(scope_text)
                         if (arg := unittest_path_argument(tokens_of(statement)))), None)
        if hit or path_arg:
            found = hit.group(0) if hit else path_arg
            return deny("bucket-command", "the bucket's tests as the named command",
                        f'"{found}" in {scope_file}',
                        "name the bucket's test files; the whole suite is not a bucket (ranking K2)")
    if job in WRITE_JOBS:
        inputs_text = "\n".join(read_text(os.path.normpath(os.path.join(cwd, p))) or "" for p in flags["input"])
        if not (WALK_HEADING.search(inputs_text) and WALK_LINE.search(inputs_text)):
            return deny("walkthrough",
                        'a "First-run walkthrough" section whose assumption lines are each measured or a refusal',
                        f"none in {' '.join(flags['input']) or 'no --input'}",
                        "walk the first run against the isolated home, no network, the read-only .git, "
                        "the job prompt and the runner workspace before dispatch (planning rule)")
    if worktree:
        trunk = conf.get("TRUNK_BRANCH", TRUNK_DEFAULT)
        probe = subprocess.run(["git", "-C", root, "merge-base", "--is-ancestor", f"origin/{trunk}", "HEAD"],  # noqa: S603, S607 - PATH git; root is a path this hook resolved
                               capture_output=True, text=True, check=False)
        if probe.returncode == 1:
            behind = subprocess.run(["git", "-C", root, "rev-list", "--count", f"HEAD..origin/{trunk}"],  # noqa: S603, S607 - PATH git; range is a branch name from the conf
                                    capture_output=True, text=True, check=False).stdout.strip() or "?"
            return deny("stale-base", f"{worktree} to contain origin/{trunk} as fetched",
                        f"HEAD behind by {behind} commits", f"git merge origin/{trunk} in the worktree before dispatch")
        if probe.returncode > 1:
            return deny("stale-base", f"a git answer from {worktree}", probe.stderr.strip().splitlines()[-1:] or "no answer",
                        "a worktree the hook can read")
        harness_dir = os.path.join(root, "ops", "devlane", "harness")
        if os.path.isdir(harness_dir):
            try:
                vet = subprocess.run(["cue", "vet", "./ops/devlane/harness/"], cwd=root,  # noqa: S607 - PATH cue; a fixed argv
                                     capture_output=True, text=True, timeout=60, check=False)
            except FileNotFoundError:
                return deny("contract-vet", "cue on PATH to vet the harness contracts", "no cue",
                            "install cue; could not look is not a pass")
            except subprocess.TimeoutExpired:
                return deny("contract-vet", "cue vet within 60 s", "timeout", "a vettable contract package")
            if vet.returncode != 0:
                first = (vet.stderr.strip().splitlines() or ["no output"])[0]
                return deny("contract-vet", "ops/devlane/harness to vet clean as a package", first,
                            "fix the contract through the ladder before any dispatch")
        pin = re.search(r"LAUNCHER_PIN=(\S+)", text)
        if not pin or not pin.group(1).strip("'\"").startswith(root):
            return deny("dispatch-env", f"LAUNCHER_PIN={root}/ops/devlane/dispatch/launch.py (the branch's own launcher)",
                        pin.group(1) if pin else "no LAUNCHER_PIN", "export it in the run script")
        for name in ("DISPATCH_TIMEOUT", "WF_AGENT"):
            if f"{name}=" not in text:
                return deny("dispatch-env", f"{name} set for the launch", f"no {name}", "export it in the run script")
    if (job in DRIVER_JOBS or job.endswith("-fix")) and not grant_covers(grant, ""):
        return deny("dispatch-by-hand", f"the ladder driver to run {job} (ops/bin/ladder.sh)",
                    f"dispatch.sh --job {job} from the session",
                    "start or resume a ladder for the lane")
    return None


# --- the decision -----------------------------------------------------------

def check_text(text, cwd, depth=0):
    root = repo_root(cwd)
    conf = lane_conf(root)
    lane = conf.get("LANE_NAME", LANE_DEFAULT)
    grant = open_grant(text, lane)
    if PY_WRITE.search(text):
        for match in PY_PATH.finditer(text):
            _, rel = relative(match.group("path"), cwd)
            if is_code(rel) and not grant_covers(grant, rel):
                return deny("hand-write", "code changed through the ladder (freeze)",
                            f"a script writing {match.group('path')}", "the ladder, or HAND_GRANT=<open id> whose scope names the path")
    for statement in commands(text):
        toks = tokens_of(statement)
        if not toks:
            continue
        for target in prune_targets(toks, cwd, conf):
            return deny("prune", "data kept (never prune)", f"rm -r {target}", "leave it; move it under .dev/tmp with a note if it is in the way")
        for target in redirect_targets(toks) + written_paths(toks):
            if target == ".":
                if grant is None:
                    return deny("hand-write", "code changed through the ladder (freeze)",
                                f"{base(toks[0])} applying a patch by hand in {root or cwd}",
                                "the landing lever (land.py), or HAND_GRANT=<open id> declared first")
                continue
            _, rel = relative(target, cwd)
            if is_code(rel) and not grant_covers(grant, rel):
                return deny("hand-write", "code changed through the ladder (freeze)", f"{base(toks[0])} writing {target}",
                            "the ladder, or HAND_GRANT=<open id> whose scope names the path (grants are for landing and merge resolution)")
        kind, flags = dispatch_args(toks)
        if kind:
            refusal = check_dispatch(kind, flags, cwd, text, grant)
            if refusal:
                return refusal
        path_arg = unittest_path_argument(toks)
        if path_arg:
            return deny("test-form",
                        "the discover form (python3 -m unittest discover -s <tests dir> -p <file>) or ops/bin/suites.sh",
                        f"a path-form unittest argument {path_arg}", "the discover form")
        if depth == 0 and base(toks[0]) in ("bash", "sh", "source", ".") and len(toks) > 1:
            if toks[1] == "-c" and len(toks) > 2:
                refusal = check_text(toks[2], cwd, depth + 1)
                if refusal:
                    return refusal
            else:
                script = os.path.normpath(os.path.join(cwd, os.path.expanduser(toks[1])))
                _, rel = relative(script, cwd)
                if os.path.isfile(script) and not is_code(rel):
                    body = read_text(script)
                    if body is not None:
                        refusal = check_text(expand(body, cwd), cwd, depth + 1)
                        if refusal:
                            return refusal
    return None


def decide(payload):
    if not isinstance(payload, dict):
        return None
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()
    if tool == "Bash":
        command = tool_input.get("command", "")
        return check_text(command, cwd) if command else None
    path = tool_input.get("file_path") or tool_input.get("relative_path") or ""
    if path:
        _, rel = relative(path, cwd)
        if is_code(rel):
            return deny("hand-write", "code changed through the ladder (freeze)", f"{tool} on {path}",
                        "the ladder; a granted hand change goes through Bash with HAND_GRANT=<open id> leading the command")
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    try:
        refusal = decide(payload)
    except Exception as error:  # noqa: BLE001 - a hook that dies takes the session with it
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"[matrix:hook-error] hook-error: expected a decision; found {type(error).__name__}: {error}; needed the hook fixed through the ladder",
        }}))
        return 0
    if refusal:
        print(json.dumps(refusal))
    return 0


if __name__ == "__main__":
    sys.exit(main())
