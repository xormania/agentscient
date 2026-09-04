"""Each open PR is judged against the expected checks of its own head.

The checkout running the overview is not that set. Two PRs in one
collect() with different heads must not share it. A skipped expected
check has reported and is not a pass.

Heads are commits in a throwaway fixture repository. They are never
written into the developer's object store. The expected set for an
unchanged head is derived from HEAD's committed derivation files, not
the working tree. collect() is invoked from a directory that is not a
Git repository; the head tree is served through the gh stub.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_blocking import (
    OVERVIEW,
    ROOT,
    assert_skipped_expected,
    check_registry,
    expected_check_names,
    load_overview,
    one_matrix_check,
)

GATE_KIND = "ops/devlane/workflow/gate-kinds/artifact.json"
CI_DEV = ".github/workflows/ci-dev.yml"
CI_APPS = ".github/workflows/ci-dev-apps.yml"
REPO = "uscient/agentscient"
DERIVATION_PATHS = (".github/workflows", "ops/devlane/workflow")

GH_STUB = r"""#!/usr/bin/env python3
import base64, hashlib, io, json, os, sys, tarfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

state = json.loads(Path(os.environ["GH_STUB_STATE"]).read_text())
args = sys.argv[1:]
prs = state["prs"]
trees = state.get("trees", {})

def git_blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()

blobs = {}
for files in trees.values():
    for text in files.values():
        data = text.encode("utf-8")
        blobs[git_blob_sha(data)] = data

def pr_by_number(n):
    for pr in prs:
        if int(pr["number"]) == int(n):
            return pr
    sys.stderr.write(f"unknown pr {n}\n")
    sys.exit(2)

def dump(obj):
    jq = None
    if "--jq" in args:
        jq = args[args.index("--jq") + 1]
    if jq:
        cur = obj
        for part in jq.strip(".").split("."):
            if part == "":
                continue
            cur = cur[part]
        if isinstance(cur, (dict, list)):
            json.dump(cur, sys.stdout)
        else:
            sys.stdout.write("" if cur is None else str(cur))
    else:
        json.dump(obj, sys.stdout)
    sys.exit(0)

if "pr" in args and "list" in args:
    keys = (
        "number", "title", "headRefName", "baseRefName", "headRefOid",
        "mergeable", "mergeStateStatus", "isDraft", "updatedAt",
    )
    json.dump([{k: pr[k] for k in keys} for pr in prs], sys.stdout)
    sys.exit(0)

if "pr" in args and "checks" in args:
    number = None
    after = args[args.index("checks") + 1 :]
    for a in after:
        if a.isdigit():
            number = a
            break
    if number is None:
        sys.stderr.write("pr checks: no number\n")
        sys.exit(2)
    pr = pr_by_number(number)
    json.dump(
        [{"name": c["name"], "bucket": c["bucket"]} for c in pr["checks"]],
        sys.stdout,
    )
    sys.exit(0)

if "api" in args and "graphql" in args:
    number = None
    for i, a in enumerate(args):
        if a.startswith("pr="):
            number = a.split("=", 1)[1]
        if a == "-F" and i + 1 < len(args) and args[i + 1].startswith("pr="):
            number = args[i + 1].split("=", 1)[1]
    if number is None:
        sys.stderr.write("graphql: no pr=\n")
        sys.exit(2)
    pr = pr_by_number(number)
    json.dump(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [],
                        },
                        "reviews": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{
                                "submittedAt": "2026-08-26T00:00:00Z",
                                "commit": {"oid": pr["headRefOid"]},
                                "author": {"login": "reviewer"},
                                "state": "APPROVED",
                                "body": "lgtm",
                            }],
                        },
                    }
                }
            }
        },
        sys.stdout,
    )
    sys.exit(0)

def api_token():
    for a in args:
        if a.startswith("repos/") or a.startswith("/repos/"):
            return a
    return None

