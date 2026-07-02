#!/bin/bash

# ============================================================
# LifeCoach AI V2 - Launcher
# Double-click to update and run the app.
# Close this terminal window to stop it.
# ============================================================

cd "$(dirname "$0")"

echo "🔄 Checking for updates..."
# The release branch is rebuilt (force-pushed) on every deploy, so a plain
# pull can't fast-forward — hard-reset to the remote instead. Local data
# (data/ folder, .env) is untracked and never touched by this.
if git fetch --quiet origin release; then
    git reset --quiet --hard origin/release
else
    echo "⚠️  Could not check for updates (offline?) — starting current version"
fi

echo "📦 Syncing dependencies..."
uv sync --quiet 2>/dev/null || echo "Dependencies up to date"

echo ""
echo "🚀 Launching Life Coach AI V2 at http://localhost:8010"
echo "   (Close this terminal window to stop the app)"
echo ""

( sleep 2 && open "http://localhost:8010" ) &
uv run uvicorn app.main:app --app-dir backend --port 8010
