"""Helpers for the U0 plan-gate suite.

The implementation lives at `ops/capabilities/checks/plan_vet.py` and
does not exist when these tests are written. Tests invoke that path as
a subprocess so collection does not import it.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PLAN_VET = REPO / "ops" / "capabilities" / "checks" / "plan_vet.py"
CONTRACTS = REPO / "ops" / "capabilities" / "contracts"
EXAMPLES = CONTRACTS / "examples"
FAULTS = CONTRACTS / "faults"
PLAN_CUE = CONTRACTS / "plan.cue"

PLAN_KEYS = (
    "id",
    "parent",
    "ref",
    "scope",
    "premises",
    "settled",
    "decisions",
    "open",
    "deliverables",
    "gates",
    "units",
    "refusals",
    "discharge",
    "denied",
    "economics",
)

# Named refusals the suite pins. §5's eighteen plus the CUE field names
# §4 step 2 re-issues as plan.<field>, plus extract/definition claims
# the extract-form tests distinguish by Refusal.claim rather than a
# two-letter substring.
PLAN_CLAIMS = (
    "plan.absent-key",
    "plan.bound-prose",
    "plan.decision-multiline",
    "plan.decision-not-new",
    "plan.decision-unratified",
    "plan.definition",
    "plan.deliverables-mismatch",
    "plan.derived-key",
    "plan.drift",
    "plan.extract-duplicate",
    "plan.extract-header",
    "plan.extract-missing",
    "plan.gate-cost",
    "plan.gate-half",
    "plan.leaf-open",
    "plan.premise-empty",
    "plan.premise-tag",
    "plan.ratified_by",
    "plan.reopened",
    "plan.root-parent",
    "plan.scope-drift",
    "plan.scope-oversize",
    "plan.settled-dropped",
    "plan.stage-blocked",
    "plan.stale-parent",
    "plan.status",
    "plan.undelegated",
)

CUE_SKIP_REASON = (
    "cue binary is not on PATH; GitHub-hosted runners do not carry it; "
    "the lane image carries cue 0.14.1"
)

_CLAIM_RE = re.compile(r"plan\.[A-Za-z0-9_-]+")


def skip_without_cue():
    """Only for tests whose correct implementation must invoke cue.

    Raw-presence, extract, drift, plant-proofs, --economics and
    argument-shape refusals must not call this: those are the suite
    that has to fire on the GitHub runner.
    """
    if shutil.which("cue") is None:
        raise unittest.SkipTest(CUE_SKIP_REASON)


def cue_on_path():
    return shutil.which("cue") is not None


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(obj):
    return json.dumps(obj, sort_keys=True, indent=2) + "\n"


def run_plan_vet(*args, cwd=None):
    """Run the plan-gate CLI. A missing file is a failing test, not a skip."""
    return subprocess.run(
        [sys.executable, str(PLAN_VET), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd or REPO,
    )


def combined(proc):
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def claims_in(text):
    return set(_CLAIM_RE.findall(text or ""))


def _resolve(obj, site):
    cur = obj
    for part in site:
        if isinstance(part, int):
            if not isinstance(cur, list) or part >= len(cur) or part < 0:
                raise KeyError(site)
            cur = cur[part]
            continue
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(site)
        cur = cur[part]
    return cur


def _set_at(obj, site, value):
    if not site:
        raise AssertionError("empty site")
    cur = obj
    for part in site[:-1]:
        cur = cur[part]
    cur[site[-1]] = value


def _del_at(obj, site):
    if not site:
        raise AssertionError("empty site")
    cur = obj
    for part in site[:-1]:
        cur = cur[part]
    del cur[site[-1]]


def prove_plant(clean, planted, *, omitted_keys=(), site=None, exclusive=True):
    """The plant landed at the named site, and nowhere else.

    Two properties, because a no-op and a clobber both make the later
    assertion answer a question about nothing; the site is the third,
    because a plant whose anchor moved still looks planted.
    """
    if planted == clean:
        raise AssertionError("plant changed nothing; the fault did not land")
    if not isinstance(planted, dict) or not planted:
        raise AssertionError("plant is not a recognisable JSON object")
    omitted_keys = tuple(omitted_keys)
    if omitted_keys:
        for key in omitted_keys:
            if key not in clean:
                raise AssertionError(
                    f"omitted key {key!r} was not in the clean fixture"
                )
            if key in planted:
                raise AssertionError(f"plant still carries omitted key {key!r}")
        remaining = [key for key in clean if key not in omitted_keys]
        missing = [key for key in remaining if key not in planted]
        if missing:
            raise AssertionError(
                f"plant dropped more than the named keys: {missing}"
            )
    else:
        missing = sorted(set(clean) - set(planted))
        if missing:
            raise AssertionError(f"plant dropped keys {missing}")
    if site is None:
        raise AssertionError(
            "prove_plant requires site=; a site-blind plant-proof "
            "cannot catch a moved anchor"
        )
    site = tuple(site)
    clean_has = True
    planted_has = True
    clean_at = None
    planted_at = None
    try:
        clean_at = copy.deepcopy(_resolve(clean, site))
    except KeyError:
        clean_has = False
    try:
        planted_at = copy.deepcopy(_resolve(planted, site))
    except KeyError:
        planted_has = False
    if clean_has == planted_has and clean_at == planted_at:
        raise AssertionError(f"named site {site} did not change")
    if not exclusive:
        return
    reverted = copy.deepcopy(planted)
    if clean_has and not planted_has:
        _set_at(reverted, site, clean_at)
    elif planted_has and not clean_has:
        _del_at(reverted, site)
    else:
        _set_at(reverted, site, clean_at)
    if reverted != clean:
        raise AssertionError(f"plant changed more than named site {site}")


def assert_refusal(test, proc, claim, *, expected=None, actual=None):
    """The copied Refusal shape, with the named claim as the first failure."""
    text = proc.stderr or ""
    test.assertIn("refused:", text, text)
    test.assertIn(claim, text, text)
    test.assertRegex(text, rf"refused:\s*{re.escape(claim)}")
    test.assertIn("expected", text, text)
    test.assertIn("actual", text, text)
    test.assertIn("needed:", text, text)
    test.assertNotEqual(proc.returncode, 0, text)
    found = claims_in(text)
    extras = found - {claim}
    test.assertEqual(
        extras,
        set(),
        f"{claim} must be the only plan.* claim; also drew {sorted(extras)}",
    )
    if expected is not None:
        test.assertIn(str(expected), text, text)
    if actual is not None:
        test.assertIn(str(actual), text, text)


def expected_change_minutes(plan_id):
    """§3.1 change: summed write.minutes of every *.plan.json under ops/
    whose parent.id is this plan."""
    total = 0
    for path in sorted((REPO / "ops").rglob("*.plan.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        parent = doc.get("parent")
        if not isinstance(parent, dict):
            continue
        if parent.get("id") != plan_id:
            continue
        economics = doc.get("economics") or {}
        write = economics.get("write") or {}
        minutes = write.get("minutes")
        if isinstance(minutes, int):
            total += minutes
    return total


def expected_carry_bytes(md_path, sidecar_path, owner_words):
    """§3.1 carry: bytes of the md, the sidecar and scope.owner_words.

    No dispatch record exists for the example pair, so the files
    themselves are the source. Readers of scope and of inputs are one
    each; the unmultiplied byte total is what --economics must name.
    """
    md_b = Path(md_path).stat().st_size
    js_b = Path(sidecar_path).stat().st_size
    ow_b = len(owner_words.encode("utf-8"))
    return md_b + js_b + ow_b, md_b, js_b, ow_b


# --- U2 registry / anatomy helpers (agentscient-u2-plan.md §§2-7) ---

REGISTRY_VET = REPO / "ops" / "capabilities" / "checks" / "registry_vet.py"
ANATOMY_PY = REPO / "ops" / "capabilities" / "checks" / "anatomy.py"
LIVE_EXPORT = REPO / "ops" / "capabilities" / "capabilities.json"
CAPABILITIES_DIR = REPO / "ops" / "capabilities" / "capabilities"
OUTCOME_CUE = CONTRACTS / "outcome.cue"
CAPABILITIES_CUE = CONTRACTS / "capabilities.cue"
CAPABILITY_CUE = CONTRACTS / "capability.cue"
REGISTRY_EXAMPLE = EXAMPLES / "registry.json"
REGISTRY_EMPTY = EXAMPLES / "registry.empty.json"
GOODCAP = EXAMPLES / "anatomy" / "goodcap"
ARTIFACT_JSON = REPO / "ops" / "devlane" / "workflow" / "gate-kinds" / "artifact.json"
CI_DEV_YML = REPO / ".github" / "workflows" / "ci-dev.yml"

OUTCOME_CLASSES = ("rejection", "denial", "abort", "finding")

REGISTRY_CLAIMS = (
    "registry.absent-key",
    "registry.contract",
    "registry.cue-unreachable",
    "registry.duplicate-id",
    "registry.fault-intact",
    "registry.fault-mismatch",
    "registry.layer",
    "registry.serves-duplicate",
    "registry.stale-export",
    "registry.undemonstrated",
    "registry.unknown-dep",
    "registry.unknown-iface",
)

ANATOMY_CLAIMS = (
    "anatomy.cue-unreachable",
    "anatomy.extra",
    "anatomy.fault-intact",
    "anatomy.fault-mismatch",
    "anatomy.iface-unresolved",
    "anatomy.manifest",
    "anatomy.member-missing",
    "anatomy.member-undeclared",
    "anatomy.migrates-empty",
    "anatomy.missing",
    "anatomy.refusals-disagree",
    "anatomy.undemonstrated",
    "anatomy.unparsed",
)

# Amendment U2-A1 F3: the §3.4(d) carve-out is exactly these two names.
# Nothing else may join. Runner-internal findings (fault-intact, fault-mismatch,
# registry.undemonstrated) are not file-fixture subjects and are not a carve-out.
COVERAGE_CARVE_OUT = frozenset(
    {
        "registry.cue-unreachable",
        "anatomy.cue-unreachable",
    }
)

REGISTRY_RUNNER_CLAIMS = frozenset(
    {
        "registry.cue-unreachable",
        "registry.fault-intact",
        "registry.fault-mismatch",
        "registry.undemonstrated",
    }
)
ANATOMY_RUNNER_CLAIMS = frozenset(
    {
        "anatomy.cue-unreachable",
        "anatomy.fault-intact",
        "anatomy.fault-mismatch",
    }
)

CAPABILITY_KEYS = (
    "id",
    "layer",
    "module",
    "iface",
    "deps",
    "tags",
    "stores",
    "serves",
)
MANIFEST_KEYS = CAPABILITY_KEYS + ("refusals",)
ANATOMY_ENTRIES = (
    "capability.json",
    "CONTRACT.md",
    "contract.cue",
    "tests/",
    "faults/",
    "guide.md",
)
META_FIELDS = ("from", "change", "violates", "reject_path", "site")

_REGISTRY_CLAIM_RE = re.compile(r"registry\.[A-Za-z0-9-]+")
_ANATOMY_CLAIM_RE = re.compile(r"anatomy\.[A-Za-z0-9-]+")
_FAMILY_CLAIM_RE = {
    "registry": _REGISTRY_CLAIM_RE,
    "anatomy": _ANATOMY_CLAIM_RE,
}

VACUOUS_HONESTY = (
    "0 capability directory(ies) scanned — none was looked at"
)


def require_path(test, path, why, *, kind="file"):
    """Missing U2 artifacts are this suite's red, never a skip."""
    path = Path(path)
    if kind == "file":
        ok = path.is_file()
    elif kind == "dir":
        ok = path.is_dir()
    else:
        ok = path.exists()
    test.assertTrue(ok, f"{path} is missing — {why}")
    return path


