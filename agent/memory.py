import json, sqlite3, time, pathlib
M = pathlib.Path("memory")

def add_episode(kind, text, meta=None):
    with open(M / "episodes.jsonl", "a") as f:
        f.write(json.dumps({"t": int(time.time()), "kind": kind, "text": text, "meta": meta or {}}) + "\n")

def search(query, k=8):
    """FTS5 index rebuilt in memory from episodes.jsonl each run (no binary db in git)."""
    db = sqlite3.connect(":memory:")
    db.execute("create virtual table e using fts5(text, kind, t unindexed)")
    for line in open(M / "episodes.jsonl"):
        r = json.loads(line)
        db.execute("insert into e values (?,?,?)", (r["text"], r["kind"], r["t"]))
    q = " OR ".join(w for w in query.replace('"', " ").split() if len(w) > 3) or "run"
    return [r[0] for r in db.execute("select text from e where e match ? order by rank limit ?", (q, k))]

def recent(n=15):
    lines = open(M / "episodes.jsonl").read().splitlines()[-n:]
    return [json.loads(l)["text"] for l in lines]

def skills():
    return {p.stem: p.read_text() for p in (M / "skills").glob("*.md")}
