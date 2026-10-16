import json

import pytest

from agent import llm


@pytest.fixture(autouse=True)
def fresh():
    llm.reset()


class _Resp:
    def __init__(self, status=200, payload=None, text=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload, headers or {}
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def _ok(content):
    return _Resp(200, {"choices": [{"message": {"content": content}}]})


def test_llm_http_success_and_headers(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "tok")
    seen = {}
    def post(url, headers=None, json=None, timeout=0):
        seen.update(url=url, headers=headers, body=json)
        return _ok('{"a": 1}')
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.call("s", "u", ("a",)) == {"a": 1}
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer tok"
    assert seen["body"]["model"] == "openai/gpt-oss-120b" and seen["body"]["response_format"] == {"type": "json_object"}


def test_llm_http_retries_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "tok")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    answers = iter([_Resp(429, {}, "slow down", {"retry-after": "1"}), _ok('{"a": 2}')])
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: next(answers))
    assert llm.call("s", "u")["a"] == 2


def test_llm_http_reports_server_text_on_garbage(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "tok")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(200, None, "<html>nope</html>"))
    with pytest.raises(llm.LLMError) as e:
        llm.call("s", "u")
    assert "nope" in str(e.value)


def test_llm_auth_error_fails_fast(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "tok")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(403, {}, "models permission missing"))
    with pytest.raises(llm.LLMError) as e:
        llm.call("s", "u")
    assert "403" in str(e.value) and llm.calls_used() == 1


def test_llm_retries_without_json_mode_when_rejected(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "tok")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    bodies = []
    def post(url, headers=None, json=None, timeout=0):
        bodies.append(dict(json))
        if "response_format" in json:
            return _Resp(400, {}, '{"error":"response_format json_object not supported for this model"}')
        return _ok('```json\n{"a": 3}\n```')
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.call("s", "u")["a"] == 3
    assert "response_format" in bodies[0] and "response_format" not in bodies[1]
    assert bodies[0]["model"] == bodies[1]["model"]


def test_llm_missing_key_is_clear(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.LLMError) as e:
        llm.call("s", "u")
    assert "LLM_API_KEY" in str(e.value) or "GROQ_API_KEY" in str(e.value)
