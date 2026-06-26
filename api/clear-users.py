#!/usr/bin/env python3
import os
import sqlite3

DB_PATH = os.environ.get("RACKFORGE_DB", "/home/stef/rackforge/plans.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
sessions = cur.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
user_plans = cur.execute("SELECT COUNT(*) FROM plans WHERE user_id IS NOT NULL").fetchone()[0]
cur.execute("DELETE FROM sessions")
cur.execute("DELETE FROM plans WHERE user_id IS NOT NULL")
cur.execute("DELETE FROM users")
conn.commit()
remaining = cur.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
conn.close()
print(f"Deleted users={users}, sessions={sessions}, user_plans={user_plans}")
print(f"Remaining anonymous plans={remaining}")