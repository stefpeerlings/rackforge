#!/usr/bin/env python3
"""Delete conflicting DNS records and route apex via cloudflared."""
import json
import subprocess
import sys

TUNNEL_ID = "468025c7-e709-4846-8cbc-a919aaf05deb"
DOMAIN = "home-labe.com"
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

    print("\nDone. Test with: curl -sI https://www.home-labe.com/")


if __name__ == "__main__":
    main()