"""
Debug bot to test individual components.
"""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def debug_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug start command with detailed logging."""
    logger.info(f"Received /start command from user {update.effective_user.id}")
    logger.info(f"Update details: {update}")

    try:
        await update.message.reply_text("🤖 DEBUG: Bot received your command!")
        logger.info("Reply sent successfully")
    except Exception as e:
        logger.error(f"Failed to send reply: {e}")


async def debug_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show debug info."""
    info = f"""
🔍 *Debug Info:*
• Bot Token: {config.BOT_TOKEN[:10]}...
• User ID: {update.effective_user.id}
• Chat ID: {update.effective_chat.id}
• Update Type: {update.update_id}
• Message Text: {update.message.text}
    """
    await update.message.reply_text(info, parse_mode="Markdown")


async def test_github(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test GitHub integration."""
    from github import get_github_client

    client = get_github_client()
    if client:
        await update.message.reply_text("✅ GitHub client initialized")
    else:
        await update.message.reply_text("❌ GitHub client not initialized")


def main():
    """Run debug bot."""
    logger.info("Starting DEBUG bot...")

    # Force use BOT_TOKEN (not DEV_BOT_TOKEN)
    token = config.BOT_TOKEN
    logger.info(f"Using BOT_TOKEN: {token[:10]}...")

    # Create application
    application = Application.builder().token(token).build()

    # Add debug handlers
    application.add_handler(CommandHandler("start", debug_start))
    application.add_handler(CommandHandler("debug", debug_info))
    application.add_handler(CommandHandler("test", test_github))

    logger.info("Debug handlers registered")

    # Initialize GitHub
    import os

    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        from github import initialize_github_client

        initialize_github_client(github_token)
        logger.info("GitHub client initialized")

    # Start bot with detailed logging
    logger.info("Starting polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
