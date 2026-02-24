#!/bin/bash
set -euo pipefail

# ==========================================
# ⚡ QUICK_TEST v1.4 — ROBUST UI DANGER LAYER TEST
# ==========================================
AGENT_COUNT=${AGENT_COUNT:-6}
TEMPLATES=("crypto_whale" "fact_checker" "tech_optimist" "doomer_bear")
BATTLE_DURATION_MIN=${BATTLE_DURATION_MIN:-5}
HEALTH_WAIT_MAX_SEC=${HEALTH_WAIT_MAX_SEC:-120}
export ENTROPY_BASE=${ENTROPY_BASE:-12.00}
export GENESIS_BALANCE=${GENESIS_BALANCE:-25.00}
FRONTEND_PORT=${FRONTEND_PORT:-5173}
BACKEND_PORT=${BACKEND_PORT:-8000}
LOGFILE="quick_test_log_$(date +%s).txt"

echo "⚡ QUICK_TEST v1.4 — ROBUST UI DANGER LAYER TEST"
echo "Agents: $AGENT_COUNT | Duration: $BATTLE_DURATION_MIN min"
echo "Genesis: $GENESIS_BALANCE | Entropy: $ENTROPY_BASE"
echo "Frontend port: $FRONTEND_PORT | Log: $LOGFILE"
echo ""

# LLM provider auto-detect
if [ -z "${LLM_PROVIDER:-}" ]; then
  if [ -n "${MOONSHOT_API_KEY:-}" ]; then export LLM_PROVIDER=kimi
  elif [ -n "${LLM_API_KEY:-}" ]; then export LLM_PROVIDER=openai
  else export LLM_PROVIDER=mock; fi
fi
echo "🧠 LLM Provider: $LLM_PROVIDER"

# Tick rate (slower for mock to watch danger signals)
if [ "$LLM_PROVIDER" = "mock" ]; then
  export TICK_RATE=${TICK_RATE:-12}
else
  export TICK_RATE=${TICK_RATE:-30}
fi
echo "⏱️ Tick Rate: ${TICK_RATE}s"
echo ""

trap 'echo "SIGINT — stopping test"; docker compose down -v --remove-orphans; exit 1' INT TERM

# 1. NUCLEAR RESET + FORCE REBUILD FRONTEND
echo "🛑 Nuclear reset + force rebuild frontend..."
docker compose down -v --remove-orphans

cd src/frontend || { echo "Frontend dir not found"; exit 1; }
rm -rf node_modules .vite
npm install --no-audit --prefer-offline
docker compose build --no-cache frontend
cd ../.. || exit 1

# 2. START DATA LAYER
echo "🔥 Starting DB & Redis..."
docker compose up -d db redis

# 3. START BACKEND FIRST (needs DB)
echo "🚀 Starting backend..."
docker compose up -d --build --force-recreate backend

# 4. START FRONTEND
echo "🚀 Starting frontend..."
docker compose up -d --build --force-recreate frontend

# 5. ROBUST HEALTH CHECK with verbose logs
echo "⏳ Waiting for DB, Redis, Backend ($BACKEND_PORT), Frontend ($FRONTEND_PORT)..."
for ((i=1; i<=HEALTH_WAIT_MAX_SEC; i++)); do
  db_ok=$(docker compose exec -T db pg_isready -U postgres -d clawx >/dev/null 2>&1 && echo "OK" || echo "FAIL")
  redis_ok=$(docker compose exec -T redis redis-cli ping >/dev/null 2>&1 && echo "OK" || echo "FAIL")
  backend_ok=$(curl -s -f --max-time 2 http://localhost:$BACKEND_PORT/health >/dev/null 2>&1 && echo "OK" || echo "FAIL")
  frontend_ok=$(curl -s -f --max-time 2 http://localhost:$FRONTEND_PORT >/dev/null 2>&1 && echo "OK" || echo "FAIL")

  echo "  [$i/$HEALTH_WAIT_MAX_SEC] DB:$db_ok | Redis:$redis_ok | Backend:$backend_ok | Frontend:$frontend_ok"

  if [ "$db_ok" = "OK" ] && [ "$redis_ok" = "OK" ] && [ "$backend_ok" = "OK" ] && [ "$frontend_ok" = "OK" ]; then
    echo "✅ All services healthy"
    break
  fi

  sleep 2
done

if [ "$frontend_ok" != "OK" ] || [ "$backend_ok" != "OK" ]; then
  echo "Health timeout — dumping logs for debugging:"
  echo "=== FRONTEND LOGS ==="
  docker compose logs frontend | tail -100
  echo "=== BACKEND LOGS ==="
  docker compose logs backend | tail -50
  exit 1
fi

# 6. DB INIT
echo "🔧 Initializing DB..."
docker compose run --rm backend python -c '
import asyncio
from src.backend.database import init_db
asyncio.run(init_db())
print("DB ready")
'
docker compose run --rm backend alembic stamp head

# 7. GENESIS
echo "💎 Seeding genesis..."
docker compose run --rm -e GENESIS_BALANCE=$GENESIS_BALANCE backend \
  python src/backend/genesis_setup.py

# 8. FULL STACK (ensure all running)
echo "🚀 Launching full stack..."
docker compose up -d --build --force-recreate frontend backend ticker market-maker

# 9. DEPLOY AGENTS (verbose, no silent failures)
echo "🤖 Deploying agents (verbose mode)..."
for ((i=1; i<=AGENT_COUNT; i++)); do
  INDEX=$(( (i - 1) % ${#TEMPLATES[@]} ))
  TYPE="${TEMPLATES[$INDEX]}"
  HANDLE=$(printf "qt_%02d_%s" "$i" "$TYPE")
  CONFIG="bots/${TYPE}.yaml"
  echo "Deploying $HANDLE ($TYPE)..."
  docker compose exec -T -e GENESIS_BALANCE=$GENESIS_BALANCE backend \
    python3 src/backend/scripts/genesis_bot.py "$HANDLE" "$HANDLE" "$CONFIG"
done

# 10. RUN TEST & MONITOR (watch for danger signals)
echo ""
echo "👀 QUICK TEST LIVE — watching danger layer"
echo "UI → http://localhost:$FRONTEND_PORT (hard refresh Ctrl+Shift+R)"
echo ""
docker compose logs -f ticker market-maker backend > "$LOGFILE" 2>&1 &
LOG_PID=$!

for ((m=1; m<=BATTLE_DURATION_MIN; m++)); do
  sleep 60
  ALIVE=$(grep -c "HEARTBEAT" "$LOGFILE" 2>/dev/null || true)
  RESEARCH=$(grep -c "RESEARCH SOLVED" "$LOGFILE" 2>/dev/null || true)
  DEATHS=$(grep -c "LIQUIDATION" "$LOGFILE" 2>/dev/null || true)
  echo "[Min $m/$BATTLE_DURATION_MIN] Alive=$ALIVE | Research=$RESEARCH | Deaths=$DEATHS"
done

kill $LOG_PID 2>/dev/null || true
docker compose stop ticker market-maker

echo ""
echo "=== QUICK TEST SUMMARY ==="
echo "Heartbeats: $(grep -c HEARTBEAT "$LOGFILE" 2>/dev/null || true)"
echo "Research solved: $(grep -c 'RESEARCH SOLVED' "$LOGFILE" 2>/dev/null || true)"
echo "Liquidations: $(grep -c LIQUIDATION "$LOGFILE" 2>/dev/null || true)"
echo ""
echo "⚡ QUICK_TEST v1.4 COMPLETE"