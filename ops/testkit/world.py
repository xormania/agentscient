"""The world a test runs in: a temporary root that owns HOME, the XDG
roots, TMPDIR, the working directory, a hermetic environment, planted
files and tools, owned child processes, and before/after snapshots of
declared paths. Hermetic by default: nothing from the host reaches a
subject unless it is named — values in ``ambient``, tools in
``ambient_tools``. Owned children are reaped at close. A plant proves it
landed.

PATH is the one exception, and it is dated. ``World(host_path=False)`` is
the hermetic PATH the contract asks for: the world's own bin and nothing
else, so a tool the case neither planted nor named is absent. That is the
default-to-be, and it is not the default today. LD-72 is the defect; the
strict shape turns 1,339 rows red across 95 modules whose fixtures run a
host tool the world would no longer carry, measured and listed in
``ops/conductor/handoff/HANDOFF-2026-09-16-hermetic-path-sweep.md`` at
``d8219578``. Until that sweep lands, ``host_path`` defaults to True and a
subject sees the world's bin followed by the host's PATH, as before. The
kit's own suite runs strict, so the behaviour stays measured while the
callers catch up.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

FIXED_DATE = "2026-01-02T03:04:05Z"
USER = "Test User"
EMAIL = "test@example.invalid"

# The host values a world never carries unless ``ambient`` names them:
# every GIT_* value, the XDG roots, HOME, TMPDIR and the escape hatches a
# hook or a tool reads. PATH is not one of them: it is never settable
# through ``ambient`` and is governed by ``host_path`` instead, whose
# strict value is the world's bin alone (LD-72).
_ALWAYS_OWN = ("HOME", "TMPDIR", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")


class PlantFailed(AssertionError):
    """The fixture was not what the case claimed to set up: INVALID, not a verdict."""


#: Words a caller writes when they mean a choice. A PATH could in
#: principle be a one-entry relative path spelled `false`, so the ambiguity
#: is refused rather than settled one way
#: (20260916T122524Z-review-codex-05a9f5#9).
_CHOICE_WORDS = frozenset({"", "0", "1", "true", "false", "yes", "no", "on", "off"})


def a_tool_name(name):
    """The name, when it names a tool a world may place on its own bin.

    A world places a tool at ``world.bin / name`` but resolves the real one
    against the caller's directory, so a name carrying a separator or ``..``
    put an executable outside the world, which then survived its close
    (20260916T122524Z-review-codex-05a9f5#3). A tool name is a file name."""
    text = str(name)
    separators = [sep for sep in (os.sep, os.altsep) if sep]
    if (not text or text in (".", "..") or text.startswith("-")
            or any(sep in text for sep in separators)):
        raise PlantFailed(
            f"INVALID: {text!r} is not a tool name; a world places its tools on "
            "its own bin, so the name is one file name with no separator, no "
            "'.' or '..', and no leading dash"
        )
    return text


def a_path_choice(value):
    """``host_path`` for a World: True or False and nothing else.

    A World uses it as a choice, never as a PATH, and ``bool('false')`` is
    True, so a caller who spelled a false value got the host's PATH and no
    word about it (20260916T122524Z-review-codex-05a9f5#9)."""
    if isinstance(value, bool):
        return value
    raise PlantFailed(
        f"INVALID: host_path is True or False; found {type(value).__name__} "
        f"{value!r}; a World uses it as a choice, and hermetic_env is the door "
        "that takes a PATH to follow"
    )


def a_path_or_choice(value):
    """``host_path`` for hermetic_env: True, False, or the PATH to follow."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() in _CHOICE_WORDS:
            raise PlantFailed(
                f"INVALID: host_path {value!r} reads as a choice and as a PATH "
                "of one entry, and nothing here can tell which was meant; pass "
                "True, False, or a PATH this is not"
            )
        return value
    raise PlantFailed(
        f"INVALID: host_path is True, False, or the PATH to follow; found "
        f"{type(value).__name__} {value!r}"
    )


class World:
    def __init__(self, *, ambient=(), ambient_tools=(), prefix="world-", keep=False,
                 host_path=True):
        self.root = Path(tempfile.mkdtemp(prefix=prefix))
        self.home = self.root / "home"
        self.xdg_state = self.root / "xdg" / "state"
        self.xdg_config = self.root / "xdg" / "config"
        self.xdg_cache = self.root / "xdg" / "cache"
        self.tmp = self.root / "tmp"
        self.cwd = self.root / "cwd"
        self.bin = self.root / "bin"
        for path in (self.home, self.xdg_state, self.xdg_config, self.xdg_cache,
                     self.tmp, self.cwd, self.bin):
            path.mkdir(parents=True)
        self.ambient = tuple(ambient)
        for name in self.ambient:
            if name == "PATH":
                raise PlantFailed(
                    "INVALID: PATH is the world's own and cannot be ambient; "
                    "name the tools the case needs in ambient_tools, or pass "
                    "host_path to choose whether the host's PATH follows the "
                    "world's bin"
                )
            if name in _ALWAYS_OWN:
                raise PlantFailed(f"INVALID: {name} is the world's own and cannot be ambient")
        for name in ambient_tools:
            a_tool_name(name)
        self.keep = keep
        # False is the hermetic PATH of LD-72, the world's bin alone; True,
        # today's default, appends the host's after it. See the module
        # docstring for the date and the sweep that moves the default.
        self.host_path = a_path_choice(host_path)
        self._children: list[subprocess.Popen] = []
        self._saved_environ: dict[str, str] | None = None
        self._tools = None
        self.closed = False
        # Read once, at construction: a world entered later has replaced
        # os.environ with its own, and the host's PATH is gone by then.
        self._host_path = os.environ.get("PATH", "/usr/bin:/bin")
        self.ambient_tools = tuple(ambient_tools)
        for name in self.ambient_tools:
            self.ambient_tool(name)

    # -- the environment -------------------------------------------------

    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """The hermetic environment: the world's own roots, a fixed git
        identity and clock, C locales, and only the ambient names from the
        host. ``extra`` overrides, as the case declares."""
        return hermetic_env(self.home, xdg_state=self.xdg_state, xdg_config=self.xdg_config,
                            xdg_cache=self.xdg_cache, tmp=self.tmp, bin=self.bin,
                            host_path=self._host_path if self.host_path else False,
                            ambient=self.ambient, extra=extra)

    def enter(self) -> World:
        """Patch ``os.environ`` to the world's environment for an
        in-process subject; ``exit`` restores it exactly."""
        if self._saved_environ is None:
            self._saved_environ = dict(os.environ)
        # The new environment is read from the host before the host is
        # cleared, or the named ambient values are lost (ruled rank 4,
        # record 20260915T025600Z-adjudicate-codex-68d3d9).
        fresh = self.env()
        os.environ.clear()
        os.environ.update(fresh)
        return self

    def exit(self) -> None:
        if self._saved_environ is not None:
            os.environ.clear()
            os.environ.update(self._saved_environ)
            self._saved_environ = None

    def __enter__(self) -> World:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- planting --------------------------------------------------------

    def path(self, target) -> Path:
        target = Path(target)
        return target if target.is_absolute() else self.root / target

    def plant_text(self, target, content: str, *, recognisable: str | None = None) -> Path:
        """Write ``content`` under the world and prove it landed intact."""
        return plant_text(self.path(target), content, recognisable=recognisable)

    def plant_bytes(self, target, data: bytes) -> Path:
        return plant_bytes(self.path(target), data)

    def stage(self, subject, name: str | None = None, *, siblings=()) -> Path:
        """Copy a subject's bytes into the world so a test never runs the
        tree's own file; ``siblings`` ride along beside it. An absent
        subject stages an absent stand-in (exit 0, no output) so the case
        fails on its own assertion, never on the copy."""
        subject = Path(subject)
        dest = self.root / "stage" / (name or subject.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if subject.is_file():
            data = subject.read_bytes()
            dest.write_bytes(data)
            if dest.read_bytes() != data:
                raise PlantFailed(f"INVALID: staged copy of {subject} did not land intact")
            for sibling in siblings:
                source = subject.with_name(sibling)
                if not source.is_file():
                    raise PlantFailed(f"INVALID: sibling {sibling} is absent beside {subject}")
                (dest.parent / sibling).write_bytes(source.read_bytes())
        else:
            dest.write_bytes(b"import sys\nsys.exit(0)\n")
        return dest

    def ambient_tool(self, name: str) -> Path:
        """A host tool this world carries, named: resolved on the host by
        absolute path and placed on the world's bin as a wrapper that logs
        every call. A name the case already planted is left where it is, so
        a plant wins over an ambient tool of the same name."""
        name = a_tool_name(name)
        placed = self.bin / name
        if placed.exists():
            return placed
        return self.tools.wrap(name, host_path=self._host_path)

    def require(self, tool: str) -> str:
        """An ambient tool the case needs; its absence is INVALID, never a verdict."""
        return require(tool)

    # -- children --------------------------------------------------------

    def own(self, child: subprocess.Popen) -> subprocess.Popen:
        """Register a child the world reaps at close."""
        self._children.append(child)
        return child

    def reap(self, child: subprocess.Popen) -> None:
        with contextlib.suppress(ProcessLookupError, OSError):
            child.kill()
        with contextlib.suppress(Exception):
            child.communicate(timeout=10)
        if child.poll() is None:
            raise PlantFailed(f"INVALID: child {child.pid} was not reaped")

    # -- git -------------------------------------------------------------

    def git(self, *args: str, cwd=None, check: bool = True, timeout: float = 60):
        """Git in this world. A world that offers git must carry it, so this
        method declares git ambient for itself: the first call places the
        logged wrapper on the world's bin. A planted git wins over it."""
        from .command import run
        self.ambient_tool("git")
        argv = ["git", "-c", f"user.name={USER}", "-c", f"user.email={EMAIL}",
                "-c", "commit.gpgsign=false", *args]
        return run(argv, cwd=cwd or self.cwd, env=self.env(), timeout=timeout,
                   expect=0 if check else None)

    # -- watching --------------------------------------------------------

    def watch(self, *paths, ignore=(), tolerate_new=(), contents=True) -> Watch:
        """Snapshot the declared paths now, to compare at the case's end.
        ``contents=True`` reads every descendant's bytes, so a rewrite in
        place shows; ``contents=False`` reads presence, kind and the
        immediate names only, the shape a guard over a large live store
        declares (ops/conductor/test-store-guard.md)."""
        return Watch(paths, ignore=ignore, tolerate_new=tolerate_new, contents=contents)

    # -- the fake registry ------------------------------------------------

    @property
    def tools(self):
        if self._tools is None:
            from .fakes import Tools
            self._tools = Tools(self)
        return self._tools

    # -- close -----------------------------------------------------------

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for child in self._children:
            self.reap(child)
        self.exit()
        if not self.keep:
            shutil.rmtree(self.root, ignore_errors=True)


# -- the environment and the plants, as functions ---------------------------
# A suite whose fixture predates the World keeps its own home and reaches
# these by name; the World's methods are the same functions bound to its
# own roots, so one implementation answers both.

def hermetic_env(home, *, xdg_state=None, xdg_config=None, xdg_cache=None, tmp=None, bin=None,
                 host_path=True, ambient=(), extra: dict[str, str] | None = None) -> dict[str, str]:
    """The hermetic environment for ``home``: the roots (defaulting to the
    XDG layout under ``home`` and ``home``/tmp), a PATH built from ``bin``
    and ``host_path``, a fixed git identity and clock, C locales, and only
    the ``ambient`` names from the host. ``extra`` overrides.

    ``host_path`` is True to read the host's PATH now and put it after
    ``bin``, a string to use one already read, and False for the hermetic
    PATH of LD-72: ``bin`` alone, so a tool the case neither planted nor
    named is absent."""
    home = Path(home)
    # TMPDIR names a directory that exists: the world's own, or a caller's
    # home/tmp when it has one; a home without one keeps the system default,
    # since a TMPDIR nobody created breaks every mktemp under it.
    if tmp is None and (home / "tmp").is_dir():
        tmp = home / "tmp"
    host_path = a_path_or_choice(host_path)
    if host_path is True:
        host_path = os.environ.get("PATH", "")
    env = {
        "PATH": os.pathsep.join(
            part for part in (str(bin) if bin is not None else "", host_path or "") if part),
        "HOME": str(home),
        "XDG_STATE_HOME": str(xdg_state or home / ".local" / "state"),
        "XDG_CONFIG_HOME": str(xdg_config or home / ".config"),
        "XDG_CACHE_HOME": str(xdg_cache or home / ".cache"),
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_AUTHOR_NAME": USER,
        "GIT_AUTHOR_EMAIL": EMAIL,
        "GIT_COMMITTER_NAME": USER,
        "GIT_COMMITTER_EMAIL": EMAIL,
        "GIT_AUTHOR_DATE": FIXED_DATE,
        "GIT_COMMITTER_DATE": FIXED_DATE,
    }
    if tmp is not None:
        env["TMPDIR"] = str(tmp)
    for name in ambient:
        if name in os.environ:
            env[name] = os.environ[name]
    if extra:
        env.update(extra)
    return env


def plant_text(path, content: str, *, recognisable: str | None = None) -> Path:
    """Write ``content`` and prove it landed intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    landed = path.read_text(encoding="utf-8")
    if landed != content:
        raise PlantFailed(f"INVALID: plant did not reach disk for {path} "
                          f"(wanted {len(content)} chars, got {len(landed)})")
    if content and not landed:
        raise PlantFailed(f"INVALID: plant emptied {path}")
    if recognisable is not None and recognisable not in landed:
        raise PlantFailed(f"INVALID: plant left {path} unrecognisable as the fixture")
    return path


def plant_bytes(path, data: bytes) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    landed = path.read_bytes()
    if landed != data:
        raise PlantFailed(f"INVALID: plant did not reach disk for {path}")
    return path


def require(tool: str) -> str:
    """An ambient tool a case needs; its absence is INVALID, never a verdict."""
    found = shutil.which(tool)
    if found is None:
        raise PlantFailed(f"INVALID: {tool} is not on PATH")
    return found


# -- snapshots -----------------------------------------------------------

def snapshot(path: Path) -> tuple[str, tuple[str, ...]]:
    """One path: ``absent``; ``file`` with its content digest; ``dir``
    with its immediate names; ``other`` for anything else."""
    path = Path(path)
    if not path.exists():
        return ("absent", ())
    if path.is_dir():
        return ("dir", tuple(sorted(p.name for p in path.iterdir())))
    if path.is_file():
        return ("file", (hashlib.sha256(path.read_bytes()).hexdigest(),))
    return ("other", ())


def snapshot_tree(path: Path) -> dict:
    """``snapshot`` of ``path`` and, under a directory, of every descendant,
    keyed by path: a rewrite in place shows as a changed digest (ruled
    rank 1, record 20260915T025600Z-adjudicate-codex-68d3d9)."""
    path = Path(path)
    tree = {str(path): snapshot(path)}
    if path.is_dir():
        for child in sorted(path.iterdir()):
            tree.update(snapshot_tree(child))
    return tree


def _patterns(items):
    return tuple(re.compile(p) if isinstance(p, str) else p for p in items)


def compare(before: dict, after: dict, *, ignore=(), tolerate_new=()) -> tuple[dict, dict]:
    """Return (expected, actual) with the declared exclusions applied:
    a name matching ``ignore`` is dropped on both sides; a name matching
    ``tolerate_new`` may appear after without being before, but a
    pre-existing one that vanished still shows."""
    ignore = _patterns(ignore)
    tolerate_new = _patterns(tolerate_new)

    def ignored(name):
        return any(p.fullmatch(name) for p in ignore)

    expected: dict = {}
    for key, (kind, names) in before.items():
        if kind == "dir":
            names = tuple(n for n in names if not ignored(n))
        expected[key] = (kind, names)
    actual: dict = {}
    for key, (kind, names) in after.items():
        if kind == "dir" and key in before and before[key][0] == "dir":
            previous = set(before[key][1])
            names = tuple(
                n for n in names
                if not ignored(n)
                and (n in previous or not any(p.match(n) for p in tolerate_new))
            )
        actual[key] = (kind, names)
    return expected, actual


class Watch:
    """A before snapshot of declared paths and their contents, compared
    at the case's end. ``ignore`` and ``tolerate_new`` are name patterns
    and reach every level: a descendant under an ignored name is dropped
    on both sides, one under a tolerated new name is dropped from the
    after side when that name was not there before."""

    def __init__(self, paths, *, ignore=(), tolerate_new=(), contents=True):
        self.paths = [Path(p) for p in paths]
        self.ignore = tuple(ignore)
        self.tolerate_new = tuple(tolerate_new)
        self.contents = contents
        self.before = self._tree(before=None)

    def _tree(self, *, before) -> dict:
        if not self.contents:
            return {str(p): snapshot(p) for p in self.paths}
        ignore = _patterns(self.ignore)
        tolerate_new = _patterns(self.tolerate_new)
        tree: dict = {}
        for root in self.paths:
            for key, value in snapshot_tree(root).items():
                parts = Path(key).relative_to(root).parts
                if any(p.fullmatch(name) for name in parts for p in ignore):
                    continue
                if before is not None and key not in before and any(
                        p.match(name) for name in parts for p in tolerate_new):
                    continue
                tree[key] = value
        return tree

    def now(self) -> dict:
        return self._tree(before=self.before)

    def changed(self) -> tuple[dict, dict]:
        return compare(self.before, self.now(), ignore=self.ignore, tolerate_new=self.tolerate_new)

    def assert_unchanged(self, case=None, message: str = "watched path mutated") -> None:
        expected, actual = self.changed()
        if case is not None:
            case.assertEqual(actual, expected, message)
        elif actual != expected:
            raise AssertionError(f"{message}: expected {expected!r}, found {actual!r}")


def make_executable(path: Path) -> Path:
    path = Path(path)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if not os.access(path, os.X_OK):
        raise PlantFailed(f"INVALID: {path} is not executable")
    return path
