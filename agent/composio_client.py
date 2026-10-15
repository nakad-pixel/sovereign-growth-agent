import time

import requests

from . import config

BASE = "https://backend.composio.dev/api/v3.1/tools/execute"


class ComposioError(Exception):
    pass


def execute(tool_slug, arguments, connected_account_id=""):
    key = config.env("COMPOSIO_API_KEY")
    if not key:
        raise ComposioError("COMPOSIO_API_KEY not set")
    body = {"arguments": arguments}
    account = connected_account_id or config.env("COMPOSIO_CONNECTED_ACCOUNT_ID")
    if account:
        body["connected_account_id"] = account
    if config.env("COMPOSIO_USER_ID"):
        body["user_id"] = config.env("COMPOSIO_USER_ID")
    last = ""
    for attempt in range(3):
        try:
            r = requests.post(f"{BASE}/{tool_slug}", headers={"x-api-key": key}, json=body, timeout=90)
        except requests.RequestException as e:
            last = type(e).__name__
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            last = f"HTTP {r.status_code}"
            time.sleep(4 * (attempt + 1))
            continue
        try:
            data = r.json()
        except ValueError:
            raise ComposioError(f"non-JSON response (HTTP {r.status_code})") from None
        if r.status_code >= 400 or data.get("successful") is False:
            err = data.get("error")
            msg = err.get("message") if isinstance(err, dict) else err
            raise ComposioError(f"{tool_slug} failed (HTTP {r.status_code}): {msg}")
        return data.get("data", data)
    raise ComposioError(f"{tool_slug} failed after retries: {last}")
