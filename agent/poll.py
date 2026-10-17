"""Approval poller (runs every ~10 min, no LLM unless a decision needs reflecting)."""
import sys

from . import config, learn, llm, publishers, state
from . import memory as mem
from . import telegram_io as tg

HELP = ("Just type an instruction (e.g. 'make a video about pricing roofing leads') and I'll draft it for approval.\n"
        "Commands: /now  /propose <topic>  /status  /pause  /resume  /rev <amount> [note]  /help\n"
        "Drafts arrive with Approve/Reject buttons.")


def _reflect(outcome, item):
    try:
        system = (open(config.ROOT / "SOUL.md").read() + "\n" + open(config.ROOT / "RULES.md").read())
        learn.reflect(system, outcome, item)
    except Exception as e:  # learning is best-effort, never blocks the decision
        print("reflect skipped:", tg.scrub(type(e).__name__))


def decide(decision, item_id):
    item = state.pop_pending(item_id)
    if not item:
        return "That draft is no longer pending (already handled or expired)."
    if decision == "no":
        mem.add_episode("approval", f"REJECTED: {item['title']} [{item['channel']}]")
        _reflect("rejected", item)
        return f"Rejected: {item['title']}. Logged so I don't repeat it."
    try:
        result = publishers.publish(item)
    except Exception as e:
        state.restore_pending(item)
        return f"Publish failed: {tg.scrub(e)}\nDraft kept; tap Approve again to retry."
    state.record_publish(item["channel"])
    mem.add_episode("approval", f"APPROVED+PUBLISHED: {item['title']} [{item['channel']}]")
    _reflect("approved", item)
    return f"Approved: {result}"


def command(text):
    cmd, _, rest = text.strip().partition(" ")
    cmd = cmd.split("@")[0].lower()
    if cmd in ("/start", "/help"):
        return HELP
    if cmd == "/status":
        led = state.ledger()
        today = led["days"].get(state.today(), {})
        return (f"Paused: {led['paused']} | Pending drafts: {len(state.load_pending())} | "
                f"Published today: {sum(today.values())}\nLast run: {led.get('last_run', 'never')}\n{learn.rung_text()}")
    if cmd == "/pause":
        state.set_paused(True)
        return "Paused. No new proposals until /resume."
    if cmd == "/resume":
        state.set_paused(False)
        return "Resumed."
    if cmd == "/rev":
        parts = rest.split(None, 1)
        try:
            amount = float(parts[0])
        except (IndexError, ValueError):
            return "Usage: /rev 12.50 gumroad sale"
        learn.log_metric("revenue", amount, parts[1] if len(parts) > 1 else "")
        return f"Logged ${amount:.2f}. {learn.rung_text()}"
    return HELP


def directive(text):
    """Human instruction -> one guarded proposal. Returns a reply (None when a draft was already sent)."""
    from . import run
    if state.ledger().get("paused"):
        return "I'm paused. Send /resume first."
    status, out = run.cycle(text)
    return None if status == "queued" else out


def handle(update):
    if "callback_query" in update:
        cq = update["callback_query"]
        decision, _, item_id = cq.get("data", "").partition(":")
        if decision not in ("ok", "no") or not item_id:
            return
        tg.answer_callback(cq["id"], "Working...")
        tg.send(decide(decision, item_id))
    else:
        text = update.get("message", {}).get("text", "").strip()
        if not text:
            return
        cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if cmd in ("/now", "/propose"):
            reply = directive(text.partition(" ")[2].strip())
        elif text.startswith("/"):
            reply = command(text)
        else:
            reply = directive(text)
        if reply:
            tg.send(reply)


def main():
    if not config.env("TELEGRAM_CHAT_ID"):
        print("TELEGRAM_CHAT_ID not set; nothing to do")
        return 0
    llm.reset()
    for u in tg.get_updates(state.ledger()["tg_offset"]):
        if tg.authorised(u):
            try:
                handle(u)
            except Exception as e:
                tg.notify_safely(f"Error handling update: {tg.scrub(type(e).__name__)}: {tg.scrub(e)}"[:400])
        state.set_offset(u["update_id"] + 1)
    for it in state.expire_pending():
        mem.add_episode("expired", f"No decision in time, expired: {it['title']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("poll failed:", tg.scrub(type(e).__name__), tg.scrub(e))
        raise
