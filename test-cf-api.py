#!/usr/bin/env python3
import base64, json, urllib.request, urllib.error

pem = open("/home/stef/.cloudflared/cert.pem").read()
b64 = pem.split("-----BEGIN ARGO TUNNEL TOKEN-----")[1].split("-----END")[0].replace("\n", "")
d = json.loads(base64.b64decode(b64))
t, z = d["apiToken"], d["zoneID"]

paths = [
    f"/zones/{z}/dns_records?per_page=1",
    f"/zones/{z}/pagerules",
    f"/zones/{z}/rulesets/phases/http_request_dynamic_redirect/entrypoint",
    f"/zones/{z}/settings/always_use_https",
]
for p in paths:
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + p,
        headers={"Authorization": "Bearer " + t},
    )
    try:
        with urllib.request.urlopen(req) as r:
            body = json.loads(r.read())
            print(p, "OK", "success=", body.get("success"))
    except urllib.error.HTTPError as e:
        print(p, "FAIL", e.code, e.read()[:120])