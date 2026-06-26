#!/usr/bin/env python3
import base64, json, urllib.request, urllib.error

pem = open("/home/stef/.cloudflared/cert.pem").read()
b64 = pem.split("-----BEGIN ARGO TUNNEL TOKEN-----")[1].split("-----END")[0].replace("\n", "")
d = json.loads(base64.b64decode(b64))
t, acc = d["apiToken"], d["accountID"]
tid = "468025c7-e709-4846-8cbc-a919aaf05deb"

def api(path, method="GET", body=None):
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4" + path,
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={"Authorization": "Bearer " + t, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(e.code, method, path)
        print(e.read().decode()[:500])
        return None

config = {
    "config": {
        "ingress": [
            {"hostname": "www.home-labe.com", "service": "http://localhost:80"},
            {"hostname": "home-labe.com", "service": "http://localhost:80"},
            {"service": "http_status:404"},
        ]
    }
}

for method in ("PUT", "POST", "PATCH"):
    print(f"\n=== {method} configuration ===")
    r = api(f"/accounts/{acc}/cfd_tunnel/{tid}/configurations", method, config)
    if r:
        print(json.dumps(r, indent=2)[:600])