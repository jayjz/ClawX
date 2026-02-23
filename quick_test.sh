#!/bin/bash
set -euo pipefail

# ==========================================
# ⚡ QUICK_TEST v1.0 — 5 MINUTE SANITY CHECK
# ==========================================
AGENT_COUNT=${AGENT_COUNT:-6}
TEMPLATES=("crypto_whale" "fact_checker" "tech_optimist" "doomer_bear")
BATTLE_DURATION_MIN=${BATTLE_DURATION_MIN:-5}
HEALTH_WAIT_MAX_SEC=${HEALTH_WAIT_MAX_SEC:-45}

export ENTROPY_BASE=${ENTROPY_BASE:-12.00}
export GENESIS_BALANCE=${GENESIS_BALANCE:-25.00}

LOGFILE="quick_test_log_$(date +%s).txt"

echo "⚡ QUICK_TEST v1.0 — FAST ARENA VALIDATION"
echo "Agents: $AGENT_COUNT | Duration: $BATTLE_DURATION_MIN min"
echo "Genesis: $GENESIS_BALANCE | Entropy: $ENTROPY_BASE"
echo "Log: $LOGFILE"
echo ""

# LLM provider auto-detect
if [ -z "${LLM_PROVIDER:-}" ]; then
  if [ -n "${MOONSHOT_API_KEY:-}" ]; then export LLM_PROVIDER=kimi
  elif [ -n "${LLM_API_KEY:-}" ]; then export LLM_PROVIDER=openai
  else export LLM_PROVIDER=mock; fi
fi
echo "🧠 LLM Provider: $LLM_PROVIDER"

# Tick rate
if [ "$LLM_PROVIDER" = "mock" ]; then
  export TICK_RATE=${TICK_RATE:-8}
else
  export TICK_RATE=${TICK_RATE:-20}
fi
echo "⏱️ Tick Rate: ${TICK_RATE}s"
echo ""

trap 'echo "SIGINT — stopping test"; docker compose down -v --remove-orphans; exit 1' INT TERM

# 1. HARD RESET
echo "🛑 Resetting stack..."
docker compose down -v --remove-orphans

# 2. DATA LAYER
echo "🔥 Starting DB & Redis..."
docker compose up -d db redis

# 3. HEALTH CHECK
echo "⏳ Waiting for DB & Redis..."
until docker compose exec -T db pg_isready -U postgres -d clawx >/dev/null 2>&1 && \
      docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do
  sleep 2
  ((HEALTH_WAIT_MAX_SEC--)) || { echo "Health timeout"; exit 1; }
done
echo "✅ DB & Redis ready"

# 4. DB INIT
echo "🔧 Initializing DB..."
docker compose run --rm backend python -c '
import asyncio
from src.backend.database import init_db
asyncio.run(init_db())
print("DB ready")
'
docker compose run --rm backend alembic stamp head

# 5. GENESIS
echo "💎 Seeding genesis..."
docker compose run --rm -e GENESIS_BALANCE=$GENESIS_BALANCE backend \
  python src/backend/genesis_setup.py

# 6. STACK
echo "🚀 Launching services..."
docker compose up -d --build --force-recreate frontend backend ticker market-maker

# 7. BACKEND HEALTH
echo "⏳ Waiting for backend..."
until curl -s -f http://localhost:8000/health >/dev/null 2>&1; do
  sleep 2
  ((HEALTH_WAIT_MAX_SEC--)) || { echo "Backend timeout"; exit 1; }
done
echo "✅ Backend healthy"

# 8. DEPLOY AGENTS
echo "🤖 Deploying agents..."
for ((i=1; i<=AGENT_COUNT; i++)); do
  INDEX=$(( (i - 1) % ${#TEMPLATES[@]} ))
  TYPE="${TEMPLATES[$INDEX]}"
  HANDLE=$(printf "qt_%02d_%s" "$i" "$TYPE")
  CONFIG="bots/${TYPE}.yaml"
  docker compose exec -T -e GENESIS_BALANCE=$GENESIS_BALANCE backend \
    python3 src/backend/scripts/genesis_bot.py "$HANDLE" "$HANDLE" "$CONFIG" || true
done

# 9. RUN TEST
echo ""
echo "👀 QUICK TEST LIVE"
echo "UI → http://localhost:5173"
echo ""

docker compose logs -f ticker market-maker backend > "$LOGFILE" 2>&1 &
LOG_PID=$!

for ((m=1; m<=BATTLE_DURATION_MIN; m++)); do
  sleep 60
  ALIVE=$(grep -c "HEARTBEAT" "$LOGFILE" 2>/dev/null || true)
  RESEARCH=$(grep -c "RESEARCH SOLVED" "$LOGFILE" 2>/dev/null || true)
  DEATHS=$(grep -c "LIQUIDATION" "$LOGFILE" 2>/dev/null || true)

  echo "[Min $m/$BATTLE_DURATION_MIN] Pulse=$ALIVE | Research=$RESEARCH | Deaths=$DEATHS"
done

kill $LOG_PID 2>/dev/null || true
docker compose stop ticker market-maker

echo ""
echo "=== QUICK TEST SUMMARY ==="
echo "Heartbeats: $(grep -c HEARTBEAT "$LOGFILE" 2>/dev/null || true)"
echo "Research solved: $(grep -c 'RESEARCH SOLVED' "$LOGFILE" 2>/dev/null || true)"
echo "Liquidations: $(grep -c LIQUIDATION "$LOGFILE" 2>/dev/null || true)"
echo ""
echo "⚡ QUICK_TEST COMPLETE"
