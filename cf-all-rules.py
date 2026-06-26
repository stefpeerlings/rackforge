#!/usr/bin/env python3
import base64, json, urllib.request, urllib.error

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
    except urllib.error.HTTPError as e:
        return {"_err": e.code, "_body": e.read().decode()[:300]}

checks = [
    f"/zones/{z}/pagerules",
    f"/zones/{z}/rulesets/phases/http_request_dynamic_redirect/entrypoint",
    f"/zones/{z}/rulesets/phases/http_request_redirect/entrypoint",
    f"/zones/{z}/rulesets/phases/http_response_headers_transform/entrypoint",
    f"/zones/{z}/rulesets/phases/http_request_transform/entrypoint",
    f"/zones/{z}/workers/routes",
    f"/accounts/{acc}/workers/scripts",
    f"/zones/{z}/settings/normalize_r_urls_to_origin",
    f"/zones/{z}/settings/always_use_https",
]
for p in checks:
    r = get(p)
    print("\n", p)
    if "_err" in r:
        print(" ERR", r["_err"], r["_body"][:120])
    elif isinstance(r.get("result"), list):
        print(" count", len(r["result"]))
        for item in r["result"][:5]:
            print(" ", json.dumps(item)[:200])
    elif isinstance(r.get("result"), dict):
        rules = r["result"].get("rules", r["result"])
        print(" ", json.dumps(rules, indent=2)[:500])
    else:
        print(" ", r)