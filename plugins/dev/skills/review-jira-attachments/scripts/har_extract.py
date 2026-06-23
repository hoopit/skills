#!/usr/bin/env python3
"""Extract the full detail of every HAR request matching a method and/or path.

Companion to har_summary.py: once a scan points you at an endpoint, pull every
matching request in full — method, URL, query params, request body, response
status + body. Returns **all** matches (a HAR usually has the same endpoint
called many times), not just the first.

Matching:
  --path is a case-insensitive SUBSTRING match against the URL path (no query),
    so `--path /clubs` matches `/v3/clubs/123/members`. Omit to match any path.
  --method is exact (case-insensitive). Omit to match any method.

Usage:
  har_extract.py FILE.har --path /v3/payments
  har_extract.py FILE.har --path /clubs --method GET
  har_extract.py FILE.har --path /payments --json     # structured list for machine use
  har_extract.py FILE.har --path /clubs --max-body 4000
"""
import argparse, json, sys
from urllib.parse import urlsplit


def main():
    ap = argparse.ArgumentParser(description="Extract full detail of HAR requests by method/path.")
    ap.add_argument("har")
    ap.add_argument("--path", help="case-insensitive substring match on the URL path")
    ap.add_argument("--method", help="exact method match (case-insensitive)")
    ap.add_argument("--json", action="store_true", help="emit a JSON list instead of formatted text")
    ap.add_argument("--max-body", type=int, default=2000, help="truncate bodies to this many chars")
    args = ap.parse_args()

    with open(args.har) as fh:
        entries = json.load(fh)["log"]["entries"]

    want_path = args.path.lower() if args.path else None
    want_method = args.method.upper() if args.method else None

    matches = []
    for i, e in enumerate(entries):
        req, resp = e["request"], e["response"]
        if want_method and req["method"].upper() != want_method:
            continue
        if want_path and want_path not in urlsplit(req["url"]).path.lower():
            continue
        matches.append((i, req, resp))

    if args.json:
        out = [{
            "index": i,
            "method": req["method"],
            "url": req["url"],
            "status": resp["status"],
            "queryString": req.get("queryString") or [],
            "requestBody": ((req.get("postData") or {}).get("text") or "")[:args.max_body],
            "responseBody": ((resp.get("content") or {}).get("text") or "")[:args.max_body],
        } for i, req, resp in matches]
        print(json.dumps(out, indent=2))
        return

    if not matches:
        print(f"no requests matched"
              f"{f' method={args.method}' if args.method else ''}"
              f"{f' path~{args.path!r}' if args.path else ''} (of {len(entries)} entries).")
        return

    for n, (i, req, resp) in enumerate(matches):
        if n:
            print("\n" + "-" * 60)
        print(f"#{i}  {req['method']} {resp['status']}  {req['url']}")
        for p in req.get("queryString") or []:
            print(f"  query: {p.get('name')}={p.get('value')}")
        body = (req.get("postData") or {}).get("text")
        if body:
            print("request body:", body[:args.max_body])
        rbody = (resp.get("content") or {}).get("text") or ""
        if rbody:
            print("response body:", rbody[:args.max_body])
    print(f"\n{len(matches)}/{len(entries)} request(s) matched.", file=sys.stderr)


if __name__ == "__main__":
    main()
