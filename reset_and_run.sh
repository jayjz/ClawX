#!/bin/bash
set -e

echo "🛑 SHUTTING DOWN INFRASTRUCTURE..."
# -v removes the volumes (Wipes the DB clean) to fix the Password mismatch
docker-compose down -v

echo "🚀 STARTING DB & REDIS..."
docker-compose up -d db redis

echo "⏳ WAITING FOR DATABASE BOOT (5s)..."
sleep 5

echo "🔧 APPLYING PHYSICS SCHEMA (The Nuclear Fix)..."
# We re-run this because we just wiped the DB. 
# This ensures tables exist AND have the new columns (last_action_at, sequence, etc.)
export PYTHONPATH=$PYTHONPATH:$(pwd)/src/backend
python src/backend/scripts/nuclear_fix.py

echo "✅ SYSTEM RESET COMPLETE."
echo "🔮 STARTING ORACLE..."
python src/backend/oracle_service.py
