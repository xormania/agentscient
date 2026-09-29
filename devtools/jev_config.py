"""Operator-owned Jev settings and rubrics; no policy is accepted from agent arguments."""

import json
import math
import re
from pathlib import Path

DEFAULT = Path(__file__).with_name("jev.json")


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
    for name, question in questions.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", name) or not isinstance(question, dict):
            raise ValueError("Invalid scope question name or definition.")
        kind = question.get("type")
        if kind not in {"noul", "choice", "score"} or set(question) - {"type", "instructions", "criteria"}:
            raise ValueError("Scope questions must use the TypeSafe question format.")
        if not isinstance(question.get("instructions"), str) or not 1 <= len(question["instructions"]) <= 2000:
            raise ValueError("Scope questions need bounded instructions.")
        criteria = question.get("criteria")
        if kind == "choice" and (not isinstance(criteria, dict) or not 2 <= len(criteria) <= 16
                                  or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in criteria.items())):
            raise ValueError("Choice criteria need distinct names and descriptions.")
        if kind == "score" and (not isinstance(criteria, list) or not 2 <= len(criteria) <= 10
                                 or any(not isinstance(v, str) or not v for v in criteria)):
            raise ValueError("Score criteria need two to ten level descriptions.")
        if kind == "noul" and criteria is not None:
            raise ValueError("Omit criteria for the configured noul questions.")
    return value
