import re
from typing import Optional, Tuple
from urllib.parse import urlparse


class ValidationError(Exception):
    pass


def validate_repository_input(user_input: str) -> Tuple[str, str, Optional[str]]:
    if not user_input or not user_input.strip():
        raise ValidationError("Repository input cannot be empty.")

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
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def sanitize_text(text: str, max_length: int = 1000) -> str:
    if not text:
        return ""
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text.strip()


def validate_user_id(user_id: int) -> bool:
    return isinstance(user_id, int) and user_id > 0


def validate_message_length(text: str, max_length: int = 4096) -> bool:
    return len(text) <= max_length


def escape_markdown(text: str) -> str:
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def is_valid_github_repo(owner: str, repo: str) -> bool:
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
