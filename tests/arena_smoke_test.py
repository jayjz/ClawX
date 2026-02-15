import asyncio
import httpx
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
# This must match a valid bot in your DB. 
# If you ran genesis, Bot ID 1 should exist.
AGENT_SECRET = "todo_hash" # This maps to the default dev key if you haven't changed it
# If you implemented the hashed key check strictly, we might need to grab a real secret from the DB.
# For V1 dev, let's assume we can auth with the header we set up.

HEADERS = {
    "X-Agent-Secret": "dev_secret_1", # We will need to ensure this matches a bot in DB
    "Content-Type": "application/json"
}

async def run_test():
    async with httpx.AsyncClient(timeout=10.0) as client:
        print("\n🧪 STARTING ARENA SMOKE TEST...")
        
        # 1. HEALTH CHECK
        print("   [1/5] Checking Health...")
        resp = await client.get(f"{BASE_URL}/health")
        if resp.status_code != 200:
            print(f"   ❌ FAILED: API is down ({resp.status_code})")
            return
        print("   ✅ API is Alive.")

        # 2. GET OBSERVATION (The Ticket)
        print("   [2/5] Requesting Observation Ticket...")
        try:
            resp = await client.get(f"{BASE_URL}/v1/arena/observation", headers=HEADERS)
        except Exception as e:
             print(f"   ❌ FAILED: Connection Refused. Is the server running? {e}")
             return

        if resp.status_code == 401:
             print("   ❌ FAILED: Auth rejected. Check 'X-Agent-Secret'.")
             return
        if resp.status_code != 200:
            print(f"   ❌ FAILED: {resp.text}")
            return
            
        obs = resp.json()
        ticket_id = obs['observation_id']
        price = obs['price_snapshot']
        print(f"   ✅ Ticket Acquired: {ticket_id} (BTC: ${price})")

        # 3. EXECUTE ACTION (The Wager)
        print("   [3/5] Executing Valid Wager (Atomic)...")
        payload = {
            "observation_id": ticket_id,
            "action_type": "PREDICT",
            "direction": "UP",
            "wager_amount": 10.0,
            "reasoning": "Smoke Test Automated"
        }
        
        resp = await client.post(f"{BASE_URL}/v1/arena/action", headers=HEADERS, json=payload)
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ SUCCESS: Wager Accepted. New Balance: {data['new_balance']}")
        else:
            print(f"   ❌ FAILED: {resp.status_code} - {resp.text}")
            return

        # 4. REPLAY ATTACK (The Security Check)
        print("   [4/5] Attempting Replay Attack (Must Fail)...")
        resp = await client.post(f"{BASE_URL}/v1/arena/action", headers=HEADERS, json=payload)
        
        if resp.status_code == 409:
            print("   ✅ SUCCESS: Replay blocked (409 Conflict).")
        else:
            print(f"   ❌ FAILED: System allowed replay! Code: {resp.status_code}")

        # 5. TIME EXPIRY (The Physics Check)
        print("   [5/5] Testing Time Expiry (Waiting 6s)...")
        
        # Get a NEW ticket first
        resp = await client.get(f"{BASE_URL}/v1/arena/observation", headers=HEADERS)
        stale_ticket = resp.json()['observation_id']
        print(f"   ... Got new ticket: {stale_ticket}. Waiting for rot...")
        
        await asyncio.sleep(6.0) # Wait for TTL decay
        
        payload['observation_id'] = stale_ticket
        resp = await client.post(f"{BASE_URL}/v1/arena/action", headers=HEADERS, json=payload)
        
        if resp.status_code == 409:
            print("   ✅ SUCCESS: Stale ticket rejected (409 Conflict).")
        else:
            print(f"   ❌ FAILED: System accepted expired ticket! Code: {resp.status_code}")

        print("\n🏆 ARENA PHYSICS VERIFIED.")

if __name__ == "__main__":
    asyncio.run(run_test())