token = api_token() if "api" in args else None
if token:
    parsed = urlparse(token if "://" in token else "https://api.github.com/" + token.lstrip("/"))
    path = parsed.path.lstrip("/")
    qs = parse_qs(parsed.query)
    for i, a in enumerate(args):
        if a in ("-f", "-F") and i + 1 < len(args) and "=" in args[i + 1]:
            k, v = args[i + 1].split("=", 1)
            qs.setdefault(k, []).append(v)
        if a.startswith("ref="):
            qs.setdefault("ref", []).append(a.split("=", 1)[1])
    parts = path.split("/")
    if parts and parts[0] == "repos":
        rest = parts[3:]
    else:
        rest = parts

    def die(msg, code=1):
        sys.stderr.write(msg + "\n")
        sys.exit(code)

    def tree_files(sha):
        files = trees.get(sha)
        if files is None:
            die(f"no tree {sha}", 1)
        return files

    if rest[:2] == ["git", "trees"] and len(rest) >= 3:
        sha = rest[2]
        files = tree_files(sha)
        tree = []
        for p, text in sorted(files.items()):
            data = text.encode("utf-8")
            tree.append({
                "path": p,
                "mode": "100644",
                "type": "blob",
                "sha": git_blob_sha(data),
                "size": len(data),
            })
        dump({"sha": sha, "tree": tree, "truncated": False})

    if rest[:2] == ["git", "blobs"] and len(rest) >= 3:
        bsha = rest[2]
        data = blobs.get(bsha)
        if data is None:
            die(f"no blob {bsha}", 1)
        dump({
            "sha": bsha,
            "content": base64.b64encode(data).decode("ascii"),
            "encoding": "base64",
            "size": len(data),
        })

    if rest[:2] == ["git", "commits"] and len(rest) >= 3:
        sha = rest[2]
        tree_files(sha)
        dump({"sha": sha, "tree": {"sha": sha}})

    if rest[:1] == ["tarball"] and len(rest) >= 2:
        sha = rest[1]
        files = tree_files(sha)
        buf = io.BytesIO()
        prefix = f"agentscient-{sha[:7]}/"
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for p, text in files.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo(name=prefix + p)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        sys.stdout.buffer.write(buf.getvalue())
        sys.exit(0)

    if rest[:1] == ["contents"]:
        rel = "/".join(rest[1:])
        ref = (qs.get("ref") or [None])[0]
        if not ref:
            die("contents: no ref", 2)
        files = tree_files(ref)
        if rel in files:
            data = files[rel].encode("utf-8")
            dump({
                "name": rel.rsplit("/", 1)[-1],
                "path": rel,
                "sha": git_blob_sha(data),
                "size": len(data),
                "type": "file",
                "content": base64.b64encode(data).decode("ascii"),
                "encoding": "base64",
            })
        prefix = (rel.rstrip("/") + "/") if rel else ""
        names = {}
        for p in files:
            if prefix and not p.startswith(prefix):
                continue
            rest_p = p[len(prefix):] if prefix else p
            if not rest_p:
                continue
            first = rest_p.split("/", 1)[0]
            names[first] = "/" not in rest_p
        if not names:
            die(f"no content {rel}", 1)
        listing = []
        for name in sorted(names):
            full = prefix + name
            if names[name]:
                data = files[full].encode("utf-8")
                listing.append({
                    "name": name,
                    "path": full,
                    "type": "file",
                    "sha": git_blob_sha(data),
                    "size": len(data),
                })
            else:
                listing.append({
                    "name": name,
                    "path": full,
                    "type": "dir",
                    "sha": "0" * 40,
                })
        dump(listing)

