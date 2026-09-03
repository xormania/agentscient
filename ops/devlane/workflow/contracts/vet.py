#!/usr/bin/env python3
"""THE one command (plan SPEC section 6).

    python3 ops/devlane/workflow/contracts/vet.py

Runs every extractor into obs/, vets every CUE contract against its example,
its observation and its faults, writes a packet for every uncovered
disagreement, validates the verdicts, and regenerates REPORT.json and
FINDINGS.md.  Standard library plus the `cue` binary; no network.

Exit 0 iff all of section 6 step 6 holds:
  * every extractor ran;
  * every examples/<name>.json passes its contract (positive control);
  * every obs/<name>.json passes, or every error line it produces is covered
    by a valid verdicts/<id>.json;
  * every contract has at least two faults and every fault fires;
  * determinism holds.
Otherwise exit 1 and list what is missing.

Nothing here is allowed to pass by absence.  A step that could not be run
records {"unresolved": "<why>"} in REPORT.json and fails the gate; it never
reports success for a check that did not happen.  In particular: zero
contracts is a failure, not a clean sweep.

Sections 9 and 10 of the plan are NOT part of the SPEC excerpt this file was
written against.  Everything they govern -- the full packet layout, the full
verdict schema beyond the three properties section 6 step 4 names, and the
standing findings section 10 contributes -- is emitted as an explicit
unresolved marker rather than invented.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)

# SPEC section 4, "Name -> definition map (fixed)".
NAME_TO_DEF = {
    "schema": "#Schema",
    "db": "#Db",
    "gatekinds": "#GateKinds",
    "meta": "#Meta",
    "layout": "#Layout",
    "cli": "#Cli",
    "exitcodes": "#ExitCodes",
    "canonical": "#Canonical",
    "events": "#Events",
    "commitmsg": "#CommitMsg",
    "mcp": "#Mcp",
    "vocab": "#Vocab",
}

# Section 9 of the plan is the arbiter for the verdict schema, and it
# names FIVE values. This tooling originally accepted three, because the
# snapshot it was written in held sections 4-6 and not section 9 -- and
# section 6 step 4 says "Validate every verdicts/<id>.json (SS9)", a
# reference to material that was not supplied. The three it did accept
# come from step 5, which lists the verdicts that produce OWNER-FACING
# FINDINGS; contract-wrong and extraction-wrong route to remediation
# instead and never reach FINDINGS.md. Mistaking the findings list for
# the enum was a reasonable inference from an under-supplied brief, and
# wrong: it rejected 12 of the adjudicator's 25 verdicts, including all
# five extraction-wrong ones -- the category that exists precisely so an
# extractor bug is not misfiled as a code fault.
VERDICT_VALUES = ("doc-wrong", "code-wrong", "contract-wrong",
                  "extraction-wrong", "ambiguous")

# Section 9 names this field `because`. Section 6 step 4 calls it
# "required citations" in prose, and this tooling took the prose word as
# the field name. Both spellings are read, because the disagreement is
# worth keeping visible rather than smoothing away.
CITATION_FIELDS = ("because", "citations")

#: Section 9 WAS absent from the excerpt this tooling was written
#: against, and the constant that said so has been carried ever since --
#: which made it a false claim the moment the whole plan was committed to
#: reports/PLAN.md. Section 9 gives the verdict schema outright, so it is
#: checked rather than noted (Codex, PR #46).
SECTION_9_ABSENT = None

#: Why a positive control could not be built, per contract. An example
#: invented to make a control pass tests nothing, so the reviser was
#: told to refuse rather than guess -- and refusing has to be RECORDED,
#: or the next reader cannot tell it from an oversight.
UNBUILT_EXAMPLES = {
    "gatekinds": "PLAN.md illustrates the `tdd` spec in full but never gives "
                 "the seeded `artifact` kind's version, scopes, checks, or "
                 "outcome-to-stage mapping",
    "meta": "PLAN.md names a format version in meta.json and supplies no key, "
            "no value, no type and no byte count",
}

#: PLAN.md section 9, lines 458-471. Every field the schema names, and
#: the one conditional rule it states in prose.
VERDICT_REQUIRED = ("id", "verdict", "rule", "observed", "action")
ACTION_VALUES = ("amend-contract", "amend-extractor", "record-finding",
                 "needs-more-context")
#: "`ambiguous` requires `action: record-finding` and goes to the owner."
ACTION_FOR = {"ambiguous": "record-finding"}
#: Section 9 line 475, verbatim: "`vet.py` enforces: `because` has >=1
#: PLAN.md citation and >=1 citation of the observation or a source
#: file". The tool's name is in the sentence and it was not enforcing
#: it: the loop read every entry's `quote` and never once looked at its
#: `artifact`, so a verdict resting entirely on PLAN.md -- or entirely
#: on the observation -- was accepted and could cover a real mismatch
#: (Codex, PR #46).
PLAN_ARTIFACT = "PLAN.md"


def citation_side(artifact):
    """`plan`, `evidence`, or None for something not named by section 9."""
    if not isinstance(artifact, str) or not artifact.strip():
        return None
    if artifact.strip() == PLAN_ARTIFACT:
        return "plan"
    # "the observation or a source file" -- obs/<name>.json, cue/<name>.cue
    # or any implementation path quoted from the packet's provenance.
    return "evidence"
#: Section 10 is present too, and this constant was the same false claim
#: as SECTION_9_ABSENT one section along -- fixed for 9 and left for 10
#: in the same commit, which is the instance-not-the-class failure this
#: repository names as its first standing rule (Codex, PR #46). The
#: standing findings are read out of the plan now.
SECTION_10_ABSENT = None

#: Section 10's table: an item, its documentation, and what was decided.
#: Read rather than transcribed, so it cannot drift from the plan.
SECTION_10_HEADING = "## 10. Undocumented"

CUE_PATH_RE = re.compile(r'^([#A-Za-z_][^\s:]*):\s')


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def unresolved(reason):
    return {"unresolved": reason}


def rel(path):
    return os.path.relpath(path, HERE).replace(os.sep, "/")


def sha8(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def listdir_sorted(path, suffix=None):
    if not os.path.isdir(path):
        return []
    names = sorted(n for n in os.listdir(path) if os.path.isfile(os.path.join(path, n)))
    if suffix:
        names = [n for n in names if n.endswith(suffix)]
    return names


class Log(object):
    def __init__(self, quiet=False):
        self.quiet = quiet

    def __call__(self, fmt, *args):
        if not self.quiet:
            sys.stdout.write((fmt % args if args else fmt) + "\n")
            sys.stdout.flush()


# --------------------------------------------------------------------------
# step 1 -- extractors
# --------------------------------------------------------------------------

def extractor_scripts():
    directory = os.path.join(HERE, "extract")
    return [(n[:-3], os.path.join(directory, n))
            for n in listdir_sorted(directory, ".py")
            if not n.startswith("_")]


# The twelve extractors were written by two independent authors from one
# shape spec, and that spec fixed the shape of an observation without
# fixing the shape of the CALL. Five take `--root DIR --out PATH` and
# write the file; seven take the root positionally and print to stdout.
# Invoked the first way, the second kind reads the literal string
# "--root" as its root -- and, to their credit, answered
# {"unresolved": "<target> is absent"} rather than an empty list, which
# is the only reason this was a missing file rather than twelve
# contracts vetting clean against nothing.
#
# Both conventions are supported rather than one being rewritten: the
# disagreement belongs in the record, not smoothed away by whoever
# happened to assemble the tree.
CONVENTIONS = ("flags", "positional")


def _argv_for(convention, script, root, out_path):
    if convention == "flags":
        return [sys.executable, script, "--root", root, "--out", out_path]
    return [sys.executable, script, root]


def run_extractor(name, script, root, out_path, hashseed=None, cwd=None):
    """Run one extractor, whichever way it wants to be called.

    Returns (proc, convention). `convention` is recorded so a reader can
    tell which door each extractor answered at; a silent fallback would
    hide exactly the coupling defect this tool exists to surface.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if hashseed is not None:
        env["PYTHONHASHSEED"] = str(hashseed)
    last = None
    for convention in CONVENTIONS:
        if os.path.exists(out_path):
            os.remove(out_path)
        proc = subprocess.run(
            _argv_for(convention, script, root, out_path),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            cwd=cwd or HERE, check=False,
        )
        last = proc
        if proc.returncode != 0:
            continue
        if os.path.exists(out_path):
            return proc, convention
        if convention == "flags":
            # It ignored --out, so it never accepted this convention --
            # and it read the literal "--root" as its root directory. Its
            # stdout is therefore a well-formed, honestly-labelled
            # observation of the WRONG TREE. Accepting it here scored ten
            # of twelve extractors as all-unresolved and printed PASS,
            # with the determinism check cheerfully confirming the wrong
            # answer was reproducible. Writing a file is the only
            # evidence that this convention was the one it wanted.
            continue
        # Positional: stdout IS the output. Accept only a whole
        # observation, never a fragment that happens to parse.
        try:
            data = json.loads(proc.stdout.decode("utf-8"))
        except ValueError:
            continue
        if not isinstance(data, dict) or "facts" not in data:
            continue
        with open(out_path, "wb") as fh:
            fh.write(proc.stdout)
        return proc, convention
    return last, None


