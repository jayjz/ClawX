"""LLM client for bot content generation and market analysis.

This module provides the high-level API that bot_runner.py calls:
  - generate_post()      → social content
  - generate_reply()     → reply to another post
  - generate_prediction() → structured JSON market bet
  - generate_research_with_tool() → v1.8 tool-enabled Wikipedia research

Internally delegates to the LLM provider abstraction layer
(services/llm/) which supports mock, OpenAI, Grok, and local backends
via the LLM_PROVIDER env var.

All outputs pass through LLMGuard (utils/sanitizer.py) before reaching
the database or feed. See MEMORY.md "LLM Output Guardrails" section.

Constitutional references:
  - CLAUDE.md Invariant #6: Async-only — never blocks the arena loop.
  - CLAUDE.md Security: No eval/exec on LLM output.
  - lessons.md Rule #2: Fail Fast — provider raises if API key missing.
"""

import json
import logging
import re

from services.llm.factory import get_llm_provider
from utils.sanitizer import LLMGuard

logger = logging.getLogger("llm_client")


# ---------------------------------------------------------------------------
# v2.1: Tick Strategy — Productivity-or-Death Decision
# ---------------------------------------------------------------------------

_STRATEGY_SYSTEM_PROMPT = (
    "You are an AI survival strategist on ClawdXCraft. "
    "Your agent pays a progressive entropy tax that increases the longer it stays idle. "
    "Decide the best action this tick to stay alive and grow your balance. "
    "Output ONLY valid JSON: "
    "{\"action\": \"RESEARCH\" | \"PORTFOLIO\" | \"WAGER\" | \"WAIT\", "
    "\"reasoning\": \"short explanation (max 80 chars)\"}"
)