def load_named(test, path, why):
    require_path(test, path, why, kind="file")
    return load(path)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(obj), encoding="utf-8")
    return path


def run_cli(script, *args, env=None, cwd=None):
    """A missing script is a failing test (nonzero), not a skip."""
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd or REPO,
        env=env,
    )


def run_registry_vet(*args, env=None, cwd=None):
    return run_cli(REGISTRY_VET, *args, env=env, cwd=cwd)


def run_anatomy(*args, env=None, cwd=None):
    return run_cli(ANATOMY_PY, *args, env=env, cwd=cwd)


def path_hiding_cue():
    kept = []
    for part in os.environ.get("PATH", "").split(":"):
        if part and os.path.isfile(os.path.join(part, "cue")):
            continue
        kept.append(part)
    return ":".join(kept)


def env_without_cue():
    env = os.environ.copy()
    env["PATH"] = path_hiding_cue()
    return env


def prove_cue_unreachable(test, env):
    """The plant landed: cue is not findable on this PATH."""
    hidden = shutil.which("cue", path=env.get("PATH", ""))
    test.assertIsNone(
        hidden,
        f"cue still reachable at {hidden}; the unreachable plant did not land",
    )


_DRAWN_CLAIM_LINE_RE = re.compile(r"(?im)^\s*refused:\s*(\S+)")


