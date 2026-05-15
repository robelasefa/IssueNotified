# IssueNotified Bot

> Never miss a GitHub issue again — get telegram notifications the moment something is opened in your favorite repos.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20+-green.svg)](https://python-telegram-bot.org/)
---

## Features

- 🔔 **Real-time notifications** — polls GitHub every 15 minutes and sends an alert the moment a new issue appears
- 🔍 **Repository search** — find repos by name or `owner/repo` and track them with one tap
- 🗂️ **Easy management** — list, track, and untrack repositories via commands or inline buttons
- 🏷️ **Keyword filtering** — only get notified when issues match terms you care about (e.g. `bug,critical`)
- ✅ **Full issue lifecycle** — alerts for both opened and closed issues
- 👑 **Admin tools** — broadcast messages and view system stats
- ⚡ **Rate-limited GitHub API** — stays safely within GitHub's 5 000 req/hour limit

---

## Project Structure

```
IssueNotified/
├── .env.example          # Environment variable template
├── .gitignore
├── README.md
├── requirements.txt
├── src/
│   ├── main.py           # Entry point — registers handlers and starts polling
│   ├── config.py         # Centralised configuration
│   ├── database.py       # SQLite operations
│   ├── github.py         # Async GitHub API client
│   ├── notifier.py       # Background notification engine (JobQueue)
│   ├── ratelimit.py      # Sliding-window rate limiter
│   ├── validators.py     # Input validation helpers
│   ├── error.py          # Global error handler
│   └── callbacks/        # One file per command
│       ├── start.py      # /start
│       ├── help.py       # /help
│       ├── track.py      # /track  (conversation handler)
│       ├── untrack.py    # /untrack (inline buttons)
│       ├── list.py       # /list   (paginated)
│       ├── search.py     # /search + inline tracking
│       ├── stop.py       # /stop   (account deletion)
│       ├── feedback.py   # /feedback
│       ├── stats.py      # /stats  (admin only)
│       └── broadcast.py  # /broadcast (admin only)
├── data/                 # SQLite database (auto-created)
└── logs/                 # Log files (auto-created)
```

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A GitHub Personal Access Token (classic, `repo` scope)

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
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope |
| `ADMIN_USER_ID` | Your Telegram user ID — unlocks `/stats` and `/broadcast` |
| `DEBUG` | Set to `true` to use `DEV_BOT_TOKEN` and verbose logging |
| `ISSUE_CHECK_INTERVAL` | Polling interval in seconds (default: `900` = 15 min) |
| `MAX_REPOS_PER_USER` | Per-user repository cap (default: `10`) |

> **Never commit your `.env` file.** It's already in `.gitignore`.

### 3. Run

```bash
python src/main.py
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

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot not responding | Check `DEBUG` in `.env` — make sure you're messaging the right bot token |
| GitHub API errors (403) | Verify your token has `repo` scope and hasn't expired |
| Notifications not arriving | Confirm `GITHUB_TOKEN` is set; check logs for rate-limit warnings |
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