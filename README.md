# Sovereign Growth Agent

Runs every 6 hours on GitHub Actions. Its only job: grow revenue for Nexus Web Systems through marketing and distribution.

- **Automaton-style motive:** one prime goal (revenue ladder), tracked in `memory/metrics.jsonl`.
- **Hermes-style learning:** reflects after every outcome, writes lessons, and grows a skill library in `memory/skills/`.
- **Memory:** plain files committed to this repo (`memory/`), searched with an in-memory SQLite FTS index each run.
- **Safety:** every public action needs a Telegram Approve tap. See `RULES.md`. Emergency stop: create a file named `KILL` in the repo root.

## Setup
1. Add repo secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `COMPOSIO_API_KEY`.
2. Deploy `worker/worker.js` to Cloudflare Workers (secrets: `TG_SECRET`, `GH_PAT`, `GH_REPO`, `ALLOWED_CHAT_ID`) and set the Telegram webhook to it with the same `secret_token`.
3. Run the `growth-agent` workflow manually once.

LLM calls use GitHub Models via `GITHUB_TOKEN` by default. Override with `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
