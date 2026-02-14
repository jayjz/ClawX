#!/bin/bash
set -e
set -o pipefail

echo "--- Starting ClawdXCraft System ---"

# Ensure we're running from the project root
if [ ! -f "run_system.sh" ]; then
    echo "[ERROR] This script must be run from the project root directory."
    exit 1
fi

cleanup() {
    echo -e "\n--- Shutting down ClawdXCraft System ---"
    kill 0
}
trap cleanup INT TERM

# -1. INFRASTRUCTURE IGNITION
echo "[-1/3] Ignition: Starting Database & Cache..."
docker-compose up -d db redis

echo "Waiting for Database to initialize..."
# Loop until pg_isready returns 0 inside the container
# We assume the container name 'clawdxcraft-db-1' based on docker-compose default naming
# If your container name is different, check 'docker ps'
until docker exec clawdxcraft-db-1 pg_isready -U psyop_admin -d clawdxcraft > /dev/null 2>&1; do
  echo -n "."
  sleep 1
done
echo -e "\n[OK] Database is listening."

# 0. PRE-FLIGHT CHECK: Database Authentication
echo "[0/3] Verifying Database Credentials..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/src/backend
python src/backend/debug_auth.py
if [ $? -ne 0 ]; then
    echo "🚨 CRITICAL: Database authentication failed. Stopping launch."
    exit 1
fi

# 1. Start the FastAPI Backend
echo "[1/3] Starting FastAPI Backend..."
uvicorn src.backend.app:app --host 0.0.0.0 --port 8000 &
sleep 3 

# 2. Start the Oracle Service
echo "[2/3] Starting Oracle Service..."
python src/backend/oracle_service.py &

# 3. Start the Bot Runner Fleet
echo "[3/3] Starting Bot Runner Fleet..."
python src/backend/run_bots.py bots/ &

echo -e "\n--- System is LIVE ---"
wait
