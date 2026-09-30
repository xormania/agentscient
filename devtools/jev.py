"""Provider evaluations selected through the trusted operator adapter manifest.

Evaluation factories accept (transport, connection) and return an object with
evaluate(state, questions, model). Results use the checked_response contract;
provider-specific wire formats and model names belong to the adapter. Missing
credentials and transport outages raise JevUnavailable; malformed policy and
responses remain ValueError. Credentials and destinations are never MCP inputs.
"""

from __future__ import annotations

import http.client
import json
import math
import re
import time
import urllib.error
import urllib.request

from .adapters import factory
from .configuration import defaults, validate_connection
from .credentials import CredentialUnavailable, read_credential
from .github_http import NoRedirect
from .jev_config import clean_questions, validate_questions
from .telemetry import clean

DEFAULTS = defaults()
MODEL = DEFAULTS["model"]
MAX_REQUEST = DEFAULTS["transport"]["max_request_bytes"]
MAX_RESPONSE = DEFAULTS["transport"]["max_response_bytes"]


class JevUnavailable(ValueError):
    """Credentials or provider transport are unavailable; no evaluation was obtained."""


def number(value, low=0, high=1):
    return type(value) in {int, float} and math.isfinite(value) and low <= value <= high


def checked_response(value, questions, model):
    """Reject unknown choices and malformed scores before retaining or recommending them."""
    if not isinstance(value, dict) or value.get("model") != model:
        raise ValueError("Jev returned an unexpected model version.")
    answers = value.get("answers")
    if not isinstance(answers, dict) or answers.keys() != questions.keys():
        raise ValueError("Jev returned an incomplete evaluation.")
    checked = {}
    for name, question in questions.items():
        answer = answers[name]
        kind = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise ValueError("Jev returned an invalid answer type.")
        if kind == "noul":
            if not number(answer.get("noul")):
                raise ValueError("Jev returned an invalid probability.")
            checked[name] = {"type": kind, "noul": answer["noul"]}
            continue
        options = (set(question["criteria"]) if kind == "choice"
                   else {str(i) for i in range(len(question["criteria"]))})
        probabilities = answer.get("probabilities")
        if (not isinstance(probabilities, dict) or probabilities.keys() != options
                or not all(number(p) for p in probabilities.values())
                or abs(sum(probabilities.values()) - 1) > 0.01 or not number(answer.get("confidence"))):
            raise ValueError("Jev returned an invalid probability distribution.")
        selected = answer.get("choice" if kind == "choice" else "score")
        if (kind == "choice" and (not isinstance(selected, str) or selected not in options)) or (
            kind == "score" and not number(selected, 0, len(options) - 1)
        ):
            raise ValueError("Jev returned an invalid choice or score.")
        checked[name] = {"type": kind, "choice" if kind == "choice" else "score": selected,
                         "probabilities": probabilities, "confidence": answer["confidence"]}
        if kind == "score":
            legend = {str(i): label for i, label in enumerate(question["criteria"])}
            if answer.get("legend") != legend:
                raise ValueError("Jev returned an invalid score legend.")
            checked[name]["legend"] = legend
    usage = value.get("usage")
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                          for k in ("input_tokens", "output_tokens")):
        raise ValueError("Jev returned invalid usage data.")
    return {"model": model, "answers": checked,
            "usage": {k: usage[k] for k in ("input_tokens", "output_tokens")}}


class TypeSafeAdapter:
    """The TypeSafe wire protocol, selected by its registered adapter name."""

    def __init__(self, settings, connection):
        self.settings, self.connection = settings, connection

    def evaluate(self, state, questions, model=MODEL):
        if not isinstance(model, str) or not re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", model):
            raise ValueError("The TypeSafe adapter requires a pinned Jev model version, for example jev-1.13.0.")
        validate_questions(questions)
        try:
            key = read_credential(self.connection["credential"])
        except CredentialUnavailable as error:
            raise JevUnavailable(str(error)) from None
        state = clean(state, secrets=(key,))
        questions = clean_questions(questions, secrets=(key,))
        validate_questions(questions)
        payload = json.dumps({"model": model, "state": state, "questions": questions},
                             ensure_ascii=False, allow_nan=False).encode()
        if len(payload) > self.settings["max_request_bytes"]:
            raise ValueError("Assessment exceeds the Jev input budget; use fewer candidates or smaller ranges.")
        opener = urllib.request.build_opener(NoRedirect())
        for attempt in range(self.settings["max_attempts"]):
            request = urllib.request.Request(self.connection["endpoint"], data=payload, method="POST", headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json",
                "Accept": "application/json", "User-Agent": "Agentscient-MCP",
            })
            try:
                with opener.open(request, timeout=self.settings["timeout"]) as response:
                    body = response.read(self.settings["max_response_bytes"] + 1)
                if len(body) > self.settings["max_response_bytes"]:
                    raise ValueError("Jev response exceeds the evaluation size limit.")
                try:
                    value = json.loads(body)
                except (ValueError, UnicodeError):
                    raise ValueError("Jev returned invalid JSON.") from None
                return checked_response(value, questions, model)
            except urllib.error.HTTPError as error:
                status = error.code
                fallback = self.settings["retry_delay"] * 2 ** attempt
                retry = error.headers.get("Retry-After", str(fallback)) if error.headers else str(fallback)
                error.close()
                try:
                    delay = float(retry)
                except ValueError:
                    delay = float("inf")  # A dated/long retry belongs to a later explicit request.
                if (attempt + 1 < self.settings["max_attempts"] and status in self.settings["retry_statuses"]
                        and number(delay, 0, self.settings["max_retry_delay"])):
                    time.sleep(min(self.settings["max_retry_delay"], max(fallback, delay)))
                    continue
                raise JevUnavailable(f"Jev is unavailable (HTTP {status}); use normal inspection or try later.") from None
            except (OSError, urllib.error.URLError, http.client.HTTPException):
                raise JevUnavailable("Jev could not be reached; use normal inspection or try later.") from None


class Jev:
    """Evaluate through the operator-selected, installed provider adapter."""

    def __init__(self, settings=None, connection=None):
        policy = defaults()
        self.settings = policy["transport"] if settings is None else settings
        self.connection = validate_connection(policy["connection"] if connection is None else connection)
        self.model = policy["model"]
        adapter = factory("evaluation", self.connection["adapter"])
        self.adapter = adapter(self.settings, self.connection)
        if not callable(getattr(self.adapter, "evaluate", None)):
            raise ValueError("Evaluation adapters must provide evaluate(state, questions, model).")

    def evaluate(self, state, questions, model=None):
        return self.adapter.evaluate(state, questions, self.model if model is None else model)
