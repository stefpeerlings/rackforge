#!/usr/bin/env python3
"""RackForge API — SQLite storage with user accounts (stdlib only)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
import secrets
import smtplib
import socket
import sqlite3
import ssl
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from email_templates import (
    TOKEN_VALID_HOURS,
    build_reset_code_message,
    build_verification_html,
    build_verification_message,
    normalize_lang,
    reset_code_email_content,
    verification_email_content,
)
from admin_panel import handle_admin_get, handle_admin_post
import license as license_module
from google_oauth import (
    build_auth_url,
    exchange_code,
    fetch_userinfo,
    google_configured,
)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

DB_PATH = os.environ.get("RACKFORGE_DB", "/home/stef/rackforge/plans.db")
HOST = os.environ.get("RACKFORGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("RACKFORGE_PORT", "8080"))
STATIC_DIR = os.environ.get(
    "RACKFORGE_STATIC_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
)
TLS_ENABLED = os.environ.get("RACKFORGE_TLS", "1") == "1"
_DATA_DIR = os.path.dirname(os.path.abspath(DB_PATH))
TLS_CERT = os.environ.get("RACKFORGE_TLS_CERT", os.path.join(_DATA_DIR, "tls-cert.pem"))
TLS_KEY = os.environ.get("RACKFORGE_TLS_KEY", os.path.join(_DATA_DIR, "tls-key.pem"))
# Clean-URL page -> static file map, same routes the old Caddyfile handled.
STATIC_ROUTES = {
    "/": "index.html",
    "/login": "login.html",
    "/main": "main.html",
    "/settings": "settings.html",
    "/privacy": "privacy.html",
    "/terms": "terms.html",
    "/verify-email": "verify-email.html",
    "/reset-password": "reset-password.html",
}
STATIC_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}
MAX_BODY = 512_000
PLAN_ID_RE = re.compile(r"^[a-f0-9]{32}$")
CUSTOM_TYPE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
SNAPSHOT_ID_RE = re.compile(r"^[a-f0-9]{32}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
SESSION_COOKIE = "rackforge_session"
SESSION_DAYS = 30
PBKDF2_ROUNDS = 260_000
SECURE_COOKIE = os.environ.get("RACKFORGE_SECURE_COOKIE", "1") == "1"
APP_URL = os.environ.get("RACKFORGE_APP_URL", "https://example.com").rstrip("/")
SMTP_HOST = os.environ.get("RACKFORGE_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("RACKFORGE_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("RACKFORGE_SMTP_USER", "")
SMTP_PASS = os.environ.get("RACKFORGE_SMTP_PASS", "")
SMTP_FROM = os.environ.get(
    "RACKFORGE_SMTP_FROM", "noreply RackForge <noreply@example.com>"
)
VERIFY_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")
RESET_CODE_RE = re.compile(r"^\d{6}$")
VERIFY_HOURS = TOKEN_VALID_HOURS
AVATAR_DIR = os.environ.get("RACKFORGE_AVATAR_DIR", "/home/stef/rackforge/avatars")
AVATAR_MAX_BYTES = 512_000
DATA_URL_RE = re.compile(
    r"^data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def session_expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).replace(microsecond=0).isoformat()


def verification_expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=VERIFY_HOURS)).replace(microsecond=0).isoformat()


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                rack_height INTEGER NOT NULL,
                devices TEXT NOT NULL,
                next_id INTEGER NOT NULL,
                user_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "username" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "email_verified" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1"
            )
        if "lang" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'nl'"
            )
        if "avatar_ext" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_ext TEXT")
        if "avatar_updated_at" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_updated_at TEXT")
        if "google_id" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        if "password_set" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN password_set INTEGER NOT NULL DEFAULT 1"
            )
            conn.execute(
                "UPDATE users SET password_set = 0 WHERE google_id IS NOT NULL"
            )
        if "blocked" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id) WHERE google_id IS NOT NULL"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                lang TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_verifications (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_resets (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        reset_cols = {row[1] for row in conn.execute("PRAGMA table_info(password_resets)")}
        if "code" not in reset_cols:
            conn.execute("ALTER TABLE password_resets ADD COLUMN code TEXT")
        cols = {row[1] for row in conn.execute("PRAGMA table_info(plans)")}
        if "user_id" not in cols:
            conn.execute("ALTER TABLE plans ADD COLUMN user_id TEXT")
        if "connections" not in cols:
            conn.execute(
                "ALTER TABLE plans ADD COLUMN connections TEXT NOT NULL DEFAULT '[]'"
            )
        if "name" not in cols:
            conn.execute("ALTER TABLE plans ADD COLUMN name TEXT")
        if "power_budget_w" not in cols:
            conn.execute(
                "ALTER TABLE plans ADD COLUMN power_budget_w INTEGER NOT NULL DEFAULT 0"
            )
        # Accounts may now hold more than one plan (tier-limited, see license.py) —
        # this index is for lookup performance only, no longer a uniqueness constraint.
        conn.execute("DROP INDEX IF EXISTS idx_plans_user_id")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_user_id ON plans(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'administrator',
                created_at TEXT NOT NULL,
                last_login TEXT,
                app_user_id TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        admin_cols = {row[1] for row in conn.execute("PRAGMA table_info(admin_users)")}
        if "must_change_password" not in admin_cols:
            conn.execute(
                "ALTER TABLE admin_users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
            )
        conn.commit()
        license_module.ensure_license_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_equipment_types (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                height INTEGER NOT NULL,
                color TEXT NOT NULL,
                power_w INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_custom_equipment_types_user_id ON custom_equipment_types(user_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_snapshots (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                rack_height INTEGER NOT NULL,
                devices TEXT NOT NULL,
                next_id INTEGER NOT NULL,
                name TEXT,
                power_budget_w INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_snapshots_plan_id ON plan_snapshots(plan_id, created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_collaborators (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                created_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(plan_id, user_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_collaborators_plan_id ON plan_collaborators(plan_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_plan_collaborators_user_id ON plan_collaborators(user_id)"
        )
        conn.commit()


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return salt, digest


def verify_password(password: str, salt: str, digest: str) -> bool:
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return secrets.compare_digest(check, digest)


def normalize_plan_name(raw: Any) -> str | None:
    """Trim to <=60 chars; blank/invalid input means "use the default", not "clear it"."""
    if not isinstance(raw, str):
        return None
    name = raw.strip()[:60]
    return name or None


def validate_plan(body: dict[str, Any]) -> dict[str, Any] | str:
    try:
        rack_height = int(body["rackHeight"])
        next_id = int(body["nextId"])
        devices = body["devices"]
    except (KeyError, TypeError, ValueError):
        return "Invalid plan payload"

    if rack_height < 1 or rack_height > 48:
        return "Invalid rack height"
    if next_id < 1:
        return "Invalid nextId"
    if not isinstance(devices, list):
        return "devices must be a list"

    for d in devices:
        if not isinstance(d, dict):
            return "Invalid device entry"
        for key in ("id", "type", "startU", "height"):
            if key not in d:
                return f"Device missing {key}"
        if not isinstance(d.get("label", ""), str):
            return "Invalid device label"
        power_w = d.get("powerW")
        if power_w is not None:
            try:
                if float(power_w) < 0:
                    return "Invalid device power"
            except (TypeError, ValueError):
                return "Invalid device power"

    power_budget_w = body.get("powerBudgetW", 0)
    try:
        power_budget_w = int(power_budget_w) if power_budget_w is not None else 0
    except (TypeError, ValueError):
        return "Invalid power budget"
    if power_budget_w < 0:
        return "Invalid power budget"

    connections = body.get("connections", [])
    if connections is None:
        connections = []
    if not isinstance(connections, list):
        return "connections must be a list"
    for c in connections:
        if not isinstance(c, dict):
            return "Invalid connection entry"
        for key in ("id", "fromDeviceId", "fromPort", "toDeviceId", "toPort"):
            if key not in c:
                return f"Connection missing {key}"
        try:
            int(c["fromDeviceId"])
            int(c["toDeviceId"])
            int(c["fromPort"])
            int(c["toPort"])
            int(c["id"])
        except (TypeError, ValueError):
            return "Invalid connection ids or ports"
        if not isinstance(c.get("label", ""), str):
            return "Invalid connection label"
        color = c.get("color", "")
        if color is not None and not isinstance(color, str):
            return "Invalid connection color"
        if color and len(color) > 32:
            return "Invalid connection color"

    return {
        "rack_height": rack_height,
        "next_id": next_id,
        "devices": json.dumps(devices, separators=(",", ":")),
        "connections": json.dumps(connections, separators=(",", ":")),
        "name": normalize_plan_name(body.get("name")),
        "power_budget_w": power_budget_w,
    }


def row_to_plan(row: sqlite3.Row, *, role: str | None = None) -> dict[str, Any]:
    raw_connections = row["connections"] if "connections" in row.keys() else "[]"
    try:
        connections = json.loads(raw_connections or "[]")
    except json.JSONDecodeError:
        connections = []
    if not isinstance(connections, list):
        connections = []
    result = {
        "id": row["id"],
        "name": (row["name"] if "name" in row.keys() else None) or "Rack",
        "rackHeight": row["rack_height"],
        "devices": json.loads(row["devices"]),
        "connections": connections,
        "nextId": row["next_id"],
        "powerBudgetW": (row["power_budget_w"] if "power_budget_w" in row.keys() else 0) or 0,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
    if role is not None:
        result["role"] = role
    return result


def get_plan_access(
    conn: sqlite3.Connection, plan_row: sqlite3.Row, user_id: str | None
) -> str | None:
    """Returns 'owner' | 'editor' | 'viewer' | None (no access).

    plan_row['user_id'] is NULL for the pre-account anonymous/guest plans (created via
    POST /api/plans, loaded via ?plan=<id> with zero auth) — that existing "anyone can
    GET/PUT a NULL-owner plan" behavior must not regress, so this returns a synthetic
    'editor' for NULL-owner rows regardless of caller, letting every call site use this
    helper uniformly instead of special-casing NULL owners individually.

    Deliberately collapses "plan doesn't exist" and "plan exists but no access" to the
    same None — no frontend code branches on 403 vs 404 for plan loads, so callers can
    just map None -> 404.
    """
    if plan_row["user_id"] is None:
        return "editor"
    if user_id and plan_row["user_id"] == user_id:
        return "owner"
    if not user_id:
        return None
    collab = conn.execute(
        "SELECT role FROM plan_collaborators WHERE plan_id = ? AND user_id = ?",
        (plan_row["id"], user_id),
    ).fetchone()
    return collab["role"] if collab else None


def maybe_snapshot_plan(
    conn: sqlite3.Connection, plan_id: str, row: sqlite3.Row, *, force: bool = False
) -> None:
    """Called just before a plan's live state is overwritten. Stores a
    snapshot of the state being replaced, throttled so routine autosaves
    (every ~1.5s while editing) don't create one row each — only the first
    save past SNAPSHOT_MIN_INTERVAL_SECONDS since the last snapshot does.

    force=True bypasses the throttle — used before a restore, since that's a
    deliberate, infrequent action whose own "before" state should always be
    recoverable, even if it happens to land inside another edit's throttle
    window."""
    now = utc_now()
    if not force:
        latest = conn.execute(
            "SELECT created_at FROM plan_snapshots WHERE plan_id = ? ORDER BY created_at DESC LIMIT 1",
            (plan_id,),
        ).fetchone()
        if latest:
            elapsed = (datetime.fromisoformat(now) - datetime.fromisoformat(latest["created_at"])).total_seconds()
            if elapsed < license_module.SNAPSHOT_MIN_INTERVAL_SECONDS:
                return
    snapshot_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO plan_snapshots (id, plan_id, rack_height, devices, next_id, name, power_budget_w, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            plan_id,
            row["rack_height"],
            row["devices"],
            row["next_id"],
            row["name"] if "name" in row.keys() else None,
            (row["power_budget_w"] if "power_budget_w" in row.keys() else 0) or 0,
            now,
        ),
    )
    max_snapshots = license_module.get_max_snapshots(conn)
    keep_rows = conn.execute(
        "SELECT id FROM plan_snapshots WHERE plan_id = ? ORDER BY created_at DESC LIMIT ?",
        (plan_id, max_snapshots),
    ).fetchall()
    keep_ids = {r["id"] for r in keep_rows}
    all_rows = conn.execute(
        "SELECT id FROM plan_snapshots WHERE plan_id = ?", (plan_id,)
    ).fetchall()
    for r in all_rows:
        if r["id"] not in keep_ids:
            conn.execute("DELETE FROM plan_snapshots WHERE id = ?", (r["id"],))


def normalize_username(raw: str) -> str | None:
    username = raw.strip()
    if not USERNAME_RE.match(username):
        return None
    return username


def oauth_password_credentials() -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    return salt, digest


def allocate_username(conn: sqlite3.Connection, email: str) -> str:
    local = email.split("@", 1)[0]
    base = re.sub(r"[^a-zA-Z0-9_]", "_", local).strip("_")
    if len(base) < 3:
        base = "user"
    base = base[:20]
    if not USERNAME_RE.match(base):
        base = "user"
    candidate = base
    n = 1
    while conn.execute(
        "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (candidate,)
    ).fetchone():
        suffix = f"_{n}"
        candidate = f"{base[: 20 - len(suffix)]}{suffix}"
        n += 1
    return candidate


def purge_expired_oauth_states(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (utc_now(),))


def oauth_state_expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat()


def find_user_by_login(conn: sqlite3.Connection, raw: str) -> sqlite3.Row | None:
    login = raw.strip()
    if not login:
        return None

    lowered = login.lower()
    row = conn.execute(
        "SELECT * FROM users WHERE lower(email) = ?", (lowered,)
    ).fetchone()
    if row:
        return row

    row = conn.execute(
        "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (login,)
    ).fetchone()
    if row:
        return row

    if USERNAME_RE.match(login):
        return conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (login,)
        ).fetchone()
    return None


def ensure_avatar_dir() -> None:
    os.makedirs(AVATAR_DIR, exist_ok=True)


def detect_lan_ip() -> str | None:
    """Best-effort local IP so the self-signed cert's SAN covers
    https://<lan-ip>:port/ out of the box. Doesn't actually send traffic —
    UDP "connect" just picks the outbound-facing interface/address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def ensure_self_signed_cert(cert_path: str, key_path: str) -> bool:
    """Generates a self-signed TLS cert via the openssl CLI (same
    zero-pip-dependency approach as license.py) if one isn't already
    present. Returns True if cert+key are ready to use."""
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return True

    lan_ip = detect_lan_ip()
    san_entries = ["DNS:localhost", "IP:127.0.0.1"]
    if lan_ip and lan_ip not in ("127.0.0.1",):
        san_entries.append(f"IP:{lan_ip}")
    san = ",".join(san_entries)

    os.makedirs(os.path.dirname(cert_path) or ".", exist_ok=True)
    try:
        result = subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", key_path,
                "-out", cert_path,
                "-days", "3650",
                "-subj", "/CN=rackforge",
                "-addext", f"subjectAltName={san}",
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("[tls] 'openssl' binary not found on PATH — cannot generate a self-signed certificate")
        return False

    if result.returncode != 0:
        print(f"[tls] openssl failed to generate a certificate: {result.stderr.strip()}")
        return False
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    print(f"[tls] generated self-signed certificate (SAN: {san})")
    return True