def family_claims(text, family):
    """Drawn claims: `refused: <name>` lines (Amendment U2-A2).

    Names appearing in expected/actual/needed prose are licensed mentions,
    not extra claims. The undemonstrated tests pass actual= of the missing
    fixture's name; that mention must not fail the sole-claim rule.
    """
    token = _FAMILY_CLAIM_RE[family]
    drawn = set()
    for name in _DRAWN_CLAIM_LINE_RE.findall(text or ""):
        if token.fullmatch(name):
            drawn.add(name)
    return drawn


def assert_u2_refusal(test, proc, claim, *, outcome, expected=None, actual=None):
    """Named refusal, sole claim of its family, with its outcome class."""
    text = combined(proc)
    family = claim.split(".", 1)[0]
    test.assertIn("refused:", text, text)
    test.assertRegex(text, rf"refused:\s*{re.escape(claim)}")
    test.assertIn("expected", text, text)
    test.assertIn("actual", text, text)
    test.assertIn("needed:", text, text)
    test.assertRegex(
        text,
        rf"(?im)^(?:outcome|class):\s*{re.escape(outcome)}\s*$",
        f"{claim} must render outcome class {outcome!r}; output was {text!r}",
    )
    test.assertEqual(
        proc.returncode,
        1,
        f"{claim} must exit 1 (Amendment U2-A1 F11); output was {text!r}",
    )
    extras = family_claims(text, family) - {claim}
    test.assertEqual(
        extras,
        set(),
        f"{claim} must be the only {family}.* claim; also drew {sorted(extras)}",
    )
    if expected is not None:
        test.assertIn(str(expected), text, text)
    if actual is not None:
        test.assertIn(str(actual), text, text)


