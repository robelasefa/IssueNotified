from unittest.mock import AsyncMock

import pytest

from src.ai import AIClient


@pytest.fixture
def ai_client():
    client = AIClient()
    client.initialize("fake_api_key")
    return client


@pytest.mark.asyncio
async def test_ai_client_start_stop(ai_client):
    await ai_client.start()
    assert ai_client.session is not None
    await ai_client.stop()
    assert ai_client.session is None


@pytest.mark.asyncio
async def test_summarize_issue_success(ai_client, mocker):
    await ai_client.start()

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "This is a mock summary."}]}}]
    }

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_response
    mocker.patch.object(ai_client.session, "post", return_value=mock_context_manager)

    summary = await ai_client.summarize_issue("Bug", "It crashes.")
    assert summary == "This is a mock summary."

    await ai_client.stop()


@pytest.mark.asyncio
async def test_summarize_issue_missing_key():
    client = AIClient()
    summary = await client.summarize_issue("Bug", "It crashes.")
    assert summary is None


@pytest.mark.asyncio
async def test_polish_broadcast_success(ai_client, mocker):
    await ai_client.start()

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Polished *Markdown*!"}]}}]
    }

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_response
    mocker.patch.object(ai_client.session, "post", return_value=mock_context_manager)

    polished = await ai_client.polish_broadcast("Hello world")
    assert polished == "Polished *Markdown*!"

    await ai_client.stop()
