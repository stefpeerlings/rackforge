"""Google OAuth 2.0 helpers (stdlib only)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

GOOGLE_CLIENT_ID = os.environ.get("RACKFORGE_GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("RACKFORGE_GOOGLE_CLIENT_SECRET", "").strip()
APP_URL = os.environ.get("RACKFORGE_APP_URL", "https://10.0.40.12").rstrip("/")


def google_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    return f"{APP_URL}/api/auth/google/callback"


def build_auth_url(*, state: str, lang: str) -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
        "hl": lang if lang in ("nl", "en") else "nl",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _post_form(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def exchange_code(code: str) -> dict:
    return _post_form(
        GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        },
    )


def fetch_userinfo(access_token: str) -> dict:
    req = urllib.request.Request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))