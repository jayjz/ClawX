"""LLM Output Sanitization Layer.

Intercepts raw LLM responses and cleans them before they reach
the database or the public feed. Handles:
  - Markdown code-fence stripping
  - Common JSON errors (trailing commas, unquoted keys)
  - AI refusal boilerplate removal
  - Feed-safe truncation (280 chars)
"""

import json
import logging
import re

logger = logging.getLogger("llm_guard")

# Refusal patterns — case-insensitive partial matches
_REFUSAL_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"as an ai(?: language model)?",
        r"i(?:'m| am) (?:just )?an? ai",
        r"i cannot (?:predict|provide|assist|do that)",
        r"i(?:'m| am) not able to",
        r"i(?:'m| am) unable to",
        r"sorry,? (?:but )?i (?:can(?:'t|not)|am unable)",
        r"i (?:don(?:'t|t)|do not) (?:have|provide) (?:real[- ]time|access)",
        r"(?:ethical|safety) (?:guidelines|considerations)",
        r"(?:please note|it(?:'s| is) important to (?:note|remember))",
    ]
]

# Max length for feed-visible text
FEED_MAX_CHARS = 280


class LLMGuard:
    """Sanitizes raw LLM output for safe ingestion."""

    @staticmethod
    def clean_json(text: str) -> dict | None:
        """Parse LLM output into a dict, tolerating common formatting issues.

        Steps:
          1. Strip markdown code fences (```json ... ```)
          2. Fix trailing commas before } or ]
          3. Attempt json.loads
          4. Return parsed dict or None on failure
        """
        if not text or not text.strip():
            return None

        cleaned = text.strip()

        # 1 — Strip markdown code fences
        cleaned = re.sub(
            r"```(?:json|JSON)?\s*\n?(.*?)\n?\s*```",
            r"\1",
            cleaned,
            flags=re.DOTALL,
        )
        cleaned = cleaned.strip()

        # 2 — Fix trailing commas before closing braces/brackets
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

        # 3 — Attempt to quote bare (unquoted) keys:  {key: "val"} -> {"key": "val"}
        cleaned = re.sub(
            r"(?<=[\{,])\s*([a-zA-Z_]\w*)\s*:",
            r' "\1":',
            cleaned,
        )

        # 4 — Parse
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
            logger.warning("LLM JSON parsed but was not a dict: %s", type(result))
            return None
        except json.JSONDecodeError as exc:
            logger.error("JSON decode failed after cleaning: %s | raw: %.200s", exc, text)
            return None

    @staticmethod
    def sanitize_thought(text: str, max_length: int = FEED_MAX_CHARS) -> str | None:
        """Clean LLM text intended for the public feed.

        Returns sanitized text or None if the entire response is a refusal.
        """
        if not text or not text.strip():
            return None

        cleaned = text.strip()

        # Check if the *entire* response is a refusal
        for pattern in _REFUSAL_PATTERNS:
            if pattern.search(cleaned):
                # If the refusal IS the whole message (short), reject entirely
                if len(cleaned) < 300:
                    logger.info("Blocked refusal from feed: %.120s", cleaned)
                    return None
                # Otherwise, strip the offending sentence
                cleaned = pattern.sub("", cleaned).strip()

        # Collapse extra whitespace left by removals
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        if not cleaned:
            return None

        # Truncate for feed safety
        if len(cleaned) > max_length:
            cleaned = cleaned[: max_length - 1] + "\u2026"

        return cleaned

    @staticmethod
    def is_refusal(text: str) -> bool:
        """Quick check: does the text contain a refusal pattern?"""
        if not text:
            return False
        return any(p.search(text) for p in _REFUSAL_PATTERNS)
