#!/usr/bin/env python3
"""Dump MIME structure of a verification email (no send)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from email_templates import build_verification_message, find_logo_bytes, verification_email_content

content = verification_email_content("register", "en", "https://netwerkengineer.com/?verify-email=test", test=True)
link = "https://netwerkengineer.com/?verify-email=test"
msg = build_verification_message(
    to_email="test@example.com",
    from_addr="noreply RackForge <noreply@netwerkengineer.com>",
    content=content,
    link=link,
    app_url="https://netwerkengineer.com",
)

print("LOGO_BYTES:", len(find_logo_bytes() or b""))
print("CONTENT_TYPE:", msg.get_content_type())
for i, part in enumerate(msg.walk()):
    if i == 0:
        continue
    payload = part.get_payload(decode=False)
    plen = len(payload) if isinstance(payload, str) else len(payload or b"")
    cid = part.get("Content-ID", "")
    print(f"  part {i}: {part.get_content_type()} charset={part.get_content_charset()} len={plen} cid={cid}")

raw = msg.as_string()
print("RAW_HAS_HTML:", "<!DOCTYPE html>" in raw)
print("RAW_HAS_CID:", "cid:rackforge-logo" in raw)
print("RAW_LEN:", len(raw))