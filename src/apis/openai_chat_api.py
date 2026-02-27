"""
OpenAI Chat API Wrapper (GPT-5 Mini)

Handles GPT-5 Mini API calls for lightweight LLM tasks in the pipeline
(image prompt generation, pin copy). Uses the raw requests library for
HTTP calls to the OpenAI chat completions endpoint.

Used as a cost-saving alternative to Claude for routine tasks, with
Claude Sonnet as the fallback when GPT-5 Mini fails.

Environment variables required:
- OPENAI_API_KEY
- OPENAI_CHAT_MODEL (optional, defaults to "gpt-5-mini")
"""

import logging
import os
import time

import requests

from src.config import OPENAI_CHAT_MODEL, GPT5_MINI_COST_PER_MTK

logger = logging.getLogger(__name__)

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIChatAPIError(Exception):
    """Raised when OpenAI Chat API calls fail."""
    pass


def call_gpt5_mini(
    prompt: str,
    system: str,
    max_tokens: int = 500,
    temperature: float = 0.8,
    timeout: int = 30,
) -> str:
    """
    Call GPT-5 Mini via the OpenAI Chat Completions API.

    Makes a single request with one automatic retry on 429 rate limit.

    Args:
        prompt: The user message / prompt.
        system: System prompt.
        max_tokens: Maximum response tokens.
        temperature: Sampling temperature.
        timeout: HTTP request timeout in seconds.

    Returns:
        str: The assistant's response text.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
        requests.HTTPError: On non-retryable HTTP errors.
        OpenAIChatAPIError: On unexpected failures.
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not set")

    model = OPENAI_CHAT_MODEL

    def _do_request() -> requests.Response:
        return requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=timeout,
        )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        response = _do_request()

        if response.status_code != 429:
            break

        if attempt == max_retries:
            break  # exhausted retries, fall through to raise_for_status

        retry_after = response.headers.get("Retry-After")
        try:
            wait = int(retry_after) if retry_after else 5
        except (ValueError, TypeError):
            wait = 5
        # Exponential backoff: multiply base wait by attempt number, cap at 60s
        wait = min(wait * attempt, 60)
        logger.warning(
            "OpenAI 429 rate limit (attempt %d/%d). Retrying after %ds...",
            attempt, max_retries, wait,
        )
        time.sleep(wait)

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
