// Cloudflare Worker: Telegram button tap -> GitHub repository_dispatch
// Secrets: TG_SECRET (webhook secret_token), GH_PAT (repo scope), GH_REPO ("user/repo"), ALLOWED_CHAT_ID
export default {
  async fetch(req, env) {
    if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TG_SECRET) return new Response("no", {status: 401});
    const u = await req.json(); const cb = u.callback_query;
    if (!cb || String(cb.message.chat.id) !== env.ALLOWED_CHAT_ID) return new Response("ok");
    const [decision, item_id] = cb.data.split(":");
    await fetch(`https://api.github.com/repos/${env.GH_REPO}/dispatches`, {
      method: "POST",
      headers: {Authorization: `Bearer ${env.GH_PAT}`, "User-Agent": "agent", Accept: "application/vnd.github+json"},
      body: JSON.stringify({event_type: "approval", client_payload: {decision, item_id}})
    });
    return new Response("ok");
  }
}