sys.stderr.write("stub gh: unhandled " + " ".join(args[:6]) + "\n")
sys.exit(2)
"""


def ready_text(n: int) -> str:
    return f"ready to merge — all {n} expected check(s) passed"


def incomplete_text(missing: set[str], expected_n: int) -> str:
    return (
        f"checks incomplete — {len(missing)} of {expected_n} "
        f"expected not reported: {', '.join(sorted(missing))} "
        f"(still registering, or never ran)"
    )


def plant_bytes(path: Path, new: bytes, *, still_contains: bytes) -> None:
    before = path.read_bytes()
    before_sum = hashlib.sha256(before).hexdigest()
    if not before:
        raise AssertionError(f"fixture empty before plant: {path}")
    path.write_bytes(new)
    after = path.read_bytes()
    after_sum = hashlib.sha256(after).hexdigest()
    if after_sum == before_sum:
        raise AssertionError(f"plant was a no-op: {path}")
    if not after:
        raise AssertionError(f"plant clobbered the file empty: {path}")
    if still_contains not in after:
        raise AssertionError(f"plant destroyed fixture identity: {path}")
    if after != new:
        raise AssertionError(f"plant did not write the intended bytes: {path}")


def _clean_git_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(key, None)
    env["GIT_AUTHOR_NAME"] = "testr"
    env["GIT_AUTHOR_EMAIL"] = "t@t.test"
    env["GIT_COMMITTER_NAME"] = "testr"
    env["GIT_COMMITTER_EMAIL"] = "t@t.test"
    return env


def prove_absent_from_developer_repo(sha: str) -> None:
    proc = subprocess.run(
        ["git", "cat-file", "-t", sha],
        cwd=ROOT,
        env=_clean_git_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        raise AssertionError(
            f"planted {sha} leaked into the developer object store "
            f"({proc.stdout.strip()})"
        )


def head_derivation_tree() -> Path:
    """Derivation files from HEAD, not the working tree."""
    dest = Path(tempfile.mkdtemp(prefix="pr-overview-tree-"))
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", "HEAD", "--", *DERIVATION_PATHS],
        cwd=ROOT,
        env=_clean_git_env(),
    )
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    for rel in (GATE_KIND, CI_DEV, CI_APPS):
        path = dest / rel
        if not path.is_file():
            raise AssertionError(f"HEAD archive missing {rel}")
        from_head = subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"],
            cwd=ROOT,
            env=_clean_git_env(),
        )
        if path.read_bytes() != from_head:
            raise AssertionError(f"{rel} export does not match HEAD")
    return dest


def git_commit_tree(tree: Path, message: str) -> str:
    env = _clean_git_env()
    for pycache in tree.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    for pyc in tree.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "fixture"],
        cwd=tree,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "add", "-A", "--", ".github", ".dev"],
        cwd=tree,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=testr",
            "-c",
            "user.email=t@t.test",
            "commit",
            "-qm",
            message,
        ],
        cwd=tree,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=tree,
        env=env,
        text=True,
    ).strip()
    if len(sha) != 40:
        raise AssertionError(f"planted commit sha looks wrong: {sha!r}")
    prove_absent_from_developer_repo(sha)
    return sha


def snapshot_repo(tree: Path, sha: str) -> dict[str, str]:
    env = _clean_git_env()
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", sha],
        cwd=tree,
        env=env,
        text=True,
    ).splitlines()
    out = {}
    for rel in names:
        if "__pycache__" in rel.split("/") or rel.endswith(".pyc"):
            continue
        data = subprocess.check_output(
            ["git", "show", f"{sha}:{rel}"],
            cwd=tree,
            env=env,
        )
        try:
            out[rel] = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AssertionError(f"{sha}:{rel} is not utf-8 ({exc})") from exc
    if not out:
        raise AssertionError(f"{sha} snapshot is empty")
    return out


def prove_git_file(repo: Path, sha: str, rel: str, data: bytes) -> None:
    shown = subprocess.check_output(
        ["git", "show", f"{sha}:{rel}"],
        cwd=repo,
        env=_clean_git_env(),
    )
    if shown != data:
        raise AssertionError(f"{sha}:{rel} does not match the planted bytes")


def prove_git_missing(repo: Path, sha: str, rel: str, sibling: str) -> None:
    names = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", sha],
        cwd=repo,
        env=_clean_git_env(),
        text=True,
    ).splitlines()
    if rel in names:
        raise AssertionError(f"{rel} still in {sha}")
    if sibling not in names:
        raise AssertionError(f"sibling {sibling} missing from {sha}")


def install_overview_script(copied: Path) -> None:
    dest = copied / OVERVIEW.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OVERVIEW, dest)
    if dest.read_bytes() != OVERVIEW.read_bytes():
        raise AssertionError("overview script copy did not land intact")


def registry_payload(tree_root: Path, *, add=(), ci_false=()) -> bytes:
    payload = json.loads((tree_root / GATE_KIND).read_text(encoding="utf-8"))
    present = [entry["name"] for entry in payload["checks"]]
    for name in add:
        if name in present:
            raise AssertionError(f"{name} already in the registry")
        payload["checks"].append(
            {
                "name": name,
                "class": "policy",
                "argv": ["python3", "-c", "raise SystemExit(0)"],
                "ci": True,
            }
        )
    found = set()
    for entry in payload["checks"]:
        if entry["name"] in ci_false:
            if entry.get("ci") is not True:
                raise AssertionError(f"{entry['name']} ci was not True")
            entry["ci"] = False
            found.add(entry["name"])
    missing = set(ci_false) - found
    if missing:
        raise AssertionError(f"registry missing {sorted(missing)}")
    return (json.dumps(payload, indent=2) + "\n").encode()


def verify_renamed_workflow(tree_root: Path) -> bytes:
    text = (tree_root / CI_DEV).read_text(encoding="utf-8")
    old, new = '"dev: verify"', '"dev: verify-late"'
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"expected one {old} in {CI_DEV}, found {count}")
    return text.replace(old, new, 1).encode()


def ready_pr(number, title, branch, oid, names, buckets=None):
    buckets = buckets or {name: "pass" for name in names}
    return {
        "number": number,
        "title": title,
        "headRefName": branch,
        "baseRefName": "dev",
        "headRefOid": oid,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "updatedAt": "2026-08-26T12:00:00Z",
        "checks": [{"name": name, "bucket": buckets[name]} for name in names],
    }


@contextlib.contextmanager
def gh_on_path(prs: list[dict], trees: dict[str, dict[str, str]]):
    tmp = Path(tempfile.mkdtemp(prefix="pr-overview-gh-"))
    state = tmp / "state.json"
    stub = tmp / "gh"
    missing = [pr["headRefOid"] for pr in prs if pr["headRefOid"] not in trees]
    if missing:
        raise AssertionError(f"gh stub has no tree for head(s) {missing}")
    state.write_text(json.dumps({"prs": prs, "trees": trees}), encoding="utf-8")
    stub.write_text(GH_STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    old_path = os.environ["PATH"]
    old_state = os.environ.get("GH_STUB_STATE")
    os.environ["PATH"] = str(tmp) + os.pathsep + old_path
    os.environ["GH_STUB_STATE"] = str(state)
    try:
        which = shutil.which("gh")
        if which is None or Path(which).resolve() != stub.resolve():
            raise AssertionError(f"stub gh not first on PATH: {which}")
        yield
    finally:
        os.environ["PATH"] = old_path
        if old_state is None:
            os.environ.pop("GH_STUB_STATE", None)
        else:
            os.environ["GH_STUB_STATE"] = old_state
        shutil.rmtree(tmp, ignore_errors=True)


@contextlib.contextmanager
def non_git_cwd():
    tmp = Path(tempfile.mkdtemp(prefix="pr-overview-cwd-"))
    old = os.getcwd()
    try:
        os.chdir(tmp)
        probe = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            env=_clean_git_env(),
            check=False,
        )
        if probe.returncode == 0:
            raise AssertionError(
                f"collect cwd is a git repo: {probe.stdout.strip()}"
            )
        yield tmp
    finally:
        os.chdir(old)
        shutil.rmtree(tmp, ignore_errors=True)


def row_by_number(rows, number: int) -> dict:
    if not rows:
        raise AssertionError("collect returned no rows")
    matched = [row for row in rows if int(row["number"]) == number]
    if len(matched) != 1:
        raise AssertionError(
            f"expected one row for #{number}, got {len(matched)} from "
            f"{[row.get('number') for row in rows]}"
        )
    return matched[0]


def assert_checks_line_is_bucket_summary(testcase, rendered: str) -> None:
    lines = [line for line in rendered.splitlines() if "checks:" in line]
    testcase.assertTrue(lines, f"no checks line in:\n{rendered}")
    for line in lines:
        testcase.assertNotIn("runs=", line, line)
        testcase.assertNotIn("{'name':", line, line)
        testcase.assertIn("pass=", line, line)


class CollectJudgesEachPrAgainstItsOwnHead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overview = load_overview(ROOT, "pr_overview_head_under_test")
        cls.temps = []
        cls.trees = {}
        cls.baseline_root = head_derivation_tree()
        cls.temps.append(cls.baseline_root)
        cls.caller = expected_check_names(cls.baseline_root)
        if len(cls.caller) < 3:
            raise AssertionError(f"caller expected set too small: {cls.caller}")
        cls.baseline_sha = git_commit_tree(
            cls.baseline_root, "baseline HEAD derivation"
        )
        cls.trees[cls.baseline_sha] = snapshot_repo(
            cls.baseline_root, cls.baseline_sha
        )
        cls.add_one = cls._registry_case(
            add=("late-added",),
            message="plant one registry check",
        )
        cls.add_two = cls._registry_case(
            add=("late-added", "late-added-2"),
            message="plant two registry checks",
        )
        cls.remove = cls._registry_case(
            ci_false=("vocabulary-wall",),
            message="plant vocabulary-wall ci false",
        )
        cls.rename = cls._registry_case(
            add=("late-added",),
            ci_false=("vocabulary-wall",),
            message="plant same-count registry rename",
        )
        cls.workflow = cls._workflow_rename_case()
        cls.unreadable = cls._unreadable_case()
        cls.planted_shas = [
            cls.baseline_sha,
            cls.add_one["sha"],
            cls.add_two["sha"],
            cls.remove["sha"],
            cls.rename["sha"],
            cls.workflow["sha"],
            cls.unreadable["sha"],
        ]
        for sha in cls.planted_shas:
            prove_absent_from_developer_repo(sha)

    @classmethod
    def tearDownClass(cls):
        for path in getattr(cls, "temps", []):
            shutil.rmtree(path, ignore_errors=True)

    @classmethod
    def _registry_case(cls, *, add=(), ci_false=(), message=""):
        root = head_derivation_tree()
        cls.temps.append(root)
        data = registry_payload(root, add=add, ci_false=ci_false)
        path = root / GATE_KIND
        still = b"vocabulary-wall"
        plant_bytes(path, data, still_contains=still)
        after = expected_check_names(root)
        added = after - cls.caller
        removed = cls.caller - after
        if add and len(added) != len(set(add)):
            raise AssertionError(
                f"expected {len(set(add))} added contexts, got {sorted(added)}"
            )
        for name in add:
            if not any(name in context for context in added):
                raise AssertionError(f"{name} not in added contexts {sorted(added)}")
        sha = git_commit_tree(root, message)
        prove_git_file(root, sha, GATE_KIND, data)
        cls.trees[sha] = snapshot_repo(root, sha)
        return {
            "root": root,
            "sha": sha,
            "expected": after,
            "added": added,
            "removed": removed,
        }

    @classmethod
    def _workflow_rename_case(cls):
        root = head_derivation_tree()
        cls.temps.append(root)
        data = verify_renamed_workflow(root)
        plant_bytes(
            root / CI_DEV,
            data,
            still_contains=b"dev: discover",
        )
        after = expected_check_names(root)
        added = after - cls.caller
        removed = cls.caller - after
        if added != {"dev: verify-late"} or removed != {"dev: verify"}:
            raise AssertionError(
                f"workflow rename added {sorted(added)} removed {sorted(removed)}"
            )
        sha = git_commit_tree(root, "plant verify rename")
        prove_git_file(root, sha, CI_DEV, data)
        cls.trees[sha] = snapshot_repo(root, sha)
        return {
            "root": root,
            "sha": sha,
            "expected": after,
            "added": added,
            "removed": removed,
        }

    @classmethod
    def _unreadable_case(cls):
        root = head_derivation_tree()
        cls.temps.append(root)
        path = root / CI_DEV
        before = path.read_bytes()
        if b"dev: verify" not in before:
            raise AssertionError("ci-dev.yml fixture missing dev: verify")
        path.unlink()
        if path.exists():
            raise AssertionError("failed to remove ci-dev.yml from the plant")
        if not (root / CI_APPS).exists():
            raise AssertionError("plant destroyed the sibling workflow")
        sha = git_commit_tree(root, "plant missing ci-dev.yml")
        prove_git_missing(root, sha, CI_DEV, CI_APPS)
        cls.trees[sha] = snapshot_repo(root, sha)
        if CI_DEV in cls.trees[sha]:
            raise AssertionError("unreadable snapshot still has ci-dev.yml")
        return {"root": root, "sha": sha}

    def collect(self, prs, overview=None):
        overview = self.overview if overview is None else overview
        with gh_on_path(prs, self.trees), non_git_cwd():
            return overview.collect(REPO)

    def test_an_unreported_check_added_on_the_pr_head_is_incomplete(self):
        case = self.add_one
        self.assertEqual(len(case["added"]), 1)
        added = next(iter(case["added"]))
        rows = self.collect(
            [
                ready_pr(
                    101,
                    "adds a registry check",
                    "repo/adds-check",
                    case["sha"],
                    sorted(self.caller),
                )
            ]
        )
        row = row_by_number(rows, 101)
        self.assertEqual(
            row["blocking"],
            incomplete_text({added}, len(case["expected"])),
        )

    def test_a_pr_head_that_adds_a_check_is_ready_on_the_head_set(self):
        case = self.add_one
        self.assertEqual(len(case["expected"]), len(self.caller) + 1)
        rows = self.collect(
            [
                ready_pr(
                    101,
                    "adds a registry check",
                    "repo/adds-check",
                    case["sha"],
                    sorted(case["expected"]),
                )
            ]
        )
        row = row_by_number(rows, 101)
        self.assertEqual(row["blocking"], ready_text(len(case["expected"])))
        self.assertNotEqual(row["blocking"], ready_text(len(self.caller)))

    def test_a_pr_head_that_removes_a_check_is_ready_without_the_removed_name(self):
        case = self.remove
        self.assertEqual(case["removed"], {"dev: gates (vocabulary-wall)"})
        self.assertEqual(len(case["expected"]), len(self.caller) - 1)
        rows = self.collect(
            [
                ready_pr(
                    102,
                    "removes a registry check",
                    "repo/removes-check",
                    case["sha"],
                    sorted(case["expected"]),
                )
            ]
        )
        row = row_by_number(rows, 102)
        self.assertEqual(row["blocking"], ready_text(len(case["expected"])))
        self.assertNotIn("vocabulary-wall", row["blocking"])

    def test_two_prs_with_the_same_reported_names_use_their_own_heads(self):
        """gh lists the same names for both; the expected sets still differ."""
        added = self.add_one["added"]
        self.assertEqual(len(added), 1)
        reported = sorted(self.caller)
        rows = self.collect(
            [
                ready_pr(
                    101,
                    "adds a registry check",
                    "repo/adds-check",
                    self.add_one["sha"],
                    reported,
                ),
                ready_pr(
                    102,
                    "unchanged head",
                    "repo/unchanged",
                    self.baseline_sha,
                    reported,
                ),
            ]
        )
        add_row = row_by_number(rows, 101)
        stay_row = row_by_number(rows, 102)
        self.assertEqual(
            add_row["blocking"],
            incomplete_text(added, len(self.add_one["expected"])),
        )
        self.assertEqual(stay_row["blocking"], ready_text(len(self.caller)))
        self.assertNotEqual(add_row["blocking"], stay_row["blocking"])

    def test_two_checks_added_on_the_head_one_unreported_is_incomplete(self):
        case = self.add_two
        self.assertEqual(len(case["added"]), 2)
        reported_new = "dev: gates (late-added)"
        still_missing = {"dev: gates (late-added-2)"}
        self.assertIn(reported_new, case["added"])
        self.assertEqual(case["added"] - {reported_new}, still_missing)
        reported = sorted(self.caller | {reported_new})
        rows = self.collect(
            [
                ready_pr(
                    104,
                    "adds two registry checks",
                    "repo/adds-two",
                    case["sha"],
                    reported,
                )
            ]
        )
        row = row_by_number(rows, 104)
        self.assertEqual(
            row["blocking"],
            incomplete_text(still_missing, len(case["expected"])),
        )

    def test_a_same_count_rename_on_the_pr_head_is_ready(self):
        case = self.rename
        self.assertEqual(len(case["expected"]), len(self.caller))
        self.assertEqual(len(case["added"]), 1)
        self.assertEqual(len(case["removed"]), 1)
        self.assertNotEqual(case["expected"], self.caller)
        rows = self.collect(
            [
                ready_pr(
                    105,
                    "renames a registry check",
                    "repo/rename-check",
                    case["sha"],
                    sorted(case["expected"]),
                )
            ]
        )
        row = row_by_number(rows, 105)
        self.assertEqual(row["blocking"], ready_text(len(case["expected"])))
        self.assertNotIn("dev: gates (vocabulary-wall)", row["blocking"])

    def test_a_same_count_wrong_reported_set_on_the_head_is_incomplete(self):
        replaced = "dev: contracts"
        wrong = "wrong-same-count"
        self.assertIn(replaced, self.caller)
        self.assertNotIn(wrong, self.caller)
        reported = sorted((self.caller - {replaced}) | {wrong})
        self.assertEqual(len(reported), len(self.caller), "the plant must preserve the count")
        self.assertNotEqual(set(reported), self.caller, "the plant must change the names")
        rows = self.collect(
            [
                ready_pr(
                    111,
                    "same-count wrong names",
                    "repo/count-only",
                    self.baseline_sha,
                    reported,
                )
            ]
        )
        row = row_by_number(rows, 111)
        self.assertEqual(
            row["blocking"],
            incomplete_text({replaced}, len(self.caller)),
        )

    def test_a_same_count_rename_is_incomplete_while_github_still_reports_the_old_names(
        self,
    ):
        case = self.rename
        self.assertEqual(len(case["expected"]), len(self.caller))
        self.assertNotEqual(case["expected"], self.caller)
        rows = self.collect(
            [
                ready_pr(
                    112,
                    "rename not yet reported",
                    "repo/rename-stale-report",
                    case["sha"],
                    sorted(self.caller),
                )
            ]
        )
        row = row_by_number(rows, 112)
        self.assertEqual(
            row["blocking"],
            incomplete_text(case["added"], len(case["expected"])),
        )

    def test_a_workflow_job_rename_on_the_pr_head_is_ready(self):
        case = self.workflow
        self.assertEqual(case["removed"], {"dev: verify"})
        self.assertEqual(case["added"], {"dev: verify-late"})
        rows = self.collect(
            [
                ready_pr(
                    106,
                    "renames a workflow job",
                    "repo/rename-job",
                    case["sha"],
                    sorted(case["expected"]),
                )
            ]
        )
        row = row_by_number(rows, 106)
        self.assertEqual(row["blocking"], ready_text(len(case["expected"])))
        self.assertNotIn("dev: verify —", row["blocking"])
        self.assertNotIn("not reported: dev: verify", row["blocking"])

    def test_an_unreadable_pr_head_is_cannot_tell(self):
        rows = self.collect(
            [
                ready_pr(
                    107,
                    "broken workflow tree",
                    "repo/broken-head",
                    self.unreadable["sha"],
                    sorted(self.caller),
                )
            ]
        )
        row = row_by_number(rows, 107)
        self.assertTrue(
            row["blocking"].startswith("cannot tell"),
            row["blocking"],
        )
        self.assertNotEqual(row["blocking"], ready_text(len(self.caller)))

    def test_running_from_a_branch_that_added_a_check_does_not_impose_it_on_other_prs(
        self,
    ):
        copied = head_derivation_tree()
        self.addCleanup(shutil.rmtree, copied, True)
        data = registry_payload(copied, add=("late-added",))
        plant_bytes(copied / GATE_KIND, data, still_contains=b"vocabulary-wall")
        install_overview_script(copied)
        self.assertFalse(
            (copied / ".git").exists(),
            "copied ROOT must not supply a local object store",
        )
        branch_overview = load_overview(copied, "pr_overview_from_add_branch")
        self.assertEqual(Path(branch_overview.ROOT).resolve(), copied.resolve())
        branch_expected = expected_check_names(copied)
        self.assertEqual(len(branch_expected), len(self.caller) + 1)

        rows = self.collect(
            [
                ready_pr(
                    108,
                    "unrelated pr still on the previous set",
                    "repo/unrelated",
                    self.baseline_sha,
                    sorted(self.caller),
                )
            ],
            overview=branch_overview,
        )
        row = row_by_number(rows, 108)
        self.assertEqual(row["blocking"], ready_text(len(self.caller)))
        self.assertNotIn("late-added", row["blocking"])

    def test_collect_does_not_report_a_skipped_expected_check_as_passed(self):
        skip_name = "dev: gates (lint)"
        self.assertIn(skip_name, self.caller)
        buckets = {name: "pass" for name in self.caller}
        buckets[skip_name] = "skipping"
        rows = self.collect(
            [
                ready_pr(
                    103,
                    "a skipped expected check",
                    "repo/skipping",
                    self.baseline_sha,
                    sorted(self.caller),
                    buckets,
                )
            ]
        )
        row = row_by_number(rows, 103)
        self.assertEqual(row["checks"].get("skipping"), 1)
        self.assertIn(skip_name, row["checks"]["names"])
        assert_skipped_expected(self, row["blocking"], {skip_name})
        rendered = self.overview.render(rows, REPO)
        self.assertIn("skipping=1", rendered)
        self.assertNotIn(">> ready to merge", rendered)
        assert_checks_line_is_bucket_summary(self, rendered)

    def test_a_skipped_extra_check_does_not_block_when_every_expected_check_passed(self):
        extra = "unrelated-extra"
        self.assertNotIn(extra, self.caller)
        names = sorted(self.caller) + [extra]
        buckets = {name: "pass" for name in self.caller}
        buckets[extra] = "skipping"
        rows = self.collect(
            [
                ready_pr(
                    109,
                    "skipped extra",
                    "repo/skip-extra",
                    self.baseline_sha,
                    names,
                    buckets,
                )
            ]
        )
        row = row_by_number(rows, 109)
        self.assertEqual(row["checks"].get("skipping"), 1)
        self.assertEqual(row["blocking"], ready_text(len(self.caller)))

    def test_an_extra_pass_cannot_cover_a_skipped_expected_check(self):
        skip_name = "dev: gates (lint)"
        extra = "unrelated-extra"
        self.assertIn(skip_name, self.caller)
        self.assertNotIn(extra, self.caller)
        names = sorted(self.caller) + [extra]
        buckets = {name: "pass" for name in self.caller}
        buckets[skip_name] = "skipping"
        buckets[extra] = "pass"
        self.assertEqual(
            sum(1 for name in self.caller if buckets[name] == "pass"),
            len(self.caller) - 1,
        )
        rows = self.collect(
            [
                ready_pr(
                    110,
                    "skip plus extra pass",
                    "repo/skip-plus-extra",
                    self.baseline_sha,
                    names,
                    buckets,
                )
            ]
        )
        row = row_by_number(rows, 110)
        self.assertEqual(row["checks"].get("pass"), len(self.caller))
        self.assertEqual(row["checks"].get("skipping"), 1)
        self.assertEqual(len(row["checks"]["names"]), len(self.caller) + 1)
        assert_skipped_expected(self, row["blocking"], {skip_name})

    def test_skipping_is_not_ready_across_workflow_matrix_and_extra_names(self):
        registry = check_registry(self.baseline_root)
        matrix = one_matrix_check(self.caller, registry)
        extra = "unrelated-extra"
        workflow = "dev: verify"
        self.assertIn(workflow, self.caller)
        self.assertIn(matrix, self.caller)
        self.assertNotEqual(matrix, "dev: gates (lint)")
        self.assertNotIn(extra, self.caller)

        cases = (
            (120, workflow, False),
            (121, matrix, False),
            (122, extra, True),
        )
        for number, skip_name, ready in cases:
            with self.subTest(skip_name=skip_name):
                names = sorted(self.caller) + ([extra] if skip_name == extra else [])
                buckets = {name: "pass" for name in self.caller}
                if skip_name == extra:
                    buckets[extra] = "skipping"
                else:
                    buckets[skip_name] = "skipping"
                self.assertEqual(buckets[skip_name], "skipping")
                rows = self.collect(
                    [
                        ready_pr(
                            number,
                            f"skip {skip_name}",
                            f"repo/skip-{number}",
                            self.baseline_sha,
                            names,
                            buckets,
                        )
                    ]
                )
                row = row_by_number(rows, number)
                if ready:
                    self.assertEqual(row["blocking"], ready_text(len(self.caller)))
                else:
                    assert_skipped_expected(self, row["blocking"], {skip_name})

    def test_render_checks_line_stays_a_bucket_summary_when_runs_are_present(self):
        extra = "unrelated-extra"
        names = sorted(self.caller) + [extra]
        buckets = {name: "pass" for name in self.caller}
        buckets[extra] = "skipping"
        rows = self.collect(
            [
                ready_pr(
                    130,
                    "runs must not leak into the checks line",
                    "repo/render-runs",
                    self.baseline_sha,
                    names,
                    buckets,
                )
            ]
        )
        row = row_by_number(rows, 130)
        self.assertEqual(row["blocking"], ready_text(len(self.caller)))
        row["checks"]["runs"] = [
            {"name": name, "bucket": buckets[name]} for name in names
        ]
        self.assertEqual(len(row["checks"]["runs"]), len(names))
        self.assertTrue(any(run["bucket"] == "skipping" for run in row["checks"]["runs"]))
        rendered = self.overview.render(rows, REPO)
        self.assertIn("skipping=1", rendered)
        assert_checks_line_is_bucket_summary(self, rendered)


if __name__ == "__main__":
    unittest.main()
