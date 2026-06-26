#!/usr/bin/env python3
import base64
import json
import urllib.error
import urllib.request

pem = open("/home/stef/.cloudflared/cert.pem").read()
b64 = pem.split("-----BEGIN ARGO TUNNEL TOKEN-----")[1].split("-----END")[0].replace("\n", "")
d = json.loads(base64.b64decode(b64))
t, z, acc = d["apiToken"], d["zoneID"], d["accountID"]


def get(path):
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + path,
        headers={"Authorization": "Bearer " + t},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


print("=== All DNS records ===")
page = 1
while True:
    r = get(f"/zones/{z}/dns_records?per_page=100&page={page}")
    for item in r["result"]:
        print(
            item["type"],
            item["name"],
            "->",
            item["content"],
            "proxied=",
            item.get("proxied"),
        )
    if page >= r["result_info"]["total_pages"]:
        break
    page += 1

print("\n=== Tunnels ===")
r = get(f"/accounts/{acc}/cfd_tunnel")
for tunnel in r.get("result", []):
    print(tunnel.get("id"), tunnel.get("name"), tunnel.get("status"))