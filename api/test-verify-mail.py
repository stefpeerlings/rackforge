#!/usr/bin/env python3
"""Send verification-style test emails in NL and EN."""
from __future__ import annotations

import os
import secrets
import smtplib
import sys
from pathlib import Path

from email_templates import build_verification_message, verification_email_content

ENV_FILE = Path.home() / ".config" / "rackforge" / "smtp.env"
TO = os.environ.get("TEST_EMAIL_TO", "stef.peerlings@netwerkengineer.com")


def load_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def send_test(lang: str, host: str, port: int, user: str, password: str, from_addr: str, app_url: str) -> None:
    token = secrets.token_hex(32)
    link = f"{app_url}/verify-email?token={token}"
    content = verification_email_content("register", lang, link, test=True)
    msg = build_verification_message(
        to_email=TO,
        from_addr=from_addr,
        content=content,
        link=link,
        app_url=app_url,
    )

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        if port == 587:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(msg)

    print(f"SMTP_OK: {lang} HTML test sent to {TO}")


def main() -> int:
    if not ENV_FILE.exists():
        print(f"MISSING {ENV_FILE}")
        return 1

    load_env(ENV_FILE)
    host = os.environ.get("RACKFORGE_SMTP_HOST", "")
    port = int(os.environ.get("RACKFORGE_SMTP_PORT", "587"))
    user = os.environ.get("RACKFORGE_SMTP_USER", "")
    password = os.environ.get("RACKFORGE_SMTP_PASS", "")
    from_addr = os.environ.get("RACKFORGE_SMTP_FROM", user)
    app_url = os.environ.get("RACKFORGE_APP_URL", "https://10.0.40.12").rstrip("/")

    if not host or not user or not password:
        print("SMTP_INCOMPLETE")
        return 1

    try:
        for lang in ("nl", "en"):
            send_test(lang, host, port, user, password, from_addr, app_url)
    except Exception as exc:
        print(f"SMTP_FAILED: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())