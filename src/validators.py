"""
Input validation utilities for the bot.
"""

import re
from typing import Tuple
from urllib.parse import urlparse


class ValidationError(Exception):
    """Raised when user-supplied input fails validation."""

    pass


def validate_repository_input(user_input: str) -> Tuple[str, str]:
    """
    Parse and validate a repository string in ``owner/repo`` format.

    Returns the (owner, repo) tuple preserving the original casing supplied
    by the user.  Canonical casing should be confirmed against the GitHub API
    after this call.

    Raises:
        ValidationError: If the input does not match the expected format.
    """
    if not user_input or not user_input.strip():
        raise ValidationError("Repository input cannot be empty.")

    # Matches owner/repo and optionally anything after it as keywords
    pattern = r"^([a-zA-Z0-9._-]+)\/([a-zA-Z0-9._-]+)(?:\s+(.+))?$"
    match = re.match(pattern, user_input.strip())

    if not match:
        raise ValidationError(
            "Invalid format. Use `owner/repo` or `owner/repo keywords`.\n"
            "Example: `facebook/react bug,critical`"
        )

    owner, repo, keywords = match.groups()

    if len(owner) > 39:
        raise ValidationError("Owner name is too long (max 39 characters).")
    if len(repo) > 100:
        raise ValidationError("Repository name is too long (max 100 characters).")

    return owner, repo, keywords


def validate_url(url: str) -> bool:
    """Return True if *url* is a well-formed HTTP/HTTPS URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def sanitize_text(text: str, max_length: int = 1000) -> str:
    """Strip control characters and truncate *text* to *max_length* chars."""
    if not text:
        return ""
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text.strip()


def validate_user_id(user_id: int) -> bool:
    """Return True for a plausible Telegram user ID."""
    return isinstance(user_id, int) and user_id > 0


def validate_message_length(text: str, max_length: int = 4096) -> bool:
    """Return True if *text* fits within Telegram's message size limit."""
    return len(text) <= max_length


def escape_markdown(text: str) -> str:
    """Escape MarkdownV1 special characters for safe use in Telegram messages."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def is_valid_github_repo(owner: str, repo: str) -> bool:
    """
    Quick check that *owner* and *repo* look like valid GitHub names.

    Does not make any network call — use ``GitHubClient.validate_repository``
    for authoritative validation.
    """
    if not owner or not repo:
        return False
    owner_pattern = r"^[a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?$"
    repo_pattern = r"^[a-zA-Z0-9._-]+$"
    return bool(
        re.match(owner_pattern, owner)
        and re.match(repo_pattern, repo)
        and len(owner) <= 39
        and len(repo) <= 100
    )
