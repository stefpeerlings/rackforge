#!/usr/bin/env python3
"""Delete conflicting DNS records and route apex via cloudflared."""
import json
import os
import subprocess
import sys

TUNNEL_ID = os.environ.get("CF_TUNNEL_ID") or sys.exit(
    "Zet CF_TUNNEL_ID (bv. via 'source deploy.local.sh')"
)
DOMAIN = os.environ.get("CF_TUNNEL_DOMAIN") or sys.exit(
    "Zet CF_TUNNEL_DOMAIN (bv. via 'source deploy.local.sh')"
)
HOSTNAMES = [f"www.{DOMAIN}", DOMAIN]


def run(cmd):
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.stderr:
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode


def main():
    # List DNS records via cloudflared's cert-backed API using flarectl alternative
    # Use dig to see what exists
    for host in HOSTNAMES:
        run(["dig", "+short", host, "A"])
        run(["dig", "+short", host, "CNAME"])

    for host in HOSTNAMES:
        code = run([
            "cloudflared", "tunnel", "route", "dns", "-f",
            TUNNEL_ID, host,
        ])
        if code != 0:
            print(f"WARN: route dns failed for {host} (code {code})")

    print(f"\nDone. Test with: curl -sI https://www.{DOMAIN}/")


if __name__ == "__main__":
    main()