#!/usr/bin/env python3
"""Test RackForge SMTP configuration."""
from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "rackforge" / "smtp.env"
TO = os.environ.get("TEST_EMAIL_TO", "test@example.com")


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
        os.environ[key.strip()] = value.strip()
    return data


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

    if not host or not user or not password or password.startswith("VERVANG"):
        print("SMTP_INCOMPLETE: host, user or password missing")
        return 1

    msg = EmailMessage()
    msg["Subject"] = "RackForge SMTP test"
    msg["From"] = from_addr
    msg["To"] = TO
    msg.set_content(
        "Dit is een testmail van RackForge.\n\n"
        "Als je dit ontvangt, werkt SMTP correct.\n\n"
        "---\n"
        "Dit is een automatisch bericht van RackForge. "
        "Antwoorden op dit e-mailadres worden niet gelezen.\n"
    )

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            if port == 587:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as exc:
        print(f"SMTP_FAILED: {exc}")
        return 1

    print(f"SMTP_OK: test sent to {TO} from {user}")
    return 0


if __name__ == "__main__":
    sys.exit(main())