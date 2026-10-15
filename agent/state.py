"""Small JSON state: approval queue + ledger (daily caps, used titles, telegram offset, pause flag)."""
import datetime
import hashlib
import json
import os
import re
import time

from . import config


def _pending_path():
    return config.MEM / "pending.json"


def _ledger_path():
    return config.MEM / "ledger.json"


def _read(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    os.replace(tmp, path)


def today():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def load_pending():
    return _read(_pending_path(), [])


def save_pending(items):
    _write(_pending_path(), items)


def add_pending(proposal, now=None):
    now = now or time.time()
    item = dict(proposal)
    item["id"] = hashlib.sha1(f"{proposal['title']}{now}".encode()).hexdigest()[:10]
    item["created"] = int(now)
    item["expires"] = int(now + config.PENDING_TTL_HOURS * 3600)
    items = load_pending()
    items.append(item)
    save_pending(items)
    return item


def restore_pending(item):
    items = [i for i in load_pending() if i["id"] != item["id"]]
    items.append(item)
    save_pending(items)


def pop_pending(item_id):
    items = load_pending()
    found = next((i for i in items if i["id"] == item_id), None)
    if found:
        save_pending([i for i in items if i["id"] != item_id])
    return found


def expire_pending(now=None):
    now = now or time.time()
    items = load_pending()
    live = [i for i in items if i.get("expires", 0) > now]
    expired = [i for i in items if i.get("expires", 0) <= now]
    if expired:
        save_pending(live)
    return expired


def ledger():
    data = _read(_ledger_path(), {})
    data.setdefault("days", {})
    data.setdefault("titles", [])
    data.setdefault("tg_offset", 0)
    data.setdefault("paused", False)
    return data


def save_ledger(data):
    days = sorted(data["days"])[-14:]
    data["days"] = {d: data["days"][d] for d in days}
    data["titles"] = data["titles"][-300:]
    _write(_ledger_path(), data)


def published_today(channel):
    return ledger()["days"].get(today(), {}).get(channel, 0)


def record_publish(channel):
    led = ledger()
    day = led["days"].setdefault(today(), {})
    day[channel] = day.get(channel, 0) + 1
    save_ledger(led)


def remember_title(title):
    led = ledger()
    led["titles"].append(slug(title))
    save_ledger(led)


def set_offset(offset):
    led = ledger()
    led["tg_offset"] = max(led["tg_offset"], offset)
    save_ledger(led)


def set_paused(flag):
    led = ledger()
    led["paused"] = bool(flag)
    save_ledger(led)


def touch_last_run():
    led = ledger()
    led["last_run"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    save_ledger(led)
