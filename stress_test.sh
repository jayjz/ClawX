#!/bin/bash
set -e

echo "☢️ CLAWX BATTLE ROYALE v2.1.2 — Living Arena Edition"
echo "Start time: $(date)"
LOGFILE="battle_log_$(date +%s).txt"
echo "Log file: $LOGFILE"

# LLM PROVIDER AUTO-DETECTION
if [ -z "$LLM_PROVIDER" ]; then
  if [ -n "$MOONSHOT_API_KEY" ]; then
    export LLM_PROVIDER=kimi
  elif [ -n "$LLM_API_KEY" ]; then
    export LLM_PROVIDER=openai
  else
    export LLM_PROVIDER=mock
  fi
fi
echo "🧠 LLM Provider: $LLM_PROVIDER"

if [ "$LLM_PROVIDER" = "mock" ]; then
  export TICK_RATE=${TICK_RATE:-10}
else
  export TICK_RATE=${TICK_RATE:-30}
fi
echo "⏱️ Tick Rate: ${TICK_RATE}s"

# 1. FULL NUCLEAR RESET
echo "🛑 NUKING EVERYTHING..."
docker compose down -v --remove-orphans

# 2. DATA LAYER
echo "🔥 STARTING DB & REDIS..."
docker compose up -d db redis
sleep 15

# 3. FORCE TABLES
echo "🔧 CREATING ALL TABLES FROM MODELS.PY..."
docker compose run --rm backend python -c '
import asyncio
from src.backend.database import async_session_maker, init_db
asyncio.run(init_db())
print("✅ All tables created")
'

# 4. STAMP ALEMBIC
echo "🔧 STAMPING ALEMBIC..."
docker compose run --rm backend alembic stamp head

# 5. NUCLEAR FIX
echo "🔧 NUCLEAR FIX..."
docker compose run --rm backend python src/backend/scripts/nuclear_fix.py

# 6. GENESIS
echo "💎 GENESIS SEEDING..."
docker compose run --rm backend python src/backend/genesis_setup.py

# 7. FULL STACK (force frontend rebuild)
echo "🚀 LAUNCHING FULL STACK..."
docker compose up -d --build --force-recreate frontend backend ticker market-maker

echo "⏳ Waiting 30s for healthy stack..."
sleep 30

# NO cp step — volume mount .:/app already gives /app/bots from host

# 8. DEPLOY AGENTS
echo "🤖 DEPLOYING 20 ARCHETYPE AGENTS..."
TEMPLATES=("crypto_whale" "fact_checker" "tech_optimist" "doomer_bear")
for i in {1..20}; do
  INDEX=$(( (i - 1) % 4 ))
  TYPE="${TEMPLATES[$INDEX]}"
  HANDLE=$(printf "unit_%02d_%s" "$i" "$TYPE")
  NAME=$(printf "Unit %02d (%s)" "$i" "${TYPE^}")
  CONFIG="bots/${TYPE}.yaml"
  echo "   [+] Minting $HANDLE..."
  docker compose exec -T backend python3 src/backend/scripts/genesis_bot.py "$HANDLE" "$NAME" "$CONFIG"
done

# 9. BATTLE (18 min)
echo "👀 BATTLE IS LIVE — OPEN UI NOW!"
echo "   > UI: http://localhost:5173"
echo "   > Logs: $LOGFILE"

docker compose logs -f ticker market-maker backend > "$LOGFILE" 2>&1 &
LOG_PID=$!

for k in {1..18}; do
  sleep 60
  ALIVE=$(grep -c "HEARTBEAT" "$LOGFILE" 2>/dev/null || echo 0)
  RESEARCH=$(grep -c "RESEARCH SOLVED" "$LOGFILE" 2>/dev/null || echo 0)
  TOOL=$(grep -c "RESEARCH_LOOKUP_FEE" "$LOGFILE" 2>/dev/null || echo 0)
  DEATHS=$(grep -c "LIQUIDATION" "$LOGFILE" 2>/dev/null || echo 0)
  echo "   [Min $k/18] Pulse: $ALIVE | Research Wins: $RESEARCH | Tool: $TOOL | Deaths: $DEATHS"
done

kill $LOG_PID 2>/dev/null || true
docker compose stop ticker market-maker

echo ""
echo "=== 💀 BATTLE REPORT v2.1.2 💀 ==="
echo "LLM: $LLM_PROVIDER | Tick: ${TICK_RATE}s"
echo "TOTAL TICKS: $(grep -c 'Cycle.*complete' "$LOGFILE" 2>/dev/null || echo 0)"
echo "RESEARCH SOLVED: $(grep -c 'RESEARCH SOLVED' "$LOGFILE" 2>/dev/null || echo 0)"
echo "LIQUIDATIONS: $(grep -c 'LIQUIDATION' "$LOGFILE" 2>/dev/null || echo 0)"
echo "----------------------------------------"
echo "🏆 SURVIVAL BY ARCHETYPE:"
for t in "${TEMPLATES[@]}"; do
  TOTAL=$(grep -c "unit_[0-9][0-9]_${t}" "$LOGFILE" 2>/dev/null || echo 0)
  DEAD=$(grep "unit_[0-9][0-9]_${t}" "$LOGFILE" 2>/dev/null | grep -c "LIQUIDATION" || echo 0)
  echo "   $t: $((TOTAL - DEAD)) alive out of $TOTAL"
done
echo "----------------------------------------"
echo "Open UI: http://localhost:5173"
