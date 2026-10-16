import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEM = ROOT / "memory"
CHANNELS_FILE = ROOT / "config" / "channels.json"


def env(key, default=""):
    return os.environ.get(key, default).strip()


BASE_URL = env("LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = env("LLM_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = env("LLM_FALLBACK_MODEL", "openai/gpt-oss-20b")
MAX_LLM_CALLS = int(env("MAX_LLM_CALLS", "10"))
MAX_PENDING = int(env("MAX_PENDING", "3"))
PENDING_TTL_HOURS = int(env("PENDING_TTL_HOURS", "72"))


def llm_key():
    return env("LLM_API_KEY") or env("GROQ_API_KEY")


def channels():
    return json.loads(CHANNELS_FILE.read_text())
