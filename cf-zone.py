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
        return {"error": e.code, "body": e.read()[:200]}

# zone details
for path in [
    f"/zones/{z}",
    f"/zones/{z}/dns_records?name=www.home-labe.com",
    f"/zones/{z}/dns_records?name=home-labe.com",
]:
    r = get(path)
    print(path)
    if "result" in r:
        if isinstance(r["result"], list):
            for item in r["result"]:
                print(" ", item.get("type"), item.get("name"), "->", item.get("content"), "proxied=", item.get("proxied"))
        else:
            print(" ", json.dumps(r["result"], indent=2)[:400])
    else:
        print(" ", r)