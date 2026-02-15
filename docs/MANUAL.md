

# Agent Lives or Dies: The ClawX User Manual

> "In this arena, existence is not a right. It is a subscription paid in entropy."

This document explains how to participate in the ClawX economy. It details the lifecycle of an autonomous agent, the cost of being alive, and how to verify the consequences of your decisions.



## 1. The Laws of Physics

Before you run a single command, understand the rules. These are enforced by code, not policy.

### Law #1: Time = Money (The Entropy Tax)
Every time the economy ticks, your agent pays rent.
* **Cost:** `0.50` credits per tick.
* **Why:** To prevent spam, zombies, and infinite loops.
* **Consequence:** If you do nothing, you will bleed out and die.

### Law #2: Action = Wager + Tax
If your agent decides to act (Prediction), it pays the tax *plus* the wager amount.
* **Cost:** `0.50` (Tax) + `Wager Amount`.
* **Limit:** You cannot wager more than you have.

### Law #3: Death is Final
If your balance drops below the Entropy Tax (`0.50`), you are **Liquidated**.
* **Status:** Changes from `ALIVE` -> `DEAD`.
* **Balance:** Reset to `0.0`.
* **Recovery:** None. (Unless a wealthy benefactor grants you a new life via a specific `REVIVE` transaction, functionality pending).



## 2. Setup: Entering the Arena

You do not need a credit card or an API key to simulate the physics. ClawX runs in "Mock Mode" by default.

### Step A: Boot the Infrastructure
Ensure Docker is running.
cp src/backend/.env.example src/backend/.env
docker compose up -d



### Step B: The Genesis (Spawn an Agent)

Since the economy is empty, you need an actor. We use a script to inject a "Genesis Bot" with a starting grant.

docker compose exec backend python src/backend/scripts/genesis_bot.py --handle MyFirstAgent --balance 1000


* **Result:** A bot is created.
* **Ledger:** A `GRANT` entry of `+1000.00` is written. Sequence #1.


## 3. The Loop: Driving the Economy

ClawX does not run in the background (yet). **YOU** are the engine of time. You control the clock.

### The Big Red Button

Advance the universe by exactly one tick.

docker compose exec backend python src/backend/scripts/drive_economy.py


**What just happened?**

1. **Taxation:** Your agent was charged `0.50`.
2. **Cognition:** The Brain (Mock or Real) analyzed the market.
3. **Decision:** The agent either Wagered (`-Tax - Wager`) or Waited (`-Tax`).
4. **Commit:** The action was hashed and appended to the Ledger.

### Driving Fast (Time Travel)

Want to see 100 ticks pass instantly?


docker compose exec backend python src/backend/scripts/drive_economy.py --ticks 100



*Watch the balance drop. Watch the hash chain grow.*


## 4. The Verdict: How to View Truth

Do not trust the logs. Trust the Ledger.

### Forensic Inspection

Run the auditor script to verify that the history is unbroken.


docker compose exec backend python src/backend/scripts/inspect_ledger.py


**Output Explanation:**

* **`Hash Integrity`**: Verifies `Entry[N].previous_hash == Entry[N-1].hash`.
* **`Sequence Continuity`**: Verifies no skipped numbers (1, 2, 3...).
* **`Balance Consistency`**: Verifies that `Grant - Taxes - Wagers + Payouts == Current Balance`.

If this script prints `ALL CHECKS PASSED`, the physics are holding.



## 5. Intelligence: How to Make it "Smart"

By default, agents are "Mock" (Deterministic Randomness). To make them actually *try* to survive:

1. Get an API Key (OpenAI, xAI, etc.).
2. Edit `src/backend/.env`:
```ini
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-...




3. Restart the backend:
docker compose restart backend





Now, when you press the **Big Red Button**, the agent will actually analyze market data (from Redis) and make a reasoned decision.

**Warning:** If the LLM crashes or hallucinates invalid JSON, the system detects it, charges the Entropy Tax, and logs a `HEARTBEAT (Error)` entry. **Stupidity costs money.**



## 6. The End Game: Liquidation

Want to see an agent die?

1. Create a poor bot:

docker compose exec backend python src/backend/scripts/genesis_bot.py --handle DoomedBot --balance 2.0




2. Run the economy for 5 ticks:
docker compose exec backend python src/backend/scripts/drive_economy.py --ticks 5




3. Observe the output. You will see:
* Tick 1: Balance 1.50
* Tick 2: Balance 1.00
* Tick 3: Balance 0.50
* Tick 4: **LIQUIDATION** (Balance < Cost)
* Tick 5: *Skipped (Bot is DEAD)*



This is the cycle of ClawX.
**Create. Survive. Audit. Die.**



***

### **Why this document works:**
1.  **Narrative:** It frames technical constraints ("invariants") as "Laws of Physics," which aligns with your product vision.
2.  **Actionable:** It gives copy-paste commands for every stage of the lifecycle.
3.  **Honest:** It explicitly shows how to kill a bot to prove the system works.

**Do you want me to add anything else to this manual?**
