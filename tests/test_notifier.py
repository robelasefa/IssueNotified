from src.notifier import _matches_keywords


def test_matches_keywords_no_keywords():
    """Should match everything if no keywords are provided."""
    issue = {"title": "Hello World", "description": "This is a test", "tags": ["bug"]}
    assert _matches_keywords(issue, "") is True
    assert _matches_keywords(issue, None) is True


def test_matches_keywords_in_title():
    """Should match if keyword is in the title."""
    issue = {"title": "CRITICAL: Database down", "description": "...", "tags": []}
    assert _matches_keywords(issue, "critical") is True
    assert _matches_keywords(issue, "safe") is False


def test_matches_keywords_in_body():
    """Should match if keyword is in the description."""
    issue = {
        "title": "Error",
        "description": "This is a security vulnerability",
        "tags": [],
    }
    assert _matches_keywords(issue, "security") is True


def test_matches_keywords_in_tags():
    """Should match if keyword matches one of the labels."""
    issue = {"title": "Update", "description": "...", "tags": ["feature", "ui"]}
    assert _matches_keywords(issue, "ui") is True
    assert _matches_keywords(issue, "ux") is False


def test_matches_keywords_comma_separated():
    """Should match if any of the comma-separated keywords match."""
    issue = {"title": "Small bug", "description": "...", "tags": ["minor"]}
    assert _matches_keywords(issue, "critical,bug,emergency") is True


def test_matches_keywords_case_insensitive():
    """Keywords should be case-insensitive."""
    issue = {"title": "BUG FOUND", "description": "...", "tags": []}
    assert _matches_keywords(issue, "bug") is True