def step1_extract(root, log):
    result = {"ran": [], "skipped": [], "failed": []}
    obs_dir = os.path.join(HERE, "obs")
    os.makedirs(obs_dir, exist_ok=True)
    scripts = extractor_scripts()
    if not scripts:
        result["unresolved"] = "no extract/*.py present"
        return result

    for name, script in scripts:
        if name == "db" and not os.path.isfile(os.path.join(root, "wf.db")):
            log("  extract %-10s SKIP (wf.db absent)", name)
            result["skipped"].append({"name": name, "why": "wf.db is absent from the tree"})
            continue
        out_path = os.path.join(obs_dir, name + ".json")
        proc, convention = run_extractor(name, script, root, out_path, hashseed=0)
        if convention is None or proc.returncode != 0:
            log("  extract %-10s FAIL (exit %d)", name, proc.returncode)
            result["failed"].append({
                "name": name,
                "exit": proc.returncode,
                "stderr": proc.stderr.decode("utf-8", "replace")[-4000:],
            })
            continue
        try:
            data = json.loads(read_bytes(out_path).decode("utf-8"))
        except ValueError as exc:
            log("  extract %-10s FAIL (output is not JSON)", name)
            result["failed"].append({"name": name, "exit": 0,
                                     "stderr": "output is not JSON: %s" % exc})
            continue
        missing = [k for k in ("facts", "provenance") if k not in data]
        if missing:
            log("  extract %-10s FAIL (container lacks %s)", name, ",".join(missing))
            result["failed"].append({
                "name": name, "exit": 0,
                "stderr": "observation container lacks key(s): %s "
                          "(SPEC section 4 requires facts + provenance)" % ",".join(missing),
            })
            continue
        n_unres = count_unresolved(data.get("facts"))
        log("  extract %-10s ok  -> obs/%s.json%s", name, name,
            ("  (%d unresolved fact(s))" % n_unres) if n_unres else "")
        result["ran"].append({"name": name, "out": "obs/%s.json" % name,
                              "unresolved_facts": n_unres})
    return result


def count_unresolved(node):
    if isinstance(node, dict):
        if set(node.keys()) == {"unresolved"}:
            return 1
        return sum(count_unresolved(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_unresolved(v) for v in node)
    return 0


def collect_unresolved(node, path="facts"):
    out = []
    if isinstance(node, dict):
        if set(node.keys()) == {"unresolved"}:
            return [{"path": path, "reason": node["unresolved"]}]
        for key in node:
            out.extend(collect_unresolved(node[key], "%s.%s" % (path, key)))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            out.extend(collect_unresolved(item, "%s.%d" % (path, i)))
    return out


def step1_determinism(root, log):
    """Run every extractor twice into two temp dirs and byte-compare.

    The two passes use different PYTHONHASHSEED values and different working
    directories, so set/dict iteration order and cwd-relative behaviour would
    both show up as a diff rather than hiding behind a lucky repeat.
    """
    scripts = extractor_scripts()
    if not scripts:
        return {"unresolved": "no extract/*.py to check"}
    checked = []
    differing = []
    tmp_a = tempfile.mkdtemp(prefix="vet-det-a-")
    tmp_b = tempfile.mkdtemp(prefix="vet-det-b-")
    try:
        for name, script in scripts:
            if name == "db" and not os.path.isfile(os.path.join(root, "wf.db")):
                continue
            path_a = os.path.join(tmp_a, name + ".json")
            path_b = os.path.join(tmp_b, name + ".json")
            # DIFFERENT working directories, not just different output
            # paths. `root` is absolute, so an extractor that reads it
            # is unaffected; one that reaches for `os.getcwd()` or
            # resolves a relative input produces different output and is
            # caught. Both arms ran from HERE before, so the docstring's
            # claim that this exposes cwd-relative behaviour was not
            # true of the code under it (Codex, PR #46).
            proc_a, conv_a = run_extractor(name, script, root, path_a,
                                           hashseed=0, cwd=tmp_a)
            proc_b, conv_b = run_extractor(name, script, root, path_b,
                                           hashseed=1, cwd=tmp_b)
            if proc_a.returncode != 0 or proc_b.returncode != 0:
                differing.append({"name": name,
                                  "why": "extractor exited non-zero during the "
                                         "determinism check (%d / %d)"
                                         % (proc_a.returncode, proc_b.returncode)})
                continue
            # A convention of None means it exited 0 and answered at
            # NEITHER door -- no --out file, no usable stdout -- so the
            # paths below were never created. Reading them raised
            # FileNotFoundError and killed vet.py before it could write
            # the unresolved result or the failure report it promises
            # (Codex, PR #46). An arm that did not run has no result,
            # which is the same rule this file applies everywhere else.
            if conv_a is None or conv_b is None:
                differing.append({
                    "name": name,
                    "why": "extractor exited 0 but produced no observation by "
                           "either convention (%s / %s), so determinism could "
                           "not be checked" % (conv_a, conv_b),
                    "unresolved": True})
                log("  determinism %-10s INVALID (no output either way)", name)
                continue
            byte_a, byte_b = read_bytes(path_a), read_bytes(path_b)
            if byte_a == byte_b:
                checked.append({"name": name, "bytes": len(byte_a),
                                "sha256": hashlib.sha256(byte_a).hexdigest()})
                log("  determinism %-10s identical (%d bytes, sha256 %s)",
                    name, len(byte_a), hashlib.sha256(byte_a).hexdigest()[:16])
            else:
                diff = "\n".join(list(difflib.unified_diff(
                    byte_a.decode("utf-8", "replace").splitlines(),
                    byte_b.decode("utf-8", "replace").splitlines(),
                    "pass-a", "pass-b", lineterm="", n=1))[:40])
                differing.append({"name": name, "why": "output differs between runs",
                                  "diff": diff})
                log("  determinism %-10s DIFFERS", name)
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)
        shutil.rmtree(tmp_b, ignore_errors=True)
    return {"identical": checked, "differing": differing,
            "method": "each extractor run twice into separate temp dirs with "
                      "PYTHONHASHSEED=0 and PYTHONHASHSEED=1, output bytes compared"}


