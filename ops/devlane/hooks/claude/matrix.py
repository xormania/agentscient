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
    stale-base      --worktree whose merge-forward from the       git merge-tree
                    trunk would conflict (behind alone is merged
                    by the dispatcher before the launch)
    contract-vet    harness contracts do not vet as a package     cue vet
    dispatch-env    a launch without LAUNCHER_PIN in the          command or run-script
                    worktree, DISPATCH_TIMEOUT and WF_AGENT       text
    dispatch-by-hand a driver job sent straight to dispatch.sh    job, command word
    test-form       unittest given a path instead of discovery    tokens
    prune           rm -r of records, state, worktrees, .git      statement
    graft-first     a grep/rg/git grep search over a code root    statement, targets
                    (counts, file lists, pipes and records paths
                    are not searches); no grant escape; every
                    refusal and every Graft query is logged
    deliverable     while the lane's deliverable lock names       lock file, statement
                    branches, a new worktree or branch, a
                    dispatch, a ladder start or a PR creation
                    aimed at any other branch; no grant escape
    claim-unmeasured a commit message, PR body or comment, or a   the text, paragraph by
                    record or law page written by heredoc, with  paragraph
                    a paragraph that claims (enforced, done,
                    landed, merged, green, impossible, verified,
                    fixed) and carries no reading (sha, record
                    id, P- row, #PR, run id, "Ran N tests") nor
                    the words not measured; quoted words are not
                    the writer's claim; no grant escape (owner,
                    2026-09-12: "stops you from lie-ing")
    trunk-commit    git commit, merge, cherry-pick, rebase,       git symbolic-ref of the
                    revert or am while the directory is on the   directory; push refspecs
                    trunk or the release branch, or a push whose
                    refspec targets them; no grant escape (owner,
                    2026-09-12: "one branch per session")
    pr-proof        gh pr ready / gh pr merge without proof the   gh pr view, the corpus
                    system verifies: a ## Proof section naming   at the head, gh run list
                    corpus rows that exist at the PR head, the
                    head fetched here, a completed green ci run
                    on that head; no grant escape (owner,
                    2026-09-12: "proof needs to be part of the
                    system - it has to generated and verified
                    at boundaries")

Every refusal is also logged as a miss against the skill it names
(``miss.py``: the deliverable row names ``deliverable``, every other row
``refused``), best effort, after the refusal is printed.

The only escape is a declared, open grant: ``HAND_GRANT=<id>`` leading the
command, the id an open row of the hand ledger whose scope covers the
path -- and only for hand-write and direct-launch.  An unscoped open grant
also permits dispatch-by-hand.  The other rows have no escape: a launch that
would refuse at mint refuses here, before the mint.
"""

import ast
import json
import os
import re
import shlex
import sqlite3
import string
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import miss
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
ALLOWED_BY_HAND = {
    "plan": "planning is a session-owned read job",
    "adjudicate": "adjudication is a session-owned decision job",
    "sweep": "sweeping is a session-owned read job",
    "verify": "verification is a session-owned read job",
}
DISPATCHERS = ("dispatch.sh", "go.sh")
# graft-first (owner, 2026-09-11: "go - force it"): the conductor navigated
# code with greps all day and called Graft zero times. A content search over
# a code root refuses with the Graft query as the remedy. Counts (-c), file
# lists (-l/-L), a grep reading a pipe, and records paths are not searches.
SEARCHERS = ("grep", "egrep", "fgrep", "rg", "ugrep", "evgrep.sh")
SEARCH_COUNT_FLAGS = {"-c", "--count", "-l", "--files-with-matches", "-L", "--files-without-match"}
GRAFT_LEVER = "ops/devlane/harness/graft.py"
GRAFT_LOG = "graft-first.log"
LAUNCHER = "launch.py"
DRIVER = "ladder.sh"
# Launcher verbs that launch nothing: they read a record the dispatcher
# already minted. ops/README.md documents the wait verb; the lane conf the
# direct-launch row protects is applied at the mint, not at a read.
LAUNCHER_READ_VERBS = ("status", "wait", "brief", "help")
SCOPE_CAP_DEFAULT = 1024
COPY_WORDS = ("cp", "mv", "install", "rsync", "ln")
# Triage 2026-09-11: the grant may follow other leading assignments
# (`export WF_AGENT='Name <a@b>' HAND_GRANT=12 && ...`); quoted values may
# carry spaces.
GRANT = re.compile(
    r"^\s*(?:export\s+)?(?:\w+=(?:'[^']*'|\"[^\"]*\"|\S*)\s+)*HAND_GRANT=(\d+)\b"
)
WHOLE_SUITE = re.compile(r"suites\.sh|unittest\s+discover(?![^\n]*\s-p\s)")
WALK_HEADING = re.compile(r"^#{1,6}\s+first-run walkthrough\b", re.IGNORECASE | re.MULTILINE)
WALK_LINE = re.compile(r"^\s*[-*]\s*assumption\b.*\b(measured|refusal)\b", re.IGNORECASE | re.MULTILINE)
ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(\S+)", re.MULTILINE)
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
ENV_LONG_OPTIONS = {
    "ignore-environment": "none", "null": "none", "debug": "none",
    "unset": "required", "chdir": "required", "split-string": "required",
    "block-signal": "optional", "default-signal": "optional",
    "ignore-signal": "optional", "list-signal-handling": "none",
    "help": "terminal", "version": "terminal",
}
HEREDOC_OPEN = re.compile(
    r"(?:(?<![\w])(\d+))?(<<-?)[ \t]*(['\"]?)([A-Za-z_]\w*)\3"
)
HEREDOC_TOKEN = re.compile(r"^(?:(\d+))?<<-?(.*)$")
PRUNE_TARGETS = (".dev/records", ".git", "ops/conductor/ideas")
STATE_DIR = os.path.expanduser("~/.local/state")


BOUNDARIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "boundaries.json")


def declared_boundaries():
    """The registry every row of this matrix is declared in (owner,
    2026-09-12: "a framework for verification"). One row per refusal
    class: boundary, actor, trigger, evidence duty, gate, tests, escape.
    A class not declared here cannot be refused with: deny() raises, and
    the hook reports hook-error, so an undeclared gate is itself a
    finding, never a silent rule."""
    with open(BOUNDARIES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return {row["class"]: row for row in data["rows"]}


def deny(klass, expected, found, needed):
    if klass not in declared_boundaries():
        raise RuntimeError(f"undeclared gate: {klass} has no row in ops/devlane/hooks/boundaries.json")
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


def is_python(word):
    return bool(re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", base(word)))


def unique_long_option(argument, vocabulary):
    """A GNU long option's unique full name and whether it carries ``=VALUE``."""
    name, equals, _value = argument[2:].partition("=")
    matches = [option for option in vocabulary if option.startswith(name)]
    if len(matches) != 1:
        return None
    return matches[0], bool(equals)


def env_operand(tokens, program):
    """The command operand after bounded GNU env options, or None."""
    if program >= len(tokens) or base(tokens[program]) != "env":
        return program
    program += 1
    while program < len(tokens):
        argument = tokens[program]
        if argument == "--":
            return program + 1
        if argument == "-" or ENV_ASSIGN.match(argument):
            program += 1
            continue
        if argument.startswith("--"):
            resolved = unique_long_option(argument, ENV_LONG_OPTIONS)
            if resolved is None:
                return None
            option, attached = resolved
            semantics = ENV_LONG_OPTIONS[option]
            if attached and semantics not in ("required", "optional"):
                return None
            if semantics == "terminal":
                return None
            if semantics == "required" and not attached:
                if program + 1 >= len(tokens):
                    return None
                program += 2
            else:
                program += 1
            continue
        if argument.startswith("-"):
            options = argument[1:]
            offset = 0
            while offset < len(options) and options[offset] in "i0v":
                offset += 1
            if offset == len(options):
                program += 1
                continue
            if options[offset] in "uCS" and offset + 1 == len(options):
                program += 2
                continue
            if options[offset] in "uCS":
                program += 1
                continue
            return None
        return program
    return None


def python_operand(tokens, program):
    """The script operand after Python options, or the literal -c source."""
    program += 1
    while program < len(tokens):
        argument = tokens[program]
        if argument == "--":
            return program + 1, None
        if argument == "-":
            return program, None
        if argument in ("-h", "-?", "-V", "--help", "--version", "--help-env",
                        "--help-xoptions", "--help-all"):
            return None, None
        if argument == "--check-hash-based-pycs":
            program += 2
            continue
        if argument.startswith("--check-hash-based-pycs="):
            program += 1
            continue
        if argument in ("--debug", "--inspect", "--isolated", "--no-site", "--no-user-site", "--quiet", "--verbose"):
            program += 1
            continue
        if argument.startswith("-"):
            options = argument[1:]
            for offset, option in enumerate(options):
                if option == "c":
                    source = options[offset + 1:]
                    if not source and program + 1 < len(tokens):
                        source = tokens[program + 1]
                    return None, source or None
                if option == "m" or option in "h?V":
                    return None, None
                if option in "WX":
                    program += 1 if options[offset + 1:] else 2
                    break
                if option not in "bBdEiIOPqRsSuvx":
                    return None, None
            else:
                program += 1
            continue
        return program, None
    return program, None


def literal_arg(call, position, keyword, default=None):
    node = call.args[position] if len(call.args) > position else None
    for item in call.keywords:
        if item.arg == keyword:
            node = item.value
            break
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else default


def python_sources(text):
    """Literal Python supplied to an executing interpreter, never quoted shell data."""
    sources = []
    for command in commands(text):
        tokens = tokens_of(command)
        program = env_operand(tokens, 0)
        if program is None or program >= len(tokens) or not is_python(tokens[program]):
            continue
        _program, source = python_operand(tokens, program)
        if source is not None:
            sources.append(source)

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = HEREDOC_OPEN.search(lines[index])
        if not match:
            index += 1
            continue
        fd = match.group(1)
        delimiter = match.group(4)
        end = index + 1
        while end < len(lines) and lines[end].strip() != delimiter:
            end += 1
        executes_python = False
        for command in commands(lines[index]):
            tokens = tokens_of(command)
            for offset, token in enumerate(tokens):
                redirect = HEREDOC_TOKEN.fullmatch(token)
                if redirect is None or redirect.group(1) != fd:
                    continue
                operand = redirect.group(2)
                if operand == delimiter:
                    del tokens[offset]
                elif not operand and offset + 1 < len(tokens) and tokens[offset + 1] == delimiter:
                    del tokens[offset:offset + 2]
                break
            if fd is not None and int(fd) != 0:
                continue
            program = env_operand(tokens, 0)
            if program is not None and program < len(tokens) and is_python(tokens[program]):
                operand, source = python_operand(tokens, program)
                executes_python = source is None and operand is not None and (
                    operand >= len(tokens) or tokens[operand] == "-"
                )
                if executes_python:
                    break
        if executes_python:
            sources.append("\n".join(lines[index + 1:end]))
        index = end + 1
    return sources


def python_written_paths(text):
    """Literal paths bound to writable stdlib open calls in executed Python."""
    paths = []
    for source in python_sources(text):
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            continue
        module_names = {}
        open_names = {"open"}
        path_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    if item.name in ("builtins", "io", "pathlib"):
                        module_names[item.asname or item.name] = item.name
            elif isinstance(node, ast.ImportFrom) and node.module in ("builtins", "io", "pathlib"):
                for item in node.names:
                    local = item.asname or item.name
                    if item.name == "open" and node.module in ("builtins", "io"):
                        open_names.add(local)
                    elif item.name == "Path" and node.module == "pathlib":
                        path_names.add(local)
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            function = call.func
            if (isinstance(function, ast.Name) and function.id in open_names) or (
                    isinstance(function, ast.Attribute) and function.attr == "open"
                    and isinstance(function.value, ast.Name)
                    and module_names.get(function.value.id) in ("builtins", "io")):
                path = literal_arg(call, 0, "file")
                mode = literal_arg(call, 1, "mode", "r")
                if path and mode and set(mode) <= set("rwaxtb+") and any(c in mode for c in "wax+"):
                    paths.append(path)
                continue
            if not isinstance(function, ast.Attribute) or function.attr not in ("open", "write_text", "write_bytes"):
                continue
            owner = function.value
            if not isinstance(owner, ast.Call) or not (
                    (isinstance(owner.func, ast.Name) and owner.func.id in path_names) or
                    (isinstance(owner.func, ast.Attribute) and owner.func.attr == "Path"
                     and isinstance(owner.func.value, ast.Name)
                     and module_names.get(owner.func.value.id) == "pathlib")):
                continue
            path = literal_arg(owner, 0, "")
            mode = literal_arg(call, 0, "mode", "r") if function.attr == "open" else "w"
            if path and mode and set(mode) <= set("rwaxtb+") and any(c in mode for c in "wax+"):
                paths.append(path)
    return paths


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
    state = os.path.join(STATE_DIR, conf.get("LANE_NAME"))
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
    program = env_operand(tokens, 0)
    if program is None:
        return None, {}
    name = base(tokens[program]) if program < len(tokens) else ""
    if is_python(name):
        program, _source = python_operand(tokens, program)
        if program is None:
            return None, {}
        name = base(tokens[program]) if program < len(tokens) else ""
    if name in DISPATCHERS:
        kind = "dispatcher"
    elif name == LAUNCHER:
        kind = "launcher"
    elif name == DRIVER:
        kind = "driver"
    if kind is None:
        return None, {}
    flags = {"input": [], "command": name}
    if kind == "launcher" and program + 1 < len(tokens) and not tokens[program + 1].startswith("-"):
        flags["verb"] = tokens[program + 1]
    elif kind == "launcher" and program + 1 < len(tokens) and tokens[program + 1] in ("--help", "-h"):
        flags["verb"] = "help"  # triage 2026-09-11: reading the usage is a read
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


def path_form_unittest(tokens):
    """The path argument of ``python -m unittest``, or None."""
    if not tokens or not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", base(tokens[0])):
        return None
    try:
        module = tokens.index("-m")
    except ValueError:
        return None
    if module + 1 >= len(tokens) or tokens[module + 1] != "unittest":
        return None
    args = tokens[module + 2:]
    if "discover" in args:
        return None
    for argument in args:
        if not argument.startswith("-") and ("/" in argument or argument.endswith(".py")):
            return argument
    return None


def expand(script_text, cwd):
    """Expand shell variables from the script's assignments, then the environment."""
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


def check_dispatch(kind, flags, cwd, text, grant):
    if kind == "launcher":
        if flags.get("verb") in LAUNCHER_READ_VERBS:
            return None
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
        if not os.path.isfile(absolute) or os.path.getsize(absolute) == 0:
            return deny("input-absent", "a readable non-empty input", f"{path} missing or empty", "write it before dispatch")
        content = read_text(absolute)
        unresolved = re.search(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[^}]+\})", content or "")
        if unresolved:
            return deny("input-absent", "inputs with literal resolved paths",
                        f"unresolved {unresolved.group(0)} in {path}", "write the resolved value into the input")
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
        if hit:
            return deny("bucket-command", "the bucket's tests as the named command",
                        f'"{hit.group(0)}" in {scope_file}',
                        "name the bucket's test files; the whole suite is not a bucket (ranking K2)")
        for statement in commands(scope_text):
            argument = path_form_unittest(tokens_of(statement))
            if argument:
                return deny("bucket-command", "the bucket's tests in unittest discover form",
                            f"path-form unittest argument {argument} in {scope_file}",
                            "name the tests with discover -s and -p")
    if job in WRITE_JOBS:
        inputs_text = "\n".join(read_text(os.path.normpath(os.path.join(cwd, p))) or "" for p in flags["input"])
        if not (WALK_HEADING.search(inputs_text) and WALK_LINE.search(inputs_text)):
            return deny("walkthrough",
                        'a "First-run walkthrough" section whose assumption lines are each measured or a refusal',
                        f"none in {' '.join(flags['input']) or 'no --input'}",
                        "walk the first run against the isolated home, no network, the read-only .git, "
                        "the job prompt and the runner workspace before dispatch (planning rule)")
    if worktree:
        trunk = conf.get("TRUNK_BRANCH")
        probe = subprocess.run(["git", "-C", root, "merge-base", "--is-ancestor", f"origin/{trunk}", "HEAD"],  # noqa: S603, S607 - PATH git; root is a path this hook resolved
                               capture_output=True, text=True, check=False)
        if probe.returncode == 1:
            # Owner, 2026-09-12: "why are the branches always out of date".
            # Behind is the dispatcher's job: it merges origin/<trunk> in
            # before the launch. Only a merge that would conflict refuses.
            trial = subprocess.run(["git", "-C", root, "merge-tree", "--write-tree", "--name-only",  # noqa: S603, S607 - PATH git; a dry merge, no ref moves
                                    "HEAD", f"origin/{trunk}"],
                                   capture_output=True, text=True, check=False)
            if trial.returncode == 1:
                files = [line for line in trial.stdout.splitlines()[1:] if line.strip()]
                return deny("stale-base", f"origin/{trunk} to merge cleanly into {worktree}",
                            f"conflicts in {', '.join(files) or 'unnamed files'}",
                            f"resolve them in the worktree (git merge origin/{trunk}), commit, then dispatch")
            if trial.returncode > 1:
                return deny("stale-base", f"a dry merge of origin/{trunk} from {worktree}",
                            (trial.stderr.strip().splitlines() or ["no answer"])[-1],
                            "a worktree the hook can read")
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
    if job and job not in ALLOWED_BY_HAND and not (grant is not None and not grant[1]):
        command = flags["command"]
        return deny("dispatch-by-hand", f"the ladder driver to run {job} (ops/bin/ladder.sh)",
                    f"{command} --job {job} from the session", "start or resume a ladder for the lane")
    return None


