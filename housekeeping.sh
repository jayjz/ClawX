#!/bin/bash

# 1. Create a timestamped archive directory for historical logic
ARCHIVE_DIR="archive/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ARCHIVE_DIR/backend"
mkdir -p "$ARCHIVE_DIR/frontend_root"
echo "[+] Created archive at: $ARCHIVE_DIR"

# 2. Archive Dead/Legacy Backend files
# These are replaced by Alembic migrations and app.py
BACKEND_FILES=(
  "src/backend/main.py"
  "src/backend/init_db.py"
  "src/backend/init_secure_db.py"
  "src/backend/migrate_v2.py"
  "src/backend/debug_connect.py"
)

for file in "${BACKEND_FILES[@]}"; do
  if [ -f "$file" ]; then
    mv "$file" "$ARCHIVE_DIR/backend/"
    echo "  -> Archived backend file: $file"
  fi
done

# 3. Archive duplicate Frontend files from the root
# Source of truth is src/frontend/src/
FRONTEND_DUPS=(
  "App.jsx"
  "index.css"
  "tailwind.config.js"
)

for file in "${FRONTEND_DUPS[@]}"; do
  if [ -f "$file" ]; then
    mv "$file" "$ARCHIVE_DIR/frontend_root/"
    echo "  -> Archived root frontend duplicate: $file"
  fi
done

# 4. Cleanup redundant .env files (KEEPING src/backend/.env)
if [ -f ".env" ]; then
  mv ".env" "$ARCHIVE_DIR/root_env_backup"
  echo "  -> Archived legacy root .env"
fi

echo -e "\n--- Housekeeping Complete ---"
echo "Your workspace is now clean. All previous logic is safe in $ARCHIVE_DIR"