def assert_not_refused(test, proc, claim):
    """A green run may name a claim in a summary; it must not refuse it."""
    text = combined(proc)
    test.assertIsNone(
        re.search(rf"refused:\s*{re.escape(claim)}", text),
        f"must not draw refused: {claim}; output was {text!r}",
    )


def load_refusal():
    root = str(REPO / "ops" / "capabilities")
    if root not in sys.path:
        sys.path.insert(0, root)
    from container.errors import Refusal

    return Refusal


def rel_files(root):
    root = Path(root)
    out = {}
    for path in root.rglob("*"):
        if path.is_file():
            out[str(path.relative_to(root)).replace("\\", "/")] = path.read_bytes()
    return out


def digest_sidecar(path):
    """Currency digest lives beside the export: `<name>.digest` (U2-A1 F2)."""
    path = Path(path)
    return path.with_name(path.name + ".digest")


def prove_dir_plant(clean_root, planted_root, *, added=(), removed=(), changed=()):
    """The directory plant landed, and only at the named paths."""
    clean = rel_files(clean_root)
    planted = rel_files(planted_root)
    if planted == clean:
        raise AssertionError("plant changed nothing; the fault did not land")
    added = set(added)
    removed = set(removed)
    changed = set(changed)
    actual_added = set(planted) - set(clean)
    actual_removed = set(clean) - set(planted)
    if added and actual_added != added:
        raise AssertionError(
            f"added files {sorted(actual_added)} != named {sorted(added)}"
        )
    if removed and actual_removed != removed:
        raise AssertionError(
            f"removed files {sorted(actual_removed)} != named {sorted(removed)}"
        )
    actual_changed = {
        name
        for name in set(clean) & set(planted)
        if clean[name] != planted[name]
    }
    if changed and actual_changed != changed:
        raise AssertionError(
            f"changed files {sorted(actual_changed)} != named {sorted(changed)}"
        )
    if added or removed or changed:
        unexpected = (actual_added - added) | (actual_removed - removed) | (
            actual_changed - changed
        )
        if unexpected:
            raise AssertionError(
                f"plant changed more than named paths: {sorted(unexpected)}"
            )


