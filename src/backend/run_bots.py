import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv
import httpx

from bot_loader import load_bot_config
from bot_runner import run_bot_loop

# Resolve paths relative to THIS script, not CWD
_SCRIPT_DIR = Path(__file__).resolve().parent
_ENV_PATH = _SCRIPT_DIR / ".env"
_ENV_BOTS_PATH = _SCRIPT_DIR / ".env.bots"

# Load local environment using absolute paths
load_dotenv(_ENV_PATH, override=True)

assert _ENV_BOTS_PATH.exists(), f".env.bots not found at {_ENV_BOTS_PATH}"
load_dotenv(_ENV_BOTS_PATH, override=True)

BASE_URL = os.environ.get("CLAWDXCRAFT_BASE_URL", "http://localhost:8000")
logger = logging.getLogger("run_bots")


def _get_bot_key(handle: str) -> str | None:
    """Lookup key for 'ApexWhale' as 'APEXWHALE_KEY'.

    Also tries with underscores stripped for handles like 'philobot_01' -> 'PHILOBOT01_KEY'
    as a fallback, but primary lookup matches the .env.bots convention exactly.
    """
    key = os.getenv(f"{handle.upper()}_KEY")
    if key:
        return key
    # Fallback: strip underscores from handle (e.g., PHILOBOT_01 -> PHILOBOT01)
    stripped = handle.replace("_", "").upper()
    return os.getenv(f"{stripped}_KEY")

async def _ensure_bot_registered(client, handle, persona, key):
    resp = await client.post(f"{BASE_URL}/bots", json={
        "handle": handle, "persona_yaml": persona, "api_key": key
    })
    if resp.status_code in (201, 409):
        logger.info("[ok] Bot '%s' is ready.", handle)
    else:
        logger.error("[!] Failed to sync '%s': %s", handle, resp.text)

async def main(bots_dir: str):
    loaded_keys = [k for k in os.environ if k.endswith("_KEY")]
    logger.info("[boot] .env.bots: %s", _ENV_BOTS_PATH)
    logger.info("[boot] Loaded keys: %s", loaded_keys)

    bots_path = Path(bots_dir)
    yaml_files = sorted(bots_path.glob("*.yaml"))
    valid_configs = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for yf in yaml_files:
            try:
                config = load_bot_config(str(yf))
                handle = config["name"]
                key = _get_bot_key(handle)
                
                if not key:
                    logger.warning("[!] Skipping '%s': No key in .env.bots", handle)
                    continue

                await _ensure_bot_registered(client, handle, config["persona"], key)
                valid_configs.append({"path": str(yf), "key": key, "handle": handle})
            except Exception as e:
                logger.error("[!] Config Error in %s: %s", yf.name, e)

    if not valid_configs:
        logger.error("No valid bots found. Shutdown.")
        return

    logger.info("🚀 Launching fleet: %s", [c['handle'] for c in valid_configs])
    tasks = [asyncio.create_task(run_bot_loop(c["path"], c["key"])) for c in valid_configs]

    def _shutdown(sig):
        for t in tasks: t.cancel()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, _shutdown, sig)

    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "bots/"))
