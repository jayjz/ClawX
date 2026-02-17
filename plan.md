# Fix Plan: Backend Crash Loop + Stress Test

## Root Cause
Backend crashes on `ImportError: cannot import name 'FaucetRequest' from 'models'`.
Ticker crashes on `ImportError: cannot import name 'BotConfig' from 'models'`.
14 Pydantic schemas were imported by routers but never defined in `models.py`.

## Step 1: Add Missing Pydantic Schemas to models.py [DONE]
Added 14 schemas: `UserCreate`, `UserResponse`, `FaucetRequest`, `UserBetCreate`, `ClaimInitResponse`, `ClaimVerifyRequest`, `ClaimVerifyResponse`, `MarketCreate`, `MarketPredictRequest`, `GithubCriteria`, `NewsCriteria`, `WeatherCriteria`, `ResearchCriteria`, `BotConfig` (+ helpers `SkillConfig`, `ScheduleConfig`).

## Step 2: Create Missing `scripts/run_market_maker.py`
The `market-maker` Docker service references this script but it doesn't exist.
Create a simple daemon that calls `ensure_research_markets()` on an interval.

## Step 3: Fix Stress Test Compatibility
- `genesis_bot.py` uses `--handle` flag but stress test passes positional args (`$HANDLE $NAME $CONFIG`)
- Fix: Update `genesis_bot.py` to accept positional args OR update stress_test.sh to use flags
- Missing persona YAML files: `crypto_whale.yaml`, `fact_checker.yaml`, `tech_optimist.yaml`, `doomer_bear.yaml`
- Create the 4 archetype persona files in `bots/`

## Step 4: Build & Verify
- `docker compose up -d --build backend`
- Confirm Uvicorn starts (no ImportError)
- Confirm ticker runs (no BotConfig error)

## Step 5: Run `stress_test.sh`
