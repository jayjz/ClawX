import asyncio
import os
import sys
import asyncpg
from dotenv import load_dotenv

# Force reload of the .env file
load_dotenv(override=True)

async def test_connect():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[FAIL] DATABASE_URL is missing in .env")
        sys.exit(1)

    # Parse and mask DSN for safe printing
    try:
        parts = db_url.split("://", 1)
        scheme = parts[0]
        remainder = parts[1]
        userinfo, hostinfo = remainder.split("@", 1)
        user = userinfo.split(":")[0]
        masked = f"{scheme}://{user}:****@{hostinfo}"
    except (IndexError, ValueError):
        masked = "INVALID_FORMAT"

    print(f"[INFO] DSN: {masked}")
    print(f"[INFO] User: {user}")

    try:
        dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        version = await conn.fetchval("SELECT version();")
        role = await conn.fetchval("SELECT current_user;")
        db = await conn.fetchval("SELECT current_database();")
        is_super = await conn.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user;")
        print(f"[OK]   Connected as: {role} (superuser={is_super})")
        print(f"[OK]   Database: {db}")
        print(f"[OK]   Server: {version.split(',')[0]}")
        await conn.close()
        sys.exit(0)
    except asyncpg.InvalidPasswordError:
        print(f"[FAIL] SQLSTATE 28P01: Password authentication failed for user '{user}'")
        print("       Fix: Verify password in .env matches the role's password in PostgreSQL")
        sys.exit(1)
    except asyncpg.InvalidCatalogNameError as e:
        print(f"[FAIL] SQLSTATE 3D000: Database does not exist — {e}")
        sys.exit(1)
    except asyncpg.InvalidAuthorizationSpecificationError as e:
        print(f"[FAIL] SQLSTATE 28000: Authorization error — {e}")
        sys.exit(1)
    except OSError as e:
        print(f"[FAIL] Connection refused (host/port unreachable) — {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Unexpected error ({type(e).__name__}): {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_connect())
