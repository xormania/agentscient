"""Runner-side advisory diagnosis; shares the dev-lane Jev transport and redaction."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from devtools.jev import Jev, checked_response, number  # noqa: E402
from devtools.jev_config import load as load_jev  # noqa: E402
from devtools.telemetry import clean  # noqa: E402

DEFAULT = Path(__file__).with_name("jev-ci.json")
NOTE = "Advisory hypothesis from bounded evidence; the original CI failure is unchanged."


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def load_config(path):
    value = json.loads(path.read_text())
    required = {"version", "enabled", "jev_policy", "min_confidence", "limits", "error_pattern",
                "evidence_patterns", "failure_question", "excerpt_instructions"}
    if not isinstance(value, dict) or value.keys() != required or value["version"] != 1:
        raise ValueError("Unsupported CI Jev policy.")
    if type(value["enabled"]) is not bool or not number(value["min_confidence"]):
        raise ValueError("Invalid CI enablement or confidence setting.")
    bounds = {"log_bytes": (1000, 8388608), "candidates": (1, 16), "excerpt_lines": (1, 100),
              "before_lines": (0, 99), "excerpt_bytes": (100, 8000), "evidence_files": (0, 16),
              "evidence_events": (1, 100),
              "evidence_read_bytes": (1000, 1048576), "evidence_bytes": (100, 8000)}
    limits = value["limits"]
    if not isinstance(limits, dict) or limits.keys() != bounds.keys():
        raise ValueError("Invalid CI evidence limits.")
    for name, (low, high) in bounds.items():
        if type(limits[name]) is not int or not low <= limits[name] <= high:
            raise ValueError("Invalid CI evidence limit.")
    if limits["before_lines"] >= limits["excerpt_lines"]:
        raise ValueError("Context before the match must fit in the excerpt.")
    re.compile(value["error_pattern"])
    patterns = value["evidence_patterns"]
    if not isinstance(patterns, list) or any(not isinstance(p, str) or not p or p.startswith("/")
                                            or ".." in Path(p).parts for p in patterns):
        raise ValueError("Evidence patterns must be relative.")
    question = value["failure_question"]
    if (not isinstance(question, dict) or question.keys() != {"type", "instructions", "criteria"}
            or question["type"] != "choice" or not isinstance(question["criteria"], dict)
            or not 2 <= len(question["criteria"]) <= 16 or "unknown" not in question["criteria"]
            or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", k) or not isinstance(v, str) or not v
                   for k, v in question["criteria"].items())):
        raise ValueError("Failure classification needs Choice criteria including unknown.")
    for text in (question["instructions"], value["excerpt_instructions"]):
        if not isinstance(text, str) or not 1 <= len(text) <= 2000:
            raise ValueError("CI questions need bounded instructions.")
    policy = load_jev(path.parent, {"policy_file": value["jev_policy"]})
    return value, policy


def clipped(text, limit):
    data = text.encode()
    return data[:limit].decode("utf-8", errors="ignore"), len(data) > limit


def read_regular(path, limit, *, tail=False):
    """Never follow an evidence symlink or block on a pipe/device."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Expected a regular evidence file.")
        if tail and info.st_size > limit:
            source.seek(-limit, os.SEEK_END)
        data = source.read(limit + 1)
        if tail and info.st_size > limit:
            # The first record may start before this byte window.
            return data.partition(b"\n")[2].decode("utf-8", errors="replace"), True
    return data[:limit].decode("utf-8", errors="replace"), len(data) > limit


def collect(log, evidence, config):
    limits = config["limits"]
    text, partial = read_regular(log, limits["log_bytes"])
    # Scrub complete lines before truncating; keep their original line numbers.
    lines = [clean(line) for line in text.splitlines()]
    pattern = re.compile(config["error_pattern"])
    starts = []
    for index, line in enumerate(lines):
        if pattern.search(line):
            start = max(0, index - limits["before_lines"])
            if not starts or start >= starts[-1] + limits["excerpt_lines"]:
                starts.append(start)
    if lines and not starts:
        starts = [max(0, len(lines) - limits["excerpt_lines"])]
    # Preserve early causes as well as late failures when there are many matches.
    total = len(starts)
    maximum = limits["candidates"]
    if total > maximum:
        first = (maximum + 1) // 2
        starts = starts[:first] + (starts[-(maximum - first):] if maximum > first else [])
    candidates = []
    for index, start in enumerate(starts):
        excerpt, cut = clipped("\n".join(lines[start:start + limits["excerpt_lines"]]), limits["excerpt_bytes"])
        candidates.append({"id": "excerpt_" + str(index), "line_start": start + 1,
                           "line_end": start + max(1, len(excerpt.splitlines())), "text": excerpt,
                           "partial": cut})
    records, omitted = [], 0
    if evidence and evidence.is_dir() and not evidence.is_symlink():
        paths = sorted({path for p in config["evidence_patterns"] for path in evidence.glob(p)})
        for path in paths:
            relative = path.relative_to(evidence)
            # Exclude intermediate symlinks as well as linked files within the evidence root.
            if any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(evidence)):
                omitted += 1
                continue
            if len(records) >= limits["evidence_files"]:
                omitted += 1
                continue
            try:
                is_trace = path.suffix == ".jsonl"
                content, truncated = read_regular(path, limits["evidence_read_bytes"], tail=is_trace)
                if is_trace:
                    rows = [clean(json.loads(line)) for line in content.splitlines() if line.strip()]
                    truncated |= len(rows) > limits["evidence_events"]
                    content = encode(rows[-limits["evidence_events"]:]).decode()
                else:
                    if truncated:
                        raise ValueError("Incomplete JSON evidence.")
                    content = encode(clean(json.loads(content))).decode()
                content, cut = clipped(content, limits["evidence_bytes"])
                truncated |= cut
            except (OSError, ValueError):
                omitted += 1
                continue
            records.append({"path": str(relative), "text": content, "partial": truncated,
                            "selection": "latest_events" if is_trace else "document"})
    return {"log": {"name": log.name, "partial": partial, "read_lines": len(lines),
                    "omitted_candidates": total - len(candidates)},
            "candidates": candidates, "runtime_evidence": records, "omitted_evidence_files": omitted}


