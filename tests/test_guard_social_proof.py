import pytest

from agent import config, guard


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    (mem / "skills").mkdir(parents=True)
    (mem / "pending.json").write_text("[]")
    monkeypatch.setattr(config, "MEM", mem)
    monkeypatch.setattr(config, "channels", lambda: {"chan": {"enabled": True, "type": "manual", "daily_cap": 9, "note": "x"}})


def p(caption="Short caption", lines=("a",)):
    return guard.clean({"title": "A fine title", "channel": "chan", "caption": caption, "video_lines": list(lines)})


@pytest.mark.parametrize("text", [
    "Join hundreds who already streamlined their homes",
    "Thousands of homeowners trust this method",
    "Trusted by 500 contractors",
    "Used by over 2,000 businesses",
    "Join 1,000+ happy customers",
    "As seen on TV",
    "Rated #1 by pros",
])
def test_invented_social_proof_is_blocked(text):
    assert not guard.validate(p(caption=text))[0]
    assert not guard.validate(p(lines=[text]))[0]


@pytest.mark.parametrize("text", [
    "Learn how pros price leads in three steps",
    "Join the free guide today",
    "A practical checklist for missed-call text-back",
])
def test_honest_copy_still_passes(text):
    assert guard.validate(p(caption=text))[0]
