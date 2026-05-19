"""
AI-powered features for IssueNotified.
"""

import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


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
        """Make a raw call to the Gemini REST API with retries and exponential backoff."""
        if not self.api_key or not self.session:
            return None

        url = f"{GEMINI_API_URL}?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                async with self.session.post(url, json=payload, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "candidates" in data and data["candidates"]:
                            return data["candidates"][0]["content"]["parts"][0][
                                "text"
                            ].strip()

                        logger.warning(
                            f"Gemini API returned unexpected data (possible safety block): {data}"
                        )
                        return None

                    # If 503 (Unavailable) or 429 (Rate Limited), retry with backoff
                    if response.status in (429, 503) and attempt < max_attempts:
                        logger.warning(
                            f"Gemini API returned {response.status} (attempt {attempt}/{max_attempts}). Retrying in {backoff}s..."
                        )
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue

                    logger.error(
                        f"Gemini API error: {response.status} - {await response.text()}"
                    )
                    return None
            except Exception as e:
                if attempt < max_attempts:
                    logger.warning(
                        f"Error calling Gemini API (attempt {attempt}/{max_attempts}): {e}. Retrying in {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                logger.error(f"Error calling Gemini API on final attempt: {e}")
                return None

    async def summarize_issue(self, title: str, description: str) -> Optional[str]:
        """Generate a concise summary of a GitHub issue."""
        if not self.api_key:
            logger.warning("summarize_issue: api_key is missing")
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
            "You are a professional Community Manager and Telegram Bot Admin. "
            "Your task is to transform the following raw text into a rich, engaging, "
            "medium-sized broadcast announcement.\n\n"
            "STYLE & STRUCTURE REQUIREMENTS:\n"
            "- Tone: Inspiring, energetic, professional, and clear.\n"
            "- Length: Medium-sized (approx. 3-4 short paragraphs or logical sections).\n"
            "- Formatting: Organised. Use a bold, attention-grabbing headline, bulleted lists for key points if applicable, and a clear call-to-action at the end.\n"
            "- Emojis: Use context-relevant emojis at the start of paragraphs, headlines, and bullet points to make it visually rich but highly scannable. Do not over-saturate.\n\n"
            "CRITICAL FORMATTING RULES (TELEGRAM MARKDOWN V1):\n"
            "1. The output MUST strictly use Telegram Markdown (V1) rules.\n"
            "2. Allowed tags: *bold*, _italic_, [link text](url), and `inline code` or ```pre-formatted blocks```.\n"
            "3. DO NOT use Markdown V2 syntax (e.g., do not escape standard punctuation like periods, dashes, or exclamation marks with backslashes, as this breaks V1 parsing).\n"
            "4. Ensure all syntax tags (like * and _) are properly closed.\n\n"
            "OUTPUT DIRECTIVE:\n"
            "Provide ONLY the final polished Telegram broadcast message. Do not include any conversational introductions, conclusions, or explanations.\n\n"
            f"Message to polish:\n{text}"
        )
        return await self._call_gemini(prompt)


# Global AI client instance
ai_client = AIClient()


def initialize_ai_client(api_key: str):
    """Initialise the global AI client with the provided API key."""
    ai_client.initialize(api_key)
