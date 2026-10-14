"""Hermes-style learning: reflect after every outcome, grow a skill library, track the money metric."""
import json, time, pathlib, re
import memory as mem

M = pathlib.Path("memory")

def log_metric(name, value, note=""):
    with open(M / "metrics.jsonl", "a") as f:
        f.write(json.dumps({"t": int(time.time()), "name": name, "value": value, "note": note}) + "\n")

def metrics_summary(n=20):
    p = M / "metrics.jsonl"
    if not p.exists():
        return "no metrics yet (rung 0: no revenue)"
    return "\n".join(open(p).read().splitlines()[-n:])

def relevant_skills(query, k=3):
    words = {w for w in re.findall(r"[a-z]{4,}", query.lower())}
    scored = []
    for name, body in mem.skills().items():
        score = len(words & set(re.findall(r"[a-z]{4,}", (name + body).lower())))
        scored.append((score, name, body))
    return [(n, b[:1500]) for s, n, b in sorted(scored, reverse=True)[:k] if s > 0]

def reflect(llm, system, outcome, item):
    """Called on approval/rejection/error. Writes a lesson and, if warranted, a skill."""
    r = llm(system + '\nReply JSON: {"lesson":str,"skill_name":str or null,"skill_body":str or null,'
            '"avoid":str or null}',
            f"Outcome: {outcome}\nItem: {json.dumps(item)}\nRecent:\n" + "\n".join(mem.recent(10)) +
            "\nExtract the lesson. Only create/update a skill if this is a repeatable pattern. "
            "Skill body = short markdown: when to use, steps, pitfalls.")
    mem.add_episode("lesson", r.get("lesson", ""), {"outcome": outcome})
    if r.get("avoid"):
        mem.add_episode("avoid", r["avoid"])
    if r.get("skill_name") and r.get("skill_body"):
        slug = re.sub(r"[^a-z0-9-]+", "-", r["skill_name"].lower()).strip("-")[:40]
        (M / "skills" / f"{slug}.md").write_text(r["skill_body"][:3000])
    return r
