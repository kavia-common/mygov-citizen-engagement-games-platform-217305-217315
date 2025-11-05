# gaming_database (SQLite)

This container hosts a SQLite database used by the platform and exposes a minimal HTTP health server on port 5001 so the preview system can detect readiness.

## How it works

- SQLite database file: myapp.db (created/seeded by init_db.py)
- Health server: health_server.py listens on 0.0.0.0:5001 and exposes:
  - GET /health (also /ready and /live)
  - Returns 200 when SQLite is available and readable; 503 otherwise.

On start, the health server will initialize the database by invoking init_db.py if myapp.db is missing.

## Run

- Start database initialization once (optional):
  - python3 init_db.py

- Start health server (required for preview readiness):
  - PORT=5001 python3 health_server.py

The preview expects port 5001 to be ready. Ensure this process is started by your container entrypoint or task runner.

## Endpoints

- GET /health
- GET /ready
- GET /live

All return JSON with status and database details.
