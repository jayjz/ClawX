#!/bin/bash
set -e

echo "☢️  CLAWX BATTLE ROYALE v1.9.4 — Fixed Migration Order (Production Safe)"
echo "Start time: $(date)"
LOGFILE="battle_log_$(date +%s).txt"
echo "Log file: $LOGFILE"

# 1. FULL NUCLEAR RESET
echo "🛑 NUKING EVERYTHING..."
docker compose down -v --remove-orphans

# 2. DATA LAYER ONLY
echo "🔥 STARTING DB & REDIS..."
docker compose up -d db redis
sleep 15

# 3. FORCE CLEAN TABLE CREATION FROM MODELS.PY (Single Source of Truth)
echo "🔧 CREATING ALL TABLES FROM MODELS.PY..."
docker compose run --rm backend python -c '
import asyncio
from src.backend.database import async_session_maker, init_db
asyncio.run(init_db())
print("✅ All tables created from models.py (Base.metadata.create_all)")
'

# 4. STAMP ALEMBIC TO HEAD (so future migrations work)
echo "🔧 STAMPING ALEMBIC TO HEAD..."
docker compose run --rm backend alembic stamp head

# 5. NUCLEAR FIX (now safe — tables exist)
echo "🔧 RUNNING NUCLEAR FIX..."
docker compose run --rm backend python src/backend/scripts/nuclear_fix.py

# 6. GENESIS SEEDING
echo "💎 SEEDING GENESIS LEDGER..."
docker compose run --rm backend python src/backend/genesis_setup.py

# 7. FULL STACK
echo "🚀 LAUNCHING FULL STACK..."
docker compose up -d --build

echo "⏳ Waiting 25s for backend to become healthy..."
sleep 25

# 8. COPY REAL PERSONA TEMPLATES
echo "📋 COPYING SPECIALIZED PERSONAS..."
docker compose cp bots/ backend:/app/bots/

# 9. MANUFACTURE 20 SPECIALIZED AGENTS
echo "🤖 DEPLOYING 20 ARCHETYPE AGENTS..."
TEMPLATES=("crypto_whale" "fact_checker" "tech_optimist" "doomer_bear")

for i in {1..20}; do
  INDEX=$(( (i - 1) % 4 ))
  TYPE="${TEMPLATES[$INDEX]}"
  HANDLE=$(printf "unit_%02d_%s" "$i" "$TYPE")
  NAME=$(printf "Unit %02d (%s)" "$i" "${TYPE^}")
  CONFIG="bots/${TYPE}.yaml"

  echo "   [+] Minting $HANDLE ($NAME)..."
  docker compose exec -T backend python3 src/backend/scripts/genesis_bot.py "$HANDLE" "$NAME" "$CONFIG"
done

# 10. BATTLE (12 minutes)
echo "👀 BATTLE IS LIVE — OPEN UI NOW!"
echo "   > UI: http://localhost:5173"
echo "   > Logs streaming to $LOGFILE"

docker compose logs -f ticker market-maker backend > "$LOGFILE" 2>&1 &
LOG_PID=$!

for k in {1..12}; do
  sleep 60
  ALIVE=$(grep -c "HEARTBEAT" "$LOGFILE" || echo 0)
  RESEARCH=$(grep -c "RESEARCH_PAYOUT" "$LOGFILE" || echo 0)
  TOOL=$(grep -c "RESEARCH_LOOKUP_FEE" "$LOGFILE" || echo 0)
  DEATHS=$(grep -c "LIQUIDATION" "$LOGFILE" || echo 0)
  echo "   [Min $k/12] Pulse: $ALIVE | Research Wins: $RESEARCH | Tool Calls: $TOOL | Deaths: $DEATHS"
done

kill $LOG_PID 2>/dev/null || true
docker compose stop ticker market-maker

echo ""
echo "=== 💀 SPECIALIZED BATTLE REPORT 💀 ==="
echo "----------------------------------------"
echo "TOTAL TICKS:          $(grep -c "TICK" "$LOGFILE" || echo 0)"
echo "RESEARCH WINS:        $(grep -c "RESEARCH_PAYOUT" "$LOGFILE" || echo 0)"
echo "TOOL USAGE:           $(grep -c "RESEARCH_LOOKUP_FEE" "$LOGFILE" || echo 0)"
echo "LIQUIDATIONS:         $(grep -c "LIQUIDATION" "$LOGFILE" || echo 0)"
echo "----------------------------------------"

echo "🏆 SURVIVAL BY ARCHETYPE:"
for t in "${TEMPLATES[@]}"; do
  COUNT=$(grep -c "unit_.._${t}" "$LOGFILE" || echo 0)
  DEATHS=$(grep -c "unit_.._${t}.*LIQUIDATION" "$LOGFILE" || echo 0)
  echo "   $t: $((COUNT - DEATHS)) alive out of $COUNT"
done

echo "----------------------------------------"
echo "Full log: $LOGFILE"
echo "View last 100 lines: tail -100 $LOGFILE"
echo "Open UI: http://localhost:5173"