# --------------------------------------------------------------------------
# cue
# --------------------------------------------------------------------------

def cue_available():
    return shutil.which("cue")


def cue_vet(defn, cue_file, data_file):
    proc = subprocess.run(
        ["cue", "vet", "-d", defn, cue_file, data_file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=HERE,
        check=False,
    )
    return {
        "exit": proc.returncode,
        "stdout": proc.stdout.decode("utf-8", "replace"),
        "stderr": proc.stderr.decode("utf-8", "replace"),
        "argv": "cue vet -d '%s' %s %s" % (defn, cue_file, data_file),
    }


def parse_cue_errors(stderr):
    """Split cue's stderr into error records.

    A non-indented line starts an error; the indented lines under it are its
    source locations.  The error *path* is the CUE path prefix before the
    first ': ', or the whole line when there is no path prefix.
    """
    errors = []
    cur = None
    for line in stderr.splitlines():
        if not line.strip():
            continue
        if line[0].isspace():
            if cur is not None:
                cur["locations"].append(line.strip())
            continue
        if cur is not None:
            errors.append(cur)
        cur = {"line": line.rstrip(), "locations": []}
    if cur is not None:
        errors.append(cur)
    for err in errors:
        match = CUE_PATH_RE.match(err["line"])
        err["path"] = match.group(1) if match else err["line"].strip()
    return errors


# --------------------------------------------------------------------------
# step 2 -- contracts
# --------------------------------------------------------------------------

SIDECAR_FIELDS = ("change", "violates", "reject_path")


def parse_fault_sidecar(path):
    """A fault's sidecar, in either spelling it was ever written in.

    This tool expected `faults/<name>.<k>.md` with header lines. The
    fault planter wrote `faults/<name>.<k>.meta.json`, because the brief
    it was given said to -- two authors of one seam handed different
    interfaces by the same conductor, for the second time in a day. All
    66 faults reported a missing sidecar and not one was proven to fire.

    The two carry the SAME three fields. Both are read rather than one
    author being rewritten, and the spelling found is returned so the
    disagreement stays in the record instead of being smoothed away by
    whoever assembled the tree.
    """
    base = os.path.splitext(path)[0]
    md, meta = base + ".md", base + ".meta.json"

    if os.path.isfile(meta):
        try:
            raw = json.loads(read_bytes(meta).decode("utf-8"))
        except ValueError as exc:
            return None, "sidecar %s is not JSON: %s" % (rel(meta), exc)
        if not isinstance(raw, dict):
            return None, "sidecar %s is not an object" % rel(meta)
        fields = {k: str(raw[k]) for k in SIDECAR_FIELDS if k in raw}
        absent = [k for k in SIDECAR_FIELDS if k not in fields]
        if absent:
            return None, "sidecar %s lacks field(s): %s" % (rel(meta), ", ".join(absent))
        fields["_spelling"] = "meta.json"
        return fields, None

    if not os.path.isfile(md):
        return None, "sidecar %s is absent (nor %s)" % (rel(md), rel(meta))
    fields = {}
    for line in read_text(md).splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match and match.group(1) in SIDECAR_FIELDS:
            fields.setdefault(match.group(1), match.group(2).strip())
    absent = [k for k in SIDECAR_FIELDS if k not in fields]
    if absent:
        return None, "sidecar %s lacks header field(s): %s" % (rel(md), ", ".join(absent))
    fields["_spelling"] = "md"
    return fields, None


def step2_contracts(root, obs_result, log):
    out = {"contracts": [], "checked": 0}
    cue_dir = os.path.join(HERE, "cue")
    names = [n[:-4] for n in listdir_sorted(cue_dir, ".cue")]
    if not names:
        out["unresolved"] = (
            "no cue/*.cue contract is present in this tree; nothing was vetted. "
            "This is recorded as a failure, not as a clean run: an absent contract "
            "has not been shown to accept or reject anything."
        )
        return out
    if not cue_available():
        out["unresolved"] = "the `cue` binary is not on PATH; no contract could be vetted"
        return out

    skipped = {s["name"] for s in obs_result.get("skipped", [])}
    for name in names:
        out["contracts"].append(vet_one(name, skipped, log))
    out["checked"] = len(names)
    return out


def example_word(example):
    """`pass`, `FAIL`, or `UNBUILT` -- three states, not two.

    A control that RAN AND FAILED and one that could not be built are
    different work: the first is a contract to fix, the second is a
    document that does not say enough. Printing both as FAIL hid exactly
    the distinction this file exists to keep (Codex, PR #46).
    """
    if example.get("unbuilt"):
        return "UNBUILT"
    return "pass" if example.get("ok") else "FAIL"


def vet_one(name, skipped_obs, log):
    entry = {"name": name}
    cue_file = "cue/%s.cue" % name
    defn = NAME_TO_DEF.get(name)
    if defn is None:
        why = "`%s` is not in SPEC section 4's fixed name->definition map" % name
        entry["definition"] = unresolved(why)
        entry["unresolved"] = why
        entry["example"] = {"ok": False, "unresolved": why}
        entry["obs"] = {"ok": False, "unresolved": why}
        entry["faults"] = []
        entry["faults_unresolved"] = why
        entry["ok_before_verdicts"] = False
        log("  contract %-10s FAIL (name not in the fixed map)", name)
        return entry
    entry["definition"] = defn

    # ---- 2a positive control ----
    example = "examples/%s.json" % name
    if not os.path.isfile(os.path.join(HERE, example)):
        # NOT the same as a control that ran and failed, and reporting
        # them identically is this file's own absent-versus-none rule
        # broken inside it (Codex, PR #46). `ok` is None: the arm did
        # not run, so it has no result. The run still refuses -- an
        # unbuilt control is an unmet requirement -- but the reader is
        # told which kind, because the two need entirely different work.
        entry["example"] = {
            "ok": None,
            "unbuilt": True,
            "unresolved": "%s is absent, so the positive control did not run"
                          % example,
            "why": UNBUILT_EXAMPLES.get(
                name, "no reason recorded; either build it or record why "
                      "PLAN.md cannot supply one"),
        }
    else:
        run = cue_vet(defn, cue_file, example)
        entry["example"] = {"ok": run["exit"] == 0, "exit": run["exit"],
                            "stderr": run["stderr"][-4000:], "argv": run["argv"]}

    # ---- 2b the observation ----
    obs = "obs/%s.json" % name
    clean_stderr_lines = []
    if name in skipped_obs:
        # SPEC section 5.2: the db observation is "skipped when the file is
        # absent (REPORT says so)".  A documented skip is recorded, not
        # counted as a failure -- but it is also not counted as a pass, and
        # the faults that would have been measured against it are skipped too.
        entry["obs"] = {"skipped": True,
                        "why": "%s was not produced; the extractor was skipped" % obs}
        entry["faults"] = []
        entry["faults_skipped"] = ("faults are measured against %s, which was not "
                                   "produced" % obs)
        entry["ok_before_verdicts"] = bool(entry["example"].get("ok"))
        log("  contract %-10s example=%s obs=SKIPPED faults=skipped",
            name, example_word(entry["example"]))
        return entry
    if not os.path.isfile(os.path.join(HERE, obs)):
        entry["obs"] = {"ok": False, "unresolved": "%s is absent" % obs}
    else:
        run = cue_vet(defn, cue_file, obs)
        clean_stderr_lines = [line.rstrip()
                              for line in run["stderr"].splitlines()
                              if line.strip()]
        errors = parse_cue_errors(run["stderr"])
        for err in errors:
            err["id"] = "%s-%s" % (name, sha8(err["path"]))
        entry["obs"] = {"ok": run["exit"] == 0, "exit": run["exit"],
                        "argv": run["argv"], "errors": errors,
                        "stderr": run["stderr"][-8000:]}

    # ---- 2c faults ----
    fault_dir = os.path.join(HERE, "faults")
    # `.meta.json` files are SIDECARS, not faults. Counting them doubled
    # every contract's fault list and made each sidecar report itself
    # missing a sidecar.
    fault_names = [n for n in listdir_sorted(fault_dir, ".json")
                   if n.startswith(name + ".") and n.count(".") >= 2
                   and not n.endswith(".meta.json")]
    faults = []
    obs_bytes = None
    obs_abs = os.path.join(HERE, obs)
    if os.path.isfile(obs_abs):
        obs_bytes = read_bytes(obs_abs)
    for fname in fault_names:
        faults.append(check_fault(name, defn, fname, obs_bytes, clean_stderr_lines))
    for fault in faults:
        for line in fault.get("matched_lines", []):
            if "vocab." in line:
                log("  refusal %s", line)
    entry["faults"] = faults
    entry["faults_required"] = 2
    if len(fault_names) < 2:
        entry["faults_unresolved"] = (
            "SPEC section 6 step 2c requires at least two faults per contract; "
            "%d present" % len(fault_names))

    ok = bool(entry["example"].get("ok")) and bool(entry["obs"].get("ok"))
    ok = ok and len(fault_names) >= 2 and all(f.get("ok") for f in faults)
    entry["ok_before_verdicts"] = ok
    log("  contract %-10s example=%s obs=%s faults=%d/%d",
        name,
        example_word(entry["example"]),
        "pass" if entry["obs"].get("ok") else "mismatch",
        sum(1 for f in faults if f.get("ok")), len(faults))
    return entry


def check_fault(name, defn, fname, obs_bytes, clean_stderr_lines):
    rel_path = "faults/%s" % fname
    abs_path = os.path.join(HERE, rel_path)
    result = {"file": rel_path, "checks": {}}
    checks = result["checks"]

    raw = read_bytes(abs_path)
    if obs_bytes is None:
        checks["differs_from_obs"] = unresolved(
            "obs/%s.json is absent; the fault cannot be shown to have landed" % name)
        checks["fixture_intact"] = unresolved(
            "obs/%s.json is absent; the fault cannot be compared to it" % name)
    else:
        checks["differs_from_obs"] = raw != obs_bytes
        # `raw != obs_bytes` proves only that SOMETHING changed -- it is
        # equally true of a wholesale replacement, which can produce a
        # novel CUE error matching the sidecar regex and score the
        # contract as catching a fault it never saw (Codex, PR #46).
        # So the parsed structures are compared: the fault must still be
        # this observation, with something changed in it.
        try:
            intact = fixture_intact(json.loads(obs_bytes.decode("utf-8")),
                                    json.loads(raw.decode("utf-8")))
        except (ValueError, UnicodeDecodeError) as exc:
            checks["fixture_intact"] = unresolved(
                "one of the documents is not readable JSON: %s" % exc)
        else:
            result["fixture"] = intact
            checks["fixture_intact"] = (True if intact["intact"]
                                        else unresolved(intact["why"]))

    try:
        json.loads(raw.decode("utf-8"))
        checks["parses"] = True
    except (ValueError, UnicodeDecodeError) as exc:
        checks["parses"] = False
        result["parse_error"] = str(exc)

    sidecar_path = abs_path   # parse_fault_sidecar resolves the spelling
    fields, why = parse_fault_sidecar(sidecar_path)
    if fields is None:
        checks["sidecar"] = unresolved(why)
        result["ok"] = False
        return result
    checks["sidecar"] = True
    result["change"] = fields["change"]
    result["violates"] = fields["violates"]
    result["reject_path"] = fields["reject_path"]

    run = cue_vet(defn, "cue/%s.cue" % name, rel_path)
    checks["rejected"] = run["exit"] != 0
    result["exit"] = run["exit"]

    try:
        pattern = re.compile(fields["reject_path"])
    except re.error as exc:
        checks["reject_path_matches"] = unresolved(
            "reject_path is not a valid regex: %s" % exc)
        checks["attributable_to_fault"] = unresolved("reject_path did not compile")
        result["ok"] = False
        return result

    matched = [line.rstrip() for line in run["stderr"].splitlines()
               if line.strip() and pattern.search(line)]
    checks["reject_path_matches"] = bool(matched)
    result["matched_lines"] = matched
    novel = [line for line in matched if line not in clean_stderr_lines]
    checks["attributable_to_fault"] = bool(novel)
    if matched and not novel:
        result["note"] = ("every line matching reject_path also appears in the clean "
                          "run's stderr, so the rejection is not attributable to the fault")

    result["ok"] = all(v is True for v in checks.values())
    return result


# --------------------------------------------------------------------------
# steps 3 and 4 -- packets and verdicts
# --------------------------------------------------------------------------

def obs_value_at(obs, path):
    """Best-effort lookup of the value a cue error path points at.

    `obs` is the whole observation container: cue reports paths relative to
    the data root, so they begin at `facts` (or at `#Name.facts` when the
    definition name is part of the path).
    """
    parts = path.split(".")
    if parts and parts[0].startswith("#"):
        parts = parts[1:]
    node = obs
    walked = []
    for part in parts:
        walked.append(part)
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None, "no value at %s" % ".".join(walked)
    return node, None


def provenance_for(obs, path):
    parts = [p for p in path.split(".") if not p.startswith("#")]
    if path.split(".")[0].startswith("#"):
        parts = path.split(".")[1:]
    top = None
    for part in parts:
        if part == "facts":
            continue
        top = part
        break
    prov = obs.get("provenance", {}).get("facts", {})
    if top is None:
        return {}, "the error path names no fact"
    hits = {k: v for k, v in prov.items() if k == top or k.startswith(top + "[") or
            k.startswith(top + ".")}
    return hits, None


def section_10_findings():
    """The standing findings section 10 enumerates, read from the plan.

    Returns a list of {item, documentation, decision}, or an
    `unresolved` dict when the plan is not present -- which is a real
    possibility for a checkout that never staged it, and must not read
    the same as a plan that lists nothing.
    """
    path = os.path.join(HERE, "reports", "PLAN.md")
    if not os.path.isfile(path):
        return {"unresolved": "reports/PLAN.md is absent, so section 10's "
                              "standing findings cannot be read"}
    lines = read_text(path).splitlines()
    try:
        start = next(i for i, line in enumerate(lines)
                     if line.startswith(SECTION_10_HEADING))
    except StopIteration:
        return {"unresolved": "reports/PLAN.md has no %s heading"
                              % SECTION_10_HEADING}
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or set(cells[0]) <= set(":- "):
            continue
        if cells[0].lower() == "item":
            continue
        rows.append({"item": cells[0], "documentation": cells[1],
                     "decision": cells[2]})
    if not rows:
        return {"unresolved": "section 10 is present and its table is empty"}
    return rows


#: Measured across the 66 planted faults: the fraction of the clean
#: observation's leaves that survive a fault unchanged runs 0.564 to
#: 1.000, median 0.984. The floor is set well below the tightest real
#: fixture so it catches wholesale damage and never a legitimate plant.
FIXTURE_SURVIVAL_FLOOR = 0.4


def _leaf_map(node, prefix=""):
    """Every scalar in the document, by path. Two of these compared say
    what survived, which a byte comparison cannot."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _leaf_map(value, "%s.%s" % (prefix, key) if prefix else key)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _leaf_map(value, "%s.%d" % (prefix, i))
    else:
        yield prefix, node


def fixture_intact(clean, planted):
    """Is `planted` still recognisably `clean`, with something changed?

    Two properties, and a byte comparison gives only the first. A plant
    that silently failed leaves a clean fixture and the assertion
    afterwards answers a question about nothing; a plant that CLOBBERED
    the file also "differs", and the assertion answers a question about
    a different document. Both exit 0 and say nothing.
    """
    out = {}
    if not isinstance(clean, dict) or not isinstance(planted, dict):
        out["why"] = "one of the documents is not a JSON object"
        out["intact"] = False
        return out
    out["same_top_level_keys"] = sorted(clean) == sorted(planted)
    leaves_clean = dict(_leaf_map(clean))
    leaves_planted = dict(_leaf_map(planted))
    survived = sum(1 for k, v in leaves_clean.items()
                   if k in leaves_planted and leaves_planted[k] == v)
    total = max(1, len(leaves_clean))
    out["leaves"] = total
    out["survived"] = survived
    out["survival"] = round(survived / total, 4)
    out["changed_structurally"] = leaves_clean != leaves_planted
    out["intact"] = bool(out["same_top_level_keys"]
                         and out["survival"] >= FIXTURE_SURVIVAL_FLOOR
                         and out["changed_structurally"])
    if not out["intact"]:
        out["why"] = (
            "top-level keys changed" if not out["same_top_level_keys"] else
            "nothing changed structurally; the plant did not land"
            if not out["changed_structurally"] else
            "only %.1f%% of the observation survived (floor %.0f%%); this is a "
            "replacement, not a plant"
            % (100 * out["survival"], 100 * FIXTURE_SURVIVAL_FLOOR))
    return out


def notes_entries(rel, name):
    """The lines of a notes file that mention this contract, or None.

    None means the file is absent -- different from present-and-silent,
    and the packet says which, because an author who declared nothing
    and an author whose notes were lost are not the same evidence.
    """
    path = os.path.join(HERE, rel)
    if not os.path.isfile(path):
        return None
    out, keeping = [], False
    for line in read_text(path).splitlines():
        if line.startswith("#"):
            keeping = name in line.lower() or ("`%s`" % name) in line
        if keeping or name in line:
            out.append(line)
    return "\n".join(out).strip()


def write_packet(name, defn, errs, log):
    """Everything section 9 says a packet contains, for EVERY error on
    this path.

    It used to take one error and be called once per error with the same
    id, so the file was overwritten and only the last line survived. And
    it carried a five-line excerpt of the contract where section 9 item
    2 asks for the WHOLE `cue/<name>.cue` -- "small, so its `// PLAN.md
    SS…` citations are visible" -- and omitted item 5, the CONTRACT-NOTES
    and EXTRACTION-NOTES entries naming this contract. The adjudicator
    has no repository access, so anything not in the packet is something
    it cannot consult and must not be assumed to have weighed (Codex,
    PR #46).
    """
    if isinstance(errs, dict):
        errs = [errs]
    err = errs[0]
    packet_id = err["id"]
    path = os.path.join(HERE, "packets", "%s.md" % packet_id)
    obs_path = os.path.join(HERE, "obs", "%s.json" % name)
    obs = {}
    if os.path.isfile(obs_path):
        try:
            obs = json.loads(read_text(obs_path))
        except ValueError:
            obs = {}

    value, value_why = obs_value_at(obs, err["path"])
    prov_hits, prov_why = provenance_for(obs, err["path"])

    lines = []
    lines.append("# packet %s" % packet_id)
    lines.append("")
    lines.append("observation: `%s`  definition: `%s`" % (name, defn))
    lines.append("id: `<name>-<sha256(error path)[:8]>` = `%s` + `%s`"
                 % (name, sha8(err["path"])))
    lines.append("")
    lines.append("## the disagreement")
    lines.append("")
    lines.append("error path: `%s`" % err["path"])
    lines.append("")
    lines.append("```")
    for i, one in enumerate(errs):
        if i:
            lines.append("")
        lines.append(one["line"])
        for loc in one["locations"]:
            lines.append("    " + loc)
    lines.append("```")
    lines.append("")
    if len(errs) > 1:
        lines.append("_%d errors share this path; a verdict here answers all "
                     "of them, so all of them are above._" % len(errs))
        lines.append("")
    lines.append("## what the extractor observed")
    lines.append("")
    if value_why:
        lines.append("The error path could not be resolved inside `obs/%s.json`: %s."
                     % (name, value_why))
    else:
        lines.append("```json")
        lines.append(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))
        lines.append("```")
    lines.append("")
    lines.append("## provenance for that fact")
    lines.append("")
    if prov_why:
        lines.append(prov_why + ".")
    elif not prov_hits:
        lines.append("No provenance entry matched this error path.")
    else:
        shown = sorted(prov_hits)
        cap = 12
        for key in shown[:cap]:
            entry = prov_hits[key]
            lines.append("### `%s`" % key)
            lines.append("")
            lines.append("- file: `%s`" % entry.get("file", "?"))
            lines.append("- lines: `%s`" % entry.get("lines", "?"))
            lines.append("- rule: %s" % entry.get("rule", "?"))
            if entry.get("unresolved"):
                lines.append("- unresolved: %s" % entry["unresolved"])
            lines.append("")
            lines.append("```")
            lines.append(str(entry.get("text", "")))
            lines.append("```")
            lines.append("")
        if len(shown) > cap:
            lines.append("_%d further provenance entries matched this fact and are "
                         "not shown here; read `obs/%s.json` for all of them._"
                         % (len(shown) - cap, name))
            lines.append("")
    lines.append("## the contract text cited above")
    lines.append("")
    seen_labels = set()
    for one in errs:
        for label, text in cited_source(one["locations"]):
            if label in seen_labels:
                continue
            seen_labels.add(label)
            lines.append("### `%s`" % label)
            lines.append("")
            lines.append("```")
            lines.append(text)
            lines.append("```")
            lines.append("")
    if not seen_labels:
        lines.append("The error carried no source location.")
        lines.append("")

    # Section 9 item 2: the WHOLE contract, so its `// PLAN.md SS…`
    # citations are visible. An excerpt shows the failing line and hides
    # the constraints around it, and the adjudicator cannot open the
    # file.
    lines.append("## the whole contract")
    lines.append("")
    contract_rel = "cue/%s.cue" % name
    contract_abs = os.path.join(HERE, contract_rel)
    if os.path.isfile(contract_abs):
        lines.append("`%s`, entire:" % contract_rel)
        lines.append("")
        lines.append("```cue")
        lines.append(read_text(contract_abs).rstrip("\n"))
        lines.append("```")
    else:
        lines.append("> unresolved: `%s` is absent, so the contract this "
                     "error came from cannot be shown." % contract_rel)
    lines.append("")

    # Section 9 item 5: the pre-declared readings and guesses. A verdict
    # that cannot see what each author SAID they were assuming is a
    # verdict on the artifact without the reasoning behind it.
    lines.append("## what the authors declared")
    lines.append("")
    found_notes = False
    for notes_rel in ("CONTRACT-NOTES.md", "EXTRACTION-NOTES.md"):
        entries = notes_entries(notes_rel, name)
        if entries is None:
            lines.append("> unresolved: `%s` is absent." % notes_rel)
            lines.append("")
            continue
        lines.append("### `%s`" % notes_rel)
        lines.append("")
        if entries:
            found_notes = True
            lines.append(entries.rstrip("\n"))
        else:
            lines.append("_No entry mentions `%s`._" % name)
        lines.append("")
    if not found_notes:
        lines.append("_Neither notes file records anything about `%s`; that "
                     "absence is itself worth weighing._" % name)
        lines.append("")

    lines.append("## verdict required")
    lines.append("")
    lines.append("Write `verdicts/%s.json`. `vet.py` checks three things, which are "
                 "the three SPEC section 6 step 4 names verbatim:" % packet_id)
    lines.append("")
    lines.append("- `verdict` is one of %s;" % ", ".join("`%s`" % v for v in VERDICT_VALUES))
    lines.append("- `action` is one of %s;" % ", ".join("`%s`" % v for v in ACTION_VALUES))
    lines.append("- `%s` are each a non-empty string;"
                 % "`, `".join(VERDICT_REQUIRED))
    lines.append("- an `ambiguous` verdict carries `action: record-finding`;")
    lines.append("- `because` is a non-empty list;")
    lines.append("- every `quote` in it appears verbatim in this packet or PLAN.md.")
    lines.append("")
    write_text(path, "\n".join(lines) + "\n")
    log("  packet   %s -> packets/%s.md", packet_id, packet_id)
    return "packets/%s.md" % packet_id


