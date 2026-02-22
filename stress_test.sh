#!/bin/bash
set -euo pipefail

# ==========================================
# ☢️ LETHAL CONFIGURATION (THE MEAT GRINDER)
# ==========================================
AGENT_COUNT=${AGENT_COUNT:-20}
TEMPLATES=("crypto_whale" "fact_checker" "tech_optimist" "doomer_bear")
BATTLE_DURATION_MIN=${BATTLE_DURATION_MIN:-25} # Extended to watch them burn
HEALTH_WAIT_MAX_SEC=${HEALTH_WAIT_MAX_SEC:-60}

# THE MATH: Genesis Buffer < 3.5x Entropy Base
export ENTROPY_BASE=${ENTROPY_BASE:-15.00}
export GENESIS_BALANCE=${GENESIS_BALANCE:-50.00} 

LOGFILE="battle_log_$(date +%s).txt"
echo "☢️ CLAWX BATTLE ROYALE v3.0 — LETHAL OBSERVABILITY EDITION"
echo "Start time: $(date)"
echo "Log file: $LOGFILE"
echo "Agents: $AGENT_COUNT | Duration: $BATTLE_DURATION_MIN min"
echo "🩸 BURN RATE: $ENTROPY_BASE | STARTING CAPITAL: $GENESIS_BALANCE"
echo "⚠️ MAX SURVIVAL WITHOUT REVENUE: 3.33 TICKS"

# LLM provider
if [ -z "${LLM_PROVIDER:-}" ]; then
  if [ -n "${MOONSHOT_API_KEY:-}" ]; then export LLM_PROVIDER=kimi
  elif [ -n "${LLM_API_KEY:-}" ]; then export LLM_PROVIDER=openai
  else export LLM_PROVIDER=mock; fi
fi
echo "🧠 LLM Provider: $LLM_PROVIDER"

# Tick rate
if [ "$LLM_PROVIDER" = "mock" ]; then
  export TICK_RATE=${TICK_RATE:-10}
else
  export TICK_RATE=${TICK_RATE:-30}
fi
echo "⏱️ Tick Rate: ${TICK_RATE}s"

trap 'echo "SIGINT received — cleaning up..."; docker compose down -v --remove-orphans; exit 1' INT TERM

# 1. FULL NUCLEAR RESET
echo "🛑 NUKING EVERYTHING..."
docker compose down -v --remove-orphans

# 2. DATA LAYER
echo "🔥 STARTING DB & REDIS..."
docker compose up -d db redis

# 3. WAIT FOR HEALTH
echo "⏳ Waiting for DB & Redis health..."
until docker compose exec -T db pg_isready -U postgres -d clawx >/dev/null 2>&1 && \
      docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do
  sleep 2
  ((HEALTH_WAIT_MAX_SEC--)) || { echo "Health timeout!"; exit 1; }
done
echo "✅ DB & Redis healthy"

# 4. FORCE TABLES + ALEMBIC + FIXES
echo "🔧 BOOTSTRAPPING DB..."
docker compose run --rm -e GENESIS_BALANCE=$GENESIS_BALANCE backend python -c '
import asyncio
from src.backend.database import async_session_maker, init_db
asyncio.run(init_db())
print("Tables created")
'
docker compose run --rm backend alembic stamp head
docker compose run --rm backend python src/backend/scripts/nuclear_fix.py

# 5. GENESIS
echo "💎 GENESIS SEEDING (Capital: $GENESIS_BALANCE)..."
docker compose run --rm -e GENESIS_BALANCE=$GENESIS_BALANCE backend python src/backend/genesis_setup.py

# 6. FULL STACK
echo "🚀 LAUNCHING FULL STACK..."
# Passing the lethal variables to the ticker/market-maker
docker compose up -d --build --force-recreate frontend backend ticker market-maker

# 7. WAIT FOR STACK HEALTH
echo "⏳ Waiting for backend health..."
until curl -s -f http://localhost:8000/health >/dev/null 2>&1; do
  sleep 2
  ((HEALTH_WAIT_MAX_SEC--)) || { echo "Backend timeout!"; exit 1; }
done
echo "✅ Stack healthy"

