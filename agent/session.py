"""Long-lived session (runs ~4-5h on GitHub Actions, or forever on a server with SESSION_MINUTES=0).
Listens to Telegram in real time, runs an autonomous cycle every CYCLE_MINUTES, syncs memory to R2."""
import sys
import time

from . import config, llm, poll, run, state, storage
from . import memory as mem
from . import telegram_io as tg


def main(session_minutes=None, cycle_minutes=None, margin=90):
    session_minutes = config.SESSION_MINUTES if session_minutes is None else session_minutes
    cycle_minutes = config.CYCLE_MINUTES if cycle_minutes is None else cycle_minutes
    start = time.time()
    deadline = start + session_minutes * 60 if session_minutes > 0 else float("inf")
    pulled = storage.pull()
    next_cycle, errors, last_alert = start + 120, 0, 0.0
    tg.notify_safely("Session started. Type any instruction, or /help. Memory: "
                     + (f"R2 ({pulled} files loaded)" if storage.enabled() else "git only (R2 not configured)"))
    while time.time() < deadline - margin:
        try:
            wait = int(max(1, min(50, deadline - margin - time.time())))
            for u in tg.get_updates(state.ledger()["tg_offset"], timeout=wait):
                if tg.authorised(u):
                    llm.reset()
                    try:
                        poll.handle(u)
                    except Exception as e:
                        tg.notify_safely(f"Error handling that: {tg.scrub(type(e).__name__)}: {tg.scrub(e)}"[:400])
                state.set_offset(u["update_id"] + 1)
            for it in state.expire_pending():
                mem.add_episode("expired", f"No decision in time, expired: {it['title']}")
            idle = (config.ROOT / "KILL").exists() or state.ledger().get("paused")
            if not idle and time.time() >= next_cycle:
                status, text = run.cycle()
                if status == "none":
                    tg.notify_safely(text)
                next_cycle = time.time() + cycle_minutes * 60
            storage.push()
            errors = 0
        except Exception as e:
            errors += 1
            print("session loop error:", tg.scrub(type(e).__name__), tg.scrub(e))
            if time.time() - last_alert > 600:
                last_alert = time.time()
                tg.notify_safely(f"Session hiccup ({errors}): {tg.scrub(type(e).__name__)}: {tg.scrub(e)}"[:400])
            if errors >= 8:
                raise
            time.sleep(min(60, 5 * errors))
    try:
        storage.push()
    finally:
        tg.notify_safely("Session ending, memory saved. The next session picks up from here.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        tg.notify_safely(f"Session crashed: {tg.scrub(type(e).__name__)}: {tg.scrub(e)}"[:400])
        raise
