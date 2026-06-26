#!/usr/bin/env python3
"""One-shot: ensure bootstrap admin user exists in admin_users table."""
import os
import sqlite3
import sys

DB = os.environ.get("RACKFORGE_DB", "/home/stef/rackforge/plans.db")
ENV = os.path.expanduser("~/.config/rackforge/admin.env")

if os.path.isfile(ENV):
    for line in open(ENV, encoding="utf-8"):
        line = line.strip()
        if line.startswith("RACKFORGE_ADMIN_PASSWORD="):
            os.environ["RACKFORGE_ADMIN_PASSWORD"] = line.split("=", 1)[1].strip()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from admin_panel import ensure_admin_schema, upsert_bootstrap_admin

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
ensure_admin_schema(conn)
admin_id = upsert_bootstrap_admin(conn)
print(f"bootstrap_admin_id={admin_id}")
for row in conn.execute("SELECT username, role FROM admin_users ORDER BY username"):
    print(f"  {row['username']}: {row['role']}")