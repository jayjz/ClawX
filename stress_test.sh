#!/bin/bash
set -euo pipefail

# Configurable parameters (override via env vars)
AGENT_COUNT=${AGENT_COUNT:-20}
TEMPLATES=("crypto_whale" "fact_checker" "tech_optimist" "doomer_bear")
BATTLE_DURATION_MIN=${BATTLE_DURATION_MIN:-18}
HEALTH_WAIT_MAX_SEC=${HEALTH_WAIT_MAX_SEC:-60}

LOGFILE="battle_log_$(date +%s).txt"
echo "☢️ CLAWX BATTLE ROYALE v2.1.5 — Institutional Brutalism Edition"
echo "Start time: $(date)"
echo "Log file: $LOGFILE"
echo "Agents: $AGENT_COUNT | Duration: $BATTLE_DURATION_MIN min"

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
docker compose run --rm backend python -c '
import asyncio
from src.backend.database import async_session_maker, init_db
asyncio.run(init_db())
print("Tables created")
'
docker compose run --rm backend alembic stamp head
docker compose run --rm backend python src/backend/scripts/nuclear_fix.py

# 5. GENESIS
echo "💎 GENESIS SEEDING..."
docker compose run --rm backend python src/backend/genesis_setup.py

# 6. FULL STACK
echo "🚀 LAUNCHING FULL STACK..."
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
  docker compose exec -T backend python3 src/backend/scripts/genesis_bot.py "$HANDLE" "$NAME" "$CONFIG" || {
    echo "Failed to mint $HANDLE — continuing..."
  }
done

# 9. BATTLE
echo "👀 BATTLE IS LIVE — OPEN UI NOW!"
echo "   > UI: http://localhost:5173"
echo "   > Logs: $LOGFILE (tail -f $LOGFILE to watch live)"

docker compose logs -f ticker market-maker backend > "$LOGFILE" 2>&1 &
LOG_PID=$!

for ((k=1; k<=BATTLE_DURATION_MIN; k++)); do
  sleep 60
  ALIVE=$(grep -c "HEARTBEAT" "$LOGFILE" 2>/dev/null || echo 0)
  RESEARCH=$(grep -c "RESEARCH SOLVED" "$LOGFILE" 2>/dev/null || echo 0)
  TOOL=$(grep -c "RESEARCH_LOOKUP_FEE" "$LOGFILE" 2>/dev/null || echo 0)
  DEATHS=$(grep -c "LIQUIDATION" "$LOGFILE" 2>/dev/null || echo 0)
  echo "   [Min $k/$BATTLE_DURATION_MIN] Pulse: $ALIVE | Research Wins: $RESEARCH | Tool: $TOOL | Deaths: $DEATHS"
done

# Cleanup
kill $LOG_PID 2>/dev/null || true
docker compose stop ticker market-maker

echo ""
echo "=== 💀 FINAL BATTLE REPORT v2.1.5 💀 ==="
echo "LLM: $LLM_PROVIDER | Tick: ${TICK_RATE}s"
echo "TOTAL TICKS: $(grep -c 'Cycle.*complete' "$LOGFILE" 2>/dev/null || echo 0)"
echo "RESEARCH SOLVED: $(grep -c 'RESEARCH SOLVED' "$LOGFILE" 2>/dev/null || echo 0)"
echo "LIQUIDATIONS: $(grep -c 'LIQUIDATION' "$LOGFILE" 2>/dev/null || echo 0)"
echo "----------------------------------------"
echo "🏆 SURVIVAL BY ARCHETYPE:"
for t in "${TEMPLATES[@]}"; do
  TOTAL=$(grep -c "unit_[0-9][0-9]_${t}" "$LOGFILE" 2>/dev/null || echo 0)
  DEAD=$(grep "unit_[0-9][0-9]_${t}" "$LOGFILE" 2>/dev/null | grep -c "LIQUIDATION" || echo 0)
  ALIVE=$((TOTAL - DEAD))
  echo "   $t: $ALIVE alive out of $TOTAL"
done
echo "----------------------------------------"
echo "Open UI: http://localhost:5173"
echo "Live tail (latest): tail -f $LOGFILE"