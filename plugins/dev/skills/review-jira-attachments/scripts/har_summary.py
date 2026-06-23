#!/usr/bin/env python3
"""Summarize a HAR capture so an agent can scan it without reading megabytes.

A HAR is often 5-15 MB — never read one whole; it will blow your context window.
This prints one compact line per request (index, method, status, path+query) so
you can scan for the request of interest, then drill into a single entry with
--detail to read off payloads and **entity IDs** — club / member / event / order
ids usually live in the request path, the query string, or the response body, so
the HAR is the first place to look for an ID before asking anyone for it.

Usage:
  har_summary.py FILE.har               # one line per request: <#> METHOD STATUS PATH?query
  har_summary.py FILE.har --failures    # only status 0 (no response / network error) or >= 400
  har_summary.py FILE.har --grep STR    # only requests whose URL contains STR (case-insensitive)
  har_summary.py FILE.har --detail N    # full request/response for entry #N (query params + bodies)
  har_summary.py FILE.har --max-body M  # truncate bodies to M chars in --detail (default 1500)
"""
import argparse, json, sys
from urllib.parse import urlsplit


def load_entries(path):
    with open(path) as fh:
        return json.load(fh)["log"]["entries"]


def path_with_query(url):
    s = urlsplit(url)
    return s.path + (("?" + s.query) if s.query else "")


def main():
    ap = argparse.ArgumentParser(description="Summarize a HAR capture.")
    ap.add_argument("har")
    ap.add_argument("--failures", action="store_true", help="only status 0 or >= 400")
    ap.add_argument("--grep", help="only URLs containing this substring (case-insensitive)")
    ap.add_argument("--detail", type=int, metavar="N", help="dump full request/response for entry #N")
    ap.add_argument("--max-body", type=int, default=1500, help="truncate bodies to this many chars (--detail)")
    args = ap.parse_args()

    entries = load_entries(args.har)

    if args.detail is not None:
        if not 0 <= args.detail < len(entries):
            sys.exit(f"no entry #{args.detail} (have 0..{len(entries) - 1})")
        e = entries[args.detail]
        req, resp = e["request"], e["response"]
        print(f"#{args.detail}  {req['method']} {resp['status']}  {req['url']}")
        for p in req.get("queryString") or []:
            print(f"  query: {p.get('name')}={p.get('value')}")
        body = (req.get("postData") or {}).get("text")
        if body:
            print("request body:", body[:args.max_body])
        rbody = (resp.get("content") or {}).get("text") or ""
        if rbody:
            print("response body:", rbody[:args.max_body])
        return

    shown = 0
    for i, e in enumerate(entries):
        req, resp = e["request"], e["response"]
        st = resp["status"]
        url = req["url"]
        if args.failures and not (st == 0 or st >= 400):
            continue
        if args.grep and args.grep.lower() not in url.lower():
            continue
        print(f"{i:<4} {req['method']:<6} {st:<5} {path_with_query(url)}")
        shown += 1
    print(f"\n{shown}/{len(entries)} request(s) shown"
          f"{' (failures only)' if args.failures else ''}"
          f"{f' matching {args.grep!r}' if args.grep else ''}.", file=sys.stderr)


if __name__ == "__main__":
    main()
