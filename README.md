# Sovereign Growth Agent

Autonomous marketing agent that wakes every 6 hours on GitHub Actions, proposes ONE revenue-oriented action,
asks you to approve it in Telegram, publishes only after you tap Approve, then learns from the outcome.

- **Automaton-style motive:** one prime goal (the revenue ladder in `SOUL.md`), tracked via `/rev` in Telegram.
- **Hermes-style learning:** reflects after every decision, writes lessons and reusable skills to `memory/`.
- **Memory:** plain files in `memory/` committed to git, searched with an in-RAM SQLite FTS5 index each run.
- **Safety:** `agent/guard.py` blocks banned claims, duplicates and over-cap proposals; `RULES.md` is immutable to the agent;
  only the configured Telegram chat can approve; hard LLM-call budget; `KILL` file or `/pause` stops it.

## Workflows
| Workflow | When | What |
|---|---|---|
| `growth-agent` | every 6h | plan, guard, build video, send draft to Telegram |
| `approvals-poller` | every ~10 min | reads your Approve/Reject taps and commands, publishes, learns |
| `ci` | on code changes | runs the test suite |

Approval latency is the poller interval (GitHub cron can lag; expect 10-30 min).

## Telegram commands
`/status` `/pause` `/resume` `/rev <amount> [note]` `/help`. Approve/Reject arrive as buttons under each draft.

## Setup (repo Settings, Secrets and variables, Actions)
Required: `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (send /start to your bot, then read the id from `getUpdates`).
Optional: `COMPOSIO_API_KEY` (project key from the Composio dashboard, needed only for the `github_blog` channel).
LLM: Groq free tier (console.groq.com, OpenAI-compatible, no card). GitHub Models was retired on 2026-07-30, so it is not used.
Any OpenAI-compatible provider works by setting `LLM_BASE_URL`, `LLM_MODEL`, `LLM_FALLBACK_MODEL`.

## Channels (`config/channels.json`)
- `telegram_manual` (enabled): after approval, a ready-to-post package + video is sent to you to post yourself.
- `github_blog` (disabled): commits an approved article to the Astro blog repo via Composio. Enable after connecting GitHub in your Composio project and setting `account_id`.

## Local test
`pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`