def cited_source(locations):
    """Read back the source lines a cue error points at."""
    out = []
    seen = set()
    for loc in locations:
        match = re.match(r"^(.*?):(\d+):(\d+)$", loc.strip())
        if not match:
            continue
        path, lineno = match.group(1), int(match.group(2))
        abs_path = os.path.join(HERE, path)
        if not os.path.isfile(abs_path) or (path, lineno) in seen:
            continue
        seen.add((path, lineno))
        source = read_text(abs_path).splitlines()
        lo = max(1, lineno - 2)
        hi = min(len(source), lineno + 2)
        block = "\n".join("%5d | %s" % (n, source[n - 1]) for n in range(lo, hi + 1))
        out.append(("%s:%d" % (path, lineno), block))
    return out


def validate_verdict(packet_id, packet_rel):
    """SPEC section 6 step 4: enum, required citations, quotes verbatim."""
    path = os.path.join(HERE, "verdicts", "%s.json" % packet_id)
    result = {"id": packet_id, "file": "verdicts/%s.json" % packet_id}
    if not os.path.isfile(path):
        result["ok"] = False
        result["why"] = "no verdict file"
        return result
    try:
        data = json.loads(read_text(path))
    except ValueError as exc:
        result["ok"] = False
        result["why"] = "verdict is not JSON: %s" % exc
        return result
    problems = []

    # Section 9's schema, in full. It used to check the enum and the
    # quotes only, so a verdict carrying an allowed `verdict` value and
    # one quote was accepted with `id`, `rule`, `observed` and `action`
    # all missing -- and a malformed verdict then covered a real
    # observation mismatch instead of failing (Codex, PR #46).
    for field in VERDICT_REQUIRED:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append("`%s` is missing or not a non-empty string" % field)
    if data.get("id") and data["id"] != packet_id:
        problems.append("`id` is %r; the verdict is filed as %r"
                        % (data["id"], packet_id))

    verdict = data.get("verdict")
    if verdict not in VERDICT_VALUES:
        problems.append("`verdict` is %r; must be one of %s"
                        % (verdict, ", ".join(VERDICT_VALUES)))
    action = data.get("action")
    if action not in ACTION_VALUES:
        problems.append("`action` is %r; must be one of %s"
                        % (action, ", ".join(ACTION_VALUES)))
    required_action = ACTION_FOR.get(verdict)
    if required_action and action != required_action:
        problems.append("a %r verdict requires action %r, not %r"
                        % (verdict, required_action, action))
    citations, cite_field = None, None
    for field in CITATION_FIELDS:
        if isinstance(data.get(field), list) and data[field]:
            citations, cite_field = data[field], field
            break
    result["citation_field"] = cite_field
    if citations is None:
        problems.append("one of %s must be a non-empty list"
                        % " or ".join("`%s`" % f for f in CITATION_FIELDS))
    else:
        # Section 9 gives the adjudicator PLAN.md WHOLE, expressly so it
        # can catch a contract citing lines that do not say what it
        # claims. A quote from PLAN.md is therefore grounded even when
        # the packet did not happen to excerpt that line. Checking the
        # packet alone -- which section 6's prose says, and which is all
        # this tooling was given -- rejected 39 of 96 correctly-sourced
        # quotes across the adjudicator's verdicts.
        # A verdict is a judgement about the packet the ADJUDICATOR READ,
        # and packets are regenerated on every run of this tool. Checking
        # a verdict against a freshly generated packet asks whether the
        # judgement matches evidence it never saw. All 25 packets in the
        # first adjudication differed from the versions Grok read.
        #
        # So a frozen copy wins, and its digest is checked against what
        # was recorded when it was frozen -- freezing has to be proved
        # like anything else. When no frozen copy exists this says so
        # rather than falling back to the live packet, because a silent
        # fallback is the original bug with a comment on it.
        frozen_note = None
        frozen_abs = os.path.join(HERE, "adjudicated", "packets",
                                  "%s.md" % packet_id)
        saw_path = os.path.join(HERE, "adjudicated", "SAW.json")
        if os.path.isfile(frozen_abs) and os.path.isfile(saw_path):
            try:
                saw = json.loads(read_text(saw_path)).get(packet_id, {})
            except ValueError:
                saw = {}
            digest = hashlib.sha256(read_bytes(frozen_abs)).hexdigest()
            if saw.get("sha256") and saw["sha256"] != digest:
                problems.append(
                    "frozen packet %s.md has itself changed since it was "
                    "recorded (%s != %s)" % (packet_id, digest[:12],
                                             saw["sha256"][:12]))
            else:
                packet_rel = "adjudicated/packets/%s.md" % packet_id
                frozen_note = "checked against the packet the adjudicator read"
        else:
            frozen_note = ("no frozen packet; checked against a REGENERATED "
                           "one, which the adjudicator may never have seen")
        result["evidence"] = frozen_note

        plan_text = ""
        plan_abs = os.path.join(HERE, "..", "PLAN.md")
        if os.path.isfile(plan_abs):
            plan_text = read_text(plan_abs)
        packet_text = ""
        packet_abs = os.path.join(HERE, packet_rel)
        if os.path.isfile(packet_abs):
            packet_text = read_text(packet_abs)
        else:
            problems.append("packet %s is absent, so no quote could be checked" % packet_rel)
        for i, citation in enumerate(citations):
            if not isinstance(citation, dict) or "quote" not in citation:
                problems.append("citations[%d] has no `quote`" % i)
                continue
            quote = citation["quote"]
            if not isinstance(quote, str) or not quote.strip():
                problems.append("citations[%d].quote is not a non-empty string" % i)
            elif packet_text and quote not in packet_text and quote not in plan_text:
                problems.append("citations[%d].quote appears verbatim in neither %s nor PLAN.md"
                                % (i, packet_rel))
    if citations:
        sides = {citation_side(c.get("artifact"))
                 for c in citations if isinstance(c, dict)}
        result["citation_sides"] = sorted(s for s in sides if s)
        if "plan" not in sides:
            problems.append(
                "`%s` has no citation whose `artifact` is PLAN.md; section 9 "
                "requires at least one" % (cite_field or "because"))
        if "evidence" not in sides:
            problems.append(
                "`%s` has no citation of the observation or a source file; "
                "section 9 requires at least one alongside the PLAN.md one"
                % (cite_field or "because"))
        for i, c in enumerate(citations):
            if isinstance(c, dict) and citation_side(c.get("artifact")) is None:
                problems.append("%s[%d] has no `artifact`; a quote with no "
                                "source cannot be checked against anything"
                                % (cite_field or "because", i))

    result["verdict"] = verdict
    result["problems"] = problems
    result["ok"] = not problems
    if SECTION_9_ABSENT:
        result["unchecked"] = SECTION_9_ABSENT
    return result


