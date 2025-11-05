#!/usr/bin/env bash
set -euo pipefail

# Start SQLite health server on port 5001
export PORT="${PORT:-5001}"

# Initialize DB if needed (health_server also initializes but this makes logs explicit)
if [ ! -f "myapp.db" ] || [ ! -s "myapp.db" ]; then
  echo "[start] Initializing SQLite database..."
  /usr/bin/env python3 init_db.py || true
fi

echo "[start] Starting health server on 0.0.0.0:${PORT}"
exec /usr/bin/env python3 health_server.py
