"""Hermes-style learning (reflect, skills) + the money metric (revenue ladder)."""
import json
import re
import time

from . import config, llm
from . import memory as mem


def _metrics_path():
    return config.MEM / "metrics.jsonl"


def log_metric(name, value, note=""):
    with open(_metrics_path(), "a") as f:
        f.write(json.dumps({"t": int(time.time()), "name": name, "value": value, "note": note[:200]}) + "\n")


def _metric_rows():
    rows = []
    try:
        for line in open(_metrics_path()):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        pass
    return rows


def metrics_summary(n=15):
    rows = _metric_rows()[-n:]
    return "\n".join(json.dumps(r) for r in rows) or "no metrics yet"


def rung_text(now=None):
    now = now or time.time()
    rows = [r for r in _metric_rows() if r.get("name") == "revenue"]
    total = sum(float(r["value"]) for r in rows)
    last30 = sum(float(r["value"]) for r in rows if now - r["t"] <= 30 * 86400)
    if total <= 0:
        return "Rung 0: no revenue yet. Next goal: first $1."
    if last30 < 100:
        return f"Rung 1: ${last30:.0f} in last 30 days. Next goal: $100/month."
    if last30 < 1000:
        return f"Rung 2: ${last30:.0f} in last 30 days. Next goal: $1k/month."
    if last30 < 10000:
        return f"Rung 3: ${last30:.0f} in last 30 days. Next goal: $10k/month."
    return f"Rung 4: ${last30:.0f} in last 30 days. Keep compounding."


def relevant_skills(query, k=3):
    words = set(re.findall(r"[a-z]{4,}", (query or "").lower()))
    scored = []
    for name, body in mem.skills().items():
        score = len(words & set(re.findall(r"[a-z]{4,}", (name + " " + body).lower())))
        if score:
            scored.append((score, name, body[:1500]))
    return [(n, b) for _, n, b in sorted(scored, reverse=True)[:k]]


def reflect(system, outcome, item):
    """After approval/rejection: write a lesson, an avoid-note, and (if repeatable) a skill."""
    brief = {k: item.get(k) for k in ("title", "channel", "caption")}
    r = llm.call(
        system + '\nReply ONE JSON: {"lesson": str, "avoid": str or null, "skill_name": str or null, "skill_body": str or null}',
        f"Outcome: {outcome}\nItem: {json.dumps(brief)}\nRecent:\n" + "\n".join(mem.recent(10))
        + "\nExtract the lesson. Create/update a skill ONLY for a repeatable pattern (markdown: when to use, steps, pitfalls).",
        ("lesson",),
    )
    mem.add_episode("lesson", r.get("lesson", ""), {"outcome": outcome})
    if r.get("avoid"):
        mem.add_episode("avoid", r["avoid"])
    if r.get("skill_name") and r.get("skill_body"):
        name = re.sub(r"[^a-z0-9-]+", "-", str(r["skill_name"]).lower()).strip("-")[:40]
        if name and name != "readme":
            (config.MEM / "skills" / f"{name}.md").write_text(str(r["skill_body"])[:3000])
    return r
