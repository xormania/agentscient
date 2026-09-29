"""Bounded TypeSafe evaluations. Credentials and HTTP destinations are never MCP inputs."""

from __future__ import annotations

import http.client
import json
import math
import os
import time
import urllib.error
import urllib.request

from .github_http import NoRedirect

MODEL = "jev-1.13.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MAX_REQUEST = 28000
MAX_RESPONSE = 128 * 1024


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
    usage = value.get("usage")
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                          for k in ("input_tokens", "output_tokens")):
        raise ValueError("Jev returned invalid usage data.")
    return {"model": model, "answers": checked,
            "usage": {k: usage[k] for k in ("input_tokens", "output_tokens")}}


class Jev:
    def evaluate(self, state, questions, model=MODEL):
        payload = json.dumps({"model": model, "state": state, "questions": questions},
                             ensure_ascii=False, allow_nan=False).encode()
        if len(payload) > MAX_REQUEST:
            raise ValueError("Assessment exceeds the Jev input budget; use fewer candidates or smaller ranges.")
        key = os.environ.get("TYPESAFE_API_KEY", "")
        if not key or any(c.isspace() for c in key):
            raise ValueError("The operator must set TYPESAFE_API_KEY for the dev-lane service.")
        opener = urllib.request.build_opener(NoRedirect())
        for attempt in range(2):
            request = urllib.request.Request(ENDPOINT, data=payload, method="POST", headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json",
                "Accept": "application/json", "User-Agent": "Agentscient-MCP",
            })
            try:
                with opener.open(request, timeout=8) as response:
                    body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise ValueError("Jev response exceeds the evaluation size limit.")
                try:
                    value = json.loads(body)
                except (ValueError, UnicodeError):
                    raise ValueError("Jev returned invalid JSON.") from None
                return checked_response(value, questions, model)
            except urllib.error.HTTPError as error:
                status = error.code
                retry = error.headers.get("Retry-After", "0.25") if error.headers else "0.25"
                error.close()
                try:
                    delay = float(retry)
                except ValueError:
                    delay = 3  # A dated/long retry belongs to a later explicit request.
                if not attempt and status in {429, 529} and number(delay, 0, 2):
                    time.sleep(max(0.25, delay))
                    continue
                raise ValueError(f"Jev is unavailable (HTTP {status}); use normal inspection or try later.") from None
            except (OSError, urllib.error.URLError, http.client.HTTPException):
                raise ValueError("Jev could not be reached; use normal inspection or try later.") from None
