"""
Main entry point for IssueNotified bot.

Starts the FastAPI webhook server via uvicorn.
"""

import logging

from config import DEBUG, PORT

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    """Start the webhook server."""
    import uvicorn

    logger.info("Starting IssueNotified webhook server…")
    uvicorn.run(
        "webhook:app",
        host="0.0.0.0",
        port=PORT,
        log_level="debug" if DEBUG else "info",
    )


if __name__ == "__main__":
    main()