# --- the decision -----------------------------------------------------------

def graft_log(lane, kind, detail):
    """Append one line to the lane's graft-first log; never raise."""
    if not lane:
        return
    try:
        path = os.path.join(STATE_DIR, lane, GRAFT_LOG)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{_now_iso()}\t{kind}\t{detail}\n")
    except OSError:
        pass


def _now_iso():
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def graft_context_path(root, lane):
    """The prepared Graft context for ``root`` under the lane's state, else None."""
    import hashlib
    if not root or not lane:
        return None
    digest = hashlib.sha256(root.encode()).hexdigest()
    path = os.path.join(STATE_DIR, lane, "graft", f"{digest}.context.json")
    return path if os.path.isfile(path) else None


def search_targets(toks):
    """(pattern, code-ish targets) of a grep-family statement, or (None, [])."""
    if not toks:
        return None, []
    word = base(toks[0])
    args = toks[1:]
    if word == "git" and len(toks) > 1 and toks[1] == "grep":
        args = toks[2:]
    elif word not in SEARCHERS:
        return None, []
    if any(a in SEARCH_COUNT_FLAGS for a in args):
        return None, []
    positional = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "--":
            continue
        if a.startswith("-"):
            if a in ("-e", "-f", "-m", "-A", "-B", "-C", "--include", "--exclude", "--exclude-dir"):
                skip = True
            continue
        positional.append(a)
    if len(positional) < 2:
        return None, []  # a pipe filter or a pattern with no path is not code navigation
    return positional[0], positional[1:]


