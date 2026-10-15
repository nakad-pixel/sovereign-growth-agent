import json
import shutil
import time

import pytest

from agent import config, guard, learn, llm, memory, poll, state, telegram_io as tg, video


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    (mem / "skills").mkdir(parents=True)
    (mem / "episodes.jsonl").write_text("")
    (mem / "pending.json").write_text("[]")
    monkeypatch.setattr(config, "MEM", mem)
    monkeypatch.setattr(config, "channels", lambda: {
        "chan": {"enabled": True, "type": "manual", "daily_cap": 2, "note": "x"},
        "off": {"enabled": False, "type": "manual"}})
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "SECRETTOKEN")
    llm.reset()


def good(**kw):
    p = {"title": "How to price a roofing lead", "channel": "chan", "caption": "Short caption", "body": "", "video_lines": ["a", "b"]}
    p.update(kw)
    return p


def test_guard_accepts_valid():
    assert guard.validate(guard.clean(good())) == (True, "")


@pytest.mark.parametrize("bad", [
    good(channel="off"), good(channel="nope"), good(title=""),
    good(caption="This is guaranteed income for everyone"),
    good(caption="Totally risk-free way"), good(video_lines=["x" * 200]),
    good(video_lines=["l"] * 11)])
def test_guard_blocks(bad):
    ok, why = guard.validate(guard.clean(bad))
    assert not ok and why


def test_guard_duplicate_and_cap():
    state.remember_title("How to price a roofing lead")
    assert not guard.validate(guard.clean(good()))[0]
    state.record_publish("chan")
    state.add_pending(good(title="other one"))
    ok, why = guard.validate(guard.clean(good(title="third one")))
    assert not ok and "cap" in why


def test_pending_lifecycle_and_expiry():
    item = state.add_pending(good())
    assert state.pop_pending(item["id"])["title"] == good()["title"]
    assert state.pop_pending(item["id"]) is None
    item = state.add_pending(good(title="x2"), now=time.time() - 10 * 24 * 3600)
    assert [e["id"] for e in state.expire_pending()] == [item["id"]]
    assert state.load_pending() == []


def test_memory_search_and_prune():
    memory.add_episode("run", "Roofing affiliate carousel performed well")
    memory.add_episode("run", "Plumbing email flopped")
    assert any("Roofing" in t for t in memory.search("roofing carousel"))
    assert memory.search('"; DROP TABLE') is not None  # hostile query must not crash FTS
    for i in range(30):
        memory.add_episode("run", f"e{i}")
    memory.prune(keep=10)
    assert len(memory.recent(100)) == 10


def test_rung_ladder():
    assert "Rung 0" in learn.rung_text()
    learn.log_metric("revenue", 5)
    assert "Rung 1" in learn.rung_text()
    learn.log_metric("revenue", 200)
    assert "Rung 2" in learn.rung_text()


def test_llm_budget(monkeypatch):
    monkeypatch.setattr(config, "MAX_LLM_CALLS", 0)
    with pytest.raises(llm.BudgetExceeded):
        llm.call("s", "u")


def test_llm_parse_fences():
    assert llm._parse('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError):
        llm._parse("[1]")


def test_telegram_scrub_and_auth():
    assert "SECRETTOKEN" not in tg.scrub("error at /botSECRETTOKEN/send")
    ok = {"message": {"chat": {"id": 42}, "from": {"id": 42}, "text": "/status"}}
    stranger = {"message": {"chat": {"id": 99}, "from": {"id": 99}, "text": "/pause"}}
    cb = {"callback_query": {"id": "1", "data": "ok:abc", "from": {"id": 42}, "message": {"chat": {"id": 42}}}}
    forged = {"callback_query": {"id": "1", "data": "ok:abc", "from": {"id": 7}, "message": {"chat": {"id": 42}}}}
    assert tg.authorised(ok) and tg.authorised(cb)
    assert not tg.authorised(stranger) and not tg.authorised(forged)


def test_poll_commands():
    assert "Paused" in poll.command("/pause")
    assert state.ledger()["paused"] is True
    poll.command("/resume")
    assert state.ledger()["paused"] is False
    assert "Logged" in poll.command("/rev 12.5 sale")
    assert "Usage" in poll.command("/rev abc")


def test_decide_reject_and_approve(monkeypatch):
    monkeypatch.setattr(poll, "_reflect", lambda *a: None)
    sent = []
    monkeypatch.setattr(poll.publishers, "publish", lambda item: sent.append(item["title"]) or "ok-published")
    a = state.add_pending(good(title="A"))
    b = state.add_pending(good(title="B"))
    assert "Rejected" in poll.decide("no", a["id"])
    assert sent == []
    assert "ok-published" in poll.decide("ok", b["id"])
    assert sent == ["B"] and state.published_today("chan") == 1
    assert "no longer pending" in poll.decide("ok", b["id"])  # double tap is harmless
    assert sent == ["B"]


def test_publish_failure_keeps_draft(monkeypatch):
    monkeypatch.setattr(poll, "_reflect", lambda *a: None)
    def boom(item):
        raise RuntimeError("down")
    monkeypatch.setattr(poll.publishers, "publish", boom)
    it = state.add_pending(good(title="C"))
    assert "Publish failed" in poll.decide("ok", it["id"])
    assert [i["id"] for i in state.load_pending()] == [it["id"]]


@pytest.mark.skipif(not shutil.which("ffmpeg") or not video.FONT, reason="ffmpeg/font missing")
def test_video_renders(tmp_path):
    out = video.render(["Hello world", "Second line that is quite a bit longer than the first"], out=str(tmp_path / "o" / "v.mp4"), secs=1)
    assert (tmp_path / "o" / "v.mp4").stat().st_size > 1000 and out.endswith("v.mp4")


def test_github_blog_commit_payload(monkeypatch):
    from agent import publishers
    cfg = {"type": "github_commit", "repo": "o/r", "branch": "main", "content_dir": "src/content/blog", "account_id": "ca_x",
           "frontmatter_template": '---\ntitle: {title_json}\ndescription: {description_json}\npubDate: "{date_human}"\n---\n'}
    monkeypatch.setattr(config, "channels", lambda: {"blog": cfg})
    seen = {}
    monkeypatch.setattr(publishers.composio_client, "execute",
                        lambda slug, args, acct="": seen.update(slug=slug, args=args, acct=acct) or {"commit_url": "http://c"})
    msg = publishers.publish({"channel": "blog", "title": 'Say "hi": a post', "caption": "Desc", "body": "## Body"})
    f = seen["args"]["upserts"][0]
    assert seen["slug"] == "GITHUB_COMMIT_MULTIPLE_FILES" and seen["acct"] == "ca_x"
    assert f["path"] == "src/content/blog/say-hi-a-post.md"
    assert f["content"].startswith('---\ntitle: "Say \\"hi\\": a post"\n') and "## Body" in f["content"]
    assert "http://c" in msg


def test_blog_channel_requires_body(monkeypatch):
    monkeypatch.setattr(config, "channels", lambda: {"blog": {"enabled": True, "type": "github_commit", "daily_cap": 2}})
    assert not guard.validate(guard.clean(good(channel="blog", body="")))[0]
    assert guard.validate(guard.clean(good(channel="blog", body="x" * 400)))[0]
