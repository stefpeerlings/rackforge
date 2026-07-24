#!/usr/bin/env python3
"""Vendor-only CLI to generate license keypairs and issue license keys.

NEVER deploy this script (or the private key it produces) to a customer's
server — it exists purely for the vendor's own machine. `license.py` (the
piece that ships with the app) only ever holds the *public* key.

Usage:
    python3 issue_license.py genkey [--out DIR]
    python3 issue_license.py issue --tier {community,pro,enterprise} \\
        --customer "Acme Inc" [--expires YYYY-MM-DD] \\
        --private-key PATH
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LICENSE_TIERS = ("community", "pro", "enterprise")
_EXP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def cmd_genkey(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    priv_path = out_dir / "license_signing_key.pem"
    pub_path = out_dir / "license_public_key.pem"

    if priv_path.exists() and not args.force:
        print(f"Refusing to overwrite existing {priv_path} (use --force)", file=sys.stderr)
        return 1

    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(priv_path)],
        check=True,
    )
    fd = os.open(priv_path, os.O_WRONLY)
    os.fchmod(fd, 0o600)
    os.close(fd)

    subprocess.run(
        ["openssl", "pkey", "-in", str(priv_path), "-pubout", "-out", str(pub_path)],
        check=True,
    )

    print(f"Private key (KEEP SECRET, never commit/deploy): {priv_path}")
    print(f"Public key (paste into api/license.py PUBLIC_KEY_PEM): {pub_path}\n")
    print(pub_path.read_text())
    return 0


def cmd_issue(args: argparse.Namespace) -> int:
    if args.expires and not _EXP_RE.match(args.expires):
        print("--expires must be in YYYY-MM-DD format", file=sys.stderr)
        return 1

    private_key = Path(args.private_key)
    if not private_key.is_file():
        print(f"Private key not found: {private_key}", file=sys.stderr)
        return 1

    payload: dict[str, object] = {"tier": args.tier, "customer": args.customer}
    if args.expires:
        payload["exp"] = args.expires
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        payload_path = tmp_path / "payload.bin"
        sig_path = tmp_path / "sig.bin"
        payload_path.write_bytes(payload_bytes)
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-inkey",
                str(private_key),
                "-rawin",
                "-in",
                str(payload_path),
                "-out",
                str(sig_path),
            ],
            check=True,
        )
        signature_bytes = sig_path.read_bytes()

    license_key = f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature_bytes)}"
    print(license_key)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_genkey = sub.add_parser("genkey", help="Generate a new signing keypair")
    p_genkey.add_argument("--out", default=".", help="Output directory (default: cwd)")
    p_genkey.add_argument("--force", action="store_true", help="Overwrite existing key")
    p_genkey.set_defaults(func=cmd_genkey)

    p_issue = sub.add_parser("issue", help="Issue a signed license key")
    p_issue.add_argument("--tier", required=True, choices=LICENSE_TIERS)
    p_issue.add_argument("--customer", required=True, help="Customer name/identifier")
    p_issue.add_argument("--expires", default="", help="Optional YYYY-MM-DD expiry date")
    p_issue.add_argument("--private-key", required=True, help="Path to signing private key")
    p_issue.set_defaults(func=cmd_issue)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