def _site_covers(name, site_entry):
    name = name.replace("\\", "/")
    site_entry = str(site_entry).replace("\\", "/").lstrip("./")
    if site_entry.endswith("/"):
        prefix = site_entry.rstrip("/")
        return name == prefix or name.startswith(prefix + "/")
    return name == site_entry


def prove_dir_site(clean_root, planted_root, site):
    """The directory plant landed at meta['site'] paths, and nowhere else.

    Each site entry is a relative file path, or a directory prefix ending in
    `/`. A named entry that covers no actual difference did not land.
    """
    clean = rel_files(clean_root)
    planted = rel_files(planted_root)
    if planted == clean:
        raise AssertionError("plant changed nothing; the fault did not land")
    if isinstance(site, (str, bytes)):
        site = [site]
    site = [str(part) for part in site]
    if not site:
        raise AssertionError("meta site must name the differing path")
    actual_diff = set(planted) - set(clean)
    actual_diff |= set(clean) - set(planted)
    actual_diff |= {
        name
        for name in set(clean) & set(planted)
        if clean[name] != planted[name]
    }
    uncovered = {
        name
        for name in actual_diff
        if not any(_site_covers(name, entry) for entry in site)
    }
    if uncovered:
        raise AssertionError(
            f"plant changed paths not in site {site}: {sorted(uncovered)}"
        )
    for entry in site:
        covered = [name for name in actual_diff if _site_covers(name, entry)]
        if not covered:
            raise AssertionError(f"named site {entry!r} did not change")


def registry_fault_path(n):
    return FAULTS / f"registry.{n}.json"


def registry_meta_path(n):
    return FAULTS / f"registry.{n}.meta.json"


def anatomy_fault_dir(n):
    return FAULTS / f"anatomy.{n}"


def anatomy_meta_path(n):
    return FAULTS / f"anatomy.{n}.meta.json"


