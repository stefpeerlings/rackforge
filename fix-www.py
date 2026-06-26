#!/usr/bin/env python3
import base64
import json
import urllib.error
import urllib.request

CERT_PATH = "/home/stef/.cloudflared/cert.pem"
TUNNEL_ID = "468025c7-e709-4846-8cbc-a919aaf05deb"


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


def main():
    token, zone_id, account_id = load_creds()

    # 1) Tunnel: route both apex and www to Caddy
    config = {
        "config": {
            "ingress": [
                {"hostname": "www.home-labe.com", "service": "http://localhost:80"},
                {"hostname": "home-labe.com", "service": "http://localhost:80"},
                {"service": "http_status:404"},
            ]
        }
    }
    print("=== Update tunnel ingress ===")
    r = api(token, "PUT", f"/accounts/{account_id}/cfd_tunnel/{TUNNEL_ID}/configurations", config)
    if r:
        print("tunnel config:", r.get("success"), r.get("errors"))

    # 2) Read redirect rules
    phase = "http_request_dynamic_redirect"
    path = f"/zones/{zone_id}/rulesets/phases/{phase}/entrypoint"
    print("\n=== Read redirect rules ===")
    data = api(token, "GET", path)
    if not data or not data.get("success"):
        print("Cannot read redirect rules (token lacks permission).")
        print("Open: https://dash.cloudflare.com/{}/home-labe.com/rules/redirect-rules".format(account_id))
        return

    result = data["result"]
    ruleset_id = result["id"]
    rules = result.get("rules", [])
    print(f"rules={len(rules)}")
    for rule in rules:
        print(json.dumps(rule, indent=2)[:500])

    # Remove www -> apex, keep apex -> www if present
    new_rules = []
    for rule in rules:
        expr = rule.get("expression", "")
        params = json.dumps(rule.get("action_parameters", {}))
        if "www.home-labe.com" in expr and "home-labe.com" in expr and "www" in expr:
            print("SKIP www->apex:", rule.get("description", expr))
            continue
        if "www.home-labe.com" in params and expr.count("www") == 0:
            print("SKIP redirect stripping www:", rule.get("description", ""))
            continue
        new_rules.append(rule)

    has_apex_to_www = any(
        "home-labe.com" in r.get("expression", "") and "www.home-labe.com" in json.dumps(r.get("action_parameters", {}))
        for r in new_rules
    )
    if not has_apex_to_www:
        new_rules.insert(0, {
            "description": "Apex naar www",
            "expression": '(http.host eq "home-labe.com")',
            "action": "redirect",
            "action_parameters": {
                "from_value": {"status_code": 301, "preserve_query_string": True},
                "to_value": {
                    "target_url": {"expression": 'concat("https://www.home-labe.com", http.request.uri.path)'},
                    "status_code": 301,
                    "preserve_query_string": True,
                },
            },
        })

    if len(new_rules) != len(rules) or not has_apex_to_www:
        print("\n=== Update redirect rules ===")
        put = api(token, "PUT", f"/zones/{zone_id}/rulesets/{ruleset_id}", {"rules": new_rules})
        if put:
            print("redirect update:", put.get("success"), put.get("errors"))


if __name__ == "__main__":
    main()