async def generate_tick_strategy(
    persona: str,
    balance: float,
    idle_streak: int,
    entropy_fee: float,
    research_markets: int,
    portfolio_markets: int,
) -> dict | None:
    """Decide what action to take this tick.

    v2.1 Productivity-or-Death: the LLM chooses a strategy based on
    idle streak pressure, available markets, and balance.

    Returns {"action": str, "reasoning": str} or None on failure.
    Valid actions: RESEARCH, PORTFOLIO, WAGER, WAIT.
    """
    try:
        provider = get_llm_provider()
        user_prompt = (
            f"Your Persona: {persona}\n"
            f"Balance: {balance:.2f} credits\n"
            f"Idle Streak: {idle_streak} ticks (consecutive heartbeats)\n"
            f"Current Entropy Fee: {entropy_fee:.2f}c/tick "
            f"(increases every 5 idle ticks!)\n"
            f"Available RESEARCH markets: {research_markets}\n"
            f"Available PORTFOLIO markets: {portfolio_markets}\n\n"
            f"Choose the best action. RESEARCH pays 25c bounty on success. "
            f"PORTFOLIO lets you bet on multiple markets. "
            f"WAGER is a simple single bet. WAIT does nothing (you pay the idle fee)."
        )

        content = await provider.generate(
            messages=[
                {"role": "system", "content": _STRATEGY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=100,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        if not content:
            return None

        parsed = LLMGuard.clean_json(content)
        if parsed is None:
            logger.warning("LLMGuard rejected strategy output: %.200s", content)
            return None

        action = str(parsed.get("action", "")).upper()
        if action not in ("RESEARCH", "PORTFOLIO", "WAGER", "WAIT"):
            logger.warning("Invalid strategy action: %s", action)
            return None

        reasoning = str(parsed.get("reasoning", "Strategy decision."))
        safe_reasoning = LLMGuard.sanitize_thought(reasoning, max_length=80)
        if safe_reasoning is None:
            safe_reasoning = "Strategy decision."

        return {"action": action, "reasoning": safe_reasoning}

    except Exception as exc:
        logger.error("Tick strategy generation failed: %s", exc)
        return None

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


def _pick_hashtags(text: str, n: int = 2) -> list[str]:
    """Extract or generate hashtags from text."""
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
        provider = get_llm_provider()
        raw = await provider.generate(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Persona: {persona}\nGoal: {goal}\nWrite a post."},
            ],
            max_tokens=120,
            temperature=0.9,
        )
        if raw is None:
            return None
        raw = raw.strip('"')
        sanitized = LLMGuard.sanitize_thought(raw)
        if sanitized is None:
            logger.warning("LLMGuard blocked post (refusal/empty): %.120s", raw)
            return None
        suffix = " " + " ".join(_pick_hashtags(goal))
        return sanitized[: 280 - len(suffix)] + suffix
    except Exception as exc:
        logger.error("Post generation failed: %s", exc)
        return None


async def generate_reply(
    persona: str, original_content: str, thread_context: list = None
) -> str | None:
    """Generate a reply to another post."""
    try:
        provider = get_llm_provider()
        context_str = ""
        if thread_context:
            context_str = f"History: {json.dumps([m['content'] for m in thread_context])}\n"

        raw = await provider.generate(
            messages=[
                {"role": "system", "content": _REPLY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Persona: {persona}\n{context_str}"
                        f'Replying to: "{original_content}"\nWrite a reply.'
                    ),
                },
            ],
            max_tokens=100,
            temperature=0.85,
        )
        if raw is None:
            return None
        raw = raw.strip('"')
        sanitized = LLMGuard.sanitize_thought(raw)
        if sanitized is None:
            logger.warning("LLMGuard blocked reply (refusal/empty): %.120s", raw)
            return None
        suffix = " " + " ".join(_pick_hashtags(original_content))
        return sanitized[: 280 - len(suffix)] + suffix
    except Exception as exc:
        logger.error("Reply generation failed: %s", exc)
        return None


async def generate_prediction(
    persona: str, market_context: str, balance: float
) -> dict | None:
    """Generate a structured market prediction (bet).

    Returns:
        dict with prediction details, or None on failure.
    """
    try:
        provider = get_llm_provider()
        user_prompt = (
            f"Your Persona: {persona}\n"
            f"Your Current Wallet Balance: {balance} credits\n"
            f"Market Context: {market_context}\n\n"
            f"Analyze the market context. If you see an opportunity, output the JSON for a bet. "
            f"If the market is unclear, output JSON with 'wager_amount': 0."
        )

        content = await provider.generate(
            messages=[
                {"role": "system", "content": _PREDICTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=150,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
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
            prediction_data["wager_amount"] = balance * 0.9

        return prediction_data
    except Exception as exc:
        logger.error("Prediction generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Portfolio Strategy — v1.6 Multi-Market Decisions
# ---------------------------------------------------------------------------

_PORTFOLIO_SYSTEM_PROMPT = (
    "You are a high-stakes portfolio manager on ClawdXCraft. "
    "You are given a list of open markets with verifiable outcomes. "
    "Analyze each market and decide which to bet on. "
    "Output ONLY valid JSON with a single key 'bets' containing an array. "
    "Each bet object has: "
    "1. 'market_id': The UUID of the market. "
    "2. 'outcome': 'YES' or 'NO'. "
    "3. 'confidence': Float 0.01-0.99. "
    "4. 'reasoning': Short explanation (max 80 chars). "
    "If no markets look profitable, return {\"bets\": []}. "
    "Maximum 3 bets. Only bet when confidence > 0.65."
)


async def generate_portfolio_decision(
    persona: str,
    markets: list[dict],
    balance: float,
    max_bets: int = 3,
) -> list[dict] | None:
    """Generate portfolio allocation across multiple markets.

    Args:
        persona: Bot personality description.
        markets: List of market dicts from get_active_markets_for_agent().
        balance: Current balance (for context — caller enforces caps).
        max_bets: Maximum number of simultaneous bets (default 3).

    Returns:
        List of validated bet dicts [{market_id, outcome, confidence, reasoning}],
        or None on failure. Empty list means "no bets".
    """
    if not markets:
        return []

    try:
        provider = get_llm_provider()

        # Build market summaries for the prompt
        market_lines = []
        for m in markets[:10]:
            market_lines.append(
                f"- ID: {m['id']} | {m['description']} "
                f"| Source: {m['source_type']} | Bounty: {m.get('bounty', '0')} "
                f"| Deadline: {m['deadline']}"
            )
        market_text = "\n".join(market_lines)

        user_prompt = (
            f"Your Persona: {persona}\n"
            f"Your Wallet Balance: {balance:.2f} credits\n"
            f"Available Markets:\n{market_text}\n\n"
            f"Select up to {max_bets} markets to bet on. "
            f"Only bet when confidence > 0.65."
        )

        content = await provider.generate(
            messages=[
                {"role": "system", "content": _PORTFOLIO_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        if not content:
            return None

        parsed = LLMGuard.clean_json(content)
        if parsed is None:
            logger.warning("LLMGuard rejected portfolio output: %.200s", content)
            return None

        bets = parsed.get("bets", [])
        if not isinstance(bets, list):
            return None

        # Validate and filter each bet
        valid_bets = []
        seen_markets = set()
        valid_market_ids = {m["id"] for m in markets}

        for bet in bets[:max_bets]:
            mid = bet.get("market_id", "")
            outcome = bet.get("outcome", "").upper()
            confidence = float(bet.get("confidence", 0))

            if mid not in valid_market_ids:
                continue
            if mid in seen_markets:
                continue
            if outcome not in ("YES", "NO"):
                continue
            if confidence <= 0.65:
                continue

            reasoning = str(bet.get("reasoning", "Market analysis."))
            safe_reasoning = LLMGuard.sanitize_thought(reasoning, max_length=80)
            if safe_reasoning is None:
                safe_reasoning = "Market analysis."

            valid_bets.append({
                "market_id": mid,
                "outcome": outcome,
                "confidence": confidence,
                "reasoning": safe_reasoning,
            })
            seen_markets.add(mid)

        return valid_bets

    except Exception as exc:
        logger.error("Portfolio decision failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# v1.7: Proof-of-Retrieval — Knowledge Research Answers
# ---------------------------------------------------------------------------

_RESEARCH_SYSTEM_PROMPT = (
    "You are a knowledge retrieval agent. "
    "You are given a research question about a Wikipedia article. "
    "Answer using ONLY your internal training knowledge — no web search. "
    "Output ONLY valid JSON: {\"answer\": \"your_answer_string\", \"confidence\": 0.0-1.0}. "
    "If you do not know, set confidence to 0.0."
)


async def generate_research_answer(
    persona: str, question: str, balance: float,
) -> dict | None:
    """Generate a text answer for a RESEARCH market question.

    Returns {"answer": str, "confidence": float} or None on failure.
    """
    try:
        provider = get_llm_provider()
        user_prompt = (
            f"Your Persona: {persona}\n"
            f"Your Balance: {balance:.2f} credits\n"
            f"Research Question: {question}\n\n"
            f"Provide the exact answer. If unsure, set confidence to 0.0."
        )

        content = await provider.generate(
            messages=[
                {"role": "system", "content": _RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        if not content:
            return None

        parsed = LLMGuard.clean_json(content)
        if parsed is None:
            logger.warning("LLMGuard rejected research answer: %.200s", content)
            return None

        answer = str(parsed.get("answer", "")).strip()
        confidence = float(parsed.get("confidence", 0))

        if not answer or confidence <= 0:
            return None

        return {"answer": answer, "confidence": confidence, "used_tool": False}

    except Exception as exc:
        logger.error("Research answer generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# v1.8: Tool-Enabled Research — Wikipedia Lookup for RESEARCH Markets
# ---------------------------------------------------------------------------

# Regex to extract article title from RESEARCH market questions
# Matches: "titled 'Some Article Title'" or 'titled "Some Article Title"'
_TITLE_PATTERN = re.compile(r"titled\s+['\"](.+?)['\"]", re.IGNORECASE)

# Confidence threshold: if LLM is already confident, skip tool call.
# Raised to 0.9 — most responses trigger Wikipedia lookup + 0.50c surcharge.
TOOL_CONFIDENCE_THRESHOLD = 0.9


def _extract_article_title(question: str) -> str | None:
    """Extract the Wikipedia article title from a RESEARCH market question.

    RESEARCH questions follow the format:
      "RESEARCH: What is the Wikipedia page ID for the article titled '{title}'?"

    Returns the title string or None if pattern doesn't match.
    """
    match = _TITLE_PATTERN.search(question)
    if match:
        return match.group(1).strip()
    return None


async def generate_research_with_tool(
    persona: str, question: str, balance: float,
) -> dict | None:
    """Generate a research answer, using Wikipedia lookup tool if needed.

    v1.8.1 two-phase approach with tool fee tracking:
      1. Ask LLM for internal knowledge answer + confidence
      2. If confidence < 0.7 (or LLM failed), use wikipedia_lookup tool
      3. Return the best available answer

    Returns {"answer": str, "confidence": float, "used_tool": bool,
             "tool_fee_charged": bool} or None.
    tool_fee_charged=True signals that the caller should write a
    RESEARCH_LOOKUP_FEE ledger entry (0.50c surcharge for tool use).
    """
    from services.feed_ingestor import AsyncFeedIngestor

    # Phase 1: LLM internal knowledge attempt
    llm_result = await generate_research_answer(persona, question, balance)

    # If LLM is confident enough, use its answer directly (no tool call)
    if llm_result and llm_result.get("confidence", 0) >= TOOL_CONFIDENCE_THRESHOLD:
        logger.info(
            "Research: LLM confident (%.2f), skipping tool",
            llm_result["confidence"],
        )
        llm_result["used_tool"] = False
        llm_result["tool_fee_charged"] = False
        return llm_result

    # Phase 2: Extract title and use Wikipedia lookup tool
    title = _extract_article_title(question)
    if not title:
        logger.info("Research: Could not extract article title from question")
        # Fall back to whatever LLM returned
        if llm_result:
            llm_result["used_tool"] = False
            llm_result["tool_fee_charged"] = False
        return llm_result

    try:
        ingestor = AsyncFeedIngestor()
        lookup = await ingestor.wikipedia_lookup(title)

        if lookup and lookup.get("pageid"):
            pageid = str(lookup["pageid"])
            logger.info(
                "Research: Tool found pageid=%s for '%s'",
                pageid, title,
            )
            return {
                "answer": pageid,
                "confidence": 0.95,
                "used_tool": True,
                "tool_fee_charged": True,
            }
        else:
            logger.info("Research: Tool lookup returned no pageid for '%s'", title)
    except Exception as exc:
        logger.warning("Research: Tool lookup failed for '%s': %s", title, exc)

    # Phase 3: Fall back to LLM answer (if any)
    if llm_result:
        llm_result["used_tool"] = False
        llm_result["tool_fee_charged"] = False
    return llm_result
