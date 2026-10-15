"""Channel executors. Called ONLY after a human tapped Approve."""
import datetime
import json

from . import composio_client, config, state, video
from . import telegram_io as tg


def publish(item):
    cfg = config.channels()[item["channel"]]
    kind = cfg.get("type", "manual")
    if kind == "manual":
        return _manual(item)
    if kind == "github_commit":
        return _github_commit(item, cfg)
    raise ValueError(f"unknown channel type: {kind}")


def _manual(item):
    text = f"READY TO POST ({item['channel']})\n\n{item['title']}\n\n{item['caption']}"
    if item.get("body"):
        text += f"\n\n{item['body']}"
    sent = False
    if item.get("video_lines"):
        try:
            path = video.render(item["video_lines"])
            if len(text) <= 1000:
                tg.send_video(path, text)
            else:
                tg.send_video(path, item["title"])
                tg.send(text)
            sent = True
        except Exception as e:
            print("video send failed:", tg.scrub(e))
    if not sent:
        tg.send(text)
    return f"package sent to Telegram for manual posting ({item['channel']})"


def _github_commit(item, cfg):
    template = cfg.get("frontmatter_template", "")
    if not template or not cfg.get("repo"):
        raise ValueError("github channel not configured (repo/frontmatter_template missing in config/channels.json)")
    owner, repo = cfg["repo"].split("/", 1)
    now = datetime.datetime.now(datetime.timezone.utc)
    front = template.format(title_json=json.dumps(item["title"]), description_json=json.dumps(item["caption"][:155]),
                            date=now.strftime("%Y-%m-%d"), date_human=now.strftime("%b %d %Y"))
    folder = cfg.get("content_dir", "").strip("/")
    path = f"{folder}/{state.slug(item['title'])}.md" if folder else f"{state.slug(item['title'])}.md"
    data = composio_client.execute(
        "GITHUB_COMMIT_MULTIPLE_FILES",
        {"owner": owner, "repo": repo, "branch": cfg.get("branch", "main"),
         "message": f"Add post: {item['title'][:60]}",
         "upserts": [{"path": path, "content": front + "\n" + (item.get("body") or item["caption"]) + "\n"}]},
        cfg.get("account_id", ""))
    url = (data.get("commit_url") or data.get("commit", {}).get("html_url")) if isinstance(data, dict) else None
    return f"committed {path} to {cfg['repo']}" + (f" ({url})" if url else "")
