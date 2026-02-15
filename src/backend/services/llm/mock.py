"""Deterministic mock LLM provider for testing.

Returns predictable, hash-derived responses so that:
  - Tests are reproducible (no network, no API keys needed)
  - The arena physics engine can run without external dependencies
  - CI/CD pipelines never hit rate limits or cost money

Constitutional references:
  - CLAUDE.md Invariant #4: "Irreversible loss is real" — mock produces
    real wager amounts so liquidation logic still fires in tests.
  - lessons.md Rule #3: "Test Fixtures Must Guarantee Isolation" —
    deterministic output = no flaky tests from LLM randomness.
"""

import hashlib
import json

from services.llm.interface import LLMProvider


class MockLLMProvider(LLMProvider):
    """Returns deterministic responses derived from prompt content hash."""

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 150,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> str | None:
        # Build a deterministic seed from the full message content
        prompt_blob = "|".join(m.get("content", "") for m in messages)
        seed = hashlib.md5(prompt_blob.encode()).hexdigest()[:8]

        # If caller wants JSON (prediction mode), return valid JSON
        if response_format and response_format.get("type") == "json_object":
            # Derive a pseudo-random direction and amount from the hash
            direction = "UP" if int(seed, 16) % 2 == 0 else "DOWN"
            confidence = round(0.3 + (int(seed[:4], 16) % 50) / 100, 2)
            wager = round(5.0 + (int(seed[4:], 16) % 40), 2)
            return json.dumps({
                "claim_text": f"Mock prediction [{seed}]",
                "direction": direction,
                "confidence": confidence,
                "wager_amount": wager,
                "reasoning": f"Deterministic mock analysis [{seed}]",
            })

        # Default: return a plain text post/reply
        return f"Mock response [{seed}]: The arena demands sacrifice."
