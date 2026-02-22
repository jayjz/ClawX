#!/bin/bash
set -euo pipefail

# ==========================================
# ☢️ STAY_ALIVE v1.0 — THE IMMORTALITY TEST
# ==========================================
AGENT_COUNT=${AGENT_COUNT:-10}          # one of each survivor
BATTLE_DURATION_MIN=${BATTLE_DURATION_MIN:-60}
export ENTROPY_BASE=${ENTROPY_BASE:-15.00}
export GENESIS_BALANCE=${GENESIS_BALANCE:-30.00}  # harder survival test
LOGFILE="stay_alive_log_$(date +%s).txt"

echo "☢️ STAY_ALIVE v1.0 — IMMORTALITY PROTOCOL"
echo "Agents: $AGENT_COUNT hyper-optimized survivors"
echo "Genesis: $GENESIS_BALANCE | Entropy: $ENTROPY_BASE | Duration: $BATTLE_DURATION_MIN min"
echo "Goal: Who lives the longest?"

# ... (reuse the same nuclear reset, db start, genesis, stack launch as your stress_test.sh)

# Deploy only the 10 survivors
echo "🛡️ DEPLOYING 10 IMMORTAL ARCHETYPES..."
for bot in research_reaper entropy_hoarder portfolio_ghost wiki_warlock iron_turtle \
           compound_scientist zero_idle bounty_hunter risk_calculator immortal_archivist; do
  echo " [+] Minting $bot..."
  docker compose exec -T -e GENESIS_BALANCE=$GENESIS_BALANCE backend \
    python3 src/backend/scripts/genesis_bot.py "$bot" "$bot" "bots/survivors/${bot}.yaml" || true
done

# Run the battle with extra survival metrics
docker compose logs -f ticker market-maker backend > "$LOGFILE" 2>&1 &
# ... (same monitoring loop as stress_test.sh but with "LONGEST SURVIVOR" tracking)

echo "STAY_ALIVE TEST COMPLETE — check $LOGFILE for the new longevity champions."
