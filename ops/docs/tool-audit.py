#!/usr/bin/env python3
"""Re-derive every external tool claim from the registries — never by hand.

    python3 ops/docs/tool-audit.py [--offline]

The report goes to stdout and is not written anywhere. A file of
external version numbers sitting on the shelf acquires authority just
by being there, and it is stale the moment any of them ships — which
is the exact failure this file exists to argue against. Run it when
you need it.

`rust-agent-tooling.md` names the gap this closes, in its own words:
"tool freshness rots and `covers:` cannot watch external projects;
only the repo-facing claims are mechanically checkable." A version
number in prose is a measurement that outlived what it measured — the
same class as a stale figure in a PR body, with no commit behind it
and nothing that would announce the drift. Two of the figures in the
owner's research reports had already moved by the time they were read.

So the roster below carries the DURABLE part of each row — why the
tool is watched and what we decided about it — and every number beside
it is fetched at run time. `tool-audit.md` holds the verdicts and
deliberately holds no figures at all.

Three refusals, because "nobody looked" must never print the same way
as "we checked and it was fine":

  * a name the registry does not have prints **ABSENT**, which is a
    finding about the name, not an error in the run;
  * a name that could not be reached prints **UNREACHABLE**, and is
    never rendered as though it were healthy;
  * if NOTHING was reachable nothing is printed and the exit is
    non-zero, because a report of UNREACHABLE rows still looks like an
    audit at a glance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

DOCS = Path(__file__).resolve().parent
REPO = DOCS.parents[1]

#: crates.io asks crawlers to identify themselves and to pace requests.
AGENT = "agentscient-tool-audit (+https://github.com/uscient/agentscient)"
#: crates.io's data-access policy caps API callers at ONE request per
#: second. 0.4 was 2.5/s — a policy violation, not a tuning choice
#: (Codex and Grok, PR review of 5387cd2). GitHub is not the binding
#: constraint here: one run makes 11 repo lookups against a 60/hour
#: unauthenticated allowance.
PACE = 1.0

OK, ABSENT, UNREACHABLE = "ok", "ABSENT", "UNREACHABLE"


class Reply(NamedTuple):
    """A registry answer, TAGGED — never inferred from a Python type.

    The first version returned a parsed dict, a bare int status, or
    None, and the callers told them apart by `isinstance`. Two ways
    that invents an absence for a tool that exists: an HTTP 200 whose
    body IS the integer 404, and a 404 HTML page from a proxy or
    captive portal. Both scored ABSENT — a finding about the NAME —
    when the truth was "we could not ask" (Codex and Grok, PR review
    of 5387cd2).
    """

    state: str
    body: dict | None = None

def tool(name, crate, repo, verdict, why):
    """One roster row. A call, not a tuple literal, so the multi-line
    `why` needs no parentheses and each field is named at the call."""
    return (name, crate, repo, verdict, why)


#: name, crate (or None), repo slug (or None), verdict, why it is watched.
#: The verdict is the durable half — it survives a version bump; the
#: figures beside it do not, which is the whole reason for this file.
ROSTER = (
    ("Registered or registerable now", (
        tool("cargo-nextest", "cargo-nextest", None, "adopt",
         "runner with JUnit output; a zero-matching run FAILS, which is "
         "the refusal-over-silence rule built into the tool"),
        tool("cargo-mutants", "cargo-mutants", None, "adopt",
         "proves a frozen suite is not weak; typed exits separate "
         "'missed mutants' from 'baseline already red'"),
        tool("cargo-llvm-cov", "cargo-llvm-cov", None, "adopt",
         "renders its own verdict via --fail-under-*; coverage suggests "
         "where mutants prove"),
        tool("cargo-deny", "cargo-deny", None, "adopt",
         "advisories, licences, bans and sources in one registered gate"),
        tool("cargo-semver-checks", "cargo-semver-checks", None, "adopt",
         "public-API gate off rustdoc JSON"),
        tool("cargo-public-api", "cargo-public-api", None, "adopt",
         "one line per public item: an API skeleton agents diff instead "
         "of reading source"),
        tool("dylint", "dylint", "trailofbits/dylint", "adopt",
         "a CUE contract invariant as a compiler diagnostic — emits the "
         "cargo --message-format=json shape diagnostics.py already reads"),
        tool("typify", "typify", None, "adopt",
         "CUE -> JSON Schema -> generated Rust types, so an agent cannot "
         "hallucinate a contract field"),
        tool("cucumber", "cucumber", None, "adopt",
         "the Rust binding for ops/design/features/*.feature, which "
         "tdd@1's test_scope already names"),
    )),
    ("Watch — real, but not load-bearing yet", (
        tool("kani-verifier", "kani-verifier", "model-checking/kani", "watch",
         "CUE bounds as proofs: timeout: int & >0 & <=60 becomes a "
         "kani::assume harness. Slow; a scheduled gate, never per-PR"),
        tool("shuttle", "shuttle", "awslabs/shuttle", "watch",
         "thread-interleaving failures, which turmoil and MadSim do not "
         "cover; probabilistic, so it scales where loom does not"),
        tool("loom", "loom", None, "watch",
         "exhaustive interleavings. Mature but slow-moving — check the "
         "release age below before preferring it to shuttle"),
        tool("cargo-careful", "cargo-careful", None, "watch",
         "UB and alignment that cargo test misses, far faster than Miri"),
        tool("cargo-fuzz", "cargo-fuzz", None, "watch",
         "byte-level edge cases in parsing and serialisation"),
        tool("insta", "insta", None, "watch",
         "snapshots that fail until reviewed; --accept can launder a "
         "behaviour change, so its diffs review as code diffs"),
        tool("anodized", "anodized", "anodized-rs/anodized", "watch",
         "design-by-contract on STABLE rust. Very early — the download "
         "count below is the number to judge it by"),
        tool("turmoil", "turmoil", None, "watch",
         "seeded network simulation; a failure is only evidence if the "
         "seed is recorded with it"),
        tool("proptest-state-machine", "proptest-state-machine", None, "watch",
         "model-based testing with shrinking to a minimal failing trace"),
        tool("rmcp", "rmcp", None, "watch",
         "the OFFICIAL MCP SDK. Several forks republish the name; the "
         "repository field below is how you tell them apart"),
    )),
    ("Marginal — judge these by the figures below", (
        tool("cargo-workspace-lints", "cargo-workspace-lints",
         "JarredAllen/cargo-workspace-lints", "marginal",
         "one of the research documents places this in 'adopt now'. "
         "Judge that against the release age and star count below"),
        tool("madsim", "madsim", None, "marginal",
         "deterministic async simulation; check the release age"),
        tool("birdcage", "birdcage", None, "marginal",
         "sandbox primitive its own docs call incomplete"),
        tool("regorus", "regorus", None, "marginal",
         "Rego in Rust, if gate predicates ever become data"),
    )),
    ("Refuted — do not register", (
        tool("rustyspec", "rustyspec", "jyjeanne/rustyspec", "refuted",
         "no crate. The research cites a single Medium post; the "
         "repository's star count and push age are below"),
        tool("ax-rust-agent-observability", "ax-rust-agent-observability",
         None, "refuted",
         "not a Rust tool at all — a SKILL.md entry in Tessl's registry"),
        tool("mcp-framework", "mcp-framework", "koki7o/mcp-framework",
         "refuted", "no crate; judge the repository by the star count "
         "and push age below"),
        tool("cue-rust", "cue-rust", "tyrchen/cue-rust", "refuted",
         "sold in the research as a Rust-native CUE implementation. The "
         "figures below are what that claim actually rests on; shell out "
         "to the Go cue binary instead"),
        tool("cargo-pmcp", "cargo-pmcp", "paiml/rust-mcp-sdk", "refuted",
         "active, but bound to a THIRD-PARTY MCP SDK rather than the "
         "official one. Take its SARIF output as an idea, not a dependency"),
        tool("agent-harness", "agent-harness", "getlatentic/agent-harness",
         "refuted",
         "a unified event vocabulary across harnesses — which usage.py "
         "already does here. Read it; do not depend on it"),
        tool("anda", "anda", "ldclabs/anda", "refuted",
         "NAME COLLISION: the crate `anda` is an unrelated Linux "
         "packaging toolchain. The agent framework publishes as "
         "anda_core / anda_engine"),
        tool("cargo-mcp", "cargo-mcp", None, "refuted",
         "presented in the research as THE cargo MCP server; check the "
         "release age below"),
    )),
)


#: The two details crates.io actually uses for a missing crate. Both
#: are the registry's own words; the second names the crate back.
_CRATES_ABSENT = ("Not Found", "crate `{name}` does not exist")


def _crates_not_found(body, url):
    """Did crates.io itself say the crate is missing?

    Checking that `detail` is A STRING stopped one step short of the
    defect above: a proxy answering {"errors":[{"detail":"blocked by
    proxy"}]} passed, and its refusal was reported as a finding about
    the NAME (Codex, PR #39 round two). The VALUE is now matched, and
    one of the two forms names the crate — so an intermediary that has
    never seen the request cannot invent an absence for it.
    """
    errors = body.get("errors")
    if not (isinstance(errors, list) and errors):
        return False
    name = url.rstrip("/").rsplit("/", 1)[-1]
    said = {form.format(name=name) for form in _CRATES_ABSENT}
    # `detail` is tested for STRING before membership: a body shaped
    # {"errors": [{"detail": ["blocked", "by", "proxy"]}]} raises
    # `TypeError: unhashable type` on the set test, and this runs
    # OUTSIDE `_fetch`'s except, so it aborted the whole audit rather
    # than costing one row. The type test is the guard, not a tidiness.
    return all(isinstance(e, dict) and isinstance(e.get("detail"), str)
               and e["detail"] in said
               for e in errors)


#: A 404 is an ABSENCE only when the registry itself said so, in the
#: shape that registry actually uses. Accepting the mere PRESENCE of a
#: key was not enough: a JSON-speaking proxy answering
#: {"message": "blocked by proxy"} has the same shape as GitHub's
#: not-found, and was reported as an absence — recreating the exact
#: false finding this file exists to prevent (Codex, PR #39).
NOT_FOUND = {
    "crates.io": _crates_not_found,
    "api.github.com": lambda body, url: body.get("message") == "Not Found",
}


class Malformed(Exception):
    """A registry value that cannot be read as the measurement it claims."""


#: Parsers, not predicates: each returns the TYPED value or refuses.
#: Three rounds of review on this file each checked one layer deeper —
#: the key is present, then its type, then its content — and each time
#: the next reader found the layer below. So the shape is declared once
#: and every field goes through it: a field cannot be added without
#: deciding what a valid value looks like, and nothing downstream can be
#: handed a string where it expected a number (Codex, PR #39, round
#: three).

def _count(value):
    # bool is an int in Python, and True is not a download count.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Malformed(f"not a count: {value!r}")
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise Malformed(f"not a non-empty string: {value!r}")
    return value


def _moment(value):
    """An instant that can be subtracted from `now`.

    A naive timestamp is refused rather than assumed to be UTC: mixed
    with an aware `now` it raises TypeError inside the row builder,
    which ABORTS the whole audit instead of degrading one row.
    """
    if not isinstance(value, str):
        raise Malformed(f"not a timestamp: {value!r}")
    try:
        when = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Malformed(f"not an ISO timestamp: {value!r}") from exc
    if when.tzinfo is None:
        raise Malformed(f"timestamp carries no offset: {value!r}")
    return when


def _flag(value):
    if not isinstance(value, bool):
        raise Malformed(f"not a flag: {value!r}")
    return value


def _url_or_blank(value):
    # Absent and null both mean "the registry named no repository",
    # which is ordinary. A non-string is not.
    if value is None:
        return ""
    if not isinstance(value, str):
        raise Malformed(f"not a URL: {value!r}")
    return value


#: (reported name, registry key, parser, default). A default of
#: REQUIRED means an absent key makes the document incomplete; a
#: reported name of None means the field must be valid but is not part
#: of the row — `full_name` proves the document is the repository's.
REQUIRED = object()

CRATE_FIGURES = (
    ("version",    "max_version", _text,         REQUIRED),
    ("released",   "updated_at",  _moment,       REQUIRED),
    ("downloads",  "downloads",   _count,        REQUIRED),
    ("repository", "repository",  _url_or_blank, ""),
)

REPO_FIGURES = (
    (None,       "full_name",        _text,   REQUIRED),
    ("stars",    "stargazers_count", _count,  REQUIRED),
    ("pushed",   "pushed_at",        _moment, REQUIRED),
    ("archived", "archived",         _flag,   False),
)


def figures(document, spec):
    """Typed measurements, or None when the answer is not one.

    None is the caller's cue to report UNREACHABLE. Presence is still
    the test for whether the registry ANSWERED — a brand-new crate
    legitimately has 0 downloads — but a key whose value cannot be read
    is not an answer either, and filling the gap with 0 and None
    fabricates figures a reader is asked to judge.
    """
    if not isinstance(document, dict):
        return None
    row = {}
    for name, key, parse, default in spec:
        if key not in document:
            if default is REQUIRED:
                return None
            value = default
        else:
            try:
                value = parse(document[key])
            except Malformed:
                return None
        if name is not None:
            row[name] = value
    return row


def _fetch(url):
    """Ask one registry. Returns a Reply; never raises on the network."""
    if not url.startswith("https://"):
        # urlopen honours file: and custom schemes. Nothing here should
        # ever reach one, so a URL that is not https is a bug in the
        # roster, not a fetch to attempt.
        raise ValueError(f"refusing a non-https URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            return Reply(UNREACHABLE)
        try:
            body = json.load(error)
        except ValueError:
            return Reply(UNREACHABLE)
        host = urllib.parse.urlsplit(url).netloc
        recognises = NOT_FOUND.get(host)
        if not isinstance(body, dict) or recognises is None \
                or not recognises(body, url):
            return Reply(UNREACHABLE)
        # NOTE: an unauthenticated GitHub 404 is also what an existing
        # PRIVATE repository returns. This cannot be told apart without
        # a token, so the page's legend says so rather than the row
        # asserting an absence it cannot know.
        return Reply(ABSENT, body)
    except Exception:                                          # noqa: BLE001
        # Any transport failure is UNREACHABLE, never ABSENT: the
        # difference between "the registry says no" and "we could not
        # ask" is the whole point of this file.
        return Reply(UNREACHABLE)
    if not isinstance(body, dict):
        return Reply(UNREACHABLE)
    return Reply(OK, body)


def _age(when, now):
    """Format an already-parsed instant. It cannot raise.

    It used to take the registry's raw string and parse it here, which
    put a `ValueError` on a malformed timestamp — and a `TypeError` on a
    naive one — inside the row builder, where it aborted the WHOLE audit
    rather than costing one row. Parsing belongs to `_moment`, which
    refuses; this only renders.
    """
    return f"{(now - when).days}d"


def crate_row(name, fetch, now):
    reply = fetch(f"https://crates.io/api/v1/crates/{name}")
    if reply.state != OK:
        return {"state": reply.state}
    figured = figures(reply.body.get("crate"), CRATE_FIGURES)
    if figured is None:
        return {"state": UNREACHABLE}
    return {"state": OK, **figured,
            "released": _age(figured["released"], now)}


def repo_row(slug, fetch, now):
    reply = fetch(f"https://api.github.com/repos/{slug}")
    if reply.state != OK:
        return {"state": reply.state}
    figured = figures(reply.body, REPO_FIGURES)
    if figured is None:
        return {"state": UNREACHABLE}
    return {"state": OK, **figured,
            "pushed": _age(figured["pushed"], now)}


def audit(roster=None, fetch=None, now=None, pace=None):
    """Measure every roster entry. Pure apart from `fetch`, so it tests.

    Every default resolves HERE rather than in the signature, so a test
    can patch the module attribute and have the call site read it. A
    default bound at def time cannot be patched, which is the shape
    that makes a seam look injectable while it is not.
    """
    roster = ROSTER if roster is None else roster
    fetch = _fetch if fetch is None else fetch
    pace = PACE if pace is None else pace
    now = now or datetime.now(timezone.utc)
    sections = []
    for heading, entries in roster:
        rows = []
        for name, crate, slug, verdict, why in entries:
            row = {"name": name, "verdict": verdict, "why": why,
                   "crate": None, "repo": None}
            if crate:
                row["crate"] = crate_row(crate, fetch, now)
                time.sleep(pace)
            if slug:
                row["repo"] = repo_row(slug, fetch, now)
                time.sleep(pace)
            rows.append(row)
        sections.append((heading, rows))
    return sections


def reachable(sections):
    """How many rows got a real answer. Zero means do not write a page."""
    return sum(
        1 for _, rows in sections for row in rows
        for side in (row["crate"], row["repo"])
        if side and side["state"] != UNREACHABLE)


def render(sections, head, branch, now):
    out = ["# External tool roster, measured", "",
           (f"Generated at `{head}` (branch `{branch}`), measured "
            f"{now.isoformat(timespec='seconds')}."), "",
           ("Every figure here was fetched from crates.io and the GitHub "
            "API at generation time. `ABSENT` means the registry itself "
            "answered not-found — a finding about the name. `UNREACHABLE` "
            "means the fetch failed and the row proves nothing. Note that "
            "an unauthenticated GitHub 404 is also what an existing "
            "PRIVATE repository returns."), ""]
    for heading, rows in sections:
        out += [f"## {heading}", ""]
        for row in rows:
            out.append(f"### {row['name']} — {row['verdict']}")
            out.append("")
            out.append(row["why"] + ".")
            out.append("")
            crate, repo = row["crate"], row["repo"]
            if crate:
                if crate["state"] == OK:
                    out.append(
                        f"- crate `v{crate['version']}`, released "
                        f"{crate['released']} ago, "
                        f"{crate['downloads']:,} downloads")
                    if crate["repository"]:
                        out.append(f"- `{crate['repository']}`")
                else:
                    out.append(f"- crate **{crate['state']}**")
            if repo:
                if repo["state"] == OK:
                    flag = " **ARCHIVED**" if repo["archived"] else ""
                    out.append(
                        f"- repo {repo['stars']:,} stars, pushed "
                        f"{repo['pushed']} ago{flag}")
                else:
                    out.append(f"- repo **{repo['state']}**")
            out.append("")
    return "\n".join(out) + "\n"


def git(*argv):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              cwd=REPO, check=False)
    except OSError:
        return "(unavailable: git)"
    return proc.stdout.strip() if proc.returncode == 0 else "(unavailable: git)"


UNAVAILABLE = "(unavailable: git)"


def head_stamp():
    """The commit this report may claim it was generated at.

    `rev-parse` answers the same SHA whether or not the generator has
    uncommitted edits, so a report built from a modified roster named a
    commit whose tree cannot reproduce it — a figure with nothing behind
    it, which is the whole thing this file argues against (Codex, PR #39
    round two).

    The marker is scoped to THIS file rather than the worktree: the
    roster and the generator are both in it, so an unrelated edit
    elsewhere does not make this report irreproducible, and refusing on
    one would make the command unusable exactly while it is being
    worked on.
    """
    head = git("git", "rev-parse", "--short", "HEAD")
    if head == UNAVAILABLE:
        return head
    self = Path(__file__).resolve().relative_to(REPO)
    dirty = git("git", "status", "--porcelain", "--", str(self))
    if dirty == UNAVAILABLE or not dirty:
        return head
    return f"{head}-dirty"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="prove the roster parses without a network")
    args = parser.parse_args(argv)
    if args.offline:
        total = sum(len(entries) for _, entries in ROSTER)
        print(f"roster parses: {len(ROSTER)} sections, {total} tools")
        return 0
    now = datetime.now(timezone.utc)
    sections = audit(now=now)
    live = reachable(sections)
    if not live:
        # A report of UNREACHABLE rows still reads as an audit at a
        # glance, so there is no report rather than a misleading one.
        print("nothing was reachable: no report", file=sys.stderr)
        return 1
    print(render(sections, head_stamp(),
                 git("git", "rev-parse", "--abbrev-ref", "HEAD"), now))
    tools = sum(len(entries) for _, entries in ROSTER)
    # "rows" conflated two different counts: reachable() counts registry
    # LOOKUPS (a tool with both a crate and a repo is two), while the
    # roster has one row per tool (Codex, PR review of 5387cd2).
    print(f"-- {live} lookups answered across {tools} tools",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
