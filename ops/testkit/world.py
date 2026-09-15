"""The world a test runs in: a temporary root that owns HOME, the XDG
roots, TMPDIR, the working directory, a hermetic environment, planted
files and tools, owned child processes, and before/after snapshots of
declared paths. Hermetic by default: nothing from the host reaches a
subject unless it is named in ``ambient``. Owned children are reaped
at close. A plant proves it landed.
"""

from __future__ import annotations

import contextlib
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
# hook or a tool reads. PATH is the one host value every world inherits,
# behind its own bin directory, so planted tools shadow real ones.
_ALWAYS_OWN = ("HOME", "TMPDIR", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")


class PlantFailed(AssertionError):
    """The fixture was not what the case claimed to set up: INVALID, not a verdict."""


class World:
    def __init__(self, *, ambient=(), prefix="world-", keep=False):
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
            if name in _ALWAYS_OWN or name == "PATH":
                raise PlantFailed(f"INVALID: {name} is the world's own and cannot be ambient")
        self.keep = keep
        self._children: list[subprocess.Popen] = []
        self._saved_environ: dict[str, str] | None = None
        self._tools = None
        self.closed = False

    # -- the environment -------------------------------------------------

    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """The hermetic environment: the world's own roots, a fixed git
        identity and clock, C locales, and only the ambient names from the
        host. ``extra`` overrides, as the case declares."""
        return hermetic_env(self.home, xdg_state=self.xdg_state, xdg_config=self.xdg_config,
                            xdg_cache=self.xdg_cache, tmp=self.tmp, bin=self.bin,
                            ambient=self.ambient, extra=extra)

    def enter(self) -> World:
        """Patch ``os.environ`` to the world's environment for an
        in-process subject; ``exit`` restores it exactly."""
        if self._saved_environ is None:
            self._saved_environ = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.env())
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
        from .command import run
        argv = ["git", "-c", f"user.name={USER}", "-c", f"user.email={EMAIL}",
                "-c", "commit.gpgsign=false", *args]
        return run(argv, cwd=cwd or self.cwd, env=self.env(), timeout=timeout,
                   expect=0 if check else None)

    # -- watching --------------------------------------------------------

    def watch(self, *paths, ignore=(), tolerate_new=()) -> Watch:
        return Watch(paths, ignore=ignore, tolerate_new=tolerate_new)

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
                 ambient=(), extra: dict[str, str] | None = None) -> dict[str, str]:
    """The hermetic environment for ``home``: the roots (defaulting to the
    XDG layout under ``home`` and ``home``/tmp), the host PATH behind
    ``bin`` when one is given, a fixed git identity and clock, C locales,
    and only the ``ambient`` names from the host. ``extra`` overrides."""
    home = Path(home)
    host_path = os.environ.get("PATH", "/usr/bin:/bin")
    # TMPDIR names a directory that exists: the world's own, or a caller's
    # home/tmp when it has one; a home without one keeps the system default,
    # since a TMPDIR nobody created breaks every mktemp under it.
    if tmp is None and (home / "tmp").is_dir():
        tmp = home / "tmp"
    env = {
        "PATH": (str(bin) + os.pathsep + host_path) if bin is not None else host_path,
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
    path = Path(path)
    if not path.exists():
        return ("absent", ())
    if not path.is_dir():
        return ("other", ())
    return ("dir", tuple(sorted(p.name for p in path.iterdir())))


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
    """A before snapshot of declared paths, compared at the case's end."""

    def __init__(self, paths, *, ignore=(), tolerate_new=()):
        self.paths = [Path(p) for p in paths]
        self.ignore = tuple(ignore)
        self.tolerate_new = tuple(tolerate_new)
        self.before = {str(p): snapshot(p) for p in self.paths}

    def now(self) -> dict:
        return {str(p): snapshot(p) for p in self.paths}

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
