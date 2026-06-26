#!/usr/bin/env python3
import base64
import json
import urllib.request

SEARCH = "10.0.40.11"
pem = open("/home/stef/.cloudflared/cert.pem").read()
b64 = pem.split("-----BEGIN ARGO TUNNEL TOKEN-----")[1].split("-----END")[0].replace("\n", "")
d = json.loads(base64.b64decode(b64))
t, z, acc = d["apiToken"], d["zoneID"], d["accountID"]


def get(path):
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + path,
        headers={"Authorization": "Bearer " + t},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def dump_if_match(label, data):
    text = json.dumps(data)
    if SEARCH in text or "10.0.40.12" in text:
        print(f"=== {label} ===")
        print(text[:3000])


page = 1
while True:
    r = get(f"/zones/{z}/dns_records?per_page=100&page={page}")
    for item in r.get("result", []):
        if SEARCH in item.get("content", "") or "10.0.40.12" in item.get("content", ""):
            print("DNS", item["type"], item["name"], "->", item["content"])
    if page >= r.get("result_info", {}).get("total_pages", 1):
        break
    page += 1

r = get(f"/accounts/{acc}/cfd_tunnel")
for tunnel in r.get("result", []):
    tid = tunnel["id"]
    cfg = get(f"/accounts/{acc}/cfd_tunnel/{tid}/configurations")
    dump_if_match(f"tunnel {tunnel.get('name')} ({tid})", cfg)