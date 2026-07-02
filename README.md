# LifeCoach AI V2

Local-first assistant for a life coaching practice: record or upload client
calls, get coach/client-labeled transcripts (Deepgram Nova-3), and — coming in
later phases — session documents generated from them.

- **Backend**: FastAPI + SQLite (`backend/`), managed with [uv](https://docs.astral.sh/uv/)
- **Frontend**: React + Tailwind (`frontend/`), built with Vite
- All data stays on the machine in `data/` (SQLite DB, audio, transcripts)

---

## Installing on Maria's Mac (V2 alongside V1)

V2 lives in its **own folder** and never touches the V1 install. It reuses the
tools V1 already installed (Homebrew, `git`, `uv`) — **no Node.js needed**,
because updates ship with the frontend pre-built (see *How updates work*).

**Step 1 — Get the app** (one time)

```bash
git clone -b release https://github.com/LouisZCode/LifeCoachAI_V2.git ~/Applications/LifeCoach_V2
cd ~/Applications/LifeCoach_V2
chmod +x LifeCoachV2.command
```

**Step 2 — API key** (one time)

```bash
cat > .env << 'EOF'
DEEPGRAM_API_KEY=your-deepgram-key-here
EOF
```

(The same Deepgram key V1 uses is fine.)

**Step 3 — Call-recording audio setup** (one time, only for in-app recording)

1. Install the virtual audio driver: `brew install blackhole-2ch`
2. Open **Audio MIDI Setup** (Cmd+Space, type "Audio MIDI Setup")
3. Click **+** (bottom left) → **Create Multi-Output Device**
4. Check **both** your headphones/speakers **and** BlackHole 2ch
5. Rename the new device to exactly: **Recording Output**
6. During calls, select **Recording Output** as the sound output in
   System Settings → Sound

The app checks all of this for you: the *Record the call* screen shows green
checks when everything is ready, and warns in red — even mid-recording — if
the sound output gets switched away (e.g. earbuds connecting).

**Step 4 — Launch**

Double-click `LifeCoachV2.command` in Finder. It updates itself, then opens
the app at [http://localhost:8010](http://localhost:8010). Close the terminal
window to stop it. V1 keeps working exactly as before.

### How updates work

| Developer | Maria |
|-----------|-------|
| `git push` (GitHub Action builds the frontend into a `release` branch) | Double-clicks `LifeCoachV2.command` |
| Changes deployed | Gets the latest version automatically |

---

## Development

Requirements: `uv`, Node 22+.

```bash
uv sync                                                  # backend deps
npm install --prefix frontend                            # frontend deps
uv run uvicorn app.main:app --app-dir backend --port 8000 --reload
npm run dev --prefix frontend                            # Vite on :5173, proxies /api
```

Open http://localhost:5173. A `.env` in the repo root provides
`DEEPGRAM_API_KEY` (see `backend/app/config.py` for all settings).

In production mode (Maria's install) there is no Vite: the GitHub Action
commits `frontend/dist` to the `release` branch and FastAPI serves it directly
at http://localhost:8010.
