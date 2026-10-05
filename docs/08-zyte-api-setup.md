# 08 — Zyte API setup (free tier for practice)

## Get a key

1. Sign up at **app.zyte.com** (Zyte API product).
2. Dashboard → *API keys* → create one.
3. `cp .env.example .env` and paste it:

```
ZYTE_API_KEY=your_key_here
ZIP_CODES=10001,90210,60601
```

`settings.py` loads `.env` with python-dotenv; `.gitignore` keeps it out of git.
`ZIP_CODES` flows env → settings (`ZIP_CODES`) → spider (`from_crawler`), with
5-digit validation; `-a zip_codes=` on the command line overrides it per run.
New signups get trial/free usage — check the dashboard's usage page for your
current plan's limits and remaining credit; don't assume a fixed number.

## How the key is used

```python
ZYTE_API_KEY = os.getenv("ZYTE_API_KEY")
```

`scrapy_zyte_api.Addon` (priority 500, after `scrapy_poet.Addon` at 400) wires
the download handler and enables **transparent mode** — every request the spider
makes is routed through Zyte API without spider code changes.

## Keeping the bill small while practicing

| Lever | Where |
|---|---|
| `page_limit_per_zip = 2` | spider — caps listing pages per zip |
| `-a zip_codes=10001` | CLI — one zip until things work |
| `CONCURRENT_REQUESTS_PER_DOMAIN = 2` | settings |
| `DOWNLOAD_DELAY = 1.0` + AutoThrottle | settings |
| Session init per zip = 1 extra browser request | remember when estimating |

Rough first-run cost: 3 zips × (1 session init + 2 listing pages + ~a few
product pages). Verify selectors with **one** zip first.

## Reading Zyte API responses in logs

- Session pools appear as `www.ralphlauren.com@US,10001`.
- 401/403 from the API itself → key problem, not the site.
- "Action setLocation not supported" → plan lacks browser actions; check plan
  features.
