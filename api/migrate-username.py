#!/usr/bin/env python3
"""One-off: ensure users.username column exists and report current users."""
import sqlite3
import sys

DB = "/home/stef/rackforge/plans.db"

conn = sqlite3.connect(DB)
cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
print("columns:", sorted(cols))
if "username" not in cols:
    conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username "
        "ON users(username) WHERE username IS NOT NULL"
    )
    conn.commit()
    print("migration: added username column")
else:
    print("migration: username column already present")

for row in conn.execute("SELECT id, email, username FROM users"):
    print("user:", row)
conn.close()