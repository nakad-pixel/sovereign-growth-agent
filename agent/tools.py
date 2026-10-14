import os, json, subprocess, requests, pathlib

TG = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN','')}"
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

def telegram(text):
    requests.post(f"{TG}/sendMessage", json={"chat_id": CHAT, "text": text[:4000]}, timeout=30)

def ask_approval(item_id, summary, video_path=None):
    """Sends draft + Approve/Reject buttons. Worker turns the tap into repository_dispatch."""
    kb = {"inline_keyboard": [[
        {"text": "Approve", "callback_data": f"ok:{item_id}"},
        {"text": "Reject", "callback_data": f"no:{item_id}"}]]}
    if video_path and os.path.getsize(video_path) < 45_000_000:
        with open(video_path, "rb") as f:
            requests.post(f"{TG}/sendVideo", data={"chat_id": CHAT, "caption": summary[:1000],
                          "reply_markup": json.dumps(kb)}, files={"video": f}, timeout=120)
    else:
        requests.post(f"{TG}/sendMessage", json={"chat_id": CHAT, "text": summary[:4000],
                      "reply_markup": kb}, timeout=30)

def make_video(script_lines, out="out/story.mp4", secs_per_line=4):
    """Text-card story video with ffmpeg only. Swap in Piper TTS / Pexels clips later."""
    pathlib.Path("out").mkdir(exist_ok=True)
    parts = []
    for i, line in enumerate(script_lines):
        p = f"out/s{i}.mp4"
        txt = line.replace("'", "").replace(":", " ").replace("%", "")[:120]
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x111111:s=1080x1920:d={secs_per_line}",
            "-vf", f"drawtext=text='{txt}':fontcolor=white:fontsize=56:x=(w-text_w)/2:y=(h-text_h)/2",
            "-pix_fmt", "yuv420p", p], check=True, capture_output=True)
        parts.append(p)
    with open("out/list.txt", "w") as f:
        f.writelines(f"file '{p.split('/')[-1]}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "out/list.txt", "-c", "copy", out],
                   check=True, capture_output=True)
    return out

def composio(tool_slug, arguments):
    """Placeholder: call your Composio MCP/REST endpoint here (needs COMPOSIO_API_KEY).
    Public-facing calls must only happen from the approval path in main.py."""
    raise NotImplementedError("wire Composio here")
