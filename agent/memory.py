"""File-based memory. episodes.jsonl is the log; an FTS5 index is rebuilt in RAM per run."""
import json
import re
import sqlite3
import time

from . import config


def _ep():
    return config.MEM / "episodes.jsonl"


def add_episode(kind, text, meta=None):
    with open(_ep(), "a") as f:
        f.write(json.dumps({"t": int(time.time()), "kind": kind, "text": str(text)[:1500], "meta": meta or {}}) + "\n")


def _rows():
    rows = []
    try:
        for line in open(_ep()):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        pass
    return rows


def search(query, k=8):
    tokens = re.findall(r"[A-Za-z0-9]{4,}", query or "")
    if not tokens:
        return recent(k)
    db = sqlite3.connect(":memory:")
    db.execute("create virtual table e using fts5(text, kind)")
    for r in _rows():
        db.execute("insert into e values (?, ?)", (r["text"], r["kind"]))
    match = " OR ".join(f'"{t}"' for t in tokens[:12])
    return [x[0] for x in db.execute("select text from e where e match ? order by rank limit ?", (match, k))]


def recent(n=15):
    return [r["text"] for r in _rows()[-n:]]


def prune(keep=1500):
    rows = _rows()
    if len(rows) > keep:
        with open(_ep(), "w") as f:
            for r in rows[-keep:]:
                f.write(json.dumps(r) + "\n")


def skills():
    folder = config.MEM / "skills"
    return {p.stem: p.read_text() for p in folder.glob("*.md") if p.stem.lower() != "readme"}
