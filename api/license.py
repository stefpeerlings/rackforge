"""RackForge license tiers — local, offline, cryptographically signed.

No license server: a license key is an Ed25519-signed JSON payload. Verification
shells out to the system `openssl` CLI (Ed25519 needs `pkeyutl -rawin`, only
present in the CLI since OpenSSL 3.0) instead of adding a pip dependency, to
keep this app's zero-dependency, single-file `python3 server.py` deploy model.

Only the *public* key lives in this file. Issuing new license keys requires
`issue_license.py` plus a private key that must never be shipped with the app.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

# Public key only — verification-only, safe to ship. Generated via
# `python3 issue_license.py genkey` on a dedicated, offline-from-the-app
# signing host — the matching private key never leaves that machine.
# Whoever holds the private key can mint valid licenses for any tier, so
# treat it as the entire security boundary of this feature.
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAlFfcdItUURfjtzLn4GCQ/RZeTTeugEig4HepRIjP9Bo=
-----END PUBLIC KEY-----
"""

LICENSE_TIERS = ("community", "pro", "enterprise")
TIER_RACK_LIMITS: dict[str, int | None] = {
    "community": 1,
    "pro": 5,
    "enterprise": None,  # unlimited
}
TIER_CUSTOM_TYPE_LIMITS: dict[str, int | None] = {
    "community": 0,
    "pro": 10,
    "enterprise": None,  # unlimited
}
# Snapshots keep growing over time (unlike a rack/type count), so even the
# top tier gets a finite ceiling to bound storage growth per plan.
TIER_SNAPSHOT_LIMITS: dict[str, int] = {
    "community": 3,
    "pro": 20,
    "enterprise": 100,
}
SNAPSHOT_MIN_INTERVAL_SECONDS = 10 * 60
TIER_COLLABORATOR_LIMITS: dict[str, int | None] = {
    "community": 0,
    "pro": 3,
    "enterprise": None,  # unlimited
}

_EXP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Keyed by the resolved license-key string (or None) so a key change — via the
# admin UI or a changed env var/file — is picked up on the next call instead
# of requiring a process restart, while repeated calls with an unchanged key
# don't re-shell out to openssl every time.
_verify_cache: dict[str | None, dict[str, Any]] = {}


def ensure_license_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS license_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            license_key TEXT
        )
        """
    )
    conn.commit()


def get_stored_license_key(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT license_key FROM license_settings WHERE id = 1"
    ).fetchone()
    if row is None:
        return None
    key = row["license_key"] if hasattr(row, "keys") else row[0]
    return key or None


def set_stored_license_key(conn: sqlite3.Connection, key_str: str | None) -> None:
    """Does not commit — caller controls the transaction (see admin_panel.py's
    handle_admin_action, which logs an audit entry in the same transaction)."""
    conn.execute(
        """
        INSERT INTO license_settings (id, license_key) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET license_key = excluded.license_key
        """,
        (key_str,),
    )


def _b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("ascii"))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _openssl_verify(payload_bytes: bytes, signature_bytes: bytes) -> bool:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pub_path = tmp_path / "pub.pem"
            payload_path = tmp_path / "payload.bin"
            sig_path = tmp_path / "sig.bin"
            pub_path.write_text(PUBLIC_KEY_PEM)
            payload_path.write_bytes(payload_bytes)
            sig_path.write_bytes(signature_bytes)
            result = subprocess.run(
                [
                    "openssl",
                    "pkeyutl",
                    "-verify",
                    "-pubin",
                    "-inkey",
                    str(pub_path),
                    "-rawin",
                    "-in",
                    str(payload_path),
                    "-sigfile",
                    str(sig_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                if "unknown option" in stderr.lower() or "-rawin" in stderr.lower():
                    print(
                        "[license] openssl does not support 'pkeyutl -rawin' for "
                        "Ed25519 (requires OpenSSL >= 3.0) — falling back to "
                        f"community tier. openssl said: {stderr}"
                    )
                else:
                    print(f"[license] signature verification failed: {stderr or 'invalid signature'}")
                return False
            return True
    except FileNotFoundError:
        print(
            "[license] 'openssl' binary not found on PATH — cannot verify "
            "license keys, falling back to community tier"
        )
        return False


def _parse_license_key(key_str: str) -> dict[str, Any] | None:
    parts = key_str.strip().split(".")
    if len(parts) != 2:
        print("[license] malformed license key (expected 'payload.signature')")
        return None
    try:
        payload_bytes = _b64url_decode(parts[0])
        signature_bytes = _b64url_decode(parts[1])
    except Exception:
        print("[license] malformed license key (base64 decode failed)")
        return None

    if not _openssl_verify(payload_bytes, signature_bytes):
        return None

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        print("[license] license payload is not valid JSON")
        return None

    if not isinstance(payload, dict) or payload.get("tier") not in LICENSE_TIERS:
        print("[license] license payload missing a valid 'tier'")
        return None

    exp = payload.get("exp")
    if exp is not None:
        if not isinstance(exp, str) or not _EXP_RE.match(exp):
            print("[license] license 'exp' field is not a valid YYYY-MM-DD date")
            return None
        try:
            exp_date = date.fromisoformat(exp)
        except ValueError:
            print("[license] license 'exp' field is not a valid calendar date")
            return None
        if exp_date < date.today():
            print(f"[license] license expired on {exp}")
            return None

    return payload


def _read_license_key_source(conn: sqlite3.Connection | None = None) -> str | None:
    # Env var / file take priority — useful for scripted or air-gapped
    # deployments. Otherwise fall back to whatever was saved via the admin UI.
    key = os.environ.get("RACKFORGE_LICENSE_KEY", "").strip()
    if key:
        return key
    path = os.environ.get("RACKFORGE_LICENSE_FILE", "").strip()
    if path:
        try:
            return Path(path).read_text().strip()
        except OSError:
            print(f"[license] could not read RACKFORGE_LICENSE_FILE at {path}")
    if conn is not None:
        return get_stored_license_key(conn)
    return None


def get_license_info(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    key_str = _read_license_key_source(conn)
    if key_str in _verify_cache:
        return _verify_cache[key_str]

    fallback = {"tier": "community", "valid": False, "customer": None, "expires": None}
    if not key_str:
        _verify_cache[key_str] = fallback
        return fallback

    payload = _parse_license_key(key_str)
    if payload is None:
        _verify_cache[key_str] = fallback
        return fallback

    info = {
        "tier": payload["tier"],
        "valid": True,
        "customer": payload.get("customer"),
        "expires": payload.get("exp"),
    }
    _verify_cache[key_str] = info
    return info


def get_max_racks(conn: sqlite3.Connection | None = None) -> int | None:
    return TIER_RACK_LIMITS[get_license_info(conn)["tier"]]


def get_max_custom_types(conn: sqlite3.Connection | None = None) -> int | None:
    return TIER_CUSTOM_TYPE_LIMITS[get_license_info(conn)["tier"]]


def get_max_snapshots(conn: sqlite3.Connection | None = None) -> int:
    return TIER_SNAPSHOT_LIMITS[get_license_info(conn)["tier"]]


def get_max_collaborators(conn: sqlite3.Connection | None = None) -> int | None:
    return TIER_COLLABORATOR_LIMITS[get_license_info(conn)["tier"]]


def verify_license_key_string(key_str: str) -> dict[str, Any] | None:
    """Validate a license key string on its own, independent of env vars or
    stored state — used by the admin UI to check a key before saving it."""
    return _parse_license_key(key_str)
