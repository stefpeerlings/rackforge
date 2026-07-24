#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.request

SEARCH = os.environ.get("DEPLOY_HOST_OLD") or os.environ.get("DEPLOY_HOST") or sys.exit(
    "Zet DEPLOY_HOST (of DEPLOY_HOST_OLD) via 'source deploy.local.sh'"
)
ALSO_MATCH = os.environ.get("DEPLOY_HOST", SEARCH)
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
    if SEARCH in text or ALSO_MATCH in text:
        print(f"=== {label} ===")
        print(text[:3000])


page = 1
while True:
    r = get(f"/zones/{z}/dns_records?per_page=100&page={page}")
    for item in r.get("result", []):
        if SEARCH in item.get("content", "") or ALSO_MATCH in item.get("content", ""):
            print("DNS", item["type"], item["name"], "->", item["content"])
    if page >= r.get("result_info", {}).get("total_pages", 1):
        break
    page += 1

r = get(f"/accounts/{acc}/cfd_tunnel")
for tunnel in r.get("result", []):
    tid = tunnel["id"]
    cfg = get(f"/accounts/{acc}/cfd_tunnel/{tid}/configurations")
    dump_if_match(f"tunnel {tunnel.get('name')} ({tid})", cfg)