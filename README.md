# Sovereign Growth Agent

Autonomous marketing agent that lives in long GitHub Actions sessions, proposes revenue-oriented actions,
asks you to approve them in Telegram, publishes only after you tap Approve, then learns from the outcome.

- **Automaton-style motive:** one prime goal (the revenue ladder in `SOUL.md`), tracked via `/rev` in Telegram.
- **Hermes-style learning:** reflects after every decision, writes lessons and reusable skills to `memory/`.
- **Memory:** files in `memory/`, searched with an in-RAM SQLite FTS5 index; durable in Cloudflare R2 (optional) or git.
- **Safety:** `agent/guard.py` blocks banned claims, duplicates and over-cap proposals; `RULES.md` is immutable to the agent;
  only the configured Telegram chat can approve; hard LLM-call budget; `KILL` file or `/pause` stops it.

## How it runs (GitHub Actions only)
- `agent-session` starts every 5 hours (cron `7 0,5,10,15,20`) and runs ~4h50m. Runs queue back to back (one at a time).
- Inside a session the agent **listens to Telegram in real time** (long polling): type any instruction, tap Approve/Reject,
  use commands. Every `CYCLE_MINUTES` (180) it also runs an autonomous planning cycle and sends you a draft.
- **Memory:** Cloudflare R2 if the `R2_*` secrets exist (durable, synced after every change). Otherwise memory is committed to git
  after every change and every 20 minutes, and once more when the session ends.
- Only ONE process may read your Telegram updates, so there are no other scheduled agent workflows.
- **Caution:** GitHub's Actions terms say Actions should not be used for serverless computing or activity unrelated to the
  repo's software project. Long listening sessions can look like that; GitHub may stop jobs or restrict the repo.
  `SESSION_MINUTES=0` on an always-on server avoids this with the same code.

## Workflows
| Workflow | When | What |
|---|---|---|
| `agent-session` | every 5h + manual | real-time Telegram session, autonomous cycles, memory sync |
| `ci` | on code changes | runs the test suite |

## Telegram commands
Any plain message = an instruction. `/now` `/propose <topic>` `/status` `/pause` `/resume` `/rev <amount> [note]` `/help`. Approve/Reject arrive as buttons under each draft.

## Setup (repo Settings, Secrets and variables, Actions)
Required: `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (send /start to your bot, then read the id from `getUpdates`).
Optional: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` (durable memory in Cloudflare R2).
Optional: `COMPOSIO_API_KEY` (project key from the Composio dashboard, needed only for the `github_blog` channel).
LLM: `GROQ_API_KEY` (free tier at console.groq.com, OpenAI-compatible, no card). GitHub Models was retired on 2026-07-30, so it is not used. Any OpenAI-compatible provider works by setting `LLM_BASE_URL`, `LLM_MODEL`, `LLM_FALLBACK_MODEL`.

## Channels (`config/channels.json`)
- `telegram_manual` (enabled): after approval, a ready-to-post package + video is sent to you to post yourself.
- `github_blog` (disabled): commits an approved article to the Astro blog repo via Composio. Enable after setting `account_id`.

## Local test
`pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`
