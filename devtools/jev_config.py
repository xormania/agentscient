"""Operator-owned Jev settings and rubrics; no policy is accepted from agent arguments."""

import json
import math
import re
from pathlib import Path

DEFAULT = Path(__file__).with_name("jev.json")


def _bounded_json(value, max_bytes):
    """Bound JSON before encoding, including direct Python callers and nested entries."""
    remaining = 512

    def visit(item, depth=0):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 8:
            raise ValueError("Jev entries exceed their structure budget.")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 200 or "\0" in key:
                    raise ValueError("Jev entry keys must be bounded text.")
                visit(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
        elif isinstance(item, str):
            if len(item) > 6000 or "\0" in item:
                raise ValueError("Jev entry text exceeds its bounds.")
        elif item is not None and type(item) is not bool:
            if type(item) not in {int, float} or not math.isfinite(item):
                raise ValueError("Jev entries must contain finite JSON values.")

    try:
        visit(value)
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf8")
    except (OverflowError, UnicodeError, RecursionError):
        raise ValueError("Jev entries must contain bounded JSON values.") from None
    if len(encoded) > max_bytes:
        raise ValueError("Jev entries exceed their byte budget.")


def validate_entry(value):
    """TypeSafe EntryType: text, object, array or null, with finite JSON inside."""
    if value is not None and type(value) not in {str, dict, list}:
        raise ValueError("Jev entries must be text, an object, an array or null.")
    _bounded_json(value, 6000)
    return value


def validate_question(value):
    """Validate the shared wire format without flattening structured rubrics."""
    if (not isinstance(value, dict) or not {"type", "instructions"} <= value.keys()
            or value.keys() - {"type", "instructions", "criteria"}):
        raise ValueError("Questions must use the TypeSafe question format.")
    kind = value["type"]
    if not isinstance(kind, str) or kind not in {"noul", "choice", "score"}:
        raise ValueError("Questions must use a supported Jev primitive.")
    validate_entry(value["instructions"])
    criteria = value.get("criteria")
    if kind == "noul":
        if criteria is not None:
            if not isinstance(criteria, dict) or criteria.keys() != {"true", "false"}:
                raise ValueError("Noul criteria need true and false descriptions.")
            for item in criteria.values():
                validate_entry(item)
    elif kind == "choice":
        # One unknown option is valid for system assignment advice with no available profiles.
        if (not isinstance(criteria, dict) or not 1 <= len(criteria) <= 32
                or any(not isinstance(key, str) or not 1 <= len(key) <= 80 or "\0" in key
                       for key in criteria)):
            raise ValueError("Choice criteria need bounded, distinct names and descriptions.")
        for item in criteria.values():
            validate_entry(item)
    else:
        if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
            raise ValueError("Score criteria need two to ten level descriptions.")
        for item in criteria:
            validate_entry(item)
    _bounded_json(value, 8000)
    return value


def validate_questions(value, max_questions=32):
    if not isinstance(value, dict) or not 1 <= len(value) <= max_questions:
        raise ValueError("Supply a bounded set of Jev questions.")
    for name, question in value.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", name):
            raise ValueError("Invalid Jev question name.")
        validate_question(question)
    # Per-question bounds permit batches; the transport separately bounds state plus questions.
    try:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf8"))
    except (OverflowError, UnicodeError, RecursionError):
        raise ValueError("Jev questions must contain bounded JSON values.") from None
    if size > 44000:
        raise ValueError("Jev questions exceed their batch budget.")
    return value


def load(directory=None, config=None):
    config = config or {}
    path = Path(config.get("policy_file", DEFAULT))
    if not path.is_absolute():
        path = Path(directory) / path
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        raise ValueError("The operator must supply a readable Jev policy JSON file.") from None
    if not isinstance(value, dict) or set(value) != {"version", "model", "transport", "scope"} or value["version"] != 1:
        raise ValueError("Unsupported Jev policy format; start from devtools/jev.json.")
    value["model"] = config.get("model", value["model"])
    if not isinstance(value["model"], str) or not re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", value["model"]):
        raise ValueError("Configure a pinned Jev model version, for example jev-1.13.0.")
    transport = value["transport"]
    bounds = {"timeout": (0.1, 60), "max_attempts": (1, 3), "retry_delay": (0, 5),
              "max_retry_delay": (0, 5), "max_request_bytes": (1000, 48000),
              "max_response_bytes": (1000, 131072)}
    if not isinstance(transport, dict) or transport.keys() != bounds.keys():
        raise ValueError("Jev transport settings do not match the policy format.")
    for key, (low, high) in bounds.items():
        number = transport[key]
        if type(number) not in {int, float} or not math.isfinite(number) or not low <= number <= high:
            raise ValueError("Invalid Jev transport setting: " + key)
        if key in {"max_attempts", "max_request_bytes", "max_response_bytes"} and type(number) is not int:
            raise ValueError("Jev counts and byte limits must be integers.")
    rubric = value["scope"]
    if not isinstance(rubric, dict) or set(rubric) != {"version", "questions"} or type(rubric["version"]) is not int or rubric["version"] < 1:
        raise ValueError("Scope rubric needs a positive version and questions.")
    questions = rubric["questions"]
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 4:
        raise ValueError("Scope rubric needs one to four questions.")
    validate_questions(questions, max_questions=4)
    for question in questions.values():
        if question["type"] == "choice" and not 2 <= len(question["criteria"]) <= 16:
            raise ValueError("Configured choice criteria need two to sixteen options.")
    return value
