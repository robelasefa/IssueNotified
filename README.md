# IssueNotified Bot

> Never miss a GitHub issue again — get telegram notifications the moment something is opened in your favorite repos.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20+-green.svg)](https://python-telegram-bot.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
---

## Features

- 🔔 **Real-time notifications** — receives GitHub webhook events the moment an issue is opened or closed
- 🔍 **Repository search** — find repos by name or `owner/repo` and track them with one tap
- 🗂️ **Easy management** — list, track, and untrack repositories via commands or inline buttons
- 🏷️ **Keyword filtering** — only get notified when issues match terms you care about (e.g. `bug,critical`)
- ✅ **Full issue lifecycle** — alerts for both opened and closed issues
- 👑 **Admin tools** — broadcast messages and view system stats
- ⚡ **Webhook-based** — no polling; events are pushed instantly via GitHub & Telegram webhooks
- 🚀 **Heroku-ready** — deploys in minutes with the included `Procfile`

---

## Architecture

IssueNotified runs as a **FastAPI** web server with two webhook endpoints:

| Endpoint | Source | Purpose |
|---|---|---|
| `POST /telegram` | Telegram Bot API | Receives user messages and commands |
| `POST /github/webhook` | GitHub | Receives issue events from tracked repositories |
| `GET /health` | Monitoring | Health check |

When a user tracks a repository, the bot attempts to install a GitHub webhook automatically. If permissions are insufficient (user doesn't own the repo), the webhook URL can be added manually.

---

## Project Structure

```
IssueNotified/
├── .env.example          # Environment variable template
├── .gitignore
├── Procfile              # Heroku deployment
├── runtime.txt           # Python version for Heroku
├── README.md
├── requirements.txt
├── src/
│   ├── main.py           # Entry point — starts uvicorn
│   ├── webhook.py        # FastAPI app with webhook endpoints
│   ├── config.py         # Centralised configuration
│   ├── database.py       # SQLite operations
│   ├── github.py         # Async GitHub API client + webhook management
│   ├── notifier.py       # Webhook event processor + notification engine
│   ├── ratelimit.py      # Sliding-window rate limiter
│   ├── validators.py     # Input validation helpers
│   ├── error.py          # Global error handler
│   └── callbacks/        # One file per command
│       ├── start.py      # /start
│       ├── help.py       # /help
│       ├── track.py      # /track  (conversation handler + webhook install)
│       ├── untrack.py    # /untrack (inline buttons + webhook cleanup)
│       ├── list.py       # /list   (paginated)
│       ├── search.py     # /search + inline tracking
│       ├── stop.py       # /stop   (account deletion)
│       ├── feedback.py   # /feedback
│       ├── stats.py      # /stats  (admin only)
│       └── broadcast.py  # /broadcast (admin only)
├── data/                 # SQLite database (auto-created)
├── logs/                 # Log files (auto-created)
└── tests/                # Pytest test suite
```

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A GitHub Personal Access Token (classic, `repo` + `admin:repo_hook` scopes)
- A publicly reachable HTTPS URL (Heroku, Render, or ngrok for local dev)

### 1. Clone and install

```bash
git clone https://github.com/robelasefa/IssueNotified.git
cd IssueNotified
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Production bot token from @BotFather |
| `DEV_BOT_TOKEN` | (Optional) Separate token for testing |
| `GITHUB_TOKEN` | GitHub PAT with `repo` + `admin:repo_hook` scopes |
| `ADMIN_USER_ID` | Your Telegram user ID — unlocks `/stats` and `/broadcast` |
| `WEBHOOK_BASE_URL` | Public HTTPS URL (e.g. `https://your-app.herokuapp.com`) |
| `WEBHOOK_SECRET` | Shared secret for GitHub webhook HMAC validation (auto-generated if empty) |
| `PORT` | Server port (default: `8443`, Heroku sets this automatically) |
| `DEBUG` | Set to `true` to use `DEV_BOT_TOKEN` and verbose logging |
| `MAX_REPOS_PER_USER` | Per-user repository cap (default: `10`) |

> **Never commit your `.env` file.** It's already in `.gitignore`.

### 3. Run locally

```bash
# Option A: Use ngrok for a public HTTPS URL
ngrok http 8443
# Copy the https URL to WEBHOOK_BASE_URL in .env

# Option B: Direct start
python src/main.py
```

### 4. Deploy to Heroku

```bash
heroku create your-app-name
heroku config:set BOT_TOKEN=... GITHUB_TOKEN=... WEBHOOK_BASE_URL=https://your-app-name.herokuapp.com WEBHOOK_SECRET=... ADMIN_USER_ID=...
git push heroku feature/webhook-fastapi:main
```

---

## Commands

### User commands

| Command | Description |
|---|---|
| `/start` | Register your account |
| `/help` | Show all commands |
| `/track` | Track a new repository |
| `/untrack` | Stop tracking a repository |
| `/list` | View all your tracked repositories |
| `/search <query>` | Search GitHub — by name or `owner/repo` |
| `/feedback` | Send feedback to the developer |
| `/stop` | Delete your account and all data |

### Admin commands

| Command | Description |
|---|---|
| `/stats` | System stats — total users, popular repos |
| `/broadcast <message>` | Send a message to all users (Markdown supported) |

---

## Feature Highlights

### Keyword Filtering

When tracking a repository you can supply comma-separated keywords. You'll only be notified when the issue title, body, or labels match at least one of them — useful for large projects where you only care about specific topics.

```
/track
> facebook/react
> bug,performance
```

### One-tap Stop Tracking

Every notification includes a **🔕 Stop Tracking** inline button. Tapping it asks for confirmation before untracking, so accidental taps don't lose your subscription.

### Smart Search

```
/search react              # full-text search across GitHub
/search facebook/react     # scoped to a specific owner
```

Results appear as an inline list with a **➕ Track** button on each entry.

### Automatic Webhook Installation

When you track a repository you own (or have admin access to), the bot automatically installs a GitHub webhook. For repos you don't own, you can manually add the webhook URL shown by the bot.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot not responding | Check `DEBUG` in `.env` — make sure you're messaging the right bot token |
| GitHub API errors (403) | Verify your token has `repo` and `admin:repo_hook` scopes and hasn't expired |
| Notifications not arriving | Confirm `WEBHOOK_BASE_URL` is set and reachable; check logs |
| Webhook creation fails | You may not have admin access to the repo — add the webhook URL manually |
| Database errors | Ensure the `data/` directory is writable; restart to reinitialise |

Enable verbose logging at any time by setting `DEBUG=true` in `.env`.

---

## Contributing

Contributions are welcome! For small fixes, open a PR directly. For larger changes, please open an issue first so we can discuss the approach.

If you find this project useful, a ⭐ on GitHub helps others discover it — thank you!

---

## License

[MIT](LICENSE) — free to use, modify, and distribute with attribution.

## Contact

- Bug reports & feature requests → [GitHub Issues](https://github.com/robelasefa/IssueNotified/issues)
- Direct feedback → `/feedback` inside the bot