def graft_first(toks, cwd, root, lane):
    pattern, targets = search_targets(toks)
    if pattern is None:
        return None
    hits = []
    for target in targets:
        _, rel = relative(target, cwd)
        # a directory target normalises without its slash ("docs/" -> "docs")
        if is_code(rel) or (rel is not None and is_code(rel + "/")):
            hits.append(target)
    if not hits:
        return None
    context = graft_context_path(root, lane)
    query = (f"python3 {GRAFT_LEVER} query --context {context} graft_find_code "
             f"'{{\"query\": \"{pattern}\", \"limit\": 20}}'") if context else (
             f"python3 {GRAFT_LEVER} prepare --root {root}  (prints the context path), then "
             f"python3 {GRAFT_LEVER} query --context <that path> graft_find_code "
             f"'{{\"query\": \"{pattern}\", \"limit\": 20}}'")
    graft_log(lane, "deny", f"{base(toks[0])} {pattern} {' '.join(hits)}")
    return deny("graft-first", "code navigated through Graft (graft_find_code, graft_repo_map, graft_file_api)",
                f"{base(toks[0])} searching {' '.join(hits)} for {pattern!r}",
                f"{query}; a count (-c) or file list (-l) stays allowed")


DELIVERABLE_LOCK = "deliverable.json"


