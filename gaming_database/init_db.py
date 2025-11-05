#!/usr/bin/env python3
"""Initialize and seed SQLite database for gaming_database.

This script:
- Creates/updates tables: users, games, game_scores, analytics_events, app_info
- Enforces foreign keys (PRAGMA foreign_keys=ON)
- Adds indices (including composite index on game_scores (game_id, user_id, score DESC))
- Inserts seed data idempotently (only if not present)
- Writes db_connection.txt with absolute file path and connection string
- Writes db_visualizer/sqlite.env for the Node viewer
It is safe to re-run multiple times.
"""

import sqlite3
import os
from contextlib import closing

DB_NAME = "myapp.db"
DB_USER = "kaviasqlite"  # Not used for SQLite, retained for parity
DB_PASSWORD = "kaviadefaultpassword"  # Not used for SQLite
DB_PORT = "5000"  # Not used for SQLite

print("Starting SQLite setup...")

# Check if database already exists
db_exists = os.path.exists(DB_NAME)
if db_exists:
    print(f"SQLite database already exists at {DB_NAME}")
    try:
        with closing(sqlite3.connect(DB_NAME)) as conn:
            conn.execute("SELECT 1")
        print("Database is accessible and working.")
    except Exception as e:
        print(f"Warning: Database exists but may be corrupted: {e}")
else:
    print("Creating new SQLite database...")

# Connect and ensure FK is enabled
with closing(sqlite3.connect(DB_NAME)) as conn:
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Core meta table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT,
            avatar_url TEXT,
            locale TEXT DEFAULT 'en',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

    # Games table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL, -- stable identifier like 'quiz_master'
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_code ON games(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_active ON games(is_active)")

    # Game scores table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
        )
    """)
    # Indices for leaderboard queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_scores_game ON game_scores(game_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_scores_user ON game_scores(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_scores_created_at ON game_scores(created_at)")
    # Composite index with score DESC for efficient top scores per game/user
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_scores_game_user_score_desc
        ON game_scores(game_id, user_id, score DESC)
    """)

    # Analytics events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_id INTEGER,
            event_type TEXT NOT NULL,
            event_props TEXT, -- JSON-encoded text
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE SET NULL ON UPDATE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON analytics_events(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_user ON analytics_events(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_game ON analytics_events(game_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_created_at ON analytics_events(created_at)")

    # Seed app_info (idempotent)
    cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("project_name", "gaming_database"))
    cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("version", "1.0.0"))
    cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("author", "MyGov Games Platform"))
    cursor.execute("INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)", ("description", "SQLite store for users, games, leaderboards, analytics."))

    # Seed users if not present
    seed_users = [
        ("alice", "alice@example.com", "Alice", None, "en"),
        ("bob", "bob@example.com", "Bob", None, "en"),
        ("chitra", "chitra@example.in", "Chitra", None, "hi"),
    ]
    for username, email, display_name, avatar_url, locale in seed_users:
        cursor.execute("""
            INSERT INTO users (username, email, display_name, avatar_url, locale)
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = ? OR email = ?)
        """, (username, email, display_name, avatar_url, locale, username, email))

    # Seed games if not present
    seed_games = [
        ("quiz_master", "Quiz Master", "A general knowledge quiz game.", "quiz", 1),
        ("civic_challenge", "Civic Challenge", "Learn about governance through mini challenges.", "education", 1),
        ("swachh_run", "Swachh Run", "Endless runner promoting cleanliness awareness.", "arcade", 1),
    ]
    for code, title, description, category, is_active in seed_games:
        cursor.execute("""
            INSERT INTO games (code, title, description, category, is_active)
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM games WHERE code = ?)
        """, (code, title, description, category, is_active, code))

    # Helper to get ids
    def get_id(table, where_col, val):
        cursor.execute(f"SELECT id FROM {table} WHERE {where_col} = ?", (val,))
        row = cursor.fetchone()
        return row[0] if row else None

    # Seed game_scores if not already present for combos
    combos = [
        ("quiz_master", "alice", 850),
        ("quiz_master", "bob", 920),
        ("civic_challenge", "alice", 1200),
        ("civic_challenge", "chitra", 1100),
        ("swachh_run", "bob", 3000),
    ]
    for game_code, username, score in combos:
        gid = get_id("games", "code", game_code)
        uid = get_id("users", "username", username)
        if gid and uid:
            cursor.execute("""
                INSERT INTO game_scores (game_id, user_id, score, metadata)
                SELECT ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM game_scores WHERE game_id = ? AND user_id = ? AND score = ?
                )
            """, (gid, uid, score, None, gid, uid, score))

    # Seed analytics_events minimal sample
    events = [
        ("alice", "quiz_master", "game_start", '{"difficulty":"medium"}'),
        ("bob", "quiz_master", "game_end", '{"score":920}'),
        ("chitra", "civic_challenge", "level_complete", '{"level":1}'),
    ]
    for username, game_code, event_type, props in events:
        uid = get_id("users", "username", username)
        gid = get_id("games", "code", game_code)
        # Allow duplicates to accumulate as analytics; optional dedupe:
        cursor.execute("""
            INSERT INTO analytics_events (user_id, game_id, event_type, event_props)
            VALUES (?, ?, ?, ?)
        """, (uid, gid, event_type, props))

    conn.commit()

    # Compute statistics
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    table_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM app_info")
    app_info_records = cursor.fetchone()[0]

# Save connection information to a file with absolute path
abs_db_path = os.path.abspath(DB_NAME)
connection_string = f"sqlite:///{abs_db_path}"

try:
    with open("db_connection.txt", "w") as f:
        f.write("# SQLite connection methods:\n")
        f.write(f"# Python: sqlite3.connect('{abs_db_path}')\n")
        f.write(f"# Connection string: {connection_string}\n")
        f.write(f"# File path: {abs_db_path}\n")
    print("Connection information saved to db_connection.txt")
except Exception as e:
    print(f"Warning: Could not save connection info: {e}")

# Create environment variables file for Node.js viewer
# Ensure db_visualizer directory exists
if not os.path.exists("db_visualizer"):
    os.makedirs("db_visualizer", exist_ok=True)
    print("Created db_visualizer directory")

try:
    with open("db_visualizer/sqlite.env", "w") as f:
        f.write(f"export SQLITE_DB=\"{abs_db_path}\"\n")
    print("Environment variables saved to db_visualizer/sqlite.env")
except Exception as e:
    print(f"Warning: Could not save environment variables: {e}")

# Final output
print("\nSQLite setup complete!")
print(f"Database: {DB_NAME}")
print(f"Location: {abs_db_path}\n")

print("To use with Node.js viewer, run: source db_visualizer/sqlite.env")

print("\nTo connect to the database, use one of the following methods:")
print(f"1. Python: sqlite3.connect('{abs_db_path}')")
print(f"2. Connection string: {connection_string}")
print(f"3. Direct file access: {abs_db_path}\n")

print("Database statistics:")
print(f"  Tables: {table_count}")
print(f"  App info records: {app_info_records}")

# If sqlite3 CLI is available, show how to use it
try:
    import subprocess
    result = subprocess.run(['which', 'sqlite3'], capture_output=True, text=True)
    if result.returncode == 0:
        print("\nSQLite CLI is available. You can also use:")
        print(f"  sqlite3 {abs_db_path}")
except Exception:
    pass

print("\nScript completed successfully.")
