import time

import pytest

from agent import config, session, storage


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)


def test_no_backup_outside_github_actions(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    calls = []
    monkeypatch.setattr(session, "_git_backup", lambda: calls.append(1))
    session._persist(True, 0)
    assert calls == []


def test_git_backup_after_changes_and_on_interval(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    calls = []
    monkeypatch.setattr(session, "_git_backup", lambda: calls.append(1))
    now = time.time()
    assert session._persist(False, now) == now and calls == []          # nothing changed, interval not reached
    assert session._persist(True, now) >= now and len(calls) == 1       # changes -> backup immediately
    session._persist(False, now - config.GIT_BACKUP_MINUTES * 60 - 1)   # interval elapsed -> backup
    assert len(calls) == 2


def test_r2_takes_over_when_configured(monkeypatch):
    for k, v in {"R2_ACCOUNT_ID": "a", "R2_ACCESS_KEY_ID": "k", "R2_SECRET_ACCESS_KEY": "s", "R2_BUCKET": "b"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    pushed, backed = [], []
    monkeypatch.setattr(storage, "push", lambda c=None: pushed.append(1) or 0)
    monkeypatch.setattr(session, "_git_backup", lambda: backed.append(1))
    session._persist(True, 0)
    assert pushed == [1] and backed == []
