"""OpenAI-compatible JSON-mode client with hard call budget, retry/backoff and model fallback."""
import json
import re
import time

from openai import APIError, OpenAI, RateLimitError

from . import config


class BudgetExceeded(Exception):
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


def call(system, user, required=()):
    global _calls
    last = None
    client = None
    for model in (config.MODEL, config.FALLBACK_MODEL):
        for attempt in range(3):
            if _calls >= config.MAX_LLM_CALLS:
                raise BudgetExceeded(f"LLM call budget ({config.MAX_LLM_CALLS}) exhausted")
            if not config.llm_key():
                raise RuntimeError("No LLM credentials: set GITHUB_TOKEN (Actions provides it) or LLM_API_KEY")
            _calls += 1
            try:
                client = client or OpenAI(base_url=config.BASE_URL, api_key=config.llm_key(), timeout=90, max_retries=0)
                r = client.chat.completions.create(
                    model=model, temperature=0.4, response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                data = _parse(r.choices[0].message.content)
                missing = [k for k in required if k not in data]
                if missing:
                    raise ValueError(f"missing keys: {missing}")
                return data
            except RateLimitError as e:
                last = e
                time.sleep(min(45, 8 * 2 ** attempt))
            except (APIError, ValueError, json.JSONDecodeError) as e:
                last = e
                time.sleep(2)
    raise RuntimeError(f"LLM failed after retries: {type(last).__name__}")
