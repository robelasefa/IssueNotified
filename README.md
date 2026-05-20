# IssueNotified Bot

> Real-time Telegram notifications for GitHub issues — the moment they're opened, closed, or reopened.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20+-green.svg)](https://python-telegram-bot.org/)
[![GitHub stars](https://img.shields.io/github/stars/robelasefa/IssueNotified?style=social)](https://github.com/robelasefa/IssueNotified/stargazers)

---

## Features

- 🔔 **Universal tracking** — works with any public GitHub repository, with or without admin access
- ⚡ **Hybrid delivery** — webhook push for repos you own, automatic polling fallback for everything else
- ✨ **AI summaries** — every notification includes a 1-2 sentence Gemini-powered summary of the issue
- 🔁 **Full issue lifecycle** — alerts for `opened`, `closed`, and `reopened` events
- 🏷️ **Keyword filtering** — subscribe only to issues matching specific terms in title, body, or labels
- 🔍 **Repository search** — find and track by name or `owner/repo` with inline one-tap tracking
- 🗂️ **Easy management** — list and untrack repositories via commands or inline buttons on every notification
- 👑 **Admin tools** — AI-polished broadcast messages and system stats
- 🛡️ **HMAC-SHA256 verification** — all GitHub webhook payloads are cryptographically validated

---

## Architecture

IssueNotified runs as a single **FastAPI** + **python-telegram-bot** process using a hybrid notification architecture. PTB's built-in polling is disabled (`updater=None`); all Telegram updates arrive via webhooks managed in the FastAPI `lifespan` context.

```
                ┌──────────────────────────────────────────────┐
  Telegram ───▶ │  POST /telegram                              │
                │  Verifies X-Telegram-Bot-Api-Secret-Token    │
                │  → PTB Application.process_update()          │
                │                                              │
  GitHub  ───▶  │  POST /github/webhook        (push path)     │
                │  Verifies X-Hub-Signature-256 (HMAC-SHA256)  │
                │  → process_github_webhook_event()            │
                │    ├─ Deduplicate via issue_id + action      │
                │    ├─ AI summary (Gemini)                    │
                │    └─ Fan out to all subscribers             │
                │                                              │
  JobQueue ───▶ │  poll_repositories()         (poll path)     │
                │  Runs every 5 min via PTB JobQueue           │
                │  Skips repos with active webhooks            │
                │  → Same dedup, AI, and fan-out pipeline      │
                │                                              │
  Monitoring ─▶ │  GET /health                                 │
                └──────────────────────────────────────────────┘
```

### Hybrid Polling

When a user tracks a repository they have admin access to, the bot installs a GitHub webhook automatically — notifications arrive instantly via push. For any other repository (public repos the user doesn't own), the bot falls back to polling the GitHub Events API every 5 minutes. The user is informed which mode is active at tracking time; both paths share the same deduplication, AI summary, and notification pipeline.

### Deduplication

Events are keyed as `issue_id + action` in the `tracked_issues` table. This means an issue being opened and later closed both trigger notifications correctly, while duplicate webhook deliveries and poll overlaps are silently ignored. Records are written before fan-out so a mid-send crash cannot re-notify on restart.

### AI Summarizer

`src/ai.py` holds a singleton `AIClient` that calls the Gemini REST API directly over `aiohttp`. It includes 3-attempt exponential backoff on `429`/`503` responses and a 15s timeout. If the key is absent or all attempts fail, notifications fall back to a 280-character description excerpt with no user-visible error.

### Rate Limiting

A sliding-window limiter in `src/ratelimit.py` governs both the GitHub API client (5,000 req/hour) and the webhook endpoints (60 req/min per IP).

---

## Project Structure

```
IssueNotified/
├── src/
│   ├── main.py           # Entry point — configures logging, starts uvicorn
│   ├── webhook.py        # FastAPI app: lifespan, middleware, route handlers
│   ├── config.py         # All env-var config, validated at import time
│   ├── notifier.py       # Webhook event processor + shared notification engine
│   ├── poller.py         # Background JobQueue polling for non-webhook repos
│   ├── github.py         # Async GitHub API client, webhook CRUD, payload parser
│   ├── ai.py             # Gemini AI client with retry/backoff
│   ├── database.py       # SQLite layer (WAL mode, FK enforcement, RLock)
│   ├── ratelimit.py      # Async sliding-window rate limiter
│   ├── validators.py     # Input validation helpers
│   ├── error.py          # Global PTB error handler
│   └── callbacks/        # One module per bot command
│       ├── start.py      # /start
│       ├── help.py       # /help
│       ├── track.py      # /track  (conversation + auto webhook install)
│       ├── untrack.py    # /untrack (inline buttons + webhook cleanup)
│       ├── list.py       # /list
│       ├── search.py     # /search + inline one-tap tracking
│       ├── stop.py       # /stop  (account deletion)
│       ├── feedback.py   # /feedback
│       ├── stats.py      # /stats  (admin only)
│       └── broadcast.py  # /broadcast (admin, AI-polished)
├── tests/                # pytest suite — 41 tests
├── data/                 # SQLite database (auto-created, gitignored)
├── .env.example
├── requirements.txt
├── README.md
└── SECURITY.md
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- GitHub Personal Access Token — classic PAT, `repo` scope required; add `admin:repo_hook` to auto-install webhooks on repos you own
- Google Gemini API key — optional, free tier at [Google AI Studio](https://aistudio.google.com/app/api-keys)
- A publicly reachable HTTPS URL (ngrok for local dev, Azure / Heroku for production)

### 1. Clone & install

```bash
git clone https://github.com/robelasefa/IssueNotified.git
cd IssueNotified
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Production bot token from @BotFather |
| `DEV_BOT_TOKEN` | — | Separate token used when `DEBUG=true` |
| `GITHUB_TOKEN` | ✅ | GitHub PAT (`repo` scope minimum; `admin:repo_hook` for auto-webhook) |
| `GEMINI_API_KEY` | — | Enables AI issue summaries |
| `ADMIN_USER_ID` | — | Your Telegram user ID — unlocks `/stats` and `/broadcast` |
| `WEBHOOK_BASE_URL` | ✅ | Public HTTPS root URL, no trailing slash |
| `WEBHOOK_SECRET` | ✅ prod | Shared secret for GitHub webhook HMAC validation |
| `PORT` | — | Server port (default: `8443`; Azure sets this automatically) |
| `DEBUG` | — | `true` → use `DEV_BOT_TOKEN` + verbose logging |
| `MAX_REPOS_PER_USER` | — | Per-user repository cap (default: `5`) |

> **Never commit `.env`.** It is already excluded by `.gitignore`.
> See `SECURITY.md` for vulnerability reporting guidance.

### 3. Run locally

```bash
# Expose a public HTTPS URL for webhooks
ngrok http 8443
# Copy the https://... URL into WEBHOOK_BASE_URL in .env

python src/main.py
```

### 4. Deploy to Azure App Service

```bash
az webapp config appsettings set --name <app> --resource-group <rg> \
  --settings BOT_TOKEN=... GITHUB_TOKEN=... GEMINI_API_KEY=... \
             WEBHOOK_BASE_URL=https://<app>.azurewebsites.net \
             WEBHOOK_SECRET=... ADMIN_USER_ID=...
```

`WEBSITE_INSTANCE_ID` is detected automatically — the database persists to `/home/data/` rather than the local `data/` directory.

---

## Bot Commands

### User

| Command | Description |
|---|---|
| `/start` | Register and receive a welcome message |
| `/track` | Start tracking a repository |
| `/untrack` | Stop tracking a repository |
| `/list` | View all your tracked repositories |
| `/search <query>` | Search GitHub by name or `owner/repo` |
| `/feedback` | Send feedback to the developer |
| `/stop` | Delete your account and all tracked data |
| `/help` | Show the command reference |

### Admin (`ADMIN_USER_ID` only)

| Command | Description |
|---|---|
| `/stats` | Users, repositories, and tracked-issue counts |
| `/broadcast <message>` | AI-polished announcement sent to all users |

---

## Feature Highlights

### Universal Repository Tracking

Any public GitHub repository can be tracked regardless of ownership:

- **You own the repo** → bot auto-installs a webhook, notifications are instant
- **You don't own the repo** → bot falls back to polling every 5 minutes automatically

No manual configuration needed in either case.

### Keyword Filtering

Filter per-repository so you're only notified when an issue's title, body, or labels match at least one of your terms:

```
/track
> torvalds/linux
> memory leak,regression,critical
```

### Notification Format

```
🔔 NEW ISSUE • facebook/react

#42 — Application crashes on startup with out of memory error
🕐 2026-05-20 01:45 PM UTC (6 minutes ago)

🏷️ `bug`  `docker`  👤 @contributor

✨ AI Summary:
The application fails to launch with a Java heap OutOfMemoryError inside Docker.
Increase container memory allocation or tune JVM heap settings.
```

Every notification includes a **🌐 View on GitHub** link and a **🔕 Stop Tracking** inline button.

---

## Running Tests

```bash
# Windows
venv\Scripts\python -m pytest

# Linux/macOS
source venv/bin/activate && pytest
```

41 tests covering the AI client, database layer, GitHub client, notification formatter, validators, and webhook routes.

---

## Troubleshooting

| Symptom | Resolution |
|---|---|
| Bot not responding | Confirm the correct token is active (`DEBUG=true` uses `DEV_BOT_TOKEN`) |
| No AI summary | Check `GEMINI_API_KEY` is set; inspect logs for `Gemini API error` |
| GitHub API 403 | Token may be missing `admin:repo_hook` scope or has expired |
| Notifications not arriving (webhook) | Verify `WEBHOOK_BASE_URL` is publicly reachable and the GitHub webhook shows green in repo settings |
| Notifications not arriving (polling) | Check logs for GitHub API errors; confirm the repo is public |
| Webhook creation fails | Normal for repos you don't own — polling is used automatically |
| Database errors on Azure | Confirm `/home/data/` is writable; `WEBSITE_INSTANCE_ID` must be set by the platform |

---

## Contributing

Small fixes — open a PR directly. Larger changes — open an issue first to align on approach.

If you find IssueNotified useful, a ⭐ on GitHub helps others discover it.

---

## License

[MIT](LICENSE)

## Contact

- Bug reports & feature requests → [GitHub Issues](https://github.com/robelasefa/IssueNotified/issues)
- Direct feedback → `/feedback` in the bot