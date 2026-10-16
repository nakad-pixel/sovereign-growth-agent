"""Chat-completions JSON client (Groq free tier by default; any OpenAI-compatible endpoint) with hard call budget,
retry/backoff, model fallback and JSON-mode fallback.
Uses plain HTTP so failures report exactly what the server said."""
import json
import re
import time

import requests

from . import config


class BudgetExceeded(Exception):
    pass


class LLMError(Exception):
    pass


_calls = 0


def reset():
    global _calls
    _calls = 0


def calls_used():
    return _calls


def _parse(text):
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")
    return data


def _headers():
    return {"Authorization": f"Bearer {config.llm_key()}", "Content-Type": "application/json"}


def _retry_after(resp, attempt):
    try:
        return min(60, max(1, int(float(resp.headers.get("retry-after", "")))))
    except ValueError:
        return min(45, 8 * 2 ** attempt)


def call(system, user, required=()):
    global _calls
    url = config.BASE_URL.rstrip("/") + "/chat/completions"
    last = "no attempt made"
    json_mode = True
    for model in (config.MODEL, config.FALLBACK_MODEL):
        for attempt in range(3):
            if _calls >= config.MAX_LLM_CALLS:
                raise BudgetExceeded(f"LLM call budget ({config.MAX_LLM_CALLS}) exhausted")
            if not config.llm_key():
                raise LLMError("No LLM credentials: set the GROQ_API_KEY repo secret (or LLM_API_KEY)")
            _calls += 1
            body = {"model": model, "temperature": 0.4,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            try:
                r = requests.post(url, headers=_headers(), json=body, timeout=90)
            except requests.RequestException as e:
                last = f"network error: {type(e).__name__}"
                time.sleep(3)
                continue
            snippet = (r.text or "")[:300].replace("\n", " ")
            if r.status_code == 429:
                last = f"HTTP 429 rate limited ({model})"
                time.sleep(_retry_after(r, attempt))
                continue
            if r.status_code in (401, 403):
                raise LLMError(f"auth/permission error HTTP {r.status_code}: {snippet}")
            if r.status_code in (400, 404):
                last = f"HTTP {r.status_code} for {model}: {snippet}"
                if json_mode and "response_format" in snippet.lower():
                    json_mode = False  # this model rejects JSON mode: retry plain, the parser strips fences
                    continue
                break  # model/params not accepted: go straight to the fallback model
            if r.status_code >= 400:
                last = f"HTTP {r.status_code}: {snippet}"
                time.sleep(3)
                continue
            try:
                content = r.json()["choices"][0]["message"]["content"]
                data = _parse(content)
                missing = [k for k in required if k not in data]
                if missing:
                    raise ValueError(f"missing keys: {missing}")
                return data
            except (ValueError, KeyError, IndexError, TypeError) as e:
                last = f"unusable response ({type(e).__name__}): {snippet}"
                time.sleep(2)
    raise LLMError(f"LLM failed: {last}")
