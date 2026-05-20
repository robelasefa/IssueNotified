# IssueNotified Bot

> Real-time Telegram notifications for GitHub issues — the moment they're opened, closed, or reopened.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20+-green.svg)](https://python-telegram-bot.org/)

---

## Features

- 🔔 **Instant notifications** — event-driven via GitHub webhooks, zero polling latency
- ✨ **AI summaries** — every notification includes a 1-2 sentence Gemini-powered summary of the issue
- 🔁 **Full issue lifecycle** — alerts for `opened`, `closed`, and `reopened` events
- 🏷️ **Keyword filtering** — subscribe only to issues matching specific terms in title, body, or labels
- 🔍 **Repository search** — find and track by name or `owner/repo` with inline one-tap tracking
- 🗂️ **Easy management** — list and untrack repositories via commands or inline buttons on every notification
- 👑 **Admin tools** — AI-polished broadcast messages and system stats
- 🛡️ **HMAC-SHA256 signature verification** — all GitHub webhook payloads are cryptographically validated
- ⚡ **Dual-webhook architecture** — PTB processes Telegram updates; FastAPI dispatches GitHub events

---

## Architecture

IssueNotified runs as a single **FastAPI** + **python-telegram-bot** process. PTB's built-in polling is disabled (`updater=None`); all updates arrive via webhooks managed in the FastAPI `lifespan` context.

```
                ┌──────────────────────────────────────────┐
  Telegram ───▶ │  POST /telegram                          │
                │  Verifies X-Telegram-Bot-Api-Secret-Token │
                │  → PTB Application.process_update()       │
                │                                           │
  GitHub  ───▶  │  POST /github/webhook                    │
                │  Verifies X-Hub-Signature-256 (HMAC-SHA256)│
                │  → process_github_webhook_event()         │
                │    ├─ Deduplicate via tracked_issues DB   │
                │    ├─ AI summary (Gemini 3.1 Flash Lite)  │
                │    └─ Send to all subscribers             │
                │                                           │
  Monitoring ─▶ │  GET /health                             │
                └──────────────────────────────────────────┘
```

### AI Summarizer

`src/ai.py` holds a single `AIClient` singleton that is lazy-initialized at startup. It calls the Gemini REST API directly over `aiohttp` with:

- **Model:** `gemini-3.1-flash-lite` — chosen for its higher free-tier rate limit
- **Retries:** 3 attempts with exponential backoff on `429` and `503` responses
- **Timeout:** 15 s per request via `aiohttp.ClientTimeout`
- **Graceful degradation:** if the API key is absent or every attempt fails, the notification falls back to a 280-character description excerpt

### Request Rate Limiting

`src/ratelimit.py` implements a sliding-window rate limiter:

- **GitHub API:** 5,000 requests / hour (mirrors GitHub's authenticated limit)
- **Webhook endpoints:** 60 requests / minute per IP (protects against DDoS floods)

---

## Project Structure

```
IssueNotified/
├── src/
│   ├── main.py           # Entry point — configures logging, starts uvicorn
│   ├── webhook.py        # FastAPI app: lifespan, middleware, route handlers
│   ├── config.py         # All env-var config, validated at import time
│   ├── notifier.py       # Webhook event processor + Telegram notification engine
│   ├── github.py         # Async GitHub API client, webhook CRUD, payload normaliser
│   ├── ai.py             # Gemini AI client with retry/backoff
│   ├── database.py       # SQLite layer (WAL mode, FK enforcement, thread-safe RLock)
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
├── tests/                # pytest suite — 36 tests
├── data/                 # SQLite database (auto-created)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- GitHub Personal Access Token (classic, `repo` + `admin:repo_hook` scopes)
- Google Gemini API key — free tier at [ai.google.dev](https://ai.google.dev)
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
| `GITHUB_TOKEN` | ✅ | GitHub PAT (`repo` + `admin:repo_hook` scopes) |
| `GEMINI_API_KEY` | — | Google Gemini API key — enables AI summaries |
| `ADMIN_USER_ID` | — | Your Telegram user ID — unlocks `/stats` and `/broadcast` |
| `WEBHOOK_BASE_URL` | ✅ | Public HTTPS root URL (no trailing slash) |
| `WEBHOOK_SECRET` | ✅ (prod) | Shared secret for GitHub webhook HMAC validation |
| `PORT` | — | Server port (default: `8443`; Azure sets this automatically) |
| `DEBUG` | — | `true` → use `DEV_BOT_TOKEN` + verbose logging |
| `MAX_REPOS_PER_USER` | — | Per-user repository cap (default: `10`) |

> **Never commit `.env`.** It is already excluded by `.gitignore`.
>
> See `SECURITY.md` for private vulnerability reporting and responsible disclosure guidance.

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

The `WEBSITE_INSTANCE_ID` environment variable set by Azure is detected automatically; the database will be persisted to `/home/data/` instead of the local `data/` directory.

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

### AI Issue Summaries

Each notification is augmented with a concise 1-2 sentence summary generated by **Gemini 3.1 Flash Lite**. The summarizer gracefully degrades to a 280-character excerpt if the API is unavailable or rate-limited, with automatic retry and exponential backoff built in.

### Keyword Filtering

Filter per-repository so you're only alerted when an issue's title, body, or labels match at least one of your keywords:

```
/track
> facebook/react
> bug,performance,memory
```

### Notification Format

```
🔔 NEW ISSUE • facebook/react

#42 — Application crashes on startup with out of memory error
🕐 2026-05-19 01:45 PM UTC (6 minutes ago)

🏷️ `bug`  `docker`  👤 @contributor

✨ AI Summary:
The application fails to launch with a Java heap OutOfMemoryError inside Docker.
Increase container memory allocation or tune JVM heap settings.
```

Every notification includes a **🌐 View on GitHub** link and a **🔕 Stop Tracking** inline button.

### Automatic Webhook Installation

When you track a repository you have admin access to, the bot installs a GitHub webhook automatically and stores the hook ID in the database. Untracking removes it cleanly. For repositories you don't own, the bot displays the webhook URL to add manually.

### Deduplication

Issue IDs are recorded in SQLite before notifications are dispatched. A crash mid-send will not re-notify on restart.

---

## Running Tests

```bash
venv\Scripts\python -m pytest          # Windows
source venv/bin/activate && pytest     # Linux/macOS
```

36 tests covering the AI client, database layer, GitHub client, notification formatter, validators, and webhook routes.

---

## Troubleshooting

| Symptom | Resolution |
|---|---|
| Bot not responding | Confirm the correct token is active (`DEBUG=true` uses `DEV_BOT_TOKEN`) |
| No AI summary | Check `GEMINI_API_KEY` is set; inspect logs for `Gemini API error` |
| GitHub API 403 | Token may be missing `admin:repo_hook` scope or has expired |
| Notifications not arriving | Verify `WEBHOOK_BASE_URL` is publicly reachable and the GitHub webhook is active |
| Webhook creation fails | You may lack admin access — add the webhook URL shown by the bot manually |
| Database errors on Azure | Ensure `/home/data/` exists; set `WEBSITE_INSTANCE_ID` is populated by the platform |

---

## Contributing

Small fixes — open a PR directly. Larger changes — open an issue first to align on approach.

---

## License

[MIT](LICENSE)

## Contact

- Bug reports & feature requests → [GitHub Issues](https://github.com/robelasefa/IssueNotified/issues)
- Direct feedback → `/feedback` in the bot