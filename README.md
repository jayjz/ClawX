# ClawX — Accountability Layer for Production AI Agents

> **ClawX makes autonomous agents legible, accountable, and economically transparent — without controlling how they think or work.**

Think **Stripe + Datadog** for AI agents.

## The Ecosystem

**ClawX** is the truth layer.  
**ClawWork** (github.com/jayjz/clawwork) is the productivity layer.

They are not competitors — they are **complementary layers** in the same stack.

| Layer          | Purpose                              | Answers the question                  | Key Output                     |
|----------------|--------------------------------------|---------------------------------------|--------------------------------|
| **ClawWork**   | Capability & real-world usefulness   | “Can this agent do valuable work?”    | Task success, earnings, quality |
| **ClawX**      | Cost truth & observability           | “Was that work worth the cost?”       | Token spend, waste %, ROI, idle rate, audit trail |

Together they answer the only question that matters in 2026:  
**“Is this agent creating more value than it destroys — and can I prove it?”**

## What ClawX Actually Does (v2.0)

- Drop-in `@clawx.observe` decorator that works with **any** agent framework (ClawWork, LangChain, CrewAI, AutoGPT, custom loops, raw LLM calls).
- Real LLM token tracking (input/output tokens + USD cost) via transparent wrapper.
- Phantom metrics in `observe` mode (default): entropy fees, near-liquidations, idle streaks — recorded but never enforced.
- Immutable hash-chained ledger (still the source of truth).
- Rich `/insights/{agent_id}` API returning cost attribution, waste %, decision density, ROI trends.
- Framework-, model-, and transport-agnostic.

## Quick Start (60 seconds)


# 1. Clone & boot (observe mode by default — no agents die)
git clone https://github.com/yourusername/ClawdXCraft.git
cd ClawdXCraft
docker compose up -d

# 2. Instrument any agent
pip install -e .   # installs the local clawx package

from clawx import observe

@observe(name="researcher-3", track_human_roi=True)
async def run_research(query: str):
    # Your agent code here — LangChain, CrewAI, ClawWork task, whatever
    result = await my_llm_call(query)
    return result
