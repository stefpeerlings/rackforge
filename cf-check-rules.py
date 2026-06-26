#!/usr/bin/env python3
import base64, json, urllib.request, urllib.error

pem = open("/home/stef/.cloudflared/cert.pem").read()
b64 = pem.split("-----BEGIN ARGO TUNNEL TOKEN-----")[1].split("-----END")[0].replace("\n", "")
d = json.loads(base64.b64decode(b64))
t, z = d["apiToken"], d["zoneID"]

def get(path):
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + path,
        headers={"Authorization": "Bearer " + t},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"err": e.code, "body": e.read().decode()[:200]}

for phase in ["http_request_dynamic_redirect", "http_request_redirect"]:
    r = get(f"/zones/{z}/rulesets/phases/{phase}/entrypoint")
    print(f"\n=== {phase} ===")
    if "err" in r:
        print("API", r["err"])
    else:
        rules = r.get("result", {}).get("rules", [])
        print(f"rules: {len(rules)}")
        for rule in rules:
            print(json.dumps(rule, indent=2)[:400])