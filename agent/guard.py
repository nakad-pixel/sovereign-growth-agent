"""Safety gate: every proposal passes through here before it can even be shown for approval."""
import re

from . import config, state

BANNED = [
    r"guaranteed (income|returns?|profits?|results?)",
    r"get rich( quick)?",
    r"\brisk[- ]free\b",
    r"\bno risk\b",
    r"make \$?\d[\d,]*\s*(a|per|/)\s*(day|week|month)",
    r"fake (reviews?|testimonials?)",
    r"i (personally )?earned \$",
    r"doctor[- ]approved",
    # invented social proof: the agent has no verified customer numbers, so any such claim is fabricated
    r"\b(join|joined by) (hundreds|thousands|millions|over \d|\d[\d,]*\+?)",
    r"(hundreds|thousands|millions) of (happy |satisfied |local )?(customers|clients|users|homeowners|contractors|businesses)",
    r"\b(trusted|used|loved) by (over |more than )?\d",
    r"\b\d[\d,]*\+? (happy |satisfied )(customers|clients|users|homeowners)",
    r"\bas seen (on|in)\b",
    r"\b(rated|ranked|voted) (#|number )?1\b",
]


def enabled_channels():
    return {k: v for k, v in config.channels().items() if v.get("enabled")}


def clean(p):
    if not isinstance(p, dict):
        return p
    out = dict(p)
    for k in ("title", "channel", "caption", "body"):
        out[k] = str(out.get(k) or "").strip()
    lines = out.get("video_lines") or []
    out["video_lines"] = [str(x).strip() for x in lines if str(x).strip()] if isinstance(lines, list) else []
    return out


def validate(p):
    if not isinstance(p, dict):
        return False, "proposal is not an object"
    for k in ("title", "channel", "caption"):
        if not p.get(k):
            return False, f"missing {k}"
    channels = enabled_channels()
    if p["channel"] not in channels:
        return False, f"channel {p['channel']!r} is not enabled; use one of {sorted(channels)}"
    if len(p["title"]) > 120 or len(p["caption"]) > 2000 or len(p.get("body", "")) > 20000:
        return False, "title/caption/body too long"
    lines = p.get("video_lines", [])
    if len(lines) > 10 or any(len(x) > 110 for x in lines):
        return False, "video_lines: max 10 lines of 110 chars"
    if channels[p["channel"]].get("type") == "github_commit" and len(p.get("body", "")) < 300:
        return False, "blog channels need a full markdown article in body (300+ chars)"
    text = " ".join([p["title"], p["caption"], p.get("body", ""), *lines]).lower()
    for pattern in BANNED:
        if re.search(pattern, text):
            return False, f"banned claim pattern: {pattern}"
    if state.slug(p["title"]) in state.ledger()["titles"]:
        return False, "duplicate of a previous title"
    cap = int(channels[p["channel"]].get("daily_cap", 3))
    queued = sum(1 for i in state.load_pending() if i["channel"] == p["channel"])
    if state.published_today(p["channel"]) + queued >= cap:
        return False, f"daily cap ({cap}) reached for {p['channel']}"
    return True, ""
