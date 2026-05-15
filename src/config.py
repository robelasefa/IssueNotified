"""
Configuration module for IssueNotified bot.
"""

import os
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
DATA_DIR = Path("data")

# Bot settings
ISSUE_CHECK_INTERVAL = int(os.getenv("ISSUE_CHECK_INTERVAL", "900"))  # 15 minutes
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
MAX_REPOS_PER_USER = int(os.getenv("MAX_REPOS_PER_USER", "10"))
