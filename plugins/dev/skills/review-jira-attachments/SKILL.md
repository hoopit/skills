---
name: review-jira-attachments
description: Download and analyze the files attached to a Jira issue — HAR network captures, screenshots, logs, PDFs — via the Jira REST API, because acli cannot download attachments. Use whenever a Jira issue/ticket has attached files you need to inspect to understand or reproduce a bug: parse a HAR for the failing request, view a screenshot, or grep a log. Don't ask the reporter to "review the HAR" — read it yourself.
---

# Review Jira Attachments

Attachments are often the single most useful evidence on a bug ticket: **HAR files** (a full browser
network capture at the moment of the failure), screenshots, and logs. They usually pin the exact failing
endpoint or screen. **Always download and analyze them yourself — never ask the reporter to "review the
HAR" or describe a screenshot they already attached.**

## acli cannot download attachments — use the REST API

`acli jira workitem attachment` only supports `list` / `delete`, **not download**. Downloading goes
through the Jira REST API with a **Jira API token** (Basic auth).

Set `JIRA_API_TOKEN` + `JIRA_EMAIL` (Hoopit: `set -a; . ~/.config/hoopit/jira.env; set +a`) and take
`$JIRA_BASE_URL` from the repo's CLAUDE.md (e.g. `https://hoopit.atlassian.net`).

```bash
A=(-u "$JIRA_EMAIL:$JIRA_API_TOKEN")

# 1. List attachments (id | filename | mimeType | size)
curl -s "${A[@]}" -H 'Accept: application/json' "$JIRA_BASE_URL/rest/api/3/issue/<KEY>?fields=attachment" \
  | python3 -c "import json,sys;[print(x['id'],x['filename'],x['mimeType'],x['size']) for x in json.load(sys.stdin)['fields'].get('attachment',[])]"

# 2. Download one by id (-L follows the redirect to media storage)
curl -sL "${A[@]}" "$JIRA_BASE_URL/rest/api/3/attachment/content/<ID>" -o /tmp/<KEY>-<filename>
```

## HAR files — parse, don't read

HARs are often **5–15 MB**. Never read one into context whole — it will blow your context window. Use
the bundled `scripts/har_summary.py` to scan it (one compact line per request: `# METHOD STATUS PATH?query`),
then drill into only the entries that matter:

```bash
HAR=$(find ~/.claude/plugins -path '*review-jira-attachments/scripts/har_summary.py' | head -1)
python3 "$HAR" /tmp/<KEY>-file.har               # full scan — spot the request(s) of interest
python3 "$HAR" /tmp/<KEY>-file.har --failures    # only status 0 (network error) or >= 400
python3 "$HAR" /tmp/<KEY>-file.har --grep clubs  # only URLs containing a substring
python3 "$HAR" /tmp/<KEY>-file.har --detail 7    # full request/response for entry #7: query params + bodies
```

From the entry of interest read off the **endpoint, method, request payload shape, and error response
body** — that usually identifies the exact view/serializer/component to investigate. Note the request
that fired immediately before a failure (timing/sequence often matters). If nothing is `>= 400`, scan
2xx responses whose body contains an error message matching the reported symptom.

When a scan points you at an endpoint and you want **every** call to it (the same endpoint usually fires
many times), use `scripts/har_extract.py` — it matches by method + path substring and returns all matches
in full (query params + request/response bodies), with `--json` for structured output:

```bash
EXT=$(find ~/.claude/plugins -path '*review-jira-attachments/scripts/har_extract.py' | head -1)
python3 "$EXT" /tmp/<KEY>-file.har --path /v3/payments              # every payments request, full detail
python3 "$EXT" /tmp/<KEY>-file.har --path /clubs --method GET       # narrow by method
python3 "$EXT" /tmp/<KEY>-file.har --path /clubs --json             # structured list
```

**The HAR is also the first place to find prod entity IDs.** Club / member / event / order / payment ids
the reporter never typed into the ticket are usually right there in a request path (`/clubs/123/…`), the
query string (`?member=456`), or a response body — `har_summary.py --detail N` or `har_extract.py` print
all three. Look there before asking anyone for an ID.

## Screenshots / images

Download as above, then use the **Read tool** on the file path — it renders images visually. Use them to
confirm which screen/state the reporter is describing.

## Other attachments

- **Plain-text logs** — download and `grep` for error/exception/traceback lines; don't cat the whole file.
- **PDFs** — use the **Read tool** (it supports PDFs).
- **Office docs / archives** — extract or convert as needed, or fall back to asking what's relevant only
  if the format is genuinely unreadable.

## Notes

- Filenames can contain spaces — quote the `-o` target path.
- The `content/<ID>` endpoint 302-redirects to media storage; `-L` is required to follow it.
- A `401/403` means the token/email is wrong or unset; a `404` means a bad attachment id (re-list).
