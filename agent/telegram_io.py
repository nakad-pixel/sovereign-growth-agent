import json

import requests

from . import config


class TelegramError(Exception):
    pass


def scrub(text):
    s = str(text)
    token = config.env("TELEGRAM_BOT_TOKEN")
    return s.replace(token, "***") if token else s


def call(method, data=None, files=None, timeout=30):
    token = config.env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN not set")
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if files:
            r = requests.post(url, data=data, files=files, timeout=timeout)
        else:
            r = requests.post(url, json=data, timeout=timeout)
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        raise TelegramError(scrub(type(e).__name__ + ": " + str(e))) from None
    if not body.get("ok"):
        raise TelegramError(scrub(body.get("description", "unknown error")))
    return body["result"]


def chat_id():
    cid = config.env("TELEGRAM_CHAT_ID")
    if not cid:
        raise TelegramError("TELEGRAM_CHAT_ID not set")
    return cid


def _kb(buttons):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]}


def send(text, buttons=None):
    data = {"chat_id": chat_id(), "text": text[:4000], "disable_web_page_preview": True}
    if buttons:
        data["reply_markup"] = _kb(buttons)
    return call("sendMessage", data)


def send_video(path, caption, buttons=None):
    data = {"chat_id": chat_id(), "caption": caption[:1000], "supports_streaming": "true"}
    if buttons:
        data["reply_markup"] = json.dumps(_kb(buttons))
    with open(path, "rb") as f:
        return call("sendVideo", data=data, files={"video": f}, timeout=180)


def answer_callback(callback_id, text=""):
    try:
        call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:180]})
    except TelegramError:
        pass


def get_updates(offset):
    return call("getUpdates", {"offset": offset, "timeout": 0, "limit": 50,
                               "allowed_updates": ["message", "callback_query"]})


def authorised(update):
    """Only the configured chat (and allowed user ids) may control the agent."""
    cid = config.env("TELEGRAM_CHAT_ID")
    src = update.get("message") or update.get("callback_query") or {}
    msg = src.get("message", src) if "callback_query" in update else src
    chat = str(msg.get("chat", {}).get("id", ""))
    sender = str(src.get("from", {}).get("id", ""))
    allowed = {x.strip() for x in config.env("TELEGRAM_ALLOWED_USERS", cid).split(",") if x.strip()}
    return bool(cid) and chat == cid and sender in allowed


def notify_safely(text):
    try:
        send(text)
    except Exception as e:  # never let a notification failure mask the real error
        print("telegram notify failed:", scrub(e))
