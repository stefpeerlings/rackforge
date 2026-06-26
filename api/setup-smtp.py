#!/usr/bin/env python3
"""Write RackForge SMTP config for Zoho Mail EU."""
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "rackforge"
CONFIG_FILE = CONFIG_DIR / "smtp.env"

CONTENT = """# RackForge SMTP — Zoho Mail EU (netwerkengineer.com)
RACKFORGE_SMTP_HOST=smtp.zoho.eu
RACKFORGE_SMTP_PORT=587
RACKFORGE_SMTP_USER=noreply@netwerkengineer.com
RACKFORGE_SMTP_PASS=VERVANG_MET_ZOHO_APP_WACHTWOORD
RACKFORGE_SMTP_FROM=noreply RackForge <noreply@netwerkengineer.com>
RACKFORGE_APP_URL=https://www.home-labe.com
"""

def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(CONTENT, encoding="utf-8")
    CONFIG_FILE.chmod(0o600)
    print(f"Written: {CONFIG_FILE}")
    print("Edit RACKFORGE_SMTP_PASS with your Zoho app password, then:")
    print("  systemctl --user restart rackforge-api")

if __name__ == "__main__":
    main()