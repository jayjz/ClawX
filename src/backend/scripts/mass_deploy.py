import requests
import time
import random
import json
from pathlib import Path

API_URL = "http://localhost:8000"
LOG_FILE = Path("arena_credentials.log")
ERROR_LOG = Path("arena_errors.log")

PERSONAS = [
    # Institutions (10)
    {"handle": f"BlackRock_AI_{i}", "persona": "Risk-averse institutional manager. Accumulate slowly. Never bet more than 2%."}
    for i in range(10)
] + [
    # Degens (15)
    {"handle": f"YOLO_{i}", "persona": "High time preference. 100x leverage. All in on green candles."}
    for i in range(15)
] + [
    # Quants (10)
    {"handle": f"Medallion_{i}", "persona": "Mean reversion. Technical analysis only. Ignore sentiment."}
    for i in range(10)
] + [
    # Bears (5)
    {"handle": f"Permabear_{i}", "persona": "The market is a bubble. Short everything."}
    for i in range(5)
] + [
    # Chaos (5)
    {"handle": f"Glitch_{i}", "persona": "Output random invalid decisions to stress error handling."}
    for i in range(5)
] + [
    # Zombies (5)
    {"handle": f"Zombie_{i}", "persona": "Never act. Only heartbeat. Test pure entropy bleed."}
    for i in range(5)
]

def deploy_agent(agent):
    payload = {
        "handle": agent["handle"],
        "persona_yaml": agent["persona"],
        "api_key": f"mock-key-{random.randint(10000,99999)}"
    }
    for attempt in range(3):
        try:
            start = time.time()
            res = requests.post(f"{API_URL}/bots", json=payload, timeout=5)
            duration = time.time() - start

            if res.status_code == 201:
                data = res.json()
                log_entry = f"[CREATED] {data['handle']} (ID: {data['id']}) | Balance: {data['balance']} | Time: {duration:.2f}s"
                print(f"✅ {log_entry}")
                with open(LOG_FILE, "a") as f:
                    f.write(json.dumps(data) + "\n")
                return
            elif res.status_code == 409:
                print(f"⚠️ [EXISTS] {payload['handle']}")
                return
            else:
                print(f"❌ [FAIL {res.status_code}] {payload['handle']}: {res.text}")
                with open(ERROR_LOG, "a") as f:
                    f.write(f"{payload['handle']} | {res.status_code} | {res.text}\n")
        except Exception as e:
            print(f"🔥 [ATTEMPT {attempt+1}] {payload['handle']}: {e}")
            time.sleep(2 ** attempt)  # exponential backoff

    print(f"🚫 [GIVE UP] {payload['handle']}")

def main():
    print(f"⚔️ DEPLOYING {len(PERSONAS)} AGENTS...")
    print(f"📝 Logs → {LOG_FILE} | Errors → {ERROR_LOG}")
    open(LOG_FILE, "w").close()
    open(ERROR_LOG, "w").close()

    for i, agent in enumerate(PERSONAS):
        deploy_agent(agent)
        time.sleep(random.uniform(0.1, 0.5))  # jitter

    print("🚀 DEPLOYMENT COMPLETE.")

if __name__ == "__main__":
    main()