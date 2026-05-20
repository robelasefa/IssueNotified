import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

_MAX_ATTEMPTS = 3
_INITIAL_BACKOFF = 1.0
_RETRYABLE_STATUSES = (429, 503)


class AIClient:
    def __init__(self):
        self.api_key: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

    def initialize(self, api_key: str) -> None:
        self.api_key = api_key

    async def start(self) -> None:
        if self.api_key and not self.session:
            self.session = aiohttp.ClientSession()

    async def stop(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        if not self.api_key or not self.session:
            return None

        # API key is passed as a query parameter per Google's REST convention, not a Bearer header
        url = f"{GEMINI_API_URL}?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        backoff = _INITIAL_BACKOFF
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with self.session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            return data["candidates"][0]["content"]["parts"][0][
                                "text"
                            ].strip()
                        except (KeyError, IndexError):
                            logger.warning(
                                "Gemini response missing expected candidates (safety block?): %s",
                                data,
                            )
                            return None

                    if (
                        response.status in _RETRYABLE_STATUSES
                        and attempt < _MAX_ATTEMPTS
                    ):
                        logger.warning(
                            "Gemini %s on attempt %d/%d — retrying in %.1fs",
                            response.status,
                            attempt,
                            _MAX_ATTEMPTS,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue

                    logger.error(
                        "Gemini API error %s: %s",
                        response.status,
                        await response.text(),
                    )
                    return None

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < _MAX_ATTEMPTS:
                    logger.warning(
                        "Gemini network error on attempt %d/%d (%s) — retrying in %.1fs",
                        attempt,
                        _MAX_ATTEMPTS,
                        e,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                logger.error("Gemini network error on final attempt: %s", e)
                return None

        return None

    async def summarize_issue(self, title: str, description: str) -> Optional[str]:
        if not self.api_key:
            return None

        # Truncated to 2000 chars to avoid inflating token cost on large stack traces.
        body = description[:2000] if description else "No description provided."
        prompt = (
            "Provide a concise 1-2 sentence summary of this GitHub issue. "
            "Focus on the core problem and any immediate action items. No markdown formatting.\n\n"
            f"Title: {title}\nDescription: {body}"
        )
        return await self._call_gemini(prompt)

    async def polish_broadcast(
        self, text: str, bot_username: str = None
    ) -> Optional[str]:
        if not self.api_key:
            return None

        bot_info = ""
        if bot_username:
            bot_link = f"https://t.me/{bot_username}"
            bot_info = f"\n\nBOT CONTEXT (ONLY USE WHEN NEEDED):\n- Bot username: @{bot_username}\n- Bot link: {bot_link}\n- Use this link for call-to-action buttons."

        prompt = (
            "You are a professional Community Manager and Telegram Bot Admin. "
            "Transform the following raw text into a rich, engaging broadcast announcement using standard HTML tags.\n\n"
            "STYLE REQUIREMENTS:\n"
            "- Tone: Inspiring, energetic, professional.\n"
            "- Length: 3-4 short paragraphs.\n"
            "- Use a bold headline, bullet points where applicable, and a clear call-to-action.\n"
            "- Emojis: context-relevant at paragraph and bullet starts. Do not over-saturate.\n\n"
            "CRITICAL TELEGRAM HTML RULES:\n"
            "- You MUST use valid, matching HTML opening and closing tags.\n"
            "- ONLY use these allowed tags: <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strikethrough</s>, <tg-spoiler>spoiler</tg-spoiler>, <a href='URL'>link text</a>, <code>code</code>.\n"
            "- Never leave a tag unclosed (e.g., if you open <b>, you must close it with </b>).\n"
            "- For links, use single quotes inside the href attribute exactly like this: <a href='https://t.me/your_bot'>Text</a>.\n"
            "- Do NOT use markdown characters like *, _, `, or [ anywhere in the message.\n"
            "- For call-to-action links, use the bot link provided in BOT CONTEXT.\n\n"
            "Output ONLY the final HTML message. No markdown blocks, no markdown code fences, no introductions, or explanations.\n\n"
            f"{bot_info}\n\n"
            f"Raw text:\n{text}"
        )
        return await self._call_gemini(prompt)


ai_client = AIClient()


def initialize_ai_client(api_key: str) -> None:
    ai_client.initialize(api_key)
