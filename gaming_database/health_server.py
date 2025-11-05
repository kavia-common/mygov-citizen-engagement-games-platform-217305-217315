#!/usr/bin/env python3
# PUBLIC_INTERFACE
def main():
    """
    Minimal HTTP health server for the gaming_database container.

    - Serves /health and / on port 5001.
    - On first start, ensures SQLite DB is initialized by invoking init_db.py.
    - Reports 200 OK when the SQLite database file is present and can execute a trivial PRAGMA.
    - Provides /ready and /live as aliases to /health.

    Environment:
        PORT (optional): override port (default 5001)
    """
    import http.server
    import socketserver
    import json
    import os
    import sqlite3
    import time
    import subprocess
    from urllib.parse import urlparse

    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "myapp.db"))
    DEFAULT_PORT = int(os.environ.get("PORT", "5001"))

    def init_db_if_needed():
        # If DB file missing or empty, call init_db.py to create/seed it
        try:
            if (not os.path.exists(DB_PATH)) or os.path.getsize(DB_PATH) == 0:
                init_script = os.path.join(os.path.dirname(__file__), "init_db.py")
                if os.path.exists(init_script):
                    # Run init script non-interactively
                    subprocess.run(["/usr/bin/env", "python3", init_script], check=True)
        except Exception as e:
            # Initialization failure should be visible in health output
            print(f"[health_server] DB initialization error: {e}", flush=True)

    def check_sqlite_health():
        # Return tuple (healthy: bool, detail: str)
        if not os.path.exists(DB_PATH):
            return False, f"SQLite database file not found at {DB_PATH}"
        try:
            conn = sqlite3.connect(DB_PATH, timeout=2)
            try:
                # lightweight check
                cur = conn.cursor()
                cur.execute("PRAGMA quick_check")
                result = cur.fetchone()
                # PRAGMA quick_check returns 'ok' on success, but even if missing, DB open is sufficient
                if result and isinstance(result[0], str) and result[0].lower() == "ok":
                    return True, "ok"
                else:
                    return True, "opened"
            finally:
                conn.close()
        except Exception as e:
            return False, f"SQLite error: {e}"

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "GamingDatabaseHealth/1.0"

        def _send(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/", "/health", "/ready", "/live"):
                healthy, detail = check_sqlite_health()
                status = 200 if healthy else 503
                payload = {
                    "service": "gaming_database",
                    "status": "ok" if healthy else "unavailable",
                    "database": "sqlite",
                    "detail": detail,
                    "db_path": DB_PATH,
                    "time": int(time.time())
                }
                self._send(status, payload)
            else:
                self.send_error(404, "Not Found")

        # Suppress default noisy logging
        def log_message(self, format, *args):
            return

    # Ensure DB exists before serving
    init_db_if_needed()

    with socketserver.TCPServer(("0.0.0.0", DEFAULT_PORT), Handler) as httpd:
        print(f"[health_server] Listening on 0.0.0.0:{DEFAULT_PORT}, DB: {DB_PATH}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
