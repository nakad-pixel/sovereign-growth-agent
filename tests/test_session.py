import io
import time

import pytest

from agent import config, llm, poll, run, session, state, storage, telegram_io as tg


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    (mem / "skills").mkdir(parents=True)
    (mem / "episodes.jsonl").write_text("")
    (mem / "pending.json").write_text("[]")
    monkeypatch.setattr(config, "MEM", mem)
    monkeypatch.setattr(config, "channels", lambda: {"chan": {"enabled": True, "type": "manual", "daily_cap": 5, "note": "x"}})
    for k, v in {"TELEGRAM_CHAT_ID": "42", "TELEGRAM_BOT_TOKEN": "T", "R2_ACCOUNT_ID": "acc", "R2_ACCESS_KEY_ID": "k",
                 "R2_SECRET_ACCESS_KEY": "s", "R2_BUCKET": "b"}.items():
        monkeypatch.setenv(k, v)
    storage.reset()
    llm.reset()


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body):
        self.objects[Key] = Body


def test_storage_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("R2_BUCKET")
    assert storage.pull() == 0 and storage.push() == 0


def test_storage_push_only_changed_then_pull_restores(monkeypatch):
    s3 = FakeS3()
    (config.MEM / "MEMORY.md").write_text("v1")
    first = storage.push(s3)
    assert first >= 3 and "memory/MEMORY.md" in s3.objects and "memory/skills/.gitkeep" not in s3.objects
    assert storage.push(s3) == 0  # unchanged -> nothing uploaded
    (config.MEM / "MEMORY.md").write_text("v2")
    assert storage.push(s3) == 1 and s3.objects["memory/MEMORY.md"] == b"v2"
    (config.MEM / "MEMORY.md").write_text("local junk")
    storage.reset()
    assert storage.pull(s3) >= 3
    assert (config.MEM / "MEMORY.md").read_text() == "v2"  # R2 wins


def test_storage_pull_blocks_path_traversal(tmp_path):
    s3 = FakeS3({"memory/../evil.txt": b"x", "memory//abs.txt": b"x", "memory/ok.txt": b"fine"})
    storage.pull(s3)
    assert (config.MEM / "ok.txt").read_text() == "fine"
    assert not (tmp_path / "evil.txt").exists()


def test_directive_runs_guarded_cycle(monkeypatch):
    seen = {}
    monkeypatch.setattr(run, "cycle", lambda d="": seen.setdefault("d", d) and ("queued", "ok"))
    assert poll.directive("make a video about pricing") is None
    assert seen["d"] == "make a video about pricing"
    state.set_paused(True)
    assert "paused" in poll.directive("x").lower()


def test_handle_routes_text_and_commands(monkeypatch):
    sent, dirs = [], []
    monkeypatch.setattr(tg, "send", lambda text, buttons=None: sent.append(text))
    monkeypatch.setattr(poll, "directive", lambda t: dirs.append(t) or "reply")
    msg = lambda text: {"message": {"chat": {"id": 42}, "from": {"id": 42}, "text": text}}
    poll.handle(msg("write a post on roofing leads"))
    poll.handle(msg("/propose lead pricing"))
    poll.handle(msg("/now"))
    poll.handle(msg("/status"))
    assert dirs == ["write a post on roofing leads", "lead pricing", ""]
    assert len(sent) == 4 and "Paused" in sent[3]


def test_cycle_queues_draft_and_respects_full_queue(monkeypatch):
    drafts = []
    monkeypatch.setattr(run, "ask_approval", lambda item: drafts.append(item["title"]))
    plan = {"reasoning": "r", "search_memory": "x", "lesson": "l", "memory_update": None,
            "proposal": {"title": "T1", "channel": "chan", "caption": "c", "body": "", "video_lines": []}}
    monkeypatch.setattr(llm, "call", lambda *a, **k: plan)
    assert run.cycle("topic")[0] == "queued" and drafts == ["T1"]
    monkeypatch.setattr(config, "MAX_PENDING", 1)
    assert run.cycle()[0] == "full" and drafts == ["T1"]


def test_session_loop_handles_updates_cycles_and_syncs(monkeypatch):
    handled, cycles, pushes, notes = [], [], [], []
    updates = iter([[{"update_id": 7, "message": {"chat": {"id": 42}, "from": {"id": 42}, "text": "hi"}},
                     {"update_id": 8, "message": {"chat": {"id": 99}, "from": {"id": 99}, "text": "/pause"}}]])
    def fake_updates(offset, timeout=0):
        time.sleep(0.15)
        return next(updates, [])
    monkeypatch.setattr(tg, "get_updates", fake_updates)
    monkeypatch.setattr(tg, "send", lambda *a, **k: notes.append(a[0]))
    monkeypatch.setattr(poll, "handle", lambda u: handled.append(u["update_id"]))
    monkeypatch.setattr(run, "cycle", lambda d="": cycles.append(1) or ("queued", "ok"))
    monkeypatch.setattr(storage, "pull", lambda c=None: 0)
    monkeypatch.setattr(storage, "push", lambda c=None: pushes.append(1) or 0)
    session.main(session_minutes=0.04, cycle_minutes=60, margin=0)
    assert handled == [7]                       # stranger (99) ignored, authorised user handled
    assert state.ledger()["tg_offset"] == 9     # both consumed
    assert state.ledger()["paused"] is False    # stranger could not pause it
    assert pushes and notes[0].startswith("Session started") and notes[-1].startswith("Session ending")


def test_session_survives_errors_and_stops_after_too_many(monkeypatch):
    monkeypatch.setattr(tg, "send", lambda *a, **k: None)
    monkeypatch.setattr(session.time, "sleep", lambda s: None)
    monkeypatch.setattr(storage, "pull", lambda c=None: 0)
    def boom(offset, timeout=0):
        raise tg.TelegramError("net down")
    monkeypatch.setattr(tg, "get_updates", boom)
    with pytest.raises(tg.TelegramError):
        session.main(session_minutes=5, margin=0)
