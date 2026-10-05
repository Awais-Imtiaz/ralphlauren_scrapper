# 06 — Zyte sessions & SessionConfig (`session_configs.py`)

Library: **scrapy-zyte-api** (v0.36 here). The user-facing concepts:

## What a session is

A sticky combination of **one IP + one cookie jar + one browser context** that
survives across many requests. Normal proxy-per-request scraping starts fresh
every time; a session keeps looking like the *same shopper* — which is what
location-aware sites need.

## Session pools

Requests are grouped into pools by `SessionConfig.pool(request)`. With location
meta present, the pool id becomes:

```
www.ralphlauren.com@US,10001
```

→ **one pool per zip code**, automatically. All requests a zip generates share
that zip's session.

## Session initialization

The first request of each pool triggers an init request built by
`SessionConfig.params(request)`; the defaults (which we keep) are:

```python
{
    "browserHtml": True,
    "actions": [{"action": "setLocation", "address": {"addressCountry": "US",
                                                      "postalCode": "10001"}}],
}
```

Zyte API starts a headless browser, geolocates it to the zip (both IP-level and
browser geolocation API), and only then hands the session to the crawl.

## Session validation

`SessionConfig.check(response, request)` inspects the init response: if
`setLocation` failed (unsupported / blocked), the session is **discarded and
rebuilt**. Our config inherits this; you'd override `location_check()` to add
site-specific checks (e.g. "page shows my zip's store").

## Our config, fully

```python
@session_config(["www.ralphlauren.com"])
class RalphLaurenSessionConfig(LocationSessionConfig):
    ...
```

- `LocationSessionConfig` — a base class that routes its hooks to
  `location_params()` / `location_check()` only when a location is set (exactly
  our case).
- `@session_config([...])` — registers it for the domain; scrapy-zyte-api picks
  it up per-request.

Sessions are opted in **per request** by the mixin's meta
(`zyte_api_session_enabled: True`). Do NOT set `ZYTE_API_SESSION_ENABLED = True`
globally: it would session-ify even Scrapy's automatic `robots.txt` fetch —
a browser session just to read a text file, which can hang the whole crawl in
session-init retries. (Lesson from the first live run: 4+ minutes of
`Crawled 0 pages` heartbeats.)

## Sessions + everything else

- Requests in a session are paced (`ZYTE_API_SESSION_DELAY`, default 2s/pool) —
  sticky sessions must be treated gently.
- The `ZipStatsMiddleware` counts still apply; session init/reset events appear
  in logs with pool ids, so "which zip had session trouble" is answerable.
- In transparent mode (set by the addon) *every* request rides Zyte API;
  sessions layer on top of that.

## How to verify a session really is "in" its zip

Open the site in your own browser with a VPN to a different region — or during
a crawl, check that identical products differ across `output/<zip>.jsonl` files
(price/availability), and watch logs for pool ids per zip.
