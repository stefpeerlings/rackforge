#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.request

TUNNEL_ID = os.environ.get("CF_TUNNEL_ID") or sys.exit(
    "Zet CF_TUNNEL_ID (bv. via 'source deploy.local.sh')"
)

pem = open("/home/stef/.cloudflared/cert.pem").read()
b64 = pem.split("-----BEGIN ARGO TUNNEL TOKEN-----")[1].split("-----END")[0].replace("\n", "")
d = json.loads(base64.b64decode(b64))
token, account_id = d["apiToken"], d["accountID"]

req = urllib.request.Request(
    f"https://api.cloudflare.com/client/v4/accounts/{account_id}/cfd_tunnel/{TUNNEL_ID}/configurations",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req) as resp:
    print(json.dumps(json.loads(resp.read()), indent=2))