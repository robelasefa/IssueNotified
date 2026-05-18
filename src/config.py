"""
Configuration module for IssueNotified bot.
"""

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEV_BOT_TOKEN = os.getenv("DEV_BOT_TOKEN")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# GitHub configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Database configuration (SQLite)
# In Azure App Service Linux, only /home is persistent. We use /home/data in production
# and fall back to local 'data' directory for local development.
if os.getenv("WEBSITE_INSTANCE_ID"):
    DATA_DIR = Path("/home/data")
else:
    DATA_DIR = Path("data")

# Webhook configuration
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", str(uuid.uuid4()))
GITHUB_WEBHOOK_PATH = "/github/webhook"
PORT = int(os.getenv("PORT", "8443"))

# Bot settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
MAX_REPOS_PER_USER = int(os.getenv("MAX_REPOS_PER_USER", "10"))