def goodcap_module(test, root):
    """Resolve the module file the manifest names, falling back to <id>.py."""
    manifest = load_named(
        test, Path(root) / "capability.json", "goodcap manifest capability.json"
    )
    module_field = manifest["module"]
    candidates = [
        Path(root) / module_field,
        Path(root) / Path(module_field).name,
        Path(root) / f"{manifest['id']}.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate, manifest
    test.fail(
        f"goodcap module {module_field!r} (id={manifest.get('id')!r}) "
        f"is not a file under {root}"
    )


def protocol_class_member_names(source, class_name):
    """Names of methods and annotated attributes on `class_name` in `source`."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            names = set()
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(stmt.name)
                elif isinstance(stmt, ast.AnnAssign) and isinstance(
                    stmt.target, ast.Name
                ):
                    names.add(stmt.target.id)
            return names
    raise AssertionError(f"Protocol class {class_name!r} not in module")


def prove_protocol_members(source, class_name, *members):
    """Planted source still parses, and each named member is on the class."""
    names = protocol_class_member_names(source, class_name)
    missing = [member for member in members if member not in names]
    if missing:
        raise AssertionError(
            f"{missing} not in {class_name} body; have {sorted(names)}"
        )
    return names


def insert_protocol_body(source, class_name, lines, *, members=()):
    """Insert indented lines immediately under `class {class_name}`.

    The rewritten source must still parse, and every name in `members`
    must be a method or annotated attribute on that class.
    """
    pattern = re.compile(rf"^(class {re.escape(class_name)}\b.*)$", re.MULTILINE)
    match = pattern.search(source)
    if not match:
        raise AssertionError(f"Protocol class {class_name!r} not in module")
    indent = "    "
    injected = "".join(indent + line + "\n" for line in lines)
    rewritten = source[: match.end()] + "\n" + injected + source[match.end() :]
    ast.parse(rewritten)
    if members:
        prove_protocol_members(rewritten, class_name, *members)
    return rewritten


def last_declared_iface(test, manifest):
    """Amendment U2-A1 F9: member plants target the last of ≥2 ifaces."""
    ifaces = manifest["iface"]
    test.assertIsInstance(ifaces, list)
    test.assertGreaterEqual(
        len(ifaces),
        2,
        "goodcap declares at least two ifaces (Amendment U2-A1 F9)",
    )
    idx = len(ifaces) - 1
    test.assertGreater(idx, 0, "the last iface must not be the only iface")
    iface = ifaces[idx]
    test.assertTrue(iface["name"], "last iface must be named")
    test.assertTrue(iface["members"], "last iface must declare members")
    return iface, idx


def stage_registry_faults(test, dest, numbers):
    """Copy committed registry faults into a scratch corpus-root."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    numbers = tuple(numbers)
    test.assertTrue(numbers, "stage_registry_faults needs at least one R-row")
    for n in numbers:
        src_json = registry_fault_path(n)
        src_meta = registry_meta_path(n)
        require_path(test, src_json, f"contracts/faults/registry.{n}.json")
        require_path(test, src_meta, f"contracts/faults/registry.{n}.meta.json")
        shutil.copy2(src_json, dest / src_json.name)
        shutil.copy2(src_meta, dest / src_meta.name)
        test.assertEqual(
            (dest / src_json.name).read_bytes(),
            src_json.read_bytes(),
            f"scratch copy of registry.{n}.json must match the committed file",
        )
        digest = digest_sidecar(src_json)
        if digest.is_file():
            shutil.copy2(digest, dest / digest.name)
            test.assertEqual(
                (dest / digest.name).read_bytes(),
                digest.read_bytes(),
            )
    return dest


def stage_anatomy_faults(test, dest, numbers):
    """Copy committed anatomy faults into a scratch corpus-root."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    numbers = tuple(numbers)
    test.assertTrue(numbers, "stage_anatomy_faults needs at least one A-row")
    for n in numbers:
        src_dir = anatomy_fault_dir(n)
        src_meta = anatomy_meta_path(n)
        require_path(
            test,
            src_dir,
            f"contracts/faults/anatomy.{n}/",
            kind="dir",
        )
        require_path(test, src_meta, f"contracts/faults/anatomy.{n}.meta.json")
        shutil.copytree(src_dir, dest / src_dir.name)
        shutil.copy2(src_meta, dest / src_meta.name)
        test.assertEqual(
            rel_files(dest / src_dir.name),
            rel_files(src_dir),
            f"scratch copy of anatomy.{n}/ must match the committed directory",
        )
    return dest