def avatar_file_path(user_id: str, ext: str) -> str:
    return os.path.join(AVATAR_DIR, f"{user_id}.{ext}")


def detect_image_ext(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def avatar_mime(ext: str) -> str:
    return {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[ext]


def remove_avatar_files(user_id: str) -> None:
    for ext in ("png", "jpg", "webp"):
        try:
            os.remove(avatar_file_path(user_id, ext))
        except FileNotFoundError:
            pass


def save_user_avatar(user_id: str, data: bytes, ext: str) -> None:
    ensure_avatar_dir()
    remove_avatar_files(user_id)
    with open(avatar_file_path(user_id, ext), "wb") as handle:
        handle.write(data)


def parse_avatar_data_url(raw: str) -> tuple[bytes, str] | str:
    match = DATA_URL_RE.match(raw.strip())
    if not match:
        return "Invalid image format"
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        return "Invalid image data"
    if len(data) > AVATAR_MAX_BYTES:
        return "Image too large"
    if len(data) < 32:
        return "Invalid image data"
    ext = detect_image_ext(data)
    if not ext:
        return "Unsupported image type"
    return data, ext


def row_to_user(row: sqlite3.Row) -> dict[str, str]:
    username = row["username"] or ""
    return {"id": row["id"], "email": row["email"], "username": username}


def user_has_password(user: sqlite3.Row) -> bool:
    if "password_set" in user.keys():
        return bool(user["password_set"])
    google_id = user["google_id"] if "google_id" in user.keys() else None
    return not bool(google_id)


def user_is_blocked(user: sqlite3.Row) -> bool:
    return bool(user["blocked"]) if "blocked" in user.keys() else False


def user_payload(conn: sqlite3.Connection, user: sqlite3.Row) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": user["id"],
        "email": user["email"],
        "username": user["username"] or "",
        "emailVerified": bool(user["email_verified"]),
        "lang": normalize_lang(user["lang"] if "lang" in user.keys() else "nl"),
    }
    avatar_ext = user["avatar_ext"] if "avatar_ext" in user.keys() else None
    avatar_updated = (
        user["avatar_updated_at"] if "avatar_updated_at" in user.keys() else None
    )
    if avatar_ext and avatar_updated:
        data["avatarUrl"] = f"/api/avatars/{user['id']}?v={avatar_updated}"
    pending = conn.execute(
        """
        SELECT email FROM email_verifications
        WHERE user_id = ? AND expires_at >= ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (user["id"], utc_now()),
    ).fetchone()
    if pending:
        data["pendingEmail"] = pending["email"]
    google_id = user["google_id"] if "google_id" in user.keys() else None
    data["hasPassword"] = user_has_password(user)
    data["signedInWithGoogle"] = bool(google_id)
    tier = license_module.get_license_info(conn)["tier"]
    data["license"] = {
        "tier": tier,
        "maxRacks": license_module.TIER_RACK_LIMITS[tier],
        "maxCustomTypes": license_module.TIER_CUSTOM_TYPE_LIMITS[tier],
        "maxCollaborators": license_module.TIER_COLLABORATOR_LIMITS[tier],
    }
    return data


def purge_expired_verifications(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM email_verifications WHERE expires_at < ?", (utc_now(),))


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def purge_expired_password_resets(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM password_resets WHERE expires_at < ?", (utc_now(),))


def normalize_reset_code(raw: str) -> str:
    return re.sub(r"\D", "", str(raw).strip())


def create_password_reset(conn: sqlite3.Connection, user_id: str) -> tuple[str, str]:
    purge_expired_password_resets(conn)
    conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    token = secrets.token_hex(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = utc_now()
    conn.execute(
        """
        INSERT INTO password_resets (token, user_id, code, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (token, user_id, code, verification_expires(), now),
    )
    return token, code


def send_password_reset_email(to_email: str, code: str, lang: str) -> None:
    if not smtp_configured():
        print(
            f"[{utc_now()}] SMTP not configured. Password reset code for {to_email}: {code}"
        )
        return

    content = reset_code_email_content(lang, code)
    msg = build_reset_code_message(
        to_email=to_email,
        from_addr=SMTP_FROM,
        content=content,
        app_url=APP_URL,
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if SMTP_PORT == 587:
            smtp.starttls()
            smtp.ehlo()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def send_verification_email(
    to_email: str, token: str, purpose: str, lang: str, *, test: bool = False
) -> None:
    link = f"{APP_URL}/verify-email?token={token}"
    if not smtp_configured():
        print(
            f"[{utc_now()}] SMTP not configured. Verification link for {to_email}: {link}"
        )
        return

    content = verification_email_content(purpose, lang, link, test=test)
    msg = build_verification_message(
        to_email=to_email,
        from_addr=SMTP_FROM,
        content=content,
        link=link,
        app_url=APP_URL,
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if SMTP_PORT == 587:
            smtp.starttls()
            smtp.ehlo()
        if SMTP_USER and SMTP_PASS:
            smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def create_verification(
    conn: sqlite3.Connection, user_id: str, email: str, purpose: str
) -> str:
    purge_expired_verifications(conn)
    conn.execute("DELETE FROM email_verifications WHERE user_id = ?", (user_id,))
    token = secrets.token_hex(32)
    now = utc_now()
    conn.execute(
        """
        INSERT INTO email_verifications (token, user_id, email, purpose, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (token, user_id, email, purpose, verification_expires(), now),
    )
    return token


def purge_expired_sessions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (utc_now(),))


def get_session_token(handler: BaseHTTPRequestHandler) -> str | None:
    cookie = handler.headers.get("Cookie", "")
    prefix = SESSION_COOKIE + "="
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            token = part[len(prefix) :]
            if re.fullmatch(r"[a-f0-9]{64}", token):
                return token
    return None


def get_current_user(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    purge_expired_sessions(conn)
    row = conn.execute(
        """
        SELECT users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ? AND sessions.expires_at >= ?
        """,
        (token, utc_now()),
    ).fetchone()
    if row and user_is_blocked(row):
        return None
    return row


class Handler(BaseHTTPRequestHandler):
    server_version = "RackForgeAPI/2.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utc_now()}] {self.address_string()} {fmt % args}")

    def send_json(self, status: int, payload: dict[str, Any], *, cookies: list[str] | None = None) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookies:
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str, *, cookies: list[str] | None = None) -> None:
        self.send_json(status, {"error": message}, cookies=cookies)

    def send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> bool:
        """Serves the frontend directly (Caddy used to do this). Returns
        True if a response was sent, False to fall through to a 404."""
        rel = STATIC_ROUTES.get(path, path.lstrip("/"))
        if not rel:
            rel = "index.html"

        static_root = Path(STATIC_DIR).resolve()
        try:
            resolved = (static_root / rel).resolve()
        except (OSError, ValueError):
            return False
        # Reject path traversal (../..) and symlinks that escape STATIC_DIR.
        if not (resolved == static_root or resolved.is_relative_to(static_root)):
            return False
        if not resolved.is_file():
            return False

        content_type = STATIC_CONTENT_TYPES.get(
            resolved.suffix.lower(), mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        )
        try:
            body = resolved.read_bytes()
        except OSError:
            return False
        self.send_bytes(200, body, content_type)
        return True

    def send_redirect(self, url: str, *, cookies: list[str] | None = None) -> None:
        self.send_response(302)
        self.send_header("Location", url)
        if cookies:
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            return None
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def cookie_header(self, token: str, *, max_age: int) -> str:
        secure = "; Secure" if SECURE_COOKIE else ""
        return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"

    def clear_cookie_header(self) -> str:
        secure = "; Secure" if SECURE_COOKIE else ""
        return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure}"

    def create_session(self, conn: sqlite3.Connection, user_id: str) -> str:
        token = secrets.token_hex(32)
        now = utc_now()
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, user_id, session_expires(), now),
        )
        return token

    def handle_register(self, body: dict[str, Any]) -> None:
        email = str(body.get("email", "")).strip().lower()
        password = str(body.get("password", ""))
        username = normalize_username(str(body.get("username", "")))
        if not EMAIL_RE.match(email):
            self.send_error_json(400, "Invalid email")
            return
        if username is None:
            self.send_error_json(400, "Invalid username")
            return
        if len(password) < 8:
            self.send_error_json(400, "Password must be at least 8 characters")
            return

        lang = normalize_lang(str(body.get("lang", "")))
        salt, digest = hash_password(password)
        user_id = uuid.uuid4().hex
        now = utc_now()
        with db_conn() as conn:
            purge_expired_sessions(conn)
            if conn.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            ).fetchone():
                self.send_error_json(409, "Email already registered")
                return
            if conn.execute(
                "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone():
                self.send_error_json(409, "Username already taken")
                return
            conn.execute(
                """
                INSERT INTO users (
                    id, email, username, password_salt, password_hash, created_at,
                    email_verified, lang, password_set
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, 1)
                """,
                (user_id, email, username, salt, digest, now, lang),
            )
            session_token = self.create_session(conn, user_id)
            verify_token = create_verification(conn, user_id, email, "register")
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        try:
            send_verification_email(email, verify_token, "register", lang)
        except Exception as exc:
            print(f"[{utc_now()}] Verification email failed: {exc}")

        max_age = SESSION_DAYS * 86400
        with db_conn() as conn:
            payload = user_payload(conn, user)
        self.send_json(
            201,
            {"user": payload, "verificationSent": True},
            cookies=[self.cookie_header(session_token, max_age=max_age)],
        )

    def handle_auth_providers(self) -> None:
        self.send_json(200, {"google": google_configured()})

    def handle_google_start(self) -> None:
        if not google_configured():
            self.send_error_json(503, "Google sign-in not configured")
            return
        qs = parse_qs(urlparse(self.path).query)
        lang = normalize_lang(qs.get("lang", ["nl"])[0])
        state = secrets.token_urlsafe(32)
        now = utc_now()
        with db_conn() as conn:
            purge_expired_oauth_states(conn)
            conn.execute(
                "INSERT INTO oauth_states (state, lang, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (state, lang, oauth_state_expires(), now),
            )
            conn.commit()
        self.send_redirect(build_auth_url(state=state, lang=lang))

    def handle_google_callback(self) -> None:
        if not google_configured():
            self.send_redirect(f"{APP_URL}/login?google_error=unavailable")
            return
        qs = parse_qs(urlparse(self.path).query)
        error = qs.get("error", [""])[0]
        if error:
            self.send_redirect(f"{APP_URL}/login?google_error={quote(error)}")
            return
        code = qs.get("code", [""])[0]
        state = qs.get("state", [""])[0]
        if not code or not state:
            self.send_redirect(f"{APP_URL}/login?google_error=invalid")
            return

        with db_conn() as conn:
            purge_expired_oauth_states(conn)
            state_row = conn.execute(
                "SELECT lang FROM oauth_states WHERE state = ? AND expires_at >= ?",
                (state, utc_now()),
            ).fetchone()
            if not state_row:
                self.send_redirect(f"{APP_URL}/login?google_error=expired")
                return
            lang = normalize_lang(state_row["lang"])
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))

        try:
            token_data = exchange_code(code)
            access_token = str(token_data.get("access_token", ""))
            if not access_token:
                raise ValueError("Missing access token")
            profile = fetch_userinfo(access_token)
        except Exception as exc:
            print(f"[{utc_now()}] Google OAuth failed: {exc}")
            self.send_redirect(f"{APP_URL}/login?google_error=failed")
            return

        google_id = str(profile.get("sub", "")).strip()
        email = str(profile.get("email", "")).strip().lower()
        email_verified = bool(profile.get("email_verified"))
        if not google_id or not email or not email_verified:
            self.send_redirect(f"{APP_URL}/login?google_error=email")
            return
        if not EMAIL_RE.match(email):
            self.send_redirect(f"{APP_URL}/login?google_error=email")
            return

        now = utc_now()
        with db_conn() as conn:
            purge_expired_sessions(conn)
            user = conn.execute(
                "SELECT * FROM users WHERE google_id = ?", (google_id,)
            ).fetchone()
            if not user:
                user = conn.execute(
                    "SELECT * FROM users WHERE email = ?", (email,)
                ).fetchone()
                if user:
                    if user["google_id"] and user["google_id"] != google_id:
                        self.send_redirect(f"{APP_URL}/login?google_error=linked")
                        return
                    conn.execute(
                        "UPDATE users SET google_id = ?, email_verified = 1 WHERE id = ?",
                        (google_id, user["id"]),
                    )
                else:
                    username = allocate_username(conn, email)
                    salt, digest = oauth_password_credentials()
                    user_id = uuid.uuid4().hex
                    conn.execute(
                        """
                        INSERT INTO users (
                            id, email, username, password_salt, password_hash,
                            created_at, email_verified, lang, google_id, password_set
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 0)
                        """,
                        (user_id, email, username, salt, digest, now, lang, google_id),
                    )
                    user = conn.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
            else:
                conn.execute(
                    "UPDATE users SET email_verified = 1, lang = ? WHERE id = ?",
                    (lang, user["id"]),
                )
                user = conn.execute(
                    "SELECT * FROM users WHERE id = ?", (user["id"],)
                ).fetchone()

            if user_is_blocked(user):
                self.send_redirect(f"{APP_URL}/login?google_error=blocked")
                return

            session_token = self.create_session(conn, user["id"])
            conn.commit()

        max_age = SESSION_DAYS * 86400
        self.send_redirect(
            f"{APP_URL}/main",
            cookies=[self.cookie_header(session_token, max_age=max_age)],
        )

    def handle_login(self, body: dict[str, Any]) -> None:
        login = str(body.get("email", "")).strip()
        password = str(body.get("password", ""))
        lang = normalize_lang(str(body.get("lang", ""))) if body.get("lang") else None
        with db_conn() as conn:
            purge_expired_sessions(conn)
            user = find_user_by_login(conn, login)
            if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
                self.send_error_json(401, "Invalid email or password")
                return
            if user_is_blocked(user):
                self.send_error_json(403, "Account blocked")
                return
            if lang:
                conn.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, user["id"]))
            token = self.create_session(conn, user["id"])
            conn.commit()
            if lang:
                user = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()

        max_age = SESSION_DAYS * 86400
        with db_conn() as conn:
            payload = user_payload(conn, user)
        self.send_json(
            200,
            {"user": payload},
            cookies=[self.cookie_header(token, max_age=max_age)],
        )

    def handle_logout(self) -> None:
        token = get_session_token(self)
        if token:
            with db_conn() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
        self.send_json(200, {"ok": True}, cookies=[self.clear_cookie_header()])

    def handle_me(self) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            payload = user_payload(conn, user)
        self.send_json(200, {"user": payload})

    def handle_verify_email(self, token: str) -> None:
        if not VERIFY_TOKEN_RE.match(token):
            self.send_error_json(400, "Invalid verification link")
            return

        with db_conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM email_verifications
                WHERE token = ? AND expires_at >= ?
                """,
                (token, utc_now()),
            ).fetchone()
            if not row:
                self.send_error_json(400, "Invalid or expired verification link")
                return

            user_id = row["user_id"]
            email = row["email"]
            purpose = row["purpose"]

            if purpose == "change_email":
                if conn.execute(
                    "SELECT 1 FROM users WHERE email = ? AND id != ?", (email, user_id)
                ).fetchone():
                    self.send_error_json(409, "Email already registered")
                    return
                conn.execute(
                    "UPDATE users SET email = ?, email_verified = 1 WHERE id = ?",
                    (email, user_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,)
                )

            conn.execute("DELETE FROM email_verifications WHERE user_id = ?", (user_id,))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            payload = user_payload(conn, user)

        self.send_json(200, {"ok": True, "user": payload})

    def handle_forgot_password(self, body: dict[str, Any]) -> None:
        login = str(body.get("email", "")).strip()
        lang = normalize_lang(str(body.get("lang", "")))
        if not login:
            self.send_error_json(400, "Invalid email")
            return

        with db_conn() as conn:
            user = find_user_by_login(conn, login)
            if not user:
                self.send_error_json(404, "Email not registered")
                return

            mail_to = user["email"]
            mail_lang = lang or normalize_lang(user["lang"] if "lang" in user.keys() else "nl")
            _token, code = create_password_reset(conn, user["id"])
            conn.commit()
            try:
                send_password_reset_email(mail_to, code, mail_lang)
            except Exception as exc:
                print(f"[{utc_now()}] Password reset email failed: {exc}")
                self.send_error_json(503, "Could not send reset email")
                return

        self.send_json(200, {"ok": True, "email": mail_to})

    def handle_verify_reset_code(self, body: dict[str, Any]) -> None:
        login = str(body.get("email", "")).strip()
        code = normalize_reset_code(str(body.get("code", "")))
        if not login:
            self.send_error_json(400, "Invalid email")
            return
        if not RESET_CODE_RE.match(code):
            self.send_error_json(400, "Invalid reset code")
            return

        with db_conn() as conn:
            purge_expired_password_resets(conn)
            user = find_user_by_login(conn, login)
            if not user:
                self.send_error_json(400, "Invalid or expired reset code")
                return
            row = conn.execute(
                """
                SELECT token FROM password_resets
                WHERE user_id = ? AND code = ? AND expires_at >= ?
                """,
                (user["id"], code, utc_now()),
            ).fetchone()
        if not row:
            self.send_error_json(400, "Invalid or expired reset code")
            return
        self.send_json(200, {"resetToken": row["token"]})

    def handle_check_reset_token(self, token: str) -> None:
        if not VERIFY_TOKEN_RE.match(token):
            self.send_error_json(400, "Invalid reset link")
            return
        with db_conn() as conn:
            purge_expired_password_resets(conn)
            row = conn.execute(
                """
                SELECT 1 FROM password_resets
                WHERE token = ? AND expires_at >= ?
                """,
                (token, utc_now()),
            ).fetchone()
        if not row:
            self.send_error_json(400, "Invalid or expired reset link")
            return
        self.send_json(200, {"ok": True})

    def handle_reset_password(self, body: dict[str, Any]) -> None:
        token = str(body.get("token", "")).strip()
        password = str(body.get("password", ""))
        if not VERIFY_TOKEN_RE.match(token):
            self.send_error_json(400, "Invalid reset link")
            return
        if len(password) < 8:
            self.send_error_json(400, "Password must be at least 8 characters")
            return

        with db_conn() as conn:
            purge_expired_password_resets(conn)
            row = conn.execute(
                """
                SELECT user_id FROM password_resets
                WHERE token = ? AND expires_at >= ?
                """,
                (token, utc_now()),
            ).fetchone()
            if not row:
                self.send_error_json(400, "Invalid or expired reset link")
                return

            user_id = row["user_id"]
            salt, digest = hash_password(password)
            conn.execute(
                """
                UPDATE users
                SET password_salt = ?, password_hash = ?, password_set = 1
                WHERE id = ?
                """,
                (salt, digest, user_id),
            )
            conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.commit()

        self.send_json(200, {"ok": True})

    def handle_resend_verification(self, body: dict[str, Any] | None) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return

            lang = normalize_lang(
                str(body.get("lang", "")) if body else user["lang"]
            )
            if body and body.get("lang"):
                conn.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, user["id"]))
                conn.commit()

            row = conn.execute(
                """
                SELECT * FROM email_verifications
                WHERE user_id = ? AND expires_at >= ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user["id"], utc_now()),
            ).fetchone()

            if row:
                token = row["token"]
                email = row["email"]
                purpose = row["purpose"]
            elif not user["email_verified"]:
                token = create_verification(conn, user["id"], user["email"], "register")
                email = user["email"]
                purpose = "register"
                conn.commit()
            else:
                self.send_error_json(400, "Nothing to verify")
                return

        try:
            send_verification_email(email, token, purpose, lang)
        except Exception as exc:
            print(f"[{utc_now()}] Verification email failed: {exc}")
            self.send_error_json(503, "Could not send verification email")
            return

        self.send_json(200, {"ok": True, "email": email})

    def handle_update_lang(self, body: dict[str, Any]) -> None:
        lang = normalize_lang(str(body.get("lang", "")))
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            conn.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, user["id"]))
            conn.commit()
            updated = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            payload = user_payload(conn, updated)
        self.send_json(200, {"user": payload})

    def handle_update_account(self, body: dict[str, Any]) -> None:
        email = str(body.get("email", "")).strip().lower()
        password = str(body.get("password", ""))
        new_password = str(body.get("newPassword", ""))
        if not EMAIL_RE.match(email):
            self.send_error_json(400, "Invalid email")
            return
        if new_password and len(new_password) < 8:
            self.send_error_json(400, "Password must be at least 8 characters")
            return

        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            if user_has_password(user):
                if not password:
                    self.send_error_json(400, "Password required")
                    return
                if not verify_password(
                    password, user["password_salt"], user["password_hash"]
                ):
                    self.send_error_json(401, "Invalid password")
                    return

            email_changed = email != user["email"]
            password_changed = bool(new_password)
            if not email_changed and not password_changed:
                self.send_json(200, {"user": user_payload(conn, user)})
                return

            if email_changed and conn.execute(
                "SELECT 1 FROM users WHERE email = ? AND id != ?", (email, user["id"])
            ).fetchone():
                self.send_error_json(409, "Email already registered")
                return

            verify_token = None
            if email_changed:
                verify_token = create_verification(
                    conn, user["id"], email, "change_email"
                )
            if body.get("lang"):
                conn.execute(
                    "UPDATE users SET lang = ? WHERE id = ?",
                    (normalize_lang(str(body.get("lang", ""))), user["id"]),
                )
            if password_changed:
                salt, digest = hash_password(new_password)
                conn.execute(
                    """
                    UPDATE users
                    SET password_salt = ?, password_hash = ?, password_set = 1
                    WHERE id = ?
                    """,
                    (salt, digest, user["id"]),
                )
            conn.commit()
            updated = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            payload = user_payload(conn, updated)
            mail_lang = normalize_lang(updated["lang"])

        verification_sent = False
        if verify_token:
            try:
                send_verification_email(email, verify_token, "change_email", mail_lang)
                verification_sent = True
            except Exception as exc:
                print(f"[{utc_now()}] Verification email failed: {exc}")
                self.send_error_json(503, "Could not send verification email")
                return

        response: dict[str, Any] = {"user": payload}
        if verification_sent:
            response["verificationSent"] = True
            response["pendingEmail"] = email
        self.send_json(200, response)

    def handle_delete_account(self, body: dict[str, Any] | None) -> None:
        password = str((body or {}).get("password", ""))

        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            google_id = user["google_id"] if "google_id" in user.keys() else None
            must_verify_password = user_has_password(user) and not (
                google_id and not password
            )
            if must_verify_password:
                if not password:
                    self.send_error_json(400, "Password required")
                    return
                if not verify_password(
                    password, user["password_salt"], user["password_hash"]
                ):
                    self.send_error_json(401, "Invalid password")
                    return

            user_id = user["id"]
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM email_verifications WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
            # Collaborator access this user has on *other* people's plans. Their own
            # plans' collaborator rows are cleaned up via ON DELETE CASCADE when those
            # plans are deleted below.
            conn.execute("DELETE FROM plan_collaborators WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM plans WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()

        remove_avatar_files(user_id)
        self.send_json(200, {"ok": True}, cookies=[self.clear_cookie_header()])

    def handle_get_avatar(self, user_id: str) -> None:
        if not PLAN_ID_RE.match(user_id):
            self.send_error_json(400, "Invalid user id")
            return
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            row = conn.execute(
                "SELECT avatar_ext FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not row or not row["avatar_ext"]:
                self.send_error_json(404, "No avatar")
                return
            ext = row["avatar_ext"]
        path = avatar_file_path(user_id, ext)
        if not os.path.isfile(path):
            self.send_error_json(404, "No avatar")
            return
        with open(path, "rb") as handle:
            data = handle.read()
        self.send_bytes(200, data, avatar_mime(ext))

    def handle_upload_avatar(self, body: dict[str, Any]) -> None:
        parsed = parse_avatar_data_url(str(body.get("image", "")))
        if isinstance(parsed, str):
            self.send_error_json(400, parsed)
            return
        data, ext = parsed
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            save_user_avatar(user["id"], data, ext)
            now = utc_now()
            conn.execute(
                """
                UPDATE users
                SET avatar_ext = ?, avatar_updated_at = ?
                WHERE id = ?
                """,
                (ext, now, user["id"]),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            payload = user_payload(conn, updated)
        self.send_json(200, {"user": payload})

    def handle_delete_avatar(self) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            remove_avatar_files(user["id"])
            conn.execute(
                """
                UPDATE users
                SET avatar_ext = NULL, avatar_updated_at = NULL
                WHERE id = ?
                """,
                (user["id"],),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            payload = user_payload(conn, updated)
        self.send_json(200, {"user": payload})

    def handle_get_my_plan(self) -> None:
        """Deprecated single-plan shim, kept for old cached clients. Read-only
        convenience: returns the most recently updated plan. Current frontend
        uses GET /api/me/plans + GET /api/plans/<id> instead."""
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            row = conn.execute(
                "SELECT * FROM plans WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user["id"],),
            ).fetchone()
        if not row:
            self.send_error_json(404, "No plan saved yet")
            return
        self.send_json(200, row_to_plan(row))

    def handle_put_my_plan(self, body: dict[str, Any]) -> None:
        """Deprecated single-plan shim. Refuses once an account has more than
        one plan — guessing "the most recent one" here would risk a stale
        cached client silently overwriting a *different* rack than the one
        it has open. Current frontend never calls this endpoint."""
        validated = validate_plan(body)
        if isinstance(validated, str):
            self.send_error_json(400, validated)
            return

        now = utc_now()
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            existing = conn.execute(
                "SELECT id FROM plans WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
            if len(existing) > 1:
                self.send_error_json(
                    409,
                    "Account has multiple plans; use /api/plans/<id> instead of /api/me/plan",
                )
                return
            if existing:
                plan_id = existing[0]["id"]
                conn.execute(
                    """
                    UPDATE plans
                    SET rack_height = ?, devices = ?, connections = ?, next_id = ?,
                        name = COALESCE(?, name), power_budget_w = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        validated["rack_height"],
                        validated["devices"],
                        validated["connections"],
                        validated["next_id"],
                        validated["name"],
                        validated["power_budget_w"],
                        now,
                        plan_id,
                    ),
                )
            else:
                plan_id = uuid.uuid4().hex
                conn.execute(
                    """
                    INSERT INTO plans (id, rack_height, devices, connections, next_id, name, power_budget_w, user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        validated["rack_height"],
                        validated["devices"],
                        validated["connections"],
                        validated["next_id"],
                        validated["name"] or "Rack",
                        validated["power_budget_w"],
                        user["id"],
                        now,
                        now,
                    ),
                )
            conn.commit()

        self.send_json(200, {"id": plan_id, "updatedAt": now})

    def handle_list_my_plans(self) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            owned_rows = conn.execute(
                """
                SELECT id, name, rack_height, devices, updated_at
                FROM plans WHERE user_id = ? ORDER BY updated_at DESC
                """,
                (user["id"],),
            ).fetchall()
            shared_rows = conn.execute(
                """
                SELECT p.id, p.name, p.rack_height, p.devices, p.updated_at, c.role,
                       u.username AS owner_username, u.email AS owner_email
                FROM plan_collaborators c
                JOIN plans p ON p.id = c.plan_id
                JOIN users u ON u.id = p.user_id
                WHERE c.user_id = ?
                ORDER BY p.updated_at DESC
                """,
                (user["id"],),
            ).fetchall()

        def to_entry(row: sqlite3.Row, *, role: str, owner_label: str | None) -> dict[str, Any]:
            try:
                device_count = len(json.loads(row["devices"]))
            except (json.JSONDecodeError, TypeError):
                device_count = 0
            entry = {
                "id": row["id"],
                "name": row["name"] or "Rack",
                "rackHeight": row["rack_height"],
                "deviceCount": device_count,
                "updatedAt": row["updated_at"],
                "role": role,
            }
            if owner_label is not None:
                entry["ownerLabel"] = owner_label
            return entry

        result = [to_entry(row, role="owner", owner_label=None) for row in owned_rows]
        result += [
            to_entry(
                row,
                role=row["role"],
                owner_label=row["owner_username"] or row["owner_email"],
            )
            for row in shared_rows
        ]
        result.sort(key=lambda entry: entry["updatedAt"], reverse=True)
        self.send_json(200, result)

    def handle_create_my_plan(self, body: dict[str, Any]) -> None:
        try:
            rack_height = int(body.get("rackHeight", 25))
        except (TypeError, ValueError):
            self.send_error_json(400, "Invalid rack height")
            return
        if rack_height < 1 or rack_height > 48:
            self.send_error_json(400, "Invalid rack height")
            return
        name = normalize_plan_name(body.get("name")) or "Rack"

        now = utc_now()
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            # get_current_user() may have implicitly opened a transaction
            # (it purges expired sessions via DELETE); close it out before
            # starting our own explicit one.
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM plans WHERE user_id = ?", (user["id"],)
            ).fetchone()["n"]
            max_racks = license_module.get_max_racks(conn)
            if max_racks is not None and count >= max_racks:
                conn.execute("ROLLBACK")
                self.send_json(
                    403,
                    {
                        "error": "rack_limit_reached",
                        "limit": max_racks,
                        "tier": license_module.get_license_info(conn)["tier"],
                    },
                )
                return
            plan_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO plans (id, rack_height, devices, connections, next_id, name, user_id, created_at, updated_at)
                VALUES (?, ?, '[]', '[]', 1, ?, ?, ?, ?)
                """,
                (plan_id, rack_height, name, user["id"], now, now),
            )
            conn.commit()

        self.send_json(201, {"id": plan_id, "name": name, "rackHeight": rack_height, "updatedAt": now})

    def handle_delete_my_plan(self, plan_id: str) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            # See handle_create_my_plan: close out get_current_user()'s
            # implicit transaction before starting our own explicit one.
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                self.send_error_json(404, "Plan not found")
                return
            if get_plan_access(conn, row, user["id"]) != "owner":
                conn.execute("ROLLBACK")
                self.send_error_json(403, "Forbidden")
                return
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM plans WHERE user_id = ?", (user["id"],)
            ).fetchone()["n"]
            if count <= 1:
                conn.execute("ROLLBACK")
                self.send_error_json(409, "Cannot delete your last remaining rack")
                return
            conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
            conn.commit()

        self.send_json(200, {"deleted": True})

    def handle_list_my_equipment_types(self) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            rows = conn.execute(
                """
                SELECT id, name, height, color, power_w FROM custom_equipment_types
                WHERE user_id = ? ORDER BY created_at ASC
                """,
                (user["id"],),
            ).fetchall()
        self.send_json(
            200,
            [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "height": row["height"],
                    "color": row["color"],
                    "powerW": row["power_w"],
                }
                for row in rows
            ],
        )

    def handle_create_my_equipment_type(self, body: dict[str, Any]) -> None:
        name = normalize_plan_name(body.get("name"))
        if not name:
            self.send_error_json(400, "Name is required")
            return
        try:
            height = int(body.get("height"))
            power_w = int(body.get("powerW", 0))
        except (TypeError, ValueError):
            self.send_error_json(400, "Invalid height or power")
            return
        if height < 1 or height > 48:
            self.send_error_json(400, "Invalid height")
            return
        if power_w < 0:
            self.send_error_json(400, "Invalid power")
            return
        color = str(body.get("color", "")).strip()
        if not COLOR_RE.match(color):
            self.send_error_json(400, "Invalid color")
            return

        now = utc_now()
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM custom_equipment_types WHERE user_id = ?",
                (user["id"],),
            ).fetchone()["n"]
            max_types = license_module.get_max_custom_types(conn)
            if max_types is not None and count >= max_types:
                conn.execute("ROLLBACK")
                self.send_json(
                    403,
                    {
                        "error": "custom_type_limit_reached",
                        "limit": max_types,
                        "tier": license_module.get_license_info(conn)["tier"],
                    },
                )
                return
            type_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO custom_equipment_types (id, user_id, name, height, color, power_w, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (type_id, user["id"], name, height, color, power_w, now),
            )
            conn.commit()

        self.send_json(
            201,
            {"id": type_id, "name": name, "height": height, "color": color, "powerW": power_w},
        )

    def handle_delete_my_equipment_type(self, type_id: str) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            row = conn.execute(
                "SELECT user_id FROM custom_equipment_types WHERE id = ?", (type_id,)
            ).fetchone()
            if not row:
                self.send_error_json(404, "Not found")
                return
            if row["user_id"] != user["id"]:
                self.send_error_json(403, "Forbidden")
                return
            conn.execute("DELETE FROM custom_equipment_types WHERE id = ?", (type_id,))
            conn.commit()

        self.send_json(200, {"deleted": True})

    def handle_list_plan_snapshots(self, plan_id: str) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            plan_row = conn.execute(
                "SELECT * FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if not plan_row:
                self.send_error_json(404, "Plan not found")
                return
            if get_plan_access(conn, plan_row, user["id"]) is None:
                self.send_error_json(403, "Forbidden")
                return
            rows = conn.execute(
                """
                SELECT id, devices, created_at FROM plan_snapshots
                WHERE plan_id = ? ORDER BY created_at DESC
                """,
                (plan_id,),
            ).fetchall()
        result = []
        for row in rows:
            try:
                device_count = len(json.loads(row["devices"]))
            except (json.JSONDecodeError, TypeError):
                device_count = 0
            result.append(
                {"id": row["id"], "createdAt": row["created_at"], "deviceCount": device_count}
            )
        self.send_json(200, result)

    def handle_restore_plan_snapshot(self, plan_id: str, snapshot_id: str) -> None:
        now = utc_now()
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            plan_row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not plan_row:
                conn.execute("ROLLBACK")
                self.send_error_json(404, "Plan not found")
                return
            if get_plan_access(conn, plan_row, user["id"]) not in ("owner", "editor"):
                conn.execute("ROLLBACK")
                self.send_error_json(403, "Forbidden")
                return
            snapshot = conn.execute(
                "SELECT * FROM plan_snapshots WHERE id = ? AND plan_id = ?",
                (snapshot_id, plan_id),
            ).fetchone()
            if not snapshot:
                conn.execute("ROLLBACK")
                self.send_error_json(404, "Snapshot not found")
                return
            # Snapshot the current (pre-restore) state too, so the restore
            # itself isn't a one-way trip. force=True: always keep this one,
            # even if it lands inside another edit's throttle window.
            maybe_snapshot_plan(conn, plan_id, plan_row, force=True)
            conn.execute(
                """
                UPDATE plans
                SET rack_height = ?, devices = ?, next_id = ?, name = ?,
                    power_budget_w = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    snapshot["rack_height"],
                    snapshot["devices"],
                    snapshot["next_id"],
                    snapshot["name"],
                    snapshot["power_budget_w"],
                    now,
                    plan_id,
                ),
            )
            conn.commit()
            restored = row_to_plan(
                conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            )

        self.send_json(200, restored)

    def handle_list_plan_collaborators(self, plan_id: str) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            plan_row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not plan_row:
                self.send_error_json(404, "Plan not found")
                return
            if get_plan_access(conn, plan_row, user["id"]) != "owner":
                self.send_error_json(403, "Forbidden")
                return
            rows = conn.execute(
                """
                SELECT c.id, c.role, u.username, u.email
                FROM plan_collaborators c
                JOIN users u ON u.id = c.user_id
                WHERE c.plan_id = ?
                ORDER BY c.created_at ASC
                """,
                (plan_id,),
            ).fetchall()
        self.send_json(
            200,
            [
                {"id": r["id"], "role": r["role"], "label": r["username"] or r["email"]}
                for r in rows
            ],
        )

    def handle_create_plan_collaborator(self, plan_id: str, body: dict[str, Any]) -> None:
        email = str(body.get("email", "")).strip().lower()
        role = str(body.get("role", "")).strip()
        if not email or not EMAIL_RE.match(email):
            self.send_error_json(400, "Invalid email")
            return
        if role not in ("viewer", "editor"):
            self.send_error_json(400, "Invalid role")
            return

        now = utc_now()
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            plan_row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not plan_row:
                conn.execute("ROLLBACK")
                self.send_error_json(404, "Plan not found")
                return
            if get_plan_access(conn, plan_row, user["id"]) != "owner":
                conn.execute("ROLLBACK")
                self.send_error_json(403, "Forbidden")
                return
            target = conn.execute(
                "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
            ).fetchone()
            if not target:
                conn.execute("ROLLBACK")
                self.send_error_json(404, "No account with that email")
                return
            if target["id"] == plan_row["user_id"]:
                conn.execute("ROLLBACK")
                self.send_error_json(400, "That account already owns this rack")
                return
            if target["blocked"]:
                conn.execute("ROLLBACK")
                self.send_error_json(400, "That account is blocked")
                return
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM plan_collaborators WHERE plan_id = ?", (plan_id,)
            ).fetchone()["n"]
            max_collaborators = license_module.get_max_collaborators(conn)
            if max_collaborators is not None and count >= max_collaborators:
                conn.execute("ROLLBACK")
                self.send_json(
                    403,
                    {
                        "error": "collaborator_limit_reached",
                        "limit": max_collaborators,
                        "tier": license_module.get_license_info(conn)["tier"],
                    },
                )
                return
            collab_id = uuid.uuid4().hex
            try:
                conn.execute(
                    """
                    INSERT INTO plan_collaborators (id, plan_id, user_id, role, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (collab_id, plan_id, target["id"], role, now),
                )
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK")
                self.send_error_json(409, "That account already has access to this rack")
                return
            conn.commit()

        self.send_json(
            201,
            {"id": collab_id, "role": role, "label": target["username"] or target["email"]},
        )

    def handle_delete_plan_collaborator(self, plan_id: str, collaborator_id: str) -> None:
        with db_conn() as conn:
            user = get_current_user(conn, get_session_token(self))
            if not user:
                self.send_error_json(401, "Not authenticated")
                return
            plan_row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not plan_row:
                self.send_error_json(404, "Plan not found")
                return
            if get_plan_access(conn, plan_row, user["id"]) != "owner":
                self.send_error_json(403, "Forbidden")
                return
            conn.execute(
                "DELETE FROM plan_collaborators WHERE id = ? AND plan_id = ?",
                (collaborator_id, plan_id),
            )
            conn.commit()

        self.send_json(200, {"deleted": True})

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if handle_admin_get(self, path, DB_PATH):
            return

        if path == "/api/health":
            self.send_json(200, {"ok": True, "googleAuth": google_configured()})
            return
        if path == "/api/auth/providers":
            self.handle_auth_providers()
            return
        if path == "/api/auth/google":
            self.handle_google_start()
            return
        if path == "/api/auth/google/callback":
            self.handle_google_callback()
            return
        if path == "/api/email/preview":
            qs = parse_qs(urlparse(self.path).query)
            lang = normalize_lang(qs.get("lang", ["nl"])[0])
            test = qs.get("test", ["1"])[0] != "0"
            link = f"{APP_URL}/verify-email?token=preview"
            content = verification_email_content("register", lang, link, test=test)
            logo_url = f"{APP_URL}/icons/rackforge-avatar.png"
            html = build_verification_html(content, logo_src=logo_url, link=link)
            self.send_html(200, html)
            return
        if path.startswith("/api/avatars/"):
            user_id = path.split("/api/avatars/", 1)[1].strip("/")
            self.handle_get_avatar(user_id)
            return
        if path == "/api/auth/me":
            self.handle_me()
            return
        if path == "/api/auth/verify-email":
            qs = parse_qs(urlparse(self.path).query)
            token = qs.get("token", [""])[0]
            self.handle_verify_email(token)
            return
        if path == "/api/auth/reset-password":
            qs = parse_qs(urlparse(self.path).query)
            token = qs.get("token", [""])[0]
            self.handle_check_reset_token(token)
            return
        if path == "/api/me/plan":
            self.handle_get_my_plan()
            return
        if path == "/api/me/plans":
            self.handle_list_my_plans()
            return
        if path == "/api/me/equipment-types":
            self.handle_list_my_equipment_types()
            return

        snapshots_match = re.fullmatch(r"/api/plans/([a-f0-9]{32})/snapshots", path)
        if snapshots_match:
            self.handle_list_plan_snapshots(snapshots_match.group(1))
            return

        collaborators_match = re.fullmatch(r"/api/plans/([a-f0-9]{32})/collaborators", path)
        if collaborators_match:
            self.handle_list_plan_collaborators(collaborators_match.group(1))
            return

        if path.startswith("/api/plans/"):
            plan_id = path.split("/api/plans/", 1)[1].strip("/")
            if not PLAN_ID_RE.match(plan_id):
                self.send_error_json(400, "Invalid plan id")
                return
            with db_conn() as conn:
                row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
                if not row:
                    self.send_error_json(404, "Plan not found")
                    return
                user = get_current_user(conn, get_session_token(self))
                role = get_plan_access(conn, row, user["id"] if user else None)
                if role is None:
                    self.send_error_json(403, "Forbidden")
                    return
            self.send_json(200, row_to_plan(row, role=role))
            return

        if not path.startswith("/api/") and not path.startswith("/admin"):
            if self.serve_static(path):
                return

        self.send_error_json(404, "Not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if handle_admin_post(self, path, DB_PATH):
            return

        body = self.read_json()

        if path == "/api/auth/register":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_register(body)
            return
        if path == "/api/auth/login":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_login(body)
            return
        if path == "/api/auth/logout":
            self.handle_logout()
            return
        if path == "/api/auth/resend-verification":
            self.handle_resend_verification(body if isinstance(body, dict) else None)
            return
        if path == "/api/auth/forgot-password":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_forgot_password(body)
            return
        if path == "/api/auth/verify-reset-code":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_verify_reset_code(body)
            return
        if path == "/api/auth/reset-password":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_reset_password(body)
            return
        if path == "/api/me/account/delete":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_delete_account(body if isinstance(body, dict) else None)
            return

        if path == "/api/me/plans":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_create_my_plan(body if isinstance(body, dict) else {})
            return
        if path == "/api/me/equipment-types":
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_create_my_equipment_type(body if isinstance(body, dict) else {})
            return

        restore_match = re.fullmatch(
            r"/api/plans/([a-f0-9]{32})/snapshots/([a-f0-9]{32})/restore", path
        )
        if restore_match:
            self.handle_restore_plan_snapshot(restore_match.group(1), restore_match.group(2))
            return

        collaborators_match = re.fullmatch(r"/api/plans/([a-f0-9]{32})/collaborators", path)
        if collaborators_match:
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_create_plan_collaborator(
                collaborators_match.group(1), body if isinstance(body, dict) else {}
            )
            return

        if path != "/api/plans":
            self.send_error_json(404, "Not found")
            return
        if body is None:
            self.send_error_json(400, "Invalid JSON body")
            return

        validated = validate_plan(body)
        if isinstance(validated, str):
            self.send_error_json(400, validated)
            return

        plan_id = uuid.uuid4().hex
        now = utc_now()
        with db_conn() as conn:
            conn.execute(
                """
                INSERT INTO plans (id, rack_height, devices, connections, next_id, name, power_budget_w, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    plan_id,
                    validated["rack_height"],
                    validated["devices"],
                    validated["connections"],
                    validated["next_id"],
                    validated["name"],
                    validated["power_budget_w"],
                    now,
                    now,
                ),
            )
            conn.commit()

        self.send_json(201, {"id": plan_id, "updatedAt": now})

    def do_PUT(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/me/plan":
            body = self.read_json()
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_put_my_plan(body)
            return

        if path == "/api/me/account":
            body = self.read_json()
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_update_account(body)
            return

        if path == "/api/me/lang":
            body = self.read_json()
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_update_lang(body)
            return

        if path == "/api/me/avatar":
            body = self.read_json()
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_upload_avatar(body)
            return

        if not path.startswith("/api/plans/"):
            self.send_error_json(404, "Not found")
            return

        plan_id = path.split("/api/plans/", 1)[1].strip("/")
        if not PLAN_ID_RE.match(plan_id):
            self.send_error_json(400, "Invalid plan id")
            return

        body = self.read_json()
        if body is None:
            self.send_error_json(400, "Invalid JSON body")
            return

        validated = validate_plan(body)
        if isinstance(validated, str):
            self.send_error_json(400, validated)
            return

        now = utc_now()
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not row:
                self.send_error_json(404, "Plan not found")
                return
            user = get_current_user(conn, get_session_token(self))
            access = get_plan_access(conn, row, user["id"] if user else None)
            if access not in ("owner", "editor"):
                self.send_error_json(403, "Forbidden")
                return
            if row["user_id"] is not None:
                maybe_snapshot_plan(conn, plan_id, row)
            cur = conn.execute(
                """
                UPDATE plans
                SET rack_height = ?, devices = ?, connections = ?, next_id = ?,
                    name = COALESCE(?, name), power_budget_w = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    validated["rack_height"],
                    validated["devices"],
                    validated["connections"],
                    validated["next_id"],
                    validated["name"],
                    validated["power_budget_w"],
                    now,
                    plan_id,
                ),
            )
            conn.commit()
            if cur.rowcount == 0:
                self.send_error_json(404, "Plan not found")
                return

        self.send_json(200, {"id": plan_id, "updatedAt": now})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/me/account":
            body = self.read_json()
            if body is None:
                self.send_error_json(400, "Invalid JSON body")
                return
            self.handle_delete_account(body if isinstance(body, dict) else None)
            return
        if path == "/api/me/avatar":
            self.handle_delete_avatar()
            return
        collaborator_match = re.fullmatch(
            r"/api/plans/([a-f0-9]{32})/collaborators/([a-f0-9]{32})", path
        )
        if collaborator_match:
            self.handle_delete_plan_collaborator(
                collaborator_match.group(1), collaborator_match.group(2)
            )
            return
        if path.startswith("/api/plans/"):
            plan_id = path.split("/api/plans/", 1)[1].strip("/")
            if not PLAN_ID_RE.match(plan_id):
                self.send_error_json(400, "Invalid plan id")
                return
            self.handle_delete_my_plan(plan_id)
            return
        if path.startswith("/api/me/equipment-types/"):
            type_id = path.split("/api/me/equipment-types/", 1)[1].strip("/")
            if not CUSTOM_TYPE_ID_RE.match(type_id):
                self.send_error_json(400, "Invalid type id")
                return
            self.handle_delete_my_equipment_type(type_id)
            return
        self.send_error_json(404, "Not found")


def main() -> None:
    init_db()
    ensure_avatar_dir()
    server = ThreadingHTTPServer((HOST, PORT), Handler)

    scheme = "http"
    if TLS_ENABLED:
        if ensure_self_signed_cert(TLS_CERT, TLS_KEY):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=TLS_CERT, keyfile=TLS_KEY)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            scheme = "https"
        else:
            print("[tls] falling back to plain HTTP — set RACKFORGE_TLS=0 to silence this")

    print(f"RackForge listening on {scheme}://{HOST}:{PORT} (db={DB_PATH}, static={STATIC_DIR})")
    server.serve_forever()


if __name__ == "__main__":
    main()