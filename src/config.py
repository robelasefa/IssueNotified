import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEV_BOT_TOKEN = os.getenv("DEV_BOT_TOKEN")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

try:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID") or "0")
except ValueError:
    ADMIN_USER_ID = 0

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Azure App Service only persists /home across restarts; fall back to local data/ otherwise.
DATA_DIR = Path("/home/data") if os.getenv("WEBSITE_INSTANCE_ID") else Path("data")

WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    if os.getenv("WEBSITE_INSTANCE_ID"):
        raise RuntimeError("WEBHOOK_SECRET is required in production.")
    WEBHOOK_SECRET = "dev_default_secret (please change)"

GITHUB_WEBHOOK_PATH = "/github/webhook"
PORT = int(os.getenv("PORT", "8443"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
MAX_REPOS_PER_USER = int(os.getenv("MAX_REPOS_PER_USER", "5"))
