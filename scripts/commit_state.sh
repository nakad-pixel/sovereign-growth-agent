#!/usr/bin/env bash
# Persist ONLY agent state (never code, rules, workflows).
set -euo pipefail
BRANCH="${GITHUB_REF_NAME:-main}"
git config user.name "growth-agent"
git config user.email "growth-agent@users.noreply.github.com"
git add memory SOUL.md
if git diff --cached --quiet; then echo "no state changes"; exit 0; fi
git commit -q -m "state: $(date -u +%FT%TZ)"
for i in 1 2 3 4 5; do
  if git pull --rebase -q origin "$BRANCH" && git push -q origin "HEAD:$BRANCH"; then echo "state saved"; exit 0; fi
  sleep $((i * 3))
done
echo "could not push state"; exit 1
