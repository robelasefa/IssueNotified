"""
AI-powered features for IssueNotified.
"""

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


class AIClient:
    """Lightweight asynchronous client for Gemini API."""

    def __init__(self):
        self.api_key: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

    def initialize(self, api_key: str):
        """Set the API key."""
        self.api_key = api_key

    async def start(self):
        """Start the aiohttp session."""
        if self.api_key and not self.session:
            self.session = aiohttp.ClientSession()

    async def stop(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """Make a raw call to the Gemini REST API."""
        if not self.api_key or not self.session:
            return None

        url = f"{GEMINI_API_URL}?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            async with self.session.post(url, json=payload, timeout=15) as response:
                if response.status != 200:
                    logger.error(
                        f"Gemini API error: {response.status} - {await response.text()}"
                    )
                    return None

                data = await response.json()
                if "candidates" in data and data["candidates"]:
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return None
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return None

    async def summarize_issue(self, title: str, description: str) -> Optional[str]:
        """Generate a concise summary of a GitHub issue."""
        if not self.api_key:
            return None

        # Truncate description to avoid massive payloads for huge stack traces
        truncated_desc = (
            description[:2000] if description else "No description provided."
        )

        prompt = (
            "Please provide a concise, 1-2 sentence summary of the following GitHub issue. "
            "Focus on the core problem and any immediate action items. Do not use any markdown formatting.\n\n"
            f"Title: {title}\n"
            f"Description: {truncated_desc}"
        )
        return await self._call_gemini(prompt)

    async def polish_broadcast(self, text: str) -> Optional[str]:
        """Refine and format an admin broadcast message."""
        if not self.api_key:
            return None

        prompt = (
            "You are a helpful assistant for a Telegram Bot Admin. "
            "Please polish the following announcement message to make it professional, clear, and engaging. "
            "CRITICAL REQUIREMENT: The output MUST be strictly valid Telegram Markdown (V1) format. "
            "In Telegram Markdown V1, you can use *bold*, _italic_, [link text](url), and `code`. "
            "Do NOT escape normal punctuation (like ., -, !, etc.) outside of code blocks as it breaks Markdown V1! "
            "Only format the text, do not add any conversational filler like 'Here is your polished message:'.\n\n"
            f"Message to polish:\n{text}"
        )
        return await self._call_gemini(prompt)


# Global AI client instance
ai_client = AIClient()


def initialize_ai_client(api_key: str):
    """Initialise the global AI client with the provided API key."""
    ai_client.initialize(api_key)