# --------------------------------------------------------------------------
# step 5 -- report and findings
# --------------------------------------------------------------------------

def write_findings(report):
    lines = ["# FINDINGS", "",
             "Generated by `vet.py`. Do not hand-edit.", ""]
    verdicts = report.get("verdicts", [])
    by_kind = {v: [] for v in VERDICT_VALUES}
    for entry in verdicts:
        if entry.get("verdict") in by_kind:
            by_kind[entry["verdict"]].append(entry)
    for kind in VERDICT_VALUES:
        lines.append("## %s" % kind)
        lines.append("")
        if not by_kind[kind]:
            lines.append("_None recorded._")
        else:
            # One verdict can answer several mismatches that share an
            # error path, so the same id arrives more than once. Listing
            # it eight times reads as eight findings; it is one.
            seen = set()
            for entry in sorted(by_kind[kind], key=lambda e: e["id"]):
                if entry["id"] in seen:
                    continue
                seen.add(entry["id"])
                lines.append("- `%s` — packet `%s`%s"
                             % (entry["id"], entry.get("packet", "?"),
                                "" if entry.get("ok") else "  **(verdict invalid)**"))
        lines.append("")
    # Findings raised by hand, which no packet could carry. A contract
    # that constrains nothing about a field generates no disagreement
    # there, so a real divergence behind that field is invisible to this
    # whole pipeline -- the hole does not merely fail to catch a planted
    # fault, it hides the finding standing behind it. Those go in
    # findings/*.json and are listed SEPARATELY, because they were never
    # adjudicated and must not read as though they were.
    hand = []
    findings_dir = os.path.join(HERE, "findings")
    if os.path.isdir(findings_dir):
        for name in listdir_sorted(findings_dir, ".json"):
            try:
                hand.append(json.loads(read_text(os.path.join(findings_dir, name))))
            except ValueError as exc:
                hand.append({"id": name, "rule": "UNPARSEABLE: %s" % exc,
                             "observed": "", "adjudicated": False})
    lines.append("## raised by hand, not adjudicated")
    lines.append("")
    if not hand:
        lines.append("_None recorded._")
    for item in hand:
        lines.append("- `%s` (%s) — %s" % (item.get("id", "?"),
                                           item.get("verdict", "?"),
                                           item.get("rule", "")))
        if item.get("observed"):
            lines.append("  - observed: %s" % item["observed"])
        if item.get("why_no_packet"):
            lines.append("  - no packet: %s" % item["why_no_packet"])
    lines.append("")
    lines.append("## standing findings from section 10 of the plan")
    lines.append("")
    standing = report.get("section_10")
    if isinstance(standing, dict):
        lines.append("> unresolved: %s"
                     % standing.get("unresolved", "not read"))
        lines.append("")
    else:
        lines.append("Decided when the plan was written, not by this run. "
                     "They are owner-facing and they do not go away because "
                     "no packet was generated for them.")
        lines.append("")
        lines.append("| item | documentation | decision |")
        lines.append("|:--|:--|:--|")
        for row in standing or []:
            lines.append("| %s | %s | %s |"
                         % (row["item"], row["documentation"], row["decision"]))
        lines.append("")
    lines.append("## observations that could not be resolved")
    lines.append("")
    unres = report.get("unresolved_facts", [])
    if not unres:
        lines.append("_No extractor emitted an unresolved fact._")
    else:
        for item in unres:
            lines.append("- `%s` — %s" % (item["path"], item["reason"]))
    lines.append("")
    write_text(os.path.join(HERE, "FINDINGS.md"), "\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser(description="vet every contract against every observation")
    ap.add_argument("--root", default=APP_ROOT, help="workflow app directory")
    ap.add_argument("--check-determinism", action="store_true",
                    help="run every extractor twice and byte-compare (on by default)")
    ap.add_argument("--no-check-determinism", action="store_true",
                    help="skip the determinism check; the gate then fails, because a "
                         "check that did not run is not a check that passed")
    ap.add_argument("--extract-only", action="store_true",
                    help="stop after step 1 (extract + determinism)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    log = Log(args.quiet)
    root = os.path.abspath(args.root)

    report = {"root": os.path.basename(root), "steps": {}}
    missing = []

    # ---- step 1 ----
    log("step 1: extract")
    obs_result = step1_extract(root, log)
    report["steps"]["extract"] = obs_result
    if obs_result.get("unresolved"):
        missing.append("extract: " + obs_result["unresolved"])
    for failure in obs_result.get("failed", []):
        missing.append("extract %s: exit %s" % (failure["name"], failure["exit"]))
    for skip in obs_result.get("skipped", []):
        log("  note: observation `%s` skipped — %s", skip["name"], skip["why"])

    unresolved_facts = []
    for ran in obs_result.get("ran", []):
        obs_path = os.path.join(HERE, ran["out"])
        try:
            data = json.loads(read_text(obs_path))
        except (OSError, ValueError):
            continue
        for item in collect_unresolved(data.get("facts", {}),
                                       "%s.facts" % ran["name"]):
            unresolved_facts.append(item)
    report["unresolved_facts"] = unresolved_facts

    if args.no_check_determinism:
        report["steps"]["determinism"] = unresolved(
            "--no-check-determinism was passed; determinism was not demonstrated")
        missing.append("determinism: not checked (--no-check-determinism)")
    else:
        log("step 1b: determinism")
        det = step1_determinism(root, log)
        report["steps"]["determinism"] = det
        if det.get("unresolved"):
            missing.append("determinism: " + det["unresolved"])
        for bad in det.get("differing", []):
            missing.append("determinism %s: %s" % (bad["name"], bad["why"]))

    if args.extract_only:
        report["steps"]["contracts"] = unresolved("--extract-only was passed")
        report["exit"] = 1 if missing else 0
        report["missing"] = missing
        write_text(os.path.join(HERE, "REPORT.json"),
                   json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n")
        finish(missing, log, extract_only=True)
        return 1 if missing else 0

    # ---- step 2 ----
    log("step 2: contracts")
    contracts = step2_contracts(root, obs_result, log)
    report["steps"]["contracts"] = contracts
    if contracts.get("unresolved"):
        missing.append("contracts: " + contracts["unresolved"])

    # ---- steps 3 and 4 ----
    log("step 3: packets  /  step 4: verdicts")
    verdicts = []
    for entry in contracts.get("contracts", []):
        name = entry["name"]
        obs_state = entry.get("obs", {})
        if obs_state.get("skipped"):
            log("  note: contract `%s` vetted against its example only — %s",
                name, obs_state["why"])
            continue
        if obs_state.get("unresolved"):
            missing.append("obs %s: %s" % (name, obs_state["unresolved"]))
            continue
        if obs_state.get("ok"):
            continue
        # ONE PACKET PER ID, carrying every error that shares it.
        # `cue` emits several errors for one path, and this loop used to
        # call write_packet once per error with the same id -- each
        # overwriting the last -- and then accept one verdict for all of
        # them. In the committed report `cli-e3d957b6` appears twenty
        # times against a packet holding only the final line, so
        # nineteen errors counted as adjudicated by a judgement that
        # never saw them (Codex, PR #46).
        grouped = {}
        for err in obs_state.get("errors", []):
            grouped.setdefault(err["id"], []).append(err)
        for packet_id, errs in grouped.items():
            packet_rel = write_packet(name, entry["definition"], errs, log)
            verdict = validate_verdict(packet_id, packet_rel)
            verdict["packet"] = packet_rel
            verdict["errors_covered"] = len(errs)
            verdict["error_path"] = errs[0]["path"]
            verdict["error_line"] = errs[0]["line"]
            verdicts.append(verdict)
            if not verdict["ok"]:
                missing.append("verdict %s: %s"
                               % (verdict["id"],
                                  verdict.get("why") or "; ".join(verdict.get("problems", []))))
    report["verdicts"] = sorted(verdicts, key=lambda v: v["id"])

    for entry in contracts.get("contracts", []):
        name = entry["name"]
        if entry.get("unresolved"):
            missing.append("contract %s: %s" % (name, entry["unresolved"]))
        example = entry.get("example", {})
        if not example.get("ok"):
            why = example.get("unresolved", "example rejected by its own contract")
            missing.append("example %s: %s" % (name, why))
        if entry.get("faults_skipped"):
            log("  note: faults for `%s` not measured — %s", name, entry["faults_skipped"])
        elif entry.get("faults_unresolved"):
            missing.append("faults %s: %s" % (name, entry["faults_unresolved"]))
        for fault in entry.get("faults", []):
            if not fault.get("ok"):
                bad = [k for k, v in fault["checks"].items() if v is not True]
                missing.append("fault %s: failed check(s) %s" % (fault["file"], ", ".join(bad)))

    # ---- step 5 ----
    report["section_9"] = (unresolved(SECTION_9_ABSENT) if SECTION_9_ABSENT
                           else {"checked": "the verdict schema in full: %s, "
                                            "the action enum, and the "
                                            "ambiguous/record-finding rule"
                                            % ", ".join(VERDICT_REQUIRED)})
    standing = section_10_findings()
    report["section_10"] = (unresolved(SECTION_10_ABSENT) if SECTION_10_ABSENT
                            else standing)
    report["missing"] = missing
    report["exit"] = 1 if missing else 0
    write_text(os.path.join(HERE, "REPORT.json"),
               json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n")
    write_findings(report)
    finish(missing, log)
    return 1 if missing else 0


def finish(missing, log, extract_only=False):
    # The verdict of the run is never suppressed by --quiet: step 6 requires
    # that a failing run list what is missing.
    log("")
    if not missing:
        log("PASS%s", " (extract only)" if extract_only else "")
        return
    sys.stderr.write("FAIL — %d thing(s) missing:\n" % len(missing))
    for item in missing:
        sys.stderr.write("  - %s\n" % item)
    sys.stderr.flush()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
