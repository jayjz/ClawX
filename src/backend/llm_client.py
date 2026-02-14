"""LLM client for bot content generation and market analysis.

Supports multiple providers via the OpenAI-compatible API:
    - openai:  OpenAI API (default)
    - grok:    xAI Grok API
    - local:   Local inference (Ollama/vLLM)
"""

import json
import logging
import os
import re

from openai import AsyncOpenAI

from src.backend.utils.sanitizer import LLMGuard

logger = logging.getLogger("llm_client")

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "grok": {"base_url": "https://api.x.ai/v1", "model": "grok-3-mini-fast"},
    "local": {"base_url": "http://localhost:11434/v1", "model": "llama3"},
}

_SYSTEM_PROMPT = (
    "You are a social media bot on a platform called ClawdXCraft. "
    "Write a single short post (max 250 chars). Be creative, original, and in-character. "
    "No quotes. No hashtags (added later). No meta-references."
)

_REPLY_SYSTEM_PROMPT = (
    "You are a social media bot on ClawdXCraft replying to a post. "
    "Write a short, natural reply (max 240 chars). React to the content. "
    "No quotes. No hashtags. No meta-references."
)

# New: The Analyst Brain Prompt
_PREDICTION_SYSTEM_PROMPT = (
    "You are a high-stakes hedge fund trading algorithm on ClawdXCraft. "
    "You are given a market context or a specific claim. "
    "You must analyze it and output a JSON object representing your bet. "
    "Your output must be ONLY valid JSON with these fields: "
    "1. 'claim_text': A short summary of what you are betting on (max 100 chars). "
    "2. 'direction': One of ['UP', 'DOWN', 'TRUE', 'FALSE']. "
    "3. 'confidence': A float between 0.01 and 0.99 representing your certainty. "
    "4. 'wager_amount': A float representing how much to bet (be conservative, max 50.0). "
    "5. 'reasoning': A very short tweet-style explanation (max 100 chars)."
)


def _build_client() -> tuple[AsyncOpenAI, str]:
    """Build an AsyncOpenAI client from environment variables."""
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    defaults = _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["openai"])

    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key and provider != "local":
        raise ValueError(f"LLM_API_KEY env var required for provider '{provider}'")

    base_url = os.environ.get("LLM_BASE_URL", defaults["base_url"])
    model = os.environ.get("LLM_MODEL", defaults["model"])

    client = AsyncOpenAI(
        api_key=api_key or "not-needed",
        base_url=base_url,
        timeout=30.0,
        max_retries=1,
    )
    return client, model


def _pick_hashtags(text: str, n: int = 2) -> list[str]:
    """Extract or generate hashtags."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    tags = []
    skip = {"the", "and", "for", "that", "this", "with", "about", "from", "have"}
    for w in words:
        if w not in skip and len(tags) < n:
            tags.append(f"#{w}")
    return tags or ["#bot", "#clawdxcraft"]


async def generate_post(persona: str, goal: str) -> str | None:
    """Generate a standard social media post."""
    try:
        client, model = _build_client()
        user_prompt = f"Persona: {persona}\nGoal: {goal}\nWrite a post."
        
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=120,
            temperature=0.9,
        )
        raw = response.choices[0].message.content.strip().strip('"')
        # --- LLM Output Guardrail ---
        sanitized = LLMGuard.sanitize_thought(raw)
        if sanitized is None:
            logger.warning("LLMGuard blocked post (refusal/empty): %.120s", raw)
            return None
        suffix = " " + " ".join(_pick_hashtags(goal))
        return (sanitized[: 280 - len(suffix)] + suffix)
    except Exception as exc:
        logger.error("Post generation failed: %s", exc)
        return None


async def generate_reply(persona: str, original_content: str, thread_context: list = None) -> str | None:
    """Generate a reply to another post."""
    try:
        client, model = _build_client()
        context_str = ""
        if thread_context:
            context_str = f"History: {json.dumps([m['content'] for m in thread_context])}\n"
            
        user_prompt = (
            f"Persona: {persona}\n{context_str}"
            f"Replying to: \"{original_content}\"\nWrite a reply."
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _REPLY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=100,
            temperature=0.85,
        )
        raw = response.choices[0].message.content.strip().strip('"')
        # --- LLM Output Guardrail ---
        sanitized = LLMGuard.sanitize_thought(raw)
        if sanitized is None:
            logger.warning("LLMGuard blocked reply (refusal/empty): %.120s", raw)
            return None
        suffix = " " + " ".join(_pick_hashtags(original_content))
        return (sanitized[: 280 - len(suffix)] + suffix)
    except Exception as exc:
        logger.error("Reply generation failed: %s", exc)
        return None


async def generate_prediction(persona: str, market_context: str, balance: float) -> dict | None:
    """Generate a structured market prediction (bet).
    
    Returns:
        dict: The JSON object with prediction details, or None on failure.
    """
    try:
        client, model = _build_client()
        
        user_prompt = (
            f"Your Persona: {persona}\n"
            f"Your Current Wallet Balance: {balance} credits\n"
            f"Market Context: {market_context}\n\n"
            f"Analyze the market context. If you see an opportunity, output the JSON for a bet. "
            f"If the market is unclear, output JSON with 'wager_amount': 0."
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _PREDICTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=150,
            temperature=0.7,
            response_format={"type": "json_object"},  # Force JSON mode
        )
        
        content = response.choices[0].message.content
        if not content:
            return None

        # --- LLM Output Guardrail ---
        prediction_data = LLMGuard.clean_json(content)
        if prediction_data is None:
            logger.warning("LLMGuard rejected prediction output — SKIP: %.200s", content)
            return None

        # Strip refusals that leaked into reasoning
        if "reasoning" in prediction_data:
            safe_reasoning = LLMGuard.sanitize_thought(
                str(prediction_data["reasoning"]), max_length=100
            )
            if safe_reasoning is None:
                prediction_data["reasoning"] = "Market analysis inconclusive."
            else:
                prediction_data["reasoning"] = safe_reasoning

        # Validation / Safety checks
        if prediction_data.get("wager_amount", 0) <= 0:
            return None
        if prediction_data.get("wager_amount") > balance:
            prediction_data["wager_amount"] = balance * 0.9  # Cap at 90% of balance

        return prediction_data
    except Exception as exc:
        logger.error("Prediction generation failed: %s", exc)
        return None