def deliverable_lock(lane):
    """The lane's deliverable lock (branches, why, by, at) or None."""
    if not lane:
        return None
    path = os.path.join(STATE_DIR, lane, DELIVERABLE_LOCK)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    branches = data.get("branches") if isinstance(data, dict) else None
    if not isinstance(branches, list) or not branches:
        return None
    return data


def branch_of(directory):
    try:
        proc = subprocess.run(["git", "-C", directory, "symbolic-ref", "--short", "HEAD"],  # noqa: S603,S607 - fixed argv, a read
                              capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() or None


def deliverable_targets(toks, cwd):
    """(what, branch) pairs a statement aims new work at."""
    if not toks:
        return []
    name = base(toks[0])
    found = []
    if name == "git" and len(toks) > 2:
        args = [t for t in toks[1:] if not t.startswith("-C")]
        if args[0] == "worktree" and args[1] == "add":
            rest = args[2:]
            if "-b" in rest or "-B" in rest:
                flag = "-b" if "-b" in rest else "-B"
                i = rest.index(flag)
                if i + 1 < len(rest):
                    found.append(("git worktree add -b", rest[i + 1]))
            else:
                positional = [t for t in rest if not t.startswith("-")]
                if len(positional) >= 2:
                    found.append(("git worktree add", positional[1]))
                elif positional:
                    found.append(("git worktree add", os.path.basename(positional[0].rstrip("/"))))
        elif args[0] in ("checkout", "switch") and any(f in args for f in ("-b", "-B", "-c", "-C")):
            flag = next(f for f in ("-b", "-B", "-c", "-C") if f in args)
            i = args.index(flag)
            if i + 1 < len(args):
                found.append((f"git {args[0]} {flag}", args[i + 1]))
    elif name == "gh" and len(toks) > 2 and toks[1] == "pr" and toks[2] == "create":
        if "--head" in toks:
            i = toks.index("--head")
            branch = toks[i + 1] if i + 1 < len(toks) else None
        else:
            branch = branch_of(cwd)
        found.append(("gh pr create for", branch or "an unreadable branch"))
    elif name in DISPATCHERS:
        if "--branch" in toks:
            i = toks.index("--branch")
            found.append((f"{name} --branch", toks[i + 1] if i + 1 < len(toks) else ""))
        elif "--worktree" in toks:
            i = toks.index("--worktree")
            directory = toks[i + 1] if i + 1 < len(toks) else cwd
            found.append((f"{name} --worktree", branch_of(os.path.join(cwd, os.path.expanduser(directory))) or directory))
    elif name == DRIVER and len(toks) > 2 and toks[1] != "resume":
        positional = [t for t in toks[1:] if not t.startswith("-")]
        if len(positional) >= 2:
            found.append(("ladder start for", positional[1]))
    return found


def deliverable(toks, cwd, lane):
    """Owner, 2026-09-11: "i want an immediate FIX to stop that". While the
    lock names the deliverable branches, new work aimed anywhere else
    refuses. Findings found on the way are evidence for the ledger, not
    work; the lock is lifted by its lever, never by a grant."""
    lock = deliverable_lock(lane)
    if lock is None:
        return None
    branches = [str(b) for b in lock["branches"]]
    for what, branch in deliverable_targets(toks, cwd):
        if branch not in branches:
            return deny("deliverable",
                        f"work on the deliverable branches {', '.join(branches)} "
                        f"(locked {lock.get('at', '?')} by {lock.get('by', '?')}: {lock.get('why', '')})",
                        f"{what} {branch}",
                        "finish the deliverable; record what you found in the ledger; "
                        "python3 ops/conductor/tools/deliverable.py clear lifts the lock when it lands")
    return None


PROOF_HEADING = re.compile(r"^##\s+Proof\b.*$", re.MULTILINE)
PROOF_ID = re.compile(r"\bP-[A-Za-z0-9][A-Za-z0-9_-]*")
PROBES_DIR = "ops/conductor/handoff/probes/"
CI_WORKFLOW = "ci"


def proof_ids(body):
    """The corpus row ids named under the PR body's ## Proof heading."""
    match = PROOF_HEADING.search(body or "")
    if match is None:
        return None
    section = body[match.end():]
    nxt = re.search(r"^##\s", section, re.MULTILINE)
    if nxt:
        section = section[:nxt.start()]
    ids = []
    for found in PROOF_ID.findall(section):
        if found not in ids:
            ids.append(found)
    return ids


def corpus_ids_at(root, head):
    """Every row id in the probes corpus at a commit; None when it cannot be read."""
    listing = subprocess.run(["git", "-C", root, "ls-tree", "--name-only", head, "--", PROBES_DIR],  # noqa: S603,S607 - fixed argv, a read
                             capture_output=True, text=True, timeout=30, check=False)
    if listing.returncode != 0:
        return None
    ids = set()
    for path in listing.stdout.split():
        if not path.endswith(".jsonl"):
            continue
        shown = subprocess.run(["git", "-C", root, "show", f"{head}:{path}"],  # noqa: S603,S607 - fixed argv, a read
                               capture_output=True, text=True, timeout=30, check=False)
        if shown.returncode != 0:
            return None
        for line in shown.stdout.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                ids.add(row["id"])
    return ids


def pr_number(toks):
    for tok in toks[3:]:
        if tok.isdigit():
            return tok
        if tok.startswith("https://") and tok.rstrip("/").rsplit("/", 1)[-1].isdigit():
            return tok.rstrip("/").rsplit("/", 1)[-1]
    return None


def pr_proof(toks, cwd):
    """Owner, 2026-09-12: "it has to be impossible to not do the work".
    A PR is marked ready or merged only against proof the system verifies
    here: the rows the body names exist at the head, and a green ci run
    on that head executed them. No grant escape."""
    if not toks or base(toks[0]) != "gh" or len(toks) < 3 or toks[1] != "pr" or toks[2] not in ("ready", "merge"):
        return None
    verb = f"gh pr {toks[2]}"
    needed_proof = ("add rows under ops/conductor/handoff/probes/ on the branch, name their ids under "
                    "a `## Proof` heading in the PR body, push, and wait for the ci run on that head")
    number = pr_number(toks)
    if number is None:
        return deny("pr-proof", f"{verb} naming the PR number", "no number", "name the PR number")
    view = subprocess.run(["gh", "pr", "view", number, "--json", "body,headRefOid,headRefName"],  # noqa: S603,S607 - PATH gh; a read
                          cwd=cwd, capture_output=True, text=True, timeout=60, check=False)
    if view.returncode != 0:
        return deny("pr-proof", f"a readable PR #{number}",
                    f"gh pr view failed: {(view.stderr or view.stdout).strip().splitlines()[:1]}",
                    "could not look is not a pass; fix gh and retry")
    try:
        data = json.loads(view.stdout)
    except ValueError:
        return deny("pr-proof", f"JSON from gh pr view {number}", "unparseable output", "fix gh and retry")
    head = str(data.get("headRefOid") or "")
    branch = str(data.get("headRefName") or "")
    ids = proof_ids(str(data.get("body") or ""))
    if not ids:
        found = "no `## Proof` section in the PR body" if ids is None else "a `## Proof` section naming no P- row id"
        return deny("pr-proof", f"a `## Proof` section naming corpus rows (P-... ids) that pass at head {head[:8]}",
                    found, needed_proof)
    root = repo_root(cwd) or cwd
    present = subprocess.run(["git", "-C", root, "cat-file", "-e", f"{head}^{{commit}}"],  # noqa: S603,S607 - fixed argv, a read
                             capture_output=True, text=True, timeout=30, check=False)
    if present.returncode != 0:
        return deny("pr-proof", f"the PR head {head[:8]} fetched here", "not a local object",
                    f"git fetch origin {branch or '<branch>'} and retry")
    corpus = corpus_ids_at(root, head)
    if corpus is None:
        return deny("pr-proof", f"the probes corpus readable at {head[:8]}", "git could not read it",
                    "could not look is not a pass; check the head")
    missing = [i for i in ids if i not in corpus]
    if missing:
        return deny("pr-proof", f"every Proof row present in {PROBES_DIR} at {head[:8]}",
                    f"absent: {', '.join(missing)}", needed_proof)
    runs = subprocess.run(["gh", "run", "list", "--commit", head, "--json", "name,workflowName,status,conclusion,headSha"],  # noqa: S603,S607 - PATH gh; a read
                          cwd=cwd, capture_output=True, text=True, timeout=60, check=False)
    if runs.returncode != 0:
        return deny("pr-proof", f"the ci runs on {head[:8]}",
                    f"gh run list failed: {(runs.stderr or runs.stdout).strip().splitlines()[:1]}",
                    "could not look is not a pass; fix gh and retry")
    try:
        rows = json.loads(runs.stdout)
    except ValueError:
        rows = None
    if not isinstance(rows, list):
        return deny("pr-proof", f"JSON from gh run list --commit {head[:8]}", "unparseable output", "fix gh and retry")
    ci = [r for r in rows if isinstance(r, dict) and CI_WORKFLOW in (r.get("workflowName"), r.get("name"))
          and str(r.get("headSha") or head) == head]
    done = [r for r in ci if r.get("status") == "completed"]
    if not done:
        state = ", ".join(str(r.get("status")) for r in ci) or "no ci run"
        return deny("pr-proof", f"a completed ci run on {head[:8]} (it executes the Proof rows)",
                    state, f"wait for it: gh run list --commit {head}")
    if not any(r.get("conclusion") == "success" for r in done):
        return deny("pr-proof", f"a green ci run on {head[:8]}",
                    f"conclusion {', '.join(str(r.get('conclusion')) for r in done)}",
                    "fix the branch until the run is green; the Proof rows are in it")
    return None


CLAIM_WORDS = re.compile(
    r"\b(enforced|in force|is done|are done|now done|landed|merged|green|complete|completed|"
    r"impossible|verified|proven|proved|passes|passing|works|wired|consumed|settled|holds|fixed)\b",
    re.IGNORECASE)
READING_TOKENS = re.compile(
    r"\b[0-9a-f]{7,40}\b|\d{8}T\d{6}Z-[a-z-]+-[0-9a-f]{6}|\bP-[A-Z0-9]+-\d{8}-[\w-]+|#\d+|\brun \d+|"
    r"\bRan \d+ tests|\b\d+ of \d+\b|\b\d+ (?:OK|red|failures?|errors?)\b|\bexit(?:=| )\d|"
    r"\bnot measured\b|\bunmeasured\b|\bunresolved\b|\bnot verified\b|\bnot enforced\b|\bnot yet\b",
    re.IGNORECASE)
PUBLISH_PATHS = re.compile(r"(^|/)(ops/conductor/|\.claude/skills/|docs/)|(^|/)(AGENTS|CONTRIB|ops/README)\.md$")
HEREDOC_WRITE = re.compile(
    r"(?:cat|tee)(?:\s+-a)?\s*>{1,2}\s*(\S+)\s*<<-?\s*(['\"]?)(\w+)\2[^\n]*\n(.*?)\n\3(?:\n|$)", re.DOTALL)
QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”')


def unmeasured_claim(text):
    """The first line that claims without a reading in its paragraph, or None.
    Quoted spans are somebody else's words and are not the writer's claim;
    a paragraph opening with `>` is a quotation."""
    for paragraph in re.split(r"\n\s*\n", text or ""):
        lines = [line for line in paragraph.splitlines() if line.strip()]
        if not lines or lines[0].lstrip().startswith(">"):
            continue
        stripped = QUOTED.sub("", paragraph)
        if READING_TOKENS.search(stripped):
            continue
        for line in lines:
            if CLAIM_WORDS.search(QUOTED.sub("", line)):
                return line.strip()
    return None


def published_texts(toks, text, cwd):
    """(surface, text) pairs a statement publishes: a commit message, a PR
    body or comment, a record or law page written by heredoc."""
    found = []
    if toks and base(toks[0]) == "git":
        sub, rest, _ = _git_subcommand(toks, cwd)
        if sub == "commit":
            for i, tok in enumerate(rest):
                if tok in ("-m", "--message") and i + 1 < len(rest):
                    found.append(("commit message", rest[i + 1]))
                elif tok.startswith("-m") and len(tok) > 2:
                    found.append(("commit message", tok[2:]))
                elif tok in ("-F", "--file") and i + 1 < len(rest):
                    body = read_text(os.path.normpath(os.path.join(cwd, os.path.expanduser(rest[i + 1]))))
                    if body is not None:
                        found.append((f"commit message {rest[i + 1]}", body))
    if toks and base(toks[0]) == "gh" and len(toks) > 2 and toks[1] in ("pr", "issue"):
        for i, tok in enumerate(toks):
            if tok == "--body" and i + 1 < len(toks):
                found.append((f"gh {toks[1]} {toks[2]} --body", toks[i + 1]))
            elif tok == "--body-file" and i + 1 < len(toks):
                body = read_text(os.path.normpath(os.path.join(cwd, os.path.expanduser(toks[i + 1]))))
                if body is not None:
                    found.append((f"gh {toks[1]} {toks[2]} --body-file {toks[i + 1]}", body))
    return found


def heredoc_records(text, cwd):
    """(path, body) for every heredoc written onto a publishing surface."""
    found = []
    for match in HEREDOC_WRITE.finditer(text or ""):
        target = match.group(1).strip("'\"")
        _, rel = relative(os.path.normpath(os.path.join(cwd, os.path.expanduser(target))), cwd)
        if PUBLISH_PATHS.search(rel or target):
            found.append((target, match.group(4)))
    return found


def claim_unmeasured(surface, body):
    line = unmeasured_claim(body)
    if line is None:
        return None
    return deny("claim-unmeasured",
                "every paragraph that claims (enforced, done, landed, merged, green, impossible, verified, "
                "fixed, ...) to carry its reading beside the claim: a sha, a record id, a P- row, #PR, a run "
                "id, \"Ran N tests\", or the words not measured",
                f"in the {surface}: \"{line[:140]}\"",
                "measure it and cite the reading in the same paragraph, or write that it is not measured; "
                "no grant lifts this row (owner, 2026-09-12: \"you have to enforce it before you state it as "
                "fact - with evidence\")")


TRUNK_WRITES = ("commit", "merge", "cherry-pick", "rebase", "revert", "am")
TRUNK_WRITES = ("commit", "merge", "cherry-pick", "rebase", "revert", "am")


def _git_subcommand(toks, cwd):
    """(subcommand, rest, directory) for a git statement, honouring -C and -c."""
    args = toks[1:]
    directory = cwd
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "-C" and i + 1 < len(args):
            directory = os.path.normpath(os.path.join(cwd, os.path.expanduser(args[i + 1])))
            i += 2
            continue
        if tok.startswith("-C") and len(tok) > 2:
            directory = os.path.normpath(os.path.join(cwd, os.path.expanduser(tok[2:])))
            i += 1
            continue
        if tok in ("-c", "--git-dir", "--work-tree") and i + 1 < len(args):
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        break
    rest = args[i:]
    return (rest[0] if rest else None), rest[1:], directory


def trunk_commit(toks, cwd, conf):
    """Owner, 2026-09-12: "one branch per session - lets try it" and "you
    have to enforce it before you state it as fact - with evidence". A
    session never commits on the trunk or the release branch, and never
    pushes to them: its work and its records ride its session branch and
    land through one draft PR. Merges into the trunk happen on the forge.
    No grant lifts this row."""
    if not toks or base(toks[0]) != "git":
        return None
    protected = {b for b in (conf.get("TRUNK_BRANCH"), conf.get("RELEASE_BRANCH")) if b}
    if not protected:
        return None
    sub, rest, directory = _git_subcommand(toks, cwd)
    needed = ("cut the session branch and commit there: git worktree add ../wt/ag-session-<date>-<id> "
              "-b lane/session-<date>-<id> origin/<trunk>; python3 ops/conductor/tools/deliverable.py add "
              "lane/session-<date>-<id> --why '<the owner's words>'; one draft PR at close. No grant lifts this row")
    if sub == "push":
        operands = [t for t in rest if not t.startswith("-")]
        for spec in operands[1:]:
            dst = spec.split(":", 1)[1] if ":" in spec else spec
            dst = dst.lstrip("+")
            dst = dst.removeprefix("refs/heads/")
            if dst in protected:
                return deny("trunk-commit", "a push to a session branch (lane/session-<date>-<id>)",
                            f"git push to {dst}", needed)
        return None
    if sub in TRUNK_WRITES:
        branch = branch_of(directory)
        if branch in protected:
            return deny("trunk-commit", "a commit on a session branch (lane/session-<date>-<id>)",
                        f"git {sub} on {branch} in {directory}", needed)
    return None


def check_text(text, cwd, depth=0):
    root = repo_root(cwd)
    conf = lane_conf(root)
    lane = conf.get("LANE_NAME")
    grant = open_grant(text, lane)
    for path in python_written_paths(text):
        _, rel = relative(path, cwd)
        if is_code(rel) and not grant_covers(grant, rel):
            return deny("hand-write", "code changed through the ladder (freeze)",
                        f"a script writing {path}", "the ladder, or HAND_GRANT=<open id> whose scope names the path")
    if depth == 0:
        for target, body in heredoc_records(text, cwd):
            refusal = claim_unmeasured(f"record {target}", body)
            if refusal:
                return refusal
    for statement in commands(text):
        toks = tokens_of(statement)
        if not toks:
            continue
        for surface, body in published_texts(toks, text, cwd):
            refusal = claim_unmeasured(surface, body)
            if refusal:
                return refusal
        for target in prune_targets(toks, cwd, conf):
            return deny("prune", "data kept (never prune)", f"rm -r {target}", "leave it; move it under .dev/tmp with a note if it is in the way")
        if depth == 0 and GRAFT_LEVER.rsplit("/", 1)[-1] in " ".join(toks) and "query" in toks:
            graft_log(lane, "query", " ".join(t for t in toks if t.startswith("graft_")) or "query")
        refusal = graft_first(toks, cwd, root, lane)
        if refusal:
            return refusal
        refusal = deliverable(toks, cwd, lane)
        if refusal:
            return refusal
        refusal = pr_proof(toks, cwd)
        if refusal:
            return refusal
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
        # after hand-write, so a patch applied by hand on the trunk names the
        # older row the tests pin; every other trunk write names this one
        refusal = trunk_commit(toks, cwd, conf)
        if refusal:
            return refusal
        kind, flags = dispatch_args(toks)
        if kind:
            refusal = check_dispatch(kind, flags, cwd, text, grant)
            if refusal:
                return refusal
        unittest_path = path_form_unittest(toks)
        if unittest_path:
            return deny("test-form", "the discover form (python3 -m unittest discover -s <tests dir> -p <file>) or ops/bin/suites.sh",
                        f"a path-form unittest argument {unittest_path}", "the discover form")
        if depth == 0 and base(toks[0]) in ("bash", "sh", "source", ".") and len(toks) > 1:
            if toks[1] == "-c" and len(toks) > 2:
                # Triage 2026-09-11: the outer command's grant covers the
                # body it runs; without this a granted `bash -c` was refused.
                body = toks[2]
                if grant is not None:
                    body = f"HAND_GRANT={grant[0]} {body}"
                refusal = check_text(body, cwd, depth + 1)
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
        # Owner, 2026-09-11: every refusal logs a miss against the skill it
        # names, so the skills report measures the pages instead of
        # believing them. Best effort, after the refusal is on stdout.
        reason = refusal.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        klass = reason.split("]", 1)[0].split(":", 1)[-1] if reason.startswith("[matrix:") else ""
        miss.log_miss((payload.get("cwd") if isinstance(payload, dict) else None),
                      klass, reason, hook="matrix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
