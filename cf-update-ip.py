#!/usr/bin/env python3
"""Update Cloudflare DNS/tunnel references from old server IP to new."""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

CERT_PATH = "/home/stef/.cloudflared/cert.pem"
OLD_IP = os.environ.get("DEPLOY_HOST_OLD") or sys.exit(
    "Zet DEPLOY_HOST_OLD (bv. via 'source deploy.local.sh')"
)
NEW_IP = os.environ.get("DEPLOY_HOST") or sys.exit(
    "Zet DEPLOY_HOST (bv. via 'source deploy.local.sh')"
)
TUNNEL_ID = os.environ.get("CF_TUNNEL_ID") or sys.exit(
    "Zet CF_TUNNEL_ID (bv. via 'source deploy.local.sh')"
)
DOMAIN = os.environ.get("CF_TUNNEL_DOMAIN") or sys.exit(
    "Zet CF_TUNNEL_DOMAIN (bv. via 'source deploy.local.sh')"
)
LAN_CIDR = os.environ.get("LAN_CIDR") or sys.exit(
    "Zet LAN_CIDR (bv. via 'source deploy.local.sh')"
)
LAN_PREFIX = LAN_CIDR.rsplit(".", 1)[0] + "."


def load_creds():
    pem = open(CERT_PATH).read()
    b64 = pem.split("-----BEGIN ARGO TUNNEL TOKEN-----")[1].split("-----END")[0].replace("\n", "")
    data = json.loads(base64.b64decode(b64))
    return data["apiToken"], data["zoneID"], data["accountID"]


def api(token, method, path, body=None):
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} {method} {path}")
        print(e.read().decode()[:600])
        return None


def list_dns(token, zone_id):
    records = []
    page = 1
    while True:
        data = api(token, "GET", f"/zones/{zone_id}/dns_records?per_page=100&page={page}")
        if not data or not data.get("success"):
            break
        records.extend(data["result"])
        if page >= data["result_info"]["total_pages"]:
            break
        page += 1
    return records


def main():
    token, zone_id, account_id = load_creds()

    print("=== DNS records (A/AAAA with local IPs) ===")
    records = list_dns(token, zone_id)
    updated = 0
    for rec in records:
        content = rec.get("content", "")
        if OLD_IP in content or (rec.get("type") in ("A", "AAAA") and content.startswith(LAN_PREFIX)):
            print(f"FOUND {rec['type']} {rec['name']} -> {content} (id={rec['id']})")
            if OLD_IP in content:
                new_content = content.replace(OLD_IP, NEW_IP)
                result = api(
                    token,
                    "PATCH",
                    f"/zones/{zone_id}/dns_records/{rec['id']}",
                    {
                        "type": rec["type"],
                        "name": rec["name"],
                        "content": new_content,
                        "proxied": rec.get("proxied", False),
                        "ttl": rec.get("ttl", 1),
                    },
                )
                if result and result.get("success"):
                    print(f"  UPDATED -> {new_content}")
                    updated += 1
                else:
                    print("  UPDATE FAILED")

    print(f"\nDNS updates: {updated}")

    print("\n=== Tunnel ingress ===")
    tunnel = api(token, "GET", f"/accounts/{account_id}/cfd_tunnel/{TUNNEL_ID}/configurations")
    if tunnel and tunnel.get("success"):
        ingress = tunnel.get("result", {}).get("config", {}).get("ingress", [])
        for rule in ingress:
            print(" ", rule)
        needs_tunnel_update = any(OLD_IP in json.dumps(ingress))
        if needs_tunnel_update:
            new_ingress = []
            for rule in ingress:
                new_rule = json.loads(json.dumps(rule).replace(OLD_IP, NEW_IP))
                new_ingress.append(new_rule)
            result = api(
                token,
                "PUT",
                f"/accounts/{account_id}/cfd_tunnel/{TUNNEL_ID}/configurations",
                {"config": {"ingress": new_ingress}},
            )
            print("tunnel update:", result.get("success") if result else False)
        else:
            print("tunnel ingress OK (uses localhost, no old IP)")

    print("\n=== Ensure CNAME tunnel routes ===")
    expected = {
        f"www.{DOMAIN}": f"{TUNNEL_ID}.cfargotunnel.com",
        DOMAIN: f"{TUNNEL_ID}.cfargotunnel.com",
    }
    for name, target in expected.items():
        matches = [r for r in records if r["name"] == name]
        if not matches:
            print(f"MISSING {name} -> creating CNAME to tunnel")
            result = api(
                token,
                "POST",
                f"/zones/{zone_id}/dns_records",
                {"type": "CNAME", "name": name, "content": target, "proxied": True, "ttl": 1},
            )
            print(" create:", result.get("success") if result else False)
        else:
            rec = matches[0]
            print(f"OK {rec['type']} {rec['name']} -> {rec['content']}")

    print("\nDone.")


if __name__ == "__main__":
    main()