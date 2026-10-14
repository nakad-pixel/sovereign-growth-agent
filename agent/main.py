import os, json, pathlib
from openai import OpenAI
import memory as mem
import tools
import learn

# GitHub Models works with GITHUB_TOKEN; any OpenAI-compatible endpoint works.
client = OpenAI(base_url=os.environ.get("LLM_BASE_URL", "https://models.github.ai/inference"),
                api_key=os.environ.get("LLM_API_KEY", os.environ.get("GITHUB_TOKEN", "")))
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4.1")

def llm(system, user):
    r = client.chat.completions.create(model=MODEL, temperature=0.4,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return json.loads(r.choices[0].message.content)

def handle_approval():
    """Runs when the Telegram tap arrives. Publishing happens ONLY here."""
    decision, item_id = os.environ["DECISION"], os.environ["ITEM_ID"]
    pending = json.load(open("memory/pending.json"))
    item = next((p for p in pending if p["id"] == item_id), None)
    if not item:
        return tools.telegram(f"Item {item_id} not found.")
    pending = [p for p in pending if p["id"] != item_id]
    json.dump(pending, open("memory/pending.json", "w"), indent=1)
    mem.add_episode("approval", f"{decision} {item['title']}", {"id": item_id})
    if decision == "ok":
        # tools.composio(item["tool"], item["args"])   # <- publish via Composio here
        tools.telegram(f"Approved: {item['title']}. (wire publish call in handle_approval)")
    else:
        tools.telegram(f"Rejected: {item['title']}. Logged so I don't repeat it.")
    soul, rules = open("SOUL.md").read(), open("RULES.md").read()
    learn.reflect(llm, f"{soul}\n{rules}", "approved" if decision == "ok" else "rejected", item)

def scheduled_run():
    if pathlib.Path("KILL").exists():
        return print("KILL file present, exiting")
    soul, rules = open("SOUL.md").read(), open("RULES.md").read()
    curated = open("memory/MEMORY.md").read()
    context = "\n".join(mem.recent(15))
    context += "\nMETRICS:\n" + learn.metrics_summary()
    system = (f"{soul}\n{rules}\nCurated memory:\n{curated}\nSkills:\n{list(mem.skills().keys())}\n"
              'Reply JSON: {"reasoning":str,"search_memory":str,"proposal":{"title":str,"channel":str,'
              '"caption":str,"video_lines":[str]} or null,"lesson":str,"memory_update":str or null}')
    plan = llm(system, f"Recent episodes:\n{context}\nPick the ONE highest-leverage marketing action for this run.")
    related = mem.search(plan.get("search_memory", ""))
    skills_hint = learn.relevant_skills(plan.get("reasoning", "") + " " + plan.get("search_memory", ""))
    related = {"past": related, "skills": skills_hint, "avoid": mem.search("avoid")}
    plan = llm(system, f"Recent:\n{context}\nRelated past:\n{related}\nPrevious plan:\n{json.dumps(plan)}\n"
                       "Finalize. Avoid repeating failures.")
    p = plan.get("proposal")
    if p:
        item_id = str(abs(hash(p["title"])) % 10**8)
        video = tools.make_video(p["video_lines"]) if p.get("video_lines") else None
        pending = json.load(open("memory/pending.json"))
        pending.append({"id": item_id, "title": p["title"], "channel": p["channel"], "caption": p["caption"]})
        json.dump(pending, open("memory/pending.json", "w"), indent=1)
        tools.ask_approval(item_id, f"{p['title']}\n[{p['channel']}]\n\n{p['caption']}", video)
    mem.add_episode("run", f"Proposed: {p['title'] if p else 'nothing'}. Lesson: {plan.get('lesson','')}")
    if plan.get("memory_update"):
        open("memory/MEMORY.md", "w").write(plan["memory_update"][:3000])

if __name__ == "__main__":
    try:
        handle_approval() if os.environ.get("EVENT") == "approval" else scheduled_run()
    except Exception as e:
        tools.telegram(f"Agent error: {e}")
        raise