def questions_for(state, config):
    choices = {c["id"]: f"Supplied log lines {c['line_start']}-{c['line_end']}" for c in state["candidates"]}
    choices["none"] = "No supplied excerpt usefully identifies the original failure."
    return {"failure_kind": config["failure_question"], "causal_excerpt": {
        "type": "choice", "instructions": config["excerpt_instructions"], "criteria": choices}}


def request_for(state, config, policy):
    while True:
        request = {"model": policy["model"], "state": state, "questions": questions_for(state, config)}
        if len(json.dumps(request, ensure_ascii=False, allow_nan=False).encode()) <= policy["transport"]["max_request_bytes"]:
            return request
        if state["runtime_evidence"]:
            state["runtime_evidence"].pop()
            state["omitted_evidence_files"] += 1
        elif len(state["candidates"]) > 1:
            state["candidates"].pop()
            state["log"]["omitted_candidates"] += 1
        else:
            raise ValueError("Even one excerpt exceeds the request budget.")


def assess(log, evidence, job, config_path=DEFAULT, client=None):
    started = time.monotonic()
    result = {"version": 1, "status": "unavailable", "note": NOTE, "job": job,
              "context": {key: os.environ.get(key, "") for key in
                          ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")}}
    try:
        config, policy = load_config(config_path)
        result["policy"] = {"ci": config, "jev": policy}
        if not config["enabled"]:
            result.update(status="disabled", reason="disabled_by_configuration")
            return result
        if not os.environ.get("TYPESAFE_API_KEY"):
            result["reason"] = "missing_TYPESAFE_API_KEY"
            return result
        state = collect(log, evidence, config)
        state["job"] = job
        if not state["candidates"]:
            result["reason"] = "no_log_evidence"
            return result
        request = request_for(state, config, policy)
        result["request"] = request
        result["input_sha256"] = hashlib.sha256(encode({"request": request, "policy": result["policy"]})).hexdigest()
        provider = client or Jev(policy["transport"])
        response = provider.evaluate(state, request["questions"], policy["model"])
        response = checked_response(response, request["questions"], policy["model"])
        answers = response["answers"]
        classification = answers["failure_kind"]
        selection = answers["causal_excerpt"]
        selected = next((c for c in state["candidates"] if c["id"] == selection["choice"]), None)
        result.update(status="assessed", response=response,
                      likely_cause=classification["choice"] if classification["confidence"] >= config["min_confidence"] else "unknown",
                      selected_excerpt=selected if selection["confidence"] >= config["min_confidence"] else None)
    except Exception as error:
        # Diagnostics must not change a test verdict or expose provider/log exception text.
        result["reason"] = "assessment_unavailable"
        result["error_type"] = type(error).__name__
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def command_escape(text):
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def publish(result, directory):
    directory.mkdir(parents=True, exist_ok=True)
    result = clean(result)
    (directory / "assessment.json").write_bytes(encode(result) + b"\n")
    summary = "### Jev CI diagnosis: " + html.escape(result["job"]) + "\n\n" + NOTE + "\n\n"
    if result["status"] == "assessed":
        answers = result["response"]["answers"]
        message = f"Likely cause: {result['likely_cause']} (classifier confidence {answers['failure_kind']['confidence']:.2f})."
        summary += message + "\n\n"
        selected = result["selected_excerpt"]
        if selected:
            location = f"Selected log lines {selected['line_start']}-{selected['line_end']}"
            summary += location + ":\n\n<pre>" + html.escape(selected["text"]) + "</pre>\n"
            message += "\n" + location + ":\n" + selected["text"]
        else:
            summary += "No excerpt selected with sufficient confidence.\n"
        print("::warning title=Jev CI diagnosis::" + command_escape(NOTE + "\n" + message))
    else:
        summary += "Assessment " + result["status"] + ": " + result.get("reason", "unknown") + ".\n"
        print("Jev CI: " + result["status"] + " (" + result.get("reason", "unknown") + ").")
    (directory / "summary.md").write_text(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
            output.write(summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT)
    args = parser.parse_args()
    publish(assess(args.log, args.evidence, args.job, args.config), args.output)


if __name__ == "__main__":
    main()
