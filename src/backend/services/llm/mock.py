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
            # Detect strategy mode: prompt mentions "Idle Streak"
            if "Idle Streak" in prompt_blob:
                return self._strategy_response(prompt_blob, seed)

            # Detect research mode: prompt mentions "Wikipedia page ID"
            if "Wikipedia page ID" in prompt_blob or "Research Question" in prompt_blob:
                return self._research_response(seed)

            # Detect portfolio mode: prompt mentions "Available Markets"
            if "Available Markets" in prompt_blob:
                return self._portfolio_response(prompt_blob, seed)

            # Legacy single-bet prediction
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

    @staticmethod
    def _strategy_response(prompt_blob: str, seed: str) -> str:
        """Generate a deterministic strategy decision based on available markets.

        Prioritizes: RESEARCH (if available) > PORTFOLIO > WAGER > WAIT.
        """
        import re
        # Extract counts from the prompt
        research_match = re.search(r"Available RESEARCH markets:\s*(\d+)", prompt_blob)
        portfolio_match = re.search(r"Available PORTFOLIO markets:\s*(\d+)", prompt_blob)
        research_count = int(research_match.group(1)) if research_match else 0
        portfolio_count = int(portfolio_match.group(1)) if portfolio_match else 0

        if research_count > 0:
            action = "RESEARCH"
            reasoning = f"Mock: {research_count} research bounties available"
        elif portfolio_count > 0:
            action = "PORTFOLIO"
            reasoning = f"Mock: {portfolio_count} portfolio markets open"
        elif int(seed[0], 16) % 3 != 0:
            action = "WAGER"
            reasoning = "Mock: no markets, placing single wager"
        else:
            action = "WAIT"
            reasoning = "Mock: nothing profitable available"

        return json.dumps({"action": action, "reasoning": reasoning})

    @staticmethod
    def _portfolio_response(prompt_blob: str, seed: str) -> str:
        """Generate a deterministic portfolio JSON from market IDs in the prompt."""
        import re

        # Extract UUIDs from the prompt (market IDs)
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        found_ids = re.findall(uuid_pattern, prompt_blob)

        if not found_ids:
            return json.dumps({"bets": []})

        # Deterministically pick up to 2 markets based on seed
        pick_count = min(2, len(found_ids), 1 + int(seed[0], 16) % 2)
        bets = []
        for i in range(pick_count):
            mid = found_ids[i]
            # Derive confidence > 0.65 from seed
            confidence = round(0.70 + (int(seed[i * 2:(i + 1) * 2], 16) % 25) / 100, 2)
            outcome = "YES" if int(seed[i], 16) % 2 == 0 else "NO"
            bets.append({
                "market_id": mid,
                "outcome": outcome,
                "confidence": confidence,
                "reasoning": f"Mock portfolio bet [{seed}:{i}]",
            })

        return json.dumps({"bets": bets})

    @staticmethod
    def _research_response(seed: str) -> str:
        """Generate a deterministic research answer JSON.

        Returns a numeric answer derived from seed (won't match real hashes,
        but tests mock at a higher level for correctness checks).
        """
        answer = str(int(seed, 16) % 100000)
        confidence = round(0.60 + (int(seed[:4], 16) % 35) / 100, 2)
        return json.dumps({"answer": answer, "confidence": confidence})
