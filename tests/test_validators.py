import pytest

from src.validators import ValidationError, validate_repository_input


def test_validate_repository_input_success():
    owner, repo, keywords = validate_repository_input("facebook/react")
    assert owner == "facebook"
    assert repo == "react"
    assert keywords is None


def test_validate_repository_input_with_keywords():
    owner, repo, keywords = validate_repository_input("facebook/react bug,critical")
    assert owner == "facebook"
    assert repo == "react"
    assert keywords == "bug,critical"


def test_validate_repository_input_invalid_format():
    with pytest.raises(ValidationError) as excinfo:
        validate_repository_input("invalid_format")
    assert "Invalid format" in str(excinfo.value)


def test_validate_repository_input_empty():
    with pytest.raises(ValidationError) as excinfo:
        validate_repository_input("   ")
    assert "cannot be empty" in str(excinfo.value)


def test_validate_repository_input_long_names():
    long_owner = "a" * 40
    with pytest.raises(ValidationError) as excinfo:
        validate_repository_input(f"{long_owner}/repo")
    assert "too long" in str(excinfo.value)