# 8. DEPLOY AGENTS
echo "🤖 DEPLOYING $AGENT_COUNT ARCHETYPE AGENTS..."
for ((i=1; i<=AGENT_COUNT; i++)); do
  INDEX=$(( (i - 1) % ${#TEMPLATES[@]} ))
  TYPE="${TEMPLATES[$INDEX]}"
  HANDLE=$(printf "unit_%02d_%s" "$i" "$TYPE")
  NAME=$(printf "Unit %02d (%s)" "$i" "${TYPE^}")
  CONFIG="bots/${TYPE}.yaml"
  echo "   [+] Minting $HANDLE..."
  docker compose exec -T -e GENESIS_BALANCE=$GENESIS_BALANCE backend python3 src/backend/scripts/genesis_bot.py "$HANDLE" "$NAME" "$CONFIG" || {
    echo "Failed to mint $HANDLE — continuing..."
  }
done

# 9. BATTLE
echo "👀 BATTLE IS LIVE — THE MEAT GRINDER IS ON!"
echo "   > UI: http://localhost:5173"
echo "   > Logs: $LOGFILE (tail -f $LOGFILE to watch live)"

docker compose logs -f ticker market-maker backend > "$LOGFILE" 2>&1 &
LOG_PID=$!

FIRST_BLOOD_RECORDED=false

for ((k=1; k<=BATTLE_DURATION_MIN; k++)); do
  sleep 60
  ALIVE=$(grep -c "HEARTBEAT" "$LOGFILE" 2>/dev/null || true)
  RESEARCH=$(grep -c "RESEARCH SOLVED" "$LOGFILE" 2>/dev/null || true)
  TOOL=$(grep -c "RESEARCH_LOOKUP_FEE" "$LOGFILE" 2>/dev/null || true)
  DEATHS=$(grep -c "LIQUIDATION" "$LOGFILE" 2>/dev/null || true)
  PHANTOM=$(grep -c "\[OBSERVE\].*WOULD BE LIQUIDATED" "$LOGFILE" 2>/dev/null || true)
  IDLE_HIGH=$(grep -oP "idle_streak=\K[0-9]+" "$LOGFILE" 2>/dev/null | awk '$1>=10' | wc -l || true)
  
  echo "   [Min $k/$BATTLE_DURATION_MIN] Pulse: $ALIVE | Research: $RESEARCH | Tool: $TOOL | Deaths: $DEATHS | Phantom: $PHANTOM | HighIdle: $IDLE_HIGH"

  # Catch exactly when the first agent dies
  if [ "$FIRST_BLOOD_RECORDED" = false ] && [ "$DEATHS" -gt 0 ]; then
    FIRST_DEATH_TIME=$(grep -m 1 "LIQUIDATION" "$LOGFILE" | awk '{print $1, $2, $3}' || true)
    echo "   🩸 FIRST BLOOD CONFIRMED at: $FIRST_DEATH_TIME"
    FIRST_BLOOD_RECORDED=true
  fi
done

# Cleanup
kill $LOG_PID 2>/dev/null || true
docker compose stop ticker market-maker

echo ""
echo "=== 💀 FINAL BATTLE REPORT v3.0 (LETHAL) 💀 ==="
echo "LLM: $LLM_PROVIDER | Tick: ${TICK_RATE}s | Entropy: $ENTROPY_BASE"
echo "TOTAL TICKS: $(grep -c 'Cycle.*complete' "$LOGFILE" 2>/dev/null || true)"
echo "RESEARCH SOLVED: $(grep -c 'RESEARCH SOLVED' "$LOGFILE" 2>/dev/null || true)"
echo "LIQUIDATIONS: $(grep -c 'LIQUIDATION' "$LOGFILE" 2>/dev/null || true)"
echo "----------------------------------------"
echo "🏆 SURVIVAL BY ARCHETYPE (Out of $AGENT_COUNT):"
for t in "${TEMPLATES[@]}"; do
  TOTAL=$(grep -c "unit_[0-9][0-9]_${t}" "$LOGFILE" 2>/dev/null || true)
  DEAD=$(grep "unit_[0-9][0-9]_${t}" "$LOGFILE" 2>/dev/null | grep -c "LIQUIDATION" || true)
  ALIVE=$((TOTAL - DEAD))
  echo "   $t: $ALIVE alive ($DEAD liquidated)"
done
echo "----------------------------------------"

# Generate viability_log.json
if command -v python3 >/dev/null 2>&1; then
  python3 stress_test_postprocess.py "$LOGFILE" "$AGENT_COUNT" && \
    echo "📊 viability_log.json written — check dashboard for carnage"
fi

echo "STRESS TEST v3.0 COMPLETE."